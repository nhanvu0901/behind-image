"""The two model jobs: draft the outline, write the narration chapter by chapter.

Both paths (button and paste) end in the same parsers and the same files. Finished chapters are saved as they
complete, so a failure, a cancel or a timeout keeps what was written.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from .brief import build_brief, load_options
from .parse import parse_outline, parse_script
from .prompting import build_prompt
from .providers import ProviderError, get_provider
from .runner import Job, JobError
from .stats import WPS_DEFAULT
from .store import (NChapter, Narration, keep_paste, clear_paste, load_narration, load_outline, now_iso,
                    save_narration, save_outline)
from .validate import markup_in, outline_gate

PER_CALL_TIMEOUT = 300.0


def call_model(spec: dict, system: str, user: str, job: Job, *, timeout: float | None = None) -> str:
    """One provider call with a hard deadline and cancel. The call runs in a helper thread that is abandoned
    (it holds only the request, which has its own timeout) when the deadline passes or the job is cancelled."""
    timeout = float(timeout or spec.get("timeout") or PER_CALL_TIMEOUT)
    box: dict = {}
    complete = get_provider(spec["provider"])

    def target() -> None:
        try:
            box["text"] = complete(spec, system, user, timeout=timeout, cancel=job.cancel)
        except BaseException as e:      # noqa: BLE001
            box["err"] = e

    t = threading.Thread(target=target, daemon=True, name="model-call")
    t.start()
    deadline = time.time() + timeout + 5
    while t.is_alive():
        t.join(0.1)
        if job.cancel.is_set():
            raise JobError("cancelled", "cancelled")
        if time.time() > deadline:
            raise JobError("timeout", f"no answer within {int(timeout)} seconds")
    if "err" in box:
        e = box["err"]
        if isinstance(e, ProviderError):
            raise JobError("cancelled" if e.kind == "cancelled" else e.kind, e.message)
        raise e
    return box["text"]


def _retry_text(msg: str, limit: int = 1500) -> str:
    return msg if len(msg) <= limit else msg[:limit] + " ..."


def run_outline(job: Job, pdir: Path, spec: dict, notes: str = "", *, wps: float = WPS_DEFAULT) -> None:
    brief = build_brief(pdir)
    opts = load_options(pdir)
    job.chapters = [{"id": "outline", "title": "Dàn ý", "state": "running", "attempts": 0, "words": 0, "message": ""}]
    retry = None
    for attempt in (1, 2):
        job.set_chapter("outline", attempts=attempt, state="running" if attempt == 1 else "retrying")
        p = build_prompt("outline", pdir, notes=notes, brief=brief, retry_message=retry, wps=wps)
        text = call_model(spec, p["system"], p["user"], job)
        res = parse_outline(text, set(brief["paragraph_ids"]), target_words=opts["target_words"])
        if res.ok:
            if job.stopped:
                return
            o = res.outline
            o.source = {"kind": "model", "model": spec["id"], "created_at": now_iso()}
            rev = save_outline(pdir, o)
            clear_paste(pdir, "outline")
            job.set_chapter("outline", state="done", message=f"{len(o.chapters)} chương, {len(o.facts)} dữ kiện")
            job.result = {"rev": rev, "issues": res.issues}
            return
        retry = _retry_text(res.error or "the outline could not be read")
        job.set_chapter("outline", message="retry: " + retry.splitlines()[0][:160])
    keep_paste(pdir, "outline", text)
    job.set_chapter("outline", state="failed", message=retry.splitlines()[0][:200])
    raise JobError("parse", "The model's answer could not be read as an outline, even after one retry. "
                            "Its text was kept in the paste box.\n" + retry)


def chapter_problems(ch: NChapter | None, cid: str) -> str | None:
    if ch is None or not ch.beats:
        return f"Chapter {cid} is missing from your answer, or has no paragraphs."
    bad = []
    for b in ch.beats:
        if not b.text.strip():
            bad.append(f"a paragraph in {cid} is empty")
        else:
            m = markup_in(b.text)
            if m:
                bad.append(f"a paragraph in {cid} contains {m}: \"{b.text[:60]}...\"")
    if bad:
        return ("Validation failed: " + "; ".join(bad[:4]) + ". The paragraphs must hold spoken words only, with the "
                "facts and the picture hint on the >> line.")
    return None


def run_narration(job: Job, pdir: Path, spec: dict, chapters: list[str] | None = None, notes: str = "", *,
                  wps: float = WPS_DEFAULT) -> None:
    outline = load_outline(pdir)
    gate = outline_gate(outline)
    if gate:
        raise JobError("conflict", gate["message"])
    brief = build_brief(pdir)
    narr = load_narration(pdir) or Narration(project=pdir.name, title=brief["painting"]["title"], language="en")
    want = [c.id for c in outline.chapters if (not chapters or c.id in chapters)]
    job.chapters = [{"id": c.id, "title": c.title, "state": "pending", "attempts": 0, "words": 0, "message": ""}
                    for c in outline.chapters if c.id in want]
    first_save = True
    for cid in want:
        if job.cancel.is_set():
            raise JobError("cancelled", "cancelled")
        oc = outline.chapter(cid)
        retry, text = None, ""
        ok = False
        for attempt in (1, 2):
            job.set_chapter(cid, state="running" if attempt == 1 else "retrying", attempts=attempt)
            p = build_prompt("script", pdir, notes=notes, chapters=[cid], narration=narr, outline=outline,
                             brief=brief, retry_message=retry, wps=wps)
            text = call_model(spec, p["system"], p["user"], job)
            has_heads = any(ln.lstrip().startswith("##") for ln in text.splitlines())
            use = outline
            if not has_heads:
                import copy
                use = copy.copy(outline)
                use.chapters = [oc]
            res = parse_script(text, use, project=pdir.name, counter_start=narr.counters["beat"])
            problem = res.error if not res.ok else None
            ch = None
            if res.ok:
                ch = res.narration.chapter(cid)
                problem = chapter_problems(ch, cid)
            if problem is None:
                ok = True
                break
            retry = _retry_text(problem)
            job.set_chapter(cid, message="retry: " + retry.splitlines()[0][:160])
        if not ok:
            keep_paste(pdir, "narration", text)
            job.set_chapter(cid, state="failed", message=retry.splitlines()[0][:200])
            raise JobError("validation", f"Chapter {cid} failed validation twice ({retry.splitlines()[0][:200]}). "
                                         "The chapters written so far were kept, and the last answer is in the paste box.")
        if job.stopped:
            return
        # keep ids: the new beats continue the counter; the replaced chapter keeps its place in the outline order
        narr.counters["beat"] = max(narr.counters["beat"], res.narration.counters["beat"])
        new = NChapter(cid, oc.role, oc.title, oc.card, ch.beats)
        order = {c.id: i for i, c in enumerate(outline.chapters)}
        narr.chapters = [c for c in narr.chapters if c.id != cid] + [new]
        narr.chapters.sort(key=lambda c: order.get(c.id, 10_000))
        narr.source = {"kind": "model", "model": spec["id"], "created_at": now_iso(), "outline_sha1": outline.rev()}
        narr.title = narr.title or brief["painting"]["title"]
        rev = save_narration(pdir, narr, backup=first_save)
        first_save = False
        clear_paste(pdir, "narration")
        words = sum(len(b.text.split()) for b in new.beats)
        job.set_chapter(cid, state="done", words=words, message="")
        job.result = {"rev": rev}
