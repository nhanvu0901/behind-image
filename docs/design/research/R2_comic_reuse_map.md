# R2. Comic pipeline reuse map for the Behind-the-Image web editor

Source repo (read-only, nothing modified): `/Users/nhanvu/Documents/code/comic-book-pipeline` (called "comic" below).
Target: `/Users/nhanvu/Documents/code/behind-the-image` (FastAPI backend, plain HTML/JS frontend, 16:9, 10-14 min).
No `.env` file or environment variable was opened or printed. The key variable name was read from source code only.

## 0. Executive summary

| Part | Key files | Verdict |
|---|---|---|
| Timeline data (cuts/words/beats/duration, waveform, snap) | `stages/mascot/timeline.py` | COPY (about 60% as is; rewire inputs, replace waveform PNG with peaks JSON) |
| Cue model + config (de)serialisation | `stages/mascot/config.py` | COPY the dataclass/clamp/atomic-write pattern; replace the mascot-specific fields |
| Auto-suggest with locks | `stages/mascot/suggest.py` | PATTERN ONLY (the lock-merge skeleton is 15 lines; the rules are mascot-specific) |
| Still frame at t | `stages/mascot/render.py::frame_at` | COPY (one function, about 35 lines) |
| Preview clip job, debounce, cache | `ui/screens/s9_mascot.py` (Flet), `render.render_preview` | PATTERN ONLY |
| Mascot Flet screen | `ui/screens/s9_mascot.py` | PATTERN ONLY (1299 lines of Flet widgets; only the helper functions at the top are portable) |
| Per-beat candidate tray, locks, approve | `ui/screens/s_review_gate.py`, `stages/review_gate.py` | PATTERN ONLY for the screen; COPY small pure helpers; adopt the JSON contract |
| Custom image | `ui/custom_image.py` | COPY `add_custom_image` + sidecar, strip Flet/VLM parts |
| Video clip search and pick | `stages/clip_fetch.py` | COPY selected functions (module top level is stdlib-only) |
| Web job routes + `/moments_review` | `ui/web_routes.py` | PATTERN ONLY for the Python (imports the whole stage_5 package); LIFT the JS widget |
| You.com client | `stages/research_scout/youcom.py` | COPY the single file, but NOT via package import (see section 6) |
| You.com scout lessons | `stages/youcom_scout.py` | PATTERN ONLY |
| Met adapter | `art_pipeline/sources/met.py` | COPY (3 imports, but one is `stages.user_errors` and one is a relative config) |
| Region proposal | `art_pipeline/regions.py` | COPY the pure geometry (`clamp_bbox_pct`, `pct_to_pixels`, `bbox_iou`, `filter_regions`, `grid_fallback_regions`); the VLM part imports pipeline config |
| Hunt (web image research) | `art_pipeline/hunt.py` | PATTERN ONLY (UA/429 lessons, download size-gate) |
| Atomic JSON + corrupt quarantine | `utils/atomic_json.py`, `ui/bridge.py::_quarantine_corrupt` | COPY |

Nothing should be IMPORTed by putting the comic repo on `sys.path`. Reasons are in section 8 (import side effects).

---

## 1. Mascot editor

### 1.1 What it does

Step 9 of the comic UI. It overlays a 2-D sticker mascot on the finished `final.mp4` (9:16, 1080x1920). The human edits a list of CUES on a timeline (time, move, pose, position, locked). "Gợi ý tự động" (auto-suggest) proposes cues from the beat structure and keeps hand-edited (locked) cues. A still preview shows the frame at time t with the sprite as a draggable box plus a resize handle. "Xem thử" renders a 3 s clip around the playhead. Everything is saved to `mascot.json` with a 0.4 s debounce. The Flet screen is `ui/screens/s9_mascot.py` (1299 lines); the logic is in `stages/mascot/*`.

### 1.2 Module map and public API

`stages/mascot/__init__.py` is docstring-only (no imports). `stages.mascot` has no dependency on the pipeline `config.py`.

`stages/mascot/config.py` (242 lines; stdlib only; defines `REPO_ROOT`, `MASCOT_ASSETS`, `CHANNEL_DEFAULTS_PATH` as constants, no mkdir at import):
- `MOVES`, `MOVES_ENTER`, `MOVES_EXIT`, `MOVES_ACCENT`, `POSITION_PRESETS`, `MOTION_LEVELS` (tuples/dicts)
- `_clamp(v, lo, hi, default) -> float` (NaN-safe)
- `@dataclass Position(preset: str, x: float, y: float)`; `Position.from_dict(d)`, `Position.from_preset(name)`
- `@dataclass Cue(t: float, move="hold", body=None, face=None, position=None, locked=False, id=uuid4().hex[:8])`; `Cue.from_dict(d) -> Cue|None` (drops cues with missing/negative t, unknown move becomes "hold"), `Cue.to_dict()`
- `@dataclass MascotConfig(kit, enabled, position, size_pct, accessories, outline, shadow, motion, talk_bounce, show_caption_guide, show_shorts_ui_guide, cues)`; `from_dict`, `to_dict(with_cues=True)`, `sorted_cues()`
- `config_path(project_dir)`, `has_config`, `load_config(project_dir, defaults_path=None)`, `save_config(project_dir, cfg)`, `load_channel_defaults`, `save_channel_defaults`, `_write_json_atomic(path, data)` (mkstemp + os.replace, no fsync), `_read_json(path)`

`stages/mascot/timeline.py` (347 lines): imports `from . import render` (only for `render.source_video`). See 1.4.
- `timeline_data(project_dir: Path) -> dict`
- `snap_time(t, data, *, threshold=0.25, kinds=("cuts","beats","words")) -> float`
- `waveform_png(project_dir, width, height) -> Path`
- `thumb_strip_png(project_dir, width, height) -> Path`

`stages/mascot/suggest.py` (322 lines): imports `.config`, `.kit` (PIL), `.timeline`.
- `suggest_cues(project_dir, cfg, kit, data=None) -> list[Cue]`
- `clear_suggestions(cfg) -> list[Cue]` (only locked cues)
- `visible_ratio(cues, duration) -> float`, plus private `_events`, `_build`, `_add_pose_changes`, `_role`

`stages/mascot/render.py` (586 lines; imports numpy, PIL, kit, motion at top): `frame_at`, `render_preview`, `render_final`, `source_video`, `ensure_clean_copy`, `restore_clean`, `has_mascot_output`. The final-render machinery (clean copy, render_state.json, atomic replace of final.mp4) is mascot specific and irrelevant for us.

`stages/mascot/motion.py` (275 lines) and `kit.py` (397 lines): sprite animation and compositor. Not reusable (they only matter if we want a mascot, which we do not).

### 1.3 JSON shapes

**mascot.json** (written by `MascotConfig.to_dict`):
```json
{
  "kit": "rook_v1", "enabled": true,
  "position": {"preset": "bottom_left", "x": 0.2, "y": 1.0},
  "size_pct": 23.0, "accessories": ["monocle"], "outline": true, "shadow": true,
  "motion": "normal", "talk_bounce": true,
  "show_caption_guide": false, "show_shorts_ui_guide": true,
  "cues": [
    {"id": "a1b2c3d4", "t": 0.2,   "move": "rise",  "body": "point", "face": "happy", "locked": false},
    {"id": "e5f6a7b8", "t": 5.55,  "move": "sink", "locked": false},
    {"id": "c9d0e1f2", "t": 25.76, "move": "shake", "body": "arms_up", "face": "shock",
     "position": {"preset": "bottom_right", "x": 0.8, "y": 1.0}, "locked": true}
  ]
}
```
Notes: coordinates are resolution independent fractions (x = sprite centre / frame width, y = feet line / frame height). A cue field of `null`/absent means "inherit the previous cue's value". `locked` is the only provenance flag.

