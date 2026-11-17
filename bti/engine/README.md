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
`min_items`/`max_items` (points/lines) and `numeric_only` (a point that cannot be a region name). `Project.draw_check` draws one small
frame per shot, overlay and transition and returns `undrawable` issues; approval runs it. A technique that fails while drawing raises
`RenderError` (shot id, overlay id, technique id) from `frame_at` and `render_range`. `bti/engine/guard.py` refuses any buffer over
four canvases. `tests/engine/test_validate_draw_sweep.py` checks the rule for all 71 techniques and all twelve param types.

## Layout

| File | Role |
|---|---|
| `api.py` | the facade (design 8.1): `open_project`, `Project`, `load_style` |
| `storyboard.py` | canonical JSON + revision, `resolve`, `validate`, atomic `save` with `history/` backup |
| `timing.py` | word lookup (`find`, `anchor_for`) and anchor resolution (`t`, `w`+`off`+`text`, `rel`) |
| `registry.py` | `@technique(id, kind)`, parameter validation against `techniques.json`, `check_registry` |
| `scene.py` | compile a resolved storyboard into a `Scene`: `frame_at`, `render_range`, transitions, end fade |
| `base.py` | the renderer interfaces, `Ctx`, and the process-wide LRU caches |
| `vfx.py` | pixel primitives lifted from the benchmark (`Img`, `Cam`, `compose_matte`, `text_layer`, `spotlight`, `ring` ...) |
| `techniques/` | one module per family: `camera`, `labels`, `annotate`, `cards`, `layout`, `diagrams`, `transitions` |

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
   Param types: `number, enum, bool, string, text, color (#rrggbb), point, box, camera, asset, points, lines`. Unknown params are errors for everyone, so list every knob. File format: `style/gae/techniques.schema.json`.
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

## Known behaviour worth knowing

- Fonts keep the benchmark's behaviour: Windows faces first, then the macOS fallback (Futura for `reg`/`bold`, Arial Bold, Georgia Italic). `style.json` `fonts.stand_in_label_mac` can override the Futura path and an optional
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
Param types: number, enum, bool, string, text, color, point, box, camera, asset, points (list of points: region names or `[x, y]`), lines (list of strings).

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
