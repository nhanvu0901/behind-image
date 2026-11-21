# FIX: the list-of-items parameter type, the geography bundle and the atlas map `MAP-01` (worker `mapbuild`, 2026-11-18)

Brief: `.scratch/agy_tasks/mapbuild/TASK.md`. Contract: `docs/design/2026-11-18-explainer-components.md` (sections 2, 3, 4 `MAP-01`, 5, 6, 7).
Approved mock-up: `docs/design/mock/2026-11-18-explainer/components.html`, function `plate`.

## What was built, per point of the brief

### 1. The `items` parameter type
* `style/gae/techniques.schema.json`: type `items`, the `fields` array (name, type, required, default, min, max, unit, values, pattern, pattern_hint), `min_items`/`max_items` for it,
  the id pattern widened for the new families (`MAP|KEY|TIME|NUM|TREE|STATE|DOC-nn`).
* `bti/engine/registry.py`: `check_items` / `check_field` (the first problem of the first bad item, naming item and field), `fill_items` (defaults and one-line text, used by
  `merged_params`), `items_at_fields`, `at_seconds`, `item_label`, and a per-technique hook `check_params(params)` that `validate_params` calls over the merged params once the per-param
  checks pass (rules between params).
* `bti/engine/storyboard.py`: `resolve` resolves word anchors in `at` fields of items for shots and overlays the way a camera key's `at` is resolved (`_resolve_item_anchors`);
  `validate` reports `item_anchor_invalid` / `item_anchor_stale` (`check_item_anchors`) and checks `ref` fields of items against the asset's regions; 18 new issue codes in
  `ISSUE_CODES`; `element_too_short` now holds for the families `ID-`, `MAP-`, `KEY-`, `TIME-`, `NUM-`, `TREE-`, `STATE-`, `DOC-` (`ELEMENT_FLOOR_FAMILIES`); `check_shape` no longer
  calls a number `at` inside a record a corrupt file.
* Page: `bti/editor/static/js/formgen.js` (pure row logic and the Vietnamese problem sentences), `formui.js` (the row editor: one input per field, add, remove, up, down; a time field
  offers seconds or "= đầu phát" for the word at the playhead), `sbissues.js` (a Vietnamese sentence for every new code, and `element_too_short` for the new families), `labels.js` (block
  `mapbuild`: words of the choices and of the rows), `bti/editor/static/css/edit.css` (rows). Every other type's form is unchanged.
* `bti/draft/techniques_md.py`: the catalogue now prints the fields of an `items` param (it printed only `places:items`).

### 2. The geography bundle `style/gae/geo/` and `tools/geo/build_bundle.py`
See "The bundle" below and `style/gae/geo/README.md`.

### 3. `MAP-01`
`bti/engine/techniques/maps.py` (renderer), `bti/engine/geo.py` (Web Mercator views, `fit`, the bundle loader), the registry entry in `style/gae/techniques.json` (label_vi, description,
usage_rule that says it replaces `STATIC-06`, `AN-04`, `X-ANN-05` for new work, 22 params with defaults and bounds, timing 8 / 3 / 30 s, engine block, evidence),
`style/gae/previews/MAP-01.mp4` (640 px, 15 fps, 8 s) and `.jpg` (480 px, at 5.6 s), `tools/geo/render_map_examples.py` (stills, timings, the preview).

