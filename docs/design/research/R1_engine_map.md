# R1 - Engine map of `demo_runs/claude_code`

Date: 2026-11-16. Scope: read-only study of the Arnolfini episode (`build_v2.py`) and the technique reel (`build_reel.py`), plus a local Mac feasibility test. Nothing under `demo_runs/claude_code/` was modified. No ssh/scp, no network, no paid API. Experiments live in `.scratch/r1/`.

## 0. TL;DR

- The code is **not data-driven**. The episode storyboard is ~180 lines of Python (`build()`, build_v2.py:348-526) with 58 `painting_shot(...)` calls, hard-coded source-pixel coordinates and 125 literal narration phrases. The only real data input is `v2/timing2.json` (word times). `v2/shots_final.json` is a lossy **output** of the build, never read back by the renderer.
- **Stills and ranges already work on the Mac, unmodified**, at about 20 ms per 1080p frame (median) and 30 ms per frame including resize + x264 for a 640x360 range. A `frame_at(t)` closure exists (`frame_fn`, build_v2.py:548) and is stateless per frame.
- The engine pieces (`lib/vfx.py`, 303 lines) are small, clean and liftable. The gap is the declarative layer: a schema, a loader, an overlay registry, and de-hardcoding of 1920x1080 and of the asset keys and anchor points.
- The reel already has a de-facto registry (`@seg(id, name, dur)` -> `SEG` list, build_reel.py:120-130), but each technique is a one-off function with literals inside; 56 functions, all of which render locally.

## 1. Primitive inventory (`lib/vfx.py`, the only library file)

Conventions (module docstring, vfx.py:1-5): frames are **BGR** (OpenCV order), `uint8` at the output, `float32` while compositing (shape `H x W x 3`). Canvas constants `W, H = 1920, 1080` (vfx.py:11) are baked into defaults. `cv2.setNumThreads(CV_THREADS env, default 4)`. Source images are loaded with `cv2.imread` (BGR). PIL text layers are RGBA and converted to BGR in `Layer`.

