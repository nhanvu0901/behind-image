"""One work at a time: build the prompt, call the model, check the answer, retry once, write the pages and the report.

Nothing of a work is written unless every check passes. The report is rewritten (atomically) after every work, so an
interrupted run loses at most the work in progress, and a second run skips the works that are done."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from bti.fsio import atomic_replace

from . import checks
from .pages import page_type, parse_page

HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE / "PROMPT.md"
REPORT_NAME = "report.json"
DEFAULT_TIMEOUT = 900.0
SYSTEM = ("You are a careful copy editor who puts a machine-translated art-history chapter into proper English "
          "without adding or dropping anything. Follow the instructions in the user message exactly.")
FATAL_KINDS = {"real_models_off", "auth", "config", "cancelled"}
RETRY_HEAD = "YOUR PREVIOUS ANSWER WAS REJECTED."


class RestoreError(Exception):
    """A problem that stops the whole run (not just one work)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Settings:
    book_id: str
    book_title: str
    works: list[dict]
    clean_dir: Path
    out_dir: Path
    model_id: str
    force: bool = False
    timeout: float = DEFAULT_TIMEOUT
    prompt_path: Path = PROMPT_PATH
    log: Callable[[str], None] = print
    complete: Callable | None = None      # tests may pass a fake; default is the project's provider for the model
    only: set[int] | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def input_hash(template: str, pages: list[tuple[int, str]]) -> str:
    """The hash of what a work's result is made from: the prompt template AND the input pages. A change of the prompt is a changed
    input, so the next run restores the work again."""
    return sha(sha(template) + "".join(f"page_{p:04d}\0{t}\0" for p, t in pages))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(text.encode("utf-8"))
    atomic_replace(tmp, path)


def read_page(clean_dir: Path, n: int) -> str | None:
    f = clean_dir / f"page_{n:04d}.txt"
    if not f.is_file():
        return None
    return f.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


# ------------------------------------------------------------------ model
def resolve_model(model_id: str) -> dict:
    """The provider spec of a model id. Refuses a real provider while BTI_NO_REAL_MODELS=1, before anything is read."""
    from bti.script import models as models_mod
    spec = models_mod.resolve(model_id)
    if spec is None:
        raise RestoreError("unknown_model", f"unknown model id: {model_id!r}")
    if spec.get("unavailable"):
        raise RestoreError("model_unavailable", f"model {model_id!r} is not available: {spec['unavailable']}")
    if os.environ.get("BTI_NO_REAL_MODELS") == "1" and spec.get("provider") != "mock":
        raise RestoreError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1); nothing was run. "
                                              "Use --model mock to try the tool without a model.")
    return spec


def call_model(spec: dict, prompt: str, st: Settings) -> str:
    from bti.script.providers import ProviderError, get_provider
    complete = st.complete or get_provider(spec["provider"])
    try:
        return complete(spec, SYSTEM, prompt, timeout=float(spec.get("timeout") or st.timeout))
    except ProviderError as e:
        if e.kind in FATAL_KINDS:
            raise RestoreError(e.kind, e.message) from e
        raise


# ------------------------------------------------------------------ prompt
def build_prompt(template: str, st: Settings, work: dict, pages: dict[str, str]) -> str:
    bits = [f"{work.get('title') or ''}".strip()]
    artist = (work.get("artist") or "").strip()
    year = (work.get("year") or "").strip() if isinstance(work.get("year"), str) else ""
    line = "The book's contents list names this chapter: "
    line += f"{artist}, " if artist else ""
    line += f"\"{bits[0]}\"" if bits[0] else "(no title)"
    line += f" ({year})" if year else ""
    line += ". That line may itself contain small errors."
    body = "\n\n".join(f"=== {pid} ===\n{text.rstrip()}" for pid, text in pages.items())
    return template.replace("{{BOOK}}", st.book_title).replace("{{CHAPTER}}", line).replace("{{PAGES}}", body)


def retry_prompt(prompt: str, failures: list[str]) -> str:
    return (prompt + f"\n\n{RETRY_HEAD} An automatic check found these problems:\n" + checks.failures_text(failures)
            + "\nWrite the answer again: every page, complete, in the exact format above, fixing these problems and changing nothing else.\n")