### 4. Tests
`tests/engine/test_map.py` (67 tests: bundle files against README hashes, projection and `fit` against the worked numbers of R10, land and sea pixels at known coordinates in both presets,
marks and labels at their times, word anchors, route growth and head, label placement against the route in the example, region tint, sea names, purity and seeded grain, every param at
its bounds, the odd-value sweep for MAP-01, no socket during a render, items validation for every field type, rules between params, `element_too_short` for the new families),
`tests/editor_frontend/items.test.mjs` (8 tests: the row editor's logic and the sentences). Counts of 78 became 79 in `test_default_params.py`, `test_registry_complete.py`,
`tests/deep/test_sweep.py` (which also gets a MAP-01 reference shot in its lab copy), `identity_lab.py` (one MAP-01 shot for the sweeps), `test_validate_draw_sweep.py` (the type `items` and its odd values),
`test_issue_codes.py` (the `map_*` codes live in the renderer's hook).

### 5. Docs
`bti/engine/README.md` (the `items` type, the map module, the bundle), `docs/APP_GUIDE.md` (one part in Vietnamese: the map, its data, the two sea colours; the count of techniques), this report.

## The bundle (`style/gae/geo/`, 2,036,798 bytes in all; the limit was 6 MB)

Downloaded 2026-11-18 from Natural Earth's own distribution (naciscdn.org, `curl` with the client name `geo-bundle-builder/1.0`, no other request header, nothing about the owner). No download was refused.
Terms of use (https://www.naturalearthdata.com/about/terms-of-use/): "All versions of Natural Earth raster + vector map data found on this website are in the public domain. [...]
No permission is needed to use Natural Earth. Crediting the authors is unnecessary."

| Download | Natural Earth version | Bytes | sha256 |
|---|---|---|---|
| `ne_10m_land.zip` (https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip) | 5.1.1 | 3,269,070 | `e547d749445eaa0964aba76738090ec88f5e63c4585122170f98c67a7ea922dc` |
| `ne_50m_land.zip` (.../50m/physical/ne_50m_land.zip) | 4.1.0 | 457,183 | `0b8e670cf80dce9cbebe2a193bc44ba5602758c22e1fa603980553646d7ff162` |
| `ne_50m_admin_0_countries.zip` (.../50m/cultural/...) | 5.1.1 | 799,734 | `5fed433373581fa648920435f937d95f2d3c0200e067409c6478dcdf1b853139` |
| `ne_50m_geography_marine_polys.zip` (.../50m/physical/...) | 5.1.0 | 700,610 | `9e460b9fe2566d3f466d69096348953f5348bab63ce1328c94c3072b9f48eef1` |

| Stored file | Bytes | sha256 | Content |
|---|---|---|---|
| `land_50m.npz` | 254,697 | `c933b25e8c1e7287ec6d9df5ac22e957b67c7504d9b8389f3f22b7ef59296236` | 1,422 rings, 59,239 vertices |
| `land_10m.npz` | 1,359,537 | `798ee3bdedb8824656259fdb466a4da577e1802b1ffb632b2afb411e5e8da2b0` | 6,838 rings, 439,317 vertices |
| `countries_50m.npz` | 413,130 | `20917462d9b4962db93cc1710e3d25c700ef793af4ca2d239e8c3f5fe6ed0eb2` | 1,629 rings, 97,832 vertices, 237 countries with ISO alpha-2 codes |
| `seas.json` | 9,434 | `caaf894813eb2716c00a9effe876a9e982c08b37af0b41b75b3c914b8aa66857` | 113 sea and ocean names with positions |
| `manifest.json`, `README.md` | 1,974; 5,484 | | the same numbers; sources, licence, format |

`tools/geo/build_bundle.py --downloads DIR [--fetch]` rebuilds it (numpy, OpenCV and the standard library only) and gives byte-identical files (checked: two builds, same hashes). A test compares every file with
the manifest and the README.

## Milliseconds per frame (Windows server, snapshot `mapbuild`, 1920 px, warm, 39 frames spread over each example; `tools/geo/render_map_examples.py timing`)

| Example | first frame (cold, includes loading the bundle, the grain and the fonts) | median | mean | p90 | max | the map itself (land, sea, lines) |
|---|---|---|---|---|---|---|
| default, blue-grey (Bruges to Lucca) | 269 ms | **59.2** | 60.3 | 63.5 | 64.8 | 36.8 |
| default, sepia | 59 ms | 61.6 | 62.2 | 64.9 | 66.1 | 36.4 |
| Oslo (1:10m, smoothed outlines) | 79 ms | 43.9 | 44.8 | 47.9 | 48.7 | 26.8 |
| Venice to Constantinople | 54 ms | 56.5 | 56.2 | 57.6 | 58.8 | 35.7 |

For comparison, the same measure on the server for other base techniques of `projects/technique_lab` (median of 14 frames at 1920 px): `X-CARD-01` 11.7 ms, `STATIC-06` 19.6, `SHORT-01` 22.7, `DIA-01` 25.4,
`CAM-01` 27.3, `CMP-01` 31.4, `LAY-03` 35.9, `LAY-01` 36.7, `FOOT-01` 42.3, `STATIC-01` 43.9, `CMP-03` 58.4, `CAM-05` 60.8. `MAP-01` is inside that range.

## Tests (snapshot `mapbuild` on the server, final tree)

| Folder (one per run, `BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_test.sh mapbuild -- ...`) | Summary line as printed |
|---|---|
| `tests/engine -m "not slow"` | `371 passed, 14 skipped, 152 deselected in 206.43s (0:03:26)` |
| `tests/draft` | `330 passed, 1 warning in 121.15s (0:02:01)` |
| `tests/editor` | `478 passed, 1 warning in 206.90s (0:03:26)` |
| `tests/identity` | `77 passed in 0.94s` |
| `tests/deep -m "not timing"` | `224 passed, 4 skipped, 1 deselected, 1 warning in 214.24s (0:03:34)` |

An earlier run of `tests/engine` failed once (`test_round3_engine.py::test_wrong_types_inside_are_a_data_error_never_an_attribute_error[camera-key-at-string]`): I had loosened `check_shape` so that any `at` that is not a list or a boolean passed; a string `at` in a camera key must stay a data error, so now only a number is let through (a time in seconds inside an `items` record). The table above is the rerun on the final tree.

On the Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs` -> `ℹ tests 310`, `ℹ pass 310`, `ℹ fail 0` (302 existing tests and the 8 of `items.test.mjs`).
Not run, because the brief forbids `-m slow`: the full validate/draw sweep of all 79 techniques (`tests/engine/test_validate_draw_sweep.py`, marked slow). Its MAP-01 row is covered by
`test_validate_accepts_only_what_the_map_can_draw` in `tests/engine/test_map.py` (the same odd values, not slow: no value that `validate` accepts failed to draw). `tests/deep` `-m timing` was not run either (the brief says
`-m "not timing"`).

## The stills (`.scratch/mapbuild/stills/`, 1280 px wide, rendered by the server)

Contact sheets (3 x 2, labelled with the time): `sheet_default.png`, `sheet_sepia.png`, `sheet_oslo.png`, `sheet_venice.png`. Single stills: `default_00.3.png`, `default_01.4.png`, `default_02.6.png`, `default_04.2.png`,
`default_06.4.png`, `default_07.6.png` (and the same six `sepia_*.png`), `oslo_00.2.png` ... `oslo_07.0.png`, `venice_00.4.png` ... `venice_08.0.png`.
Besides looking, I compared the engine with the approved mock-up as the mock-up runs in headless Chrome (a 960 x 540 stage at device scale 2, i.e. the size the owner saw, with the bundled EB Garamond):
land colour within 1 level of the mock-up after calibrating the paper grain on it (mean 212.1 against 212.8 in the blue channel, noise 4.0 against 3.4), the same coast, water lines and shade pixel for pixel at 4.2 s, the same
marks, label sizes, route dots (spacing 22.5 px at that time) and head; the first comparison found a grain that was twice too strong, a coastline and graticule that were too thin (the mock-up's non-scaling strokes are
in CSS pixels of a 540 px stage) and sea names that were missing; all three were fixed.

What I saw in the final stills:
* **Default example, blue-grey.** 0.3 s: the wide plate (3,800 km), land cream and sea blue-grey clearly apart, the sea darker toward the coast with a flat strip and two pale water lines along it, a firm ink coastline, graticule, three sea names (NORTH SEA, BAY OF BISCAY,
  MEDITERRANEAN SEA, as in the mock-up), nothing marked, Belgium not tinted. 1.4 s: Belgium tinted with its outline and name, the Bruges mark and its italic label (north-east of the mark). 2.6 s: Lucca fading in (mark first, label 0.2 s later, south-east of the mark), the camera already pushed in.
  4.2 s: the dotted route half drawn with its head and halo, ends on the head, nothing beyond it; Bruges label cleared of the coast clutter by its halo. 6.4 s and 7.6 s are identical (end view, route complete, head gone): the map holds, as in the mock-up (which then fades to black; see the deviations).
* **Sepia.** The same frames; the brown sea is clearly darker than the pale land, the water lines and shade are as in the mock-up's sepia preset.
* **Oslo, Ekeberg, 240 km to 60 km wide.** A different place, a single mark with its label (south-east), graticule every 0.25 degree, no route, no region, no sea name (none is in view). The 1:10m outline of the Oslofjord is coarse at this scale: its corners are cut so it reads as a coast,
  but it has no more detail than the data has (the fjord head and two arms, no islands).
* **Venice to Constantinople, 4,200 km to the view fitted to both places and the route's bends.** Two marks with labels on the side that is clear of the route (Venice north-east, Constantinople east, over the Black Sea), a dotted sea route down the Adriatic, round the Peloponnese and up the Aegean with its head, sea names
  that avoid the route and the labels (MEDITERRANEAN SEA, BLACK SEA, TYRRHENIAN SEA when in view).
* Not fine: MEDITERRANEAN SEA crosses Sardinia and Corsica at the start (as in the mock-up); the Oslo outline is coarse; the route in the Venice example passes close to the Greek coast because the `via` points are a rough sea route.

## Deviations from the contract and from the mock-up, and why

1. **The coastline is not stored apart.** The brief says "land and coastline at 1:50m and 1:10m"; the engine strokes the rings of the land file (minus the edges that only cut the world at the antimeridian and at -90 degrees). The separate coastline downloads carry other versions
   (10m coastline 5.0.0-pre9 against 10m land 5.1.1), so line and fill could disagree at the coast, and storing both would double the bytes.
2. **Flat view parameters.** The contract writes `view_end` as an object (`fit` with `margin_pct`, or a centre and `width_km`) and `view_start_center` as a `lonlat`; the type `lonlat` exists only as a field of an `items` record, and params are flat, so the entry has `view_end_mode` (fit | manual),
   `view_end_margin_pct`, `view_end_center` (text "lon, lat"), `view_end_width_km` (50 to 20,000, an ordinary number bound), `view_start_width_km`, `view_start_center` (text "lon, lat", empty = the end centre). Out-of-world centres are `map_bad_center`.
3. **`region_at` is seconds only** (a flat number), not a word anchor; the places and the route take word anchors.
4. **Extra params**: `sea_names_max` (3), `label_cap_pct` (2.4), `fade_s` (0.3), `seed` (4).
5. **`fit` also keeps the route's bend points** (`via`) in the frame, not only the places; for the example the box is unchanged. The exact fit of Bruges and Lucca is 2,348 km wide (Bruges at 38.4 / 19.0 percent, Lucca at 61.6 / 81.0, as R10); R10's 2,357 km is the mock-up's rounded push factor 1.612, so the test accepts 1 percent.
6. **Stroke widths.** The contract gives colours and opacities, not widths; the mock-up's coastline, graticule and region outline are "non-scaling" strokes of 1.5, 1 and 1.6 CSS pixels on a stage 540 px high, which is 3, 2 and 3 px at 1080 (R10 wrote 1.5 px at 1080 for the coast, which is half the weight the owner saw).
   Shade, water lines and route dots live in map space in the mock-up and scale with the camera (1 to 1.612); here they scale with the zoom since the start view, held to 0.6 .. 1.65, so a push of a hundred times does not smear them.
7. **No fade to black at the end.** The mock-up's `fade` layer (7.2 to 8 s) is a looping artefact of the page; the end of a shot is the storyboard's (`end.fade_s`, transitions). The head and its halo fade out 0.5 s after the route is complete, as in the mock-up.
8. **A paper-coloured halo (2 px) around place labels.** Not in the mock-up; line work under a label (Bruges sits on a dense coast) ate the letters.
9. **Sea names** are chosen by rules the contract does not give: at most `sea_names_max`, most important first (Natural Earth scale rank), only seas big enough for the view (8 percent of the width for the major ones, 30 percent for rank 3, 45 percent for the rest), text mostly on water (up to 30 percent land under a major sea's name, as the mock-up's Mediterranean, 10 percent otherwise), clear of routes, marks and labels. The
   positions of the four seas of the mock-up are the mock-up's; the rest of `LABEL_AT` are my choices, other names use the pole of inaccessibility of their polygon.
10. **The region's name** is placed at the pole of inaccessibility of the biggest ring of the region and nudged to stay inside the outline and off the marks, not at the mock-up's fixed offset from Bruges.
11. **Narrow views smooth the 1:10m outlines** (corner cutting, `maps.chaikin`) when their segments are longer than 8 px; the contract does not say what to do when the data is coarser than the view. The switch from 1:50m to 1:10m at 1,500 km is by the width of the current frame, so a push that crosses it changes the outline's detail at that moment.
12. **Label sides**: the preference order is se, ne, e, sw, nw, w, s, n, and the first side that is clear at the start, the middle and the end of the push wins; with it the example gets Bruges north-east and Lucca south-east, as the mock-up.
13. **Files outside the brief's list that I edited**: `bti/engine/storyboard.py` beyond the issue codes and the `element_too_short` families (the anchor resolution of items in `resolve`, `check_item_anchors`, the `ref` fields in `check_regions`, the shape check), because that is where anchors are resolved and validated;
    `bti/draft/techniques_md.py` (the catalogue printed `places:items` without its fields); `tests/deep/test_sweep.py` and `tests/engine/identity_lab.py` (a MAP-01 reference shot for the sweeps).
14. Category of `MAP-01` is `static` (like `STATIC-06`), so no gallery category or label had to be added.

## What I could not verify

* The row editor in a real browser: the logic is tested in Node (`items.test.mjs`) and the page code passes `node --check`, but I did not open the page and click the rows (no DOM test exists in this repository).
* A real video with a `MAP-01` shot inside a storyboard from the draft agent: the draft agent was not run (no model call); `draw_check`, `validate` and the editor and draft suites pass.
* The slow sweep of the registry (forbidden); see above.
* The look against the mock-up in motion beyond the frames compared (0.3, 1.4, 2.6, 4.2, 6.4, 7.6 s in both presets, pixel statistics at 4.2 s): I looked at stills, not at the played clip; the preview clip `style/gae/previews/MAP-01.mp4` exists (640 x 360, 15 fps, 8 s, h264) and was checked with ffprobe, not watched.
* Timings are from one server session; the server was otherwise idle but I did not control its load.
* The Vietnamese sentences were written by me and read by nobody else.


## Fix round 1 (worker `mapfix`, worktree `.worktrees/mapfix`, branch `wt/mapfix`, 2026-11-19)

Six things the coordinator saw in the stills of the first build. Everything below was done in the worktree; tests ran in snapshot `mapfix`.

### 1. A place label sits on ink: now it does not
`bti/engine/techniques/maps.py`: a `Field` per sample view holds what a label must keep off (the land, the distance of each sea pixel to the coast, the coast stroke, the region's fill and outline).
The labels are placed against five views along the push (progress 0, 0.25, 0.5, 0.75, 1: the start, the middle, the end and between). A label box is clear when no ink (coastline stroke, either water line,
the outline of a region) lies within `INK_MARGIN` = 5 px of it, it touches no route, mark, other label or frame edge. Order: the eight sides at the mark's gap (se, ne, e, sw, nw, w, s, n), the same eight twice and three times
as far out, then, when none is clear, the nearest clear place on a grid of offsets (6 px apart, up to 240 x 170 px), then the cheapest. `label_side` still forces a side. Sea names are placed after the labels and avoid them, so no label ever lies on a sea name.
In the default example Bruges sits on the corner where the Belgian coast meets the outline of Belgium: no side, at any of the three gaps, is clear at all five views, and the nearest clear text place is 82 px from the mark
(measured by scanning every offset); Bruges ends north-east of its mark at (72, -44) px and Lucca north of its mark at (-36, -56) px. Tests: `test_a_place_label_has_no_ink_under_it_in_the_default_example` (the pixels of the same
frames drawn without marks and labels, at 1.4, 4.2 and 7.6 s: no dark coastline pixel and no accent outline pixel under the box of "Bruges" and "Lucca" grown by 2 px), `test_a_crowded_place_gets_its_label_farther_out_not_on_the_ink`.

### 2. The region name touches its outline: now it is inside with clearance, or outside on free ground
`place_region_label`: the shift (px) from the region's pole where the name's box, in all five views, has no ink under it (outline, coast, water lines) with `REGION_MARGIN_IN` = 6 px (inside) or `REGION_MARGIN_OUT` = 10 px (outside)
around it, touches no mark, place label, route or frame edge, and lies wholly inside the region's fill (first choice) or wholly outside it (second); the nearest to the pole first; none: the name is left out. BELGIUM ends below-left of Belgium, on French ground, outside the outline;
FRANCE ends inside France, clear of the outline. Test: `test_the_region_name_goes_inside_a_big_country_and_outside_a_small_one` (France inside, Belgium outside; no ink, route, mark or label touched at the five views).

### 3. Sea names lie on land: now wholly on water, or left out
`place_sea_names`: a name is printed only at a position where, in every sample view where it would be printed, every pixel within 4 px of its text is sea more than 8 px beyond the outer water line
(`Field.water_clear`), and it touches no route, mark, label or other name. The position is searched around the sea's listed position (`SEA_RADIUS`: 45 percent of its extent, at most 2,500 km), nearest first, INSIDE the sea's own outline: `seas.json` now carries
`poly`, the outlines of each sea simplified to 0.3 degree (`tools/geo/build_bundle.py`, `_in_sea`), so "Mediterranean Sea" is never put in the Atlantic. The 30 percent land allowance (`LAND_UNDER_NAME`) is gone. In the default example NORTH SEA and BAY OF BISCAY are printed
(Biscay moved west, to -5.4 E 45.3 N, off the French coast); MEDITERRANEAN SEA has no water wide enough for its name in the start view and is left out; the Adriatic has none in a view of 2,000 km. Tests: `test_a_sea_name_lies_wholly_on_water_with_clearance` (the land mask of every still time:
no land within 8 px of any printed name), `test_a_sea_name_is_left_out_when_the_sea_has_no_room_for_it`, `test_a_sea_name_is_placed_inside_its_own_sea`.
Bundle: `seas.json` 44,427 bytes, sha256 `718e57af6d0ec2765aa99e8d88ae9f746477d087c5478912c8302bd5252d839b` (the three `.npz` files are unchanged); the bundle is 2,071,791 bytes; `manifest.json` and `style/gae/geo/README.md` are regenerated.

### 4. A parameter type `at` (one moment: seconds or a word)
`registry.py`: `at_params(spec)`, `_check_at` (number held to `min`/`max`, or a word anchor; codes `param_bad_at`, `param_below_min`, `param_above_max`) and one branch in `check_problem`; the hook of a renderer's `check_params` may return a fifth item, `"warn"`, to make an issue a warning.
`storyboard.py`: `resolve` resolves a word anchor of such a param like a camera key's (`_resolve_item_anchors`), `validate` reports `stale_anchor` / `anchor_invalid` (with `param`, no `index`); `param_bad_at` and `map_view_coarse` in `ISSUE_CODES`.
`techniques.schema.json`: `at` in the param types. Page: `formgen.js` (`WIDGETS.at`, `validateValue`, `coerce` reuse `fieldProblem` / `coerceField`), `formui.js` (`case 'at'`: "seconds | word" and the button "= đầu phát", the control of an `at` field of an items row), `edit.css` (one rule), `sbissues.js` (the sentence of `param_bad_at`).
`MAP-01.region_at` is of this type. `bti/engine/README.md`: the section "One moment: the parameter type `at`". Tests: `test_a_param_of_type_at_takes_seconds_or_a_word_and_is_held_to_its_bounds`, `test_region_at_takes_a_word_and_the_tint_comes_on_that_word`, `tests/editor_frontend/at_param.test.mjs`;
the sweep gets the type (`test_validate_draw_sweep.py`). Checked in a real browser (headless Chrome, a harness that loads `formui.js` with the real registry): typing seconds, clamping at 0, "= đầu phát" gives the word at the playhead, back to seconds, a change from outside.
The files merge line by line with the other workers' edits: `registry.py` (one new function pair after `items_at_fields`, one `elif`, the hook loop), `storyboard.py` (two small blocks), `formgen.js` (three single lines), `formui.js` (one new `case` before `case 'camera'`).

### 5. Narrow views
(a) Warning `map_view_coarse` (never an error; a storyboard with it saves) when `view_start_width_km` or the end view is narrower than 300 km: on `view_start_width_km`, on `view_end_width_km` (manual), or on `view_end_mode` (a fitted view); sentence on the page (`sbissues.js`): "Bản đồ này quá gần: đường bờ biển chỉ còn nét thô. Với một địa điểm trong thành phố, hãy dùng ảnh bản đồ đường phố ở bước Chọn hình thay cho bản đồ atlas."
(b) The `usage_rule` says the map is for countries, regions and journeys, views of 300 km and wider, and that a spot inside a city is shown with a street-map picture from the picks. (c) `K_MAX` = 1.617, the zoom of the default example's end view (3,800 to 2,348 km): the shade, the water lines and the route dots never get heavier, however far the push goes; the hairlines (coast 3 px, outline 3 px, graticule 2 px) are constants.
The Oslo example (60 km) is replaced by a regional one: the Oslo fjord, Oslo and Tønsberg, 900 km pushed to 400 km (`fjord_*.png`). Tests: `test_a_view_narrower_than_300_km_is_a_warning_not_an_error`, `test_the_usage_rule_says_what_the_map_is_for_and_how_to_draw_a_sea_route`, `test_strokes_and_the_shade_never_get_heavier_than_in_the_default_end_view`.

### 6. The sea route crosses land
The `via` points of the Venice example were chosen by a shortest path over the 1:10m water (a Dijkstra over a 0.03 degree raster of the water with a cost near the coast, then simplified to 0.35 degree): `16.43, 42.56; 18.59, 40.40; 18.72, 39.47; 21.68, 36.49; 22.89, 35.96; 26.07, 36.26; 26.27, 36.97; 25.32, 38.42; 25.32, 39.38; 25.94, 39.94; 27.2, 40.4; 28.3, 40.8`
(the last two are the Dardanelles and the Sea of Marmara, which the data cannot resolve). The usage rule has the sentence: a sea route needs `via` points in open water, or it is drawn across land. Test: `test_the_venice_example_route_stays_on_water` (about 1,200 samples of the curve per sample view, all on sea in the land mask, from the Adriatic to the Aegean entrance).

### Other changes
`tools/geo/render_map_examples.py`: the examples are now `default`, `sepia`, `fjord`, `venice`, `france` (a large country with its name inside). `bti/engine/README.md`, `docs/APP_GUIDE.md` (one paragraph in Vietnamese) updated. The preview clip and thumbnail are regenerated from the final code.

### Milliseconds per frame, this session (server shared with other workers; `tools/geo/render_map_examples.py timing`)
default 76.9 ms median (p90 95.2, max 129.5), sepia 83.0, fjord 76.3, venice 76.2, france 119.2 (a big region mask and outline per frame); the map itself 42 to 62 ms. The first round measured 59 ms on an idle server; the frame's code is the same except
the region masks (now a function) and the sea names (chosen at the start, not per frame), so the difference is the load of the other workers. Compiling a shot (placing labels in five views) costs 50 to 100 ms; 12 places spread over the world 700 ms.

### Tests (snapshot `mapfix`, final tree)
| Folder (one per run, `tools/deploy/snapshot_test.sh mapfix -- ...`) | Summary line as printed |
|---|---|
| `tests/engine -m "not slow"` | `383 passed, 14 skipped, 152 deselected in 309.81s (0:05:09)` |
| `tests/draft` | `330 passed, 1 warning in 175.32s (0:02:55)` |
| `tests/editor` | `478 passed, 1 warning in 294.09s (0:04:54)` |
| `tests/identity` | `77 passed in 1.64s` |
| `tests/deep -m "not timing"` | `224 passed, 4 skipped, 1 deselected, 1 warning in 338.11s (0:05:38)` |

`node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs`: `ℹ tests 314`, `ℹ pass 314`, `ℹ fail 0`, `ℹ skipped 0` (310 of the first build and the 4 of `at_param.test.mjs`).
In a worktree there is no `.venv`, so the one test that asks Python for `ISSUE_CODES` (`every code in bti.engine.storyboard.ISSUE_CODES has a Vietnamese template`) is skipped ("no .venv/bin/python", 313 passed, 1 skipped); I ran it with a temporary `.venv/bin/python` that points to the system Python (removed again) and it passes: every engine code, `param_bad_at` and `map_view_coarse` included, has a Vietnamese sentence.

### Stills (`.scratch/mapfix/stills/` in the worktree, 1280 px, rendered on the server)
Contact sheets: `sheet_default.png`, `sheet_sepia.png`, `sheet_fjord.png`, `sheet_venice.png`, `sheet_france.png`; the single stills `<name>_<seconds>.png` (default and sepia at 0.3, 1.4, 2.6, 4.2, 6.4, 7.6 s; fjord, venice, france at six moments).
