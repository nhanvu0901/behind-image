# Fix Report: Identity Fit to Painted Surface, Full-Draft Title Propagation, and `strip_without_light`

Worker: `idfix` (worktree `wt/idfix`)

## Changes Made

### A. Keeping Identity-Written Shots Inside the Painted Surface
- **Shared helper (`bti/identity/apply.py`, `bti/identity/__init__.py`)**: Extracted `fit_camera_to_box(asset, keys, project_dir=None, *, box=None)` using `contentbox.box_of(asset, project_dir)` and `contentbox.fit_frame` / `outside_share` + `_clamp_zoom`, returning `(keys, [])` without mutation when no box exists or every key fits.
- **Identity & retime callers**: Added `project_dir=None` to `_Applier.__init__`, `apply_identity`, and `bti/draft/retime.py::retime`; `_Applier.box_of` / `in_box` now resolve `CB.box_of(a, self.project_dir)` and delegate to `fit_camera_to_box`. Threaded `project_dir` through `bti/draft/compile.py`, `bti/editor/identity_api.py`, `bti/editor/title_api.py` (covering both `title.set` and `title.apply.apply_to_storyboard` / `title.generate`), and `bti/editor/retime_api.py`. Replaced the duplicate loop in `bti/draft/compile.py::fit_to_box` with `ID.fit_camera_to_box`.
- **Tests**: Added unit checks in `tests/identity/test_panelbox_box.py` and end-to-end integration tests in `tests/editor/test_identity_fit.py` covering both a whole-file painting without stored `content_box` and a matte painting with stored `content_box` across `identity.set`, `title.set`, `tapply.apply_to_storyboard`, `storyboard.retime`, and full-draft compile (`0` `frame_off_painting` warnings).

### B. Preserving `identity.video_title` Across Full Draft Application
- **Root cause**: `bti/draft/compile.py` already wrote `chosen_text(project_dir)` into `proposed["identity"]["video_title"]` on full drafts while preserving `current["identity"]` in edit mode, but `bti/editor/proposals.py` (`shape_problem`, `diff`, `apply`) only diffed/applied `assets`, `shots`, `overlays`, and `end`, dropping `identity` whenever a proposal was applied onto an existing storyboard.
- **Fix & tests**: Updated `bti/editor/proposals.py` (`shape_problem`, `diff`, `apply`) to validate, diff, and apply `identity` (inserting right after `style` when absent from `doc`). Edit-mode drafts keep `current["identity"]`, so `diff` emits no `identity` change and preserves the existing storyboard title. Added unit and integration tests in `tests/editor/test_proposals.py` and `tests/title/test_title_storyboard.py` (person title set off-voice, agent title via `title.json`, subsequent `identity.set`, and edit mode). *(Note: `bti/editor/proposals.py` was edited outside the initial file list in the isolated worktree because `apply_proposal` directly drops `identity.video_title` without it.)*