| Primitive | Signature (line) | What it does / I-O |
|---|---|---|
| fonts | `font(kind, size)` (:22) | kind in `reg, bold, sans_bold, serif_it`. Candidate lists try Windows paths first (`C:\Windows\Fonts\GOTHIC.TTF` = Century Gothic, `GOTHICB.TTF`, `arialbd.ttf`, `georgiai.ttf`), then macOS fallbacks (Futura.ttc index 0 for reg / 2 for bold, Arial Bold, Georgia Italic, Helvetica), then PIL default. Returns `ImageFont`. |
| easing | `EASE` dict (:38), `ease(name,p)` (:50), `ramp(t,t0,dur,name)` (:54), `window(t,t0,t1,fin,fout)` (:61) | Names: `linear, in_quad, in_cubic, out_cubic, out_quad, inout_cubic, inout_sine`. `ramp` = 0->1 envelope; `window` = 0..1..0 trapezoid envelope. Pure scalars. |
| source image | `class Img(path_or_arr, name)` (:67) | Loads full-res BGR and builds an area-averaged half-size pyramid down to min side >= 256 (A = 4386x6000 -> 5 levels). `view(cx,cy,zoom,ow=W,oh=H)` (:80) picks the pyramid level so the warp scale stays 0.7-1.4, `cv2.warpAffine` INTER_CUBIC, returns `(frame BGR uint8 oh x ow x3, alpha float32 oh x ow x1 (analytic AA rectangle), (x0,y0,x1,y1) screen rect)`. `to_screen(px,py,cx,cy,zoom)` (:103) maps source px to screen px. |
| backdrop | `backdrop(ow,oh)` (:111) | Cached (per size) radial near-black gradient (#1e centre -> #06 edge) with grain; float32 BGR. |
| matte | `compose_matte(img,cx,cy,zoom,ow,oh,shadow=True)` (:125) | Painting over the backdrop with a soft drop shadow (shadow computed at 1/4 res, blur, upsample). Short-circuits to the plain view if the image covers the canvas. Returns float32 BGR. |
| camera | `class Cam(keys)` (:143), `.at(t) -> (cx,cy,zoom)` | keys = `[(t, cx, cy, zoom, ease_to_next)]`; pan linear in eased p, zoom interpolated in log space; clamps outside the range. |
| overlay layer | `class Layer(rgba, x0, y0)` (:164), `.apply(frame, env=1.0, dx=0, dy=0)` | Pre-rendered RGBA (PIL order) -> BGR float + alpha; alpha-blends into the frame in place with an envelope and pixel offset, clipped to the frame. |
| text | `_tracked(draw,xy,text,font,fill,tracking,anchor)` (:187); `text_layer(text,cx,cy,size=90,kind='reg',tracking=6,color,sub=None,subsize=30,w=W,h=H,shadow=True)` (:218) | Letter-spaced centred text (+optional sub line, blurred drop shadow) on a transparent full-frame RGBA, cropped to its bbox -> `Layer`. Returns a 1x1 empty layer if the text is entirely off-canvas (fix for the reel TXT-02 crash). |
| label strip | `label_layer(title, sub=None, y0=.70, h=140, x_text=.07, w=W, hh=H)` (:199) | Dark translucent strip (alpha .80, right 22 % fades out), white upper-case title 58 px + grey sub 32 px -> `Layer` at `y0*hh`. |
| spotlight | `spotlight(frame,sx,sy,rx,ry,a,floor=.35,feather=.55)` (:244) | Darkens everything outside a feathered ellipse (screen coords) to `floor` gain; mask computed at 1/4 res then upsampled; `a` is the ramp 0..1. Returns frame. |
| ring | `ring(frame,sx,sy,r,prog,alpha=.75,thick=13,color=(205,205,205))` (:259) | Anti-aliased arc drawn on clockwise from the top, `prog` 0..1 (2x supersampled mask). In place + returned. |
| helpers | `blend(a,b,p)` (:278), `to_u8(f)` (:282), `hline(frame,cx,y,w,th,alpha)` (:300), `blurred_bg(img_bgr,ow,oh,sigma=38,dark=.38,center)` (:286) | cross-dissolve, float->uint8 clip, rule line, 16:9 cover-crop heavily blurred darkened vignette (title cards). |

Episode-level primitives (build_v2.py), all callables with the uniform signature `ov(frame, t, cx, cy, z, img) -> frame` and an `.info` dict:

| Class / builder | Line | Parameters | Draws |
|---|---|---|---|
| `TL` | :47 | `TL(path)`; `.find/.at/.after(phrase,nth,off,wi)`, `.chapter_start/_end(name)`, `.card(text)` | Reads `timing2.json`; flattens all words into `(norm, s, e)`; **phrase -> seconds** lookup. |
| `Lbl` | :109 | `(title, sub, t0, dur=3.2)` | `label_strip` with `window(t,t0,t0+dur,.1,.12)`; strip at y 79-93 %. |
| `Spot` | :118 | `(pt, rx, ry, t0, t1, floor=.20, ramp_in=.5, ramp_out=.5)`; `pt` may be callable | `spotlight` at a **source-pixel** point mapped through the camera. |
| `RingOv` | :132 | `(pt, r_src, t0, hold=2, fade=.4, draw=.5)` | `ring` anchored to a source point/radius; alpha .75. |
| `ScreenText` | :148 | `(text,t0,t1,pt=None,screen=None,size=44,fin,fout)` | plain white text at a source point or fixed screen pos. |
| `DimOv` | :166 | `(t0,t1,zz)` | AN-05 ruler lines + "60 cm / 82 cm / OIL ON OAK PANEL" (text literals inside the class). |
| `Years` | :195 | `(items=[(text, sub, x, t0, t1)])` | big year captions with sub text. |
| `painting_shot` | :212 | `(t0,t1,keys,overlays,key='A',desc,ids,words,params)` | **The generic shot**: `Cam(keys)` -> `compose_matte(IM(key),...)` -> overlays. Returns `dict(t0,t1,fn,effect,ids,image,params,words)`. |
| `still_shot` | :227 | `(t0,t1,key,title,sub,push,center,z0,cam_keys,overlays,hold=4.0)` | Context still with label, 4 s hold, then falls back to a "back to painting" shot. |
| `card_shot` | :241 | `(t0,t1,text)` | Black frame + auto-sized text at y 88 %, in at +0.2 s, out at +1.7 s. |
| `title_card_shot` | :263 | `(t0,t1,bgimg)` | Blurred artwork + 3 text layers + rule (strings hard-coded). |
| `map_shot`, `dia_mirror_shot`, `split_shot` | :277, :304, :321 | tiny parameter sets | Procedural map with route, convex-mirror diagram, split-screen slide-in with synchronised push-ins (all text and geometry hard-coded). |
| `frame_fn(T)` | :548 | returns `(frame_at(t), shots)` | `bisect` over shot start times; calls `shots[i]["fn"](t)`; applies the global end fade (last 1.6 s); `to_u8`. |

Reel-level helpers (build_reel.py:55-130): `S()` loads/caches images and builds stand-in assets (couple cut-out + mask, inpainted "plate", PDF images); `view/matte/cview` wrappers; `paste, gray, txt (cached text_layer), chip (corner label), vpanel (9:16 panel in 16:9 with blurred fill)`; `seg()` decorator; `two_panels`.

## 2. Data model of the episode

### 2.1 `v2/timing2.json` (the real input)
Top level keys: `atempo, wpm_first_to_last_incl_pauses_and_cards, wpm_speech_only, span_s, words (1971), alignment {tool, matched, total, fake}, cards, beats (91), end (820.8333)`.

```json
"beats":[{"group":"1","chapter":"COLD_OPEN","text":"Most people will tell you ...","start":0.35,"end":5.75,
          "raw_start":0.0,"raw_end":5.4,
          "words":[{"w":"Most","s":0.35,"e":0.85,"src":"whisper","est":0.35}, ...]}]
"cards":[{"text":"__title__","t0":74.31,"t1":76.91},{"text":"THE MERCHANT CITY","t0":77.21,"t1":79.21}, ...]  // 7 cards
```
Chapter and title cards are **only** timed here (`cards`); the card text strings are keys that `build()` looks up with `T.card("THE ROOM")`. `__title__` is the title-card sentinel. Chapter names are in `beats[].chapter` (COLD_OPEN, THE MERCHANT CITY, THE ARNOLFINIS, FASHIONS AND FABRICS, THE ROOM, THE MIRROR, THE ALCHEMIST, CLOSING). `v2/chapters.json` is just word/beat counts per chapter, not used by the renderer.

Upstream (word-level): `v2/voice/voice_J{1,2,3}_words.json` = `{sample_rate, word_timestamps:[{word,start,end}], beats:[text], seconds}` (TTS-side estimates, evenly spread); `v2/voice/whisper_J*.json` = flat list `[{"w","s","e"}]` (faster-whisper small.en, 700 words in J1). `scripts/make_timing2.py` merges them (difflib match, 1966/1971 matched, rest interpolated; `src` field says `whisper` or interpolated) and shifts to final time via `v2/server/audio_spec2.json` (`{atempo, end, segments:[{wav, raw_start, raw_end, final_start}]}`) and `beats_v2.json` (`{group:{chapters, beats[]}}`).

### 2.2 `v2/shots_final.json` (derived, 82 entries)
Written by `build_v2.py timeline` (:571). It is a **report**, not a storyboard.

```json
{"t0":29.17,"t1":38.28,"effect":"dimension annotation (AN-05) on the matte painting",
 "ids":["AN-05","STATIC-01"],"image":"A",
 "params":{"hold_s":4.5,"overlays":[{"annotation":"AN-05 82 cm x 60 cm, OIL ON OAK PANEL","t0":29.87,"t1":34.37}]},
 "words":"It is small ... eighty-two centimetres tall and sixty wide"}
```
Fields: `t0,t1,effect,ids,image,params,words`. There is **no shot kind field**; the kind is implicit in `effect` text ("chapter card", "context still (two-line label)", "title card (blurred artwork)", "route map (procedural stand-in)", "split-screen comparison...", painting shots otherwise). Overlay entries (`params.overlays[]`) are the `.info` dicts of `Lbl/Spot/RingOv/...` and are lossy: they record e.g. `{"spotlight":[[2220,1790],440,440],"t0":38.62,"t1":39.72,"floor":0.2}` or `{"ring":[x,y],"r_src":..,"t0","draw_s","hold_s","fade_s"}` or `{"label":"Dog at her feet","t":..}`, but **camera keyframes are not saved** (only prose like "from_z/to_z/ratio/ease"), so a shot cannot be rebuilt from this file. `image` is the short key "A" (Arnolfini), "V" (Van der Paele) or a context-image key; 18 of the 82 are not painting shots. Word anchoring is by prose only (`words`); the real anchor is the Python call `tt("phrase", nth, wi, off)`.

`timeline.json` (top level `final_demo, sources, music, voice`) is the delivery manifest written by `scripts/make_timeline2.py`: `final_demo{duration_s:820.83, resolution:1920x1080, fps:30, cards, shots[{start,end,duration_s,effect,...}]}`, `sources{key: {url, licence, author, size}}`. It does **not** contain the reel; reel times come from `ref/server/technique_reel_segments.json` (`[{id,name,t0,t1,render_s}]`) or by summing `dur` over `SEG`.

### 2.3 Where images and regions are named
- Image keys: `IM(key)` (build_v2.py:34): `"A"` -> `assets/commons/arnolfini_commons.jpg` (4386x6000), `"V"` -> `paele_commons.jpg` (4169x3249), anything else -> `assets/context/<key>.jpg` (bruges, blue_cap, ghent, turban, giovanni_berlin, tomb, rogier, matsys, durer, meninas). `assets/context/context_images.json` holds provenance per key.
- Regions are **module constants of source-pixel centres for image A** (build_v2.py:16-28): `MIRROR=(2220,1790) HANDS=(2420,2540) DOG=(2098,5446) RUG=(2388,4200) INSCR=(2220,1390) R1,R2, LIT, SNUF, ORANGE, PATTENS, BOOTS, LION, STM, BRUSH, AMBER, HAT, TABARD, FURSLEEVE, BLUESL, RUFFLES, BEDP, COSFACE, GIOFACE`, plus `FULL=(2193,3000)`, `ZW=1920/4386`, `ZF=0.172`. Radii are inline numbers (e.g. `RingOv(DOG, 330, ...)`). No JSON anywhere names a region.
- Masks (`assets/masks/couple|costanza|giovanni|dog.png`) are used only by the reel.

### 2.4 How much is data-driven?
Estimate: **~10-15 % data, ~85-90 % hard-coded** (by the content that defines this video).
- Data-driven: word/beat/chapter/card times (timing2.json) -> `T.at(...)`; global duration `T.end`; shot contiguity (`contiguous()`, :529, forces `t1 = next t0`).
- Hard-coded (examples): all 78 shot-builder calls inside `build()` (58 `painting_shot`, 11 `still_shot`, 6 `card_shot`, 1 each of map/split/mirror/title); 125 phrase literals such as `tt("Notice the mirror", wi=2) - .12`; every camera keyframe tuple, e.g. `(t_mirror, 2220, 1650, .72, "inout_cubic")`; all overlay choices (`Spot(MIRROR,440,440,...)`, `RingOv(R1,82,...)`); label texts (`Lbl("Dog at her feet",...)`); title card strings, map, diagram and split-screen geometry; chapter order and card names.
- Also hard-coded: nearly every size is in absolute 1080p pixels via the global `W,H` (DimOv, Years, Lbl, split_shot panel rects, map).

Per-line: `build()` is lines 348-526 = 179 of 597 lines (30 %) and essentially 100 % content; the ~170 lines of overlay/shot classes (95-345) are reusable engine code that happens to contain content literals in 5 of them.

## 3. How rendering is invoked

CLI (`build_v2.py` docstring lines 3-6, `main()` :563):
```
build_v2.py still    <timing2.json> <out_dir> t1 t2 ...          # PNG per time, always 1920x1080: "t%07.2f.png"
build_v2.py render   <timing2.json> <out.mp4> [--t0 S] [--t1 S] [--size WxH] [--fps N]   # defaults 1920x1080, 30 fps, whole episode
build_v2.py timeline <timing2.json> <shots.json>                  # writes shots_final.json
```
`build_reel.py`: `still <out_dir> ID[:t] ...` (default t = 0.6*dur), `render <out.mp4> [--fps --size --only ID,ID]`, `timeline <out.json>`.

- **One frame at t**: yes. `frame_fn(T)` returns `frame_at(t)` (:553) -> `uint8 BGR 1080x1920x3`. `still` mode calls it. It is stateless per frame (no inter-frame state; only memo caches `_IMG`, `_TLC`, `_BD`). Reel: `corner_frame(entry, t)` (:~940).
- **Time range**: yes, `render --t0 --t1` (:573-593). It loops `i in [round(t0*fps), round(t1*fps))`, calls `fa(i/fps)`, resizes with `cv2.resize(..., INTER_AREA)` if `--size` differs, and writes `fr.tobytes()` to an ffmpeg pipe. There is **no size parameter** in the renderer: everything renders at 1080p and is downscaled afterwards.
- **Encoding**: `ffmpeg -y -v error -f rawvideo -pix_fmt bgr24 -s WxH -r fps -i - -c:v libx264 -preset medium -crf 15 (27 if not 1080p) -pix_fmt yuv420p -g 60 -threads 4 out.mp4`. Plain `ffmpeg` from PATH. No audio at this stage: audio is built by `v2/server/audio_job2.py` and muxed by `v2fin.bat` (concat of 3 parts, then `-c:v copy -c:a aac -b:a 192k -c:s mov_text`).
- **Windows-server dependencies** (what exists only there):
  - `.bat` wrappers (`v2/server/v2r1/2/3.bat`, `v2prev.bat`, `v2fin.bat`) hard-code `D:\bench\claude_code`, `D:\code\comic-book-pipeline\.venv\Scripts\python.exe`, a lock dir `D:\bench\_heavy.lock`, and env `CV_THREADS=4`. They split the render into 3 parts (cut at the FASHIONS and MIRROR cards) and concat.
  - TTS (`tts_v2.py`, Chatterbox from `comic-book-pipeline`, voice reference file) and the audio job. The render itself does not need the server.
  - Fonts: `lib/vfx.py` lists Windows Century Gothic/Arial/Georgia first, but **already has macOS fallbacks**, so no code change was needed locally. Result: labels render in Futura instead of Century Gothic (glyph widths differ; see section 4).
  - ffmpeg build: any with libx264 (Homebrew ffmpeg 8.0.1 works).
  - Whisper alignment (`venv_align`, `hf_cache`) was already Mac-side.

## 4. Local feasibility test (Mac, M-series, 10 cores, 16 GB)

Setup: copied `lib/`, `build_v2.py`, `build_reel.py`, `timing2.json`, `assets/{commons,context,masks,pdf_images}` into `.scratch/r1/` (86 MB + pdf_images). Ran with system `python3` (cv2 4.11, numpy 2.3, Pillow 12.3). **No code changes.**

Result: **works out of the box.**
- `build_v2.py still timing2.json out/stills 40 310 560`: 3 stills, 2.4 s wall including interpreter start and one-time image load, peak RSS 1.44 GB (measured with `/usr/bin/time -l`).
- Per-frame (1080p render, `.scratch/r1/bench.py`): t=40 s first call 0.22 s (cold: JPEG decode + pyramid of image A), then 0.02 s warm; t=310 s 0.03 s; t=560 s 0.01 s. Downscale to 960x540 with INTER_AREA adds ~1 ms. Timeline build `make(T)` (all 82 shot closures) takes <2 s.
- All 82 shots sampled at mid-time (`bench2.py`): median 21 ms, p90 25 ms, max 194 ms (shot 0, cold image load); slow ones are procedural: route map 123 ms, split-screen 82 ms (two pyramids).
- Looked at the PNGs (`.scratch/r1/out/960/still_{40,310,560}_960x540.png`): t=40 s = mirror/inscription close-up with the spotlight dimming the surround; t=310 s = pan down the green dress with the "GREEN WOOL GOWN" label strip; t=560 s = full painting with mirror push beginning. All sensible and framed as in the video.
- Fidelity check against the actual `final_demo.mp4` frames (ffmpeg scaled to 960x540): PSNR 34.6 / 24.7 / 39.2 dB. The only large differences at t=310 are the label glyphs (font substitution Futura vs Century Gothic; max diff confined to a 330x24 px box at y 442-465). Geometry, camera and spotlight match. Substituted font: `/System/Library/Fonts/Supplemental/Futura.ttc` (index 0) via the existing fallback, nothing installed.
- Range: `build_v2.py render timing2.json out/cli_range.mp4 --t0 300 --t1 305 --size 640x360 --fps 30` -> 150 frames, **3.6 s render (5.5 s wall incl. startup)**, h264 640x360 verified with ffprobe. At 10 fps (preview-grade): 50 frames in 1.4 s. In-process timing: ~0.03 s/frame including resize and `veryfast` x264.
- Reel: all 56 segment functions render at t=0.6*dur locally (`bench3.py`, 0 errors, `S()` setup 0.33 s, peak RSS 1.19 GB). Warm median 15 ms/frame; the five SHORT-* segments cost 0.84-0.93 s/frame (vpanel blurs a 1920x3410 image with sigma 38 each frame), STATIC-07 0.1 s, AN-04 0.06 s. Montage: `.scratch/r1/out/reel_montage.jpg`; every thumbnail looks as the reel intends, including the known defects.
- Blockers found: **none**. First attempt of the reel failed only because I had not copied `assets/pdf_images/` (reel needs it); not a code problem. Hidden risks, not blockers: font mismatch; 1.4 GB RSS (see 6); `still` CLI has no size option.

## 5. Reel mapping (56 techniques)

Catalogue: `docs/research/great-art-explained/corpus/EFFECTS_CATALOG.md` (not re-read in full; IDs taken from `@seg` ids and `capabilities_report.md`). All functions have signature `(t, d) -> float32 BGR frame`, `t` = seconds into the segment, `d` = segment duration (the `@seg` argument). Times from `ref/server/technique_reel_segments.json` (total 320.5 s, matches ffprobe). The "ms/frame" column is a warm local 1080p timing of `corner_frame` (includes the corner chip). Status is copied from `capabilities_report.md` (35 done / 21 partial). Note that `capabilities_report.md` has stale v1 text elsewhere ("final_demo 81 s") and its "Where: final" column refers to v1 shots, not v2.

| ID | Function (build_reel.py line) | Key parameters | t0-t1 in technique_reel.mp4 (s) | Status (capabilities_report) | Local warm ms/frame 1080p |
|---|---|---|---|---|---|
| CAM-01 | `cam01` (:136) | matte(A); cx,cy=(2300,3050); z=0.52*1.142^ease; 6 s | 0.0-6.0 | done | 10 |
| CAM-02 | `cam02` (:142) | plate + couple cut-out+mask; fg zoom 1.30x, bg 1.06x, pan +60/+380 px; inout_sine | 6.0-12.0 | partial: Clean empty-room plate not available; plate is cv2.inpaint+blur stand-in, GrabCut mask rough (wall chunk next to Giovanni). Would need hand-painted layers | 29 |
| CAM-03 | `cam03` (:152) | z 0.62->0.47 (1/1.31), in_quad, centre (2220,1900)->(~2200,2600) | 12.0-19.0 | done: final pull-backs are 2-5x faster than the channel because the 90 s budget | 11 |
| CAM-04 | `cam04` (:163) | zoom .90, linear cy ramp 19 px/s | 19.0-25.0 | done | 10 |
| CAM-05 | `cam05` (:170) | z 0.44->0.57 (1.30x), centre +240/+350 px, linear | 25.0-31.0 | done | 10 |
| CAM-06 | `cam06` (:178) | full painting + label_layer("The Arnolfini Portrait","Jan van Eyck, 1434"); window(2.0,5.2) | 31.0-37.0 | done | 23 |
| TR-01 | `tr01` (:186) | matte A -> view V, linear dissolve 1.0 s at t=2 | 37.0-42.0 | done | 29 |
| TR-02 | `tr02` (:194) | 900x740 panels, out_cubic slide 0.8 s in, in_cubic out | 42.0-47.5 | done | 13 |
| TR-03 | `tr03` (:208) | warpPerspective shutters (A halves) over V, 84 deg hinge, 3.2 s | 47.5-53.5 | partial: Shutter art is a stand-in (no real triptych); timing only coarse in reference | 36 |
| TR-04 | `tr04` (:230) | hard cut at t=2.4: full -> crop (2420,2480) z .75 | 53.5-58.5 | done | 11 |
| LAY-01 | `lay01` (:249) | two_panels A / V + captions (900x740) | 58.5-63.5 | done | 14 |
| LAY-02 | `lay02` (:257) | 4 tiles (MIRROR,HANDS,DOG,(2193,880)) stagger fade, connector lines | 63.5-69.0 | done | 15 |
| LAY-03 | `lay03` (:274) | 5 columns 360x1000: scan/print/grey/sepia/contrast | 69.0-74.0 | partial: Reference columns are five different works; stand-in uses one painting in 5 treatments | 42 |
| LAY-04 | `lay04` (:296) | matte crop + 560x315 inset of V, push | 74.0-79.5 | done: Inset shows a painting crop, not footage | 11 |
| LAY-05 | `lay05` (:316) | cut-out held, 4 backgrounds cross-faded | 79.5-85.5 | partial: Rough mask; backgrounds are paintings, not footage | 44 |
| LAY-06 | `lay06` (:329) | 6 translucent 260 px strips of A over matte | 85.5-91.0 | done | 23 |
| LAY-07 | `lay07` (:344) | 2x2 grid + circular translucent overlay (r 360) | 91.0-96.5 | done | 33 |
| LAY-08 | `lay08` (:356) | mirror tile mirrored 4x4 kaleidoscope | 96.5-101.5 | done | 9 |
| HI-01 | `hi01` (:367) | matte (2300,2300) z .55->.61; spotlight on HANDS rx=380z+60, ry=280z+60, floor .35 (default) | 101.5-107.5 | done: Reference surround level only estimated by eye | 15 |
| HI-02 | `hi02` (:375) | plate + two halves of cut-out slide in from edges, out_cubic | 107.5-114.5 | partial: Stand-in plate is smeared; hook in final uses a clean detail move | 54 |
| HI-03 | `hi03` (:395) | colour kept inside mask, rest greyscale .75, 1.0 s | 114.5-120.0 | done: Mask rough | 30 |
| AN-01 | `an01` (:406) | ring on HANDS r230 and (1130,1980) r190, z .85, thick 13 | 120.0-125.5 | done | 14 |
| AN-02 | `an02` (:417) | contour of couple mask drawn progressively (3 s) | 125.5-131.5 | partial: Outline follows the rough mask, not the true silhouette | 21 |
| AN-03 | `an03` (:436) | 9 rays converging to vanishing point, staggered .35 s | 131.5-137.5 | done | 18 |
| AN-04 | `an04` (:476) | procedural map + bezier route + arrow head (_map) | 137.5-143.5 | partial: Procedural stand-in map (no map asset) | 58 |
| AN-05 | `an05` (:487) | ruler lines + "60 cm","82 cm","OIL ON OAK PANEL"; zz=.84*Z_FULL | 143.5-149.5 | done: Gallery photo backdrop not available; painting on matte instead | 22 |
| AN-06 | `an06` (:506) | thirds grid + translucent triangle (fill alpha .28) | 149.5-155.5 | done | 15 |
| AN-07 | `an07` (:521) | up to 9000 dots, colour sampled from base, radius shrinks, mix to image | 155.5-162.0 | done | 36 |
| TXT-01 | `txt01` (:540) | blurred_bg(pdf p30) + "THE MIRROR" size 84 tracking 14 | 162.0-166.5 | done | 5 |
| TXT-02 | `txt02` (:547) | 3 sliding serif_it quotes, 520 px/s | 166.5-172.0 | done: Font is Georgia Italic, channel font unknown | 12 |
| STATIC-01 | `st01` (:557) | matte full painting, z=Z_FULL*(1+.015 t/d) | 172.0-176.5 | done: Deliberate departure from raw black (spec forbids bars) | 22 |
| STATIC-02 | `st02` (:562) | view + bottom-left source label layer | 176.5-181.5 | done | 10 |
| STATIC-04 | `st04` (:575) | darkened crop x.38 + serif_it quote | 181.5-187.0 | done | 11 |
| STATIC-05 | `st05` (:581) | label_layer("Speaker Name","Curator, Example Museum (placeholder)", y0=.76) | 187.0-192.0 | partial: No interview footage; text is a generic placeholder | 11 |
| STATIC-06 | `st06` (:588) | _map static route | 192.0-197.5 | partial: Stand-in map | 58 |
| STATIC-07 | `st07` (:593) | 6 wedge crops (R=470) with labels in a circle | 197.5-203.5 | done | 96 |
| STATIC-08 | `st08` (:613) | 2 name labels w/ leader lines to (1233,1300) and (3500,1500) | 203.5-209.0 | partial: Labels sit over the figures heads instead of beside them (placement defect, not re-rendered) | 10 |
| STATIC-09 | `st09` (:627) | blurred_bg + "1434" size 190 tracking 16 | 209.0-213.5 | done | 5 |
| DIA-01 | `dia01` (:634) | crop with 6x6 grid + A..F letters + ray fan | 213.5-220.0 | partial: No anamorphic skull; analogue only | 8 |
| DIA-02 | `dia02` (:657) | frontal vs perspective-warped crop (getPerspectiveTransform) | 220.0-226.0 | partial: Different object | 16 |
| DIA-03 | `dia03` (:674) | 5 painted layers (oak, chalk, imprimatura, paint, varnish) + light rays | 226.0-232.5 | partial: Schematic, not a real micrograph | 6 |
| DIA-04 | `dia04` (:697) | cut-out + 3 circular piece crops flying out | 232.5-238.5 | partial: Different subject | 29 |
| DIA-05 | `dia05` (:716) | silhouette -> outline (Canny) -> photo | 238.5-244.5 | partial: No process footage | 46 |
| DIA-06 | `dia06` (:730) | isometric room wireframe + false-colour (COLORMAP_OCEAN) crop | 244.5-251.0 | partial: Simulated UV | 12 |
| DIA-07 | `dia07` (:755) | convex mirror arc + ray reflection | 251.0-257.0 | partial: Different diagram | 6 |
| CMP-01 | `cmp01` (:777) | grey vs colour crop (1233,1300) z .75 | 257.0-262.0 | done | 13 |
| CMP-02 | `cmp02` (:787) | 3 blur stages + finished mirror crop | 262.0-268.0 | partial: Stages are blur levels, not real underdrawing | 32 |
| CMP-03 | `cmp03` (:802) | white/sepia/colour 610x900 | 268.0-273.5 | done | 15 |
| CMP-04 | `cmp04` (:815) | crop vs pixel mosaic 8->32 cells | 273.5-279.0 | done | 11 |
| CMP-05 | `cmp05` (:827) | wipe between scan and PDF print at x(t) | 279.0-285.0 | done | 21 |
| FOOT-01 | `foot01` (:841) | 4 material cards + colour swatches | 285.0-291.0 | partial: No real footage | 13 |
| SHORT-01 | `sh01` (:858) | 3 stacked 608x356 strips cycling crops, vpanel() | 291.0-297.0 | done | 840 |
| SHORT-02 | `sh02` (:872) | 608x1080 crop with warpPerspective, BORDER_REPLICATE; vpanel() | 297.0-303.0 | partial: No skull; BORDER_REPLICATE smears vertical streaks at the warped edge (visible defect, not re-rendered) | 933 |
| SHORT-03 | `sh03` (:884) | big words LOOK/CLOSER/1434 size 130 bold; vpanel() | 303.0-309.0 | done | 836 |
| SHORT-04 | `sh04` (:894) | yellow box + label (20,20,20) text; vpanel() | 309.0-314.5 | done: Label text is slightly clipped at the box bottom | 859 |
| SHORT-05 | `sh05` (:903) | k-means 8-colour wheel; vpanel() | 314.5-320.5 | partial: Palette wheel is synthetic | 862 |

Techniques that the 82-shot episode actually exercises (from `ids` in shots_final.json): CAM-01/03/04/05, TR-02/04, LAY-01, HI-01, AN-01/04/05, TXT-01, STATIC-01/02/08/09, DIA-07. The remaining ~39 exist only in the reel.

## 6. Gap analysis and proposal

### 6.1 What the target needs vs what exists

| Need | Exists | Gap |
|---|---|---|
| `frame_at(storyboard, t, size)` | `frame_at(t)` closure over code-built shots (build_v2.py:553) | Shots come from Python, not from a storyboard object; no `size` (global `W,H`); no cache control. |
| `render_range(storyboard,t0,t1,out,size,fps)` | `render` mode (:573) | Embedded in `main()`; size handled by downscaling; ffmpeg flags fixed. |
| technique registry `technique_id -> renderer` | `SEG` list in reel (id/name/dur/fn), `painting_shot` + overlay classes in episode | Two disjoint mechanisms; reel renderers take only `(t,d)` and carry literals. |
| Schema + anchors to words | `TL.find/at` over timing2.json | Phrases are in code; no JSON representation of camera keys, overlays, regions or image keys. |

### 6.2 Smallest refactor (proposed)

1. **Schema.** `storyboard.json` = `{canvas:{w,h,fps}, assets:{key:{path,regions:{name:[x,y,r?]}}}, timing:"timing2.json", cards:[...], shots:[...]}`. Shot = `{id, t0|anchor, t1|anchor, technique, image, params, overlays:[{technique, t0|anchor, t1|dur, params}]}`. An **anchor** is `{phrase, nth, wi, off}` (exactly the arguments of `TL.at`), resolved once at load into seconds so the editor can show and edit both forms. Regions replace `MIRROR`, `DOG` ... so that `pt:"MIRROR"` or `pt:[x,y]` works.
2. **Move `lib/vfx.py` to `engine/` unchanged** (see 6.3) and add a `Canvas(w,h)` object (or module-level setter) so defaults `W,H` stop being import-time constants. Because `W` is used as a default argument in 11 signatures, the cheapest approach that keeps the pixel look: always render the scene at 1920x1080 and `cv2.resize` to `size` (this already costs ~1 ms and is what the code does). Add true low-res rendering only if previews need >30 fps.
3. **Registry.** `TECHNIQUES = {}` with `@technique("CAM-05", kind="camera"|"overlay"|"layout"|"standalone")`. Wrap the existing pieces:
   - camera shot (`painting_shot` + `Cam`) registers CAM-01..05 (they differ only in keys/easing: the reel versions are just parametrised `Cam` specs), STATIC-01/02, TR-04 (a cut between two shots, not a renderer).
   - overlay classes register HI-01 (`Spot`), AN-01 (`RingOv`), AN-05 (`DimOv`), STATIC-02/CAM-06/STATIC-05 (`Lbl` with different y0), STATIC-08/09 (`ScreenText`, `Years`).
   - standalone renderers keep signature `fn(t, d, params, ctx) -> frame`.
4. **Storyboard compiler**: `compile(sb) -> Scene` that resolves anchors, builds the `Cam`/overlay objects, and returns `frame_at(t)`. Port `build()` to emit a `storyboard.json` once (script that executes today's `build()` and serialises camera keys + `.info` + new `params` that the classes must retain). Verify by diffing frames against current output (the 3 known stills at PSNR >40 on the same machine is a good test).
5. **`render_range`** = lift `main()`'s render branch into a function; pass an ffmpeg preset parameter (`veryfast`, crf 27 for preview); keep rawvideo pipe.
6. **Shot-level result cache**: keep the existing `contiguous()` semantic (shots tile the timeline) but make it an explicit validation, since an editor will create gaps.

### 6.3 Reuse classification
- **Lift as is**: everything in `lib/vfx.py` (`Img`, `Cam`, `compose_matte`, `backdrop`, `Layer`, `text_layer`, `label_layer`, `spotlight`, `ring`, `blend`, easing); `TL` word lookup; `Lbl, Spot, RingOv, ScreenText` (turn constructor args into params); `frame_fn` shot dispatch + end fade; ffmpeg pipe.
- **Parameterise**: `painting_shot/still_shot/card_shot` (move literals to params; `still_shot` auto-adds a second shot, which needs expressing as two storyboard shots); `DimOv`, `Years`, `title_card_shot` (text/rect literals); `W,H`-bound defaults; font table (add a configurable font map and a bundled TTF so Mac/Windows/web renders agree; Futura vs Century Gothic already differ); `TLC` cache keys (keyed on text only, would collide across sizes); end-fade (uses `T.end`); `split_shot` (panel rects, images, captions -> params); `map_shot`.
- **Missing / one-off in the reel, to be generalised as registry entries** (all 56 render but with hard-coded content): all LAY-* (grid/columns/strips/inset/kaleidoscope), HI-02/HI-03 (need mask asset), AN-02/03/06/07, DIA-01..07, CMP-01..05, FOOT-01, SHORT-01..05 (vertical panel `vpanel`), TR-01/02/03 (transition between two sources; need a first-class "transition" between shots, which the episode never uses besides the slide), TXT-02, STATIC-04/05/06/07. Common pattern to extract: a tile/grid layout engine (`two_panels`, 2x2, 5 columns), a mask-based matting layer (couple/dog masks are rough GrabCut), and a text/annotation layer set. Realistically 6-8 generic renderers cover the 39 reel-only techniques once layouts are parameterised.
- **Assets that do not exist as reusable data**: real masks and empty-room plate (stand-ins), maps, interview footage; these are the 21 "partial" items and will need uploads, not code.

### 6.4 Performance risks for interactive use (measured locally)
- **Cold image cost**: first touch of a 6000-px image = ~0.2 s (JPEG decode + 5-level pyramid); full episode touches 12 images -> **1.4 GB RSS** (pyramids kept in `_IMG`, ~105 MB for A, ~170 MB for the 7442-px blue_cap). Fine on this Mac; for a web editor process use lazy load + LRU, or precompute pyramids to disk (e.g. `.npy`/tiles) and memory-map. Preview-resolution renders only need the levels with scale >= 0.5, so for 640x360 previews levels 0-1 can be skipped (saves memory and decode).
- **Per-frame cost** is small (20-30 ms at 1080p; 5-s preview at 30 fps = ~4 s, at 10 fps ~1.4 s) so stills are interactive (<100 ms warm). Do not respawn a Python process per request (startup + load = 2.4 s): keep a long-lived worker with the `Scene` cached.
- **Outliers**: SHORT-* 0.85-0.93 s/frame (blur of a 1920x3410 image per frame -> blur once and cache, or blur at 1/4 scale); STATIC-07/AN-04/map ~0.06-0.12 s (cache the static background and draw only the animated part); `blurred_bg` for title cards is recomputed once (cached via `TLC`) - fine. Frame 0 of any shot that first uses an image pays the cold cost: prefetch images referenced by shots near the playhead.
- **Cache keys**: `Layer` caches (`TLC`, reel `TL`) must include canvas size and font if size/fonts become parameters. `backdrop` is already keyed by size.
- **Determinism**: all randomness is seeded (`RandomState(5/7/2/11)`), so cached frames are reproducible. Verified only by inspection of the code, not by an A/B test.
- **Thread use**: `CV_THREADS` default 4; on 10 cores a pool of 2-3 workers each with 3-4 threads would parallelise preview range rendering (frame-independent).
- **Hard failure modes for an editor**: `T.find()` raises `KeyError` if a phrase is not in the narration (every anchor edit needs validation); `render` raises `ValueError("bad shot duration")` for shots shorter than 0.2 s (`make()` :539); an off-canvas text layer previously crashed (already fixed in `text_layer`).

### 6.5 Open items / what I could not determine
- I did not diff against the 56-record `EFFECTS_CATALOG.md` text, only its IDs as embedded in `build_reel.py` and the capabilities table; I assume the 56 IDs match.
- Final-quality 1080p render time was not re-run locally for the whole episode (the Windows logs `ref/server/v2r*.log`, `render_times.json` exist but I did not analyse them); local numbers say ~25 ms/frame x 24,625 frames is about 10 min of render plus x264, not verified.
- `build_final.py` (v1 81-s cut) is a separate older code path with its own `Scene` class; ignored apart from reading the header. `scripts/` is mostly Mac-side planning/QA (timing merge, QA sheets, jitter/sync measurement, mask making, report generation, ssh/scp wrappers), none required by the renderer.
- Peak memory was measured as maximum RSS of the whole process, not per frame.

## Appendix: files created
`.scratch/r1/{lib,build_v2.py,build_reel.py,timing2.json,assets/}` (copies), `bench.py, bench2.py, bench3.py, gen_table.py`, outputs in `.scratch/r1/out/` (stills, 960x540 PNGs, `cli_range.mp4`, `range_10fps.mp4`, `range_30fps.mp4`, reel thumbnails, `reel_montage.jpg`, `reel_times.json`).
