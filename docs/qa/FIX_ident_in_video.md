# Fix: Channel Ident (`ID-BRAND-04`) and Chapter Marks in Finished Videos (worker `identfix`)

## 1. Root Causes Found on Real Data (`arnolfini-v3` and `eligius`)

1. **Ident light starting in the black matte margin and tiny rest spot (`arnolfini-v3`):**
   - Shot `s0311` (`ID-BRAND-04`, variant `B`) fell back to `whole_keys` (`zoom = 0.19634 -> 0.20224`) because the preceding shot `s0478` ended on `FULL_UPPER` (`zoom = 0.31`), where `DOORWAY_FIGURES` (`y = 1597`) fell outside `_region_framed`'s zoom check (`0.31 > 0.2056 * 1.35`).
   - At `zoom = 0.19634`, the `3840 x 5253` portrait painting covers only the central ~39% of the 1920x1080 frame width, leaving ~30% black matte on each side. `BrandRakingSweep.finish` (variant `B`) swept from `0.16 * W` to `0.84 * W`, so the lamp started in empty black matte outside the painting (`in_video_0m51_to_0m59.jpg`).
   - `DOORWAY_FIGURES` has `rx = 25, ry = 50` px (`~11 px` tall at `zoom = 0.20`). The old floor (`0.08 * W`, `0.095 * H` on `srx, sry`) left the illuminated region too small on a phone screen.
2. **`choose_rest_region` step 2 ignored list-valued `where`:**
   - Subjects in `picks.json` commonly store `where` as a list of places (e.g., `[{"region": "MAN_FIGURE"}, {"region": "MAN_HEAD"}]`), whereas step 2 checked `isinstance(where, dict)` only.
3. **Chapter marks 3 and 7 (`s0338`, `s0389`, and also 5 and 6 `s0362`, `s0373`) sitting on a narrow pillarboxed column (`zoom = 0.31`):**
   - `chapter_marks` copied `next`'s first camera key unconditionally. In `arnolfini-v3`, those next shots (`s0339`, `s0493`, `s0374`, `s0194`) start on a half-way pose (`FULL_UPPER` / `FULL_LOWER` at `zoom = 0.31`, covering ~62% of frame width between two black bars, between `z_whole = 0.19634` and `z_fill_w = 0.50`).

## 2. Changes Made

- **`bti/engine/techniques/identity.py` (`BrandRakingSweep` / `ID-BRAND-04` and `_warp_relief_roi`):**
  - Proposed and applied phone-readable rest-spot floors: `REST_MIN_RY_PCT = 12.0` (`% H` for `sry`) and `REST_MIN_RX_PCT = 10.5` (`% W` for `srx`), preserving Variant `B`'s warm horizontal-oval lamp pool while guaranteeing a measured visible half-light radius `>= 10.6% H` vertically (`>= 15.6% H` horizontally) even for pinpoint regions.
  - Added `_paint_rect_raw` and `_paint_rect_visible` (respecting asset `content_box` via `bti.media.contentbox.clean`) and made `_resolve_region` respect `content_box` when `region` is `None`.
  - Confined Variant `B`'s Move 1 entry, turn point (`x_start`, `x_mid` inside `[vx0 + 0.02*vw, vx1 - 0.02*vw]` respecting `direction`), beam size, and Move 2 arc/pivot strictly to the visible painted surface.
  - Updated `_apply_surface(..., matte_gain=...)` and `_warp_relief_roi(..., paint_rect=...)` across variants `A`, `B`, `C` so lamp illumination, warm tint, and relief stay strictly inside the painted surface while any visible matte margin remains uniformly dark (`floor -> 1.0` with `p_open`).
