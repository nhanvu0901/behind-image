"""Fast path for editing the storyboard by instruction (contract A2).

One single-turn call through bti.script.providers (no workspace, no tools).
Tolerant JSON extraction, shape checking, edit compilation and validation,
with one repair cycle on error.
"""
from __future__ import annotations

import copy
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from bti.draft import decompile as D
from bti.draft import techniques_md
from bti.draft.compile import CompileResult, compile_specs
from bti.draft.decompile import chapter_of, resolved_current, shot_to_spec
from bti.draft.inputs import SPEC_SCHEMA, DraftInputs
from bti.engine import registry as R
from bti.engine.timing import Timing
from bti.script.brief import REPO_ROOT
from bti.settings import model_for

TEMPLATE_PATH = REPO_ROOT / "skills" / "storyboard_edit" / "FAST.template.md"


@dataclass
class FastEditResult:
    status: str       # "applied" | "cannot" | "escalate" | "failed"
    summary: str = ""
    reason: str | None = None
    code: str | None = None       # for "failed": spec_invalid (not JSON or wrong shape) | edit_outside_scope | compile_error | bad_model
    changes: list[dict] = field(default_factory=list)
    storyboard: dict | None = None
    issues: list[str] = field(default_factory=list)
    repair_used: bool = False
    raw_answer: str = ""


def extract_json(raw: str) -> tuple[dict | None, str | None]:
    """Tolerantly extract the first valid JSON object from the model response."""
    text = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
    else:
        candidate = text
    try:
        data = json.loads(candidate)
        if not isinstance(data, dict):
            return None, f"JSON root must be an object, got {type(data).__name__}"
        return data, None
    except Exception as e:
        return None, f"JSON parse error: {e}"


def check_shape(data: dict) -> list[str]:
    """Check that the extracted JSON object conforms to the contract."""
    issues = []
    res = data.get("result")
    if res not in ("edit", "cannot", "escalate"):
        issues.append(f"'result' must be 'edit', 'cannot', or 'escalate', got {res!r}")
        return issues
    if res in ("cannot", "escalate"):
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            issues.append(f"Result {res!r} requires a non-empty 'reason' in Vietnamese")
        return issues

    # result == "edit"
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        issues.append("Result 'edit' requires a non-empty 'summary' in Vietnamese")
    shots = data.get("shots")
    remove = data.get("remove")
    if shots is None:
        shots = []
    if remove is None:
        remove = []
    if not isinstance(shots, list):
        issues.append("'shots' must be a list of the shots you change or add (the other shots of the scope stay as they are)")
        shots = []
    if not isinstance(remove, list) or not all(isinstance(x, str) and x for x in remove):
        issues.append("'remove' must be a list of shot ids to delete (use [] when none)")
        remove = []
    if not shots and not remove:
        issues.append("Result 'edit' needs at least one shot in 'shots' (changed or new) or one id in 'remove'")
    for i, s in enumerate(shots):
        if not isinstance(s, dict):
            issues.append(f"shots[{i}] must be an object")
            continue
        if not s.get("technique"):
            issues.append(f"shots[{i}] is missing 'technique'")
        if not isinstance(s.get("start_word"), int) or isinstance(s.get("start_word"), bool):
            issues.append(f"shots[{i}] is missing integer 'start_word'")
        if not s.get("beat"):
            issues.append(f"shots[{i}] is missing 'beat'")
    changes = data.get("changes")
    if not isinstance(changes, list):
        issues.append("Result 'edit' requires a 'changes' list")
    else:
        for i, ch in enumerate(changes):
            if not isinstance(ch, dict) or not ch.get("what"):
                issues.append(f"changes[{i}] must have a 'what' sentence in Vietnamese")
    if "regions" in data and data["regions"] is not None:
        if not isinstance(data["regions"], list):
            issues.append("'regions' must be a list if provided")
        else:
            for i, reg in enumerate(data["regions"]):
                if not isinstance(reg, dict) or not reg.get("name") or not reg.get("asset"):
                    issues.append(f"regions[{i}] must be an object with 'asset' and 'name'")
    return issues


