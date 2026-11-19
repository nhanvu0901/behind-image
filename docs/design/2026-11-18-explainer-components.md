# Explanatory components: the atlas map and six devices that make one point visible

Build contract, 2026-11-18. Evidence and parameter lists: `docs/design/research/R10_explainer_components.md` (parts 3 and 5).
The moving mock-ups the owner chose from: `docs/design/mock/2026-11-18-explainer/` (each scene's `update(t)` holds the exact
timings, sizes and colours). Where this contract and the mock-up differ, the contract wins.

## 1. What the owner decided

- The map: look **A, the atlas plate** ("the first one"), with one correction in their words: "it hard to diff sea and land in
  that map". The corrected mock-up gives the sea its own colour, darker toward the coast, and a lighter land. Two sea colours
  exist as presets; the default is the blue-grey one until the owner says otherwise.
- Components: "do all 1 to 6": labels as a key to parts of a picture, a time axis with dates, a big number with a comparison of
  two figures, a tree of family and patrons, the same picture in two states, a document line that is lit.
- Looks B (relief under raking light) and C (cut paper, globe) are not built.

## 2. Rules that hold for all seven (from the channel identity, `2026-11-18-identity-raking-light.md`)

- Typeface EB Garamond (the bundled files), sizes given as cap height in percent of the frame height. Nothing is boxed, ruled
  or underlined. Text appears and leaves by a fade (0.3 s unless stated); it never slides, grows or types itself.
- Each item (a place, a label, a date, a row, a relation) appears at its own time, so that it can land on the word that names
  it. An item's time is either seconds from the start of the element or a word of the narration, written the way the
  storyboard already writes anchors.
- A frame is a pure function of time (frames are rendered in any order).
- Everything is driven by data an agent can write as JSON and a person can edit on the page; no component needs an asset
  that the project does not already have, except where a slot says so.
- An element shorter than its technique's `timing.min_s` is the existing validation error `element_too_short` (extend that
  rule from the `ID-` family to these families).

## 3. A parameter type for lists of items

