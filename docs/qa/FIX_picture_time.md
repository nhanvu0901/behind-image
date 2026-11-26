# FIX: Picture Time (`pictime`)

Report on the four deliverables implemented in worktree `pictime` (general for any painting).

## 1. Minimum Shot Length Raised from 1.5 s to 2.5 s

- **Shared threshold**: `MIN_SHOT_S = 2.5` in `bti/engine/viewchecks.py` is imported and reused everywhere instead of hard-coding separate numbers:
  - `bti/engine/viewchecks.py`: `MIN_SHOT_S = 2.5`; `_short_shots` checks `0.2 <= d < MIN_SHOT_S - 1e-6` (`shot_short`), using `HINTS["shot_short"]` and `CODES["shot_short"]`.
  - `bti/draft/compile.py`: imports `bti.engine.viewchecks as VC`, sets `PACE_SHORT_S, PACE_LONG_S = VC.MIN_SHOT_S, 30.0`, and enforces `VC.MIN_SHOT_S` in shot-merging/floor enforcement (while keeping `SB.MIN_SHOT_S = 0.2` for `shot_too_short`). Where the compiler removes an agent shot below the floor, borrowed pictures are kept in preference per deliverable 2.
  - `bti/draft/providers/auto.py`: imports `viewchecks as VC` and sets `MIN_BEAT_S = VC.MIN_SHOT_S`.
  - Style, briefings, evals, and tests: added `"min_shot_s": 2.5` under `"pacing"` in `style/gae/style.json`; updated `skills/storyboard_draft/TASK.template.md`, `skills/storyboard/SKILL.md`, `evals/cases/draft/draft-pace-seven-seconds.json`, `bti/auto_run/checks.py`, and test expectations (`tests/engine/test_viewchecks.py`, `tests/engine/test_catalogue_real.py`, `tests/draft/test_picture_time.py`).
