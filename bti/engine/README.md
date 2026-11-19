# bti.engine: how it works and how to add a technique renderer

The engine renders `projects/<id>/storyboard.json` (schema `bti.storyboard/1`, design section 6) deterministically. It never decides
anything: every piece of content comes from the storyboard, every default from `style/gae/style.json` and `style/gae/techniques.json`.

```
python -m bti.engine still    projects/arnolfini 310 --width 960 -o out.png
python -m bti.engine render   projects/arnolfini --t0 300 --t1 310 -o out.mp4 --width 640 --fps 15
python -m bti.engine validate projects/arnolfini
python -m pytest tests/engine -q                      # use .venv-engine/bin/python (includes the validate/draw sweep)
python tests/engine/equivalence_check.py              # new engine vs the benchmark frame_at (writes equivalence_report.md)
python tools/export_arnolfini.py                      # rebuild projects/arnolfini from demo_runs/claude_code
```

### Command line rules

Limits come from `bti/engine/limits.py` (the same constants the editor's HTTP API uses). Times are finite and `>= 0`; `render` needs
`--t1 > --t0`; `--t0` / `t` must be before the end of the storyboard; `--width` 64..1920; `--fps` 1..30; `--threads` 0 (automatic, the
default) or 1..64. `0` is a value, not "not given". Exit codes: 0 success, 1 run-time failure (missing project, unreadable storyboard,
unwritable output, ffmpeg failed, a technique cannot draw, `validate` found errors), 2 usage error. A failure prints one line on stderr;
the traceback only with `--debug`. A failed `render` leaves no partial output file.

### Validate, draw and the registry

`Project.validate` reports every issue with `level`, `path`, `message`, `code` and `args` (`bti.engine.storyboard.ISSUE_CODES` lists the
codes). The rule behind the registry is: whatever `validate` accepts without an error can be drawn. Param definitions therefore carry
`min`/`max` (every number has both), `pattern` + `pattern_hint` (string/text/lines; the Vietnamese hint says what to type),
`min_items`/`max_items` (points/lines/items), `fields` (items, below) and `numeric_only` (a point that cannot be a region name). `Project.draw_check` draws one small
frame per shot, overlay and transition and returns `undrawable` issues; approval runs it. A technique that fails while drawing raises
`RenderError` (shot id, overlay id, technique id) from `frame_at` and `render_range`. `bti/engine/guard.py` refuses any buffer over
four canvases. `tests/engine/test_validate_draw_sweep.py` checks the rule for all 82 techniques and all fourteen param types.

## Layout

| File | Role |
|---|---|
| `api.py` | the facade (design 8.1): `open_project`, `Project`, `load_style` |
| `storyboard.py` | canonical JSON + revision, `resolve`, `validate`, atomic `save` with `history/` backup |
| `timing.py` | word lookup (`find`, `anchor_for`) and anchor resolution (`t`, `w`+`off`+`text`, `rel`) |
| `registry.py` | `@technique(id, kind)`, parameter validation against `techniques.json` (including the `items` type and a per-technique `check_params` hook), `check_registry` |
| `geo.py` | Web Mercator views (`View`, `fit`, `ease_view`) and the bundled Natural Earth data (`land`, `countries`, `seas`), read once and cached |
| `scene.py` | compile a resolved storyboard into a `Scene`: `frame_at`, `render_range`, transitions, end fade |
| `base.py` | the renderer interfaces, `Ctx`, and the process-wide LRU caches |
| `vfx.py` | pixel primitives lifted from the benchmark (`Img`, `Cam`, `compose_matte`, `text_layer`, `spotlight`, `ring` ...) |
| `techniques/` | one module per family: `camera`, `labels`, `annotate`, `cards`, `layout`, `diagrams`, `transitions`, `identity` (the ID family, below), `maps` (MAP-01, below) |

Frame pipeline: shot lookup (bisect on shot starts) -> base renderer -> overlays in list order -> optional `transition_in`
(both shots are rendered during the overlap) -> end fade (`end.fade_s`, default 1.6 s, `inout_sine`) -> uint8 -> resize.
The engine always renders 1920x1080 and resizes down with `INTER_AREA` (a 960 px still costs the same as 1080p plus ~1 ms).

## The four renderer interfaces (`base.py`)

A renderer is constructed once per compiled Scene (cheap: no image decoding) and called once per frame. All arguments are already
resolved: `shot["_t0"]`, `shot["_t1"]`, `ov["_t0"]`, `ov["_t1"]` and every anchor's `_t` are seconds.

```python
class BaseRenderer:                     # kind "base" or "card": draws the whole frame
    def __init__(self, tid, shot, ctx)  # self.p = registry defaults overlaid with shot["params"]; self.t0, self.t1; self.slot_asset("image")
    def render(self, t) -> float32 BGR (1080, 1920, 3), values 0..255
    def view(self, t) -> View | None    # (cx, cy, zoom, img, asset_key) when there is a camera; overlays use it. None for cards.

class OverlayRenderer:                  # kind "overlay": drawn on top of the base
    def __init__(self, tid, ov, shot_r, ctx)   # self.p merged params; self.t0, self.t1 = overlay start/end seconds
    def apply(self, f, t, view) -> f           # f is float32 BGR; mutate/return it; view may be None (cards)

class TransitionRenderer:               # kind "transition": used via shot["transition_in"] = {technique, dur, params}
    def __init__(self, tid, tr, ctx)           # self.dur seconds
    def blend(self, f_out, f_in, p) -> f       # p in 0..1; the outgoing shot keeps rendering past its end during the overlap
```

Every renderer class may also define a classmethod

```python
@classmethod
def default_params(cls, tid, spec, context, bundle) -> dict
```

which is what `Project.default_params(technique_id, context)` calls. The default implementation returns the registry defaults.

One class can serve several ids: stack `@technique` decorators on it (`MatteShot` serves CAM-01, 03, 04, 05,
STATIC-01 and X-LAY-01); the renderer learns which id it was built for from `self.tid`.

## The context object (`Ctx`, `base.py`)

| Member | Use |
|---|---|
| `ctx.w`, `ctx.h` | canvas size (always 1920x1080); pass them to every vfx call that takes a size |
| `ctx.sv(section, key, default)` | a constant from `style.json` (`ctx.sv("ring", "opacity")`) |
| `ctx.asset(key)`, `ctx.asset_size(key)` | the storyboard's asset record and its pixel size (no decoding when `width`/`height` are stored) |
| `ctx.image(key)` | lazy, LRU-cached `vfx.Img` (full resolution plus pyramid) |
| `ctx.point(pt, asset_key)` | region name or `[x, y]` to source pixels |
| `ctx.layer(key_tuple, build)` | cached pre-rendered RGBA `vfx.Layer` (text, label strips) |
| `ctx.cached(key_tuple, build)` | cached anything else big (a blurred background, a procedural bitmap) |
| `ctx.t(anchor, shot)` | seconds for a resolved anchor (rarely needed: use `self.t0/t1` and `shot["_t0"]`) |

## Coordinate conventions

- **Source pixels** are pixels of the shot's image. Region names (`"MIRROR"`) and `[x, y]` points, `rx`, `ry`, `radius`, camera `cx`, `cy` are all source pixels. A point param
  (type `point`) is a region name of the shot's main image (slot `image`) or `[x, y]`.
- **Camera**: `cx, cy` is the source point at the centre of the canvas, `zoom` is screen pixels per source pixel on the 1920-wide canvas. The visible box is `1920/zoom` by `1080/zoom`.
  `view.to_screen(x, y)` maps source to canvas pixels. Multiply source sizes by `view.z` for screen sizes.
- **Canvas pixels** (1920x1080, origin top left) are used only for things that have no image: `screen` text positions, the procedural map and diagram points. The registry marks them with unit `canvas px`.
- Camera keys are `{"at": anchor, "cx", "cy", "zoom", "ease"}`; `ease` is the curve to the NEXT key; zoom interpolates in log space. Default anchors are `{"rel": 0}` and `{"rel": 1}` so a camera follows its shot when the shot is retimed.
- Times in params are seconds relative to the shot (cards, diagrams) or to the overlay start; absolute times live only in anchors.
- Frames are BGR, float32 while compositing, uint8 only at the end.

## Caching rules

1. Never keep per-frame state on the renderer: `render(t)` and `apply(f, t, view)` must be pure functions of `t` (frames are rendered out of order and by several callers).
2. Load images only through `ctx.image` (LRU by bytes, `BTI_IMAGE_CACHE_MB`, default 900). Never hold an `Img` on the renderer for longer than a call; fetch it in `render`/`view`.
3. Build text or any pre-rendered layer through `ctx.layer(key, build)`. The key must contain EVERY input of `build` (text, sizes, tracking, colours, positions). Canvas size and the font choice are appended
   to the key for you, so a size or font change never returns a stale layer. Cache bytes are bounded (`BTI_LAYER_CACHE_MB`).
4. Static procedural backgrounds go through `ctx.cached`, never recomputed per frame (the map background took 120 ms per frame before).
5. All randomness is seeded (`np.random.RandomState(seed)` with a `seed` param); two renders of the same storyboard must be bit-identical (`tests/engine/test_render.py` checks).
6. Text placed at a position that changes per frame: render the layer once at the canvas centre and `layer.apply(f, env, dx, dy)` with integer offsets (see `DimensionAnnotation`).

## Registering default parameters

`default_params(tid, spec, context, bundle)` receives:

- `spec`: the registry entry (`spec["params"]` have `name, type, default, min, max, values, required`).
- `context` (all keys optional, see `Project.default_params`): `asset` (a dict `{key, w, h, title, artist, year, regions}` once the facade has resolved it), `asset_right`, `region`/`focus`, `camera`
  (`{cx, cy, zoom}` at the playhead), `text`, `title`, `artist_year`.
- `bundle`: `bundle.sv(section, key, default)` reads `style.json`; `bundle.by_id` is the registry.

Rules: start from the registry defaults, override from `style.json` (measured channel values) and from the context (asset size, region, label text). Every returned value must pass
`registry.validate_params` (a test checks this for every available technique, with and without context). A param whose default is `null` and that cannot work empty is marked `"required": true` in the
registry and `default_params` must fill it when it can.

## Adding a technique: worked example (STATIC-02, the source line at the bottom left)

1. **Pick the registry entry.** The id, kind and slots come from `style/gae/techniques.json`; you may not invent ids. STATIC-02 is `kind: overlay`.
2. **Correct the registry params to what the renderer really uses** and flip the engine block. For this entry the final form is (`style/gae/techniques.json`):

   ```json
   "params": [
     {"name": "text", "type": "string", "default": "Jan van Eyck, The Arnolfini Portrait, 1434", ...},
     {"name": "size_px", "type": "number", "default": 24, "min": null, "max": null, ...},
     {"name": "margin_left_px", "type": "number", "default": 36, ...},
     {"name": "margin_bottom_px", "type": "number", "default": 26, ...},
     {"name": "fade_in_s", "type": "number", "default": 0.3, ...},
     {"name": "fade_out_s", "type": "number", "default": 0.3, ...}
   ],
   "engine": {"status": "done", "available": true, "impl": "bti.engine.techniques.labels.SourceLabel", "reason": null, "notes": "..."}
   ```
   Param types: `number, enum, bool, string, text, color (#rrggbb), point, box, camera, asset, points, lines, items, at`. Unknown params are errors for everyone, so list every knob. File format: `style/gae/techniques.schema.json`.
3. **Write the renderer** in the family module (`techniques/labels.py`) and decorate it with the id and kind:

   ```python
   @technique("STATIC-02", "overlay")
   class SourceLabel(OverlayRenderer):
       def __init__(self, tid, ov, shot_r, ctx):
           super().__init__(tid, ov, shot_r, ctx)               # self.p, self.t0, self.t1
           p = self.p
           text, size = p["text"], int(p["size_px"])
           x, y = int(p["margin_left_px"]), ctx.h - int(p["margin_bottom_px"]) - (size + 12)
           def build():                                        # runs once per distinct key
               ft = font("reg", size)
               w = int(ImageDraw.Draw(Image.new("L", (10, 10))).textlength(text, font=ft)) + 12
               im = Image.new("RGBA", (max(w, 1), size + 12), (0, 0, 0, 0))
               ImageDraw.Draw(im).text((0, 2), text, font=ft, fill=(255, 255, 255, 235))
               return Layer(np.array(im), x, y)
           self.layer = ctx.layer(("srclabel", text, size, x, y), build)

       def apply(self, f, t, view):
           return self.layer.apply(f, window(t, self.t0, self.t1, float(self.p["fade_in_s"]), float(self.p["fade_out_s"])))

       @classmethod
       def default_params(cls, tid, spec, context, bundle):
           d = {p["name"]: p["default"] for p in spec["params"]}
           a = context.get("asset") or {}
           d["text"] = context.get("text") or ", ".join(x for x in (a.get("artist"), a.get("title"), a.get("year")) if x) or d["text"]
           return d
   ```
4. **Make sure the module is imported** by `techniques/__init__.py` (new modules must be added there).
5. **Test it**: add a case to `tests/engine/test_render.py` (see `test_worked_example_source_label_renders`). `test_default_params.py` and `test_registry_file_is_valid_and_consistent`
   already cover default params and the registry/renderer consistency for every available technique (`registry.check_registry`: a renderer without `available: true`, or the reverse, fails).
6. **Look at it**: `python -m bti.engine still projects/arnolfini <t> -o x.png` after adding it to a shot, or use a draft in a script.

### Timing semantics are part of the technique

An overlay has `start` plus `dur` (or `end`); the renderer gets `self.t0`, `self.t1`. Each technique documents what t1 means in its docstring. Examples in this repo: label strips and screen text fade out ending at t1
(`window`); the spotlight starts its ramp-out AT t1 and lets it run past (the shot clips it, as in the benchmark); the ring ignores everything at or after t1 and uses its own `draw_s/hold_s/fade_s`.
Keep a benchmark's semantics when porting so equivalence holds, and write it down.

### Porting a reel-only technique

The reel functions in `demo_runs/claude_code/build_reel.py` have the signature `(t, d) -> frame` with literals inside. To port one: move the literals into registry params (or `style.json`),
turn `(t, d)` into `render(t)` using `self.t0`/`self.t1`, replace `S()["A"]` / `view(...)` by `ctx.image(slot_asset)`, replace the module-global text cache by `ctx.layer`, replace the global `W, H` by `ctx.w, ctx.h`.
Check it against the reel's own frame the same way `tests/engine/equivalence_check.py` checks the episode (PSNR >= 40 dB, same Mac).

## Channel identity: the family ID (`techniques/identity.py`)

The opening, the channel-name beat and the chapter marks of "Raking Light", in two styles that the owner (or an agent) picks per video.
Contract and numbers: `docs/design/2026-11-18-identity-raking-light.md` (sections 2 to 5); moving mock-ups: `docs/design/2026-11-18-d13-identity-mock.html`.

| id | kind | style | what it draws |
|---|---|---|---|
| `ID-OPEN-01` | overlay | raking | the opening: black, the picture rises to `floor`, a band of light sweeps across and leaves it at `wake`, then 100 % (nominal 9.0 s) |
| `ID-LABEL-01` | overlay | raking | two-line artwork label bottom left, no strip, soft shadow (4.5 s) |
| `ID-BRAND-01` | base | raking | the channel name written by a band over the dimmed picture (5.0 s) |
| `ID-MARK-01` | base | raking | one chapter-mark line written by a band, then the picture is released (3.2 s) |
| `ID-OPEN-02` | overlay | dim | the frame dims, the title (italic) and a small "ARTIST · YEAR" line fade in, then out (5.0 s) |
| `ID-BRAND-02` | base | dim | the channel name fades in over the dimmed picture, then out (4.0 s) |
| `ID-MARK-02` | base | dim | one chapter-mark line fades in over the dimmed picture (3.0 s) |

`style/gae/style.json` has a block `identity` (`channel_name`, `default_style`, and per style the technique of each role `open`, `label`,
`brand`, `mark`, the `mark_transition` and the `nominal` start and length of each role); the applier reads it, never constants of its own.

Rules that hold for all seven (and that a new technique of the family must keep):

- **Nominal timeline, scaled.** Times in the params are nominal seconds from the start of the element (the overlay; the shot for a base
  technique). An element shorter than its nominal length (`nominal_s`, or the sum of its own times for `ID-OPEN-01`, `ID-MARK-*`) scales every
  time by actual / nominal; a longer one keeps the nominal times (the brand beats hold their last state and fade out at the real end; opening and
  marks end plain). An element is meant to be >= 1.5 s (`timing.min_s`, `style.identity.min_element_s`).
- **The picture is CAM-01's.** The four base techniques derive from `camera.MatteShot`: same `camera` keys, slot `image` and `shadow`, same `view()`,
  so overlays work on them. Light and text come after the picture. With neutral light (`floor`/`wake`/`dim` = 1, no text) the frame equals CAM-01's.
- **Light is a gain on brightness**, never a box or strip: `vfx.Band` (below) for the raking style, a smoothstep dim for the dim style.
- **Text** is one line, EB Garamond, with a soft shadow, placed by cap height in percent of the frame height (the font size comes from the real
  glyph H of the font, `vfx.cap_ratio`) and centred at `y_pct` (the middle of the capitals). A line wider than 88 % of the frame is made
  smaller, never wrapped. Capital-only lines (channel name, small-caps line) are upper-cased by the renderer and tracked per letter.
- **Revealed by the band** means: the opacity of the text at a pixel is the largest value the band's mask has had there so far. For a band that
  moves in one direction at constant speed that is `Band.reveal(s)`: 1 behind the band's centre line, the band's own shoulder ahead of it. No
  accumulation over frames, so a frame is a pure function of time.

### The band primitive (`vfx.Band`)

`Band(w, h, width_pct, feather, angle_deg, direction)`: a strip with straight edges tilted `angle_deg` from the vertical ("/" for positive), a
plateau of full brightness (`core`) and smoothstep shoulders (`edge`). `width_pct` is the width at half brightness, `feather` the part of it that
one shoulder takes. It moves along the axis perpendicular to its edges; the progress `q` runs 0..1 from just off the canvas on the entering side
to just off the canvas on the leaving side (with a 13 % run-in), at constant speed. `s` is the signed distance in px ahead of the centre line.
`Band.light(frame, q, ahead, wake, warm)` multiplies the frame (in place) by `ahead` in front of the band, 1 in it, `wake` behind it, and adds the
warm screen tint; the gain is a map at 1/4 resolution enlarged bilinearly (as `spotlight` does) and only the columns where it varies are touched.
`Band.reveal_box(q, x0, y0, x1, y1)` gives the reveal mask of a text box; `vfx.composite_layer_masked(frame, layer, mask_fn, env)` draws a
text layer through it. Measured on the Windows server (1080p frame, warm caches): see `docs/qa/FIX_identity_engine.md`.

### Font kinds

`vfx.font(kind, size)` knows three bundled kinds besides the old system faces: `eb_regular`, `eb_italic`, `eb_medium` = `EBGaramond-Regular.ttf`,
`-Italic.ttf`, `-Medium.ttf` in `style/gae/fonts/` (static files from github.com/octaviopardo/EBGaramond12, SIL Open Font Licence in `OFL.txt` next to
them). They load from that folder on every machine; a missing or unreadable file raises `vfx.BundledFontError` (a `FileNotFoundError`) that names the
file and the folder. There is no fallback to another face and `fonts.map` of style.json cannot replace them. The file size is part of
`font_signature()`, so a replaced file never returns a stale text layer.

### Tests and previews

`tests/engine/test_identity.py` draws frames of a flat grey (or black) picture that fills the canvas and measures: band position, the three zones,
text only behind the band, the dim levels, end state = plain picture, time scaling, cap heights, fonts, every param at min and max.
`tests/engine/identity_lab.py` adds one item per ID technique to a copy of `projects/technique_lab` for the registry sweeps. Preview clips of the
family are 640x360, 30 fps, as long as the nominal timeline; since the server gets its code by `git pull`, `style/gae/previews/*.mp4` is tracked
(`.gitignore` no longer ignores it).

## Lists of records: the parameter type `items`

A param of type `items` holds a list of objects whose fields the registry entry declares (contract `docs/design/2026-11-18-explainer-components.md` section 3).
The entry carries `fields` (each: `name`, `type`, `required`, `default`, `min`, `max`, `values`, and for text `pattern` + `pattern_hint`) and the usual
`min_items` / `max_items`. Field types: `string`, `number`, `enum`, `bool`, `lonlat` (`[longitude, latitude]`, -180..180 and -85..85), `ref` (a region
name of the shot's picture or a pixel point, checked against `regions` like a `point`) and `at` (seconds from the start of the element as a number, or a
word anchor `{"w": index, "off": s, "text": word}`, `{"t": s}` or `{"rel": 0..1}`).

* **Validation** (`registry.check_items`): the first problem of the first bad item, as `(code, args, message)`; the message and the args name the item
  (`item 2 (Lucca)`, `index` 1) and the field. Codes: `param_not_items`, `item_not_object`, `item_unknown_field`, `item_field_missing`, `item_field_bad_type`,
  `item_field_below_min`, `item_field_above_max`, `item_field_not_in_values`, `item_field_bad_form`, `item_field_bad_lonlat`, `item_field_bad_at` (all listed in
  `storyboard.ISSUE_CODES`, each with a Vietnamese sentence in `sbissues.js`). Rules between params (a route end names a place, an ISO code exists) go in a
  classmethod `check_params(params) -> [(param, code, args, message)]` of the renderer; `validate_params` calls it over the merged params when the per-param
  checks found nothing, so the rule "what validate accepts can be drawn" holds across params too.
* **Defaults**: `registry.merged_params` fills every missing field of every item from the field default and collapses line breaks of text fields, so a renderer
  never meets a missing field (`R.fill_items`). The registry default of the param is a list of complete items.
* **Anchors**: `storyboard.resolve` resolves a word anchor in an `at` field the way a camera key's `at` is resolved (`_t` = absolute seconds; `rel` counts from the
  element's own start to its end); `validate` reports `item_anchor_invalid` / `item_anchor_stale`. The renderer turns an `at` into seconds from its own start with
  `R.at_seconds(at, self.t0)`. `R.items_at_fields(spec)` lists where anchors can sit.
* **Page**: `formgen.js` (pure: `newItem`, `addItem`, `removeItem`, `moveItem`, `setItemField`, `itemsProblem`) and `formui.js` (rows: one input per field, add,
  remove, up, down; a time field offers seconds or "= playhead word"). Every other param type's form is unchanged. Tests: `tests/editor_frontend/items.test.mjs`.
* **Catalogue** (`bti/draft/techniques_md.py`): prints the fields, e.g. `places:items(1..12)[{id:string*, name:string*, lonlat:lonlat*, at:at[0..600]=1.0, ...}]`.
* An element of the families `ID-`, `MAP-`, `KEY-`, `TIME-`, `NUM-`, `TREE-`, `STATE-`, `DOC-` shorter than its technique's `timing.min_s` is the error `element_too_short`.

## One moment: the parameter type `at`

A param of type `at` is ONE moment: a number of seconds from the start of the element (held to the param's `min` and `max`), or a word anchor `{"w": index, "off": s, "text": word}`,
`{"t": s}` or `{"rel": 0..1}` (a word, so that the moment lands on the word that names it). It is validated like the `at` field of an item (`param_bad_at`, `param_below_min`,
`param_above_max`), resolved by `storyboard.resolve` in `_t` (absolute seconds, `rel` counts over the element) like every other anchor, and checked by `validate` (`stale_anchor`,
`anchor_invalid`, with `param` in the args and no `index`). A renderer reads it with `registry.at_seconds(self.p["name"], self.t0)` (seconds from the start of the element);
`registry.at_params(spec)` lists the names. The page (`formgen.js`, `formui.js`) edits it as "seconds | word" with a number field and the button "= đầu phát" (the word at the playhead),
the same control as an `at` field of an items row. `MAP-01.region_at` is the first user; a technique with a single-moment param declares `"type": "at"` with `min`, `max` in seconds.

## The explanatory devices `TIME-01`, `TREE-01`, `STATE-01` (`techniques/explain_base.py`)

Three base techniques, each the approved moving mock-up (`docs/design/mock/2026-11-18-explainer/components.html`, functions `timeline`, `tree`, `states`); contract
`docs/design/2026-11-18-explainer-components.md` sections 2 to 5. Dark ground `#131519`, text `#E9E2D0`, hairlines `#8D877A` (2 px for the axis and stalks, 3.2 px for the connectors),
second lines and edge labels at 72 percent, sizes as cap heights of the bundled EB Garamond. The agent gives data only; the technique solves the layout. Report with the numbers:
`docs/qa/FIX_comp_base.md`. Stills, timings and the preview clips: `python tools/explain_base/render_examples.py stills OUTDIR | timing | preview`.

* **`TIME-01`** (`items`: `date` a whole year, negative for BC, `label`, `side` auto|up|down, `at`, `accent`; `from`, `to` as text, empty = the items' range with one year of margin; `tick_every`
  0 = automatic; `focus_s`, `dim_to`, `cap_pct`). The axis grows from the left over 0.8 s (ease in and out), ticks fade in (staggered), a stalk grows over 0.35 s from its `at` (ease out), the year fades in from
  +0.2 s and the label from +0.35 s; at `focus_s` (0.8 s ramp) the accented items brighten, get a dot on the axis, and the others dim to `dim_to`. **Layout** (`solve_time`): for every item a depth first search over
  side, stalk length (three lengths above the axis, 13, 24 and 35 percent of the height, two below, 13 and 24) and label place (centred and pushed into the frame, or shifted to either side), the accented items
  first, then by date; a choice is refused when a label or year box touches another one (padding 1.2 percent of the width, 0.8 of the height), when a stalk runs through another item's box, or when a box leaves the
  frame. The first choices are the mock-up's (alternate sides, short stalks, a longer one only where two labels would touch), so the default data comes out exactly as the mock-up. Data that cannot be laid out is the
  error `time_crowded`; a date outside the axis is `time_date_outside`; `to` not after `from` is `time_range_inverted`.
* **`TREE-01`** (`nodes`: `id`, `name`, `sub`, `row`, `col` (both -1 = automatic), `at`, `strong`; `edges`: `from`, `to`, `kind` descent|marriage|link, `label`, `at`; `cap_pct`). A name fades in over 0.4 s; a connector is
  drawn over 0.7 s from `from` (ease in and out), its label fades in from +0.4 s. **Layout** (`solve_tree`, automatic when any name lacks `row` or `col`): spouses are one unit (a chain: a person has at most two
  marriages, else `tree_marriage_shape`); generations are the longest path down along descent and link edges, a source whose people all stand further down moves down next to them; an edge that skips rows gets a
  virtual node per skipped row so that it runs between the names; the order inside the rows comes from barycentre sweeps (the best of ten by number of crossings), a couple's members from where their parents stand;
  the coordinates from a weighted least-squares relaxation with minimum gaps (pool adjacent violators, symmetric Gauss-Seidel, re-centred every sweep): a parent stands over the middle of a child couple, a child straight
  below the middle of a marriage line, a small tree is spread over up to 82 percent of the width; text is made smaller (down to 64 percent) while a row is too wide, then `tree_too_big`. Descent from one of two spouses starts at
  the middle of their marriage line and is drawn once when both spouses name the same child. Connectors are right-angled: down from the upper name, across in the gap between the rows (parallel runs get lanes), down into the lower
  name. A marriage line is level with the names, between their ends. A label sits above its own horizontal run when that is long enough, else beside the longest vertical run, else where it touches least. A hand-made grid
  (`row` and `col` on every name) maps the cells onto the frame (rows evenly spaced, columns up to 20 percent of the width apart); names that touch are `tree_overlap`, married names in different rows `tree_marriage_rows`.
* **`STATE-01`** (slots `a` required with regions, `b` required; `label_a`, `label_b`, `camera`, `dissolve_s` 0.5 to 1.5, `holds` "h0; h1; ...", `first`, `label_cap_pct`, `shadow`). Both pictures are drawn as CAM-01 draws one, through the
  shot's `camera` in the pixels of `a`; `b` is scaled to the width of `a` and centred on it, so two images of one crop line up at any pixel size (a different shape is not corrected). Timeline: hold, linear dissolve of
  `dissolve_s`, hold ..., alternating from `first`; the last state is held to the end, a shorter shot cuts the schedule. A hold is exactly one picture. **The camera does not move during a change**: its clock stands still through a
  dissolve and runs faster in the holds by the time lost, so the whole move of its keys is still made by the end of the shot; `view()` returns the camera and the regions of `a`, so overlays follow. Caption: small capitals,
  tracking 0.14 em, at 4.5 percent from the left, baseline 6 percent above the bottom, soft shadow; it fades in at 0.3 s, flips through a fade at the middle of every dissolve, fades out ending 0.1 s before the end.
* A shot of these three shorter than 3 s is the error `element_too_short`. Word anchors in an item's `at` are the `items` machinery's; `focus_s` is seconds only. Tests: `tests/engine/test_explain_base.py`,
  `tests/editor_frontend/explain_base.test.mjs`, `tests/draft/test_explainers_briefing.py` (the catalogue's filled example and the briefing part).

## The atlas map `MAP-01` (`techniques/maps.py`, `geo.py`, `style/gae/geo/`)

The approved moving mock-up is `docs/design/mock/2026-11-18-explainer/components.html` (function `plate`); the renderer reproduces its look and timeline. Data it
takes: `places` (id, name, lonlat, `at`, `label_side`), `route` (from, to, `via` as `lon, lat; lon, lat`, shape, `at`, `draw_s`, head), `region_iso` + `region_label` +
`region_at` + `region_fill_s`, the views (`view_start_width_km`, `view_start_center`, `view_end_mode` fit | manual with `view_end_margin_pct`, `view_end_center`,
`view_end_width_km`, `push_s`), `sea` (`blue_grey`, `sepia`), `sea_names`, `sea_names_max`, `graticule_deg`, `grain`, `vignette`, `label_cap_pct`, `fade_s`, `seed`.

* **Projection**: Web Mercator. A view is a centre and a ground width in km at the centre's latitude: pixels per radian `s = 1920 R cos(lat0) / width_km`
  (`geo.View`). `geo.fit(points, margin_pct)` keeps the points in the middle (100 - 2 x margin) percent of the longer side (Bruges and Lucca at 19 percent: centre
  6.86 E 47.66 N, 2,348 km wide, Bruges at 38.4 / 19.0 percent). The push eases the zoom and the centre linearly in an in-out-quad progress (`push_s`), as the mock-up's `scale()`.
* **A frame** (a pure function of t, about 45 to 60 ms at 1920 px on the server): the land rings of the 1:10m file (views narrower than 1,500 km) or 1:50m file are
  filled on a canvas 96 px larger than the frame; one distance transform of the sea gives each sea pixel its distance to the coast, and one lookup table (distance to
  colour) paints the sea, the shade toward the coast (the profile of the mock-up's blurred stroke), the flat strip beside the coast and the two water lines; then the graticule,
  the ink coastline, the region tint, the dotted route and its head, grain and vignette (pinned to the screen, seeded), sea names, place marks and labels.
  Widths that live in map space in the mock-up (shade, water lines, route dots) scale with the push (`k`, held to 0.6..1.65); marks, labels and the hairlines keep their pixel size.
  Outlines whose segments are longer than 8 px (a narrow view of 1:10m data) are clipped to the canvas and have their corners cut (`maps.chaikin`).
* **Place labels** are put where no ink lies under their text box. The ink of a view is the coastline stroke, the two water lines and the outline of the region (a `Field`,
  made for five views along the push: the start, the middle, the end and between); a box is clear when none of it lies within `INK_MARGIN` (5 px) of the box, and it touches
  no route, mark, other label or frame edge in any of the five views. The eight sides are tried in the order se, ne, e, sw, nw, w, s, n at the mark's gap, then twice and three
  times as far out; when none is clear (a mark on a crowded coast, as Bruges beside the outline of Belgium), the nearest clear place on a grid of offsets (6 px apart) is taken,
  which can be 80 px or more from the mark; `label_side` forces a side. Labels get a 2 px paper-coloured halo (not in the mock-up). `r.label_at[id]` is the (dx, dy) from the mark
  to the label's left edge and baseline, `r.sides[id]` its compass name, `r.placed(place, x, y)` its box.
* **The region's name** goes inside the outline when it fits there with 6 px of clearance in all five views, else outside, beside the region on free ground (10 px off the
  fill), nearest to the region's pole first; never over ink, the route, a mark or a place label. When there is no such place the name is left out.
* **Sea names** (at most `sea_names_max`, most important first) lie wholly on water: in every view of the push where a name would be printed (its sea is big enough for the view
  and its text is inside the frame), every pixel within 4 px of the text is sea more than 8 px beyond the outer water line, and the text touches no route, mark, label or other name.
  The position is searched around the sea's listed position, inside the sea's own outline (`poly` of `seas.json`, `_in_sea`), nearest first; when there is none the name is left out
  (the Mediterranean has none in the default example, the Adriatic none in a view of 2,000 km).
* **Warnings and bounds**: a view narrower than 300 km (start or end) is the warning `map_view_coarse` (no error: the storyboard saves): Natural Earth has no detail there, and a spot
  inside a city belongs on a street-map picture from the picks. The widths that live in map space (shade, water lines, route dots) scale with the zoom since the start view but never
  above `K_MAX` = 1.617, the zoom of the default example's end view; the hairlines are the same in px at every zoom. A sea route needs `via` points in open water
  (the Venice example's are found by a shortest path over the 1:10m water, `tests/engine/test_map.py::test_the_venice_example_route_stays_on_water`).
* **Geography bundle** (`style/gae/geo/`, 2 MB, public domain, README there with sources, versions and sha256): land at 1:50m and 1:10m, countries at 1:50m with ISO
  codes, sea names with positions and outlines. Rebuild: `python tools/geo/build_bundle.py --downloads DIR --fetch` (numpy and OpenCV only; byte-identical output). Loaded once per process, no network.
* **Stills, timings and the preview clip**: `python tools/geo/render_map_examples.py stills|timing|preview`.

## Known behaviour worth knowing

- Fonts keep the benchmark's behaviour for the old kinds: Windows faces first, then the macOS fallback (Futura for `reg`/`bold`, Arial Bold, Georgia Italic); the three EB Garamond kinds of the ID family are bundled and never fall back (see above). `style.json` `fonts.stand_in_label_mac` can override the Futura path and an optional
  `fonts.map = {kind: [paths]}` replaces a whole list (`vfx.configure_fonts`). The font choice is part of every layer cache key.
- `shots[0]` also covers `t < its start`; `end` may carry `fade_s`.
- A storyboard with validation errors can still be drawn through `use_draft` (the editor needs live previews), but `save` refuses it.

## Porting a reel-only technique (parallel work rules)

Four engineers port the remaining 47 techniques at the same time. The rules that keep them from colliding:

1. **Only add files.** Put your renderers in NEW modules under `bti/engine/techniques/` (name them for your family, e.g. `layouts_grid.py`). Every module there is imported automatically
   (`techniques/__init__.py` uses `pkgutil`); modules starting with `_` are skipped. Never edit another engineer's module, `base.py`, `scene.py`, `registry.py` or `helpers.py`. If you need a new shared helper,
   put it in your own module and tell the coordinator.
2. **Never edit `style/gae/techniques.json`.** Write a patch file `style/gae/patches/<your-name>.json` (below). The loader merges patches over the registry in sorted file-name order, so use a unique name.
   `python tools/registry_merge.py` validates the merged result against the schema; the coordinator folds the patches in with `--apply` (moves them to `patches/applied/`).
3. **Test in your own lab project** `projects/lab_<name>/` (storyboard.json, timing.json, media/). Copy `projects/arnolfini/timing.json` and the images you need (or symlink `media`), write a tiny
   storyboard with shots using your techniques, and run `python -m bti.engine validate|still projects/lab_<name> ...`. Do not touch `projects/arnolfini`.
4. **Frames must be pure functions of t**, use `ctx.image` / `ctx.layer` / `ctx.cached`, seed all randomness, render at 1920x1080 (README "Caching rules"). Compare against the reel's own frame
   (`build_reel.py` `corner_frame` / the `@seg` function at t) with PSNR >= 40 dB, same Mac, and say so in your notes.
5. Add pytest cases in your own `tests/engine/test_<your_family>.py`.

### The patch file

`style/gae/patches/<name>.json` is `{"<ID>": {fields}}`. `params`, `slots`, `timing`, `engine` and `preview` REPLACE the entry's field wholesale (so include the full list). Unknown ids are an error. Example:

```json
{"CMP-01": {
  "params": [{"name": "colour_fade_s", "type": "number", "default": 1.0, "min": 0, "max": 10, "unit": "s", "values": null, "measured": null}],
  "slots": [{"name": "image", "type": "image", "required": true, "region": true}],
  "engine": {"status": "done", "available": true, "impl": "bti.engine.techniques.compare.GreyToColour", "reason": null, "notes": "ported from build_reel cmp01"},
  "preview": {"reel_start": 0, "reel_end": 6, "clip": "previews/CMP-01.mp4", "thumb": "previews/CMP-01.jpg"}}}
```
Required: `engine.available: true` with `impl` starting `bti.engine.` and `reason: null`. A param whose value cannot be empty and has no sensible default: `"default": null, "required": true`.
Param types: number, enum, bool, string, text, color, point, box, camera, asset, points (list of points: region names or `[x, y]`), lines (list of strings), items (list of records, below), at (one moment, below).

### Declaring extra slots

A slot is `{"name", "type": "image"|"video"|"text", "required", "region"}`. The shot stores `slots: {"<name>": {"asset": "<key>"}}`; read it with `self.slot_asset("<name>")` and load with `ctx.image(key)`.
Slot names `image` (main picture, the one overlay regions refer to), `left`/`right`, `tile_1..` are already used. For a second image just add another named image slot (`"background"`, `"inset"`).
A MASK is an asset of `kind: "mask"` (grey PNG, white = inside) with `"aligned_to": "<image asset key>"` (the mask may have another resolution); declare it as an image slot named `mask` and call
`helpers.mask_alpha(ctx, self.slot_asset("mask"), cx, cy, zoom)`: cx, cy, zoom are the IMAGE's camera, the result is a screen-space alpha. A VIDEO is `kind: "video"`; declare a slot of type `video` and call
`helpers.video_frame(ctx, key, t_source)` (clamped or `loop=True`; at most 3 files open). Validation only requires image/video slots to be present; check mask/video assets exist in `validate`-time by listing them in slots.

### Helper APIs (`bti/engine/helpers.py`, stable)

```python
paste(f, p, x, y); gray(f); cover_zoom(iw, ih, pw, ph); contain_zoom(iw, ih, pw, ph, pct=0.94)
tile_rects(n, cols, area=(x, y, w, h), gutter=20, caption_h=0) -> [(x, y, w, h)]
render_tiles(ctx, f, tiles, cols, area=(50, 36, 1820, 920), gutter=20, caption_px=30, sub_px=26) -> (f, rects)
    # tile = {"asset": key, "view": (cx, cy, zoom) or None (cover-fit), "matte": bool, "caption": str|None, "sub": str|None}
mask_alpha(ctx, mask_key, cx, cy, zoom, ow=None, oh=None, image_key=None) -> float32 (H, W, 1) 0..1
video_frame(ctx, key, t, loop=False) -> uint8 BGR;  close_videos()
vertical_panel(ctx, content_float32_ph_x_pw, ambient_key, ambient_src=None, pw=608, ph=1080) -> float32 canvas   # blur cached by ambient_key
text_block(ctx, lines, cx, cy, size, kind="reg", tracking=0, color=(255,255,255), line_gap=1.25, align="center", shadow=True, upper=False) -> Layer
fade_env(t, t0, t1, fade_in, fade_out)      # 0..1..0 envelope for Layer.apply(f, env, dx, dy)
```
Existing primitives you also use: `vfx.Img.view`, `vfx.compose_matte`, `vfx.Cam`, `vfx.text_layer`, `vfx.label_layer`, `vfx.spotlight`, `vfx.ring`, `vfx.blend`, `vfx.blurred_bg`, `vfx.ramp/window/ease`.

### Preview clip and thumbnail for a technique that has none

Make a 6 s (or shorter) shot in your lab project that shows the technique, then (from the repo root, with `.venv-engine`):

```
.venv-engine/bin/python -m bti.engine render projects/lab_<name> --t0 0 --t1 6 --width 640 --fps 15 -o style/gae/previews/<ID>.mp4
.venv-engine/bin/python -m bti.engine still  projects/lab_<name> 3 --width 480 -o style/gae/previews/<ID>.jpg
```
`render` writes silent H.264 yuv420p at 640x360. Check with `ffprobe -v error -show_entries stream=codec_name,width,height,duration -of csv=p=0 style/gae/previews/<ID>.mp4`. Then set the entry's `preview` in your patch
(`{"reel_start": 0, "reel_end": 6, "clip": "previews/<ID>.mp4", "thumb": "previews/<ID>.jpg"}`; `reel_*` are the old reel positions and may be 0 / the clip length for new previews).

### STABLE API (will not change; port against these)

`registry.technique`; `base.BaseRenderer`, `OverlayRenderer`, `TransitionRenderer` (constructor signatures, `render/apply/blend`, `default_params` classmethod, `self.p/t0/t1/tid/spec/slot_asset`);
`base.View`; `Ctx.w/h/sv/asset/asset_path/asset_size/image/point/layer/cached/t/raw_image_reduced`; `helpers.*` above; the `vfx` primitives listed; anchors `_t/_t0/_t1`; `Project` facade (design 8.1).

## Final-quality render (also for the Windows server)

```
python -m bti.engine render projects/<id> --t0 0 --t1 300 --quality final --threads 4 -o part1.mp4     # 1920 px, 30 fps by default
python -m bti.engine render projects/<id> --t0 300 --t1 820.8333 --quality final -o part2.mp4
ffmpeg -f concat -safe 0 -i list.txt -c copy full.mp4                                                  # parts concatenate without re-encoding
```
`--quality preview` (default; 640 px, 15 fps) uses `-preset veryfast -crf 27`; `final` uses `-preset medium -crf 15 -pix_fmt yuv420p -g 60`. Frame i is drawn at `t = i/fps` for
`i in range(round(t0*fps), round(t1*fps))` (half-open), so parts that share a boundary are frame-exact and gap-free. `--threads N` sets ffmpeg and OpenCV threads. Progress lines (`progress 35%`)
go to stdout every 5 %. Only `ffmpeg` on PATH is needed; no platform-specific paths. Python: `Project.render_range(t0, t1, out, width, fps, on_progress, quality="preview", threads=None)`.
