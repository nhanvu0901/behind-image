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
from .store import (NChapter, Narration, disk_rev, keep_paste, clear_paste, load_narration, load_outline, now_iso,
                    save_narration, save_outline, script_dir, script_lock)
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


_UNSET = object()


def run_outline(job: Job, pdir: Path, spec: dict, notes: str = "", *, wps: float = WPS_DEFAULT, base_rev=_UNSET) -> None:
    """`base_rev`: the revision of outline.json (None = no file) the owner's request started from. The route fixes it BEFORE it
    returns the job id; this thread never decides what the base was (R3B-014). Left out, it is read here (direct callers)."""
    brief = build_brief(pdir)
    opts = load_options(pdir)
    start_rev = disk_rev(script_dir(pdir) / "outline.json", "outline") if base_rev is _UNSET else base_rev
    job.chapters = [{"id": "outline", "title": "Dàn ý", "state": "running", "attempts": 0, "words": 0, "message": ""}]
    retry = None
    for attempt in (1, 2):
        job.set_chapter("outline", attempts=attempt, state="running" if attempt == 1 else "retrying")
        p = build_prompt("outline", pdir, notes=notes, brief=brief, retry_message=retry, wps=wps)
        text = call_model(spec, p["system"], p["user"], job)
        res = parse_outline(text, set(brief["paragraph_ids"]), target_words=opts["target_words"])
        if res.ok:
            o = res.outline
            o.source = {"kind": "model", "model": spec["id"], "created_at": now_iso()}
            with script_lock(pdir):
                if job.stopped:
                    return
                if disk_rev(script_dir(pdir) / "outline.json", "outline") != start_rev:
                    # The outline was saved by the owner while the model ran. A generated outline replaces the whole
                    # document, so it is never written over their save: it goes to the paste box instead.
                    keep_paste(pdir, "outline", text)
                    job.set_chapter("outline", state="failed", message="outline changed while the model ran")
                    raise JobError("conflict", "The outline was saved while the model was writing, so the model's outline was "
                                               "not written over it. It was kept in the paste box; import it if you want it.")
                rev = save_outline(pdir, o, start_rev)
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
                  wps: float = WPS_DEFAULT, base_locked=_UNSET) -> None:
    """`base_locked`: the ids of the beats that were locked when the owner's request started (fixed by the route before the
    job id was returned); a beat locked after that, while the model ran, makes its chapter be skipped (R3B-014)."""
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
    start_locked = ({b.id for c in narr.chapters for b in c.beats if b.locked}     # locks that already stood (force replaced them)
                    if base_locked is _UNSET else set(base_locked))
    written: list[str] = []
    skipped: list[dict] = []
    job.result = {"written": written, "skipped": skipped}
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
        # Finish the chapter against the document AS IT IS ON DISK NOW, under the lock every save takes: only this chapter is
        # replaced; whatever the owner saved to other chapters while the model ran is kept.
        with script_lock(pdir):
            if job.stopped:
                return
            cur = load_narration(pdir) or Narration(project=pdir.name, title=brief["painting"]["title"], language="en")
            old = cur.chapter(cid)
            new_locks = [b.id for b in (old.beats if old else []) if b.locked and b.id not in start_locked]
            if new_locks:
                skipped.append({"chapter": cid, "beats": new_locks, "reason": "locked while the job ran"})
                job.set_chapter(cid, state="skipped", message="beats locked while the job ran: " + ", ".join(new_locks))
                narr = cur
                job.result = {"written": written, "skipped": skipped, "rev": cur.rev()}
                job.changed()
                continue
            beats = ch.beats
            taken = {b.id for c in cur.chapters if c.id != cid for b in c.beats}
            for b in beats:                     # ids the owner's edits used in the meantime are never reused
                if b.id in taken or not b.id:
                    b.id = cur.new_beat_id()
                taken.add(b.id)
            cur.counters["beat"] = max(cur.counters["beat"], res.narration.counters["beat"])
            new = NChapter(cid, oc.role, oc.title, oc.card, beats)
            order = {c.id: i for i, c in enumerate(outline.chapters)}
            cur.chapters = [c for c in cur.chapters if c.id != cid] + [new]
            cur.chapters.sort(key=lambda c: order.get(c.id, 10_000))
            cur.source = {"kind": "model", "model": spec["id"], "created_at": now_iso(), "outline_sha1": outline.rev()}
            cur.title = cur.title or brief["painting"]["title"]
            rev = save_narration(pdir, cur, backup=first_save)
            first_save = False
            clear_paste(pdir, "narration")
            narr = cur                          # the next chapter's prompt sees the owner's edits too
            written.append(cid)
        job.result = {"written": written, "skipped": skipped, "rev": rev}
        words = sum(len(b.text.split()) for b in new.beats)
        job.set_chapter(cid, state="done", words=words, message="")