# ------------------------------------------------------------------ report
def report_path(st: Settings) -> Path:
    return st.out_dir / REPORT_NAME


def load_report(st: Settings) -> dict:
    p = report_path(st)
    if not p.is_file():
        return {"format": 1, "book_id": st.book_id, "works": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("works"), dict):
            raise ValueError("no works object")
    except ValueError as e:
        raise RestoreError("report_unreadable", f"{p} cannot be read ({e}); fix or move it, the run will not overwrite it") from e
    return data


def summarise(rep: dict, total: int) -> dict:
    works = rep["works"]
    ok = [w for w in works.values() if w.get("ok")]
    pairs: dict[str, int] = {}
    for w in ok:
        for n in w.get("names", []):
            k = f"{n['from']} => {n['to']}"
            pairs[k] = pairs.get(k, 0) + 1
    rpairs: dict[str, int] = {}
    for w in ok:
        for n in w.get("readings", []):
            k = f"{n['from']} => {n['to']}"
            rpairs[k] = rpairs.get(k, 0) + 1
    return {"works_in_book": total, "ok": len(ok), "failed": len(works) - len(ok), "not_run": max(0, total - len(works)),
            "unclear_passages": sum(w.get("unclear", 0) for w in ok), "name_corrections": len(pairs),
            "names_all": dict(sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))),
            "readings": sum(len(w.get("readings", [])) for w in ok),
            "readings_dropped": sum(len(w.get("readings_dropped", [])) for w in ok),
            "names_dropped": sum(len(w.get("names_dropped", [])) for w in ok),
            "readings_all": dict(sorted(rpairs.items(), key=lambda kv: (-kv[1], kv[0])))}


def save_report(st: Settings, rep: dict, prompt_sha: str) -> None:
    rep["updated"] = now_iso()
    rep["prompt_sha"] = prompt_sha
    rep["summary"] = summarise(rep, len(st.works))
    atomic_write_text(report_path(st), json.dumps(rep, ensure_ascii=False, indent=1) + "\n")


# ------------------------------------------------------------------ one work
def page_ids(work: dict) -> list[int]:
    a, b = work["pdf_pages"]
    return list(range(int(a), int(b) + 1))


def _out_file(st: Settings, n: int) -> Path:
    return st.out_dir / f"page_{n:04d}.txt"


def is_done(st: Settings, work: dict, entry: dict | None, in_hash: str) -> bool:
    if st.force or not entry or not entry.get("ok") or entry.get("input_hash") != in_hash:
        return False
    return all(_out_file(st, n).is_file() for n in page_ids(work))