### C. `strip_without_light` Viewer Check, Auto-Run Gate, Prompts, and UI
- **Check (`bti/engine/viewchecks.py`)**: Extracted shared `_shot_target` (used by `_region_framing` and `_strip_without_light`) and added `_strip_without_light`, `STRIP_FILL_SHARE = 0.60`, `HINTS["strip_without_light"]`, and `CODES["strip_without_light"]` (via `CODES.update`, keeping `CODES` literal intact). Warns on any main-painting non-structure shot with an `X-ANN-01` strip whose `params.text` is not a cast name/alias (`picks.json["names"]` `name` and `also`, token-sequence match) when no overlapping `HI-01`, `X-HI-01`, or `AN-01` appears in that shot during the strip.
- **Measurement when a region is larger than the frame & narrow-detail guard**: At the strip's midpoint `t_mid = 0.5 * (osp[0] + osp[1])`, `_strip_fill_at` intersects the region box `rbox` with the camera frame rectangle `(fx0, fy0, fx1, fy1)` (`iw = max(0, min(rbox[2], fx1) - max(rbox[0], fx0))`, and similarly `ih`), yielding `w_share = iw / vw` and `h_share = ih / vh` clipped to `[0.0, 1.0]`. A region larger than the frame clamps to `1.0` along the spanned axis, while an off-frame region clamps to `0.0`. The `> 0.60` exemption also requires `min(w_vis, h_vis) >= THIN_ON_SCREEN` (`0.20`, measured against the visible painted surface as in `is_small_on_screen`), so tall narrow details like `SETTLE_CUSHION` (`15.6% W x 60.8% H` at midpoint) are still flagged rather than falsely exempted.
- **Missing cast list finding & choice**: Evaluating stored Arnolfini storyboards lacking `picks["names"]` with `names=[]` flags unlit person strips in both: `19` warnings in `tests/engine/fixtures/catalogue/arnolfini` (including `s0120` `Giovanni Arnolfini`, `s0125` `Costanza Trenta?`, `s0148` `Saint Martha?`, `s0155` `Erwin Panofsky`, `s0087` `Saint Margaret`, `s0103` `Giovanni Arnolfini`) and `8` warnings in `tests/draft/fixtures/arnolfini_live` (including `s0008` `GIOVANNI ARNOLFINI`, `s0019` `COSTANZA TRENTA`, `s0078` `SAINT MARTHA AND BRUSH`). Accordingly, `_strip_without_light` skips checking when `picks.get("names")` is not a list (`0` warnings on stored legacy Arnolfini storyboards) and judges any project with an explicit `names` list (including `"names": []`).
- **Real-data check (`/Users/nhanvu/Documents/code/behind-the-image/.scratch/agy_tasks/namefirst/data/`)**: Verified `storyboard.json` (`150689` bytes) and `timing.json` (`131976` bytes) match `tests/engine/fixtures/namefirst/` byte-for-byte, and `picks.json` matches apart from omitting `names`. Results of `_strip_without_light`:
  - Without `picks["names"]` (`namefirst/data/picks.json` as-is): `0` warnings.
  - With the Arnolfini cast `names` (`tests/engine/fixtures/namefirst/picks.json`) and the coordinator's `o4` (`HI-01`) kept on `s0040`: `1` warning — `s0030` (`Tabard`, `TABARD_FUR`, `0.582 x 0.226`).
  - With `o4` removed from `s0040` (`"Settle"` alone): `2` warnings — `s0030` (`Tabard`, `TABARD_FUR`, `0.582 x 0.226`) and `s0040` (`Settle`, `SETTLE_CUSHION`, `0.156 x 0.608`), and `0` warnings on the lit shots (`s0045` `Anatolian rug`, `s0049` `Crown glass`, `s0074` `Pattens`).
- **Pipeline & UI integration**: Added `"strip_without_light"` to `bti/auto_run/checks.py::STOPS["storyboard"]`, `bti/draft/compile.py::summary_text` (`pointfix`), `skills/storyboard_draft/TASK.template.md` (`34946` chars), `style/gae/techniques.json` (`X-ANN-01.needs`), regenerated `docs/AGENT_API.md`, added Vietnamese sentence/label blocks in `bti/editor/static/js/errmsg.js` (`IDFIX_SENTENCES` / `IDFIX_CODES`) and `bti/editor/static/js/labels.js` (`CODE_IDFIX`), and added/updated tests in `tests/engine/test_strip_without_light.py`, `tests/auto/test_viewer_checks_bar.py`, `tests/editor_frontend/sbissues.test.mjs`, and `tests/editor_frontend/idfix.test.mjs`.

## Verification Summary Lines

Windows snapshot `idfix` (`tools/deploy/snapshot_test.sh idfix`):
- `tests/identity`: `============================= 104 passed in 3.52s =============================`
- `tests/title`: `======================= 198 passed, 1 warning in 42.62s =======================`
- `tests/draft`: `================= 550 passed, 1 warning in 162.89s (0:02:42) ==================`
- `tests/engine -m "not slow"`: `========= 798 passed, 14 skipped, 166 deselected in 353.78s (0:05:53) =========`
- `tests/editor`: `================= 533 passed, 1 warning in 240.52s (0:04:00) ==================`
- `tests/auto`: `================= 253 passed, 1 warning in 104.77s (0:01:44) ==================`
- `tests/state`: `================= 322 passed, 1 warning in 186.28s (0:03:06) ==================`
- `tests/ops`: `================= 542 passed, 1 warning in 130.30s (0:02:10) ==================`

Generator checks (`tools/deploy/snapshot_py.sh idfix`):
- `python -m bti.cli.docgen --check`: exit `0`
- `python -m bti.ops.doc --check`: exit `0`
- `python -m bti.editor.hints --check`: exit `0`

Mac Node tests (`node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`):
- `tests 499 / pass 498 / fail 0 / skipped 1`

## What Could Not Be Verified
- Running the live Windows server on port 8560 or executing real LLM draft/title/render/export jobs (per standing rules, only fake/fixture tests and snapshot verification ran).
- Slow engine tests (`166 deselected` under `tests/engine -m "not slow"`).
