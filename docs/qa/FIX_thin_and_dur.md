# Thin details count as small; overlay lengths past shot end are cut, not refused

Worker `thindur` (2026-11-21). Short report.

## Why
1. **The settle (`small_detail_not_lit`).** On a 3840 x 5253 painting, `SETTLE_CUSHION` (588 x 1288 px, centre 2010, 2592) is framed by `viewchecks.region_frame` (`FRAME_FILL = 0.62`) at zoom `0.51988`, so it fills 15.9% of the frame's width and 62.0% of its height. `_small_detail_not_lit` only flagged regions under `SMALL_ON_SCREEN` (`0.40`) on BOTH dimensions, so tall narrow or long flat objects never asked for `HI-01` and got only `X-ANN-01` ("ribbon text").
2. **Overlay `dur` slightly past shot end (`bti.ops.sb_ops`).** In `draft.edit` (fast path), asking `add_overlay` for an overlay running "to the end of the shot" failed twice (`invalid_field`: `"ops[0].dur: ends at 284.94 s, after shot s0040 ends (284.91 s): use a shorter dur"`) when `dur` overshot by `0.03 s`.

## What changed

### A. A thin thing is small
- [`bti/engine/viewchecks.py`](../../bti/engine/viewchecks.py):
  - Added `THIN_ON_SCREEN = 0.20`, `THIN_MAX_SPAN = 0.70`, and shared helper `is_small_on_screen(x, y, rx, ry, cx, cy, z, w=None, h=None, box=None)`.
  - A region wholly inside the frame (`box_inside_frame` with `REGION_IN_TOL_PX = 1.0`) is small when `ws < SMALL_ON_SCREEN and hs < SMALL_ON_SCREEN` (unchanged), OR when measured against the visible painted surface (`ow x oh`) inside the frame, its narrower side is `< THIN_ON_SCREEN` (`0.20`) and its longer side is `<= THIN_MAX_SPAN` (`0.70`).
  - `_small_detail_not_lit` and `region_frame_info` (`needs_spotlight`) both call `is_small_on_screen`; `_small_detail_not_lit` sets `args["limit"]` to `SMALL_ON_SCREEN` (`0.4`) or `THIN_ON_SCREEN` (`0.2`) depending on which clause matched.
  - `_highlight_nothing_to_dim` is unchanged.
- [`style/gae/techniques.json`](../../style/gae/techniques.json) (propagating to generated `inputs/techniques.md`): updated `HI-01` (`use_when`, `needs`) and `X-ANN-01` (`usage_rule`, `needs`) so "small on screen" explicitly covers a narrow or flat thing in a wide frame (a bench, a rug, a string of beads, a candle) whose narrower side is under 20% of the frame's matching side.
- [`skills/storyboard_draft/TASK.template.md`](../../skills/storyboard_draft/TASK.template.md) (rule 14) and [`skills/storyboard_edit/FAST.template.md`](../../skills/storyboard_edit/FAST.template.md): added the same narrow-or-flat wording.

### B. Overlay lengths past shot end are cut, and `HI-01` without a length runs to shot end
- [`bti/ops/sb_ops.py`](../../bti/ops/sb_ops.py):
  - Added `_cut_dur(ot0, t1)` (floors `t1 - ot0` to milliseconds so `ot0 + dur <= t1` never trips `overlay_outside_shot` on rounding).
  - `_overlay_window`: still refuses overlays starting outside `[t0, t1)` (`ops[i].start`) or with zero/negative duration (`<= 0 s`), and cuts any `dur` or `end` running past `t1` instead of refusing (`(clamped_ot1, was_cut)`).
  - `_build_overlay` (`add_overlay`, `replace_range`) and `set_overlay`: when `dur` or `end` runs past `t1`, drop `end` if present and set `dur = _cut_dur(ot0, t1)`, recording `"cắt đến hết cảnh"` (or `"lớp phủ cắt đến hết cảnh"` in `replace_range`) in the change sentence.
  - `_build_overlay` when neither `dur` nor `end` is given: `HI-01` uses `bti.draft.defaults.overlay_default_window("HI-01", ...)` (running to `t1 - ramp_out`, shifting `start` earlier up to `2.5 s` before `t1 - ramp_out` when needed, with safe fallback to `(ot0, t1)` if the shot is shorter than `ramp_out`), instead of capping at `3.0 s`. Other overlays keep `min(3.0, _cut_dur(ot0, t1))`.
  - Updated `OVERLAY_FIELDS`, `add_overlay`, and `set_overlay` schema descriptions/summaries.