def prepare_prompt(
    inp: DraftInputs,
    instruction: str,
    thread_turns: list[dict] | None = None,
    bundle = None,
) -> str:
    """Render the fast edit prompt from FAST.template.md."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8") if TEMPLATE_PATH.is_file() else ""
    bundle = bundle or R.load_bundle(inp.style)
    tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})

    # Thread history (last 3)
    if thread_turns:
        t_lines = []
        for i, t in enumerate(thread_turns[-3:], 1):
            t_lines.append(f"Turn {i}:")
            t_lines.append(f"- Lệnh: {t.get('instruction', '')}")
            if t.get("summary"):
                t_lines.append(f"- Tóm tắt: {t.get('summary', '')}")
            elif t.get("notes"):
                t_lines.append(f"- Ghi chú: {t.get('notes', '')}")
        hist_text = "\n".join(t_lines)
    else:
        hist_text = "(Không có lịch sử trước)"

    # Scope shots from decompile
    dec = D.decompile(inp, inp.edit_shots)
    beats_map = {b["id"]: b.get("text", "") for b in inp.timing["beats"]}
    scope_shots = []
    for cid in inp.in_scope():
        for s in dec.get(cid, {}).get("spec", {}).get("shots", []):
            if s.get("in_scope"):
                b_text = beats_map.get(s.get("beat"), "")
                dur = round(float(s.get("end_s", 0)) - float(s.get("start_s", 0)), 3)
                scope_shots.append({**s, "beat_text": b_text, "duration_s": dur})
    scope_shots_json = json.dumps(scope_shots, indent=2, ensure_ascii=False)

    # Neighbour shots
    cur_resolved = [rc for rc in resolved_current(inp, tm) if not D.is_card(bundle, rc["shot"])]
    scope_indices = [i for i, rc in enumerate(cur_resolved) if rc["shot"].get("id") in (inp.edit_shots or set())]
    prev_neighbour = "(none)"
    next_neighbour = "(none)"
    if scope_indices:
        first_idx = min(scope_indices)
        last_idx = max(scope_indices)
        if first_idx > 0:
            prc = cur_resolved[first_idx - 1]
            pspec = shot_to_spec(inp, tm, prc["shot"], prc["t0"], prc["t1"])
            pspec["id"] = prc["shot"].get("id")
            pspec["beat_text"] = beats_map.get(pspec.get("beat"), "")
            pspec["duration_s"] = round(prc["t1"] - prc["t0"], 3)
            prev_neighbour = json.dumps(pspec, indent=2, ensure_ascii=False)
        if last_idx + 1 < len(cur_resolved):
            nrc = cur_resolved[last_idx + 1]
            nspec = shot_to_spec(inp, tm, nrc["shot"], nrc["t0"], nrc["t1"])
            nspec["id"] = nrc["shot"].get("id")
            nspec["beat_text"] = beats_map.get(nspec.get("beat"), "")
            nspec["duration_s"] = round(nrc["t1"] - nrc["t0"], 3)
            next_neighbour = json.dumps(nspec, indent=2, ensure_ascii=False)

    # Assets & regions
    all_assets = {**inp.picks.get("assets", {}), **((inp.current or {}).get("assets") or {})}
    used_asset_keys = {inp.picks.get("main_asset")}
    for s in scope_shots:
        for slot in (s.get("slots") or {}).values():
            if isinstance(slot, dict) and slot.get("asset"):
                used_asset_keys.add(slot["asset"])
    assets_info = {}
    for k in used_asset_keys:
        if k in all_assets and isinstance(all_assets[k], dict):
            a = all_assets[k]
            assets_info[k] = {
                "title": a.get("title", k),
                "file": a.get("file"),
                "regions": a.get("regions", {}),
            }
    assets_json = json.dumps(assets_info, indent=2, ensure_ascii=False)

    # Techniques catalogue
    tech_md = techniques_md.generate(bundle)

    # The narration words over the scope (index:word@second), so that a shot can be moved to another word
    words = inp.timing["words"]
    scope_starts = [s.get("start_word", 0) for s in scope_shots] or [0]
    w_lo, w_last = min(scope_starts), max(scope_starts)
    after = [D._word_of(tm, rc["shot"].get("start") or {}, rc["t0"])[0] for rc in cur_resolved if rc["shot"].get("id") not in (inp.edit_shots or set())]
    w_hi = min([w for w in after if w > w_last] or [len(words)])          # up to the first shot after the scope
    w_hi = min(w_hi, w_lo + 1500)
    words_text = " ".join("%d:%s@%.1f" % (i, str(words[i].get("w", "")), float(words[i].get("s", 0.0))) for i in range(w_lo, w_hi))

    # Fill template
    rendered = template
    rendered = rendered.replace("{{WORDS}}", words_text or "(none)")
    rendered = rendered.replace("{{INSTRUCTION}}", instruction.strip())
    rendered = rendered.replace("{{THREAD_HISTORY}}", hist_text)
    rendered = rendered.replace("{{SCOPE_SHOTS}}", scope_shots_json)
    rendered = rendered.replace("{{PREV_NEIGHBOUR}}", prev_neighbour)
    rendered = rendered.replace("{{NEXT_NEIGHBOUR}}", next_neighbour)
    rendered = rendered.replace("{{MAIN_ASSET}}", str(inp.picks.get("main_asset", "")))
    rendered = rendered.replace("{{ASSETS_JSON}}", assets_json)
    rendered = rendered.replace("{{TECHNIQUES_MD}}", tech_md)
    return rendered


def try_compile(
    inp: DraftInputs,
    shots: list[dict],
    regions: list[dict] | None,
    bundle = None,
    project_dir: Path | None = None,
    remove: list[str] | None = None,
) -> tuple[CompileResult | None, list[str]]:
    """Compile and check the model's answer. `shots` are the shots it changes (with their `id`) or adds (without), `remove` the ids it
    deletes; every other shot of the scope stays exactly as it is."""
    issues: list[str] = []
    remove = list(remove or [])
    allowed_shots = set(inp.edit_shots or set())
    locked_shots = {s["id"] for s in (inp.current or {}).get("shots", []) if s.get("locked") and s.get("id")}
    current_shots_map = {s["id"]: s for s in (inp.current or {}).get("shots", []) if s.get("id")}

    seen_ids: set[str] = set()
    for s in shots:
        sid = s.get("id")
        if not sid:
            continue
        if sid in seen_ids:
            issues.append(f"Shot {sid} appears twice in 'shots'")
        seen_ids.add(sid)
        if sid in locked_shots:
            issues.append(f"Shot {sid} is locked and cannot be changed")
        elif sid in current_shots_map and sid not in allowed_shots:
            issues.append(f"Shot {sid} is outside the allowed edit scope (allowed: {', '.join(sorted(allowed_shots))})")
        elif sid not in current_shots_map:
            issues.append(f"Shot id {sid!r} does not exist; for a NEW shot leave out 'id'")
    for sid in remove:
        if sid in locked_shots:
            issues.append(f"Shot {sid} is locked and cannot be removed")
        elif sid not in allowed_shots:
            issues.append(f"Cannot remove {sid}: it is outside the allowed edit scope (allowed: {', '.join(sorted(allowed_shots))})")
        if sid in seen_ids:
            issues.append(f"Shot {sid} is both in 'shots' and in 'remove'")

    dec = D.decompile(inp, inp.edit_shots)
    returned = {s["id"]: s for s in shots if s.get("id")}
    new_shots = [s for s in shots if not s.get("id")]
    specs = {}
    from bti.draft import spec as S
    for cid in inp.in_scope():
        chap_shots = []
        for s in dec.get(cid, {}).get("spec", {}).get("shots", []):
            sid = s.get("id")
            if not s.get("in_scope"):
                chap_shots.append(copy.deepcopy(s))
            elif sid in remove:
                continue
            elif sid in returned:
                chap_shots.append(copy.deepcopy(returned[sid]))
            else:
                chap_shots.append(copy.deepcopy(s))              # not mentioned: exactly as it is
        for s in new_shots:
            sw = s.get("start_word", 0)
            scid = chapter_of(inp, sw)
            if scid == cid:
                chap_shots.append(copy.deepcopy(s))
            elif scid not in inp.in_scope():
                issues.append(f"Shot with start_word {sw} falls into chapter {scid!r} which is outside the scope")
        chap_shots.sort(key=lambda x: (x.get("start_word", 0), float(x.get("off") or 0.0)))
        clean_spec, shape_probs = S.shape_problems({"schema": SPEC_SCHEMA, "chapter": cid, "shots": chap_shots}, cid)
        for p in shape_probs:
            if p.get("level") == "error":
                issues.append(p["message"])
        specs[cid] = clean_spec

    if issues:
        return None, issues

    # Prepare regions dict
    reg_dict = {}
    if regions:
        for r in regions:
            asset = r.get("asset")
            name = r.get("name")
            if asset and name:
                reg_dict.setdefault(asset, {})[name] = r

    try:
        res = compile_specs(inp, specs, regions=reg_dict, degrade=False, draw=False)
    except Exception as e:
        return None, [f"Compilation error: {e}"]

    if res.storyboard is not None:
        from bti.draft.normalize import keep_saved
        keep_saved(inp.current, res.storyboard, bundle or R.load_bundle(inp.style))
    if res.violations:
        for v in res.violations:
            issues.append(f"Scope violation: {v.get('message', str(v))}")
    if res.errors:
        for err in res.errors:
            issues.append(f"Compile error ({err.get('code', 'unknown')}): {err.get('message', str(err))}")

    # Draw check of changed shots only
    if not issues and (project_dir is not None or inp.project_dir is not None):
        try:
            draw_issues = _draw_check_changed_shots(inp, res.storyboard)
            for di in draw_issues:
                issues.append(f"Draw error in shot {di.get('shot')}: {di.get('message')}")
        except Exception as e:
            issues.append(f"Draw check failure: {e}")

    if issues:
        return None, issues
    return res, []


def _draw_check_changed_shots(inp: DraftInputs, new_sb: dict) -> list[dict]:
    """Draw check of what the edit can have affected (see bti/draft/drawcheck.py). A check that cannot run is an issue, never a
    silent pass."""
    from bti.draft.drawcheck import draw_changed
    return draw_changed(inp, new_sb).issues


def _issue_code(issues: list[str], json_failed: bool) -> str:
    """The error code the page shows for a failed fast edit, from the issue texts the checks produced."""
    if json_failed:
        return "spec_invalid"
    text = " ".join(issues)
    if "outside the allowed edit scope" in text or "Scope violation" in text or "outside the scope" in text or "is locked" in text:
        return "edit_outside_scope"
    if "Compile error" in text or "Draw error" in text or "Draw check" in text or "Compilation error" in text:
        return "compile_error"
    return "spec_invalid"


def _warm_engine(inp: DraftInputs) -> None:
    """Best effort, never raises: the first use of the engine in a process (style registry, picture decoding, the scene of the
    saved storyboard) takes seconds. It runs while the model thinks, so the checks after the answer find everything warm."""
    try:
        from bti.draft.engine import DraftProject
        cur = inp.current
        shots = [s for s in (cur or {}).get("shots", []) if isinstance(s, dict) and s.get("id") in (inp.edit_shots or ())]
        eng = DraftProject(inp.project_dir, cur, inp.timing)
        try:
            eng.validate(cur)
            eng.use_draft(cur)
            tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
            if shots and isinstance(shots[0].get("start"), dict):
                eng.frame_at(tm.resolve(shots[0]["start"]) + 0.2, 320)
        finally:
            eng.close()
    except Exception:       # noqa: BLE001
        pass


class _CancelFlag:
    """What the providers want (`is_set()`) from what a long job has (`cancelled()`)."""

    def __init__(self, fn):
        self._fn = fn

    def is_set(self) -> bool:
        return bool(self._fn())


def fast_edit(
    inp: DraftInputs,
    instruction: str,
    *,
    model: str | None = None,
    thread_turns: list[dict] | None = None,
    bundle = None,
    project_dir: Path | None = None,
    on_progress: Callable | None = None,
    cancel: Any = None,
    max_repairs: int = 1,
    timeout: float = 240.0,
) -> FastEditResult:
    """Run one fast edit turn with up to `max_repairs` repair calls. `inp` must carry the scope (`inp.edit_shots`, `inp.scope`).
    `cancel` is a threading.Event or a callable returning True once the job is cancelled. A provider error is raised as
    bti.script.providers.ProviderError (the caller decides what the owner is told)."""
    if inp.edit_shots is None:
        raise ValueError("fast_edit needs inp.edit_shots (the scope); use inputs.clone_inputs(inp, scope=..., edit_shots=...)")
    if callable(cancel):
        cancel = _CancelFlag(cancel)
    model_id = model or model_for("edit.fast")
    bundle = bundle or R.load_bundle(inp.style)
    prompt = prepare_prompt(inp, instruction, thread_turns=thread_turns, bundle=bundle)
    system_prompt = "You are an expert storyboard editor. Respond with a single JSON object."

    from bti.script import models as models_mod
    from bti.script.providers import get_provider

    spec = models_mod.resolve(model_id)
    if spec is None:
        return FastEditResult(status="failed", code="bad_model", reason=f"unknown model: {model_id}")
    provider_fn = get_provider(spec["provider"])

    issues: list[str] = []
    json_failed = False
    raw_text = ""
    warm = threading.Thread(target=_warm_engine, args=(inp,), daemon=True, name="fastedit-warm")
    warm.start()
    for attempt in range(max_repairs + 1):
        if attempt == 0:
            ask = prompt
        else:
            ask = (f"{prompt}\n\n[REPAIR TURN]\nYour previous response had the following issues:\n"
                   + "\n".join(f"- {iss}" for iss in issues)
                   + "\n\nPlease fix all issues and output the complete JSON object again.")
        raw_text = provider_fn(spec, system_prompt, ask, timeout=timeout, on_progress=on_progress, cancel=cancel)
        warm.join(30)                       # never compile while the warm-up still runs
        used_repair = attempt > 0
        data, json_err = extract_json(raw_text)
        issues = []
        json_failed = False
        if json_err:
            issues.append(json_err)
            json_failed = True
            continue
        shape_issues = check_shape(data)
        if shape_issues:
            issues.extend(shape_issues)
            json_failed = True
            continue
        if data.get("result") in ("cannot", "escalate"):
            return FastEditResult(status=data["result"], summary=data.get("summary") or "", reason=data.get("reason") or "",
                                  raw_answer=raw_text, repair_used=used_repair)
        comp_res, comp_issues = try_compile(inp, data.get("shots") or [], data.get("regions"), bundle, project_dir, remove=data.get("remove"))
        if comp_issues:
            issues.extend(comp_issues)
            continue
        return FastEditResult(status="applied", summary=data.get("summary") or "", changes=data.get("changes") or [],
                              storyboard=comp_res.storyboard if comp_res else None, repair_used=used_repair, raw_answer=raw_text)

    return FastEditResult(status="failed", summary="", reason="; ".join(issues), issues=issues, code=_issue_code(issues, json_failed),
                          repair_used=max_repairs >= 1, raw_answer=raw_text)