def restore_work(st: Settings, work: dict, spec: dict, template: str, prompt_lines: set[str], prev: dict | None = None) -> dict:
    """-> the report entry of this work. Raises RestoreError only for problems that stop the whole run."""
    n = work["n"]
    nums = page_ids(work)
    entry: dict = {"n": n, "title": work.get("title"), "artist": work.get("artist"), "model": st.model_id,
                   "pages": [f"page_{p:04d}" for p in nums], "ok": False, "result": "not_run", "attempts": 0, "seconds": 0.0,
                   "attempt_problems": []}
    texts: dict[int, str] = {}
    for p in nums:
        t = read_page(st.clean_dir, p)
        if t is None:
            entry["result"] = f"input_missing: page_{p:04d}.txt"
            return entry
        texts[p] = t
    in_hash = input_hash(template, [(p, texts[p]) for p in nums])
    entry["input_hash"] = in_hash
    body = {f"page_{p:04d}": texts[p] for p in nums if page_type(texts[p]) == "body"}
    bad = [f"page_{p:04d}" for p in nums if page_type(texts[p]) is None]
    if bad:
        entry["result"] = "input_bad_first_line: " + ", ".join(bad)
        return entry
    entry["body_pages"] = len(body)
    entry["input_chars"] = sum(len(t) for t in texts.values())
    result: checks.Check | None = None
    if body and any(i.kind == "p" for t in body.values() for i in parse_page(t)):
        prompt = build_prompt(template, st, work, body)
        entry["prompt_chars"] = len(prompt)
        t0 = time.monotonic()
        attempt_prompt = prompt
        failures: list[str] = []
        raws: list[str] = []
        # an answer saved by an earlier failed run of this same input (same pages, same prompt) may pass the current checks
        saved = saved_answers(st, n) if prev and not prev.get("ok") and prev.get("input_hash") == in_hash else []
        for name, raw in saved:
            r = checks.check_answer(body, raw, prompt_lines, "\n".join(body.values()))
            if r.ok:
                result = r
                entry["from_saved"] = True
                entry["saved_file"] = name
                st.log(f"  work {n}: a saved earlier answer ({name}) passes the checks now; no model call")
                break
        for attempt in ((1, 2) if result is None else ()):
            entry["attempts"] = attempt
            try:
                raw = call_model(spec, attempt_prompt, st)
            except RestoreError:
                raise
            except Exception as e:                                   # noqa: BLE001 - one work fails, the run goes on
                kind = getattr(e, "kind", type(e).__name__)
                failures = [f"the model call failed: {kind}: {getattr(e, 'message', str(e))[:200]}"]
                result = None
                entry["last_error"] = failures[0]
                entry["attempt_problems"].append(failures[:30])
                if attempt == 1:
                    st.log(f"  work {n}: attempt 1 failed ({failures[0][:200]}); retrying")
                continue
            raws.append(raw)
            result = checks.check_answer(body, raw, prompt_lines, "\n".join(body.values()))
            if result.ok:
                break
            failures = result.failures
            entry["attempt_problems"].append(failures[:30])
            attempt_prompt = retry_prompt(prompt, failures)
            if attempt == 1:
                st.log(f"  work {n}: attempt 1 rejected ({len(failures)} problem(s)): {_short(failures)}; retrying")
        entry["seconds"] = round(time.monotonic() - t0, 1)
        if result is None or not result.ok:
            entry["result"] = ("failed_checks" if result is not None else "failed_model_call")
            entry["failures"] = failures[:30]
            if result is not None:
                entry["warnings"] = result.warnings[:30]
            _save_failed_raw(st, n, raws)
            return entry
        entry.update(_stats(result))
    else:
        entry["result"] = "ok"
        entry["note"] = "no prose paragraphs to restore; pages copied as they are"
    # write: restored body pages, every other page copied as it is
    for p in nums:
        pid = f"page_{p:04d}"
        text = result.pages[pid] if result is not None and pid in result.pages else texts[p]
        atomic_write_text(_out_file(st, p), text)
    _clear_failed_raw(st, n)
    entry["ok"] = True
    entry["result"] = "ok"
    entry["finished"] = now_iso()
    return entry


def _short(problems: list[str], limit: int = 400) -> str:
    s = " | ".join(problems)
    return s if len(s) <= limit else s[:limit] + " ..."


def saved_answers(st: Settings, n: int) -> list[tuple[str, str]]:
    d = _failed_dir(st)
    out = []
    if d.is_dir():
        for f in sorted(d.glob(f"work_{n:03d}_try*.txt"), reverse=True):       # the later try first
            try:
                out.append((f.name, f.read_bytes().decode("utf-8")))
            except (OSError, UnicodeDecodeError):
                pass
    return out


def _stats(r: checks.Check) -> dict:
    return {"names": [{"from": a, "to": b} for a, b in r.names],
            "readings": [{"from": a, "to": b} for a, b in r.readings],
            "readings_dropped": r.readings_dropped, "names_dropped": r.names_dropped,
            "unclear": sum(r.unclear.values()), "unclear_by_page": {k: v for k, v in r.unclear.items() if v},
            "unclear_chars": r.unclear_chars, "length_ratio": r.ratio, "page_ratios": r.page_ratios,
            "warnings": r.warnings[:30], "new_capitalised_words": r.new_names}


def _failed_dir(st: Settings) -> Path:
    return st.out_dir / "_failed"


