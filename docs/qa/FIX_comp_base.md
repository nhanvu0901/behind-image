# FIX: the time axis `TIME-01`, the relations tree `TREE-01`, the same picture in two states `STATE-01`, and the catalogue and briefing text for the seven explanatory devices (worker `compbase`, 2026-11-19)

Brief: `.scratch/agy_tasks/compbase/TASK.md`. Contract: `docs/design/2026-11-18-explainer-components.md` (sections 2, 3, 4, 5, 7). Approved mock-up: `docs/design/mock/2026-11-18-explainer/components.html`,
functions `timeline`, `tree` and `states`. Branch `wt/compbase`, 82 techniques in this checkout (the coordinator sets the final number after the join with `compover`).

## What was built

* `bti/engine/techniques/explain_base.py` (new): three renderers of kind `base`, registered as `TIME-01` (`TimeAxis`), `TREE-01` (`RelationTree`), `STATE-01` (`TwoStates`), with their own text, rectangle and layout helpers
  (`vfx.py`, `registry.py` and `geo.py` are untouched).
* `style/gae/techniques.json`: the three entries inserted immediately before `MAP-01` (text splice, nothing else in the file touched), preview clips and thumbnails `style/gae/previews/{TIME-01,TREE-01,STATE-01}.{mp4,jpg}`.
* The catalogue (`bti/draft/techniques_md.py`) prints, for each explanatory device (`MAP-`, `KEY-`, `TIME-`, `NUM-`, `TREE-`, `STATE-`, `DOC-`), the fields (already printed by the map worker) and now ONE filled example taken from the registry defaults;
  one part on explanatory devices in `skills/storyboard_draft/TASK.template.md` (draft, chapter and edit of the full workspace) and in `skills/storyboard_edit/FAST.template.md`.
