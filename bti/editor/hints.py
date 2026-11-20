"""What to do about an error: ONE table `code -> {fix, retry}`, and the places that use it.

Every error body of the API carries, next to its `detail` (a sentence for a person, unchanged):
    code    a stable snake_case word
    fix     one English imperative sentence an agent can act on; it names the call to make when there is one
    retry   "no" (the same call can never work), "after_fix" (change the request or the project first) or "later" (the same
            call may work in a moment: something is busy or a service is not answering)
and, where they apply, `fields` (the request fields that are wrong: `[{path, problem, allowed?}]`, the form the operations use)
and `current_rev` (the revision to start from again).

`complete(body, status)` adds what is missing and never changes a key that is there (an error that carries its own `fix` keeps
it). `app.py` calls it in every exception handler; `ErrorHintMiddleware` is the net under the handlers: it completes the error
bodies that are not made by a handler (the long-job routes, the body-size and nesting limits).

`python -m bti.editor.hints` rewrites the generated parts of docs/AGENT_API.md; `--check` fails when they are stale.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from bti.ops.errors import ERRORS as OPS_ERRORS        # the operations' table: the one source of the codes they share with the rest of the API

RETRY = ("no", "after_fix", "later")
REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "AGENT_API.md"

# the codes whose body may carry `rev` meaning "the revision to start again from": `complete` copies it to `current_rev`
STALE_CODES = frozenset({"stale", "stale_revision"})

STALE_FIX = OPS_ERRORS["stale_revision"][2]          # `stale` (picks, agent, proposals) and `stale_revision` say the same sentence
BUSY_FIX = ("Wait until the running job is finished (GET /api/projects/{pid}/longjobs lists it) or cancel it, then call again.")
UPLOAD_FIX = "Send a file of a supported kind (jpg, jpeg, png, webp, mp4, webm, mov or m4v) of at most 80 MB."


def _t(retry: str, fix: str) -> dict:
    assert retry in RETRY, retry
    return {"retry": retry, "fix": fix}


# ----------------------------------------------------------------------------------------------------------------- the table
HINTS: dict[str, dict] = {
    # --- generic: the codes an error gets when nothing more specific is known (by status), and the shared ones
    "bad_request": _t("after_fix", "Read `detail`, correct the request and send it again."),
    "forbidden": _t("no", "This call is not allowed on this project; read `detail` for the rule."),
    "route_not_found": _t("no", "There is no such route: check the path and the method against docs/AGENT_API.md or GET /openapi.json."),
    "method_not_allowed": _t("no", "Use another HTTP method for this path (the Allow header of the answer lists them)."),
    "conflict": _t("after_fix", "Read `detail`: the project is in a state that refuses this call. GET /api/projects/{pid}/state shows what to do first."),
    "too_large": _t("after_fix", "Send a smaller JSON body (at most 8 MB)."),
    "too_deep": _t("after_fix", "Flatten the JSON body to at most 40 levels of nesting."),
    "unsupported_media": _t("after_fix", "Send a file this route can read, or leave the file out."),
    "range_not_satisfiable": _t("after_fix", "Ask for a byte range inside the file, or send no Range header."),
    "source_unavailable": _t("later", "The service this call needs is not answering; call again in a minute."),
    "source_timeout": _t("later", "The service did not answer in time; call again in a minute."),
    "internal_error": _t("no", "This is a bug of the server, not of your input: do not repeat the call; report `detail`."),
    "bad_text_character": _t("after_fix", "Remove lone surrogate characters from the text you send, then send it again."),

    # --- revisions
    "stale": _t("after_fix", STALE_FIX),

    # --- projects
    "project_busy": _t("later", "A save of this project is in progress: call again in a moment."),
    "project_file_damaged": _t("after_fix", "Repair or remove the damaged project.json by hand, then call again."),
    "project_protected": _t("no", "This project is protected: do not delete it."),
    "project_is_symlink": _t("no", "The project folder is a symbolic link: remove the link by hand; the API will not delete through it."),
    "invalid_project_path": _t("no", "Use a project id that names a folder directly under the projects folder."),
    "delete_not_confirmed": _t("after_fix", "Call DELETE /api/projects/{pid}?confirm={pid}: `confirm` must be the exact project id."),
    "longjob_running": _t("later", "Cancel the long job (POST /api/longjobs/{job_id}/cancel) or wait until it is finished, then call again."),
    "script_job_running": _t("later", "Cancel the model job (POST /api/jobs/{job_id}/cancel) or wait until it is finished, then call again."),
    "preview_running": _t("later", "Wait until the preview is finished (GET /api/jobs/{job_id}), then call again."),
    "storyboard_corrupt": _t("after_fix", "Call POST /api/projects/{pid}/storyboard/restore (no body) to bring back the newest good copy from history/, then call again."),
    "storyboard_unusable": _t("after_fix", "Repair storyboard.json: POST /api/projects/{pid}/storyboard/restore brings back the newest good copy from history/."),
    "timing_unusable": _t("after_fix", "Make the voice again with POST /api/projects/{pid}/voice/generate: timing.json is missing or damaged."),
    "style_unusable": _t("after_fix", "The style named by the storyboard is missing or damaged: set `style` in the storyboard to a style that exists under style/."),
    "data_unusable": _t("after_fix", "A data file of the project is missing or damaged: read `detail` for its name and repair it."),
    "library_data_corrupt": _t("after_fix", "A file of the book library is damaged: repair it or rebuild the library (python -m bti.library build), then call again."),
    "nothing_to_restore": _t("no", "Leave the storyboard as it is: storyboard.json is readable, there is nothing to restore."),
    "no_history_copy": _t("no", "There is no good copy in history/: the storyboard cannot be restored; make a new draft with POST /api/projects/{pid}/draft/start."),
    "history_file_not_found": _t("after_fix", "Name a file that exists in the project's history/ folder, or leave `file` out to use the newest good one."),
    "history_file_unreadable": _t("after_fix", "The named history file is not a storyboard: name another file, or leave `file` out."),
    "save_refused": _t("after_fix", "The engine refused the document: read `issues`, fix the values they name, then send it again."),
    "storyboard_has_errors": _t("after_fix", "Fix every issue with level `error` in `issues` (GET /api/projects/{pid} lists them), then call again."),
    "storyboard_incomplete": _t("after_fix", "Fill in the items named in the answer (their technique needs a picture, a clip or a mask), then approve again."),
    "undrawable": _t("after_fix", "Change the shots named in `issues` so the engine can draw them, then approve again."),
    "render_failed": _t("after_fix", "Change the values of the shot (and overlay, technique, asset) the answer names, save the storyboard, then render again."),
    "shot_not_found": _t("no", "Use a shot id that exists in the storyboard (GET /api/projects/{pid})."),
    "no_audio_file": _t("after_fix", "This project has no audio file yet: make the voice first (POST /api/projects/{pid}/voice/generate)."),
    "style_not_found": _t("no", "Use a style id that exists under style/ (the storyboard names it in `style`)."),
    "preview_too_long": _t("after_fix", "Ask for a shorter preview: t1 - t0 must stay within the limit in `detail`."),
    "preview_too_many_frames": _t("after_fix", "Ask for fewer frames: shorten the range (t1 - t0) or lower `fps`."),
    "job_not_found": _t("no", "Use the job id the start call answered with; after a server restart only finished jobs are still known."),
    "asset_not_found": _t("no", "Use an asset key that exists in the storyboard (GET /api/projects/{pid}/assets lists them)."),
    "licence_rejected": _t("after_fix", "The licence of this picture is not accepted: choose another picture."),
    "unsupported_file_type": _t("after_fix", UPLOAD_FIX),
    "file_too_large": _t("after_fix", UPLOAD_FIX),
    "video_unreadable": _t("after_fix", "The video cannot be read: send another file (mp4, webm, mov or m4v)."),
    "image_empty": _t("after_fix", "The image file is empty: send another file."),
    "image_truncated": _t("after_fix", "The image is cut off: send a complete file."),
    "image_unreadable": _t("after_fix", "The image cannot be read: send a jpg, png or webp that opens."),
    "thumbnail_failed": _t("no", "No thumbnail can be made of this file: use the file itself."),
    "proposal_not_found": _t("no", "Use a proposal id from GET /api/projects/{pid}/proposals."),
    "proposal_corrupt": _t("after_fix", "The proposal file was damaged and has been set aside: make a new proposal."),
    "proposal_malformed": _t("after_fix", "The proposal's storyboard has the wrong shape: make a new proposal (POST /api/projects/{pid}/draft/start)."),
    "proposal_has_errors": _t("after_fix", "The proposal's storyboard has errors (see `issues`): make a new proposal, or fix the values and save them with PUT /api/projects/{pid}/storyboard."),
    "accept_all_required": _t("after_fix", 'This project has no storyboard yet: call apply again with {"accept": "all"}.'),
    "unknown_change_ids": _t("after_fix", "Use change ids listed by GET /api/projects/{pid}/proposals/{id}, or send accept: \"all\"."),
    "accept_invalid": _t("after_fix", 'Send accept as "all" or as a list of change ids.'),

    # --- script step (outline and narration)
    "outline_missing": _t("after_fix", "Make the outline first: POST /api/projects/{pid}/outline/generate, then approve it."),
    "outline_not_approved": _t("after_fix", "Approve the outline: POST /api/projects/{pid}/outline/approve with {\"rev\": <outline rev>}."),
    "outline_stale": _t("after_fix", "The outline changed after it was approved: approve it again (POST /api/projects/{pid}/outline/approve)."),
    "no_outline": _t("after_fix", "There is no outline: make it with POST /api/projects/{pid}/outline/generate or /outline/import."),
    "no_narration": _t("after_fix", "There is no narration: write it with POST /api/projects/{pid}/narration/generate or /narration/import."),
    "outline_has_errors": _t("after_fix", "Fix the errors listed in `issues` (PUT /api/projects/{pid}/outline), then approve again."),
    "narration_has_errors": _t("after_fix", "Fix the errors listed in `issues` and `chapter_diff` (PUT /api/projects/{pid}/narration or POST .../narration/ops), then approve again."),
    "outline_unreadable": _t("after_fix", "The pasted outline could not be read (see `issues`): correct the text and import it again; nothing was overwritten."),
    "narration_unreadable": _t("after_fix", "The pasted narration could not be placed (see `issues`): correct the text and import it again; nothing was overwritten."),
    "document_invalid": _t("after_fix", "The document has the wrong shape (see `detail`): send a document as GET returns it."),
    "locked_beats": _t("after_fix", "Unlock the beats named in `locked`, or send {\"force\": true} to replace them."),
    "unknown_chapter": _t("after_fix", "Use chapter ids that exist in the outline (GET /api/projects/{pid}/outline)."),
    "op_invalid": _t("after_fix", "Correct the operation named in `detail` (GET the narration for the current beat and chapter ids), then send the ops again."),
    "prompt_error": _t("after_fix", "The prompt cannot be built from the current documents: read `detail`."),
    "model_required": _t("after_fix", "Name a model in `model` (GET /api/models lists them), or leave `model` out to use the project's agent."),
    "model_invalid": _t("after_fix", "Send `model` as a model id string, or leave it out to use the project's agent."),
    "unknown_model": _t("after_fix", "Use a model id listed by GET /api/models (or GET /api/settings/models)."),
    "model_unavailable": _t("after_fix", "The model cannot run on this machine (see `missing_env`): choose another model or agent."),
    "agent_unavailable": _t("after_fix", "The agent cannot run on this machine: choose another agent (PUT /api/projects/{pid}/agent, GET /api/agents lists them)."),
    "model_job_busy": _t("later", "Another model job is running for this project: wait for it (GET /api/jobs/{job_id}) or cancel it (POST /api/jobs/{job_id}/cancel), then call again."),
    "options_error": _t("after_fix", "Correct the option named in `detail` and send the options again."),
    "at_least_one_source": _t("after_fix", "Keep at least one book source included in the brief options."),

    # --- voice step
    "narration_missing": _t("after_fix", "There is no narration: write and approve it first (see GET /api/projects/{pid}/state)."),
    "narration_not_approved": _t("after_fix", "Approve the narration first: POST /api/projects/{pid}/narration/approve."),
    "nothing_to_say": _t("after_fix", "The narration has no sentence to speak: write it (POST /api/projects/{pid}/narration/generate)."),
    "voice_not_configured": _t("no", "This machine has no voice worker (or aligner) configured: the voice cannot be made here."),
    "voice_busy": _t("later", "A voice job is already running: wait for it (GET /api/projects/{pid}/longjobs) or cancel it, then call again."),
    "voice_worker_failed": _t("later", "The voice worker failed: call POST /api/projects/{pid}/voice/generate again, finished sentences are kept."),
    "voice_chunks_failed": _t("later", "Some sentences could not be spoken (see `sentences` or the job log): call POST /api/projects/{pid}/voice/generate again."),
    "voice_chunks_missing": _t("later", "A sentence has no audio: call POST /api/projects/{pid}/voice/generate again to read the missing ones."),
    "voice_assemble_failed": _t("later", "The mix could not be made: call POST /api/projects/{pid}/voice/generate again."),
    "voice_align_failed": _t("later", "The word timing could not be made: call POST /api/projects/{pid}/voice/generate again."),
    "no_voice": _t("after_fix", "There is no voice mix yet: make it with POST /api/projects/{pid}/voice/generate."),
    "no_chunk": _t("after_fix", "That sentence has no audio yet: make the voice with POST /api/projects/{pid}/voice/generate."),
    "longjob_missing": _t("no", "The long-job runner is not installed on this server: the job cannot be started."),
    "bad_scope": _t("after_fix", 'Send scope as "all", "changed" or a list of chunk ids (and reseed as a list of chunk ids).'),
    "bad_tempo": _t("after_fix", "Send `tempo` as a number inside the range in `detail`."),
    "bad_pad": _t("after_fix", "Send `pad` as true or false."),
    "bad_lead": _t("after_fix", "Send `lead` as a number of seconds from 0.2 to 15 (or null to use the standard one)."),
    "bad_title": _t("after_fix", "Send `title` as a number of seconds from 3 to 30 (or null to use the standard one)."),
    "bad_pronounce": _t("after_fix", "Send `pronounce` as an object of written form -> spoken form (at most 500 entries)."),
    "cancelled": _t("later", "The job was cancelled: start it again to continue; finished parts are kept."),

    # --- picks step
    "picks_error": _t("after_fix", "Read `detail`, correct the request or the picks, then call again."),
    "invalid": _t("after_fix", "Correct the request as `detail` says and send it again."),
    "query_required": _t("after_fix", "Send `query` (words to search for) or a `beat`."),
    "confirm_required": _t("after_fix", "This call is paid: send confirm_paid: true only when the owner agreed to the cost."),
    "youcom_key_missing": _t("no", "The You.com key is not set on this machine: use the free sources, or paste a YouTube link."),
    "video_bad_url": _t("after_fix", "Send a YouTube link (youtube.com or youtu.be) in `url`."),
    "video_bad_range": _t("after_fix", "Send `start` and `end` as numbers of seconds with a clip length inside the allowed range."),
    "video_fetch_failed": _t("later", "The video could not be fetched: call again in a minute, or use another link."),
    "video_timeout": _t("later", "The video download took too long: call again, or choose a shorter range."),
    "tool_missing": _t("no", "A tool the clip needs (yt-dlp or ffmpeg) is not installed on this machine."),
    "no_picks": _t("after_fix", "There are no picks yet: add the main painting (POST /api/projects/{pid}/picks/import with as_main) first."),
    "picks_have_errors": _t("after_fix", "Fix the errors listed in `issues` (the main painting, missing files, unknown assets or regions), then approve again."),
    "region_name": _t("after_fix", "Use a region name made of letters, digits, - and _ (see `region` for the bad one)."),
    "region_shape": _t("after_fix", "Give the region numeric x and y (and a short label): see `region` for the bad one."),
    "region_outside": _t("after_fix", "Keep the region inside the picture (x and y between 0 and 1): see `region`."),
    "busy": _t("later", "A job of this kind is already running for the project: wait for it (GET /api/projects/{pid}/longjobs) or cancel it, then call again."),
    "suggest_off": _t("no", "Suggestions are switched off in config/picks.json: search with POST /api/projects/{pid}/picks/search instead."),
    "suggest_no_key": _t("no", "The key for suggestions is not set on this machine: search with POST /api/projects/{pid}/picks/search instead."),
    "suggest_key_refused": _t("no", "The suggestion service refused the key: use POST /api/projects/{pid}/picks/search instead."),
    "suggest_quota": _t("later", "The suggestion service quota is used up: call again later, or use POST .../picks/search."),
    "suggest_timeout": _t("later", "The suggestion service did not answer in time: call again later."),
    "suggest_bad_answer": _t("later", "The suggestion service gave an unusable answer: call again later."),
    "suggest_failed": _t("later", "The suggestion service failed: call again later, or use POST .../picks/search."),
    "too_many": _t("after_fix", "Send fewer beat ids in `beats` (the limit is in `detail`)."),
    "real_models_off": _t("no", "Real model and paid calls are switched off on this machine (BTI_NO_REAL_MODELS): the owner must turn them on."),

    # --- picks step: the agent that chooses the pictures (POST /api/projects/{pid}/picks/auto, bti/picks/auto), c3picks
    "picks_approved": _t("after_fix", "The picks are approved: send redo true to let the agent choose again (the approval is dropped and the picks must be approved again)."),
    "picks_nothing_to_do": _t("no", "Every line already has pictures: send redo true to choose them again, or name the lines in `beats`."),
    "picks_auto_no_output": _t("later", "The agent wrote no usable file even after one repair message: call POST /api/projects/{pid}/picks/auto again, or choose the other agent."),
    "picks_auto_limit": _t("later", "The agent used up the limits of one session (time and steps): call POST /api/projects/{pid}/picks/auto again; the parts that finished are kept."),
    "picks_auto_tampered": _t("after_fix", "The agent changed files outside its work folder and its result was dropped: check the project, then call POST /api/projects/{pid}/picks/auto again."),
    "picks_auto_stale": _t("after_fix", "The narration or the main painting changed while the agent worked: call POST /api/projects/{pid}/picks/auto again."),
    # --- join2: the one agent run of a project (the pictures agent, a prompt-box turn and a draft run one at a time)
    "agent_job_running": _t("later", "Another agent job of this project is running (the agent's choice of pictures, a prompt-box turn or a draft): wait for it (GET /api/projects/{pid}/longjobs) or cancel it, then call again."),
    "turn_not_escalated": _t("after_fix", "That turn did not end as `escalate` (or an agent run of it that failed): only such a turn can be handed to the pictures agent; send POST /api/projects/{pid}/picks/auto with the lines instead."),

    # --- draft (storyboard) step
    "draft_not_ready": _t("after_fix", "Make the voice (timing.json) and approve the picks first: GET /api/projects/{pid}/state shows which is missing."),
    "timing_missing": _t("after_fix", "Make the voice first (POST /api/projects/{pid}/voice/generate): timing.json is missing."),
    "timing_corrupt": _t("after_fix", "Make the voice again (POST /api/projects/{pid}/voice/generate): timing.json cannot be read."),
    "timing_shape": _t("after_fix", "Make the voice again (POST /api/projects/{pid}/voice/generate): timing.json has the wrong shape (see `detail`)."),
    "picks_missing": _t("after_fix", "Choose the pictures first (see GET /api/projects/{pid}/picks): picks.json is missing."),
    "picks_corrupt": _t("after_fix", "Save the picks again (PUT /api/projects/{pid}/picks) or repair picks.json: it cannot be read."),
    "picks_shape": _t("after_fix", "Save the picks again (PUT /api/projects/{pid}/picks): picks.json has the wrong shape (see `detail`)."),
    "picks_no_main": _t("after_fix", "Choose the main painting (POST /api/projects/{pid}/picks/import with as_main), then approve the picks."),
    "storyboard_missing": _t("after_fix", "This project has no storyboard yet: run the draft first (POST /api/projects/{pid}/draft/start)."),
    "scope_needs_storyboard": _t("after_fix", "This needs an existing storyboard: apply the first draft proposal first (POST /api/projects/{pid}/proposals/{id}/apply)."),
    "edit_no_storyboard": _t("after_fix", "Editing needs an existing storyboard: apply the first draft proposal first."),
    "bad_provider": _t("after_fix", 'Send provider as "agy" or "auto".'),
    "bad_model": _t("after_fix", "Send `model` as a plain model id, or leave it out to use the project's agent."),
    "bad_chapters": _t("after_fix", "Send `chapters` as a list of chapter ids (at most 100)."),
    "draft_note_too_long": _t("after_fix", "Send `note` of at most 600 characters (the owner's wish for this draft), or leave it out."),      # fixdraft
    "draft_note_invalid": _t("after_fix", "Send `note` as text (the owner's wish for this draft), or leave it out."),                       # fixdraft
    "bad_action": _t("after_fix", 'Send action as "overwrite" or "discard".'),
    "agy_missing": _t("no", "The agy command is not installed on this machine: choose the other agent (PUT /api/projects/{pid}/agent) or use provider auto."),
    "agy_config": _t("no", "The agy on this machine cannot be used (too old or not running): choose the other agent or use provider auto."),
    "agy_busy": _t("later", "Another agent run is in progress: call again when it is finished."),
    "agy_auth": _t("after_fix", "Ask the owner to sign agy in once on the server, then call again."),
    "agy_rate_limit": _t("later", "The agy quota is used up: call again after `retry_after_seconds`, or choose the other agent (PUT /api/projects/{pid}/agent)."),
    "agy_model": _t("after_fix", "Choose another model or agent: agy does not know this model."),
    "agy_error": _t("later", "Call again, and if it repeats choose the other agent: agy reported an error."),
    "agy_no_result": _t("later", "Call again: agy stopped without an answer."),
    "agy_timeout": _t("later", "The agent ran past its time limit and was stopped: call again, or work on fewer chapters."),
    "claude_missing": _t("no", "Claude Code (the claude command) is not installed on the server: choose the other agent (PUT /api/projects/{pid}/agent)."),
    "claude_auth": _t("after_fix", "Claude Code is not signed in on the server: the owner must run `claude auth login` there, then call again."),
    "claude_config": _t("no", "Claude Code on this machine cannot be used (too old or not running): choose the other agent."),
    "claude_model": _t("after_fix", "Use a Claude Code model id of the form claude:<model>@<effort>, or choose an agent."),
    "claude_rate_limit": _t("later", "The Claude Code quota is used up: call again after `retry_after_seconds`, or choose the other agent."),
    "claude_error": _t("later", "Claude Code reported an error: call again; if it repeats choose the other agent."),
    "claude_no_result": _t("later", "Claude Code stopped without an answer: call again."),
    "claude_timeout": _t("later", "The agent ran past its time limit and was stopped: call again, or work on fewer chapters."),
    "draft_tampered": _t("after_fix", "The agent changed files outside its workspace and its result was dropped: check the project, then run the draft again."),
    "draft_no_output": _t("later", "The agent wrote no result file: run the draft again (POST /api/projects/{pid}/draft/start)."),
    "compile_empty": _t("later", "No shot could be built from the agent's result: run the draft again."),
    "compile_error": _t("after_fix", "The edit could not be assembled (parameter or syntax errors): send a simpler instruction or a narrower scope."),
    "edit_outside_scope": _t("after_fix", "The agent changed something outside the scope or a locked shot: narrow the instruction to the scope and call again."),
    "edit_no_change": _t("after_fix", "The agent changed nothing: restate the instruction more concretely."),
    "edit_degraded": _t("after_fix", "The edit was refused because a shot would be degraded or incomplete: narrow the instruction."),
    "edit_failed": _t("later", "The edit failed unexpectedly and nothing changed: call again."),
    "edit_bad_scope": _t("after_fix", "Send scope as exactly one of {\"shots\": [ids]} (step 5), {\"beats\": [ids]} (step 4), {\"chapter\": id} or {\"all\": true}, an instruction of 1 to 2000 characters and, for step 5, mode auto, fast or deep."),
    "edit_empty_instruction": _t("after_fix", "Send `instruction` as a non-empty text."),
    "edit_needs_agy": _t("after_fix", "Editing by instruction needs an agent (agy or Claude Code), not provider auto: choose an agent."),
    "spec_invalid": _t("later", "The model answered in the wrong shape, or with operations the server refused, even after one repair: call again with the request said more plainly."),
    "escalate": _t("after_fix", "This request needs a closer look at the picture, more than the chosen scope or a picture the project does not have: on step 5 call again with mode deep, on step 4 search for the picture by hand."),
    "cannot": _t("no", "The project lacks what this request needs (for example a new painting, or a change of narration or voice): do that step first."),
    "main_asset_unreadable": _t("after_fix", "The main painting has no readable file: import it again (POST /api/projects/{pid}/picks/import with as_main)."),
    "project_missing": _t("no", "The project folder is missing: use the id of a project that exists."),
    "template_missing": _t("no", "The draft task template is missing from this installation: restore skills/storyboard_draft/TASK.template.md."),
    "workspace_invalid": _t("after_fix", "The draft workspace is damaged: run the draft again."),
    "not_needs_choice": _t("no", "This turn is not waiting for a choice: GET /api/projects/{pid}/draft/thread shows its status."),
    "turn_data_lost": _t("after_fix", "The stored storyboards of this turn are gone: send the instruction again as a new edit."),
    "already_undone": _t("no", "This turn was already undone."),
    "turn_not_applied": _t("no", "Only an applied turn can be undone: GET /api/projects/{pid}/draft/thread shows its status."),
    "undo_unavailable": _t("no", "The earlier storyboard of this turn is no longer kept (only the last 20 turns are): edit the shots by hand instead."),
    "undo_conflict": _t("after_fix", "Some shots were changed since this turn (see `conflicts`): call undo again with {\"force\": true} to override them."),
    "turn_not_found": _t("no", "Use a turn id listed by GET /api/projects/{pid}/draft/thread."),
    "turn_frame_not_found": _t("no", "Use `when` before or after, and a turn and shot that exist (GET /api/projects/{pid}/draft/thread)."),
    "edit_running": _t("later", "An edit is running: cancel it (POST /api/longjobs/{job_id}/cancel) or wait, then delete the thread."),
    "identity_style_required": _t("after_fix", "Send `style` as an identity style id (GET /api/projects/{pid}/identity lists them)."),
    "identity_style_unknown": _t("after_fix", "Use one of the ids in `allowed` as `style`."),
    "video_title_invalid": _t("after_fix", "Send `video_title` as text: one line of at most 90 characters (\"\" takes the title away)."),
    "video_title_too_long": _t("after_fix", "Shorten `video_title` to one line of at most 90 characters."),
    "storyboard_off_voice": _t("after_fix", "The cards, the channel-name beat or the end of the video sit where an earlier voice put them (`problems` lists them): call the action storyboard.retime "
                                            "(POST /api/projects/{pid}/storyboard/retime with {\"base_rev\": <storyboard rev>}), then call this again."),

    # --- titlestep: the video's title (bti/title/)
    "title_invalid": _t("after_fix", "Send `text` as the title: text that is not empty (or `option`: the number, from 1, of a candidate of GET /api/projects/{pid}/title)."),
    "title_not_one_line": _t("after_fix", "Send `text` as one line: no line breaks."),
    "title_too_long": _t("after_fix", "Shorten `text` to at most 60 characters (GET /api/projects/{pid}/title `limits.person_max_chars`)."),
    "title_option_unknown": _t("after_fix", "Send `option` as the number, from 1, of a candidate listed by GET /api/projects/{pid}/title, or send `text` instead."),
    "title_choice_needed": _t("after_fix", "Send exactly one of `text` (a title) and `option` (the number of a candidate)."),
    "title_note_too_long": _t("after_fix", "Shorten `note` to at most 600 characters, or leave it out."),
    "title_note_invalid": _t("after_fix", "Send `note` as text, or leave it out."),
    "title_no_output": _t("later", "The agent wrote no usable title file even after one repair message: call POST /api/projects/{pid}/title/generate again, or choose the other agent."),
    "title_limit": _t("later", "The agent used up the limits of one run without a usable title: call POST /api/projects/{pid}/title/generate again."),
    "title_tampered": _t("after_fix", "The agent changed files outside its work folder and its answer was thrown away: check the project, then call POST /api/projects/{pid}/title/generate again."),

    # --- export step
    "no_storyboard": _t("after_fix", "There is no storyboard yet: run the draft and apply its proposal first."),
    "storyboard_unreadable": _t("after_fix", "Call POST /api/projects/{pid}/storyboard/restore to bring back the newest good copy: storyboard.json cannot be read."),
    "not_approved": _t("after_fix", "Approve the storyboard first: POST /api/projects/{pid}/approve with {\"rev\": <storyboard rev>}."),
    "approval_stale": _t("after_fix", "The storyboard changed after it was approved: approve it again (POST /api/projects/{pid}/approve), then export."),
    "no_audio": _t("after_fix", "The audio mix is missing: make the voice again (POST /api/projects/{pid}/voice/generate)."),
    "no_timing": _t("after_fix", "Make the voice again (POST /api/projects/{pid}/voice/generate): timing.json is missing or empty."),
    "part_missing": _t("later", "A rendered part is missing: call POST /api/projects/{pid}/export/start again; finished parts are kept."),
    "frames_mismatch": _t("after_fix", "The video has the wrong number of frames: call POST /api/projects/{pid}/export/start again; if it repeats, validate the storyboard."),
    "join_failed": _t("later", "The parts could not be joined: call POST /api/projects/{pid}/export/start again."),
    "mux_failed": _t("later", "Sound and chapters could not be added: call POST /api/projects/{pid}/export/start again."),
    "project_gone": _t("no", "The project was removed while the job ran."),
    "plan_failed": _t("after_fix", "The export could not be planned: GET /api/projects/{pid} shows the storyboard's issues; fix them first."),
    "export_file_not_found": _t("no", "Use a file name listed by GET /api/projects/{pid}/export (`files`)."),

    # --- agents and settings
    "unknown_agent": _t("after_fix", "Use one of the agent ids in `allowed` (GET /api/agents lists them)."),
    "unknown_step": _t("after_fix", "Use a step id that GET /api/projects/{pid}/agent lists under `effective`."),
    "invalid_payload": _t("after_fix", "Send the body in the shape of the route: read `detail`, correct it and send again."),
    "agentic_role_needs_agy": _t("after_fix", "Choose an agy or Claude Code model for this role (it works with files and tools)."),
    "invalid_model": _t("after_fix", "Send each role's model as a non-empty model id string."),
    "unknown_role": _t("after_fix", "Use only role names listed by GET /api/settings/models."),

    # --- files and pictures
    "audio_decode_failed": _t("after_fix", "The audio file cannot be decoded: make the voice again (POST /api/projects/{pid}/voice/generate); if it repeats the file is damaged."),
    "image_too_small": _t("after_fix", "Choose a larger picture: its short side is below the smallest size the app stores."),

    # --- other runners and sources
    "claude_outdated": _t("after_fix", "Run `claude update` on the server (the owner does this once), then call again."),
    "map_place_unknown": _t("after_fix", "Search for the place again (POST /api/projects/{pid}/picks/search with source osm) and import the result it gives."),

    # --- long jobs
    "longjob_not_found": _t("no", "Use the job id the start call answered with (GET /api/projects/{pid}/longjobs lists the jobs of a project)."),
    "longjob_bad_kind": _t("after_fix", "Use a job kind such as voice, draft, export or picks in `kind`, or leave it out."),
    "interrupted": _t("later", "The server restarted while the job ran: start the same job again; finished parts are kept."),

    # --- library
    "book_not_found": _t("no", "Use a book id listed by GET /api/library/books."),
    "book_not_catalogued": _t("after_fix", "Rebuild the library catalogue (python -m bti.library build), then call again."),
    "work_not_found": _t("no", "Use a work id (book/n) listed by GET /api/library/books/{book}/works."),
    "page_not_in_work": _t("no", "Ask for a page inside the page range of this work."),
    "image_not_in_work": _t("no", "Ask for an image listed by GET /api/library/works/{book}/{n}."),
    "image_extract_failed": _t("no", "This image cannot be extracted from the book: skip it."),
    "artwork_not_found": _t("no", "Use an artwork key listed by GET /api/library/artworks."),
    "dossier_not_found": _t("no", "This artwork has no dossier yet: rebuild the library (python -m bti.library build)."),
    "source_not_found": _t("no", "Use a source name listed in the artwork's dossier."),
    "source_text_missing": _t("after_fix", "The source text file is missing: rebuild the library (python -m bti.library build)."),
    "library_file_unreadable": _t("after_fix", "A file of the library cannot be read (see `detail`): repair it, then call again."),
    "merge_refused": _t("after_fix", "Read `detail`: choose two different artworks that can be merged."),
    "split_refused": _t("after_fix", "Read `detail`: choose a work that can be split off."),
    "project_create_refused": _t("after_fix", "Read `detail`: change the slug, the artwork or the work ids and call again."),
    "project_source_missing": _t("after_fix", "A source file of the artwork is missing: rebuild the library (python -m bti.library build)."),
    "page_not_found": _t("no", "Ask for a page that exists in the book."),
    "book_pdf_missing": _t("no", "The PDF of this book is missing from the server."),

    # --- c5cli: who may approve a gate and spend (bti/auto.py, bti/editor/auto_api.py)
    "gate_needs_human": _t("after_fix", "Ask the owner to approve this gate on the page, or to turn automatic running on for this project and allow the gate (the switch on the page, PUT /api/projects/{pid}/auto), then call again."),
    "auto_needs_human": _t("no", "Ask the owner to change automatic running on the page: an agent may only read it (GET /api/projects/{pid}/auto)."),
    "spend_needs_human": _t("no", "Ask the owner to start this paid call on the page: an agent never spends money, whatever the settings of automatic running."),
    # c6auto: the automatic run (bti/auto_run/)
    "auto_not_enabled": _t("after_fix", "Ask the owner to turn automatic running on for this project (the switch on the page, PUT /api/projects/{pid}/auto), then call again."),
    "auto_running": _t("later", "An automatic run of this project is going: follow it (GET /api/longjobs/{job_id}) or stop it (POST /api/longjobs/{job_id}/cancel), then call again."),
    "auto_run_not_found": _t("no", "Take a run id from GET /api/projects/{pid}/auto/runs."),
    # outfolder: the output folder (bti/output/)
    "output_disabled": _t("no", "This app was started without an output folder: ask the owner to set BTI_OUTPUT_ROOT or to start the app the usual way, then call again."),
    "output_not_applicable": _t("no", "A reference or imported project has no output folder: use a project made from the library."),
    "output_failed": _t("later", "The output folder could not be written (see `detail`): check that the disk has room and the folder is not open elsewhere, then call POST /api/projects/{pid}/output/build again."),
}


# One source for the codes the operations routes share with the rest of the API: their table (bti/ops/errors.py) wins, and an
# operations error carries exactly this sentence (it takes it from the same table), so the two cannot drift. tests/state checks it.
for _code, (_status, _retry, _fix, _meaning) in OPS_ERRORS.items():
    HINTS[_code] = _t(_retry, _fix)

# ------------------------------------------------------------------------------------------------- codes made by the handlers
def fallback_code(status: int) -> str:
    """The code of an error that carries none, by status (the raise sites outside this worker's files rely on it)."""
    return {400: "bad_request", 401: "forbidden", 403: "forbidden", 404: "not_found", 405: "method_not_allowed", 409: "conflict",
            410: "not_found", 413: "too_large", 415: "unsupported_media", 416: "range_not_satisfiable", 422: "invalid_field",
            500: "internal_error", 502: "source_error", 503: "source_unavailable", 504: "source_timeout"}.get(status, "bad_request" if status < 500 else "internal_error")


def data_error_code(what: str | None) -> str:
    """The code of a `DataError`: which project data is unusable."""
    return f"{what}_unusable" if what in ("storyboard", "timing", "style") else "data_unusable"


def default_hint(status: int) -> dict:
    """What an unknown code gets: by status."""
    if status in (502, 503, 504):
        return _t("later", "Call again in a minute; read `detail` if it repeats.")
    if status >= 500:
        return _t("no", "This is a bug of the server, not of your input: do not repeat the call; report `detail`.")
    if status == 404:
        return _t("no", "What the call names does not exist: check the ids and the path.")
    return _t("after_fix", "Read `detail`, change the request or the project as it says, then call again.")


# codes of the job records and of the stage packages that reach an agent through a job (`error_code`), not through an HTTP error
EXTRA_CODES = ("agy_busy", "agy_config", "claude_config", "voice_chunks_failed", "voice_chunks_missing", "frames_mismatch", "join_failed",
               "mux_failed", "part_missing", "render_failed", "project_gone", "interrupted")

_PID_PATH = re.compile(r"^/api/projects/([a-z0-9][a-z0-9_-]{0,63})(?:/|$)")
_FIELD = re.compile(r"^([A-Za-z_][\w.\[\]]*) (?:\((?:string|object|list|number)\) is required|is required|must |needs |is too long|out of range)")


def pid_of_path(path: str) -> str | None:
    m = _PID_PATH.match(path or "")
    return m.group(1) if m else None


def _fill(text: str, pid: str | None) -> str:
    return text.replace("{pid}", pid) if pid else text


def hint(code: str | None, status: int = 400, pid: str | None = None) -> dict:
    """`{fix, retry}` of `code` (a generic one by status for a code the table does not know), `{pid}` filled in when known."""
    h = HINTS.get(code or "") or default_hint(status)
    return {"fix": _fill(h["fix"], pid), "retry": h["retry"]}


def infer_field(detail: Any) -> str | None:
    """The request field a 422 sentence is about ("width must be an integer" -> "width"), None when the sentence names none."""
    m = _FIELD.match(detail) if isinstance(detail, str) else None
    return m.group(1) if m else None


def complete(body: dict, status: int, pid: str | None = None) -> dict:
    """The error body with `code`, `fix` and `retry` (and `fields`, `current_rev` where they apply). A key that is already there is
    never changed: an error that carries its own `fix` keeps it."""
    out = dict(body)
    code = out.get("code")
    if not isinstance(code, str) or not code:
        code = out["code"] = fallback_code(status)
    h = hint(code, status, pid)
    out.setdefault("fix", h["fix"])
    if out.get("retry") not in RETRY:
        out["retry"] = h["retry"]
    if code in STALE_CODES and isinstance(out.get("rev"), str):
        out.setdefault("current_rev", out["rev"])
    if "field" in out:                                  # a raise site names ONE field; the body says it the way the operations do
        path = out.pop("field")
        out.setdefault("fields", [{"path": str(path), "problem": str(out.get("detail", ""))[:200]}])
    elif status in (400, 422) and "fields" not in out:
        f = infer_field(out.get("detail"))
        if f:
            out["fields"] = [{"path": f, "problem": str(out.get("detail", ""))[:200]}]
    return out


def validation_fields(errors: list) -> list[dict]:
    """`fields` of a request-validation error: [{path, problem}], from the errors FastAPI lists."""
    out = []
    for e in errors or []:
        loc = e.get("loc") if isinstance(e, dict) else None
        path = ".".join(str(x) for x in loc) if isinstance(loc, (list, tuple)) else ""
        out.append({"path": path, "problem": str((e or {}).get("msg", "invalid value"))[:200]})
    return out


# ------------------------------------------------------------------------------------------------------ the net under the handlers
class ErrorHintMiddleware:
    """Pure ASGI middleware: a JSON error response (status 400 and up) that is not complete gets its `code`, `fix` and `retry`.
    The handlers of `app.py` already make complete bodies; this covers the answers they do not make (the long-job routes, the
    body-size and nesting limits). A body that is complete, or that is not a JSON object, passes through byte for byte."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        held: dict = {"start": None, "chunks": []}

        async def wrapped(message):
            if message["type"] == "http.response.start":
                ctype = next((v for k, v in message.get("headers", []) if k.lower() == b"content-type"), b"")
                if message["status"] >= 400 and b"json" in ctype.lower():
                    held["start"] = message
                    return
            elif message["type"] == "http.response.body" and held["start"] is not None:
                held["chunks"].append(message.get("body", b""))
                if message.get("more_body", False):
                    return
                start, raw = held["start"], b"".join(held["chunks"])
                held["start"] = None
                fixed = _patched(raw, start["status"], scope.get("path", ""))
                if fixed is not raw:
                    start = {**start, "headers": [(k, v) for k, v in start.get("headers", []) if k.lower() != b"content-length"]
                             + [(b"content-length", str(len(fixed)).encode())]}
                await send(start)
                await send({"type": "http.response.body", "body": fixed})
                return
            await send(message)
        await self.app(scope, receive, wrapped)


def _patched(raw: bytes, status: int, path: str) -> bytes:
    """`raw` itself (the same object) when nothing is added, else the completed body."""
    try:
        body = json.loads(raw)
    except ValueError:
        return raw
    if not isinstance(body, dict):
        return raw
    done = complete(body, status, pid_of_path(path))
    if done == body:
        return raw
    return json.dumps(done, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


# --------------------------------------------------------------------------------------------------------- the generated document
BEGIN = "<!-- BEGIN GENERATED: {name} -->"
END = "<!-- END GENERATED: {name} -->"


def codes_table() -> str:
    """The table of every code with its retry word and its fix sentence (markdown)."""
    rows = ["| code | retry | fix |", "|---|---|---|"]
    for code in sorted(HINTS):
        h = HINTS[code]
        rows.append("| `%s` | %s | %s |" % (code, h["retry"], h["fix"].replace("|", "\\|")))
    return "\n".join(rows)


def autorun_tables() -> str:
    """c6auto: the reasons an automatic run ends with, and the quality bar before each gate (markdown), from bti/auto_run/."""
    from bti.auto_run import checks, reasons
    rows = ["| reason | outcome | what it means | what to do |", "|---|---|---|---|"]
    for code, (outcome, _vi, en, fix) in reasons.REASONS.items():
        rows.append("| `%s` | %s | %s | %s |" % (code, outcome, en.replace("|", "\\|"), (fix or "").replace("|", "\\|")))
    rows += ["", "| gate | warning that stops the run | why | warnings it lets through |", "|---|---|---|---|"]
    for gate in reasons.GATES:
        stops = checks.STOPS[gate]
        share = checks.SHARE_LIMITS.get(gate, {})
        names = ["`%s`%s" % (c, (" (only when more than %d%% of the %shave it)" % (round(share[c] * 100), "lines about something outside the painting "
                                                                                   if checks.SHARE_OF.get(c) == "outside" else "lines ")) if c in share else "") for c in stops]
        rows.append("| `%s` | %s | %s | %s |" % (gate, ", ".join(names), "; ".join("%s: %s" % (c, w[0]) for c, w in stops.items()).replace("|", "\\|"),
                                              ", ".join("`%s`" % c for c in sorted(checks.TOLERATED[gate])) or "none"))
    return "\n".join(rows)


def generated_parts() -> dict[str, str]:
    """name -> markdown of every part of docs/AGENT_API.md that is generated from code."""
    from . import state_api
    return {"actions": state_api.actions_table(), "needs": state_api.needs_table(), "codes": codes_table(), "autorun": autorun_tables()}


def render_doc(text: str, parts: dict[str, str] | None = None) -> str:
    """`text` with the generated parts replaced between their markers (a marker that is missing is an error)."""
    parts = parts or generated_parts()
    for name, body in parts.items():
        b, e = BEGIN.format(name=name), END.format(name=name)
        i, j = text.find(b), text.find(e)
        if i < 0 or j < i:
            raise ValueError("docs/AGENT_API.md has no %s ... %s block" % (b, e))
        text = text[:i + len(b)] + "\n" + body + "\n" + text[j:]
    return text


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    text = DOC_PATH.read_text(encoding="utf-8")
    fresh = render_doc(text)
    if "--check" in argv:
        if fresh != text:
            print("docs/AGENT_API.md is stale: run `python -m bti.editor.hints`", file=sys.stderr)
            return 1
        return 0
    if "--print" in argv:
        sys.stdout.write(fresh)
        return 0
    if fresh != text:
        DOC_PATH.write_text(fresh, encoding="utf-8")
        print("docs/AGENT_API.md updated")
    else:
        print("docs/AGENT_API.md is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