The registry's parameter types (number, string, enum, bool, color, point, points, lines, box, text, camera) cannot hold a list
of records. Add one type, `items`: a list of objects whose fields the registry entry declares (`fields`: name, type, required,
default, and for numbers min and max). Field types: `string`, `number`, `enum`, `bool`, `lonlat` (two numbers, longitude
-180..180 and latitude -85..85), `ref` (a region name of the shot's picture or a pixel point of it), `at` (seconds from the
element's start as a number, or a word anchor). Validation names the item and the field in its message and has a Vietnamese
sentence on the page. The page edits such a list as rows (add, remove, reorder, one input per field); the generated form of
every other type is unchanged. An `at` that is a word anchor is resolved by the engine the way camera keys' `at` is.

## 4. The seven techniques

Ids, kinds and data. Sizes in percent of the frame height. Colours in section 5. Defaults follow the mock-up.

### `MAP-01` Atlas map (base)
Real geography, Web Mercator, drawn from bundled Natural Earth data (section 6); no network at render time.
- `places` (items): `id`, `name`, `lonlat`, `at`, `label_side` (`auto`, `n`, `ne`, `e`, `se`, `s`, `sw`, `w`, `nw`).
- `route` (items, zero or more): `from`, `to` (place ids), `via` (text: `lon,lat; lon,lat`), `shape` (`curve`, `straight`),
  `at`, `draw_s`, `head` (`dot`, `none`).
- `region_iso` (lines: ISO 3166-1 alpha-2 codes of today's countries), `region_label` (string), `region_at`, `region_fill_s`.
- `view_start_width_km`, `view_start_center` (lonlat, optional), `view_end` (`fit` of all places with `margin_pct`, or a
  centre and `width_km`), `push_s` (how long the eased push lasts), `sea` (`blue_grey`, `sepia`), `sea_names` (bool),
  `graticule_deg`, `grain`, `vignette`.
- Look: land, sea shaded toward the coast, ink coastline (hairline), two water lines in the sea, graticule, paper grain and
  vignette pinned to the screen. Place mark: accent dot inside an ink ring. Labels italic, placed beside the mark where they
  touch neither the route nor another label (eight candidate positions, then `label_side`). Sea names in small capitals from
  a bundled list, shown only when they fall inside the view. Route: dotted accent line drawn progressively with a travelling
  head, anchored in map space. Region: accent tint with a hairline outline and an optional small-capital label.
- Labels keep their size while the camera pushes; only their position follows.
- Validation: at least one place; every route end names a place; `view_end.width_km` between 50 and 20,000; ISO codes exist
  in the bundled data.
- The three older map techniques (`STATIC-06`, `AN-04`, `X-ANN-05`) stay valid for existing storyboards; the catalogue the
  draft agent reads tells it to use `MAP-01` for any place, journey or territory.

### `KEY-01` Labels as a key to parts of a picture (overlay, on any shot that shows one picture through a camera)
- `labels` (items): `text`, `ref` (region name or point), `side`, `at`, `style` (`italic`, `regular`, `caps`).
- `cap_pct` (2.0 to 3.0, default 2.4), `dim_picture_to` (0.6 to 1.0, default 0.78), `fade_s`, `shadow` (bool).
- A label sits beside its detail (outside the region's ellipse on the given side), follows the base shot's camera if it moves,
  and keeps its size. No leader line by default (`leader`: `none`, `hairline`).

### `TIME-01` Time axis with dates (base, dark ground)
- `items` (items): `date` (a year; negative for BC), `label`, `side` (`up`, `down`, `auto`), `at`, `accent` (bool).
- `from`, `to` (years; default: the items' range with one year of margin), `tick_every`, `focus_s` (when the accented item
  brightens and the others dim to 55 percent), `cap_pct`.
- A hairline axis grows from the left (0.8 s), ticks fade in, each item's stalk grows and its year and label fade in at its
  time; stalk lengths alternate so that labels never touch (the technique solves collisions, the agent does not).

### `NUM-01` Big number and comparison (overlay, on any shot)
- `rows` (items): `label`, `value` (text as shown, for example "2,000"), `units` (text), `count` (number of pictogram marks,
  0 for none), `at`.
- `caption` (one line, for example what one mark stands for), `source` (small line), `dim_picture_to` (default 0.38),
  `cap_pct` (6 to 14, default 8), `align` (`left`, `right`).
- One to four rows. Marks of a row appear one after another over about 1.1 s after its number.

### `TREE-01` Relations: family and patrons (base, dark ground)
- `nodes` (items): `id`, `name`, `sub` (a second, smaller line: dates or role), `row`, `col` (grid position; `auto` layout
  when omitted), `at`, `strong` (bool).
- `edges` (items): `from`, `to`, `kind` (`descent`, `marriage`, `link`), `label`, `at`.
- Names and second lines only, hairline connectors drawn progressively (0.7 s each), edge labels in small italic.
  Marriage is a short horizontal line between two names of one row; descent runs down in right angles.

### `STATE-01` The same picture in two states (base)
- Slots `a` and `b` (two images of the same crop, required), `label_a`, `label_b` (the technique names, small capitals,
  bottom left), `camera` (one framing for both; it does not move during a change), `dissolve_s` (0.5 to 1.5),
  `holds` (text: seconds each state is held, for example `1.5; 2.5; 1.5`), `first` (`a`, `b`).

### `DOC-01` A line that is lit, with its reading (overlay, on any shot that shows one picture or document through a camera)
- `lit` (items): `ref` (region name, or a box in source pixels), `at`, `hold_s`.
- `dim_to` (0.25 to 0.6, default 0.34), `ramp_s`, `edge_px` (soft edge), `reading` (the line in today's words, italic),
  `original` (the line as written, small capitals), `reading_at`.
- The lit window follows the base shot's camera. No outline.

## 5. Colours (hex)

Map, sea `blue_grey`: land `#F3EBD9`, sea `#AFC6C4`, coastal shade `#6F9796` at 55 percent blurred over about 1 percent of the
frame height, ink `#3B2F26` (coastline at 85 percent; water lines at 26 and 42 percent; graticule 9 percent), accent
`#8C2F23`. Sea `sepia`: land `#F5EEDF`, sea `#C6B592`, shade `#8E7A52` at 50 percent, water lines 22 and 36 percent.
Dark grounds (`TIME-01`, `TREE-01`): ground `#131519`, text `#E9E2D0`, hairlines `#8D877A`, secondary text at 72 percent.
Text over pictures: `#F1EADB` with a soft shadow.

## 6. Geography data

Natural Earth, public domain (terms: https://www.naturalearthdata.com/about/terms-of-use/). Bundle in `style/gae/geo/`
only what `MAP-01` draws: land and coastline at 1:50m and 1:10m (the finer one for views narrower than about 1,500 km),
countries at 1:50m (for `region_iso`), a short list of sea and ocean names with positions. Stored compactly, loaded once,
cached; a `README.md` there states the source URLs, versions, file hashes and the licence sentence. Nothing else is bundled.

## 7. What the agents and the page get

- The catalogue the draft agent reads names, for each of the seven, the kind of sentence it serves and one filled example
  (the R10 report's table in part 4 says which sentences of the sample narration each serves).
- The agent supplies coordinates itself; the validation bounds catch nonsense. A place the agent is unsure of is left out
  rather than guessed (the briefing says so).
- Vietnamese names for the seven techniques and their parameters on the page; preview clips like every other technique.

## 8. Not in this build

Looks B and C, a globe, relief, historical borders, portraits or thumbnails inside the time axis and the tree, a count-up of
digits, a draggable before-and-after, a plan of a room, a chain of owners.

## 9. Build order

1. Worker `mapbuild`: the `items` type (engine, validation, page rows), the geography bundle, `MAP-01`.
2. Worker `compbuild`: `KEY-01`, `TIME-01`, `NUM-01`, `TREE-01`, `STATE-01`, `DOC-01`, and the catalogue and briefing text
   for all seven.
Each ends with stills for the coordinator to compare with the mock-up, tests, previews and a report.