- [`skills/storyboard_edit/FAST.template.md`](../../skills/storyboard_edit/FAST.template.md): instructed the fast-edit model to leave `dur` (and `end`) out for "until the end of the shot" (`HI-01` runs to shot end; `set_overlay`: `dur: null`).
- Regenerated [`docs/OPS.md`](../../docs/OPS.md) (`python -m bti.ops.doc`) and [`skills/storyboard/SKILL.md`](../../skills/storyboard/SKILL.md) (`python -m bti.cli.docgen`).

## `THIN_ON_SCREEN = 0.20` on the real documents, and keeping faces/figures out

Chosen thresholds: `THIN_ON_SCREEN = 0.20` and `THIN_MAX_SPAN = 0.70` (measured against the visible painted area `ow x oh` inside the frame). Checked with `.scratch/thindur/arnolfini_check.py` against `.scratch/agy_tasks/pointfix/data/arnolfini/` and `tests/engine/fixtures/catalogue/{arnolfini,eligius}`:

- **Stored Arnolfini storyboard as-is**: `[]` (0 flagged, because the stored hand-written cameras use loose boxes or do not hold those thin regions inside the frame throughout).
- **Settle shot rebuild** (`b0023` / `s0040`, `SETTLE_CUSHION` `588 x 1288` px at `(2010, 2592)`, built with `camera.build_main_camera` and holding only `X-ANN-01` "Settle"): flagged `small_detail_not_lit` (`beat='b0023'`, `region='SETTLE_CUSHION'`, `shot='s0040'`, `width_share=0.159`, `height_share=0.617`, `limit=0.2`); cleared (`[]`) once `HI-01` is added.
- **Stored Arnolfini unique-detail shots rebuilt with `region_frame` on stored regions**: 4 shots flagged:
  - `b0025` `RUG` in `s0045` (`18.5% W x 62.0% H`)
  - `b0027` `WINDOW` in `s0049` (`7.6% W x 62.0% H`)
  - `b0037` `ROUNDELS_WOMAN` in `s0067` (`19.6% W x 62.0% H`)
  - `b0056` `BEADS` in `s0096` (`17.1% W x 62.0% H`)
- **`region_frame_info` (`needs_spotlight`) across fixtures**:
  - Stored Arnolfini (28 regions): 9 lit (`BEADS`, `CHERRY_TREE`, `FUR_SLEEVE`, `LIT_CANDLE`, `ORANGE_SILL`, `RED_SHOES`, `ROUNDELS_WOMAN`, `RUG`, `WINDOW`); 19 not lit (`MAN_HEAD`, `WOMAN_HEAD`, `TABARD`, `BED`, `JOINED_HANDS`, etc.).
  - Catalogue Arnolfini (31 regions): 9 lit (`BEADS`, `BLUE_HEM`, `BRUSH`, `CHERRY_TREE`, `FUR_SLEEVE`, `LIT_CANDLE`, `MIRROR_VISITORS`, `ORANGE_SILL`, `WINDOW`); 22 not lit (`MAN_FULL`, `WOMAN_FULL`, `MAN_HEAD`, `WOMAN_HEAD`, `BED`, etc.).
  - Catalogue St. Eligius (21 regions): 2 lit (`COCONUT`, `MIRROR`); 19 not lit (`SAINT`, `SAINT_FACE`, `WOMAN`, `COUPLE`, `MAN_CHAIN`, `SHELVES`, etc.).