**timeline_data output** (all seconds, sorted):
```json
{
  "duration": 61.2,
  "cuts":   [0.0, 3.4, 7.1, 61.2],
  "scenes": [{"scene_id": 1, "t": 0.0, "end": 7.1}],
  "beats":  [{"id": 1, "function": "COLD_OPEN", "name": "Hook", "t": 0.0}],
  "words":  [{"w": "Hello", "t": 0.2, "end": 0.55}]
}
```
Inputs it reads from the project dir (all optional): video via `render.source_video()` (ffprobe duration), `shots.json` (`duration_seconds` per shot, cumulative = cuts), `shots/shot_*.mp4`, ffmpeg scene detection (cached `mascot/cache/cuts_<sha1>.json`), `scene_timings.json` (`[{scene_id,start,end}]`), `narration.json` (`beats[{id,function,name}]` mapped to time through `scenes[].beat_id`), `word_timestamps.json` (`[{word,start,end}]`).

**Cut source order:** first source whose total is within 0.5 s of the video duration (or shorter by at most 6 s for the outro card) wins: shots.json, then shot files, then ffmpeg scene detect (threshold 0.25 on a 160 px downscale), then scene starts. 0 and duration are always added; cuts closer than 0.05 s are merged (`_finish_cuts`).

### 1.4 Timeline questions

**What does it produce?** The dict above. It also writes cache files under `<project>/mascot/cache/` (created by `_cache_dir` on first use, not at import).

**How is the waveform made?** `waveform_png(project_dir, width, height)`:
1. Picks the audio source: `audio.wav` if its duration is within 0.5 s of the video, else the video file.
2. `ffmpeg -vn -ac 1 -ar 8000 -f s16le -` into memory (14 min is about 6.7 M samples, about 13 MB; fine).
3. `abs` of int16, then `np.linspace(0, n, width+1)` bin edges; per-column MAX of the bin gives `peaks[width]`.
4. Normalise by the 99th percentile of peaks, clip to 0..1.
5. Draw one vertical line per column (PIL, RGBA `(235,235,235,204)`) on a transparent PNG, mirrored about the mid line.
6. Cache: `wave_<sha1(path|size|mtime_ns, w, h)[:16]>.png`; atomic PNG write.
The PNG is fixed pixel width (`TL_W` in the Flet screen), so it cannot zoom. For a 14 min web timeline return the `peaks` array as JSON (for example 2000 to 8000 points, 0..1 floats rounded to 3 decimals) and draw on a `<canvas>` client side. The Python column loop is cheap at those widths. Copy steps 1-4 and drop 5-6.

**How does `snap_time` work?** Linear scan over `data["cuts"]`, then `beats` (item `t`), then `words` (item `t`; only word STARTS, not ends). A candidate qualifies if `abs(c - t) <= threshold` (default 0.25 s). The winner is the minimum of the tuple `(distance, priority, time)` with priority cuts(0) < beats(1) < words(2), so on equal distance a cut beats a beat beats a word. If nothing qualifies it returns `t` unchanged. `kinds` restricts which lists are used. Pure, no I/O, about 15 lines, works with float lists or dicts. For 14 min (about 2100 words, about 200 cuts) a linear scan per drag event is fine; use `bisect` only if profiling says so.

**Can it be copied nearly as is for 16:9, 14 min?** Mostly yes. Nothing in `timeline.py` is aspect-ratio specific (no 1080x1920 anywhere). What must change:
- `render.source_video(project_dir)` is the only dependency on `render`. Replace by a parameter or a function returning the proxy video / audio path.
- The cut sources (shots.json durations, scene_timings, narration beats) are comic file formats. In the new project cuts come directly from `storyboard.json` (shot start times) and words from the TTS/forced-alignment file; the ffmpeg scene detection fallback and `_agrees/OUTRO_TAIL_MAX/MATCH_TOL` logic can be deleted.
- `thumb_strip_png` spawns one ffmpeg per shot, serially. Our shots are stills (not video), so build thumbs by resizing the still files instead. Cache pattern (`_hash(_signature(file), params)`) is worth keeping.
- Beat mapping through `narration.scenes[].beat_id` is comic-specific; use chapters/sections of the storyboard.
- `_run()` is the single choke point for ffmpeg calls (patched in tests); keep that idea.
Verdict: **COPY** `_run`, `_read_json`, `_f`, `_probe_duration`, `_signature`, `_hash`, `_atomic_write`, `_save_png_atomic` (only if PNGs are still used), `_cache_dir` (change the dir), `_finish_cuts`, `snap_time`, and the waveform decode/peak math. Rewrite `timeline_data`.

### 1.5 Suggest and locks