* Page: Vietnamese sentences for the 12 new issue codes (`sbissues.js`), words of the choices and of the row fields (`labels.js`), `camgeom.js` (one line, see "Files outside my module").
* Tests: `tests/engine/test_explain_base.py` (86), `tests/editor_frontend/explain_base.test.mjs` (6), `tests/draft/test_explainers_briefing.py` (14); counts, sweeps and the issue-code test updated.
* Docs: `bti/engine/README.md` and `docs/APP_GUIDE.md` (a part each, directly before the map's), a tool `tools/explain_base/render_examples.py` (stills, timings, previews), this report.

## Parameters, fields and milliseconds per frame

Milliseconds per frame at 1920 px on the Windows server, snapshot `compbase`, warm, 39 frames spread over each example (`python tools/explain_base/render_examples.py timing`, one session, the server not otherwise controlled):

| Example | first frame (cold) | median | mean | p90 | max |
|---|---|---|---|---|---|
| `TIME-01` default (6 items) | 175 ms | **25.2** | 25.7 | 31.0 | 36.1 |
| `TIME-01` nine items, two in 1492 | 21 ms | 25.0 | 30.2 | 42.7 | 66.7 |
| `TREE-01` default (6 names, 5 relations) | 30 ms | **51.6** | 51.5 | 70.5 | 88.9 |
| `TREE-01` Medici (7 names, 8 relations, 4 generations) | 23 ms | 48.9 | 50.3 | 72.2 | 115.6 |
| `STATE-01` default (crop of the Arnolfini Portrait, 4386 x 6000 images) | 552 ms | **65.4** | 72.9 | 101.4 | 218.0 |
| `STATE-01` half-size second image, moving camera | 120 ms | 62.2 | 75.5 | 126.1 | 172.8 |

For comparison (`docs/qa/FIX_map_build.md`, same server): `X-CARD-01` 11.7, `STATIC-06` 19.6, `CAM-01` 27.3, `FOOT-01` 42.3, `CMP-03` 58.4, `CAM-05` 60.8, `MAP-01` 59.2: all three are inside that range. The tree's layout is solved once per
construction (cached on the data), not per frame.

### `TIME-01` (kind base, category diagram, `channel_usage` occasional, intents quantify and context, timing 8 / 3 / 30 s, anchor word, no slots)

| Param | Type | Default | Bounds |
|---|---|---|---|
| `items` | items, 1 to 12 | the six dates of the mock-up (1425, 1426, 1431, 1432, 1433, 1434 accented) | fields: `date` number, required, -4000 to 3000 (a whole year, negative is BC); `label` string, required, 1 to 48 characters; `side` auto, up, down (auto); `at` seconds 0 to 600 or a word anchor (1.0); `accent` bool (false) |
| `from`, `to` | string | "" (the items' range with one year of margin) | `-?\d{1,4}` or empty |
| `tick_every` | number | 0 (automatic, at most twelve spaces) | 0 to 1000 years |
| `focus_s` | number | 6.0 | 0 to 600 s |
| `dim_to` | number | 0.55 | 0.2 to 1.0 |
| `cap_pct` | number | 2.1 (cap height of a label; the year is 1.4375 times larger) | 1.4 to 3.2 % of the height |

Rules between params (`check_params`): `time_range_inverted`, `time_date_outside` (names the item, the date and the axis), `time_crowded` (no arrangement leaves every label clear of the others and inside the frame).

### `TREE-01` (kind base, category diagram, occasional, intent context, timing 8 / 3 / 30 s, anchor word, no slots)

| Param | Type | Default | Bounds |
|---|---|---|---|
| `nodes` | items, 2 to 14 | Philip the Good, Jan van Eyck, The Arnolfini, Giovanni di Nicolao, Costanza Trenta, The Arnolfini Portrait | `id` (1 to 24 of letters, digits, `_`, `-`), required; `name` 1 to 40, required; `sub` 0 to 48 (""); `row` -1 to 4 (-1); `col` -1 to 11 (-1); `at` 0 to 600 or anchor (1.0); `strong` bool (false) |
| `edges` | items, 0 to 24 | duke to jan (link), fam to gio (descent), gio to cos (marriage "married 1426"), jan to pic and gio to pic (links "paints", "buys") | `from`, `to` required ids; `kind` descent, marriage, link (link); `label` 0 to 32 (""); `at` 0 to 600 or anchor (1.0) |
| `cap_pct` | number | 2.55 (regular names; strong 1.1 times, second line 0.72, edge labels 0.667) | 1.6 to 3.4 % |

`row` and `col` at -1 mean "the technique places it"; positions are used only when EVERY name has both. Rules between params: `tree_duplicate_node`, `tree_edge_unknown_node`, `tree_edge_self`, `tree_marriage_shape`, `tree_marriage_rows`,
`tree_overlap`, `tree_too_big`.

### `STATE-01` (kind base, category compare, rare, intents compare and reveal, timing 7.5 / 3 / 30 s, anchor shot_start; slots `a` required with regions, `b` required)

| Param | Type | Default | Bounds |
|---|---|---|---|
| `label_a`, `label_b` | string | "Colour", "Infrared" | 0 to 32 characters (empty = no caption for that state) |
| `camera` | camera | null (the whole of `a`, as CAM-01) | the usual keys, in source pixels of `a` |
| `dissolve_s` | number | 1.0 | 0.5 to 1.5 s |
| `holds` | string | "1.5; 2.5; 1.5" | two to six numbers, each 0.2 to 60 s |
| `first` | enum | a | a, b |
| `label_cap_pct` | number | 1.8 | 1.2 to 3.2 % |
| `shadow` | bool | true | |

Rules between params: `state_holds_count` (the pattern already refuses a wrong count; kept as a second guard), `state_hold_range`.

## How each layout is solved

* **`TIME-01`** (`solve_time`, a pure function of the data, cached). Positions: the years are spread from 9 to 91 percent of the width, the axis runs from 6 to 94 percent at 56 percent of the height, as the mock-up. For every item the technique chooses a side (up or down; `auto` prefers
  alternation by date order, as the mock-up), a stalk length (three above the axis, 13, 24 and 35 percent of the height; two below, 13 and 24), and a place for the label (centred on its stalk and pushed into the frame, or shifted 22 or 78 percent as the mock-up shifts its two outer labels).
  A depth first search takes the items accented first, then by date, and tries for each item: its preferred side with every tier centred, the other side, then the shifted places; a choice is dropped when the box of its year or label
  comes within 1.2 percent of the width or 0.8 of the height of another item's box, when another item's stalk runs through the box, or when the box leaves the frame (3 percent margin). The order of the choices makes the default data come out exactly as the mock-up
  (up, down, up, down, up, down; 13 percent stalks except 1432 below and 1433 above at 24 percent); the accented item gets the first choice (the short stalk next to the axis). Items of one year get different places (different side or tier, or a shifted label). The
  search is limited to 60,000 steps; data it cannot solve is the validation error `time_crowded`, so what `validate` accepts has no clash. Ticks sit on multiples of `tick_every`; a tick is major (twice as long) on every fifth.
* **`TREE-01`** (`solve_tree`, cached on the data). Marriages make units (a chain of at most two marriages per person). Generations: longest path down along descent and link edges, spouses in one row, a source whose people all stand further down moves down next to them, edges that
  close a ring are ignored; at most five rows. An edge that skips rows gets a virtual node in each skipped row, so that it runs between the names. Order inside a row: ten barycentre sweeps, the order with the fewest crossings kept; a couple's two members are ordered by where their parents stand.
  Coordinates: a weighted least-squares relaxation (pool adjacent violators with minimum gaps between units, symmetric Gauss-Seidel sweeps, the picture re-centred every sweep). Units are lined up by their centres, so a parent stands over the middle of a child couple; the child of a couple stands straight below the middle of
  the marriage line; both spouses writing the same child give one connector. A small tree is spread over up to 82 percent of the width (the spread is tried at 3.4, 2.8, 2.3, 1.8, 1.4 times the minimum gap), a wide one gets smaller text (steps down to 64 percent) until it fits, else `tree_too_big`. Rows are at 51.5 percent of the height
  plus the row number times the pitch (32.75 percent for two or three rows, less for more; five rows at most), so the default data has its rows at 19, 52 and 84 percent as the mock-up. Connectors are right-angled: out of the lower edge of the upper name (or the middle of a marriage), across in the gap between two rows
  (parallel runs get their own height), into the upper edge of the lower name; a marriage is a level line between the two names. A label sits above its own horizontal run when that is long enough for the words, else beside the longest vertical run (right, then left), else where it touches least. Manual grid (`row` and `col` on every name):
  the cells are mapped onto the frame, rows evenly, columns at most 20 percent of the width apart, with the end names kept inside the frame; touching names are `tree_overlap`.
* **`STATE-01`**. Both pictures go through the same `compose_matte` as CAM-01, with the shot's `camera` in the pixels of `a`; `b` is looked at through the same frame, scaled to the width of `a` and centred on it, so two images of one crop line up whatever their pixel sizes (the half-size copy
  in the stills lands on the same pixels; images of different SHAPES are mapped by width and centred, not corrected, and `validate` does not warn about them). A hold draws only one picture and is bit-identical to it; a dissolve is a linear mix. The camera clock stands still through a dissolve and runs faster in the holds by the time lost, so the
  whole move of the keys is still made at the end of the shot and the camera is the same just before and just after a change. The caption flips at the middle of each dissolve by a fade out and in.

## The catalogue and the briefings

* Catalogue (`techniques_md.generate`): every explanatory device gets a line `- example (the defaults; replace ALL of its data): {...}` after its params line: all its lists of items, written compactly (a field that holds its default and is not required is left out), plus the non-empty lines and
  strings; for `MAP-01` that is places, route, region_iso and region_label, for `TIME-01` the six items, for `TREE-01` nodes and edges, for `STATE-01` the two labels and the holds. Taken from the registry defaults, so it cannot drift; no other technique gets one. The generated catalogue is 71,820 characters.
* The new part (in `skills/storyboard_draft/TASK.template.md`, section 5, before "Habits that make a draft good"; it serves the full draft, a chapter and an edit through `TASK.md`) in full:

> Explanatory devices (`MAP-01`, `TIME-01`, `TREE-01`, `KEY-01`, `NUM-01`, `STATE-01`, `DOC-01`; use only those `inputs/techniques.md` lists). Each makes one point that a picture alone cannot show, so use one only where the narration makes that point, never as decoration:
> - `MAP-01`: a place, a journey or a territory (use it for ANY place, journey or territory instead of STATIC-06, AN-04 and X-ANN-05); `TIME-01`: events with dates, in order or as a span; `TREE-01`: who is related to whom or who worked for whom; `KEY-01`: names for parts of the picture on screen; `NUM-01`: a figure, or two figures compared; `STATE-01`: the same picture in two states (before and after, colour and infrared); `DOC-01`: one line of a document, lit, with its reading.
> - Tie every item (a place, a date, a name, a row) to the word that names it: its `at` is that word, written `{"w": <the word's index in words.tsv>}`, so the item appears as it is spoken (a plain number of seconds from the start of the shot also works).
> - Coordinates, dates, figures, names and relations come only from the narration and the project's sources: leave an item out when you are unsure, never guess. The `example` in the catalogue is only a template: replace all of its data, never half of it.
> - How often: real videos use them sparingly, about 6 to 12 in a ten-minute video, never two in a row and none through general talk; many sentences are served better by a camera move.

* The same for the fast edit (`skills/storyboard_edit/FAST.template.md`, one bullet in "How the usual requests turn into changes"):

> **Explanatory devices (`MAP-01`, `TIME-01`, `TREE-01`, `KEY-01`, `NUM-01`, `STATE-01`, `DOC-01`; only those the catalogue lists)**: each makes one point a picture alone cannot show (a place or journey or territory; dated events; who is related to whom; names for parts of the picture; a figure; the same picture in two states; one line of a document, lit). Add or change one only when the owner's sentence is about that kind of point, never as decoration. Use `MAP-01` for ANY place, journey or territory instead of STATIC-06, AN-04 and X-ANN-05. Tie every item to the word that names it (its `at`: `{"w": <word index>}`). Coordinates, dates, figures and relations come only from the narration and the project's sources, so if the owner asks for one you cannot fill from them, or for a second picture the project does not have, answer `cannot` (or `escalate` when a slower agent that sees the picture could do it); never guess. Real videos use about 6 to 12 of them in ten minutes, so do not add one beside another.

  The part adds 1,443 bytes to `TASK.template.md` (22,250 to 23,693) and 1,018 bytes to `FAST.template.md` (10,498 to 11,516); no existing test bounds their size, so `tests/draft/test_explainers_briefing.py` pins the part (under 1,900 and 1,300 bytes) and the templates (at most 1,700 and 1,300 bytes over their old sizes).
  "How often" rests on R10 part 4.3 and part 2: in the 91 sentences of the Arnolfini narration 48 could be served by a device (10 places, 14 parts to name, 8 dates, 6 relations, 5 figures, 2 changes, 3 documents) but the reference channel shows a map only for 4 to 14 s at a time; the range 6 to 12 is my reading of that, not a measured rate (see "Could not verify").
* The intent index at the top of the catalogue serves the new techniques: `TIME-01` under quantify and context, `TREE-01` under context, `STATE-01` under compare and reveal.

## Tests (snapshot `compbase`, `BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_test.sh compbase -- ...`, one folder per run)

| Folder | Summary line as printed |
|---|---|
| `tests/engine -m "not slow"` (final tree) | `457 passed, 14 skipped, 158 deselected in 344.18s (0:05:44)` (371 passed before; +86 = `test_explain_base.py`) |
| `tests/draft` (final tree) | `344 passed, 1 warning in 138.30s (0:02:18)` (330 before; +14 = `test_explainers_briefing.py`) |
| `tests/editor` (final tree) | `478 passed, 1 warning in 401.65s (0:06:41)` |
| `tests/identity` | `77 passed in 1.39s` |
| `tests/deep -m "not timing"` | `227 passed, 4 skipped, 1 deselected, 1 warning in 331.00s (0:05:31)` (the sweep now draws the three new references and counts 82 techniques) |
| Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs` | `ℹ tests 316`, `ℹ pass 315`, `ℹ fail 0`, `ℹ skipped 1` (310 before and 6 new in `explain_base.test.mjs`) |

The one skipped JS test, "every code in bti.engine.storyboard.ISSUE_CODES has a Vietnamese template", skips itself because the worktree has no `.venv/bin/python`; I ran its check by hand with the engine's Python: 134 codes, 134 templates, none missing and none extra.
Not run, because the brief forbids `-m slow`: the full validate and draw sweep of the registry (`tests/engine/test_validate_draw_sweep.py`; its three new rows are covered by `test_validate_accepts_only_what_the_three_can_draw`); `tests/deep -m timing` was not run either.
During development I also ran the new test file alone, with fixes between runs (7 failures found and fixed on the first full run of the file: tick spacing assumed one year, a connector with a point in the middle of a straight run, a crossing in an adversarial tree, an over-wide test tree, the camera's end key, the caption at 7.8 s, a test line that expected the wrong refusal); the table above is the final tree.

`tests/engine/test_explain_base.py` measures: the axis' right end per time (it starts at the left, stops at 94 percent at 0.8 s), tick fade and stagger, every stalk, year and label absent before its `at` and present after (stalk length per time), label boxes pairwise clear
and inside the frame for 1, 2, 5, 9 (two in 1492) and 12 items, BC and AD together, two items in one year; every ink pixel of the finished axis belongs to the axis, a stalk, the dot or a label box; the default layout equals the mock-up's sides and tiers; accented brightness and the others'
brightness at exactly `dim_to`; for the tree every node and connector absent before its time, connector growth along its own path, the marriage line (level, between the names, label above and centred), the single pair, three generations with two marriages (rows, spouses adjacent, child under the middle of the marriage, no crossing, no connector through a name, no label touching a name or a line),
the default against the mock-up's rows, a hand-made grid, shrinking text, all rules between params; for the states frames inside a hold equal the single picture (bit for bit), the mix at 25, 50 percent is the mean of the two within one level, `first`, the camera before, during and after a change and at the ends of the shot, the caption (position, cap height, fade in, flip, fade out), a half-size second image against the full one,
a short and a long shot; every param at `min` and `max`; the odd-value rule of the registry (`validate` accepts only what draws) for the three; the same frame twice and out of order identical; no socket; `element_too_short`.

## The stills (`.scratch/compbase/stills/`, 1280 px wide, rendered on the server by `tools/explain_base/render_examples.py stills`)

Contact sheets (labelled with the time): `sheet_time_default.png`, `sheet_time_nine.png`, `sheet_tree_default.png`, `sheet_tree_medici.png`, `sheet_state_default.png`, `sheet_state_moving.png`; single stills `<example>_<time>.png` (five moments each: `time_default` 0.5, 2.0, 3.8, 5.8, 7.2 s; `time_nine` 0.6, 2.7, 4.6, 6.6, 8.6;
`tree_default` 0.9, 2.2, 3.6, 5.4, 7.2; `tree_medici` 1.2, 2.6, 3.8, 5.0, 7.0; `state_default` 0.8, 2.0, 3.8, 5.5, 6.8; `state_moving` 0.8, 2.5, 4.2, 6.0, 8.2). The picture is the Arnolfini Portrait of `projects/technique_lab/media`; the second state is made by the tool: the mock-up's "infrared" filter
(grey, contrast 1.45, brightness 1.08) for the default, a half-size sepia copy for the stress example. I also rendered the mock-up in headless Chrome (960 x 540 at scale 2, the bundled EB Garamond) at the same times and compared it with the engine side by side (on the Mac with the engine's Python; the delivered stills are the server's).

What I saw:
* **Time axis, default.** Same positions as the mock-up for the axis, ticks (every year, a longer one at 1425, 1430, 1435), the six stalks (13 percent, with 1432 below and 1433 above at 24 percent), the years in medium weight and the labels in italic, the accented 1434 in full brightness with its dot, and at 7.2 s the others dim to 55 percent
  and the dot has grown by half. The differences from the mock-up: its two outer labels are shifted by hand and mine are centred under their stalks (1425 and 1434); its axis starts growing from the middle (a CSS default), mine from the left.
* **Time axis, nine items, two in 1492, 1397 to 1492.** Ticks every ten years; labels alternate above and below; 1464 and 1492 (above) stand on the second tier because their neighbours are close; the two 1492 items are on opposite sides; the longest label ("Columbus reaches the Americas") ends at 97 percent of the width; nothing touches.
* **Tree, default.** The same six names, strong ones larger, second lines in italic at 72 percent; the duke straight above the painter, the Arnolfini family over the middle of the couple with a right-angled connector into Giovanni, the marriage line level between the two names with its label above, and the two links into the portrait as one right-angled bus with "paints" and "buys" above their own runs.
  Differences: the mock-up's two links to the portrait are slanted lines; mine are right-angled; the whole drawing is centred in the frame (the mock-up's is left-heavy).
* **Tree, Medici (three generations, two marriages and a patron, laid out automatically).** Rows at 18, 40, 62 and 84 percent; Piero straight below the middle of Cosimo's marriage line, Lucrezia on his right with her marriage line; Lorenzo and Giuliano under the middle of Piero's marriage; Botticelli straight below Lorenzo with "patron of" beside the line; no crossing.
* **States, default.** The crop of the mock-up: "COLOUR" at the bottom left, the dissolve to the infrared-like picture (the caption fades out and the other fades in at the middle), a hold on it, the dissolve back; the picture does not move. At the same times the engine and the mock-up agree on crop, caption position and size; the mock-up's second dissolve is 0.6 s, mine 1.0 s (one `dissolve_s`).
* **States, half-size sepia copy with a moving camera.** The half-size copy lands on the same pixels as the colour picture; the camera moves in the holds and stands still in the dissolves; the caption names the right state ("SEPIA COPY AT HALF SIZE" first).

## Deviations from the contract and from the mock-up, and why

1. **`from` and `to` of `TIME-01` are text, not numbers** (empty = automatic). A number cannot be empty on the page, and a default of 1424 to 1435 would make every replaced `items` list an error until the agent also replaced the axis (a date outside the axis is an error); the map worker made the same choice for its view centres.
2. **Extra params**: `dim_to` (the contract fixes 55 percent; exposed so that the stated amount can be tested and changed), `tick_every` 0 = automatic, `label_cap_pct` and `shadow` of `STATE-01`. `cap_pct` of `TIME-01` is the cap height of a label (default 2.1 = the mock-up's 3.2 cqh font); the contract gives no default.
3. **`row` and `col` are numbers from -1** and -1 means automatic (the page cannot leave a number cell empty; a blank cell goes back to the minimum, which is -1). Positions are used only when every name has both. The contract's "grid position" allows halves (`col` 1.5).
4. **Mock-up quirks not reproduced**: the axis grows from the left, as the contract and the brief say (the mock-up scales from the centre by default); outer labels are shifted by the solver only when needed, not by hand; the end fade of the page (7.5 to 8 s) is a looping artefact (the end of a shot is the storyboard's, as the map worker decided); the mock-up's `STATE-01` second dissolve is 0.6 s, the contract has one `dissolve_s`.
5. **`TREE-01` connectors are right-angled for every kind.** The mock-up draws the two links into the portrait as slanted lines by hand; the contract says only that descent runs down in right angles and does not describe a link. Marriage and descent are as specified; the rest follows the same rule so that a layout solved by a program stays tidy. Edge labels use text at 72 percent (contract section 5) instead of the mock-up's `#b9b2a2`.
6. **Hairlines are 2 px (axis, stalks, ticks) and 3.2 px (connectors)** at 1080 high: the mock-up's 1 and 1.6 CSS px on a stage 540 px high, measured on the mock-up's own screenshot (3.2 px).
7. **`STATE-01` caption colour** is `#F1EADB` with a soft shadow (contract section 5, text over pictures), the mock-up's is `#E9E2D0`.
8. **The camera of `STATE-01` is not frozen but re-timed**: its clock stops during a dissolve and runs faster in the holds, so the whole move of its keys is still made by the end of the shot (a plain stop would leave the last key unreached).
9. **Second image mapping**: scaled to the width of `a` and centred (documented above); no validation warning for images of different shapes (adding one needs a slot check in `storyboard.validate`, which I did not touch).
10. **Limits chosen where the contract is silent**: 12 items, 48 characters per label; 14 names, 5 generations, 24 relations, 32 characters per edge label; at most two marriages per person; holds 2 to 6 of 0.2 to 60 s; a TIME-01 axis has three tiers above and two below.
11. `channel_usage` of the three is `occasional`, `occasional`, `rare` (R10: 8, 6 and 2 sentences of 91); categories `diagram`, `diagram`, `compare`.

## Files outside my own module that I touched

`bti/engine/storyboard.py` (a block of 12 issue codes marked `compbase`, directly before the map's `map_*` block; there is no `mapbuild` marker in that table), `bti/editor/static/js/labels.js` (a block before the `mapbuild` block for the words of the choices; a second small piece directly after the `ITEM_FIELD` definition,
because `ITEM_FIELD` is declared inside the map's block and cannot be extended before it), `bti/editor/static/js/sbissues.js` (a block directly before the `mapbuild` block), **`bti/editor/static/js/camgeom.js` (one line, `'STATE-01': { camera: MATTE('a') }`; not in the brief's list, but the existing test `camgeom.test.mjs` fails for any technique with a camera parameter that the table does not know)**,
`bti/draft/techniques_md.py`, `skills/storyboard_draft/TASK.template.md`, `skills/storyboard_edit/FAST.template.md`, `bti/engine/README.md`, `docs/APP_GUIDE.md` (my parts before the map's; the technique count 79 became 82 in both), `tests/engine/test_default_params.py`, `test_registry_complete.py` (count and the prefix tuple of the lab
that predates the families: `("ID-", "MAP-", "TIME-", "TREE-", "STATE-")`, a line the other worker edits too), `test_validate_draw_sweep.py` (docstring), `identity_lab.py` (`append_explain_base_shots`, before the map's function), `test_issue_codes.py` (`_compbase_codes`), `tests/deep/test_sweep.py` (count, three reference shots before the map's). `registry.py`, `vfx.py`, `geo.py` and `bti/editor/static/mock/techniques.json` are untouched.

## What I could not verify

* The row editor in a real browser (no DOM test exists): the logic and the sentences are tested in Node; I did not open the page.
* A real draft: the draft agent was not run (no model call), so I do not know how an agent fills `items` from a real narration; `draw_check`, `validate` and the draft suite pass, and the catalogue example validates.
* The slow sweep of the registry (`-m slow` is forbidden); its three rows are covered by `test_validate_accepts_only_what_the_three_can_draw` (the same odd values, not slow). `tests/deep` `-m timing` was not run either.
* The played clips: the preview clips (640 x 360, 15 fps) were checked with ffprobe and by extracting frames, not watched. The motion against the mock-up was compared on stills at the same times, not as moving pictures.
* `STATE-01` with a real infrared scan: the second state is a copy made here. Images that are not the same crop are not detected.
* The briefing's frequency range ("about 6 to 12 in ten minutes") is my reading of R10, not a measured rate; the effect of the part on a real draft is unknown.
* The Vietnamese sentences and labels were written by me and read by nobody else.
* Timings come from one server session whose load I did not control.

## Status lines

See `.scratch/agy_tasks/compbase/STATUS.md` (last line `DONE:`).
