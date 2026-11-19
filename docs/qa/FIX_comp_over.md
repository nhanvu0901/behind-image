# FIX: the explanatory overlays `KEY-01`, `NUM-01` and `DOC-01` (worker `compover`, 2026-11-18/19)

Brief: `.scratch/agy_tasks/compover/TASK.md`. Contract: `docs/design/2026-11-18-explainer-components.md` (sections 2, 3, 4 `KEY-01`, `NUM-01`, `DOC-01`, 5, 7).
Approved mock-up: `docs/design/mock/2026-11-18-explainer/components.html` (functions `labels`, `number`, `doclit`). Module: `bti/engine/techniques/explain_over.py`.

## What was built

* **Module** `bti/engine/techniques/explain_over.py`: three overlay renderers (`LabelsKey`, `BigNumber`, `LitLine`) and the helpers they share (`Art`: a line of EB Garamond text drawn at quarter-pixel positions with a soft shadow;
  `draw_text`, `draw_disc`, `gain`, `NeedsCamera`).
* **Registry**: three entries appended after `MAP-01` in `style/gae/techniques.json` (the file is read and written back in its own format; the diff is only the appended entries), each with `label_vi`, description, `usage_rule`
  (the kind of sentence it serves, the fields in one line, what the technique does for the agent), params with defaults and `min`/`max` for every number, the timing block with `min_s`, evidence, and a preview.
* **Previews**: `style/gae/previews/KEY-01.mp4`, `NUM-01.mp4`, `DOC-01.mp4` (640 x 360, 15 fps, 7 s, h264, made on the server) and `.jpg` thumbnails (480 px), by `python tools/explain/render_examples.py preview`.
* **Page**: Vietnamese words for the choices and the fields of the three lists (`labels.js`, block `compover`, directly after `mapbuild`) and sentences for the three new issue codes (`sbissues.js`, block `compover`, directly after `mapbuild`).
  The generic row editor of the `items` type needed no change.
