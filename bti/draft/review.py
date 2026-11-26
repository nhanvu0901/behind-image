"""Strict result handling and bounded repair loop for viewer review.

The caller supplies the reviewer and the existing scoped editor; this module does
not start agents or write to a project on its own.
"""
from __future__ import annotations

ISSUE_CODES = {
    "picture_mismatch": "review_picture_mismatch",
    "text_wrong": "review_text_wrong",
    "context_missing": "review_context_missing",
    "picture_repeated": "review_picture_repeated",
}
CODES = frozenset(ISSUE_CODES)
DRAFT_REPAIR_CODES = frozenset({"outside_on_painting", "outside_picture_brief", "outside_picture_dropped"})


class ReviewError(ValueError):
    """The reviewer did not return a complete, usable answer."""


def _draft_repair_issues(project_dir, ids) -> list[dict]:
    """Read compiled draft warnings about unseen or brief outside pictures for repair rounds."""
    try:
        from bti.engine.api import open_project
        issues = open_project(project_dir).validate()
    except Exception:       # noqa: BLE001 - minimal test fixtures without timing/picks have no validate warnings
        return []
    return [i for i in issues if isinstance(i, dict) and i.get("code") in DRAFT_REPAIR_CODES]


def _index_draft_issues(ids, raw_issues) -> dict[str, list[dict]]:
    """Map draft warnings of `DRAFT_REPAIR_CODES` onto current shot ids."""
    import re
    expected = set(ids)
    out: dict[str, list[dict]] = {}
    seen: set[tuple[str, str, str]] = set()
    for i in raw_issues or []:
        if not isinstance(i, dict):
            continue
        code = i.get("code")
        if code not in DRAFT_REPAIR_CODES:
            continue
        args = i.get("args") if isinstance(i.get("args"), dict) else {}
        sid = args.get("shot") or i.get("shot")
        if not (isinstance(sid, str) and sid in expected):
            m = re.match(r"shots\[(\d+)\]", str(i.get("path") or ""))
            idx = int(m.group(1)) if m else None
            sid = ids[idx] if idx is not None and 0 <= idx < len(ids) else None
        if not sid or sid not in expected:
            continue
        detail = str(i.get("message") or code).strip()[:350]
        if not detail:
            detail = code
        key = (sid, code, detail)
        if key in seen:
            continue
        seen.add(key)
        out.setdefault(sid, []).append({"code": code, "detail": detail})
    return out


def _build_repair_batches(ids, repair_map, prefix: str) -> list[tuple[list[str], str]]:
    """Group flagged shots and their repair lines into bounded <= 2000-character edit instructions."""
    batches: list[tuple[list[str], str]] = []
    scope: list[str] = []
    lines: list[str] = []
    for sid in ids:
        problems = repair_map.get(sid) or []
        if not problems:
            continue
        block = "\n".join("%s: %s: %s" % (sid, p["code"], p["detail"].strip()) for p in problems)
        if len(prefix) + len(block) > 2000:
            raise ReviewError("problems for a shot exceed the edit limit")
        if scope and len(prefix) + len("\n".join(lines)) + 1 + len(block) > 2000:
            batches.append((scope, prefix + "\n".join(lines)))
            scope, lines = [], []
        scope.append(sid)
        lines.append(block)
    if scope:
        batches.append((scope, prefix + "\n".join(lines)))
    return batches


def _validate(ids, answer):
    if not isinstance(answer, dict) or not isinstance(answer.get("shots"), list):
        raise ReviewError("review must contain a shots list")
    expected = set(ids)
    if len(expected) != len(ids):
        raise ReviewError("shot ids must be unique")
    found = {}
    for shot in answer["shots"]:
        if not isinstance(shot, dict) or not isinstance(shot.get("id"), str) or shot["id"] not in expected or shot["id"] in found:
            raise ReviewError("unknown or duplicate shot in review")
        problems = shot.get("problems")
        if not isinstance(problems, list):
            raise ReviewError("shot needs a problems list")
        seen = set()
        for problem in problems:
            if not isinstance(problem, dict):
                raise ReviewError("invalid review problem")
            code, detail = problem.get("code"), problem.get("detail")
            if not isinstance(code, str) or code not in CODES or code in seen or not isinstance(detail, str) or not detail.strip() or len(detail) > 350:
                raise ReviewError("invalid review problem")
            seen.add(code)
        found[shot["id"]] = problems
    if set(found) != expected:
        raise ReviewError("review omitted shots")
    return found


