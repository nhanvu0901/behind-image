"""The two model jobs: draft the outline, write the narration chapter by chapter.

Both paths (button and paste) end in the same parsers and the same files. Finished chapters are saved as they
complete, so a failure, a cancel or a timeout keeps what was written.
"""
from __future__ import annotations

import copy
import threading
import time
from pathlib import Path

from .brief import build_brief, load_options
from .parse import parse_outline, parse_script
from .prompting import build_prompt, cut_note
from .providers import ProviderError, get_provider
from .runner import Job, JobError
from .stats import WPS_DEFAULT, count_words
from .store import (NChapter, Narration, disk_rev, keep_paste, clear_paste, load_narration, load_outline, now_iso,
                    save_narration, save_outline, script_dir, script_lock)
from .validate import markup_in, outline_gate

PER_CALL_TIMEOUT = 300.0

# THE length rule of the narration job: the budget of a chapter is a ceiling. A chapter that comes out more than CUT_OVER_SHARE over its budget is written
# again ONCE, with a note that says how many words to cut (`prompting.cut_note`); at most MAX_CUTS chapters of one job get that second call (each one is a model
# call more); the rewrite is kept only when it can be used and is nearer to the budget, otherwise the first text stays and the checks warn as before
# (`chapter_off_budget`, `words_off_target`). The job says what happened in the chapter's message and in `result["shortened"]`.
CUT_OVER_SHARE = 0.10
MAX_CUTS = 4


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
            raise JobError("cancelled" if e.kind == "cancelled" else e.kind, e.message, getattr(e, "retry_after_seconds", None))
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


def chapter_words(ch: NChapter) -> int:
    return sum(count_words(b.text) for b in ch.beats)


def over_budget(words: int, budget: int) -> bool:
    """True when `words` is more than CUT_OVER_SHARE over a (known) budget."""
    return budget > 0 and words > budget * (1 + CUT_OVER_SHARE)


def _read_chapter(text: str, outline, oc, pdir: Path, counter_start: int):
    """(the parse result, the chapter, what is wrong with it or None) of a model's answer for the chapter `oc`."""
    has_heads = any(ln.lstrip().startswith("##") for ln in text.splitlines())
    use = outline
    if not has_heads:
        use = copy.copy(outline)
        use.chapters = [oc]
    res = parse_script(text, use, project=pdir.name, counter_start=counter_start)
    problem = res.error if not res.ok else None
    ch = None
    if res.ok:
        ch = res.narration.chapter(oc.id)
        problem = chapter_problems(ch, oc.id)
    return res, ch, problem


def _cut_once(job: Job, pdir: Path, spec: dict, outline, oc, narr, brief: dict, notes: str, wps: float, res, ch, calls: int):
    """The one rewrite of a chapter that is over its budget. -> (parse result, chapter, record of what happened); the first text is returned
    (with a record that says why) whenever the rewrite cannot be used or is not nearer to the budget."""
    words, budget = chapter_words(ch), oc.word_budget
    rec = {"chapter": oc.id, "words": words, "budget": budget}
    job.set_chapter(oc.id, state="retrying", attempts=calls + 1, message=f"viết lại ngắn hơn: {words} từ, ngân sách {budget}")
    try:
        p = build_prompt("script", pdir, notes=notes, chapters=[oc.id], narration=narr, outline=outline, brief=brief, wps=wps,
                         cut_message=cut_note(words, budget, ch))
        text = call_model(spec, p["system"], p["user"], job)
    except JobError as e:
        if e.kind == "cancelled":
            raise
        return res, ch, {**rec, "kept": "first", "why": "the second call failed (%s)" % e.kind}
    res2, ch2, problem = _read_chapter(text, outline, oc, pdir, narr.counters["beat"])
    if problem is not None:
        return res, ch, {**rec, "kept": "first", "why": "the rewrite could not be used"}
    after = chapter_words(ch2)
    if abs(after - budget) >= abs(words - budget):
        return res, ch, {**rec, "after": after, "kept": "first", "why": "the rewrite is not nearer to the budget"}
    return res2, ch2, {**rec, "after": after, "kept": "rewrite"}


def _cut_message(rec: dict) -> str:
    """What the chapter line of the job says afterwards (Vietnamese: the page and `bti job` show it)."""
    if rec["kept"] == "rewrite":
        return f"đã cắt từ {rec['words']} xuống {rec['after']} từ (ngân sách {rec['budget']})"
    return f"giữ bản đầu {rec['words']} từ, vượt ngân sách {rec['budget']}: bản viết lại không dùng được hoặc không ngắn hơn"


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
    shortened: list[dict] = []          # the chapters that came out over their budget and were written again (see CUT_OVER_SHARE)

    def result_of(rev: str | None = None) -> dict:
        out = {"written": written, "skipped": skipped}
        if shortened:
            out["shortened"] = shortened
        if rev is not None:
            out["rev"] = rev
        return out
    job.result = result_of()
    for cid in want:
        if job.cancel.is_set():
            raise JobError("cancelled", "cancelled")
        oc = outline.chapter(cid)
        retry, text = None, ""
        ok = False
        res = ch = None
        for attempt in (1, 2):
            job.set_chapter(cid, state="running" if attempt == 1 else "retrying", attempts=attempt)
            p = build_prompt("script", pdir, notes=notes, chapters=[cid], narration=narr, outline=outline,
                             brief=brief, retry_message=retry, wps=wps)
            text = call_model(spec, p["system"], p["user"], job)
            res, ch, problem = _read_chapter(text, outline, oc, pdir, narr.counters["beat"])
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
        done_message = ""
        if over_budget(chapter_words(ch), oc.word_budget) and len(shortened) < MAX_CUTS and not job.cancel.is_set():
            res, ch, rec = _cut_once(job, pdir, spec, outline, oc, narr, brief, notes, wps, res, ch, attempt)
            shortened.append(rec)
            done_message = _cut_message(rec)
            job.result = result_of()
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
                job.result = result_of(cur.rev())
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
        job.result = result_of(rev)
        job.set_chapter(cid, state="done", words=sum(len(b.text.split()) for b in new.beats), message=done_message)
