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
