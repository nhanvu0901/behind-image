"""The long job "Viết tựa video" (`POST /api/projects/{pid}/title/generate`, action `title.generate`): an agent reads the approved narration and writes the video's title
by the written skill `skills/title/TASK.template.md`. One part, about a minute of a model:

    1. the work folder (copies of the narration, the outline's thesis and hook, the painting) and the rendered task
    2. one agent session in it (`bti.picks.auto.session.run_session`: Antigravity's `agy` or Claude Code's `claude`, the draft's confinement, a time limit, a step limit,
       one repair round with the program's own check (`helper.run_check`, the same `./check` prints))
    3. the checked file becomes the project's `title.json`: the candidates, and the first one as the title in use. A title a person set before is replaced only because
       this generation was asked for (by hand); the automatic run never starts one over a person's title (the state answer does not list the action then).
    4. the storyboard, when one exists, takes the new title (`bti.title.apply`)

The job is of kind `title`. It holds the project's one agent run: it does not start while the pictures agent, a prompt-box turn, a draft or an automatic run (other than the
caller itself) works on the project, and none of those starts while it runs (`bti.draft.run.other_agent_job`)."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from bti import agents as AG
from bti.draft import run as draft_run
from bti.draft.inputs import DraftError
from bti.picks.auto import session
from bti.script.store import now_iso

from . import apply as tapply
from . import helper, inputs as tinputs, store, texts, workspace
from .store import TitleError

KIND = "title"
ACTION = "generate"
ROLE = "script.title"
LIMITS = session.Limits(minutes=10, steps=40, repairs=1)
HELPERS = ("check",)                           # the work folder has the `check` helper and no `crop` (that one is the pictures job's)
EST_SECONDS = 90
KEEP_RUNS = 5


def _manager():
    import bti.longjob as lj
    return lj.manager


def actor_of(model: str) -> str:
    return "agent:" + model


def _runs_dir(pdir: Path) -> Path:
    return Path(pdir) / "cache" / "title" / "runs"


def _transcript(pdir: Path, started: float) -> Path | None:
    if not Path(pdir).is_dir():
        return None
    d = _runs_dir(pdir) / time.strftime("%Y%m%d-%H%M%S", time.localtime(started))
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return d / "title-events.jsonl"


def _prune(pdir: Path) -> None:
    """Keep the transcripts of the newest KEEP_RUNS runs (folders under cache/title/runs that this module made, one level deep)."""
    try:
        runs = sorted(p for p in _runs_dir(pdir).iterdir() if p.is_dir() and not p.is_symlink())
    except OSError:
        return
    for p in runs[:-KEEP_RUNS]:
        try:
            for f in p.iterdir():
                if f.is_file() and not f.is_symlink():
                    f.unlink()
            p.rmdir()
        except OSError:
            pass


def _fail(out: session.Outcome, ctx):
    from bti.longjob import PartError
    if out.status == "tampered":
        return PartError("title_tampered", texts.vi("title_tampered"))
    if out.status == "limit":
        return PartError("title_limit", texts.vi("title_limit"))
    if out.status in ("error", "timeout") and out.code:
        if out.retry_after_seconds:
            ctx.meta.update(draft_run.rate_limit_fields(out.retry_after_seconds))
        return PartError(out.code, out.message or texts.vi(out.code))
    return PartError("title_no_output", texts.vi("title_no_output"))


def make_parts(pdir: Path, inp: tinputs.Inputs, res, *, actor: str | None, note: str | None, seams: dict):
    from bti.longjob import Part, PartError
    started = time.time()

    def run(ctx):
        if ctx.cancelled():
            return None
        workspace.clean_old()
        try:
            ws = workspace.build(inp, LIMITS, python=seams.get("python"))
        except TitleError as e:
            raise PartError(e.code, texts.vi(e.code, e.message))
        ctx.progress(0.02, "Đã chuẩn bị dữ liệu cho agent.")
        try:
            out = session.run_session(ws.root, model=res.model, project_dir=pdir, ctx=ctx, label=texts.LABEL, limits=LIMITS,
                                      check_fn=lambda: helper.run_check(ws.root).problems(), transcript=_transcript(pdir, started),
                                      python=seams.get("python"), guard_factory=seams.get("guard_factory"),
                                      allow=session.allow_rules(helpers=HELPERS))
        except DraftError as e:
            shutil.rmtree(ws.root, ignore_errors=True)
            raise PartError(e.code, session.refuse_text(e))
        rep = helper.run_check(ws.root)
        if out.status == "cancelled" or ctx.cancelled():
            shutil.rmtree(ws.root, ignore_errors=True)
            return None
        if out.status == "tampered" or not rep.ok:
            raise _fail(out, ctx)                      # the work folder is kept for a look (the draft does the same)
        written = {"at": now_iso(), "model": res.model, "agent": res.public(), "note": note, "job_id": ctx.job_id, "requested_by": actor, "warnings": rep.warnings,
                   "session": {"steps": out.steps, "turns": out.turns, "repairs": out.repairs, "status": out.status, "elapsed": round(out.elapsed)}}
        try:
            doc = store.write_generated(pdir, rep.value["candidates"], by=actor_of(res.model), narration_rev_=inp.narration_rev, written=written)
        except OSError as e:                           # the project folder is gone, or the disk refused
            raise PartError("title_no_output", "%s (%s)" % (texts.vi("title_no_output"), type(e).__name__))
        shutil.rmtree(ws.root, ignore_errors=True)
        _prune(pdir)
        sb = tapply.apply_to_storyboard(pdir, doc["chosen"]["text"])
        sentence = texts.result_sentence(len(doc["candidates"]), doc["chosen"]["text"])
        if sb is not None and sb.get("off_voice"):           # the title is stored; the storyboard takes it when it has been fitted to the voice
            sentence += " " + sb["sentence"]
        ctx.progress(1.0, sentence)
        result = {"title": doc["chosen"]["text"], "candidates": len(doc["candidates"]), "warnings": rep.warnings, "sentence": sentence, "agent": res.public(),
                  "limits": LIMITS.public(), "session": written["session"]}
        if sb is not None:
            result["storyboard"] = sb
        return result

    return [Part(key="title", title=texts.PART_TITLE, run=run, est_seconds=EST_SECONDS)]


def start(pid: str, pdir: Path, *, note=None, model: str | None = None, actor: str | None = None, by_run: bool = False, manager=None, **seams) -> dict:
    """Start the job; -> the job's public record (`["id"]`). Raises `TitleError` (the refusals of the route, with their HTTP status). `by_run`: the caller is the automatic run (it
    takes this action itself as its step): the run's own job is not a reason to refuse, any other caller is refused while a run goes on. `seams` (tests): python, guard_factory."""
    pdir = Path(pdir)
    if model is not None and (not isinstance(model, str) or draft_run._bad_model_name(model)):
        raise TitleError("bad_model", "the model name is not valid", 422, field="model")
    note = tinputs.check_note(note)
    inp = tinputs.load(pdir, note)
    res = draft_run._resolve(pdir, ROLE, model)
    try:
        session.check_installed(res.model)
    except DraftError as e:
        raise TitleError(e.code, e.message, 409)
    m = manager or _manager()
    other = draft_run.other_agent_job(pid, KIND, m, run_ok=by_run)
    if other is not None:
        raise TitleError("agent_job_running", "%s is working on this project: wait for it or cancel it, then call again" % draft_run.AGENT_JOB_WHO.get(other.get("kind"), "another job"),
                         409, job_id=other.get("id"))
    meta = {"action": ACTION, "model": res.model, "agent": res.public(), "limits": LIMITS.public(), "requested_by": actor, **({"note": note} if note else {})}
    try:
        return m.start(kind=KIND, pid=pid, project_dir=pdir, parts=make_parts(pdir, inp, res, actor=actor, note=note, seams=seams), meta=meta)
    except Exception as e:      # noqa: BLE001
        if type(e).__name__ == "Busy":
            raise TitleError("longjob_running", "a title job is already running for this project", 409, job_id=getattr(e, "job_id", None))
        raise


def active_job(pid: str) -> dict | None:
    try:
        return _manager().active(pid, kind=KIND)
    except Exception:       # noqa: BLE001
        return None