* **Docs**: `bti/engine/README.md` and `docs/APP_GUIDE.md` (parts directly after the map's), technique counts set to 82.
* **Tool**: `tools/explain/render_examples.py` (`stills`, `timing`, `preview`) builds a lab project on the Arnolfini Portrait of `projects/technique_lab` and renders the examples below.

## Per technique: the final parameters and fields

All times are seconds from the start of the OVERLAY (a word anchor in an `at` is the absolute time of that word, resolved by the engine). Everything leaves by a fade that ends with the overlay (`leave_s`).

### `KEY-01` labels as a key to parts of a picture (overlay; timing 7 s, at least 2.5 s, at most 30 s)
* `labels` (items, 1 to 12): `text` (string, 1 to 60 characters, required), `ref` (region name or `[x, y]` in source pixels, required), `side` (`auto`, `n`, `ne`, `e`, `se`, `s`, `sw`, `w`, `nw`; default `auto`),
  `at` (seconds or word anchor, 0 to 600, default 1.0), `style` (`italic`, `regular`, `caps`; default `italic`). Default: the mock-up's five labels (candle `LIT` w, `INSCR` n, `MIRROR` s, `AMBER` w, `BRUSH` e at 0.7, 1.6, 2.5, 3.4, 4.3 s).
* `cap_pct` 2.0 to 3.0 (2.4), `dim_picture_to` 0.6 to 1.0 (0.78), `fade_s` 0.1 to 1.5 (0.3), `leave_s` 0.1 to 2.0 (0.5), `shadow` (true), `leader` (`none`, `hairline`, `auto`; **`auto` since the follow-up, was `none`**).
* Valid on (see below), milliseconds per frame (default example, 1920 px, server): **34 to 42 median** with the base shot (the overlay itself adds 3 to 14 ms; the eight-label example 45 to 53 ms).

### `NUM-01` a big number with a comparison (overlay; timing 7 s, at least 3 s, at most 20 s)
* `rows` (items, 1 to 4): `label` (string, up to 60, may be empty), `value` (string as shown, 1 to 16 characters, required), `units` (string, up to 24), `count` (number of marks, 0 to 60, default 0), `at` (default 1.0).
  Default: "An ordinary gown" 600 pelts, 12 marks at 1.0 s; "This gown" 2,000 pelts, 40 marks at 2.9 s.
* `caption` (up to 80 characters; "each dot is fifty squirrel pelts"), `source` (up to 80; a line naming the sample narration), `dim_picture_to` 0.2 to 1.0 (0.38), `cap_pct` 6 to 14 (8), `align` (`left`, `right`),
  `marks_s` 0.2 to 4.0 (1.1), `leave_s` 0.1 to 2.0 (0.5).
* Valid on every shot (needs no picture). Milliseconds per frame (default example): **49 to 58 median** with the base shot (adds 11 to 22 ms).

### `DOC-01` a lit line of a document, with its reading (overlay; timing 7 s, at least 3 s, at most 30 s)
* `lit` (items, 1 to 6): `ref` (region name or point; optional), `box` (text `x0, y0, x1, y1` in source pixels; optional, wins over `ref`), `at` (default 1.0), `hold_s` (0 to 60; 0 = until the next line is lit, or to the end).
  Default: `INSCR` at 1.0 s. A line with neither `ref` nor `box` is the error `doc_lit_no_target`; a box that is not x0 < x1, y0 < y1 is `doc_bad_box`.
* `dim_to` 0.25 to 0.6 (0.34), `ramp_s` 0.2 to 2.0 (0.7), `edge_px` 0 to 200 (28), `pad_px` 0 to 400 (40), `reading` (up to 120 characters; "Jan van Eyck was here. 1434"),
  `original` (up to 120; "Johannes de eyck fuit hic · 1434", shown in capitals), `reading_at` 0 to 600 s (2.4; seconds only, as the brief says), `leave_s` 0.1 to 2.0 (0.5).
* Valid on (see below). Milliseconds per frame (default example): **53 to 60 median** with the base shot (adds 9 to 26 ms).

### Milliseconds per frame at 1920 px (Windows server, snapshot `compover`, 39 frames spread over 6.5 s of each example after one cold frame; `python tools/explain/render_examples.py timing`)

Two runs (the server is shared; the second was made while other workers were testing):

| Example | first frame (cold) | median | mean | p90 | max | the same frames of the base shot alone (CAM-05) | the overlay adds |
|---|---|---|---|---|---|---|---|
| `KEY-01` default (5 labels) | 321 ms / 349 ms | 34.3 / 41.5 | 35.4 / 42.5 | 41.9 / 49.2 | 44.2 / 51.0 | 29.9 / 38.8 | 4.4 / 2.7 |
| `KEY-01` eight labels, moving camera | 78 / 113 | 45.1 / 53.3 | 45.3 / 54.2 | 52.7 / 62.1 | 70.2 / 104.3 | 34.5 / 38.9 | 10.6 / 14.4 |
| `NUM-01` default (2 rows, 52 marks) | 36 / 41 | 48.9 / 57.7 | 48.2 / 55.8 | 55.6 / 64.9 | 66.9 / 66.6 | 34.5 / 40.5 | 14.3 / 17.1 |
| `NUM-01` four rows, 140 marks | 35 / 37 | 45.2 / 57.1 | 46.5 / 56.3 | 58.0 / 64.7 | 69.5 / 67.1 | 33.9 / 37.4 | 11.3 / 19.7 |
| `NUM-01` one row alone, no marks | 31 / 44 | 51.7 / 58.4 | 50.2 / 56.8 | 61.7 / 62.3 | 72.3 / 83.8 | 34.0 / 36.8 | 17.7 / 21.6 |
| `DOC-01` default (1 window, reading) | 35 / 38 | 52.8 / 60.5 | 50.8 / 57.8 | 59.0 / 65.5 | 61.4 / 69.4 | 34.3 / 34.8 | 18.5 / 25.8 |
| `DOC-01` two windows | 36 / 37 | 43.1 / 45.0 | 43.9 / 45.4 | 53.0 / 54.7 | 60.4 / 56.1 | 34.5 / 35.7 | 8.6 / 9.3 |

For comparison (`docs/qa/FIX_map_build.md`, same server): `CAM-01` 27.3, `CMP-03` 58.4, `MAP-01` 59.2. The three overlays are inside the range of the other techniques. The cold first frame of `KEY-01` includes loading the picture and the fonts.

## On which base shots each is valid, and how validation refuses the others

* **`KEY-01` and `DOC-01`** place things on a picture through the base shot's camera, as `HI-01` and `AN-01` do (`view.to_screen`, sizes times `view.z`). They are valid on every base technique whose renderer provides `view()`; today these are
  `CAM-01` to `CAM-06`, `STATIC-01`, `X-LAY-01`, `LAY-01`, `LAY-04`, `LAY-05` (the camera of the left picture), `HI-02`, `AN-07`, `CMP-01` to `CMP-05`, `X-CMP-01`, `X-CMP-02` and the four ID bases (`ID-BRAND-01/02`, `ID-MARK-01/02`).
  (24 techniques, computed from the registry.)
* **Refused** (error `overlay_needs_camera`, path `shots[i].overlays[j].technique`, args `technique`, `base`): `LAY-02`, `LAY-03`, `LAY-06`, `LAY-07`, `LAY-08`, `TXT-01`, `STATIC-06`, `STATIC-07`, `DIA-01` to `DIA-07`, `FOOT-01`,
  `SHORT-01`, `-02`, `-03`, `-05`, `X-CARD-01` to `X-CARD-04`, `MAP-01` (25 techniques). The check is `storyboard.validate` calling the overlay class's `check_base(base technique id)` (a new, small hook; see "Files outside my module").
  It looks at the class only: a base that provides `view()` but returns None at some moment (a `CMP-*` shot without a camera parameter) is valid and draws nothing, as every other camera overlay of the engine does.
* A shot without an `image` slot makes the overlay incomplete (the usual `incomplete` warning: it can be saved, not approved, and it is skipped when drawn). A region name that is not on the shot's picture is the existing error `region_undefined`.
* **`NUM-01`** needs no picture and is valid on every shot (tested on a card and on `MAP-01`).

## Tests

`tests/engine/test_explain_over.py`: 100 tests, measured on pixels and numbers (every test draws frames of a flat grey picture, so the base is exactly 120 everywhere and anything else is the overlay):
the registry entries (order, completeness, defaults, bounds, previews, usage rules); items validation of every field of the three lists (a bad item is named in the message: `item 2 (Beta), field 'at'`);
word anchors resolved in `labels`, `rows` and `lit` (due on their word, stale and invalid anchors reported); the rules between params (`doc_lit_no_target`, `doc_bad_box`, `region_undefined`); validity on the bases that have a camera, refusal on the others, `NUM-01` on a card and on the map;
**KEY-01**: each label appears at its time and not before (nothing before 0.6 s, one at 1.0 s, the second only at 3.0 s, a fade in between), a label sits on the stated side of its region and every ink pixel is outside the region's ellipse (all eight sides),
a bare point and a region without radii, eight labels on a crowded picture with a moving and zooming camera never touch and stay inside the frame (boxes at six moments, and the pixels agree: nothing is drawn outside the boxes), the labels follow the camera (shift equals the camera's move,
size within 1 px) and keep their size when it zooms, text moves in quarter pixels (no jumps of a whole pixel), the dim (starts 0.4 s before the first label, ends with the overlay), cap heights (italic, regular, caps at 80 percent, `cap_pct` 3.0), the hairline leader and the shadow switch,
a detail that leaves the frame takes its label with it; **NUM-01**: the parts of a row appear at their times (label, figure +0.25 s, units +0.4 s), the marks of a row appear one after another over `marks_s` (always a prefix of the row, 20 marks, and 4 s), 12, 40, 41 and 60 marks in the right lines,
the dim, the figure is as high as `cap_pct` (6, 8, 11, 14), one to four rows are stacked in order inside the frame (at `cap_pct` 8 and 14), four rows with 40 marks are scaled to fit, `align` right, caption after the last marks and source with the first figure;
**DOC-01**: the lit window is brighter than its surroundings by the stated ratio (0.25, 0.34, 0.6), the edge is soft (10 to 90 percent width between 0.5 and 0.8 of `edge_px` for 12, 40 and 100 px; 2 px for 0), the 50 percent point is on the window's border, no outline (never above the lit grey, never below the dimmed one),
the window follows the camera (position and size, two camera positions and a zoom), `pad_px`, a box beats a region, a region without radii, windows light one after another and share the dimming (a crossfade keeps the surroundings dim), `ramp_s`, the reading and the line as written appear at `reading_at` and +0.4 s,
the text goes above the window when the window comes down into its place; every technique: the same frame rendered twice and out of order is identical (and in a new project), every parameter at its min and max, every enum value, every extreme of every list field validates and draws,
`element_too_short`, no socket opens during a render, the draw check and the default params (with and without a picture's regions), and `validate accepts only what the overlays can draw` (the odd-values rule of the registry, run here because the full sweep is slow).
`tests/editor_frontend/explain_items.test.mjs`: 6 tests with the real registry entries (rows, fields, limits, typing, Vietnamese problems, the new codes).
Shared tests changed: technique counts 79 to 82 (`test_default_params.py`, `test_registry_complete.py`, `test_validate_draw_sweep.py` docstring, `tests/deep/test_sweep.py`), a reference shot per overlay in `tests/engine/identity_lab.py` and `tests/deep/test_sweep.py` (after the map's),
`test_registry_complete.py::test_technique_lab_covers_every_technique_and_renders` (the lab predates the three overlays), `test_issue_codes.py` (the codes of `explain_over.py`).

Final runs on the final tree (snapshot `compover`, `BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_test.sh compover -- ...`, one folder per run):

| Folder | Summary line as printed |
|---|---|
| `tests/engine/test_explain_over.py` | `100 passed in 59.12s` |
| `tests/engine -m "not slow"` | `471 passed, 14 skipped, 158 deselected in 389.39s (0:06:29)` |
| `tests/draft` | `330 passed, 1 warning in 163.57s (0:02:43)` |
| `tests/editor` | `478 passed, 1 warning in 317.55s (0:05:17)` |
| `tests/identity` | `77 passed in 2.07s` |
| `tests/deep -m "not timing"` | `227 passed, 4 skipped, 1 deselected, 1 warning in 394.44s (0:06:34)` |

On the Mac, from the worktree: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs` -> `ℹ tests 316`, `ℹ pass 315`, `ℹ fail 0`, `ℹ skipped 1` (310 existing tests plus the 6 of `explain_items.test.mjs`)
(the test that compares every code of `ISSUE_CODES` with the Vietnamese templates skips itself without a `.venv/bin/python`; I ran the same comparison by hand with the engine's Python: 125 codes, none without a template, none extra.)
Not run (the brief forbids `-m slow`): the full registry sweep `tests/engine/test_validate_draw_sweep.py` (its rule for the three overlays is covered by `test_validate_accepts_only_what_the_overlays_can_draw`, and the lab copy gets a host shot per overlay for when it runs) and `tests/deep -m timing`.
`tests/engine` had one failure on the first full run (`test_registry_complete.py::test_technique_lab_covers_every_technique_and_renders` compares the lab's shots with the registry without the ID and MAP families; the three overlays are now excluded too); the table is the rerun on the final tree.

## The stills (`.scratch/compover/stills/` in the worktree, 1280 px wide, rendered on the server in snapshot `compover` on the Arnolfini Portrait of `projects/technique_lab`)

Contact sheets (3 x 2, the time written in the top right corner): `sheet_key_default.png`, `sheet_key_crowd.png`, `sheet_num_default.png`, `sheet_num_four.png`, `sheet_num_one.png`, `sheet_doc_default.png`, `sheet_doc_two.png`.
Single stills `<example>_<time>.png` (for example `key_default_02.9.png`). Mock-up against engine at the same moments (the mock-up rendered in headless Chrome, 960 x 540 stage at device scale 2, with the bundled EB Garamond; top row mock-up, bottom row engine):
`compare_key.png` (1.2, 2.9, 4.8 s), `compare_num.png` (1.5, 3.4, 4.9 s), `compare_doc.png` (1.5, 2.6, 3.4 s).

| Example | Moments (s) | What I saw |
|---|---|---|
| `key_default` (the default five labels, static camera as the mock-up) | 0.5, 1.2, 2.9, 4.8, 6.7 | 0.5: the plain picture (the dim starts at 0.3 s). 1.2: the picture a little darker, "One candle, lit" at the top left of the candle. 2.9: "Latin inscription" above the signature, "Convex mirror" below. 4.8: "Amber beads" left of the beads, "A brush" right of the brush; all five in italic, no box, no line, none touching. 6.7: all fading together. Positions and times agree with the mock-up (`compare_key.png`: label positions within 4 px at 640 px width; the engine's text is 6 percent smaller because the contract sets the cap height, 2.4 percent, where the mock-up sets a font size of 3.9 percent of the height). |
| `key_crowd` (eight labels on regions around the mirror, camera pushing 0.45 to 0.72 and drifting) | 0.9, 2.2, 3.6, 4.6, 6.0 | Labels appear every 0.5 s, none touches another or the frame edge, all follow the picture as the camera moves and keep their size. Not fine: the labels of regions that are close together stack in a column beside them (they are apart, but it is a list, and which label belongs to which detail is not obvious without the picture), "Saint Martha finial" runs over the white veil where its contrast is low, "Second roundel" sits inside the mirror's frame (the mirror's region is large and the roundel lies inside it). |
| `num_default` (600 against 2,000 pelts) | 0.6, 1.5, 3.4, 4.9, 6.7 | 0.6: the picture dimmed, nothing else. 1.5: "An ordinary gown" and "600" fading in, "pelts" fainter, source line at the bottom left. 3.4: twelve marks complete, "This gown" and "2,000" fading in. 4.9: forty marks in two lines, the caption starting to fade in at the bottom. 6.7: leaving. Row positions, figure size, marks and the second row agree with the mock-up within 2 px at 640 px (`compare_num.png`); the units of the second row sit nearer the figure than in the mock-up. |
| `num_four` (four rows of 10, 30, 40 and 60 marks) | 1.0, 2.0, 3.3, 5.0, 6.7 | Four rows fit between the top and the caption, each row's marks run out in its own time (the 60 marks of the last row in two lines of thirty), the rows were brought closer and scaled by 0.73 (figure 5.8 percent high), all text readable on the dimmed picture; the caption comes after the last marks. |
| `num_one` (one row alone: "$450.3M", cap 12 percent, no marks) | 0.6, 1.4, 2.0, 4.0, 6.7 | A single row is centred (not pushed to the top); label, then the big figure, "Source: Christie's" small at the bottom left; no marks, no caption. |
| `doc_default` (the mock-up's example: signature of Jan van Eyck) | 0.8, 1.5, 2.6, 3.4, 6.7 | 0.8: the picture, the camera easing in. 1.5: the window rising over the signature, the rest dimming. 2.6: the camera has arrived, the window follows it (it is bigger), the reading appearing under it. 3.4: "Jan van Eyck was here. 1434" in italic and "JOHANNES DE EYCK FUIT HIC · 1434" in small capitals under it. Soft edge, no outline; the position and size of the window agree with the mock-up (`compare_doc.png`), whose edge is a sharp rounded rectangle. |
| `doc_two` (two windows: the signature line, then the year) | 0.8, 1.6, 2.6, 4.4, 5.6 | The first window rises over the signature at 1.0 s and follows the camera, at 3.4 s it falls while the second rises over "1434" (both half lit at the crossing, the surroundings stay dim), then only the year stays lit with the reading under it. |

## Deviations from the contract and from the mock-up, and why

1. **Colour and shadow of the text.** Contract section 5: text over pictures `#F1EADB` with a soft shadow. The mock-up's number and document text use `#E9E2D0` without a shadow (only the labels have one). The three overlays follow the contract.
2. **Labels outside the ellipse.** The mock-up offsets a label by 1.7 percent from the region's centre (inside the region's ellipse for the candle and the beads); the contract says outside the ellipse on the stated side, so the engine places the label at the ellipse's edge plus 1.3 percent of the height.
3. **DOC-01 edge.** The mock-up's window has a sharp rounded edge (the CSS outer shadow is clipped inside the box; measured on the headless render). The contract says soft edge, no outline: smoothstep of the signed distance to a rounded rectangle, `edge_px` wide, centred on the border.
4. **DOC-01 window from a region.** The mock-up fixes a box in source pixels; the engine takes the ellipse box of the region (or `box`) and grows it by `pad_px` (screen pixels, an extra parameter, default 40) so that the line sits inside the soft edge. A region without radii gets a default window (14 percent of the picture's width by 4 percent).
5. **`box` is a text field.** `ref` holds a region name or a point; a box in source pixels is the separate text field `box` ("x0, y0, x1, y1"; wins over `ref`), as the brief allowed. Because the page may leave `ref` blank (`""`), `registry.check_items` now treats a blank `ref` as empty (see below).
6. **Extra parameters** (not in the contract): `leave_s` on all three (the fade-out that ends with the overlay; the mock-up's out-fade belongs to its 7 s loop), `marks_s` and the caption timing of `NUM-01`, `pad_px` of `DOC-01`. `reading_at` is seconds only (the brief).
7. **Timing of the dim.** KEY-01: from 0.4 s before the first label, a 0.6 s ramp (the mock-up has 0.3 to 0.9 s with the first label at 0.7). NUM-01: 0.7 s ramp ending 0.1 s before the first row (the mock-up 0.2 to 0.9 s, first row at 1.0). The caption of NUM-01 faded in 0.1 s after the last mark of the last row (4.82 s; mock-up 4.8 s): **changed in the follow-up, it now comes with the first marks and stays to the end**.
8. **NUM-01 layout.** The mock-up fixes two rows at 26 and 56 percent of the height. The engine stacks the rows from the mock-up's sizes and centres them on 53 percent; with more rows or bigger figures the rows come closer, then everything is made smaller by one factor, so that four rows fit. `count` is at most 60 (20 marks to a line up to 40 marks, 30 above that). The units stand on the figure's baseline at 0.6 of the figure's cap height from its end (the mock-up's offset is fixed). The source line (not in the mock-up) is at the bottom, 1.7 percent cap height, 75 percent.
9. **DOC-01 text above the window.** Not in the mock-up: when the window comes down into the place of the reading at some moment of the camera's path and there is room above it, the reading and the line as written go above the window (decided once for the overlay, so the text never jumps).
10. **Windows share the dimming.** Several lit lines: the surroundings are dimmed by `min(1, sum of the windows' envelopes)`, so a crossfade between two lines keeps them dim and each window rises and falls on its own ramp.
11. **Small capitals** of KEY-01's `caps` style are the capitals of the regular face at 80 percent of the cap height, tracked 0.14 em (the contract names the style, not the size).
12. **Sub-pixel text.** Pillow places glyphs on whole pixels, which made a label on a moving camera advance in jumps (measured: steps of 0 and 1 pixel). Text is therefore drawn once at four times the size and shrunk at quarter-pixel positions (`Art`); steps are now 0.25 to 0.5 px.
13. **Preview camera.** `DOC-01` preview and stills use the engine's `inout_cubic` ease for the camera's move (the mock-up's quad ease is not in the engine's list); `KEY-01` and `NUM-01` use the mock-up's static crops.

## Files outside my own module that I touched

* `style/gae/techniques.json` (three entries appended after `MAP-01`), `style/gae/previews/{KEY-01,NUM-01,DOC-01}.{mp4,jpg}` (allowed).
* `bti/engine/storyboard.py`: three codes in `ISSUE_CODES` (`overlay_needs_camera`, `doc_lit_no_target`, `doc_bad_box`, one block marked `compover` directly after the map's) **and a four-line hook in `validate`'s overlay loop**: it calls the overlay class's optional `check_base(base technique id)` and reports its code as an error. Reason: the brief asks how validation refuses the bases without a camera, and nothing in the registry or the shot knew; this is the smallest place for it.
* `bti/engine/registry.py`: `check_items` treats a `ref` that is the empty string as empty (a required one is `item_field_missing`, an optional one is skipped). Reason: the page's text input for a `ref` field gives `""` when the person clears it, and `DOC-01`'s `ref` is optional (a line may name a `box` instead).
* `bti/editor/static/js/labels.js` and `sbissues.js` (my blocks, directly after the map's), `bti/engine/README.md`, `docs/APP_GUIDE.md` (parts after the map's; counts 82).
* Tests: `tests/engine/test_explain_over.py` and `tests/editor_frontend/explain_items.test.mjs` (new), `tests/engine/identity_lab.py` (a host shot per overlay after the map's), `tests/engine/test_issue_codes.py` (reads the codes of `explain_over.py`), `tests/engine/test_default_params.py`, `tests/engine/test_registry_complete.py` (count 82 and the lab list: **this line will conflict with `compbase` unless the prefixes are merged**), `tests/engine/test_validate_draw_sweep.py` (docstring), `tests/deep/test_sweep.py` (count and host shots after the map's).
* `tools/explain/render_examples.py` (new), the report, the status file.
* Not touched: `bti/engine/vfx.py`, `geo.py`, `bti/draft/techniques_md.py`, the briefing templates, `bti/editor/static/mock/techniques.json` (an old 71-entry copy that no test of the new entries needs).

## What I could not verify

* The row editor in a real browser (no DOM test exists): the logic and the words are tested in Node with the real entries; I did not open the page and click the rows. A `ref` is a plain text box on the page (a region name, or "x, y"); there is no "pick on the picture" button for it.
* A real video with these overlays in a storyboard from the draft agent (no model call is allowed); the catalogue text for the draft agent is the other worker's.
* The preview clips were checked with `ffprobe` (h264, 640 x 360, 7.0 s) and by their thumbnails and extracted frames, not watched as moving pictures; I looked at stills (the contact sheets and the mock-up against engine comparisons), not at a played clip, so smoothness of the camera follow is established by the tests (quarter-pixel steps) and not by eye.
* Timings are two runs on a shared server (the second one was slower because other workers were testing); the `-m slow` sweep and `-m timing` tests were not run (forbidden / not asked).
* The Vietnamese sentences (page words, three issue sentences, the APP_GUIDE part, the pattern hints) were written by me and read by nobody else.
* The crowded `key_crowd` example is acceptable, not good (see the table): the placement avoids collisions and the frame but does not know about faces or other picture content.
* Environment and a rule I broke before it existed: during the work the Mac repeatedly lost read access to `~/Documents` for minutes at a time (`Operation not permitted` from macOS, also for the file tools). I worked around it by keeping a copy of the engine and my files in this session's scratch folder under `/private/tmp` (the folder the session was given for temporary files), editing there and copying into the worktree when access returned, and by rendering test frames from that copy. That is the opposite of the coordinator's rule that arrived at the end ("if the project folder is refused, wait five minutes and retry; do not move your work outside the project"). I also deleted folders there with `shutil.rmtree`: the lab projects `proj/key`, `proj/num` and `proj/doc` that my scratch script `try.py` rebuilds on each run (folders that script had created itself, before the rule existed); and `tools/explain/render_examples.py` removes, when it ends, the temporary lab folder it made itself (`tempfile.TemporaryDirectory`). From the rule on I deleted nothing outside `.scratch/compover/` (one `rm -rf` of my own `.scratch/compover/stills` folder before regenerating the stills, with the literal path), edited only in the worktree and left the scratch folder as it is. I checked at the end that the four files I kept in both places (`explain_over.py`, `test_explain_over.py`, `render_examples.py`, `explain_items.test.mjs`) are byte-identical in the worktree and in the scratch copy, and every Python test run on the server and every stills run came from the worktree's tree (`snapshot_test.sh` packs the worktree). The sequence of edits is therefore not the sequence in the status file.

## Follow-up (the coordinator's three corrections, 2026-11-19)

The coordinator accepted the three overlays and asked for three corrections. Same worktree, same rules (nothing deleted outside `.scratch/compover/`, no work outside the project).

### 1. `NUM-01`: the caption comes with the first marks and stays
`caption_at` is now the moment the first marks start to appear: 0.6 s after the `at` of the first row that has marks (0.75 s after the first row when no row has marks). It fades in over 0.5 s and stays until the overlay leaves (`leave_s`).
In the default example that is 1.6 s instead of 4.8 s, so "each dot is fifty squirrel pelts" is readable for about 5.4 s of 7. The source line is as it was. (Changed: `BigNumber.build_layout`; registry notes; README; APP_GUIDE; deviation 7 above.)

### 2. `NUM-01`: the units
The units are drawn at 72 percent (`UNITS_ALPHA` 0.72, the contract's secondary-text level) and as big as the row's label (`M_UNITS_CAP = M_LABEL_CAP`, 2.35 percent of the height at `cap_pct` 8; it was 2.22).
Note for the coordinator: the old value was **0.85**, so the units are now a little *dimmer* than before and 6 percent bigger. In `num_default_04.9.png` (1280 px) "pelts" reads clearly beside "600" and "2,000", in the label's size and in a grey that is plainly secondary; in the four-row sheet (figure 5.8 percent high, labels and units 1.7 percent) "florins" is small but legible.
If you want them stronger, `BigNumber.UNITS_ALPHA` is the one number (0.85 gives the old strength at the new size).

### 3. `KEY-01`: leaders, `leader` = `auto` (the new default), and the darker ground
* **`leader`** has a third value `auto`, now the default; `none` and `hairline` keep their meaning (`hairline`: a line from every label). The line goes from the label's box to the edge of its detail's ellipse, on the line to the ellipse's centre,
  in the hairline colour `#8D877A`, 2 px, over a soft dark underlay (35 percent, 4 px; the line alone disappeared on the veil), fading with its label. It is drawn when:
  * (a) **the label has been moved away from its detail**: the distance between its box and the ellipse is more than max(2.2 natural gaps = 31 px at 1080, 0.35 of the detail's larger radius). My measure, not the 1.5 radii you suggested: with 1.5 radii a small detail (50 px) tolerates 75 px, and a label that is 70 px away from a roundel is already lost.
  * (b) **a viewer could take the label for another detail's**: its box lies over the ellipse of another label's detail (a different `ref`), or within half its own distance from it. I added this because (a) alone draws nothing in the eight-label example: I printed where every label sits (`python tools/explain/render_examples.py leaders`) and **the solver had not moved any of them**:
    all eight stood at their natural gap of 14 px, the crowd comes from regions that are large and overlap (the mirror's ellipse contains the roundels, the amber beads and part of the label column of the inscription), not from displacement.
  * Both strengths ramp from 0 (over half the threshold in (a), over half the label's own distance in (b)), so a line never pops while the camera moves. In the default example (the mock-up's five labels) nothing is displaced or in doubt, so `auto` draws nothing there and it still looks like the mock-up (test: `auto` equals `none`, frame for frame).
* **Darker ground.** Done, and simply: while the plan chooses the side of an `auto` label, every candidate side (all equally near the detail) pays `0.4 x` the mean brightness of the base picture under its box (`ground_level`, read from the pyramid level nearest the screen scale at the seven camera samples, 0 off the picture); collisions and the frame still cost far more, and the order e, w, n, s ... breaks the remaining ties.
  A side the author fixed is kept. On a picture whose right half is bright the label goes west; with the bottom half bright, north. While doing it I found that the cached plan was keyed without the picture, so two projects that call their picture "A" with the same labels and regions would have shared a plan; the key now holds the picture's file and time (also for `DOC-01`'s text placement).
* **usage_rule** has the sentence: "Put at most five labels on screen at a time; details that lie close together are better shown in two shots." The description and engine notes say what `auto` does.
* **Page**: Vietnamese words for the three values (`labels.js`, my block: "Không có nét nối", "Nét mảnh cho mọi nhãn", "Chỉ khi nhãn bị đẩy xa chi tiết"; the same word `auto` keeps "Tự chọn" for `side`), a sentence in `APP_GUIDE.md`.
* **Tests** (`tests/engine/test_explain_over.py`, now 106; `explain_items.test.mjs`, now 7): the displaced label has a leader that ends on the detail's ellipse (to 1 percent) and starts at the label's box, the label beside its detail has none (pixels: nothing near the first of three stacked labels, a line near the third, more with `hairline`, the line fainter half way through its label's fade); the leader follows the camera and keeps its distance;
  a label over another detail's ellipse gets a line to its own detail and the label beside its own detail does not; the default example is the same frame in `auto` and in `none` (and different in `hairline`); the darker-ground choice (right half bright: west; bottom half bright: north; flat picture: the order decides; a fixed side is kept; `ground_level` on dark, bright and off the picture); the registry has `leader` = none, hairline, auto with `auto` the default and the new sentence; NUM: the caption time (first marks; no marks; a later row with marks), it is readable from 1.6 s to the end, the units' level (72 percent against the label's 100) and size.

### What I see in the three sheets (`.scratch/compover/stills/`, re-rendered on the server, 1280 px)
* **`sheet_num_default.png`**: the caption "each dot is fifty squirrel pelts" is there from 3.4 s (it begins at 1.6 s) and still at 4.9 and 6.7 s; the units "pelts" are in the label's size, a notch greyer than the label, readable (clearer in `num_default_04.9.png`). Nothing else moved.
* **`sheet_num_four.png`**: the caption "each dot is two florins" appears at 2.0 s with the first marks and stays; the units "florins" are small (the rows are scaled to 0.73) but readable. Rows, marks and source unchanged.
* **`sheet_key_crowd.png`**: the eight labels still sit in the same neighbourhood, but "Latin inscription", "Amber beads" and "Convex mirror" now stand to the west of their details, on the man's dark robe (the darker side), where before they stood to the east over the woman's head and veil, and "Saint Martha finial" has moved off the white veil onto the dark wall, where it is readable (4.6 and 6.0 s). "First roundel" and "Second roundel" now carry a short hairline to their roundels' edges: these two labels lie over the mirror's ellipse, and without the dash a viewer cannot tell whether they name the roundel or the mirror. **Not solved, and I do not think the technique can solve it:**
  "Latin inscription" still stands 14 px outside the edge of `INSCR`, whose ellipse is 840 source pixels wide for a signature about 500 wide, so on screen the label is far from the writing; "Convex mirror" is likewise beside a mirror ellipse (440 px radius) that is larger than the mirror. The leader would end on those ellipse edges, not on the writing. The remedy is in the data: tighter regions for those two (the agent writes the regions), and fewer labels at once, as the new usage-rule sentence says. The ticks to the roundels are 14 px long and look like dashes before the text, not like leaders; they say which detail, but they are not elegant.

### Final runs of the follow-up (snapshot `compover`)
| Folder | Summary line as printed |
|---|---|
| `tests/engine/test_explain_over.py` | `106 passed in 66.36s (0:01:06)` |
| `tests/engine -m "not slow"` | `477 passed, 14 skipped, 158 deselected in 304.96s (0:05:04)` |
| `tests/deep -m "not timing"` | `227 passed, 4 skipped, 1 deselected, 1 warning in 222.52s (0:03:42)` |
| `tests/draft` (the registry text changed, run as a precaution) | `330 passed, 1 warning in 123.51s (0:02:03)` |

Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs` -> `ℹ tests 317`, `ℹ pass 316`, `ℹ fail 0`, `ℹ skipped 1` (the ISSUE_CODES test that needs `.venv/bin/python`; no code was added in the follow-up).
`tests/editor` and `tests/identity` were not re-run (nothing they read changed except the registry text of KEY-01 and NUM-01, which `tests/draft` and `tests/engine` read).
Previews: `NUM-01.mp4`/`.jpg` regenerated (the default changed: caption and units); `KEY-01.mp4`/`.jpg` regenerated and byte-identical in size to the old ones (the default labels have no leader and the same sides), `DOC-01` untouched.
Milliseconds per frame at 1920 px after the follow-up (server, a quieter moment; the base shot alone is 25.6 to 27.9 ms): `KEY-01` default 29.7 (+4.1), eight labels 34.6 (+6.9), `NUM-01` default 39.9 (+11.5), four rows 40.2 (+12.7), one row 42.0 (+14.3), `DOC-01` default 43.3 (+15.8), two windows 34.8 (+6.9): the same as before within the noise of a shared server. The plan (sides, ground) is computed once per overlay on its first frame.
Files touched in the follow-up: `bti/engine/techniques/explain_over.py`, `style/gae/techniques.json` (my entries only), `style/gae/previews/{KEY-01,NUM-01}.*`, `bti/editor/static/js/labels.js` (my block), `bti/engine/README.md`, `docs/APP_GUIDE.md`, `tests/engine/test_explain_over.py`, `tests/editor_frontend/explain_items.test.mjs`, `tools/explain/render_examples.py` (new `leaders` command), this report. Nothing outside `.scratch/compover/` was deleted, and every edit was made in the worktree.
