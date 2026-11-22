# Subjects in the storyboard draft

## What was built

- **Draft inputs & template (`bti/draft/workspace.py`, `skills/storyboard_draft/TASK.template.md`)**:
  - `_beats_doc` forwards `picks.subjects` and each beat's ordered `about` entries (`id`, `words`) into `inputs/beats.json`, keeping legacy `present` intact.
  - `TASK.template.md` instructs the draft model to read `subjects`/`about`, show a person as a face or figure before details, show the whole painting when named as a whole, and leave `about` strips/pointers (including `also` proper names, excluding `idea` and `text`, keeping illustrating `work` strips) to the compiler. All Arnolfini-specific examples were replaced with generic ones (`35,020` bytes, below `35,500`).
- **Compiler overlay generation (`bti/draft/compile.py`)**:
  - `_subject_overlays` strips model `X-ANN-01` captions matching subject names/`also` (and overlapping `idea`/`text` `about.words`) and model `HI-01`/`X-HI-01`/`AN-01` pointers on subject regions.
  - Across all beats overlapping each shot, it generates `X-ANN-01` (`name`/`also`, `sub`) once per unique `(subject_id, spoken_name)` at its first spoken occurrence while visible (ignoring shorter aliases nested inside a longer spoken name, skipping `idea`/`text`, clamping non-overlapping sequential durations, and honoring borrowed-picture end-of-shot strips).
  - It generates `HI-01` for a single small non-person region and `AN-01` circles when a sentence names multiple subject regions, continuing circles across mid-beat cuts to sentence-ending punctuation. On `LAY-01`/`X-CMP-01` panels, strips are generated when visible while pointers are withheld (see below). Legacy projects without `subjects` keep the previous behavior.
- **Visibility check & UI/pipeline integration (`bti/engine/viewchecks.py`, `bti/auto_run/checks.py`, `bti/editor/static/js/errmsg.js`, `labels.js`)**:
  - Shared `subject_visible_at` and `_subject_not_on_screen` verify that each spoken `about` subject (excluding `idea` and `text`) is visible at its spoken time: matching asset or >= 60% of its main-painting region inside the visible frame (>= 95% of `content_box`/image for whole-main `work` subjects), using renderer defaults when camera keys are omitted, and flagging a small `person` (< 15% of visible frame) when another subject fills > 50%. Supports `LAY-01` sliding-panel reveal clipping, `X-CMP-01` swap schedules, `LAY-04` inset delay, and `STATE-01` dissolves.
  - `subject_not_on_screen` is prioritized in `summary_text` (`pointfix`), listed in `STOPS["storyboard"]` and `tests/auto/test_viewer_checks_bar.py`, and given Vietnamese templates/labels in `errmsg.js` (`SUBJDRAFT_SENTENCES` / `SUBJDRAFT_CODES`, alongside `year_already_on_screen` and the updated `strip_without_light` without the obsolete 60% exemption) and `labels.js`. Updated `tests/editor_frontend/idfix.test.mjs`, `sbissues.test.mjs`, and added `subjdraft.test.mjs`.

## Checks evaluated for folding

- **Kept (`name_not_shown`, `small_detail_not_lit`, `strip_without_light`, `thing_arrives_late`, `year_already_on_screen`)**:
  - `name_not_shown` still covers legacy `picks.names` projects without `subjects`.
  - `small_detail_not_lit` and `strip_without_light` still catch unlit small details or unlit non-cast strips on legacy projects or post-compile/manual edits.
  - `thing_arrives_late` checks sustained visibility across a shot (`< 2.0 s` and `< 55%` of shot duration), which visibility at a single spoken word does not prove.
  - `year_already_on_screen` remains unchanged as required.

## Needs another worker

- `bti/engine/techniques/layout.py`: `LAY-01.view()` returns the left panel camera across the full 1920x1080 canvas rather than the panel bounds (and `X-CMP-01.view()` returns `None`), so `HI-01`/`AN-01` pointers via `View.to_screen` cannot align to panels until the renderer provides per-panel views.

## Verification summaries

- `tests/draft/test_subject_beats.py`: `33 passed in 5.16s`
- `tests/engine/test_subject_visibility.py`: `16 passed in 1.12s`
- `tests/draft`: `589 passed, 1 warning in 166.99s (0:02:46)`
- `tests/engine -m "not slow"`: `817 passed, 14 skipped, 166 deselected in 349.49s (0:05:49)`
- `tests/auto`: `256 passed, 1 warning in 88.53s (0:01:28)`
- `tests/editor`: `533 passed, 1 warning in 236.15s (0:03:56)`
- Mac Node (`node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`): `ℹ tests 500`, `ℹ pass 499`, `ℹ fail 0`, `ℹ skipped 1` (worktree has no `.venv/bin/python` for `sbissues.test.mjs`; running that exact check against the main repo `.venv/bin/python` output `ISSUE_CODES check passed: 163 codes`).
- `bti.cli.docgen --check` and `bti.editor.hints --check`: exit 0 with no output.
- `git diff --check`: clean.
