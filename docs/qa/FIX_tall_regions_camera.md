# Fix: Travel Oversized Tall/Wide Regions at Filling Zoom Instead of Fitting Small (`tallcam`)

**Contract:** Rule C3 of [docs/design/2026-11-27-unified-pipeline.md](../design/2026-11-27-unified-pipeline.md)  
**Modules touched:** [bti/draft/camera.py](../../bti/draft/camera.py), [bti/engine/viewchecks.py](../../bti/engine/viewchecks.py)  
**Tests touched:** [tests/draft/test_tall_camera.py](../../tests/draft/test_tall_camera.py), [tests/draft/test_box_camera.py](../../tests/draft/test_box_camera.py), [tests/engine/test_box_camera_checks.py](../../tests/engine/test_box_camera_checks.py)

---

## 1. Root cause

The scorecard (`bti/scorecard/`) measured **11.39%** (`76.62 s` across `21` shots, target `<= 6%`) of the delivered `arnolfini-v3` video showing the main painting (`van_eyck_arnolfini`, `3840 x 5253`) small between two black bars (`coverage < 0.70`), compared to **2.16%** (`14.00 s` across `3` shots) on `eligius` (`goldsmith_his_shop_3bc1`, `3469 x 4000`).

Inspection of the saved `arnolfini-v3` storyboard and regions showed two causes in `viewchecks.region_frame` and `camera._build_main_camera`:

1. **`FRAME_FILL = 0.62` drove zoom below screen-filling width (`cover_zoom = 0.50`)**:
   - `region_frame` computed `z_raw = min(0.62 * 1920 / rw, 0.62 * 1080 / rh)` and clamped the floor only at `whole_painting_frame` (`0.19634`), never at `cover_zoom` (`max(1920 / bw, 1080 / bh) = 0.50`).
   - Full-width bands and large regions (`FULL_UPPER`, `FULL_MIDDLE` `3840 x 2160` -> `z_raw = 0.3100`; `GREEN_SKIRT` `1320 x 1888` -> `z_raw = 0.3547`; `FACES_HANDS` -> `0.4238`; `LIGHT_ROOM` -> `0.4783`; `MAN_FIGURE` -> `0.1588`; `WOMAN_FIGURE` -> `0.1586`) all fell into `contentbox.MATTE_RATIO = 1.25` (`1920 / z >= 1.25 * 3840`, i.e. `z <= 0.40`) or near it, showing the whole painting small between black sidebars (`coverage ~ 0.60-0.68`).
   - Those under-filled shots (`#42 FULL_UPPER`, `#41/#67/#79/#96 ID-MARK-01`) also chained `prev_main_frame` at `z ~ 0.31` into the next shot (`#43`, `#68`, `#97`) and into `ID-BRAND-04` (`#11`, `0.199-0.202`, `coverage ~ 39%`).
2. **Oversized tall/wide regions had no travel path**:
   - Regions taller than a 16:9 filling frame (`MAN_FIGURE`, `WOMAN_FIGURE`, `BED`, `TABARD`, `WINDOW` on Arnolfini; `SAINT`, `WOMAN`, `COUPLE`, `SHELVES` on Eligius) were fitted as one static/push box at `z < cover_zoom`, shrinking the painting into black bars instead of holding filling zoom and travelling along the region from its head end.

---

## 2. What changed

### 2.1 Frame & travel helpers (`bti/engine/viewchecks.py`)

- **`cover_zoom(w, h, box=None)`**: Minimum zoom `ceil(max(1920 / bw, 1080 / bh))` filling the painted surface `box` with zero black bars.
- **`region_oversized_axis(region, w, h, box=None, *, sharp_zoom=None)`**: Returns `"tall"` or `"wide"` when the region (clamped to `pbox`) exceeds the frame at `cover_zoom` by more than `REGION_IN_TOL_PX`, and `cover_zoom <= sharp_limit(w, h)`. On small stored pictures (`long side < 1000 px`, e.g. `800 x 1200` where `cover_zoom = 2.4 > SMALL_PICTURE_MAX_ZOOM = 2.0`), it returns `None` and leaves small-picture matte rules intact.
- **`find_head_region(region_name, region, regions)`**: For a person's whole-figure region, finds a matching `head`/`face` region inside `region` (70% overlap and center inside a 5% padded box, excluding non-person regions such as `BED`, `TABARD`, `WINDOW`, `SHELVES`, and excluding group/non-head keywords). Priority prefers matching specific key tokens (`MAN_FIGURE` -> `MAN_HEAD`, `WOMAN_FIGURE` -> `WOMAN_HEAD`, `SAINT` -> `SAINT_FACE`), then label/thing tokens, and allows an unambiguous single-person fallback only when exactly one candidate exists (so multi-person `COUPLE` never picks one face arbitrarily). `head` is preferred over `face` (e.g. `MAN_HEAD` over `HUSBAND_FACE`) so hats/headdresses are not cropped.
  - **When there is no head region:** non-person tall regions (`BED`, `TABARD`, `WINDOW`, `SHELVES`), multi-person groups (`COUPLE`), and figures without a separate head region (`Eligius WOMAN`) return `None` and anchor at the top end (`y0`) for `"tall"` or left end (`x0`) for `"wide"`.