**How faces and figures stay out purely by shape (no region names):**
1. **Faces**: `region_frame` scales the limiting axis to `FRAME_FILL = 0.62`. On 16:9, any box with height/width `<= 1.74` stays `>= 20%` wide (`WOMAN_HEAD` 37.4%, `MAN_HEAD` 38.9%, `SAINT_FACE` 30.2%, tight `1.5:1` face 23.2%).
2. **Figures on upright paintings**: measuring against the **visible painted width `ow`** (excluding pillarbox black bars on upright works) keeps standing figures well above 20% (`MAN_FULL` and `WOMAN_FULL` are 19.6% of the 1920 px canvas with black bars, which would false-fire against canvas width, but **50.0% of `ow`**).
3. **Full-height standing figures on wide/landscape paintings** (e.g. `650 x 1950` on `3840 x 2600`): even when narrower than 20% of `ow`, their height covers `> THIN_MAX_SPAN = 0.70` of visible painted height `oh` (e.g. 75.0%), whereas details framed by `region_frame` (`FRAME_FILL = 0.62`) stay `<= 65%`.

## Tests

### New and updated tests
- [`tests/engine/test_pointfix_checks.py`](../../tests/engine/test_pointfix_checks.py): tall narrow (`300x670` and settle `588x1288`), long flat (`1200x160` and `1400x180`), square small (`80x80`), large (`900x600`), face-shaped (`844x788`, `260x390`), upright standing figures (`1920x4360`, `1300x4200`), landscape standing figure (`650x1950`), and `region_frame_info` `needs_spotlight`.
- [`tests/draft/test_pointfix_catalogue.py`](../../tests/draft/test_pointfix_catalogue.py): thin-thing guidance reaching `inputs/techniques.md` (`HI-01` and `X-ANN-01`), `TASK.template.md` rule 14, and `FAST.template.md` (including leaving `dur` out).
- [`tests/ops/test_sb_ops.py`](../../tests/ops/test_sb_ops.py): `add_overlay`, `set_overlay`, and `replace_range` cutting `dur` (+0.03 s and 60 s) and `end` to shot end, out-of-shot `start` still refused, `HI-01` with no `dur`/`end` running to `shot_end - ramp_out` (with early-start shift and sub-`ramp_out` short shot), and `AN-01` keeping `min(3.0, remaining)`.
- [`tests/draft/test_box_storyboard.py`](../../tests/draft/test_box_storyboard.py): fast-edit turn with `mock` provider answering `add_overlay` (`HI-01`) with `dur` 0.03 s past shot end accepted on attempt 1 (`repairs == 0`), cut to `7.0` s.

### Summary lines (exact output after final code/template/test edits)
- Windows snapshot `thindur` (`tools/deploy/snapshot_test.sh thindur`):
  - `tests/engine -m "not slow"`: `========= 783 passed, 14 skipped, 166 deselected in 354.82s (0:05:54) =========`
  - `tests/draft`: `================= 547 passed, 1 warning in 161.18s (0:02:41) ==================`
  - `tests/ops`: `================= 539 passed, 1 warning in 129.00s (0:02:08) ==================`
  - `tests/editor`: `================= 530 passed, 1 warning in 241.90s (0:04:01) ==================`
  - `tests/auto`: `================== 242 passed, 1 warning in 99.68s (0:01:39) ==================`
  - `tests/state`: `================= 321 passed, 1 warning in 213.76s (0:03:33) ==================`
- Windows generator checks (`tools/deploy/snapshot_py.sh thindur -m ... --check`):
  - `bti.cli.docgen --check`: exit `0`
  - `bti.ops.doc --check`: exit `0`
  - `bti.editor.hints --check`: exit `0`
- Mac Node tests (`node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`):
  - `tests 496`, `pass 495`, `fail 0`, `skipped 1`, `duration_ms 969.2335`

## What could not be verified
- No real model call (`agy`, `claude`, `codex`) or live `draft.start` / `draft.edit` run was executed (prohibited by task limits); model prompts and fast-edit handling were verified through `mock` responses and static/compile tests.
- No rendered video or still frames from the 2026-11-21 real Arnolfini draft project were inspected; the settle-shot check used `.scratch/agy_tasks/pointfix/data/arnolfini/` rebuilt at compile/check level.
- `-m slow` engine tests were not run (prohibited by task limits).