def _save_failed_raw(st: Settings, n: int, raws: list[str]) -> None:
    _clear_failed_raw(st, n)
    for i, raw in enumerate(raws, 1):
        atomic_write_text(_failed_dir(st) / f"work_{n:03d}_try{i}.txt", raw if raw.endswith("\n") else raw + "\n")


def _clear_failed_raw(st: Settings, n: int) -> None:
    d = _failed_dir(st)
    if d.is_dir():
        for f in d.glob(f"work_{n:03d}_try*.txt"):
            try:
                f.unlink()
            except OSError:
                pass


# ------------------------------------------------------------------ whole book
def restore_book(st: Settings) -> dict:
    """Run every selected work; -> {"ok": n, "failed": [n...], "skipped": [n...], "report": path}."""
    spec = resolve_model(st.model_id)
    template = st.prompt_path.read_text(encoding="utf-8")
    prompt_lines = checks.prompt_lines_of(template + "\n" + RETRY_HEAD)
    prompt_sha = sha(template)
    rep = load_report(st)
    done, failed, skipped = [], [], []
    todo = [w for w in st.works if st.only is None or w["n"] in st.only]
    if st.only is not None:
        missing = sorted(st.only - {w["n"] for w in st.works})
        if missing:
            raise RestoreError("no_such_work", f"no such work number(s) in the catalogue: {', '.join(map(str, missing))}")
    for i, work in enumerate(todo, 1):
        n = work["n"]
        if not work.get("pdf_pages"):
            rep["works"][str(n)] = {"n": n, "title": work.get("title"), "ok": False, "result": "no_pages_in_catalogue"}
            failed.append(n)
            save_report(st, rep, prompt_sha)
            continue
        got = [(p, read_page(st.clean_dir, p)) for p in page_ids(work)]
        in_hash = input_hash(template, got) if all(t is not None for _, t in got) else ""
        if in_hash and is_done(st, work, rep["works"].get(str(n)), in_hash):
            skipped.append(n)
            st.log(f"[{i}/{len(todo)}] work {n} {work.get('title')}: already restored, skipped")
            continue
        st.log(f"[{i}/{len(todo)}] work {n} {work.get('title')} ...")
        entry = restore_work(st, work, spec, template, prompt_lines, rep["works"].get(str(n)))
        rep["works"][str(n)] = entry
        save_report(st, rep, prompt_sha)
        if entry["ok"]:
            done.append(n)
            st.log(f"  ok in {entry['seconds']}s, {len(entry.get('names', []))} name(s), {len(entry.get('readings', []))} reading(s), {entry.get('unclear', 0)} unclear, "
                   f"length x{entry.get('length_ratio', 1.0)}")
        else:
            failed.append(n)
            st.log(f"  FAILED: {entry['result']}: " + "; ".join(entry.get("failures", []))[:300])
    return {"ok": done, "failed": failed, "skipped": skipped, "report": str(report_path(st))}


def dry_check_saved(st: Settings, work: dict, template: str, prompt_lines: set[str], rep: dict) -> str | None:
    """Read-only: what the next run would do with the saved raw answers of a failed work. None when there is nothing to say."""
    n = work["n"]
    prev = rep.get("works", {}).get(str(n))
    if not prev or prev.get("ok"):
        return None
    texts = [(p, read_page(st.clean_dir, p)) for p in page_ids(work)]
    if any(t is None for _, t in texts):
        return None
    saved = saved_answers(st, n)
    if not saved:
        return f"work {n}: failed earlier, no saved answer"
    if prev.get("input_hash") != input_hash(template, texts):
        return f"work {n}: saved answers belong to another input or prompt; the next run calls the model"
    body = {f"page_{p:04d}": t for p, t in texts if page_type(t) == "body"}
    out = []
    for name, raw in saved:
        r = checks.check_answer(body, raw, prompt_lines, "\n".join(body.values()))
        out.append(f"{name}: " + ("PASSES the current checks (the next run uses it without a model call)" if r.ok
                                  else "still rejected: " + _short(r.failures, 300)))
    return f"work {n}: " + "; ".join(out)