- **`region_travel_frames(...)`**: Computes filling-zoom `(head, tail)` poses (`z >= cover_zoom`, `z <= sharp_limit`):
  - Sets cross-axis zoom (`0.62 * 1920 / rw` for tall, `0.62 * 1080 / rh` for wide, capped by `HEAD_FIT_FILL = 0.85` on any matched head box).
  - When `dur` and `max_speed` are given, reduces `z` down toward `cover_zoom` (`z_speed`) if needed so the travel from `head` to `tail` (with `TRAVEL_MARGIN = 0.08` headroom at both ends) stays within `MAX_TRAVEL_SPEED = 0.35 fw/s`.
  - Anchors `head` at the matched head end (supporting upside-down/right-facing regions as well as normal top/left), ensures `head_box` fits inside `head`, and clamps both poses via `fit_frame_to_box`.
- **`region_frame` / `region_frame_info`**:
  - Returns `travel["head"]` for oversized regions; for non-oversized regions (`FULL_UPPER`, `FULL_MIDDLE`, `GREEN_SKIRT`, `FACES_HANDS`, `COUNTER`), enforces `z >= cover_zoom` when `cover_zoom <= sharp_limit`, keeping `whole_painting_frame` only when `region` is `None`.
- **`_region_framing` (`camera_off_region`, `thing_arrives_late`)**:
  - Clamps `rbox` to `pbox` when `content_box` is present (so regions touching black cloth margins, like Eligius `COUNTER`, do not false-fire when the camera stays inside `content_box`).
  - For oversized regions, checks cross-axis containment plus along-axis overlap (`_oversized_box_in_frame`) instead of requiring all 4 edges of a `4200 px` tall figure to sit inside one `1920 x 1080` frame at once.

### 2.2 Camera builder (`bti/draft/camera.py`)

- **Filling-zoom floor (`z_floor`)**: All named-region shots (`reg is not None`) keep `z >= cover_zoom` (when `can_fill`), including `clamp()`, `push_on_end()`, `travel_to_end()`, and `CAM-04`.
- **Whole painting only when asked**:
  - `reg is None` (`STATIC-01`, `CAM-03`, `CAM-01` opening) still frames/pulls back to `whole_painting_frame` (and `from="whole"` explicitly starts at `whole`).
  - `resolve_from(None | "previous")` falls back to `filling_default()` instead of `whole` after a cutaway when `reg is not None` and `can_fill`.
  - `CAM-03` with a named region ends on the filling region frame instead of `whole`.
- **Oversized tall/wide travel (`travel is not None`)**:
  - Travels `head -> tail` at filling zoom within `MAX_TRAVEL_SPEED = 0.35 fw/s` and `ZOOM_RATE_MAX = 1.0 oct/s`.
  - If the shot (or remaining duration after a continuity move from `prior_start`) is too short to travel within `MAX_TRAVEL_SPEED`, holds the `head` end with a gentle `hold_head()` push (keeping `head_box` inside frame and `z >= cover_zoom`).
  - If a naming overlay (`t_name`) would find the head clipped while gliding away, holds `head` past `t_name` before starting the glide (or holds `head` for the shot if remaining time is too short).
  - In `build_main_camera`: keeps `prev_frame` when `prev_region == region_name`; avoids collapsing a multi-key travel (`tail -> head -> tail`) when `keys[-1]` happens to match `prev_frame`; and only snaps `keys[0]` to `prev_frame` when `prev_frame[2] >= z_cov - 1e-5` so a filling region shot never inherits black bars.

---

## 3. Real-data acceptance (copies of `arnolfini-v3` and `eligius`)