- **How program / identity / opening shots are told apart from agent shots**:
  - `bti.engine.viewchecks.is_program_shot(shot, spec=None, style=None)` returns `True` when any of the following holds:
    1. `shot.get("id") == "s0000"` (the compiler's fixed opening-hold shot, `1.6 s`).
    2. `spec is not None and spec.get("kind") == "card"` (title card / chapter card).
    3. `shot.get("source") == "identity"` (channel-identity shots placed by identity rules).
    4. `shot.get("technique")` is recognized by `style`'s `read_identity(style).is_identity_technique(tid)` (or starts with `"ID-"` when `style` is unavailable).
  - `_short_shots` skips shots where `is_program_shot(...)` is `True`, so compiler-placed opening holds (`s0000`) and identity/card shots keep their own lengths without raising `shot_short`.

## 2. Borrowed Pictures and Maps Held at >= 3.0 s

- **Borrowed-shot classification**: `is_borrowed_shot(shot, main_asset, spec=None, style=None)` in `bti/engine/viewchecks.py` identifies non-program shots whose technique is `"MAP-01"` or whose primary slot asset differs from `main_asset`. Threshold constant: `OUTSIDE_MIN_SHOT_S = 3.0`.
- **Viewer checks (`bti/engine/viewchecks.py`)**:
  - `_outside_picture_brief` warns (`outside_picture_brief`) when any borrowed picture or `MAP-01` shot lasts `0.2 <= d < OUTSIDE_MIN_SHOT_S - 1e-6`.
  - `_outside_picture_dropped` warns (`outside_picture_dropped`) when a multi-picture line in `picks.json` (`OUTSIDE_ROLES + ("map",)`) shows at least one outside asset during the line but leaves another unshown.
  - Both codes have `HINTS` and `CODES` entries registered outside the fixed 9-key literal block (so frontend contract parsing in `tests/editor_frontend/fixdraft.test.mjs` stays intact); `docs/AGENT_API.md` was regenerated via `bti.editor.hints`.
- **Compiler timing & drop rule (`bti/draft/compile.py`)**:
  - `ensure_borrowed_duration(recs)` runs up to two stabilization passes:
    1. **Drop only on physical beat capacity shortage** (Phase 1): if a line holds `n >= 2` borrowed shots and `beat_dur < n * 3.0`, drop one borrowed shot at a time — choosing the one whose subject has the fewest spoken words (tie-broken by shorter duration) — and emit warning `outside_picture_dropped` (duplicate `outside_picture_dropped` from `eng.validate` is suppressed for `_dropped_beats`).
    2. **Borrow order** (Phase 2): for any remaining borrowed/`MAP-01` shot `< 3.0 s`, move its start back to the start of the sentence that names it, borrowing from the previous editable same-chapter shot while that shot keeps its own floor (`3.0 s` if borrowed, `2.5 s` otherwise); then borrow any remaining shortfall from the start of the next editable same-chapter shot (keeping its floor); then borrow any remaining slack from before. Chapter boundaries and non-editable (`locked`, `kept`, `verbatim`, card, opening) shots are never crossed.
    3. Any borrowed/`MAP-01` shot still under `3.0 s` afterward keeps the `outside_picture_brief` warning (not dropped).
- **Briefings, stopping bar, and Vietnamese UI**:
  - Updated `skills/storyboard_draft/TASK.template.md` Rule 19 & Section 7 list (length checked under the `< 35_500` char limit).
  - Added `outside_picture_brief` and `outside_picture_dropped` to `STOPS["storyboard"]` in `bti/auto_run/checks.py` and `STOPPING` in `tests/auto/test_viewer_checks_bar.py`.
  - Appended `pictime` Vietnamese warning sentences and labels blocks at the end of `bti/editor/static/js/errmsg.js` and `bti/editor/static/js/labels.js`.

## 3. One More Try When a Picture Search Finds Nothing

- **Where it lives**:
  - `bti/picks/auto/search.py`: `retry_query_for(want, tried)`, `_free_retry_sources(want, wider_period)`, inline retry inside `search_want` (when initial candidates are empty/`no_candidates`), and `retry_after_rejection(pdir, wants, state, choice, ...)` (when the chooser returns `null` / `agent_none` in `bti/picks/auto/job.py::run_choose`, launching at most one `choose_retry` session when new candidates are found).
  - `bti/picks/auto/write.py`, `bti/picks/doc.py`, `bti/ops/picks_ops.py`, `skills/picks_auto/CHOOSE.template.md`, `skills/picks_auto/PLAN.template.md`: record both wordings (`tried_queries` -> `missing[].queries`, capped at 4 strings and omitted when empty so existing revisions are unaffected). Preserves `no_thumbs` when initial search had candidates without thumbnails and the retry finds nothing.
- **How wording progresses**:
  1. Stage 1: plain thing without modifiers/dates (`_RETRY_DROP_WORDS`, `_RETRY_YEAR_RE`; for maps, city/first comma segment).
  2. Stage 2: wider period / later depiction (`_RETRY_BROAD_SUFFIXES` + `"depiction"`, `"historic"`).
- **What bounds the cost**:
  - Executed **at most once per want**, gated by `w["retried"] = True` (covering both empty initial search and `agent_none` rejection retry).
  - Queries **free sources only** (`_free_retry_sources` + `wikipedia`, and wider-period free photo sources only within `retry_after_rejection` / `_free_retry_sources`), respecting existing per-source limits (`WIKI_LIMIT`, `MORE_LIMIT`, `PER_WANT`) and cooldowns (`state["limited"]`).
  - **Never calls** paid `web` search (`web_ask`) or the paid `suggest` service.

## 4. Viewer Review Repairs Unseen or Brief Outside Pictures

- `bti/draft/review.py`:
  - Added `DRAFT_REPAIR_CODES = frozenset({"outside_on_painting", "outside_picture_brief", "outside_picture_dropped"})`.
  - Added `_draft_repair_issues` and `_index_draft_issues`, and extracted shared `_build_repair_batches` so `review_and_repair`, `run_job`, and `make_job_parts` merge compiled draft warnings of `DRAFT_REPAIR_CODES` directly into the same `draft.edit` repair request (still capped by the existing `2`-repair-round limit and request-size batch limit). Any findings remaining afterward stay warnings.

## Modified and Added Files

- Production / templates / style / docs: `bti/engine/viewchecks.py`, `bti/draft/compile.py`, `bti/draft/providers/auto.py`, `bti/draft/review.py`, `bti/auto_run/checks.py`, `bti/picks/auto/search.py`, `bti/picks/auto/job.py`, `bti/picks/auto/write.py`, `bti/picks/doc.py`, `bti/ops/picks_ops.py`, `bti/editor/static/js/errmsg.js`, `bti/editor/static/js/labels.js`, `style/gae/style.json`, `skills/storyboard_draft/TASK.template.md`, `skills/storyboard/SKILL.md`, `skills/picks_auto/CHOOSE.template.md`, `skills/picks_auto/PLAN.template.md`, `evals/cases/draft/draft-pace-seven-seconds.json`, `docs/AGENT_API.md`.
- Tests: `tests/draft/test_picture_time.py` (new), `tests/editor_frontend/pictime.test.mjs` (new), `tests/draft/test_viewer_review.py`, `tests/engine/test_viewchecks.py`, `tests/engine/test_catalogue_real.py`, `tests/auto/test_viewer_checks_bar.py`, `tests/picks/test_auto_search.py`, `tests/picks/test_auto_job.py`.

## Verification Results

All checks below ran after the final edits to the corresponding code, docs, and tests (`tests/cli` and all three doc generator checks ran after regenerating `docs/AGENT_API.md`; `tests/picks` ran after the final edit to `bti/picks/auto/*` and `tests/picks/*`; `tests/engine`, `tests/auto`, and `tests/draft` batches ran after the final edit to Python/templates/tests; `node --check` and `node --test` ran on the final JS tree):

- **Mac JS syntax & frontend tests** (`node --check bti/editor/static/js/errmsg.js && node --check bti/editor/static/js/labels.js && node --test tests/editor_frontend/*.test.mjs`):
  - `node --check`: exit code `0`
  - `tests 472`
  - `suites 0`
  - `pass 471`
  - `fail 0`
  - `cancelled 0`
  - `skipped 1`
  - `todo 0`
  - `duration_ms 1287.753416`
- **Server `tests/picks -q`** (`tools/deploy/snapshot_test.sh pictime -- tests/picks -q`):
  - `490 passed, 1 warning in 149.39s (0:02:29)`
- **Server `tests/engine -m "not slow" -q`** (`tools/deploy/snapshot_test.sh pictime -- tests/engine -m "not slow" -q`):
  - `829 passed, 14 skipped, 166 deselected in 447.62s (0:07:27)`
- **Server `tests/auto -q`** (`tools/deploy/snapshot_test.sh pictime --no-sync -- tests/auto -q`):
  - `265 passed, 1 warning in 113.75s (0:01:53)`
- **Server `tests/draft`** (all 40 files run in 3 disjoint batches after single-stream SSH timeouts on full-folder runs):
  - Batch A (14 files): `238 passed, 1 warning in 96.18s (0:01:36)`
  - Batch B (14 files): `231 passed, 1 warning in 70.93s (0:01:10)`
  - Batch C (12 files): `154 passed, 1 warning in 25.88s`
- **Server `tests/cli -q`** (`tools/deploy/snapshot_test.sh pictime -- tests/cli -q`, after `docs/AGENT_API.md` regeneration):
  - `132 passed, 1 warning in 53.57s`
- **Doc generator checks** (`tools/deploy/snapshot_py.sh pictime`):
  - `bti.cli.docgen --check` -> exit code `0` (`RC_DOCGEN=0`)
  - `bti.ops.doc --check` -> exit code `0` (`RC_OPS=0`)
  - `bti.editor.hints --check` -> exit code `0` (`RC_HINTS=0`)