- **`bti/identity/apply.py`:**
  - Added `_paint_box`, `_cover_zoom`, `_fills_screen` (`>= 99%` coverage on both axes, matching `1 - CB.OFF_LIMIT`), `_clamp_fill_pose`, and `filling_band_keys` (keeping `whole_keys` intact for existing callers/tests).
  - Updated `title_slot` and `_region_framed`: `ID-BRAND-04` always fills 100% of the screen (`zoom >= _cover_zoom`, so never smaller than the opening shot), continuing from `prev`'s end pose with `BRAND_SWEEP_PUSH = 1.08` (`inout_sine`) when `prev` fills the screen and frames the rest region cleanly, or using a width-filling band centred near the rest region otherwise; `ID-BRAND-01/02/03` likewise fall back to a width-filling band when `prev` does not fill the screen.
  - Updated `chapter_marks`: uses `next`'s first camera key (starting up to 4% wider, clamped to keep 100% screen coverage) ONLY when `next`'s first key fills the screen; otherwise places the mark on a width-filling band (`filling_band_keys`) centred near `next`'s target position, never on a half-way pose or pillarboxed whole frame.
  - Fixed `choose_rest_region` step 2 to iterate over list-valued `where` entries (`list` or `dict`), matching `asset in (None, main_key)` and `tight: true`.

## 3. Real-Data Acceptance & Frame-by-Frame Inspection