**Method (no model calls):**
1. Copied `D:\code\behind-the-image\projects\arnolfini-v3` and `...\eligius` into `D:\code\behind-the-image\run\snap-tallcam\real_data\` (read-only originals untouched).
2. Decompiled saved storyboards via `bti.draft.decompile.decompile(inp)`, dropped the compiler-generated `s0000` opening shot from `c01`, stripped `params.camera` on offered main-painting camera shots that carried `slots.image.region` or were whole-painting `CAM-03`/`STATIC-01` shots (`end_zoom < 0.85 * cover_zoom`), cleaned via `bti.draft.spec.shape_problems`, and recompiled via `bti.draft.compile.compile_specs(..., draw=False, identity=True)`.
3. For `eligius` (whose saved storyboard predates `boxcam` and has `0` `slots.image.region` entries), ran both an as-saved recompile (3 whole-painting shots) and a `picks.json` beat-region pass assigning unambiguous single main-painting beat regions (`31` shots, exercising `SAINT`, `COUPLE`, `WOMAN`, `SHELVES`, `COUNTER`, etc.).

### 3.1 Scorecard & validator comparison

| Project | Metric / Check | Before | After | Target |
|---|---|---:|---:|---:|
| `arnolfini-v3` (`672.73 s`) | `small_painting_share` | **11.39%** (`76.62 s` / `21` shots) | **0.87%** (`5.86 s` / `3` shots) | `<= 6%` |
| `arnolfini-v3` | `unfilled_identity` | **5** (`ID-BRAND-04` + 4 `ID-MARK-01`) | **0** | `0` |
| `arnolfini-v3` | `camera_off_region` / `thing_arrives_late` / `frame_off_painting` / `upright_whole_share` | `0 / 0 / 0 / 0` | `0 / 0 / 0 / 0` | `0` |
| `arnolfini-v3` | `subject_not_shown` | `5` | `6` | `0` |
| `eligius` (`648.79 s`, as saved) | `small_painting_share` | **2.16%** (`14.00 s` / `3` shots) | **1.93%** (`12.49 s` / `2` shots) | `<= 6%` |
| `eligius` (`picks.json` regions) | `small_painting_share` | **2.16%** (`14.00 s` / `3` shots) | **1.17%** (`7.61 s` / `2` shots) | `<= 6%` |
| `eligius` (`picks.json` regions) | `camera_off_region` / `thing_arrives_late` | `7 / 8` | **0 / 0** | `0` |

Remaining small-painting shots in `arnolfini-v3` after recompile (`3` shots = `5.86 s`):
- `s0000` (`1.65 s`, `min_cover=0.375`): opening whole-painting shot (required by owner).
- `s0503` (`2.98 s`, `min_cover=0.375`): closing `CAM-03` pull-back to whole painting (`region=None`).
- `s0493` (`0.74 s`, `min_cover=0.622`): hand-written `CAM-01` shot with `region=None` (kept verbatim because no region was set; its first key starts at `0.31`).

---

## 4. Visual observations from contact sheets & what still looks wrong

Contact sheets rendered (stills only, `480 x 270` tiles) in `.scratch/agy_tasks/tallcam/out/`:
- [arnolfini_21_before.jpg](../../.scratch/agy_tasks/tallcam/out/arnolfini_21_before.jpg) — midpoint & end stills of all 21 `small_painting_share` shots before the fix.
- [arnolfini_21_after.jpg](../../.scratch/agy_tasks/tallcam/out/arnolfini_21_after.jpg) — midpoint & end stills of the same 21 shots after recompile.
- [tall_regions_check.jpg](../../.scratch/agy_tasks/tallcam/out/tall_regions_check.jpg) — start, midpoint & end stills for oversized tall regions (`MAN_FIGURE` 8.0s & 1.5s, `WOMAN_FIGURE` 8.0s, `BED` 8.0s, `TABARD` 8.0s, `WINDOW` 8.0s on Arnolfini; `SAINT`, `WOMAN`, `COUPLE`, `SHELVES` 7.0s on Eligius).

**What improved visually:**
- In `arnolfini_21_after.jpg`, all 18 non-whole shots that previously had wide black sidebars (`FULL_UPPER`, `FULL_MIDDLE`, `GREEN_SKIRT`, `ID-BRAND-04`, `ID-MARK-01`, and transitions `#43` / `#97`) now fill 100% of the 16:9 frame (`z = 0.50-0.55`, `cov = 100%`), with both heads, joined hands, mirror, chandelier, and green gown clearly framed and zero black bars.
- In `tall_regions_check.jpg`, `MAN_FIGURE (8.0s)` and `WOMAN_FIGURE (8.0s)` start cleanly on the head end (`MAN_HEAD` hat/face and `WOMAN_HEAD` headdress/face intact with headroom) and glide smoothly to the hem/boots/dog; `MAN_FIGURE (1.5s)` holds the head end at filling zoom; `BED`, `TABARD`, `WINDOW`, and Eligius `SAINT`, `WOMAN`, `COUPLE`, `SHELVES` all fill 100% of the frame and travel top-to-bottom within `content_box`.