**Algorithm (`suggest_cues`):**
1. `locked = [c for c in cfg.sorted_cues() if c.locked]`.
2. `_events(data, kit)` turns beats into highlight events `{t, role}` (role from keywords in the beat's `function`: hook/landing/peak/build/other) and "extras"; every time is snapped with `snap_time`. Fallbacks: scene starts, then a single event at 0.2 s.
3. For each `hold` in a grid (1.5 s to 41 s in 0.5 s steps, plus infinity), run `_build(events, locked, data, kit, hold)`, a small state machine that walks `locked cues + events` merged and sorted by time: a locked cue only updates state (visible/hidden, `last_cue`); an event is skipped if it is within `LOCK_GAP` (0.8 s) of any locked cue or within `MIN_GAP` (1.2 s) of the previous cue; it "sinks" the mascot at the next cut after `hold` seconds idle; it adds an end exit 0.5 s before the end.
4. Score each plan by `visible_ratio` (target band 0.45-0.65, closest to 0.55), keep the best.
5. `_add_pose_changes` breaks up stretches longer than 6 s with extra "pop" cues at beats, then cuts.
6. Return `sorted(locked + best, key=t)`.

**How locked cues are kept and unlocked replaced:** the function builds the new list as `locked + fresh`. The old unlocked cues are simply never carried over (the caller does `cfg.cues = list(cues)`). Locked cues are kept byte-identical (same object, same id), and the generator keeps `LOCK_GAP` clear around them. `clear_suggestions` is the inverse: `[c for c in cfg.sorted_cues() if c.locked]`.

**Suggestion vs human edit:** only the boolean `Cue.locked`.
- Fresh suggestions: `locked=False` (dataclass default).
- `edit_cue(fn, lock=True)` in the screen sets `cue.locked = True` after any manual edit; `new_cue_at` creates cues with `locked=True`; the lock checkbox (`on_lock_change`) toggles it.
- There is no `source` / `origin` field and no timestamp. Cue ids are regenerated on each suggestion run (the screen sets `S.selected = None` after suggest because of this).
- First open: the screen auto-suggests only when `first_open and not cfg.cues`.

**Reuse verdict: PATTERN ONLY.** The reusable skeleton is: `locked = keep; fresh = generate(avoid within LOCK_GAP of locked); result = sorted(locked + fresh)`; plus "any manual edit sets locked". Recommended additions for the storyboard: `"source": "auto"|"human"`, `"locked": bool`, stable ids derived from `(anchor word index, technique)` so a re-suggest does not lose selection, and the anchoring to word span rather than float seconds. The rules (ROLE_KEYWORDS, RULES, POSE_POOLS, VISIBLE_BAND, hold grid) are mascot-specific; do not copy.

### 1.6 Preview (still frame and short clip)

**Still frame:** `render.frame_at(project_dir, t, *, width=540) -> Path` (JPEG of the CLEAN video).
- Cache key: `sha1(json([_sig(src), round(t*30), width]))[:20]`, file `mascot/cache/frames/<key>.jpg`; `_sig` is `[size, sha1(first MiB + last MiB)]` (content fingerprint, survives copies).
- ffmpeg: `-ss <t> -i src -frames:v 1 -vf scale=<width>:-2 -q:v 3`, output to a `.tmp.jpg` then `os.replace`. If t is past the end it re-grabs at `duration - 0.1`. Fast seek (input `-ss`) is acceptable for a preview; it is keyframe-accurate-ish.
- For our project the "frame at t" is not a video grab: the storyboard says which still image and which region box is active; we render the still + region/Ken Burns state in Python (PIL) or just show the still with a CSS overlay. `frame_at` is only useful when previewing a rendered proxy video.

**Short clip:** `render.render_preview(project_dir, cfg, t_center, span=3.0, width=540, progress, log) -> Path`.
- Window `[t_center - span/2, +span]` clamped to the video; decodes the source via an ffmpeg rawvideo pipe, composites the mascot with PIL frame by frame (`_overlay_pass`), encodes H.264 `veryfast crf 23` plus AAC 128k, to `mascot/preview.mp4` via `preview.tmp.mp4` and `os.replace`.
- The screen's `_preview_job` copies the file to `mascot/cache/previews/preview_<mtime_ns>.mp4` and deletes older ones, so a browser never shows the previous clip (cache-busting by unique name). In our design: render with the real render engine to `previews/preview_<sha1(storyboard slice)>.mp4`, which is both a cache key and a cache-buster.

**Debounce and threading (Flet specifics):**
- Still preview: `schedule_preview()` increments `S.token` and `page.run_task(_preview_task, token)`. The task does `await asyncio.sleep(PREVIEW_DEBOUNCE=0.12)`, bails if `token != S.token`, runs `_compute_preview` in `run_blocking` (`asyncio.to_thread`), checks the token again, then applies the result. This is "latest wins" with a monotonically increasing token, not a cancel.
- Save: same pattern with `SAVE_DEBOUNCE=0.4` and `S.save_token`.
- Clip: `_preview_clip_task` calls `save_now()`, `_begin("...")` (a `S.busy` flag so only one job runs; it also shows a progress bar), then `run_blocking(_preview_job, center)`. Centre = selected cue time else playhead.
- Web equivalent: JS `setTimeout` debounce + `AbortController`/request-id for the still; `POST /api/preview` returning a job id for the clip, with polling (section 4).

**What is cached:** cuts (`cache/cuts_*.json`), waveform PNG, thumb strip PNG, frame JPEGs (`cache/frames`), sprite PNGs (`cache/sprites`), preview clips (`cache/previews`, only the latest kept).

**Verdict:** `frame_at` COPY (change `source_video` lookup, change cache dir, keep the `_sig` fingerprint idea). `render_preview` / Flet screen PATTERN ONLY (token debounce, busy flag, unique file names).

### 1.7 Portable helpers at the top of `s9_mascot.py` (no Flet use)
`snap_position(x, y)` (drag-end snapping to presets/bottom edge; adapt to snapping a region box to composition guides), `active_cue_index(cues, t)`, `pose_after(kit, cues, idx)` ("last non-None wins" inheritance), `cue_position`, `preview_plan(cfg, kit, t)` (active + neighbour "ghosts"), `new_cue_at`. The ghost-neighbour idea (show the previous and next cue faintly on the still) is good UX for a region box editor.

### 1.8 Design doc
`docs/archive/avatar-narrator/2026-11-05-mascot-step-design.md` section 4 gives the mascot.json sample (older, slightly different position shape with pixel x/y and `slide_right`; the code is the truth). Section 8 records decision "keep a clean copy and never stack overlays" (not needed for us because our storyboard is declarative and render is always from source).

---

## 2. Per-beat review and picking (review gate)

### 2.1 What it does
After narration is written, the comic UI shows one card per "beat" (a scene, a fragment, intro or outro). Each card shows the narration text in an editable box and a tray of candidate panels (thumbnails). The human selects 2-5 panels per scene beat (1 for fragment/intro/outro), can hide a panel project-wide, add a custom image, see a "MP4 clip selected" badge when a video clip is picked instead, and finally Approve. Approval writes the sha1 of `narration.json` into `locks.json`; Stage 4/5 refuse to run unless approved and the sha matches. Candidates are NOT ranked: `build_candidates` writes every eligible panel page-sorted with `score: 0.0` ("manual-first").

### 2.2 Public functions

`stages/review_gate.py` (1031 lines). Top-level imports `from config import PROJECTS_ROOT`, `from stages._arc import ...`, `from stages.user_errors import ...` and does a `sys.path.insert` of the repo root. It reads env at import (`REVIEW_GATE`, `MONEY_SHOT_*`).
- `load_state(project) -> dict` (always fully shaped)
- `save_state(project, state) -> Path` (non-atomic `write_text`)
- `lock_panels(lock) -> list[{"page","panel"}]` (reads v1 and v2 shapes)
- `lock_custom_image(lock) -> str|None` (v3)
- `remap_locks_by_src(locks, src_by_page) -> dict` (pure; fixes `page` when global page numbering shifts, by the stamped `src` basename)
- `narration_sha1(project) -> str|None` (sha1 of `narration.json` BYTES)
- `ensure_reviewed(project, skip_flag=False, *, log=print)` raises `SystemExit` if not approved or sha mismatch
- `build_candidates(project_name, k=0, *, log=print) -> Path`
- `bookend_row_keys`, `review_beat_rows`, `validate_project_beat_key`

`ui/screens/s_review_gate.py` (2877 lines of Flet): pure helpers worth knowing, all module level: `_normalize_lock_panels(raw)`, `splice_locked_orphans(cands, lock, hidden)`, `_init_pre_selected(beats, locks, src_by_page)`, `hidden_set(doc)`, `filter_hidden(beats, hidden)` (keeps `candidates_all`), `beats_locking(locks, page, panel)`, `reconcile_beats(beats, narration, qa_mode)`, `remap_fragment_locks`, `_narration_fingerprint(doc)`, `clear_project_locks_and_clips`. It imports flet, `config`, `ui.bridge`, `stages.stage_5.*` lazily.

`ui/custom_image.py` (243 lines; no flet): `add_custom_image(project_root, src_image, beat_key, *, data=None) -> dict`, `enrich_custom_image(project_root, rel_file, *, log=print)` (VLM describe via Claude SDK, never raises), `list_custom_images`, `remap_fragment_custom_images`, `remove_scene_custom_images`, `rename_beat_custom_images`. Imports `.bridge.write_json_atomic` lazily inside `_save_sidecar` (so importing `ui.custom_image` pulls `ui/__init__`).

`ui/bridge.py` (1505 lines; imports `config`, `stages.user_errors`, `utils.*`): relevant to the review screen are `run_blocking(fn, *args, **kwargs)` (one line: `await asyncio.to_thread(...)`), `asset_src(abs_path)`, `set_web_mode`, `load_review_candidates`, `save_review_candidates`, `load_review_locks`, `save_review_locks`, `load_hidden_panels`, `save_hidden_panels`, `write_json_atomic` (re-export), `_quarantine_corrupt(path, what)`, `narration_sha1`.
- `asset_src`: desktop returns the absolute path; web returns `"/" + path.relative_to(PROJECTS_ROOT)` because the Flet server serves `PROJECTS_ROOT` as its assets dir. In our app this becomes a validated `GET /media/{project}/{path}` route.
- `load_review_locks`: on `JSONDecodeError` it MOVES the file to `locks.json.corrupt` and returns an empty doc, because the old behaviour (return empty, next click overwrites) destroyed hand work. Copy this.

### 2.3 JSON shapes

**locks.json** (v2 plus v3 custom image; v1 single shape is still read):
```json
{
  "approved": true,
  "approved_at": "2026-11-12T20:11:03",
  "narration_sha1": "9f2c...e1",
  "locks": {
    "3":    {"panels": [{"page": 12, "panel": 2, "src": "p012.jpg"},
                        {"page": 12, "panel": 4, "src": "p012.jpg"}], "source": "batcave"},
    "5:1":  {"custom_image": "review/custom/custom_1731412345_logo.png", "source": "custom"},
    "intro":{"panels": [{"page": 1, "panel": 0}], "source": "pre_selected"},
    "7":    {"page": 20, "panel": 1, "source": "batcave"}
  }
}
```
Keys are BEAT KEYS: `"<scene_id>"`, `"<scene_id>:<frag_idx>"`, `"intro"`, `"outro"`. A lock is exclusive: panels or custom_image, never both.

**candidates.json:**
```json
{"generated_at": "2026-11-12T19:00:00+00:00",
 "beats": [{
   "scene_id": 3, "beat_key": "3", "unit": "scene",
   "narration_text": "...", "page_ref": 12, "panel_ref": 2,
   "pre_selected": [{"page": 12, "panel": 2}],
   "source": {"title": "...", "issue": "...", "url": "...", "research_urls": []},
   "candidates": [{"page": 12, "panel": 0, "score": 0.0,
                   "thumb": "review/thumbs/p012_0.jpg",
                   "desc": "...", "dialog": "..."}]
 }]}
```
`score` is always 0.0; `money`/`money_conf`/`panel_source` appear only when their funnels ran. In memory the UI adds `candidates_all` (unfiltered pool) next to `candidates` (after hide filter); `save_review_candidates` folds it back so the hide filter stays a pure UI layer.

**hidden_panels.json:** `{"hidden": [{"page": 12, "panel": 3}]}`, project wide, a UI filter over candidates.json. Hidden WINS over a lock in the tray (`splice_locked_orphans` will not resurrect it), and hiding a panel that is selected somewhere first drops those locks (`beats_locking`).

**review/custom/custom_images.json** (sidecar):
```json
{"images": [{"file": "review/custom/custom_1731412345_logo.png", "beat_key": "5:1",
             "added_at": "2026-11-12T20:00:00", "desc": "", "enrich_status": "pending"}]}
```
`enrich_status` ends as `"ok"` or a comma list such as `"sdk_unavailable,desc_empty"`.

### 2.4 Specific answers

**How are candidates ranked per beat?** They are not. `build_candidates` lists every panel of the beat's eligible pool in (page, panel) order with `score=0.0`; `k>0` is only a cap on the first k. The comment says "nothing is ranked, Master picks by eye". The only ranking-like signals are `pre_selected` (the panel the scene was anchored to), the `money` flag (default off), and duplicate badges in the UI. The old matcher scoring was removed. For our media panel we need real ranking (text similarity of the narration beat vs candidate caption); `utils/lexical_sim.token_jaccard` (stdlib only, about 100 lines) plus the `score_video` formula in clip_fetch are the nearest reusable ranking code.

**How does the user add a custom image?** The card's "Add image" button opens a Flet `FilePicker` (web mode needs `with_data=True` because `.path` is None in a browser and only `.bytes` exist). `add_custom_image(project_root, Path(f.path or f.name), beat_key, data=f.bytes)` writes `review/custom/custom_<unix>_<slug>.<ext>` and appends the sidecar entry. It is instant and never fails on content. Then `page.run_task(run_blocking, enrich_custom_image, ...)` runs fire-and-forget to VLM-describe it. The user can lock it to the beat at once (`_toggle_custom` writes the v3 lock). Design principle recorded in the docstring: a custom image is never gated; it WILL appear; auto-assignment to a beat only happens when it is not locked. In the web app this is a `multipart` upload route plus a lock call; strip `enrich_custom_image` or replace with a description step of our own.

**What happens to locks when the narration text changes (sha1 staleness)?**
- Locks are keyed by beat key, not by text, so editing a line's wording does not orphan or delete its lock.
- Every UI action that rewrites `narration.json` sets `approved=False`, `approved_at=None` and saves locks.json (`_save_narration_text`, fragment split/merge/drop, insert scene, and so on). The user must press Approve again, which stamps `narration_sha1 = sha1(bytes of narration.json)`.
- `ensure_reviewed` blocks Stage 4/5 when `approved` is false OR `approved_sha != current_sha` (an edit made outside the UI is caught too).
- Structural edits remap the keys: `remap_fragment_locks`, `remap_fragment_clips`, `remap_fragment_custom_images`, `rename_beat_*` shift `"<sid>:<i>"` keys after a split/merge/drop.
- With `ENABLE_VIDEO_CLIPS=1`, if `_narration_fingerprint` (sha256 over each scene's id, text and visual_beats) changed, `clear_project_locks_and_clips` wipes ALL locks and ALL clips because a clip is cut to the beat's exact TTS duration. A save that changed none of those fields does not wipe anything.
- Page renumbering is handled separately: each panel lock stamps `src` (source image basename) and `remap_locks_by_src` rewrites `page` when the basename moved.
- `locks.json` is rewritten on every click through `write_json_atomic` (tmp + fsync + replace). This came from a real incident: a 40-lock file became 0 bytes.

Lesson for the storyboard: locks should carry an anchor fingerprint (for example sha1 of the covered word span text + start/end word index). If the span text changes, mark the lock "stale" (show it, do not delete it, do not silently move it). The comic approach (approval-level sha1 only) is coarse; the beat-key-level remap plus `src` stamp is the part to imitate.

### 2.5 Verdict
- Screen: **PATTERN ONLY** (2877 lines of Flet; behaviours to keep: select cap, hide project-wide with filter-layer semantics, orphan splice, one-click approve that stamps a hash, "clip chosen" badge, duplicate badge).
- **COPY** (pure, small): `lock_panels`, `_normalize_lock_panels`, `hidden_set`, `filter_hidden`, `splice_locked_orphans`, `beats_locking`, `narration_sha1`, `utils/atomic_json.write_json_atomic` (strip the `fs_remove` import and the Windows retry if on macOS only), `_quarantine_corrupt`, `add_custom_image` + sidecar helpers.
- `bridge.py` itself: do not import (it imports `config`, which loads `.env` and creates `projects/`; see section 8).

---

## 3. Video clip search and pick

### 3.1 What it does
`stages/clip_fetch.py` (1281 lines) finds YouTube clips for a narration beat. `moment_search(desc)` sends three phrasings (`desc`, `desc scene clip`, `desc animated`) to You.com Search restricted to `youtube.com`, dedups videos by 11-char id (counting how many phrasings found each: "hits"), then reads yt-dlp metadata (no download, 8 threads) and extracts candidate windows from chapters, subtitle lines and "most replayed" heatmap peaks, scores and ranks the shortlist. The human picks a video and in/out points in the browser; a background job downloads only that section with yt-dlp and renders a preview, and finally writes `review/clips/clips.json`.

### 3.2 Public functions (module top level imports only stdlib; `config`, `utils.lexical_sim`, `stages.stage_4`, `stages.stage_5` are imported lazily inside functions)
- `parse_search_results(payload) -> list[{"title","url","snippet","is_video"}]`
- `youtube_search(query, *, client=None) -> list[dict]` (raises RuntimeError)
- `video_id(url) -> str|None`
- `moment_queries(desc, extra=()) -> list[str]`
- `gather_candidates(queries, *, search=youtube_search, log=print) -> list[{"id","url","title","snippet","hits","best_rank"}]`
- `parse_vtt(text)`, `heatmap_peaks(heatmap, duration, *, k=3, ...)`
- `find_moments(desc, info, cues=None, *, k=3) -> list[{"start","end","strength","why"}]`
- `score_video(desc, cand, info, moments, n_queries) -> {"score","match","consensus","timing"}`
- `video_metadata(url, work_dir, *, timeout=120, use_cache=False) -> (info, cues)`
- `moment_search(desc, *, limit=8, extra_queries=(), search=..., metadata=..., log=print, use_cache=True) -> list[dict]`
- `ytdlp_section_args(...)`, `fetch_clip_section(url, clip_dir, *, start, beat_duration, end=None, margin=2.0, max_height=1080, log, source_file=None) -> Path`
- `process_clip_pick(project_root, beat, video_id, start, beat_duration, url=None, *, end=None, crop=None, ..., on_state=None, preview_token=None, commit=None) -> dict|None`
- `class ClipPickError(RuntimeError)`, `class DownloadTimeout`
- Env knobs: `YTDLP_BIN`, `CLIP_SECTION_TIMEOUT` (180 s), `CLIP_DOWNLOAD_TIMEOUT` (900 s). yt-dlp needs a JS runtime (`--js-runtimes node`) and a recent build (the requirements comment says 2026.07.04 gets HTTP 403; 2026.08.19 works).

**Side effects to strip when copying:** `REPO = parent.parent` and `_MOMENTS_CACHE_DIR = REPO/"cache"/"moments"`, `_META_CACHE_DIR = REPO/"cache"/"metadata"` (they write into the comic repo folder; repoint into the new project). `_api_key()` regex-reads `REPO/.env` for `YDC_API_KEY`; replace with `os.environ` only (the new project can `load_dotenv` itself). `process_clip_pick`, `resolve_beat_duration` import `stage_5.clips.render_clip_preview` (9:16 fit) and `stage_4.tts_status`: rewrite those two against our own render engine and storyboard durations; do not copy.

### 3.3 clips.json (manifest, `stages/stage_5/clips.py`)
Entry written by `process_clip_pick`:
```json
{"clips": [{
  "id": "gKiT1ekWIAA",
  "file": "review/clips/gKiT1ekWIAA_64.5_to_72.0.mp4",
  "beat": "3:1",
  "start": 0.0,
  "end": 7.5,
  "fit_to_beat": true,
  "source_url": "https://www.youtube.com/watch?v=gKiT1ekWIAA",
  "source_start": 64.5,
  "source_end": 72.0,
  "beat_duration": 6.2,
  "preview_file": "review/clips/preview_3_1.mp4",
  "crop": {"cx": 0.55}
}]}
```
Semantics: `start` is 0 because t=0 of the downloaded SECTION file is the picked moment; `end` is present only when the user gave an out point (then the span is time-fitted to the beat); `enabled:false` disables; `desc` (instead of `beat`) places by word overlap. Helpers `read_manifest_doc`, `upsert_beat_clip` (replace the beat's entry outright), `remove_beat_clip`, with an `RLock` and atomic writes because the Flet UI, web routes and Stage 5 all write it. `stages/stage_5/__init__.py` imports `pipeline` (cv2, etc.), so importing `stages.stage_5.clips` drags the whole stage 5 package; the manifest helpers are 30 lines and should be copied, not imported.

Search cache file: `review/clips/search_<beat with ":"→"_">_<sha256(query)[:8]>.json` (list of shortlist dicts as returned by `moment_search`, each with `id,title,channel,duration,height,subtitles,vertical,thumbnail,embeddable,moments[],score,match,consensus,timing,hits,best_rank`).

### 3.4 Verdict: COPY selected functions
Copy `parse_search_results`, `video_id`, `moment_queries`, `gather_candidates`, `parse_vtt`, `heatmap_peaks`, `find_moments`, `score_video`, `video_metadata`, `moment_search`, `ytdlp_section_args`, `fetch_clip_section`, `_ytdlp_cmd`, `_kill_tree`, `_run_capture`, `DownloadTimeout` (the process-tree kill with timeout is valuable for yt-dlp), plus `utils/lexical_sim.content_words` (stdlib). Edit: move cache dirs, drop `.env` regex, 16:9 instead of 9:16 in the normalisation step, and change the phrasings in `moment_queries` (they say "animated"/"scene clip", comic-specific; for art documentaries use "documentary", "museum", "x-ray", "analysis"). Beat duration source: storyboard shot/cue duration.

---

## 4. Web job pattern (`ui/web_routes.py`, 850 lines)

### 4.1 How it works
- `router = APIRouter()`; routes: `GET /moments_review`, `POST /api/pick_moment`, `GET /api/pick_status`, `GET /api/clip_preview`, `GET /api/beat_tts_status`, `POST /api/bump_beat_tts`, `POST /api/delete_beat_clip`.
- **Background job:** `POST /api/pick_moment` validates, calls `_set_pick(project, beat, state="queued", ...)` (returns a generation number), then starts `threading.Thread(target=_run_pick_job, args=..., daemon=True)` and returns `{"status":"accepted","state":"queued"}` at once. `?sync=true` runs the job in `run_in_threadpool` and returns the result (tests). Blocking network work in an endpoint is wrapped in `starlette.concurrency.run_in_threadpool`.
- **Job state:** a process-global dict `PICK_STATES[(project, beat)] = {state, message, gen, t, ...}` guarded by a lock (`stages/clip_cleanup.py` holds `PICK_STATES`, `PICK_LOCK`, `PICK_STATES` import). States: `queued, waiting_tts, downloading, rendering, ready, error, none`. State is in memory only; `get_pick_state` falls back to the manifest (`ready` if an entry exists, else `none`) after a restart.
- **Generation counter:** each new pick bumps `gen`; every state write passes its own `gen` and is dropped (`-1`) if superseded; `commit()` re-checks `gen` under the lock and only then `os.replace`s the staged preview (`preview_<beat>.pending_<gen>.mp4`) into place and upserts the manifest. A stale job can never overwrite a newer pick. This is the most valuable pattern in the file.
- **Status polling:** the page polls `/api/pick_status` every 1 s with an `epoch` counter (`pickEpoch`) so a response arriving after the user started another action is ignored; terminal states (`ready`, `none`, `error`) stop the loop.
- **Event broadcast:** `add_moment_picked_listener(cb, key)` lets the Flet screen repaint when a pick finishes. Not needed in a web-only app (the page polls).
- **Path validation:** `get_safe_project_dir(project)`: non-empty, `(PROJECTS_ROOT/project).resolve()` must be `is_relative_to(PROJECTS_ROOT.resolve())` and not equal to root, must be a dir (404 otherwise), else 400. `validate_beat_key` regex `^[a-zA-Z0-9_\-\.:]+$` up to 64 chars. `validate_video_id` regex `^[A-Za-z0-9_-]{11}$`, and the YouTube URL is REBUILT from the id (a client URL is never fetched). `start`/`end` must be finite, `0 <= start <= 24h`, `end > start`. Pydantic `BaseModel` for request bodies.
- **File serving:** `GET /api/clip_preview` looks up the manifest entry, builds `target = (root / rel).resolve()`, requires `target.is_relative_to(root)` and `is_file()`, returns `FileResponse(target, media_type="video/mp4")`. The page appends `&t=Date.now()` to the video src to defeat browser caching.
- **JS injection safety:** `_js(value)` JSON-encodes and escapes `</` and `<!--` for inline `<script>` use; `html.escape` for HTML attributes.

### 4.2 The `/moments_review` page and what can be lifted
The page is one Python f-string (HTML + CSS + JS, doubled braces). Do not copy it as Python; extract the JS into a static file. Liftable pieces for a generic "pick a moment in a video" widget:
1. **YouTube IFrame API wiring:** iframes with `?enablejsapi=1`; `onYouTubeIframeAPIReady` must be defined BEFORE the `https://www.youtube.com/iframe_api` script tag; create `new YT.Player(iframeId)` per card; handle `document.readyState === 'loading'`.
2. **Time helpers:** `fmtTime(sec)` -> `m:ss.s`; `parseTimeStr(raw)` accepts `5`, `0:05`, `1:02:03`, trailing `s`, and fixes typed letter "o" for zero; returns `null` (empty) or `NaN` (invalid).
3. **In/Out range bar:** inputs "from" and "to"; buttons "take from player" (`getPlayerTime`), "preview range" (`seekTo(in)`, `playVideo`, `setInterval` every 150 ms to pause at out); live hint text with validation and the speed ratio `(out-in)/beatDuration`.
4. **Suggested moment buttons:** each `moments[]` entry becomes a button that seeks and fills "from".
5. **Non-embeddable fallback:** `embeddable === false` shows an external link `watch?v=ID&t=NNs` and a manual numeric start input.
6. **Pick + poll + preview:** `pickMoment(vid)` validates, POSTs, then `pollPick()` with epoch; on `ready` it sets `<video src=/api/clip_preview?...&t=now>`; `deletePickedClip`.
7. **Search form** (GET with `q`) and server-side shortlist cache by `sha256(query)[:8]`.
Not liftable: the TTS wait loop (`waiting_tts`, `bump_beat_tts`) and `listener` broadcast; both are comic specific.

### 4.3 Verdict
Python: **PATTERN ONLY** (module imports `config`, `stages.clip_fetch`, `stages.stage_4.tts_status`, `stages.stage_5.clips` which triggers `stages/stage_5/__init__` and therefore `pipeline`/cv2/`config`; also `clip_cleanup`). Copy the validation functions, the gen-counter state machine, and the endpoint shapes. JS: **COPY (extract)** items 1-7 into a static `moment_picker.js`.

---

## 5. Media candidates (see section 2 for the ranking, custom image, locks answers)

Additional art helpers that match our "media search-and-choose panel":

**`art_pipeline/sources/met.py`** (Met Open Access REST; stdlib urllib):
- `fetch_meta(object_id) -> dict`, `search(query, *, has_images=True, limit=50) -> list[int]` (calls `/search?hasImages=true&q=`), `validate_cc0(meta) -> (ok, reason)` (hard gate: `isPublicDomain` and non-empty `primaryImage`), `parse_candidate(meta) -> {"object_id","title","artist","year","department","image_url","object_url","credit_line","medium"}`, `fetch_image(meta, dest) -> Path`.
- Imports: `from stages.user_errors import ArtworkNotUsableError` (this class must exist in `stages/user_errors.py`; check, or replace by a local exception) and `from ..config import MET_API_BASE, MET_USER_AGENT`. `art_pipeline/config.py` creates `ART_PROJECTS_ROOT` with `mkdir` at import (line 11), reads many `ART_*` env vars. So `from art_pipeline.sources import met` triggers that mkdir.
- Verdict: **COPY** `met.py` (about 55 lines), inline the two constants (`https://collectionapi.metmuseum.org/public/collection/v1`, a descriptive User-Agent), replace the exception.

**`art_pipeline/regions.py`** (region proposal): pure geometry is directly useful for the draggable region box. Region format is PERCENT bbox: `{"x":0..100,"y":0..100,"w":..,"h":..}` origin top-left. Functions: `clamp_bbox_pct(b) -> dict|None` (None if malformed or smaller than 1 percent), `pct_to_pixels(b, width, height)`, `bbox_iou(a, b)`, `filter_regions(regs, min_area_pct, max_area_pct, iou_thresh)` (clamp, area filter, IoU dedup keeping the richer `significance`), `grid_fallback_regions()` (full + 4 quadrants + centre). The VLM proposer `propose_regions_vlm` and `build_page_dict` import `config.OPENROUTER_*`, `stages.stage_2.cache`, `stages.stage_2.schema` (comic page schema), so: **COPY the geometry functions only**; the module as a whole is an IMPORT trap. Region record from the VLM: `{"bbox_pct": {...}, "description": "...", "significance": "...", "dominant_emotion": ""}`.

**`art_pipeline/hunt.py`** (skim): finds web images via a Claude SDK web-research session. Lessons worth keeping: UA policy differs per host (Wikimedia 429s browser-like UAs and wants a tool UA with contact, other sites 403 obvious bots), at most one retry after a 429 with a 5 s wait, a 1 s gap between downloads, download size gate (`min(w,h) >= VISUAL_MIN_SHORT_SIDE`), record `source_url` and `license` for credits, SDK turn budget scales with the number of subjects (default 12 turns starved a 6-subject hunt). **PATTERN ONLY**.

---

## 6. You.com research agent

### 6.1 What it does
`stages/research_scout/youcom.py` (186 lines) is a small audited HTTP boundary over two endpoints: Research (`POST https://api.you.com/v1/research`, an LLM-driven multi-step web research with structured output) and Search (`GET https://api.you.com/v1/search`). It returns a `RawCall` dataclass (never raises on HTTP errors). `stages/youcom_scout.py` (743 lines) is the older standalone script (3 stages: discover, enumerate, confirm) built on the same Research call.

**Env var:** `YDC_API_KEY`. The client reads `os.environ.get("YDC_API_KEY", "")` in its constructor; `clip_fetch._api_key()` and `youcom_scout._load_key()` additionally regex-read `REPO/.env`. Sent as header `X-API-Key`. (I did not read the key.)

### 6.2 Public API
```python
@dataclass(frozen=True)
class RawCall:
    api: str = ""; payload: Any = None; error: str | None = None
    status_code: int | None = None; response_text: str | None = None
    @classmethod empty(cls); @property ok -> bool   # ok == (error is None)

class YouComClient:
    def __init__(self, api_key: str | None = None, *, timeout: float = 1800)
    def research(self, prompt: str, schema: dict, profile: Mapping | None, *, effort: str = "standard") -> RawCall
    def search(self, query: str, profile: Mapping | None) -> RawCall

def compact_search_query(text: str) -> str   # <= 45 words and <= 360 chars
```
`profile` is a mapping with `"domains"` or `"include_domains"` (a list or a single string).

### 6.3 Request and response shapes as used

**Research request body:**
```json
{"input": "<prompt, max 40000 chars>",
 "research_effort": "standard",
 "source_control": {"include_domains": ["theartnewspaper.com", "metmuseum.org"]},
 "output_schema": { ...JSON Schema, OpenAI-strict style... }}
```
Efforts seen in code: `"standard"` and `"deep"` (the scout uses standard for discovery, deep for enumerate/confirm).

**Research response (keys the code reads):**
```json
{"output": {
   "content": { ...object matching output_schema... },
   "sources": [{"url": "https://...", "...": "..."}]
}}
```
The code reads `output.content` (a dict when a schema is given; the scout takes `content["candidates"]`) and `output.sources[].url`.

**Search request:** `GET /v1/search?query=<compact>&count=8&livecrawl=all&livecrawl_formats=markdown&include_domains=youtube.com` (repeat `include_domains` per domain).

**Search response (keys the code reads):**
```json
{"results": {"web":  [{"url": "...", "title": "...", "description": "...", "snippets": ["..."]}],
             "news": [ ...same... ]}}
```
`parse_search_results` also accepts `results` as a plain list. Snippets come from `description` else `snippets[0]`.

### 6.4 Minimal code (self-contained, stdlib only, copy-ready)

```python
import json, os, urllib.request, urllib.parse, urllib.error

KEY = os.environ["YDC_API_KEY"]           # the only secret
HEAD = {"X-API-Key": KEY, "Accept": "application/json",
        "User-Agent": "behind-the-image/0.1"}   # NOT the default Python-urllib UA: the WAF 403s it

def strict(props: dict) -> dict:
    """You.com validates OpenAI-strict schemas: every object level needs
    additionalProperties:false AND every property listed in required."""
    return {"type": "object", "additionalProperties": False,
            "properties": props, "required": list(props)}

def research(prompt, schema, domains, effort="standard", timeout=1800):
    assert len(prompt) <= 40_000
    body = {"input": prompt, "research_effort": effort,
            "source_control": {"include_domains": domains},
            "output_schema": schema}
    req = urllib.request.Request("https://api.you.com/v1/research",
        data=json.dumps(body).encode(), method="POST",
        headers={**HEAD, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())       # {"output": {"content": {...}, "sources": [...]}}

def search(query, domains, count=8, timeout=120):
    q = [("query", " ".join(query.split()[:45])[:360]), ("count", str(count))]
    q += [("include_domains", d) for d in domains]
    req = urllib.request.Request("https://api.you.com/v1/search?" + urllib.parse.urlencode(q),
                                 headers=HEAD)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())       # {"results": {"web": [...], "news": [...]}}

# example
schema = strict({"claims": {"type": "array", "items": strict({
            "claim": {"type": "string"}, "source_url": {"type": "string"},
            "quote": {"type": "string"}})},
         "notes": {"type": "string"}})
resp = research("Who commissioned The Arnolfini Portrait and why?", schema,
                ["nationalgallery.org.uk", "metmuseum.org", "wikipedia.org"])
content = resp["output"]["content"]
returned = {s["url"] for s in resp["output"]["sources"] if s.get("url")}
claims = [c for c in content["claims"] if c["source_url"] in returned]   # provenance gate
hits = search("Arnolfini Portrait restoration documentary", ["youtube.com"])
```
Error handling to keep from the file: catch `urllib.error.HTTPError` and truncate the body to 2000 chars (a 422 can echo the whole prompt, and you do not want that persisted), catch `URLError/TimeoutError/OSError` separately, and return a result object instead of raising (so one failed branch in a thread pool does not kill a batch).

### 6.5 Lessons recorded in the code comments

From `youcom_scout.py` module docstring and helpers:
- **Who owns the plan:** "You.com only finds what its own PLAN step thinks to search for (it missed 3/3 known answers on one broad query). So WE own the plan: every stage fans out into narrow angled queries, and You.com owns the digging." Pilot 2026-08-05. Discovery fans out over 5 angled queries (angle list in `research_policies/general_angles.v1.json`), enumeration over an angle matrix, confirmation is one refutation-framed query per item.
- **What is trusted:** the domain whitelist ("hard: 0 leaks / 11 pilot queries"). Still verified: `offdomain(resp)` compares each `output.sources[].url` against the whitelist and logs `LEAKED`.
- **What is NOT trusted:** its labels and its dedup (UK reprints double-counted, a "deep cut" mislabeled). Authoritative filters stay on our side: hard dedup in code (token containment/Jaccard; Jaccard not containment because "Batman Annual #1" vs "Batman #1" scored 1.0 by containment), exact-issue gates, banlist of already produced topics. The prompt-side digest of already-produced items is advisory only.
- **Strict schema:** every object level needs `additionalProperties:false` and all properties in `required`.
- **WAF:** the default `Python-urllib` User-Agent gets 403 (probed 2026-08-05); use a custom UA.
- **Timeouts:** Research can take minutes; the client uses a 1800 s timeout. Prompt cap 40,000 chars. Search query cap 45 words / 360 chars.
- **Provenance gate (`evidence.py`):** every URL a candidate cites (`evidence_urls`, `source_urls`) must appear in the call's own returned sources (`output.sources` for research; every `url` anywhere under `results` for search), else flag `URL_NOT_RETURNED`. Do not trust model claims over raw evidence; flags are stable enums (`GateFlag`).
- **Gate verdicts:** an unconfirmed verdict is a judgement a human may override; a gate that cannot be read is a defect. They are separate flags on purpose.
- **Cited pages are fetched through a reader (`cited_sources.py`):** `https://r.jina.ai/<url>` because Cloudflare blocks direct reads; max 3 URLs, 10 s timeout, 6000 chars per source; never raises; a failed fetch is reported as "COULD NOT FETCH" so the judge distinguishes "read it and it says otherwise" from "never looked". Gating runs one thread per candidate.
- **Audit logging:** every query logged with prompt (first 2000 chars), candidates, sources, off-domain leaks, seconds to a per-day JSON file (`scout_runs/log/<date>.json`).

### 6.6 Dependencies and import side effects
- `youcom.py` itself: stdlib only. But importing it as `stages.research_scout.youcom` first runs `stages/research_scout/__init__.py`, which imports `.models` (pydantic) and `.storage` (`stages.user_errors`, `utils.atomic_json`, `utils.fs_remove`). Those three are stdlib-clean (no `config`, no dotenv, no mkdir), so there is no .env load or directory creation, but it needs pydantic and the `utils`/`stages` top-level packages, so a bare `sys.path` import works only if the comic repo root is on the path.
- `youcom_scout.py`: `from stages.question_archetype import ...` at top and reads `research_policies/general_angles.v1.json` at import (`DISCOVER_ANGLES = json.loads(...)` at module level, comic-specific; breaks if the file is missing).
- `evidence.py` imports `.micro_recency`, `.models`, `.youcom` (comic-specific gates, skim only). `cited_sources.py`: stdlib only (good template).

### 6.7 Verdict
- `youcom.py`: **COPY** as one file (change the `User-Agent` string, drop nothing else; it is stdlib). Do not import via `stages.research_scout` because of the package `__init__`.
- `youcom_scout.py`, `evidence.py`, `cited_sources.py`: **PATTERN ONLY** (fan-out of narrow queries, strict schema helper, provenance gate, reader-based page fetch with bounded size, never-raise thread-safe gates, per-day audit log).

---

## 7. Serving (`ui/__main__.py`, 103 lines)

- Desktop: `python -m ui` runs `ft.run(main)` (a native Flet window).
- Web/LAN: `python -m ui --lan [--port N]` (default **8550**), binds `0.0.0.0` and sets `bridge.set_web_mode(True)` so `asset_src` returns paths relative to `PROJECTS_ROOT`.
  - Flag `ENABLE_VIDEO_CLIPS` off (default): `ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port, assets_dir=str(PROJECTS_ROOT))`. Flet's own web server; no FastAPI.
  - Flag on (`ENABLE_VIDEO_CLIPS=1`): `flet_asgi = ft.run(main, export_asgi_app=True, assets_dir=str(PROJECTS_ROOT))`, then `app = FastAPI(); app.include_router(clip_router); app.mount("/", flet_asgi); uvicorn.run(app, host="0.0.0.0", port=port)`. So the FastAPI routes (`/moments_review`, `/api/*`) sit on the same port as the Flet app, and the Flet app is mounted at `/` (after the router so the API routes win).
- **No authentication.** The module docstring says anyone reaching the port can edit, approve, and read every file under `projects/` (served as assets). Use a VPN (Tailscale) for outside access.
- `ui/__main__.py` does `sys.path.insert(0, repo_root)` and imports `_flet_compat` (patches flet 0.85) before any screen.

**Collisions to avoid:**
- Port **8550**: do not use it for the new app (pick another, for example 8600), in case the comic UI is running.
- Do not use `comic-book-pipeline/projects/`, `cache/moments`, `cache/metadata`, `research_sessions/`, `scout_runs/`, `assets/mascot/`, or `art_projects` (ART_PROJECTS_ROOT); the copied code must not default to them (several modules compute `REPO = Path(__file__).parent.parent`; that resolves into the NEW project after a copy, which is what we want, but verify each constant).
- The mascot cache lives inside each project (`<project>/mascot/cache`); for us use `<project>/cache/...`.
- yt-dlp global state: `YTDLP_BIN` env var may point at a Windows exe on the owner's other machine; the new code should resolve `shutil.which("yt-dlp")`.

---

## 8. Global concerns: import side effects (why not IMPORT)

`config.py` (632 lines), imported by almost every UI/stage module (`ui/bridge.py`, `ui/web_routes.py`, `stages/review_gate.py`, `stages/stage_5/shots.py`, `art_pipeline/regions.py`, `stages/clip_fetch.py` lazily):
- Line 8-10: `from dotenv import load_dotenv; load_dotenv()` runs at import. It loads the comic repo's `.env` (from the working directory upwards) into `os.environ`, so keys of the comic project (and the `ENABLE_VIDEO_CLIPS` flag, `MUSIC_*`, `CHATTERBOX_SEED`, ...) leak into the new process. If the new app is started from a directory that has its own `.env`, `load_dotenv()` (default) finds it by walking up from the CALLER's file, so the behaviour depends on where config.py lives; avoid the question.
- Line 617-618: `PROJECTS_ROOT = Path(__file__).parent / "projects"; PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)`, which creates a `projects/` folder inside the comic repo as a side effect of importing `config`. This violates the read-only rule if the new app imports it.
- Also at import: dozens of env parses (`bool(int(os.getenv(...)))` can raise `ValueError` on a bad value), `RESEARCH_SESSIONS_ROOT` path.
- `art_pipeline/config.py` line 11: `ART_PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)` at import.
- `stages/review_gate.py` inserts the repo root into `sys.path` and reads `REVIEW_GATE`/`MONEY_SHOT_*` at import.
- `ui/__main__.py` and `ui.app` import `flet`, `flet_video`, `_flet_compat` (monkey patch of flet 0.85).
- `stages/stage_5/__init__.py` imports `pipeline` and `cli` (cv2, torch-adjacent heavy deps, `config`).
- Clean (safe to import or copy): `stages/mascot/config.py`, `stages/mascot/timeline.py` (needs `render`, which needs numpy/PIL/`kit`), `stages/mascot/suggest.py`, `stages/clip_fetch.py` top level (lazy imports inside), `stages/research_scout/youcom.py` (not the package `__init__`), `ui/custom_image.py` (but `ui/__init__` and `ui.bridge`), `utils/atomic_json.py`, `utils/lexical_sim.py`, `stages/review_gate.py` pure helpers (not the module, because of `config`).

**requirements.txt (66 lines) relevant to the new project:** `fastapi>=0.110`, `uvicorn>=0.29`, `pydantic>=2.5`, `Pillow>=10`, `numpy>=1.24`, `yt-dlp>=2026.08.19`, `python-dotenv>=1.0`, ffmpeg/ffprobe on PATH. Not needed and heavy: flet/flet-audio/flet-video, torch/transformers/Florence/Magi stack, `simple-lama-inpainting`, spacy, curl_cffi, opencv, `claude-agent-sdk`, `openai`, `tavily-python`, `gradio_client`. Node is needed for yt-dlp `--js-runtimes node`.

**IMPORT risks, if it were ever done anyway:** `load_dotenv` + `projects/` mkdir inside the comic repo at first `import config`; namespace collision of the top-level packages `config`, `stages`, `utils`, `ui` with same-named packages in the new project (the new project must not have a `config.py`, `utils/`, or `stages/`); pydantic/flet versions; behaviour changes when the comic repo is edited upstream; yt-dlp/ffmpeg paths that default to the comic repo's cache dirs.

---

## 9. Recommended adoption list for the architect

1. **Cue/shot JSON:** adopt the `Cue` pattern (`id`, `t` rounded to 3 decimals, `locked`, from_dict that drops/repairs bad input, to_dict that omits `None` fields, resolution independent fractions for geometry, "None means inherit"), but anchor to words: `{"id","word_start","word_end","t","technique","region_pct":{x,y,w,h},"locked","source":"auto|human"}`.
2. **`timeline_data` JSON** (`duration, cuts, scenes, beats, words`) is a good API payload for the page as is; add `waveform: {"peaks":[...], "step": seconds}`.
3. **Re-suggest keeps locks:** `result = sorted(locked + generate(avoid=locked), key=t)`; manual edit => `locked=true`; "clear suggestions" keeps locked.
4. **Debounced preview:** token-based "latest wins", `busy` flag for the 10 s clip, unique output file name per render (hash of the storyboard slice) to defeat browser cache, only the newest preview kept.
5. **Job runner:** the `PICK_STATES` + generation counter + staged file then `commit()` under lock pattern from `web_routes.py`, plus path validators (`get_safe_project_dir`, regex-validated keys/ids, rebuild URLs from ids).
6. **Locks file:** `write_json_atomic` for every write, quarantine corrupt files to `.corrupt`, store a fingerprint per lock so staleness is shown per item.
7. **Media panel:** tray with hide-project-wide as a filter layer (`candidates_all` + `hidden`), orphan splice, custom upload = instant copy + sidecar, optional enrichment later; add a real ranking (token Jaccard + source trust), because comic's tray is unranked.
8. **Research:** copy `youcom.py`; our code owns the query plan (narrow angled queries per artwork/claim), schema helper `strict()`, provenance gate (cited URL must be in returned sources), domain whitelist verified after the fact, never trust labels/dedup.
9. **Moments picker:** copy the clip_fetch search functions and extract the JS widget; change the phrasings and the 9:16 fit.
10. **Serving:** one FastAPI app, own port (not 8550), static route for the HTML/JS, validated media route; no auth in the comic app, so add at least a bind to `127.0.0.1` by default.