Rendered in `D:\code\behind-the-image\run\snap-identfix\` on copies of `arnolfini-v3`, `eligius`, and four synthetic shapes (`shape_tall` 1000x2000, `shape_wide` 2400x1000, `shape_square` 1400x1400, `shape_bright` 1800x1300 ~240/255), plus whole-painting matte-isolation stills. All clips and stills copied to `.scratch/agy_tasks/identfix/out/` and visually inspected.

### Frame-by-frame comparison: `arnolfini-v3` ident vs `intro_B.mp4` (`intro_B_start/middle/rest.png`) and `in_video_0m51_to_0m59.jpg`

- **`start` (`u = 0.16`, `arnolfini-v3_ident_start.png` vs `intro_B_start.png`):**
  - *Matches demo look:* Warm raking lamp enters from the left, revealing crisp relief on the window frame, Giovanni's face/hat, and the chandelier as `RAKING LIGHT` cuts in with directional bevel highlights.
  - *Differs from demo:* The new ident is full-bleed width-filling (`zoom = 0.50 -> 0.54`, `cov = 1.0 x 1.0`) rather than the demo's pillarboxed whole painting (`zoom = 0.205 -> 0.295`), so there are zero black side margins and the lamp starts directly on the painted window edge (no empty matte glow as in `in_video_0m51_to_0m59.jpg`).
- **`middle` (`u = 0.36`, `arnolfini-v3_ident_middle.png` vs `intro_B_middle.png`):**
  - *Matches demo look:* `RAKING LIGHT` is fully revealed across the upper canvas; the lamp reaches the right painted edge (red bed curtain folds with strong grazing relief) before pivoting downward.
  - *Differs from demo:* Full-bleed painting fills the entire 16:9 frame; the lamp turns at the painted bed-curtain edge instead of in black matte space.
- **`rest` (`u = 0.68`, `arnolfini-v3_ident_rest.png` vs `intro_B_rest.png` and `in_video_0m51_to_0m59.jpg`):**
  - *Matches demo look:* `RAKING LIGHT` dims slightly above the spot; `Is He Marrying Her or Mourning Her?` and `THE ARNOLFINI PORTRAIT · JAN VAN EYCK, 1434` sit cleanly below the spot with crisp two-tier shadow contrast; strong relief shows across the lit mirror roundels and plaster wall (`relief_mean_diff_in_spot = 9.2`).
  - *Differs from demo:* The demo targeted `JOINED_HANDS`, whereas the real project cold-open question line (`b0133`) targets `DOORWAY_FIGURES` (the mirror). Compared to `in_video_0m51_to_0m59.jpg`, the rest spot now illuminates the full convex mirror and its Passion roundels (`measured_half_ry = 114.5 px = 10.60% H`, `measured_half_rx = 169.0 px = 15.65% H`) instead of a tiny dot, with zero black side bars.

### Real project measurements & visual notes

- **`arnolfini-v3`:** `chosen_rest_region = "DOORWAY_FIGURES"`, `opening_zoom = 0.19634`, ident `zoom = 0.50 -> 0.54` (`cov = 1.0 x 1.0`), rest spot `10.60% H x 15.65% H` half-light radius. Marks 1, 2, 4 flow into `next`'s first camera key (`cov = 1.0 x 1.0`); Marks 3, 5, 6, 7 (previously `zoom = 0.31` pillarboxed columns in `zoom4.jpg`) now sit on width-filling bands (`zoom = 0.50 -> 0.515`, `cov = 1.0 x 1.0`) centred vertically near each next shot's start `cy`.
- **`eligius`:** `chosen_rest_region = None` (cold open `b0005` has `region: None` and `subjects: []`), `opening_zoom = 0.27185`, ident `zoom = 0.58842 -> 0.63549` (`cov = 1.0 x 1.0`, `content_box` excludes the black studio cloth), rest spot on St. Eligius's face and red tunic (`16.85% H x 16.11% H`, `relief_mean_diff_in_spot = 6.91`). All 8 marks have `cov = 1.0 x 1.0`.
  - *Observed imperfection:* In `eligius_mark_1_middle.png` / `rest.png` (`zoom = 0.5884`), the painting's own dark painted wooden border strip along the right edge of `content_box` (`x1 = 3363`) is visible on the far right, because `s0013` starts at `0.5884` (`within 1%` of `0.58842`).
- **Test shapes (`tall`, `wide`, `square`, `bright`):**
  - `shape_tall` (tiny `rx=12, ry=12`): `11.34% H x 15.69% H`, `cov = 1.0 x 1.0`, `relief_mean_diff = 14.17`.
  - `shape_wide` (tiny `rx=15, ry=12`): `10.93% H x 16.06% H`, `cov = 1.0 x 1.0`, `relief_mean_diff = 16.93`.
  - `shape_square` (`region=None`): `16.76% H x 22.45% H`, `cov = 1.0 x 1.0`, `relief_mean_diff = 13.16`.
  - `shape_bright` (~240/255, `wake=0.85`): `10.97% H x 15.93% H`, `cov = 1.0 x 1.0`, `relief_mean_diff = 20.59`.
  - Whole-painting matte checks (`shape_*_whole_start/middle/rest.png`): black matte outside the painting stays dark throughout Move 1 and Move 2.
  - *Observed imperfection:* On `shape_bright_start.png` with `wake=0.85`, Move 1's bright wake behind `RAKING` slightly lowers stem contrast while the beam passes through the upper text band; at rest (`shape_bright_rest.png`), the two-tier glyph shadow keeps all three lines legible.

## 4. Verification Summary

- **Server test suites (`tools/deploy/snapshot_test.sh identfix ...`):**
  - `tests/identity`: `108 passed` (3.99s)
  - `tests/engine -m "not slow"`: `858 passed, 14 skipped, 168 deselected` (408.82s)
  - `tests/draft`: `643 passed` (180.89s)
  - `tests/editor`: `534 passed` (263.35s)
  - `tests/ops`: `561 passed` (173.27s)
  - `tests/cli`: `132 passed` (57.97s)
  - `tests/auto`: `270 passed` (107.67s)
  - `tests/export`: `87 passed, 2 skipped` (47.54s)
  - `tests/music`: `34 passed` (2.52s)
  - `tests/picks`: not run on server — unreachable by our changes (`git grep "bti\.identity\|bti\.engine" bti/picks/ tests/picks/` returned zero matches).
- **Server generator checks (`tools/deploy/snapshot_py.sh identfix ...`):**
  - `python -m bti.cli.docgen --check`: exit 0 (up to date)
  - `python -m bti.ops.doc --check`: exit 0 (up to date)
  - `python -m bti.editor.hints --check`: exit 0 (up to date)
- **Mac JS tests:**
  - `node --test tests/editor_frontend/*.test.mjs tests/picks/*.test.mjs tests/output/*.test.mjs`: `505 passed, 0 failed, 1 skipped` (`sbissues.test.mjs` skipped in worktree as expected).
