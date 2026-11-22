"""`GET /api/projects/{pid}/state`: where the project is, what blocks it, and every call that can be made now (contract: the part
"Trạng thái và việc tiếp theo" of docs/design/2026-11-18-agent-first-design.html; the answer is documented in docs/AGENT_API.md).

    {project, stage, current, steps: [{step, label, state, page_state, detail, blocked_by}], next_actions: [...], jobs: [...],
     problems: [{code, step, detail, fix}]}

The steps come from `pipeline_api.compute`, the computation the page's step bar uses, so the page and an agent never disagree.
`state` is one of done | current | locked (`page_state` keeps the page's own word: available, waiting or no_data for the
steps that are none of those three). A caller that wants to know what to do reads `next_actions`: every entry names the real
route, an example body that is valid as it stands (or null, then `fill` lists what the caller must supply), whether it can be
called now (`ready`, else `needs` lists the unmet conditions: see NEEDS), and what it costs.

Reads files and the stage packages' own small state functions; never calls a model and never starts a job. A project whose data is
damaged still answers: the step carries the problem, `problems` names it and the first action is the repair the API offers.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Request

from bti import agents as AG
from bti import auto as auto_mod                      # c5cli: which gates and which kinds of spending an agent may use
from bti.script import store as sstore

from . import hints as hints_mod
from . import pipeline_api
from .common import ApiError, compute_rev, read_json, safe_join, storyboard_approval, storyboard_shape_problem

log = logging.getLogger("bti.editor")

# ----------------------------------------------------------------------------------------------------------- the vocabulary of `needs`
# An unmet condition of an action that is not `ready`: a stable word, what it means and how to meet it.
NEEDS: dict[str, tuple[str, str]] = {
    "book_data": ("The project has no book data (it was imported from an earlier edit).", "Nothing: the script steps do not apply to this project."),
    "documents_readable": ("A document of the step cannot be read (see `problems`).", "Repair the file named in `problems`, then ask for the state again."),
    "outline": ("There is no outline yet.", "Make one: outline.generate or outline.import."),
    "outline_approved": ("The outline is not approved, or it changed after it was approved.", "Call outline.approve."),
    "narration": ("There is no narration yet.", "Write one: narration.generate or narration.import."),
    "narration_approved": ("The narration is not approved, or it changed after it was approved.", "Call narration.approve."),
    "voice_done": ("The voice is not made (or is out of date).", "Call voice.generate and wait for its job."),
    "picks": ("There are no picks yet.", "Import the main painting: picks.import (as_main) or picks.import_book_image."),
    "main_asset": ("No main painting is chosen in the picks.", "Import a picture with as_main true (picks.import), or send picks.put with main_asset."),
    "picks_errors": ("The picks have errors other than the main painting (a missing file, an unknown asset or region).", "Read `issues` of GET /api/projects/{pid}/picks and fix them."),
    "picks_approved": ("The picks are not approved, or they changed after they were approved.", "Call picks.approve."),
    "picks_saved_files": ("The saved files of the last run of the agent's choice of pictures (cache/picks_auto: plan, search, choice) are not in the project, so what the agent chose cannot be read again.",
                          "Call picks.auto for these lines (with redo true): it chooses again."),      # fixes4
    "storyboard": ("The project has no storyboard yet.", "Run draft.start, then proposal.apply."),
    "storyboard_readable": ("storyboard.json cannot be read.", "Call storyboard.restore."),
    "storyboard_approved": ("The storyboard is not approved, or it was edited after it was approved.", "Call storyboard.approve."),
    "history_copy": ("There is no good copy of the storyboard in history/.", "Make a new draft: draft.start."),
    "audio_mix": ("The audio mix the storyboard names is missing.", "Call voice.generate."),
    "timing": ("timing.json is missing.", "Call voice.generate."),
    "no_running_job": ("A job of the same kind is already running for this project; for the agent's work (picks.auto, picks.edit, draft.start, draft.edit) any other agent job of the project counts: the agent's choice of pictures, a prompt-box turn or a draft run one at a time; the two prompt boxes (picks.edit, draft.edit) also wait while an automatic run goes on.",
                       "Wait for it (see `jobs`), or cancel it with the matching *.cancel action."),
    "agent_usable": ("The agent that would run cannot run on this machine (see `agent.reason`).", "Choose another agent: PUT /api/projects/{pid}/agent, GET /api/agents lists them."),
    "suggest_enabled": ("Picture suggestions are switched off on this machine.", "Use picks.search instead."),
    "locked_beats": ("Some beats of the narration are locked and would be replaced.", "Unlock them, or send {\"force\": true} (the body shown does)."),
    "draft_proposal": ("There is no draft proposal to apply.", "Call draft.start and wait for its job."),
    "storyboard_fits_voice": ("The storyboard does not fit the voice: the cards, the channel-name beat or the end of the video sit where an earlier voice put them.",
                              "Call storyboard.retime (it moves them, and puts the opening shot in or takes it out), then ask for the state again."),
    # titlestep
    "title_done": ("The video's title is not written yet (or the narration changed after it was written), and an agent can write it.",
                   "Call title.generate and wait for its job, or set a title yourself with title.set."),
}


# ----------------------------------------------------------------------------------------------------------------- the catalogue
@dataclass(frozen=True)
class Spec:
    """What never changes about an action. `when` is the condition in words (it is the "condition" column of docs/AGENT_API.md)."""
    id: str
    step: str                       # the pipeline step this belongs to (steps[].step)
    label: str                      # Vietnamese, as the page's button says
    method: str
    path: str                       # the route as the app declares it; {pid} and the ids below are filled in
    when: str
    gate: bool = False
    long_job: bool = False
    follow: str | None = None       # how to follow the job the call answers with
    role: str | None = None         # the agent role it runs (bti.agents) when it uses a model
    cost: tuple[str, str] | None = None
    auto_ok: bool = True


P = "/api/projects/{pid}"
JOBS = "GET /api/jobs/{job_id}"
LONGJOBS = "GET /api/longjobs/{job_id}"

SPECS: list[Spec] = [
    # ---- script
    Spec("outline.generate", "script", "Lập dàn ý", "POST", P + "/outline/generate", long_job=True, follow=JOBS, role="script.outline",
         cost=("model", "a few minutes"),
         when="A project made from a book. Ready unless a model job of the project is running or the agent cannot run. Advances while there is no outline."),
    Spec("outline.import", "script", "Dán dàn ý", "POST", P + "/outline/import",
         when="A project made from a book. Always ready; the caller supplies the outline text (`fill`)."),
    Spec("outline.approve", "script", "Duyệt dàn ý", "POST", P + "/outline/approve", gate=True,
         when="While the outline is not approved. Needs an outline. Advances."),
    Spec("narration.generate", "script", "Viết lời dẫn", "POST", P + "/narration/generate", long_job=True, follow=JOBS, role="script.narration",
         cost=("model", "a few minutes"),
         when="A project made from a book. Needs the approved outline; refused while beats are locked unless forced; ready unless a model job is running or the agent cannot run. Advances while there is no narration."),
    Spec("narration.import", "script", "Dán lời dẫn", "POST", P + "/narration/import",
         when="A project made from a book. Needs an outline; the caller supplies the narration text (`fill`)."),
    Spec("narration.ops", "script", "Sửa lời dẫn", "POST", P + "/narration/ops",
         when="Needs a narration; the caller supplies the typed operations (`fill`)."),
    Spec("narration.approve", "script", "Duyệt lời dẫn", "POST", P + "/narration/approve", gate=True,
         when="While the narration is not approved. Needs a narration and the approved outline. Advances."),
    Spec("outline.cancel", "script", "Dừng", "POST", "/api/jobs/{job_id}/cancel", when="While an outline job of the project runs."),
    Spec("narration.cancel", "script", "Dừng", "POST", "/api/jobs/{job_id}/cancel", when="While a narration job of the project runs."),
    # ---- titlestep: the video's title (bti/title/, skills/title/SKILL.md)
    Spec("title.generate", "script", "Viết tựa video", "POST", P + "/title/generate", long_job=True, follow=LONGJOBS, role="script.title",
         cost=("model", "about 1 minute"),
         when="A project made from a book. Needs the approved narration, no other agent job running on the project (the pictures agent, a prompt-box turn, a draft, a title job) and a usable agent. "
              "An agent reads the narration and writes the title by the skill; the first of its candidates becomes the title in use (the storyboard, the export's description and the output folder use it). "
              "Advances while the title is not written (`none`) or the narration changed after it was written (`stale`) and the project has no storyboard yet (a title written later changes the storyboard and so its approval: that is for the owner to ask); a title a person or an operator set is never stale and is replaced only by this call made by hand. "
              "The automatic run takes it by itself (nobody approves a title), before the voice. Optional body field `note` (text, at most 600 characters, `--set note=...`): the owner's wish for this title in their words."),
    Spec("title.set", "script", "Đặt tựa video", "PUT", P + "/title",
         when="A project made from a book. Always ready; the caller supplies `text` (`--set text=...`: one line of at most 60 characters; the banned phrases are not looked for), or sends `option` "
              "(the number, from 1, of a candidate of GET .../title) in a body of its own. Never stale afterwards. When the project has a storyboard the channel identity is applied again with the title "
              "in the same call: its revision changes and its approval stops standing (the answer says so). While the storyboard does not fit the voice (`storyboard_off_voice`) the title is stored all the same, "
              "the storyboard is left as it is and the answer says it takes the title when `storyboard.retime` has fitted it to the voice."),
    Spec("title.cancel", "script", "Dừng", "POST", "/api/longjobs/{job_id}/cancel", when="While a title job of the project runs."),
    # ---- voice
    Spec("voice.generate", "voice", "Tạo giọng đọc", "POST", P + "/voice/generate", long_job=True, follow=LONGJOBS,
         cost=("machine_time", "about 1 hour"),
         when="Once the narration is approved. Ready unless a voice job runs. Advances while the voice is not made or is out of date; when it is done the body re-reads everything."),
    Spec("voice.cancel", "voice", "Dừng", "POST", "/api/longjobs/{job_id}/cancel", when="While a voice job of the project runs."),
    # ---- picks
    Spec("picks.search", "picks", "Tìm hình", "POST", P + "/picks/search",
         when="Once the picks step is open. Always ready; the body searches the painting's title when the project knows it."),
    Spec("picks.import", "picks", "Nhập hình", "POST", P + "/picks/import",
         when="Once the picks step is open. The caller supplies a source and source_id from a search (`fill`)."),
    Spec("picks.import_book_image", "picks", "Nhập hình từ sách", "POST", P + "/picks/import-book-image",
         when="Once the picks step is open. The caller supplies a source_id from GET .../picks/book-images (`fill`)."),
    Spec("picks.import_clip", "picks", "Cắt clip video", "POST", P + "/picks/import-clip", long_job=True, follow=LONGJOBS,
         cost=("machine_time", "about 1 minute"),
         when="Once the picks step is open. Ready unless a picks job runs. The caller supplies the link and the range (`fill`)."),
    Spec("picks.suggest", "picks", "Gợi ý hình (tốn tiền)", "POST", P + "/picks/suggest", long_job=True, follow=LONGJOBS,
         cost=("paid", "You.com calls, charged per beat"), auto_ok=False,
         when="Once the picks step is open. Paid: `auto_ok` is false, the owner must agree. Needs the approved narration and suggestions switched on."),
    Spec("picks.put", "picks", "Lưu chọn hình", "PUT", P + "/picks",
         when="Once the picks step is open. The caller supplies the picks document (`fill`)."),
    Spec("picks.auto", "picks", "Để agent chọn hình", "POST", P + "/picks/auto", long_job=True, follow=LONGJOBS, role="picks",       # c3picks
         cost=("model", "about 20 minutes"),
         when="Once the picks step is open. Needs the approved narration, a main painting and a usable agent; refused while the picks are approved unless `redo` is true, and while another long job of the project runs (the agent's choice, a prompt-box turn or a draft: one at a time; an automatic run goes on: only the run itself, as the `actor` `agent:auto`, takes it, any other caller is refused with `agent_job_running`). It never approves and never calls the paid suggestion service. Advances while no line has pictures yet."),
    Spec("picks.retry_missing", "picks", "Tải lại hình đã chọn", "POST", P + "/picks/retry-missing", long_job=True, follow=LONGJOBS,         # fixes4
         when="Listed only while a line of the picks says that a picture the agent chose could not be downloaded (`missing` with the code `import_limited`: the source limited the downloads; a `web_budget` is not retried here). "
              "No model and no search: for each such line it reads what the agent chose in the saved files of the last run of picks.auto (cache/picks_auto: plan, search, choice, and the second choice when there is one), "
              "imports that picture (at most one request a second to a host, and a refusal of \"too many requests\" is waited for), and writes the line again the way picks.auto would have written it: the plan's pictures in the plan's order, "
              "the agent's reason as the note of the new picture, `missing` without what it fixed, one batch of the change log for the line (undoable). A line that was changed after the agent wrote it is left alone. "
              "Ready while such lines exist and the saved files are there (`picks_saved_files` otherwise), the picks are open, and no agent job runs. It advances once for the lines it has not looked at since the last run of picks.auto: "
              "the automatic run takes it once, before the pictures gate; a line still limited after that stays listed (call it again later by hand). Optional body field `beats` (a list of line ids) limits it to those lines. "
              "Writing drops the approval of the picks, as every edit does."),
    Spec("picks.tighten", "picks", "Đo lại khung chi tiết", "POST", P + "/picks/tighten", long_job=True, follow=LONGJOBS, role="picks",       # tightbox
         cost=("model", "about 5 minutes"),
         when="Listed only while the main painting has non-tight regions (`tight` not true). Runs a second-look session on 1,024-px gridded full-resolution cut-outs of those regions (confirmed on clean 6-per-sheet check images) and updates ONLY the main painting's regions in one undoable batch; never changes any beat's chosen pictures. Optional body field `regions` (a list of region names, or null for all non-tight regions) limits which regions are measured. Needs the picks step open, a usable agent and no agent job running; writing drops the approval of the picks, as every edit does. Never advances (`advances` is false: manual action, not part of automatic running)."),
    Spec("picks.edit", "picks", "Nhờ agent sửa chọn hình", "POST", P + "/picks/edit", long_job=True, follow=LONGJOBS, role="picks",       # c2box
         cost=("model", "about 30 seconds"),
         when="Once the picks step is open. Ready unless the agent cannot run, another long job of the project runs (a prompt-box turn, a draft or the agent's choice of pictures: one at a time) or an automatic run goes on. The caller supplies the instruction and the scope (`fill`): {\"beats\": [ids]}, {\"chapter\": id} or {\"all\": true}. One call, typed picks operations (never an import), one batch in the change log; a request that needs a new picture ends as `escalate`, and then POST .../picks/auto with those lines does the work."),
    Spec("picks.ops", "picks", "Sửa chọn hình", "POST", P + "/picks/ops",
         when="Once the picks step is open. `body` is a dry run (it writes nothing) of the registry's first example operation; send your own operations with `fill`. See docs/OPS.md."),
    Spec("picks.approve", "picks", "Duyệt chọn hình", "POST", P + "/picks/approve", gate=True,
         when="While the picks are not approved. Needs the approved narration, picks with a main painting and no errors. Advances."),
    Spec("picks.cancel", "picks", "Dừng", "POST", "/api/longjobs/{job_id}/cancel", when="While a picks job (suggestions, a clip or the agent's choice of pictures) of the project runs."),
    # ---- storyboard (step 5, page step id `edit`)
    Spec("draft.start", "edit", "Dựng bản nháp", "POST", P + "/draft/start", long_job=True, follow=LONGJOBS, role="draft",
         cost=("model", "about 20 minutes"),
         when="Once step 5 is open. Needs the voice and the approved picks, no draft job running, the pictures agent not working (one agent run at a time) and a usable agent. Advances while there is no draft (or it is out of date) and no storyboard. Optional body field `note` (text, at most 600 characters, `--set note=...`): the owner's wish for this draft (for example \"fewer close-ups\"), put into the agent's task file; leave it out when the owner gave none."),
    Spec("proposal.apply", "edit", "Áp dụng", "POST", P + "/proposals/{prop_id}/apply",
         when="While the project has no storyboard and a draft proposal exists. Advances when the draft is up to date."),
    Spec("storyboard.restore", "edit", "Khôi phục bản gần nhất", "POST", P + "/storyboard/restore",
         when="Only when storyboard.json is unreadable. Ready when history/ has a good copy. It is the repair: listed first."),
    Spec("storyboard.validate", "edit", "Kiểm tra", "GET", P,
         when="While the storyboard is readable. Always ready; the answer's `issues` are the validation of the saved storyboard."),
    Spec("storyboard.retime", "edit", "Khớp lại với giọng đọc", "POST", P + "/storyboard/retime",
         when="While the storyboard is readable, the voice is done and the storyboard does not fit it (a card, the channel-name beat or the end of the video sits where an earlier "
              "voice put it; the opening shot is missing or no longer needed): listed only then. No model and no cost. Moves them to where the voice puts them, puts the opening "
              "shot in or takes it out, and applies the identity style again with the project's title (`title.json`) on the channel-name beat; no shot of the model or the owner is changed except the start of the shot after the opening shot. "
              "One batch in the change log (undoable: `bti undo` gives back the whole document the batch changed, the shots, the end of the video and the identity). Advances when something can be moved; approving the storyboard and the export are refused (`storyboard_off_voice`) until it is done."),
    Spec("storyboard.approve", "edit", "Duyệt storyboard", "POST", P + "/approve", gate=True,
         when="While the storyboard is not approved (or was edited after). The route refuses while validation errors remain: call storyboard.validate first, and while the storyboard "
              "does not fit the voice (`storyboard_off_voice`: call storyboard.retime). Advances."),
    Spec("storyboard.preview", "edit", "Xem thử", "POST", P + "/preview", long_job=True, follow=JOBS,
         when="While the storyboard is readable. Ready; renders a short clip (a job of a few seconds)."),
    Spec("storyboard.put", "edit", "Lưu storyboard", "PUT", P + "/storyboard",
         when="While the storyboard is readable. The caller supplies the document (`fill`); base_rev is the current rev."),
    Spec("storyboard.ops", "edit", "Sửa storyboard", "POST", P + "/storyboard/ops",
         when="While the storyboard is readable. `body` is a dry run (it writes nothing) of the registry's first example operation; send your own operations with `fill`. See docs/OPS.md."),
    Spec("changes.list", "edit", "Lịch sử thay đổi", "GET", P + "/changes",
         when="Once the change log holds a batch (of the picks or the storyboard). Always ready. `step` is the step of the newest batch's document."),
    Spec("changes.undo", "edit", "Hoàn tác", "POST", P + "/changes/{batch}/undo",
         when="The newest batch that can be undone now: it still has its copies, nothing undid it, and nothing it changed was changed since. `step` is the step of its document."),
    Spec("draft.edit", "edit", "Nhờ agent sửa", "POST", P + "/draft/edit", long_job=True, follow=LONGJOBS, role="edit.fast",
         cost=("model", "from about 30 seconds to about 20 minutes"),
         when="While the storyboard is readable. Ready unless a draft job runs, the pictures agent is working (one agent run at a time), an automatic run goes on or the agent cannot run. The caller supplies the instruction and the scope (`fill`)."),
    Spec("identity.set", "edit", "Chọn kiểu mở đầu", "PUT", P + "/identity",
         when="While the storyboard is readable. The caller supplies the style (`fill`); GET .../identity lists them. Optional body field `video_title` (`--set video_title=...`): the video's title shown under the channel name, one line of at most 90 characters (an empty text takes it away); with a title the style may also be left out of a direct call to the route. Refused with `storyboard_off_voice` while the storyboard does not fit the voice (call storyboard.retime first; title.set stores a title in that case all the same)."),
    Spec("draft.cancel", "edit", "Dừng", "POST", "/api/longjobs/{job_id}/cancel", when="While a draft job of the project runs."),
    # ---- export
    Spec("export.start", "export", "Xuất video", "POST", P + "/export/start", long_job=True, follow=LONGJOBS,
         cost=("machine_time", "about 25 minutes"),
         when="Once the storyboard is approved. Ready unless an export runs, or the audio mix or timing is missing. Advances until a video is exported. Renders in ~60-second parts keyed by what each part shows; kept parts from the last export are reused, so a small edit costs only its changed parts."),
    Spec("export.cancel", "export", "Dừng", "POST", "/api/longjobs/{job_id}/cancel", when="While an export job of the project runs."),
    # ---- c6auto: the automatic run (bti/auto_run/): `step` is the step the project is at (the export is the last one, so this is its default)
    Spec("auto.run", "export", "Chạy tự động", "POST", P + "/auto/run", long_job=True, follow=LONGJOBS,
         cost=("machine_time", "the sum of what it may start from where the project stands"),
         when="Listed while automatic running is on for the project and no video is exported yet. Ready unless a job of the project runs (an automatic run included). "
              "Takes `until` (a step id) and `max_steps`; walks the project forward with the first allowed advancing action of this answer, until it is exported, or stops "
              "with a reason (see docs/AGENT_API.md, \"Chạy tự động\"). `cost` is the sum of what it may start: only the kinds the owner allowed."),
    Spec("auto.cancel", "export", "Dừng", "POST", "/api/longjobs/{job_id}/cancel", when="While an automatic run of the project goes on."),
    # ---- outfolder: the output folder (bti/output/)
    Spec("output.build", "export", "Ghi thư mục output", "POST", P + "/output/build",
         when="Listed when the app has an output folder (`output/<artwork key>/`) and the project is not a reference project. Always ready: fills (or refills) the folder from the project as it stands "
              "(the video, the readable documents, the log, the index); the body `{\"clean\": true}` also removes the working folder's caches when the export stands. A project of the same painting "
              "as the folder's last project takes it over."),
]
SPEC: dict[str, Spec] = {s.id: s for s in SPECS}
assert len(SPEC) == len(SPECS), "duplicate action id"

STEP_ORDER = [s[0] for s in pipeline_api.STEPS]
# page state -> the three words of `state`
STATE_OF = {"done": "done", "current": "current", "available": "current", "waiting": "locked", "locked": "locked", "no_data": "locked",
            "not_built": "locked"}
OPEN = ("done", "current", "available", "waiting")        # page states of a step that opens
BLOCKER_NEED = {"script": "narration_approved", "voice": "voice_done", "picks": "picks_approved", "edit": "storyboard_approved"}
ACTIVE_JOB = ("queued", "waiting", "running")
# what a running job of a kind blocks: the jobs kinds of one family run one at a time
FAMILY = {"outline": "script", "narration": "script", "voice": "voice", "draft": "draft", "export": "export", "picks": "picks", "auto": "auto", "title": "title"}      # titlestep: `title`
CANCEL_ID = {"outline": "outline.cancel", "narration": "narration.cancel", "voice": "voice.cancel", "draft": "draft.cancel",
             "export": "export.cancel", "picks": "picks.cancel", "auto": "auto.cancel", "title": "title.cancel"}
SCRIPT_JOB_KINDS = ("outline", "narration")


# --------------------------------------------------------------------------------------------------------------------------- facts
def _iso(ts: Any) -> str | None:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(float(ts)))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _try(fn: Callable, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:       # noqa: BLE001 - one fact that cannot be read never breaks the whole answer
        log.warning("state: a fact could not be read", exc_info=True)
        return default


class Ctx:
    """Everything the builders of the actions read. Built once per request."""

    def __init__(self, root: Path, pid: str, pipe: dict, jobs: list[dict], picks_provider: Any = None):
        self.root, self.pid, self.d = root, pid, root / pid
        self.pipe, self.jobs, self.picks_provider = pipe, jobs, picks_provider
        self.steps = {s["id"]: s for s in pipe.get("steps", [])}
        self.imported = bool(pipe.get("imported"))
        self.problems: list[dict] = []
        self._agents: dict[str, dict] = {}
        self._avail: dict[str, dict] = {}
        self.script_error: str | None = None
        self.outline = self.narration = None
        self.outline_rev = self.narration_rev = None
        self.outline_fresh = self.narration_ok = self.locked_beats = False
        self.picks = None
        self.picks_error: str | None = None
        self.picks_rev: str | None = None
        self.picks_main = self.picks_ok = False
        self.picks_lines = (0, 0)             # c3picks: (lines of the narration, lines that are settled: pictures or skipped)
        self.picks_issues: list[dict] = []
        self.non_tight_regions: list[str] = []            # tightbox: main-painting regions whose `tight` flag is not true
        self.retry_lines: list[str] = []                  # fixes4: the lines that say `import_limited` (picks.retry_missing)
        self.retry_files = False                          # ... whether the saved files of the last run of picks.auto are there
        self.retry_untried: list[str] = []                # ... and which of the lines it has not looked at yet
        self.narration_present = False
        self.draft_ready = {"voice": False, "picks": False}
        self.draft_state: dict = {"state": "none"}
        self.proposal: str | None = None
        self.sb_exists = self.sb_corrupt = self.sb_old_narration = False
        self.proposal_after_sb = False
        self.sb_rev: str | None = None
        self.sb_approval = "none"
        self.has_history = False
        self.has_audio = self.has_timing = True
        self.picks_ops_rev: str | None = None
        self.auto: dict = auto_mod.default_doc()          # c5cli: what the owner allowed (auto.json)
        self.sb_record: Any = None                        # c5cli: the storyboard's approval record
        self.sb_off: list = []                            # introflow: what of the storyboard does not sit where the voice puts it (bti/draft/retime.off_voice)
        self.change_count = 0
        self.change_doc: str | None = None
        self.undo_target: dict | None = None
        self.picks_agent_running = False                  # join2: the job of picks.auto runs (kind `picks`, meta.action `auto`): it holds the agent like a `draft` job does
        self.run_going = False                            # join2: an automatic run goes on (a job of kind `auto`): the request boxes are not started meanwhile
        self.output_root = None                           # outfolder: the app's output folder (None: this app has none)
        self.title_state, self.title_rev = "none", None   # titlestep: none | done | stale of the project's title, and the revision of title.json
        self.sb_title: str | None = None                  # titlestep: the video's title the saved storyboard already carries (`identity.video_title`), if any

    # -- steps
    def page_state(self, sid: str) -> str:
        return (self.steps.get(sid) or {}).get("state", "locked")

    def open(self, sid: str) -> bool:
        return self.page_state(sid) in OPEN

    def blocker_need(self, sid: str) -> list[str]:
        """The need of a step that is open but `waiting` on an earlier step (its page is read-only), else []."""
        s = self.steps.get(sid) or {}
        return [BLOCKER_NEED[s["blocked_by"]]] if s.get("state") == "waiting" and s.get("blocked_by") in BLOCKER_NEED else []

    def work(self, sid: str) -> str | None:
        return (self.steps.get(sid) or {}).get("work")

    # -- jobs
    def running(self, kind: str) -> dict | None:
        return next((j for j in self.jobs if j["kind"] == kind), None)

    def busy(self, family: str) -> bool:
        return any(FAMILY.get(j["kind"]) == family for j in self.jobs)

    def box_busy(self) -> bool:
        """join2: may a prompt-box turn (`picks.edit`, `draft.edit`) not start now? Another agent job runs, or an automatic run goes on (it takes the
        pictures agent and the draft itself, step by step, and a person's request in between would change what it reads)."""
        return self.agent_busy("draft") or self.run_going

    def agent_busy(self, family: str) -> bool:
        """join2: may the agent's work of `family` (`draft` or `picks`) not start now? A job of the same family runs, or an agent job of the other
        family does: a prompt-box turn or a draft (kind `draft`) and the agent's choice of pictures (kind `picks`) run one at a time per project."""
        return self.busy(family) or self.busy("draft") or self.picks_agent_running or self.busy("title")      # titlestep: the title writer holds the agent too

    # -- agent
    def agent(self, role: str) -> dict:
        """{id, label, usable, reason} of the agent that would run `role` (bti.agents; the answer of the availability check is cached
        by the app for ten minutes, nothing is called here)."""
        if role in self._agents:
            return self._agents[role]
        try:
            res = AG.model_for_project(self.d, role)
            av = self._avail.get(res.model)
            if av is None:
                av = self._avail[res.model] = AG.model_availability(res.model)
            out = {"id": res.agent_id, "label": res.label, "usable": bool(av.get("available")), "reason": av.get("reason")}
        except Exception:       # noqa: BLE001
            log.warning("state: the agent of %s could not be resolved", role, exc_info=True)
            out = {"id": None, "label": None, "usable": False, "reason": "Chưa kiểm tra được agent này."}
        self._agents[role] = out
        return out

    def title_waits(self) -> bool:
        """titlestep: does the storyboard draft wait for the video's title? The narration is approved, no title stands (or it is stale, or only the storyboard carries one) and an agent could
        write it now."""
        return bool(self.narration_ok and self.title_state in ("none", "stale") and not (self.title_state == "none" and self.sb_title) and self.agent("script.title")["usable"])

    def actor(self, role: str) -> str:
        """The `actor` of an example batch: `agent:<model id>` of the agent that works on this project for `role` (no availability check)."""
        try:
            return "agent:" + AG.model_for_project(self.d, role).model
        except Exception:       # noqa: BLE001
            return "cli:state"

    def problem(self, code: str, step: str | None, detail: str, fix: str | None = None, vi: str | None = None) -> None:
        """Record something wrong with the project's data: `detail` English (for the agent), `vi` the Vietnamese line the step shows."""
        h = hints_mod.hint(code, 409, self.pid)
        self.problems.append({"code": code, "step": step, "detail": detail, "fix": fix or h["fix"], "vi": vi})


def _load_script(c: Ctx) -> None:
    try:
        n, o = sstore.load_narration(c.d), sstore.load_outline(c.d)
    except Exception as e:      # noqa: BLE001 - DocumentCorrupt or an unreadable file
        c.script_error = str(e)[:200]
        c.problem("document_corrupt", "script", c.script_error, vi="Tệp kịch bản không đọc được.")
        return
    c.outline, c.narration = o, n
    c.outline_rev = o.rev() if o is not None else None
    c.outline_fresh = bool(o is not None and o.approved_fresh())
    c.narration_rev = n.rev() if n is not None else None
    c.narration_ok = bool(sstore.narration_approval(n, o)["approved"])
    c.locked_beats = bool(n is not None and any(b.locked for ch in n.chapters for b in ch.beats))


def _load_title(c: Ctx) -> None:
    """titlestep: the state and the revision of title.json (a file that cannot be read counts as no title; the next `title.set` or generation replaces it)."""
    from bti.title import store as tstore
    doc, problem = tstore.read(c.d)
    c.title_rev = tstore.revision(doc)
    c.title_state = tstore.state_of(doc, c.narration_rev)
    if problem:
        c.problem("document_corrupt", "script", "title.json cannot be read: " + problem[:160], fix="Set the title again with title.set (it writes a new file), or write it with title.generate.",
                  vi="Tệp tựa video không đọc được: hãy đặt lại tựa để ghi tệp mới.")


def _load_picks(c: Ctx) -> None:
    from bti.picks import context, doc
    try:
        pd, nv = doc.load(c.d), context.narration_view(c.d)
    except Exception as e:      # noqa: BLE001
        c.picks_error = str(e)[:200]
        c.problem("document_corrupt", "picks", "picks.json or the narration cannot be read: " + c.picks_error,
                  vi="Tệp chọn hình hoặc lời dẫn không đọc được.")
        return
    c.picks, c.narration_present = pd, bool(nv["present"])
    c.picks_rev = doc.revision(pd) if pd is not None else None
    c.picks_ops_rev = doc.revision(pd if pd is not None else doc.empty())         # what the operations call the revision of a project with no picks yet
    c.picks_main = bool(pd and pd.get("main_asset") and pd["main_asset"] in pd["assets"])
    c.picks_ok = bool(doc.approval_state(pd, nv["rev"], nv["approved"])["approved"])
    beats = (pd or {}).get("beats") or {}
    c.picks_lines = (len(nv["beat_ids"]), sum(1 for b in nv["beat_ids"] if (beats.get(b) or {}).get("items") or (beats.get(b) or {}).get("status") == "skip"))     # c3picks
    c.narration_ok = c.narration_ok or bool(nv["approved"])
    if pd is not None:
        c.picks_issues = [i for i in doc.blocking(doc.issues(pd, c.d, nv["beat_ids"] if nv["present"] else None)) if i.get("code") != "no_main"]
        c.non_tight_regions = doc.non_tight_regions(pd)
        from bti.picks.auto import retry                                                # fixes4
        f = retry.facts(c.d, pd)
        c.retry_lines, c.retry_files, c.retry_untried = f["lines"], f["files"], f["untried"]


def _has_history_copy(d: Path) -> bool:
    """Whether history/ holds a storyboard that restore can bring back (the rule of app.py::newest_valid_history)."""
    h = d / "history"
    if not h.is_dir() or h.is_symlink():
        return False
    for f in sorted((f for f in h.glob("*.json") if f.is_file() and not f.is_symlink()), key=lambda f: (f.stat().st_mtime_ns, f.name), reverse=True):
        try:
            if isinstance(read_json(f), dict):
                return True
        except (OSError, ValueError, RecursionError):
            continue
    return False


def _file_named(d: Path, sb: dict, key: str, default: str) -> bool:
    rel = sb.get(key)
    try:
        return safe_join(d, rel if isinstance(rel, str) and rel else default).is_file()
    except ApiError:
        return False


def storyboard_old_narration(d: Path, sb: dict) -> bool:
    """Detect obsolete beat references, or an older draft's narration snapshot."""
    from bti.picks.context import narration_view
    ids = set(narration_view(d)["beat_ids"])
    if not ids:
        return False
    beats = [s.get("beat") for s in sb.get("shots", []) if isinstance(s, dict) and isinstance(s.get("beat"), str) and s.get("beat")]
    if beats:
        return sum(b not in ids for b in beats) * 2 > len(beats)
    # Compiled shots have word anchors, not beat ids. A saved draft records the
    # narration hash; use it only when picks were approved after the storyboard.
    from datetime import datetime
    from bti.draft.inputs import canon_hash
    picks = read_json(d / "picks.json")
    approved_at = (picks.get("approval") or {}).get("approved_at")
    if not approved_at or datetime.fromisoformat(approved_at.replace("Z", "+00:00")).timestamp() <= (d / "storyboard.json").stat().st_mtime:
        return False
    current = canon_hash(read_json(d / "script" / "narration.json"))
    sb_time = (d / "storyboard.json").stat().st_mtime
    proposals = sorted((p for p in (d / "proposals").glob("draft_*.json") if p.stat().st_mtime <= sb_time), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in proposals:
        old_hash = (read_json(path).get("made_from") or {}).get("narration")
        if old_hash:
            return old_hash != current
    return False


def _load_storyboard(c: Ctx) -> None:
    f = c.d / "storyboard.json"
    c.sb_exists = f.is_file()
    if not c.sb_exists:
        return
    try:
        sb = read_json(f)
        problem = storyboard_shape_problem(sb)
    except (OSError, ValueError, RecursionError) as e:
        sb, problem = None, "it is not valid JSON" + (" (line %d, column %d)" % (e.lineno, e.colno) if hasattr(e, "lineno") else "")
    if problem:
        c.sb_corrupt = True
        c.has_history = _has_history_copy(c.d)
        c.problem("storyboard_corrupt", "edit", "storyboard.json is corrupt: " + problem
                  + ("; a good copy is in history/" if c.has_history else "; there is no good copy in history/"),
                  fix=hints_mod.hint("storyboard_corrupt", 409, c.pid)["fix"] if c.has_history else hints_mod.hint("no_history_copy", 404, c.pid)["fix"],
                  vi="Storyboard không đọc được.")
        return
    c.sb_old_narration = not c.imported and _try(lambda: storyboard_old_narration(c.d, sb), False)
    c.sb_rev, c.sb_approval = compute_rev(sb), storyboard_approval(sb)
    if c.sb_old_narration:
        c.sb_approval = "stale"
    ident = sb.get("identity") if isinstance(sb.get("identity"), dict) else {}      # titlestep
    c.sb_title = ident["video_title"].strip() or None if isinstance(ident.get("video_title"), str) else None
    c.sb_record = (sb.get("approvals") or {}).get("storyboard") if isinstance(sb.get("approvals"), dict) else None      # c5cli
    c.has_audio = _file_named(c.d, sb, "audio", "audio/mix.m4a")
    c.has_timing = _file_named(c.d, sb, "timing", "timing.json")
    from bti.draft import retime
    c.sb_off = _try(lambda: retime.project_off_voice(c.d, sb), [])          # introflow
    if not c.has_timing:
        c.problem("timing_unusable", "voice", "the timing file the storyboard names is missing",
                  vi="Thiếu tệp thời gian (timing.json): cần làm lại giọng đọc.")


# ---- c5cli: automatic running and who approved
def _load_auto(c: Ctx) -> None:
    c.auto, _ = auto_mod.read_project(c.d)


def _auto_ok(spec: Spec, c: Ctx) -> bool:
    """May an AGENT make this call now: a gate needs automatic running on and the gate allowed; a call that costs needs its kind of spending
    allowed (`paid` never); every other call is free for an agent. A spec that says `auto_ok` false never is."""
    if not spec.auto_ok:
        return False
    if spec.gate:
        return auto_mod.gate_allowed(c.auto, spec.id.split(".")[0])
    if spec.id == "auto.run":                          # c6auto: the run spends only what the owner allowed, and only while the switch is on
        return c.auto.get("enabled") is True
    if spec.cost:
        return auto_mod.spend_allowed(c.auto, spec.cost[0])
    return True


def _stamp(record: Any, stands: bool) -> dict | None:
    """{by, at, stands} of one approval record (None when nothing was approved); `by` is null for an approval made before it was recorded."""
    if not isinstance(record, dict) or not (record.get("approved") is True or record.get("approved_at")):
        return None
    by = record.get("by")
    return {"by": by if isinstance(by, str) and by else None, "at": record.get("approved_at"), "stands": bool(stands)}


def approvals_of(c: Ctx) -> dict:
    """The four gates: who approved, when, and whether the approval still stands (None for a gate never approved or not there)."""
    out: dict = {g: None for g in auto_mod.GATES}
    if c.outline is not None:
        out["outline"] = _stamp(c.outline.approval, c.outline_fresh)
    if c.narration is not None:
        out["narration"] = _stamp(c.narration.approval, c.narration_ok)
    if c.picks is not None:
        out["picks"] = _stamp(c.picks.get("approval"), c.picks_ok)
    if isinstance(c.sb_record, dict):
        out["storyboard"] = _stamp({"approved": True, **c.sb_record}, c.sb_approval == "fresh")
    return out


def _load_changes(c: Ctx) -> None:
    """The change log (bti/ops/log.py): how many batches, and the newest one that can be undone now (the check `POST .../undo` makes first)."""
    from bti.ops import undo as U
    from bti.ops.log import LOG_DIR, ChangeLog, number
    from bti.picks import doc as pdoc
    if not (c.d / LOG_DIR).is_dir():
        return
    log = ChangeLog(c.d)
    recs = log.list(limit=30)
    c.change_count = len(recs)
    c.change_doc = recs[0].get("doc") if recs else None
    for r in recs:
        kind = r.get("doc")
        if r.get("undone_by") or not r.get("copies") or kind not in ("picks", "storyboard"):
            continue
        both = log.copies(r["batch"])
        if both is None:
            continue
        if kind == "picks":
            cur, rev = pdoc.load_or_new(c.d), c.picks_ops_rev
        elif c.sb_exists and not c.sb_corrupt:
            cur, rev = read_json(c.d / "storyboard.json"), c.sb_rev
        else:
            continue
        later = [x for x in log.records(kind) if number(x["batch"]) > number(r["batch"])]
        if not U.find_conflicts(kind, cur, both[0], both[1], later, whole=kind == "storyboard" and U.is_whole(r))[1]:
            c.undo_target = {"batch": r["batch"], "doc": kind, "rev": rev}
            return


def _load_agent_jobs(c: Ctx, longjobs: Any) -> None:
    """join2/tightbox: whether the agent's choice or tightening of pictures (a `picks` job with `meta.action` in `("auto", "tighten")`) runs: the one `picks` job that holds the agent; and whether an
    automatic run (kind `auto`) goes on."""
    c.run_going = any(j.get("kind") == "auto" for j in c.jobs)
    if longjobs is None:
        return
    for j in longjobs.for_project(c.pid, c.d, kind="picks"):
        if j.get("state") in ACTIVE_JOB and (j.get("meta") or {}).get("action") in ("auto", "tighten"):
            c.picks_agent_running = True
            return


def _load_draft(c: Ctx) -> None:
    from bti.draft import run as draft_run
    r = draft_run.readiness(c.d)
    c.draft_ready = {"voice": bool(r["voice"]["ok"]), "picks": bool(r["picks"]["ok"])}
    c.draft_state = draft_run.state(c.d)
    c.proposal = c.draft_state.get("proposal") if isinstance(c.draft_state.get("proposal"), str) else None
    if c.sb_old_narration and c.proposal:
        c.proposal_after_sb = _try(lambda: (c.d / "proposals" / (c.proposal + ".json")).stat().st_mtime_ns > (c.d / "storyboard.json").stat().st_mtime_ns, False)


def running_jobs(pid: str, d: Path, script_jobs, preview_jobs, longjobs) -> list[dict]:
    """The jobs of the project that are queued, waiting or running, from the three registries: {id, kind, state, progress, started,
    path (the GET that follows it), cancel (the POST that stops it, null for a preview)}."""
    out: list[dict] = []

    def row(j: dict, kind: str, path: str, cancel: str | None) -> None:
        out.append({"id": j.get("id"), "kind": kind, "state": j.get("state"), "progress": j.get("progress") or 0.0,
                    "started": _iso(j.get("created")), "path": path.replace("{job_id}", str(j.get("id"))),
                    "cancel": cancel.replace("{job_id}", str(j.get("id"))) if cancel else None})
    for j in _try(lambda: script_jobs.for_project(pid), []) if script_jobs is not None else []:
        if j.get("state") in ("queued", "running"):
            row(j, str(j.get("kind")), "/api/jobs/{job_id}", "/api/jobs/{job_id}/cancel")
    for j in _try(lambda: longjobs.for_project(pid, d), []) if longjobs is not None else []:
        if j.get("state") in ACTIVE_JOB:
            row(j, str(j.get("kind")), "/api/longjobs/{job_id}", "/api/longjobs/{job_id}/cancel")
    for j in _try(lambda: preview_jobs.active(pid), []) if preview_jobs is not None else []:
        row(j, "preview", "/api/jobs/{job_id}", None)
    out.sort(key=lambda r: r["started"] or "")
    return out


# ------------------------------------------------------------------------------------------------------------ the builders
def E(needs: list[str] | None = None, body: Any = None, **kw) -> dict:
    return {"needs": list(needs or []), "body": body, "advances": False, **kw}


def _model_needs(c: Ctx, role: str) -> list[str]:
    return [] if c.agent(role)["usable"] else ["agent_usable"]


def _script_open(c: Ctx) -> bool:
    return c.open("script") and not c.imported


def b_outline_generate(c: Ctx):
    if not _script_open(c):
        return None
    needs = (["documents_readable"] if c.script_error else []) + (["no_running_job"] if c.busy("script") else []) + _model_needs(c, "script.outline")
    return E(needs, {}, advances=c.outline is None)


def b_outline_import(c: Ctx):
    if not _script_open(c):
        return None
    return E(["documents_readable"] if c.script_error else [], fill=["text"], template={"text": None})


def b_outline_approve(c: Ctx):
    if not _script_open(c) or c.outline_fresh:
        return None
    needs = ["documents_readable"] if c.script_error else (["outline"] if c.outline is None else [])
    return E(needs, {"rev": c.outline_rev} if c.outline is not None else None, advances=True)


def b_narration_generate(c: Ctx):
    if not _script_open(c):
        return None
    needs = ["documents_readable"] if c.script_error else ([] if c.outline_fresh else ["outline_approved"])
    needs += (["no_running_job"] if c.busy("script") else []) + _model_needs(c, "script.narration")
    if c.locked_beats:
        needs.append("locked_beats")
    return E(needs, {"force": True} if c.locked_beats else {}, advances=c.narration is None and c.outline_fresh)


def b_narration_import(c: Ctx):
    if not _script_open(c):
        return None
    needs = ["documents_readable"] if c.script_error else (["outline"] if c.outline is None else [])
    return E(needs, fill=["text"], template={"text": None, "merge": False, "force": False})


def b_narration_ops(c: Ctx):
    if not _script_open(c):
        return None
    needs = ["documents_readable"] if c.script_error else (["narration"] if c.narration is None else [])
    return E(needs, fill=["ops"], template={"base_rev": c.narration_rev, "ops": None})


def b_narration_approve(c: Ctx):
    if not _script_open(c) or c.narration_ok:
        return None
    if c.script_error:
        needs = ["documents_readable"]
    else:
        needs = (["narration"] if c.narration is None else []) + ([] if c.outline_fresh else ["outline_approved"])
    return E(needs, {"rev": c.narration_rev} if c.narration is not None else None, advances=True)


def b_title_generate(c: Ctx):
    """titlestep: the agent writes the video's title from the approved narration. It advances while there is no title or the narration changed after it was written."""
    if not _script_open(c):
        return None
    needs = ["documents_readable"] if c.script_error else ([] if c.narration_ok else ["narration_approved"])
    if c.agent_busy("title"):
        needs.append("no_running_job")
    needs += _model_needs(c, "script.title")
    return E(list(dict.fromkeys(needs)), {"note": None, "actor": c.actor("script.title")}, advances=c.title_state in ("none", "stale") and not c.sb_exists)


def b_title_set(c: Ctx):
    """titlestep: a person or an operator sets the title (text, or the number of a candidate in a body of its own)."""
    if not _script_open(c):
        return None
    return E(["documents_readable"] if c.script_error else [], fill=["text"], template={"base_rev": c.title_rev, "text": None, "actor": "cli:title"})


def b_voice_generate(c: Ctx):
    if not c.open("voice") or c.imported:
        return None
    done = c.work("voice") == "done"
    needs = c.blocker_need("voice") + ([] if c.narration_ok else ["narration_approved"])
    needs = list(dict.fromkeys(needs)) + (["no_running_job"] if c.busy("voice") else [])
    repair = not c.has_timing and c.sb_exists and not c.sb_corrupt
    return E(needs, {"scope": "all" if done else "changed"}, advances=(c.work("voice") in ("none", "stale")) or repair, repair=repair)


def _picks_open(c: Ctx) -> bool:
    return c.open("picks") and not c.imported


def b_picks_search(c: Ctx):
    if not _picks_open(c):
        return None
    p = c.pipe.get("painting") or {}
    query = " ".join(str(x) for x in (p.get("title"), p.get("artist")) if x).strip()
    if query:
        return E(body={"query": query[:200], "kind": "image"})
    return E(fill=["query"], template={"query": None, "kind": "image"})


def b_picks_import(c: Ctx):
    return E(fill=["source", "source_id"], template={"source": None, "source_id": None, "as_main": False}) if _picks_open(c) else None


def b_picks_import_book_image(c: Ctx):
    return E(fill=["source_id"], template={"source_id": None, "as_main": False}) if _picks_open(c) else None


def b_picks_import_clip(c: Ctx):
    if not _picks_open(c):
        return None
    return E(["no_running_job"] if c.busy("picks") else [], fill=["url", "start", "end"],
             template={"url": None, "start": None, "end": None, "beat_id": None, "role": "video"})


def b_picks_suggest(c: Ctx):
    if not _picks_open(c):
        return None
    from bti.picks import suggest
    needs = [] if c.narration_ok else ["narration_approved"]
    if not _try(lambda: suggest.provider_info(c.picks_provider)["available"], False):
        needs.append("suggest_enabled")
    if c.busy("picks"):
        needs.append("no_running_job")
    return E(needs, fill=["beats", "confirm_paid"], template={"beats": None, "confirm_paid": None})


def b_picks_auto(c: Ctx):                                                   # c3picks
    if not _picks_open(c):
        return None
    needs = [] if c.narration_ok else ["narration_approved"]
    if c.picks_error:
        needs.append("documents_readable")
    elif not c.picks_main:
        needs.append("main_asset")
    if c.agent_busy("picks"):                                               # join2: not while a prompt-box turn or a draft runs either
        needs.append("no_running_job")
    needs += _model_needs(c, "picks")
    total, settled = c.picks_lines
    body = {"beats": None, "redo": bool(c.picks_ok or (total and settled == total)), "base_rev": c.picks_ops_rev, "actor": c.actor("picks")}       # every line settled or approved: only `redo` runs; join2: `actor` (a caller names itself: the automatic run, the command, the bench) as the operations take it
    return E(list(dict.fromkeys(needs)), body, advances=bool(not c.picks_ok and total and not settled))


def b_picks_retry_missing(c: Ctx):                                          # fixes4
    """Listed while a line says `import_limited`; ready when the saved files of the last run are there; advances for the lines it has not looked at yet."""
    if not _picks_open(c) or not c.retry_lines:
        return None
    needs = [] if c.narration_ok else ["narration_approved"]
    if c.picks_error:
        needs.append("documents_readable")
    elif not c.picks_main:
        needs.append("main_asset")
    if not c.retry_files:
        needs.append("picks_saved_files")
    if c.agent_busy("picks"):                                               # nor while the pictures agent, a prompt-box turn, a draft or the title writer works
        needs.append("no_running_job")
    return E(list(dict.fromkeys(needs)), {"beats": None, "actor": "cli:state"}, advances=bool(c.retry_untried))


def b_picks_tighten(c: Ctx):                                                # tightbox
    """Listed only while the main painting has non-tight regions; ready when a main asset and usable agent exist and no agent job runs."""
    if not _picks_open(c) or not c.non_tight_regions:
        return None
    needs: list[str] = []
    if c.picks_error:
        needs.append("documents_readable")
    elif not c.picks_main:
        needs.append("main_asset")
    if c.agent_busy("picks"):
        needs.append("no_running_job")
    needs += _model_needs(c, "picks")
    return E(list(dict.fromkeys(needs)), {"regions": None, "base_rev": c.picks_ops_rev, "actor": c.actor("picks")}, advances=False)


def b_picks_put(c: Ctx):
    if not _picks_open(c):
        return None
    return E(["documents_readable"] if c.picks_error else [], fill=["picks"], template={"picks": None, "base_rev": c.picks_rev})


def b_picks_approve(c: Ctx):
    if not _picks_open(c) or c.picks_ok:
        return None
    needs: list[str] = []
    if c.picks_error:
        needs.append("documents_readable")
    else:
        needs += c.blocker_need("picks")
        if not c.narration_ok:
            needs.append("narration_approved")
        if c.picks is None:
            needs.append("picks")
        elif not c.picks_main:
            needs.append("main_asset")
        if c.picks_issues:
            needs.append("picks_errors")
    return E(list(dict.fromkeys(needs)), {"rev": c.picks_rev} if c.picks is not None else None, advances=True)


def _example_batch(c: Ctx, doc: str, rev: str | None, role: str) -> tuple[dict, dict]:
    """(body, template) of an operations call. The body is a DRY RUN (it writes nothing) of the first operation's example in the
    operations registry (`GET /api/ops/schema` has every operation's own); the template is the real call with the operations left to
    the caller."""
    import copy
    from bti.ops import registry
    first = next(iter(registry.defs(doc).values()))
    actor = c.actor(role)
    return ({"base_rev": rev, "actor": actor, "dry_run": True, "ops": [copy.deepcopy(first.example)]},
            {"base_rev": rev, "actor": actor, "ops": None, "dry_run": False})


def b_picks_ops(c: Ctx):
    if not _picks_open(c):
        return None
    body, template = _example_batch(c, "picks", c.picks_ops_rev, "picks")
    return E(["documents_readable"] if c.picks_error else [], body, fill=["ops"], template=template)


def b_picks_edit(c: Ctx):
    """c2box: the prompt box of step 4. The edit job is of the draft family (one agent call at a time), its model is the role `picks`."""
    if not _picks_open(c):
        return None
    needs = (["documents_readable"] if c.picks_error else []) + (["no_running_job"] if c.box_busy() else []) + _model_needs(c, "picks")      # join2: not while the agent's choice of pictures or an automatic run goes on
    return E(needs, fill=["instruction", "scope"], template={"instruction": None, "scope": None, "base_rev": c.picks_ops_rev})


def _edit_open(c: Ctx) -> bool:
    return c.open("edit")


def b_draft_start(c: Ctx):
    if not _edit_open(c):
        return None
    needs = c.blocker_need("edit")
    if c.title_waits() and not c.sb_old_narration:                          # titlestep: the channel-name beat shows the video's title: wait for it while an agent can write it
        needs.append("title_done")
    if not c.draft_ready["voice"]:
        needs.append("voice_done")
    if not c.draft_ready["picks"]:
        needs.append("picks_approved")
    if c.agent_busy("draft"):                                               # join2: nor while the agent's choice of pictures runs
        needs.append("no_running_job")
    needs += _model_needs(c, "draft")
    st = c.draft_state.get("state")
    return E(list(dict.fromkeys(needs)), {"provider": "agy", "note": None}, advances=(not c.sb_exists and st in ("none", "stale")) or (c.sb_old_narration and (st in ("none", "stale") or (st == "done" and not c.proposal_after_sb))))      # note: optional, null = none


def b_proposal_apply(c: Ctx):
    if not _edit_open(c) or (c.sb_exists and not c.sb_old_narration) or c.proposal is None:
        return None
    return E(body={"accept": "all", **({"base_rev": c.sb_rev} if c.sb_old_narration else {})}, advances=c.draft_state.get("state") == "done" and (not c.sb_old_narration or c.proposal_after_sb), path_args={"prop_id": c.proposal})


def b_storyboard_restore(c: Ctx):
    if not (c.sb_exists and c.sb_corrupt):
        return None
    return E([] if c.has_history else ["history_copy"], {}, advances=True, repair=True)


def _sb_ok(c: Ctx) -> bool:
    return _edit_open(c) and c.sb_exists and not c.sb_corrupt


def b_storyboard_validate(c: Ctx):
    return E() if _sb_ok(c) else None


def b_storyboard_approve(c: Ctx):
    if not _sb_ok(c) or c.sb_approval == "fresh" or c.sb_old_narration:
        return None
    return E(["storyboard_fits_voice"] if c.sb_off else [], {"rev": c.sb_rev}, advances=True)


def b_storyboard_retime(c: Ctx):
    """introflow: listed while the storyboard does not fit the voice; ready when the voice is done; it advances when something of it can be moved (a problem
    that `retime` cannot repair, like a number of cards that differs from the number of chapters, only blocks the gate)."""
    if not _sb_ok(c) or not c.sb_off:
        return None
    needs = [] if c.draft_ready["voice"] else ["voice_done"]
    return E(needs, {"base_rev": c.sb_rev, "actor": "cli:retime"}, advances=not c.sb_old_narration and any(p.get("repair") for p in c.sb_off), problems=[p["code"] for p in c.sb_off][:12])


def b_storyboard_preview(c: Ctx):
    return E(body={"t0": 0.0, "t1": 3.0, "width": 640, "fps": 15}) if _sb_ok(c) else None


def b_storyboard_put(c: Ctx):
    return E(fill=["storyboard"], template={"storyboard": None, "base_rev": c.sb_rev}) if _sb_ok(c) else None


def b_storyboard_ops(c: Ctx):
    if not _sb_ok(c):
        return None
    body, template = _example_batch(c, "storyboard", c.sb_rev, "edit.fast")
    return E([], body, fill=["ops"], template=template)


def b_changes_list(c: Ctx):
    if not c.change_count or not (c.open("picks") or c.open("edit")):
        return None
    return E(step="picks" if c.change_doc == "picks" else "edit")


def b_changes_undo(c: Ctx):
    t = c.undo_target
    if t is None:
        return None
    role = "picks" if t["doc"] == "picks" else "edit.fast"
    return E([], {"base_rev": t["rev"], "actor": c.actor(role), "note": ""}, path_args={"batch": t["batch"]},
             step="picks" if t["doc"] == "picks" else "edit")


def b_draft_edit(c: Ctx):
    if not _sb_ok(c):
        return None
    needs = (["no_running_job"] if c.box_busy() else []) + _model_needs(c, "edit.fast")
    return E(needs, fill=["instruction", "scope"], template={"instruction": None, "scope": None, "base_rev": c.sb_rev, "mode": "auto"})


def b_identity_set(c: Ctx):
    return E(fill=["style"], template={"style": None, "base_rev": c.sb_rev}) if _sb_ok(c) else None


def b_export_start(c: Ctx):
    if not c.open("export"):
        return None
    needs = c.blocker_need("export")
    if c.sb_exists and not c.sb_corrupt and c.sb_approval != "fresh":
        needs.append("storyboard_approved")
    elif c.sb_off:                                   # introflow: an approved storyboard whose voice was made again since
        needs.append("storyboard_fits_voice")
    if not c.has_audio:
        needs.append("audio_mix")
    if not c.has_timing:
        needs.append("timing")
    if c.busy("export"):
        needs.append("no_running_job")
    return E(list(dict.fromkeys(needs)), None, advances=c.work("export") != "done")


# c6auto: the actions of a person's own content or choice that are never taken by the automatic run (so they are not part of its cost)
RUN_MANUAL = frozenset({"picks.import_clip", "picks.tighten", "draft.edit", "picks.edit"})


def cost_about(spec: Spec, c: Ctx | None = None) -> str:
    """What a cost line says: the spec's own words, and for `picks.auto` with the owner's switch for the web search ON, the paid searches it may make
    (`, up to 80 web searches (You.com)`). With the switch off the line is the spec's, so nothing paid is ever implied."""
    about = spec.cost[1]
    # ---- partexport: tell an agent when prior exported parts exist that a small edit only re-renders its changed parts
    if spec.id == "export.start" and c is not None:
        has_parts = False
        try:
            pdir = c.d / "cache" / "export" / "parts"
            has_parts = pdir.is_dir() and any(p.is_file() and ".partial" not in p.name for p in pdir.glob("part_*.mp4"))
        except OSError:
            has_parts = False
        if has_parts or c.work("export") in ("stale", "done"):
            return "only changed ~60 s parts (full export: about 25 minutes)"
    if spec.id == "picks.auto":
        from bti.picks import websettings
        from bti.picks.auto import webround
        try:
            on = websettings.for_run()
        except Exception:       # noqa: BLE001 - a damaged settings file never breaks the state answer
            on = {"on": False, "max": 0}
        if on["on"]:
            about += webround.cost_line(on["max"])
    return about


def run_cost(c: Ctx) -> dict | None:
    """The cost of `auto.run`: the sum of what it may start from where the project stands, and only of the kinds the owner allowed (`spend` of auto.json). Every
    long action with a cost that is not paid and not a person's own request (RUN_MANUAL) and whose step is not done yet counts: an action somebody adds later
    (an agent that chooses the pictures) is in the sum without a change here. None when the run may start nothing that costs."""
    left: dict[str, list[tuple[str, str]]] = {}
    for s in SPECS:
        if s.cost and s.cost[0] != "paid" and s.long_job and s.id not in RUN_MANUAL and not s.id.startswith("auto.") and c.page_state(s.step) != "done" and auto_mod.spend_allowed(c.auto, s.cost[0]):
            left.setdefault(s.cost[0], []).append((s.id.split(".")[0], cost_about(s)))
    if not left:
        return None
    about = "; ".join("%s: %s" % (k, ", ".join("%s (%s)" % x for x in v)) for k, v in left.items())
    return {"kind": "machine_time" if "machine_time" in left else "model", "about": about, "kinds": sorted(left)}


def b_auto_run(c: Ctx):
    """Listed while the switch is on (or a run goes on) and nothing is exported yet; ready unless a job of the project runs."""
    running = any(j.get("kind") == "auto" for j in c.jobs)
    if not (c.auto.get("enabled") is True or running) or c.page_state("export") == "done":
        return None
    busy = any(j.get("kind") != "preview" for j in c.jobs)
    return E(["no_running_job"] if busy else [], {"until": None, "max_steps": 40}, step=c.pipe.get("current") or "export", run_cost=run_cost(c))


def b_output_build(c: Ctx):
    """outfolder: refill the project's output folder. Listed when the app has one and the project is not a reference project; nothing to wait for."""
    if c.output_root is None or c.imported or c.pipe.get("protected"):
        return None
    return E([], {})


BUILDERS: dict[str, Callable[[Ctx], dict | None]] = {
    "outline.generate": b_outline_generate, "outline.import": b_outline_import, "outline.approve": b_outline_approve,
    "narration.generate": b_narration_generate, "narration.import": b_narration_import, "narration.ops": b_narration_ops,
    "narration.approve": b_narration_approve, "title.generate": b_title_generate, "title.set": b_title_set, "voice.generate": b_voice_generate,
    "picks.search": b_picks_search, "picks.import": b_picks_import, "picks.import_book_image": b_picks_import_book_image,
    "picks.import_clip": b_picks_import_clip, "picks.suggest": b_picks_suggest, "picks.put": b_picks_put,
    "picks.auto": b_picks_auto, "picks.retry_missing": b_picks_retry_missing, "picks.tighten": b_picks_tighten, "picks.edit": b_picks_edit, "picks.ops": b_picks_ops, "picks.approve": b_picks_approve,
    "draft.start": b_draft_start, "proposal.apply": b_proposal_apply, "storyboard.restore": b_storyboard_restore,
    "storyboard.validate": b_storyboard_validate, "storyboard.retime": b_storyboard_retime, "storyboard.approve": b_storyboard_approve, "storyboard.preview": b_storyboard_preview,
    "storyboard.put": b_storyboard_put, "storyboard.ops": b_storyboard_ops, "changes.list": b_changes_list, "changes.undo": b_changes_undo,
    "draft.edit": b_draft_edit, "identity.set": b_identity_set,
    "export.start": b_export_start, "auto.run": b_auto_run, "output.build": b_output_build,
}
CANCELS = set(CANCEL_ID.values())


def _label(spec: Spec, c: Ctx) -> str:
    if spec.id == "export.start" and c.work("export") == "done":
        return "Xuất lại video"
    if spec.id == "voice.generate" and c.work("voice") == "done":
        return "Đọc lại toàn bộ"
    return spec.label


def _action(spec: Spec, e: dict, c: Ctx, job: dict | None = None) -> dict:
    args = {"pid": c.pid, **(e.get("path_args") or {})}
    path = spec.path
    for k, v in args.items():
        path = path.replace("{%s}" % k, str(v))
    if job is not None:
        path = path.replace("{job_id}", str(job["id"]))
    needs = e["needs"]
    out = {"id": spec.id, "step": e.get("step") or spec.step, "label": _label(spec, c), "method": spec.method, "path": path, "body": e["body"],
           "ready": not needs, "needs": needs, "gate": spec.gate, "auto_ok": _auto_ok(spec, c), "long_job": spec.long_job,
           "uses_model": spec.role is not None, "agent": c.agent(spec.role) if spec.role else None,
           "cost": ({"kind": spec.cost[0], "about": cost_about(spec, c)} if spec.cost else None) if spec.id != "auto.run" else e.get("run_cost"),      # c6auto: the run's own cost
           "advances": bool(e["advances"]) and not needs and spec.id != "auto.run"}
    if spec.follow:
        out["follow"] = spec.follow
    if e.get("fill"):
        out["fill"], out["body_template"] = e["fill"], e.get("template")
    if job is not None:
        out["job_id"] = job["id"]
    return out


def build_actions(c: Ctx) -> list[dict]:
    """Every action that can be called now (or is gated ahead), in the order of the catalogue, then sorted: the repair of a damaged
    project first, then what moves the project forward, then the other ready calls, then the ones that are gated."""
    rows: list[tuple[dict, bool]] = []
    for spec in SPECS:
        if spec.id in CANCELS:
            continue
        e = _try(lambda: BUILDERS[spec.id](c))
        if e is not None:
            rows.append((_action(spec, e, c), bool(e.get("repair"))))
    for j in c.jobs:                                              # one cancel per running job that can be cancelled
        sid = CANCEL_ID.get(j["kind"])
        if sid and j.get("cancel"):
            spec = SPEC[sid]
            rows.append((_action(spec, E(), c, job=j), False))
    pos = {s["id"]: i for i, s in enumerate(c.pipe.get("steps", []))}

    def key(item):
        a, repair = item
        tier = 0 if repair else 1 if a["advances"] else 2 if a["ready"] else 3
        return (tier, pos.get(a["step"], 99))
    rows.sort(key=key)                                             # stable: the catalogue order is kept inside a tier
    return [a for a, _ in rows]


# ------------------------------------------------------------------------------------------------------------------ the answer
def _steps_out(pipe: dict) -> list[dict]:
    out = []
    for s in pipe.get("steps", []):
        out.append({"step": s["id"], "label": s.get("label"), "state": STATE_OF.get(s["state"], "locked"), "page_state": s["state"],
                    "detail": s.get("reason") or s.get("detail") or "", "blocked_by": s.get("blocked_by"), "problem": None})
    return out


def damaged_answer(pid: str, why: str, code: str, fix: str | None = None) -> dict:
    """The answer for a project whose own file cannot be read at all: every step locked, the problem named, no action."""
    steps = [{"step": sid, "label": label, "state": "locked", "page_state": "locked", "detail": "Tệp dự án (project.json) bị hỏng.",
              "blocked_by": None, "problem": code} for sid, label in pipeline_api.STEPS]
    h = hints_mod.hint(code, 409, pid)
    return {"project": pid, "stage": None, "current": None, "steps": steps, "next_actions": [], "jobs": [],
            "problems": [{"code": code, "step": None, "detail": why, "fix": fix or h["fix"]}],
            "auto": auto_mod.public(auto_mod.default_doc()), "approvals": {g: None for g in auto_mod.GATES}}      # c5cli


def build_state(root: Path, pid: str, *, script_jobs=None, preview_jobs=None, longjobs=None, picks_provider: Any = None, output_root: Any = None) -> dict:
    """The whole answer of GET /api/projects/{pid}/state."""
    d = root / pid
    try:
        pipe = pipeline_api.compute(root, pid)
    except Exception as e:      # noqa: BLE001 - a damaged project still answers
        if type(e).__name__ != "DocumentCorrupt":
            log.warning("state: the pipeline of %s could not be computed", pid, exc_info=True)
        return damaged_answer(pid, str(e)[:300], "project_file_damaged" if "project.json" in str(e) else "document_corrupt")
    jobs = running_jobs(pid, d, script_jobs, preview_jobs, longjobs)
    c = Ctx(root, pid, pipe, jobs, picks_provider)
    c.output_root = output_root                                      # outfolder
    if not c.imported:
        _try(lambda: _load_script(c))
        _try(lambda: _load_title(c))                                 # titlestep
        _try(lambda: _load_picks(c))
    _try(lambda: _load_storyboard(c))
    _try(lambda: _load_changes(c))
    _try(lambda: _load_draft(c))
    _try(lambda: _load_auto(c))                                      # c5cli
    _try(lambda: _load_agent_jobs(c, longjobs))                      # join2
    if c.sb_old_narration:
        edit = c.steps.get("edit")
        if edit:
            if edit["state"] == "done":
                edit["state"] = "current"
            edit["detail"] = "Storyboard được dựng cho lời dẫn cũ. Cần dựng bản nháp mới."
        export = c.steps.get("export")
        if export and export["state"] in ("done", "current", "available"):
            export.update(state="waiting", blocked_by="edit")
    steps = _steps_out(pipe)
    for p in c.problems:                                            # a step that carries a problem says so on its line
        s = next((x for x in steps if x["step"] == p.get("step")), None)
        if s is not None:
            s["problem"] = s["problem"] or p["code"]
            if p.get("vi") and p["vi"] not in s["detail"]:
                s["detail"] = (s["detail"] + " " + p["vi"]).strip()
    problems = [{k: v for k, v in p.items() if k != "vi"} for p in c.problems]
    answer = {"project": pid, "stage": pipe.get("stage"), "current": pipe.get("current"), "steps": steps,
              "next_actions": build_actions(c), "jobs": jobs, "problems": problems,
              "auto": auto_mod.public(c.auto), "approvals": _try(lambda: approvals_of(c), {g: None for g in auto_mod.GATES})}      # c5cli
    if not c.imported:                                               # titlestep: the video's title (state none | done | stale, the text, who chose it, how many candidates)
        from bti.title import view as title_view
        answer["title"] = title_view.summary(d)
    if output_root is not None:                                      # outfolder: a problem with the output folder is a warning with its sentence (the key is there only then)
        from bti.output import hooks as output_hooks
        w = _try(lambda: output_hooks.warnings_for(output_root, d), [])
        if w:
            answer["warnings"] = w
    if not c.imported and c.title_state == "none" and c.sb_exists and not c.sb_corrupt and not c.sb_title:      # titlestep: a storyboard with no video title: the channel-name beat falls back to the painting's title
        answer["warnings"] = [*answer.get("warnings", []), {
            "code": "title_missing", "detail": "The project has no video title: the channel-name beat shows the painting's title. Write one with title.generate or set one with title.set.",
            "sentence": "Dự án chưa có tựa video nên đoạn tên kênh đang hiện tên bức tranh. Nhờ agent viết tựa hoặc tự đặt tựa ở bước Kịch bản."}]
    return answer


def make_router(projects_root: Path, *, pdir: Callable[[str], Path], script_jobs=None, preview_jobs=None, longjobs=None) -> APIRouter:
    """`pdir(pid)` is the app's own helper (404 for an unknown project); the registries are the app's, like pipeline_api's."""
    r = APIRouter(prefix="/api", tags=["state"])
    root = Path(projects_root)

    @r.get("/projects/{pid}/state")
    def get_state(pid: str, request: Request):
        pdir(pid)
        mgr = getattr(request.app.state, "longjob_manager", None) or longjobs
        return build_state(root, pid, script_jobs=script_jobs, preview_jobs=preview_jobs, longjobs=mgr,
                           picks_provider=getattr(request.app.state, "picks_provider", None), output_root=getattr(request.app.state, "output_root", None))

    return r


# --------------------------------------------------------------------------------------------------------- generated document
def _route_cell(s: Spec) -> str:
    return "`%s %s`" % (s.method, s.path)


def actions_table() -> str:
    """The table of every action id of docs/AGENT_API.md (markdown), from SPECS."""
    rows = ["| id | step | route | gate | long job | model | cost | when it is listed, and when it is ready |", "|---|---|---|---|---|---|---|---|"]
    for s in SPECS:
        cost = "%s: %s" % s.cost if s.cost else ""
        rows.append("| `%s` | %s | %s | %s | %s | %s | %s | %s |" % (
            s.id, s.step, _route_cell(s), "yes" if s.gate else "", "yes" if s.long_job else "", s.role or "",
            cost + ("" if s.auto_ok else " (auto_ok false)"), s.when.replace("|", "\\|")))
    return "\n".join(rows)


def needs_table() -> str:
    rows = ["| need | meaning | how to meet it |", "|---|---|---|"]
    for k, (meaning, how) in NEEDS.items():
        rows.append("| `%s` | %s | %s |" % (k, meaning, how.replace("|", "\\|")))
    return "\n".join(rows)