def review_and_repair(shot_ids, review, edit, *, draft_issues=None):
    """Review every current shot and perform at most two scoped repairs.

    The caller must raise on failed or cancelled review/edit. A fresh review is
    required after each repair so a failed or incomplete answer cannot pass as
    a clean result.
    """
    history = []
    prefix = "Fix these viewer-review problems using only the narration and project sources:\n"
    for round_index in range(3):
        ids = list(shot_ids())
        found = _validate(ids, review(ids))
        history.append(found)
        extra = _index_draft_issues(ids, draft_issues(ids) if draft_issues else [])
        combined = {sid: list(found[sid]) + list(extra.get(sid, [])) for sid in ids}
        flagged = [sid for sid in ids if combined[sid]]
        if not flagged or round_index == 2:
            warnings = [{"level": "warn", "code": ISSUE_CODES[p["code"]], "shot": sid, "message": p["detail"].strip()}
                        for sid in ids for p in found[sid]]
            draft_warnings = [{"level": "warn", "code": p["code"], "shot": sid, "message": p["detail"].strip()}
                              for sid in ids for p in extra.get(sid, [])]
            out = {"rounds": round_index, "warnings": warnings, "history": history}
            if draft_warnings:
                out["draft_warnings"] = draft_warnings
            return out
        for scope, instruction in _build_repair_batches(ids, combined, prefix):
            edit(scope, instruction)
    raise AssertionError("unreachable")


def _subject_phrases(picks):
    """Names and image/region labels supplied by the project, never guessed facts."""
    from bti.engine.timing import norm
    terms = set()
    def add(value):
        if isinstance(value, str):
            words = tuple(norm(w) for w in value.split())
            if words and all(words):
                terms.add(words)
    for name in picks.get("names") or []:
        if isinstance(name, dict):
            add(name.get("name"))
            for alias in name.get("also") or []:
                add(alias)
    for asset in (picks.get("assets") or {}).values():
        if isinstance(asset, dict):
            add(asset.get("title"))
            for region in (asset.get("regions") or {}).values():
                if isinstance(region, dict):
                    add(region.get("label"))
    return terms