**What still looks wrong (observed honestly):**
1. **`#68 s0493` (`arnolfini-v3`) still starts at `z = 0.31` for `0.74 s`**: because `s0493` has `slots.image.region = null` in the saved storyboard, `decompile` + `compile` kept its saved `params.camera` verbatim. Naming its region (`BACK_WALL` / `MIRROR`) in the storyboard/visual script would eliminate that remaining `0.74 s` sidebar.
2. **`subject_not_on_screen` went from 5 to 6 on `arnolfini-v3` (`s0481`, `b0136`, `"silks, fine fabrics"`)**: `s0481` follows a cutaway (`02_lucca_seen`) and has `region = "GREEN_GLOW"`. Previously `whole -> GREEN_GLOW` exceeded `ZOOM_RATE_MAX`, so `no-race` cut straight to `GREEN_GLOW`; with `filling_default()` (`z = 0.50`), `0.50 -> 1.116` stayed inside `ZOOM_RATE_MAX` and zoomed in over `45%` of the shot. (`silks` in `picks.json` points to an unused borrowed image `damask_fragment_pomegran`, not `GREEN_GLOW`, so `s0481` was already a picks/draft mismatch.)
3. **Pre-existing issues outside camera scope**:
   - `arnolfini-v3` has `repeated_regions = 5` (`FULL_UPPER`, `WOMAN_HEAD`, target `<= 4`), `2` pre-existing `narration_on_screen` compile errors on `c01:2` / `c01:3` `params.sub`, and `5` other `subject_not_on_screen` warnings.
   - `eligius` has `6` `borrowed_without_caption` and `3` `text_too_brief` warnings, and in `eligius_regions` `biggest_mark` rose from `0.388` to `0.620` (`s0074`, `GIRDLE` `AN-01` ring) when zoomed to `region_frame` without re-sizing the legacy ring overlay.

---

## 5. Tests & doc-checks run after final edit

### 5.1 Server snapshot (`winbox-cmd`, `tools/deploy/snapshot_test.sh tallcam --no-sync -- ...`)

| Suite | Result | Reachability / Notes |
|---|---|---|
| `tests/draft -q` | **650 passed**, 0 failed | Includes 7 new tests in `test_tall_camera.py` + updated `test_box_camera.py` |
| `tests/engine -m "not slow" -q` | **859 passed**, 14 skipped, 168 deselected, 0 failed | Includes 2 new tests in `test_box_camera_checks.py` |
| `tests/scorecard -q` | **12 passed**, 0 failed | Reached via `viewchecks` |
| `tests/picks -q` | **506 passed**, 0 failed | Reached via `viewchecks` / `picks` |
| `tests/editor -q` | **534 passed**, 0 failed | Reached via `viewchecks` / `draft` |
| `tests/auto -q` | **270 passed**, 0 failed | Reached via `viewchecks` / `auto_run` |
| `tests/ops -q` | **561 passed**, 0 failed | Reached via `storyboard` / `viewchecks` |
| `tests/cli -q` | **132 passed**, 0 failed | Reached via `bti` CLI / validation |
| `tests/export -q` | **87 passed**, 2 skipped, 0 failed | Reached via `export` / `viewchecks` |
| `tests/identity -q` | **108 passed**, 0 failed | Reached via `identity` / `viewchecks` |
| `tests/music` | Not run (unreachable) | `bti/music/` does not import or call `bti/draft/camera.py` or `bti/engine/viewchecks.py` |

*(Note: on `winbox-cmd`, pytest folders that emit `fastapi\testclient.py` deprecation warnings had stdout truncated inside the `$()` capture right at the warning line while exiting `0`; exact per-folder counts above were verified from the 100% progress dots `[100%]` in the full log and exit code `0`.)*

### 5.2 Generators (`--check` on `winbox-cmd`) & Mac JS tests

- `bti.cli.docgen --check`: exit **0**
- `bti.ops.doc --check`: exit **0**
- `bti.editor.hints --check`: exit **0**
- Mac JS (`node --test tests/editor_frontend/*.test.mjs tests/picks/*.test.mjs tests/output/*.test.mjs`): **508 tests: 507 passed, 0 failed, 1 skipped** (`sbissues.test.mjs`, skipped by default in worktrees). No JS files were modified.