def prepare_sheets(project, picks, destination, *, batch_size=6, cancelled=lambda: False):
    """Render the saved storyboard into numbered contact sheets and shot metadata.

    Frame choice matches curated names and picture/region labels against timed
    speech; absent a match, it uses the shot midpoint. At most two frames are
    selected per shot. The supplied engine object is the same facade as the
    engine still command and can be replaced by a fake in tests.
    """
    import cv2
    import numpy as np
    from pathlib import Path
    from bti.engine.timing import norm
    from bti.engine.viewchecks import _texts

    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    shots = project.resolve().get("shots") or []
    if not shots:
        raise ReviewError("storyboard has no shots")
    words = project.timing().get("words") or []
    terms = _subject_phrases(picks)
    rows, tiles, sheets = [], [], []
    for shot in shots:
        if cancelled():
            from bti.longjob import Cancelled
            raise Cancelled()
        sid, start, end = shot.get("id"), shot.get("_t0"), shot.get("_t1")
        if not isinstance(sid, str) or not sid or not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
            raise ReviewError("invalid resolved shot")
        spoken = [w for w in words if start <= float(w["s"]) < end]
        folded = [norm(w["w"]) for w in spoken]
        moments = sorted({float(spoken[i]["s"]) for i in range(len(spoken)) for phrase in terms
                          if tuple(folded[i:i + len(phrase)]) == phrase})
        if len(moments) > 2:
            moments = [moments[0], moments[-1]]
        if not moments:
            moments = [(start + end) / 2]
        texts = []
        for item in [shot] + [o for o in (shot.get("overlays") or []) if isinstance(o, dict)]:
            spec = project.bundle.spec(item.get("technique"))
            if spec and isinstance(item.get("params"), dict):
                texts.extend(x[3] for x in _texts(spec, item["params"]) if x[3].strip())
        frames = []
        for t in moments:
            image = project.frame_at(t, 640)
            if image is None or len(image.shape) != 3:
                raise ReviewError("could not render shot %s" % sid)
            frame = cv2.resize(image, (640, 360))
            banner = np.zeros((32, 640, 3), dtype=np.uint8)
            cv2.putText(banner, "%s  %.2fs" % (sid, t), (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(np.vstack((banner, frame)))
            frames.append({"time": t, "sheet": len(tiles) - 1})
        rows.append({"id": sid, "start": start, "end": end, "words": " ".join(w["w"] for w in spoken), "text": texts, "frames": frames})
    for first in range(0, len(tiles), batch_size):
        batch = tiles[first:first + batch_size]
        blank = np.zeros_like(batch[0])
        if len(batch) % 2:
            batch.append(blank)
        sheet = np.vstack([np.hstack(batch[i:i + 2]) for i in range(0, len(batch), 2)])
        path = destination / ("sheet-%03d.jpg" % (len(sheets) + 1))
        if not cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85]):
            raise ReviewError("could not save contact sheet")
        sheets.append(path)
    for row in rows:
        for frame in row["frames"]:
            frame["sheet"] = sheets[frame["sheet"] // batch_size].name
    return rows, sheets


def run_model_review(workspace, rows, *, project_dir=None, model=None, provider=None, ctx=None, timeout=900):
    """Run the project's storyboard agent against prepared sheets and validate its JSON.

    The workspace must be newly created by the caller, and sheets referenced by
    rows must already be present in it. Failures never count as a clean review.
    """
    import json
    from pathlib import Path
    from . import run as draft_run
    from .guard import Guard

    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    out = root / "out"
    out.mkdir(exist_ok=True)
    answer_path = out / "review.json"
    if answer_path.exists():
        raise ReviewError("review output already exists")
    if project_dir is not None and model is None:
        model = draft_run._resolve(Path(project_dir), "draft", None).model
    if provider is None:
        provider = draft_run._agent_module(model)
    template = Path(__file__).resolve().parents[2] / "skills" / "storyboard_review" / "TASK.template.md"
    task = template.read_text(encoding="utf-8")
    task += ("\n\nRead shots.json for each shot's words, text, times and sheet filenames. "
             "Open every contact sheet and review every shot in sequence. "
             "Write the complete JSON answer to out/review.json.\n")
    (root / "TASK.md").write_text(task, encoding="utf-8")
    (root / "shots.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    kwargs = {"model": model, "timeout": timeout, "max_repairs": 0}
    if project_dir is not None:
        kwargs["guard"] = Guard(Path(project_dir))
    if ctx is not None:
        kwargs.update(cancel=ctx.cancelled, runner=ctx.run_process)
    result = provider.run(root, **kwargs)
    if result.status == "cancelled":
        from bti.longjob import Cancelled
        raise Cancelled()
    if result.status != "ok":
        from .inputs import DraftError
        code = getattr(result, "error_code", None)
        if not code:
            code = "draft_tampered" if result.status == "tampered" else (
                "claude_timeout" if draft_run._is_claude(model) else "agy_timeout") if result.status == "timeout" else "agy_error"
        raise DraftError(code, getattr(result, "error_message", "") or "viewer review agent failed",
                         retry_after_seconds=getattr(result, "retry_after_seconds", None))
    try:
        if out.is_symlink() or answer_path.is_symlink() or answer_path.stat().st_size > 2_000_000:
            raise ReviewError("review output is not a regular, bounded file")
        def invalid_constant(value):
            raise ValueError("invalid JSON constant: " + value)
        answer = json.loads(answer_path.read_text(encoding="utf-8"), parse_constant=invalid_constant)
    except (OSError, UnicodeError, ValueError) as e:
        raise ReviewError("review agent did not write valid JSON") from e
    _validate([r["id"] for r in rows], answer)
    return answer


def scoped_edit(project_dir, shots, instruction, *, model, ctx, make_parts=None, base_rev=None):
    """Run request-box edit parts inside the current agent job, without a nested job."""
    from . import run as draft_run
    from bti.longjob import Cancelled
    if not shots or len(instruction) > 2000:
        raise ReviewError("invalid or oversized scoped repair")
    factory = make_parts or draft_run.make_edit_parts
    parts = factory(project_dir, model=model, instruction=instruction, edit_scope={"shots": list(shots)}, mode="deep", base_rev=base_rev)
    result = None
    for part in parts:
        if ctx.cancelled():
            raise Cancelled()
        value = part.run(ctx)
        if isinstance(value, dict) and value.get("status"):
            result = value
    if not result or result.get("status") not in ("applied", "no_change"):
        raise ReviewError("scoped repair did not apply cleanly")
    return result


def _revision(project_dir):
    import json
    from pathlib import Path
    from bti.editor.common import compute_rev
    return compute_rev(json.loads((Path(project_dir) / "storyboard.json").read_text(encoding="utf-8")))


def _report_path(project_dir, revision):
    from pathlib import Path
    import re
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision):
        return None
    return Path(project_dir) / "cache" / "draft" / "viewer_reviews" / (revision + ".json")


def _input_signature(project_dir):
    import hashlib
    from pathlib import Path
    h = hashlib.sha256()
    for name in ("timing.json", "picks.json"):
        h.update(name.encode())
        try:
            h.update((Path(project_dir) / name).read_bytes())
        except FileNotFoundError:
            h.update(b"<missing>")
    return h.hexdigest()


def load_report(project_dir, revision):
    import json
    path = _report_path(project_dir, revision)
    if path is None:
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    return doc if isinstance(doc, dict) and doc.get("revision") == revision and doc.get("inputs") == _input_signature(project_dir) and isinstance(doc.get("warnings"), list) else None


def save_report(project_dir, report):
    import json
    from bti.engine.storyboard import write_atomic
    path = _report_path(project_dir, report.get("revision"))
    if path is None:
        raise ReviewError("invalid report revision")
    path.parent.mkdir(parents=True, exist_ok=True)
    inputs = report.get("inputs") or _input_signature(project_dir)
    if inputs != _input_signature(project_dir):
        raise ReviewError("review inputs changed before saving")
    report = {**report, "inputs": inputs}
    write_atomic(path, json.dumps(report, ensure_ascii=False, indent=2))


def issues_for(project_dir, revision):
    report = load_report(project_dir, revision)
    if report is None:
        return []
    return [{**w, "path": "shots", "args": {"shot": w.get("shot")}} for w in report["warnings"] if isinstance(w, dict)]


def _review_round(project_dir, directory, model, ctx):
    import json
    from pathlib import Path
    from bti.engine.api import open_project
    project_dir = Path(project_dir)
    project = open_project(project_dir)
    picks = json.loads((project_dir / "picks.json").read_text(encoding="utf-8"))
    rows, _ = prepare_sheets(project, picks, directory, cancelled=ctx.cancelled)
    return rows, run_model_review(directory, rows, project_dir=project_dir, model=model, ctx=ctx)


def run_job(project_dir, model, ctx, *, review_round=None, edit=None, draft_issues=None):
    """Review the current revision and repair only flagged shots, within one job."""
    import json
    import uuid
    from pathlib import Path
    from bti.editor.common import save_lock
    from bti.engine.storyboard import write_atomic
    from bti.longjob import Cancelled
    project_dir = Path(project_dir)
    review_round = review_round or _review_round
    edit = edit or scoped_edit
    draft_issues_fn = draft_issues or (lambda cur_ids: _draft_repair_issues(project_dir, cur_ids))
    root = project_dir / "cache" / "draft" / "viewer_review" / uuid.uuid4().hex
    revision = _revision(project_dir)
    inputs = _input_signature(project_dir)
    round_no = 0

    def ids():
        if ctx.cancelled():
            raise Cancelled()
        sb = json.loads((project_dir / "storyboard.json").read_text(encoding="utf-8"))
        return [shot["id"] for shot in sb.get("shots", [])]

    def review_shots(expected):
        nonlocal round_no
        if ctx.cancelled():
            raise Cancelled()
        if _revision(project_dir) != revision or _input_signature(project_dir) != inputs:
            raise ReviewError("storyboard changed during viewer review")
        directory = root / str(round_no)
        round_no += 1
        ctx.progress(min(0.95, round_no / 4), "Đang xem lại storyboard…")
        rows, answer = review_round(project_dir, directory, model, ctx)
        if [r["id"] for r in rows] != expected or _revision(project_dir) != revision or _input_signature(project_dir) != inputs:
            raise ReviewError("storyboard changed during viewer review")
        return answer

    def edit_shots(shots, instruction):
        nonlocal revision
        if _revision(project_dir) != revision or _input_signature(project_dir) != inputs:
            raise ReviewError("storyboard changed during viewer review")
        if edit is scoped_edit:
            edited = edit(project_dir, shots, instruction, model=model, ctx=ctx, base_rev=revision)
            actual = _revision(project_dir)
            if edited.get("after_rev") and edited["after_rev"] != actual:
                raise ReviewError("storyboard changed during scoped repair")
        else:
            edit(project_dir, shots, instruction, model=model, ctx=ctx)
            actual = _revision(project_dir)
        revision = actual

    result = review_and_repair(ids, review_shots, edit_shots, draft_issues=draft_issues_fn)
    if ctx.cancelled():
        raise Cancelled()
    with save_lock(project_dir):
        if _revision(project_dir) != revision or _input_signature(project_dir) != inputs:
            raise ReviewError("storyboard changed during viewer review")
        result["revision"] = revision
        result["inputs"] = inputs
        save_report(project_dir, result)
    ctx.progress(1.0, "Đã xem lại storyboard.")
    return result


def start(pid, project_dir, *, manager=None, run_ok=False):
    from bti.longjob import Part, PartError
    from . import run as draft_run
    from .inputs import DraftError
    project_dir = __import__("pathlib").Path(project_dir)
    if not (project_dir / "storyboard.json").is_file():
        raise DraftError("scope_needs_storyboard", "review requires a storyboard")
    if not draft_run.readiness(project_dir)["ok"]:
        raise DraftError("draft_not_ready", "review requires the voice timing and approved picks")
    draft_run.refuse_while_agent_busy(pid, manager, run_ok=run_ok)
    resolved = draft_run._resolve(project_dir, "draft", None)
    draft_run._check_agent_installed(resolved.model)
    m = manager or draft_run._manager()
    return m.start(kind="draft", pid=pid, project_dir=project_dir,
                   parts=make_job_parts(project_dir, resolved.model),
                   meta={"mode": "review", "model": resolved.model, "agent": resolved.public()})


def make_job_parts(project_dir, model, *, review_round=None, edit=None, draft_issues=None):
    """Separate review and repair rounds so each has its own long-job time limit."""
    import json
    import uuid
    from pathlib import Path
    from bti.editor.common import save_lock
    from bti.longjob import Cancelled, Part, PartError
    from . import run as draft_run
    project_dir = Path(project_dir)
    reviewer, editor = review_round or _review_round, edit or scoped_edit
    draft_issues_fn = draft_issues or (lambda cur_ids: _draft_repair_issues(project_dir, cur_ids))
    root = project_dir / "cache" / "draft" / "viewer_review" / uuid.uuid4().hex
    state = {"revision": None, "inputs": None, "history": [], "pending": [], "rounds": 0, "finished": False, "found": {}, "draft_extra": {}}
    prefix = "Fix these viewer-review problems using only the narration and project sources:\n"

    def check(ctx):
        if ctx.cancelled():
            raise Cancelled()
        if state["revision"] is not None and (_revision(project_dir) != state["revision"] or _input_signature(project_dir) != state["inputs"]):
            raise ReviewError("storyboard or review inputs changed")

    def guarded(fn):
        def call(ctx):
            try:
                return fn(ctx)
            except ReviewError as exc:
                raise PartError("review_failed", str(exc)) from exc
            except draft_run.DraftError as exc:
                wait = exc.extra.get("retry_after_seconds") if exc.code in draft_run.RATE_LIMIT_CODES else None
                if hasattr(ctx, "meta"):
                    ctx.meta.update(draft_run.rate_limit_fields(wait))
                words = (draft_run.rate_limit_sentence(exc.code, wait) if wait is not None
                         else draft_run.vi(exc.code, exc.message))
                raise PartError(exc.code, words) from exc
        return call

    def examine(n):
        def part(ctx):
            if state["finished"]:
                return
            if state["revision"] is None:
                state["revision"] = _revision(project_dir)
                state["inputs"] = _input_signature(project_dir)
            check(ctx)
            sb = json.loads((project_dir / "storyboard.json").read_text(encoding="utf-8"))
            ids = [shot["id"] for shot in sb.get("shots", [])]
            if not ids:
                raise ReviewError("storyboard has no shots")
            rows, answer = reviewer(project_dir, root / str(n), model, ctx)
            check(ctx)
            if [row["id"] for row in rows] != ids:
                raise ReviewError("review omitted or reordered shots")
            found = _validate(ids, answer)
            extra = _index_draft_issues(ids, draft_issues_fn(ids))
            combined = {sid: list(found[sid]) + list(extra.get(sid, [])) for sid in ids}
            state["found"] = found
            state["draft_extra"] = extra
            state["history"].append(found)
            flagged = [sid for sid in ids if combined[sid]]
            state["pending"] = []
            if not flagged or n == 2:
                state["finished"] = True
                return
            state["pending"] = _build_repair_batches(ids, combined, prefix)
        return part

    def repair(ctx):
        if state["finished"]:
            return
        for shots, instruction in state["pending"]:
            check(ctx)
            if editor is scoped_edit:
                result = editor(project_dir, shots, instruction, model=model, ctx=ctx, base_rev=state["revision"])
                actual = _revision(project_dir)
                if result.get("after_rev") and result["after_rev"] != actual:
                    raise ReviewError("storyboard changed during scoped repair")
            else:
                editor(project_dir, shots, instruction, model=model, ctx=ctx)
                actual = _revision(project_dir)
            if _input_signature(project_dir) != state["inputs"]:
                raise ReviewError("review inputs changed during scoped repair")
            state["revision"] = actual
        state["rounds"] += 1

    def finish(ctx):
        check(ctx)
        if not state["finished"]:
            raise ReviewError("review did not complete")
        warnings = [{"level": "warn", "code": ISSUE_CODES[p["code"]], "shot": sid, "message": p["detail"].strip()}
                    for sid, problems in state["found"].items() for p in problems]
        draft_warnings = [{"level": "warn", "code": p["code"], "shot": sid, "message": p["detail"].strip()}
                          for sid in state["found"] for p in (state.get("draft_extra") or {}).get(sid, [])]
        result = {"revision": state["revision"], "inputs": state["inputs"], "rounds": state["rounds"], "warnings": warnings, "history": state["history"]}
        if draft_warnings:
            result["draft_warnings"] = draft_warnings
        with save_lock(project_dir):
            check(ctx)
            save_report(project_dir, result)
        ctx.progress(1.0, "Đã xem lại storyboard.")
        return result

    return [Part(key="review_%d" % (n + 1), title="Xem lại storyboard lần %d" % (n + 1), run=guarded(examine(n)), est_seconds=900)
            if k == "review" else Part(key="repair_%d" % (n + 1), title="Sửa cảnh lần %d" % (n + 1), run=guarded(repair), est_seconds=900)
            for k, n in (("review", 0), ("repair", 0), ("review", 1), ("repair", 1), ("review", 2))] + [
                Part(key="review_save", title="Lưu kết quả xem lại", run=guarded(finish), est_seconds=1)]


def after_full_edit_parts(project_dir, model, turn_id):
    """Append viewer review after a successfully applied whole-storyboard edit."""
    from dataclasses import replace
    from bti.longjob import PartError
    from . import run as draft_run
    from .thread import load_thread
    parts = make_job_parts(project_dir, model)
    def unchanged(ctx):
        turn = next((t for t in load_thread(project_dir) if t.get("id") == turn_id), None)
        return bool(turn and turn.get("status") == "no_change")
    parts = [replace(part, is_done=unchanged) for part in parts]
    first = parts[0]
    def start_review(ctx):
        turn = next((t for t in load_thread(project_dir) if t.get("id") == turn_id), None)
        if not turn or turn.get("status") != "applied":
            raise PartError("review_failed", "Không thể xem lại vì lần sửa chưa được áp dụng.")
        try:
            draft_run._check_agent_installed(model)
        except draft_run.DraftError as exc:
            raise PartError(exc.code, draft_run.vi(exc.code, exc.message)) from exc
        return first.run(ctx)
    parts[0] = replace(first, run=start_review)
    return parts
