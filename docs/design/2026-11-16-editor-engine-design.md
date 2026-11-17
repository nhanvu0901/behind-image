# Video editing page and storyboard engine: design and contracts

Date: 2026-11-16. Status: approved direction, contract v1. Owner: Master. Author: the orchestrating analyst.
Code, comments and docs are in English. The editor's UI labels are in Vietnamese, with technique names in English.

## 1. Intent

We make 10+ minute art documentaries in the style of the YouTube channel Great Art Explained (GAE). An LLM agent (Gemini in production) drafts the edit, and a human approves and corrects it.

The owner wants two things that pull against each other:
- the flexibility of an agent across very different source books
- control over which animations and styles end up in the video

The answer is a closed, predefined set of techniques plus a declarative file:
- **`style/gae/techniques.json`** lists every editing technique and style the channel uses. Nothing outside it can be rendered.
- **`projects/<id>/storyboard.json`** describes one video using only those techniques. Agents and humans both edit this file. Nobody writes per-video render code.
- **The engine** renders any storyboard, deterministically.
- **The editing page** is where the human sees and changes the storyboard: timeline, true still preview, technique gallery, media picker, locks, preview clips.

## 2. Goals, non-goals, anti-goals

**Goals for this build:**
1. An engine that renders a storyboard: a still at any time, a short preview clip, a full range.
2. The existing 13.7-minute Arnolfini episode exported to a storyboard, and rendered by the new engine to match the old frames.
3. A web editing page that opens that project and lets a human change shots, overlays, techniques, parameters, media and timing, with every predefined technique visible in a gallery.
4. Media search-and-choose from licence-clear sources, plus a You.com research client that is wired in but not called live.

**Non-goals for this build:**
- Gemini skills.
- Book ingestion.
- Script writing.
- TTS.
- Final full-quality render on the Windows server.
- Audio mixing.

These come later and plug into the same files.

**Anti-goals:**
- Subtitles burned into the picture (owner's rule, restated 2026-11-16). The narration text is never rendered into frames, in previews or in final renders. Subtitles exist only as a sidecar `subtitles.srt`, with an optional soft subtitle track in the mp4. The on-screen text that IS rendered is the channel's own techniques from the registry: labels, cards, year text, quotes.
- An agent or a page that can produce an animation that is not in the registry.
- Any change to the comic repo.
- Any careless use of the Windows production server (see the rule below).
- Any paid API call without the owner's say-so.

**Windows server (owner's decision, 2026-11-16):** the server may be used for testing. Only an agent whose brief says so may use it, and only under the rules of `docs/benchmarks/video_edit_benchmark_prompt.md` section 4:
- Write only under `D:\bench\`.
- The comic repo and its venvs are read-only.
- Take the `D:\bench\_heavy.lock` lock for any heavy job, keep each job under about 30 minutes, and release the lock even on failure.
- Check for production jobs and free memory first.
- Wrap ssh and scp in retries.

Stills and editor previews stay on the Mac.

## 3. Approaches considered

- **A. Free agent writes render code per video.** This is what the benchmark did. It is flexible but cannot be controlled: 85–90% of that code was hard-coded for one video (see R1). Rejected.
- **B. Hard-coded pipeline.** Controllable, but every new book shape needs new code. Rejected.
- **C. Skills decide, a fixed engine renders, a human approves** on an editing page. Chosen by the owner on 2026-11-16.

## 4. Research inputs

Read the one that concerns you before coding.
- `docs/design/research/R1_engine_map.md`: what exists in `demo_runs/claude_code/` (primitives, speed, gaps).
- `docs/design/research/R2_comic_reuse_map.md`: what to copy from `/Users/nhanvu/Documents/code/comic-book-pipeline` (read-only).
- `docs/design/research/R3_style_inventory.md` and `style/gae/`: the technique registry and previews.

## 5. Repository layout and ownership

All new Python lives in one package, `bti`. This avoids name clashes with the comic repo's `config`, `stages`, `utils` and `ui`.

| Path | Purpose |
|---|---|
| `bti/engine/` | storyboard engine |
| `bti/editor/` | FastAPI backend (`*.py`) |
| `bti/editor/static/` | frontend (HTML, JS, CSS, no build step) |
| `bti/media/` | sources, licence gate, You.com client, clips |
| `style/gae/` | `techniques.json`, `style.json`, `previews/`, optional `fonts/` |
| `projects/<id>/` | `storyboard.json`, `timing.json`, `media/`, `audio/`, `cache/`, `history/`, `proposals/` |
| `tools/` | command-line scripts |
| `tests/engine`, `tests/editor`, `tests/media` | tests |
| `requirements/` | `engine.txt`, `editor.txt`, `media.txt` |

**Rules for parallel work:**
- Write only inside the folders your brief gives you.
- Create `bti/__init__.py` (empty) only if it is missing, and never edit it otherwise.
- Use your own virtual env (`.venv-<role>`, created with `--system-site-packages`) and your own `requirements/<role>.txt`.
- Do not import another role's internals. Use the facades in section 8.
- Copying code from the comic repo is allowed. Put a header comment on each copied file naming the source path. Never import the comic repo through `sys.path`: its `config.py` loads a `.env` and creates folders at import (R2).
- Never read or print any `.env`.
- No ssh or scp unless your brief explicitly gives you the Windows server (see section 2).

## 6. The storyboard (`projects/<id>/storyboard.json`, schema `bti.storyboard/1`)

```jsonc
{
  "schema": "bti.storyboard/1",
  "project": "arnolfini",
  "title": "The Arnolfini Portrait",
  "style": "gae",
  "canvas": {"w": 1920, "h": 1080, "fps": 30},
  "timing": "timing.json",
  "audio": "audio/mix.m4a",
  "assets": {
    "A": {
      "file": "media/arnolfini_commons.jpg",
      "kind": "image",
      "title": "The Arnolfini Portrait", "artist": "Jan van Eyck", "year": "1434",
      "width": 4386, "height": 6000,
      "credit": {"source": "commons", "source_url": "https://…", "author": "…",
                 "licence": "PD", "licence_url": ""},
      "regions": {
        "MIRROR": {"x": 2220, "y": 1790, "rx": 440, "ry": 440, "label": "Mirror"}
      }
    }
  },
  "shots": [
    {
      "id": "s0012",
      "start": {"w": 87, "off": -0.12, "text": "Notice"},
      "technique": "CAM-05",
      "intent": "point_at",
      "slots": {"image": {"asset": "A"}},
      "params": {
        "camera": [
          {"at": {"rel": 0.0}, "cx": 2193, "cy": 3000, "zoom": 0.172, "ease": "inout_cubic"},
          {"at": {"w": 91, "off": 0.0, "text": "mirror"}, "cx": 2220, "cy": 1650, "zoom": 0.72, "ease": "linear"}
        ]
      },
      "transition_in": null,
      "overlays": [
        {"id": "o1", "technique": "HI-01", "intent": "isolate",
         "start": {"w": 91, "off": 0.0, "text": "mirror"}, "dur": 6.2,
         "params": {"at": "MIRROR", "rx": 440, "ry": 440, "floor": 0.2, "ramp_in": 0.5, "ramp_out": 0.5},
         "locked": false, "source": "import", "note": ""}
      ],
      "locked": false, "source": "import", "note": ""
    }
  ],
  "end": {"t": 820.83},
  "approvals": {"storyboard": null}
}
```

Field values:
- `assets.<key>.kind`: `image`, `video` or `mask`.
- `shots[].technique`: a registry id of kind `base` or `card`.
- `shots[].source` and `overlays[].source`: `import`, `agent` or `human`.

**Rules:**
- **Shots tile the timeline.** A shot ends where the next one starts; the last ends at `end`. The editor changes a duration by moving a boundary. Minimum shot length is 0.2 s.
- **Anchors** say when something happens. There are three forms:
  - `{"t": seconds}`: an absolute time.
  - `{"w": index, "off": seconds, "text": word}`: a spoken word. `index` points into `timing.words`, and `text` is that word, kept so a stale anchor can be detected after the script changes.
  - `{"rel": 0..1}`: a fraction of the parent shot. Allowed only inside a shot, for camera keys.
  
  The resolved time is `words[w].s + off`. When the engine resolves a storyboard, it adds `_t` next to every anchor and `_t0`/`_t1` to every shot and overlay. Keys starting with `_` are derived; they are stripped on save.
- **Overlays** belong to a shot and must lie inside its span. An overlay has `start` plus either `dur` or `end` (an anchor). With neither, it runs to the end of the shot.
- **Slots are the one form for assets, on shots and on overlays.** A shot or an overlay may carry `"slots": {"<slot>": {"asset": "<key>"}}`; the technique's registry `slots` list declares which slots exist (an overlay's `image` slot is the shot's own image; any other slot, such as HI-03's `mask`, is set on the overlay). An asset must sit in a slot of its kind: an `image` slot takes an image, a `mask*` slot a mask, a `video` slot a video (a still image is accepted as a stand-in). `/defaults` returns `slots` as well as `params`; it fills an `image` slot from the context image and leaves `video` and `mask` slots empty unless the context names an asset of exactly that kind.
- **Incomplete is not invalid.** A shot or overlay whose required slot is empty, or whose required parameter has no value, is *incomplete*: validation reports it as `level: "warn"` with `code: "incomplete"`, naming the slot or parameter; saving is allowed (a human may keep half-finished work); approval is refused while any `incomplete` issue exists; and the engine never fails on it: an incomplete shot renders as a neutral placeholder frame that names the technique and what is missing, an incomplete overlay or transition is skipped. Every other problem is an error and blocks the save (an unknown asset key or technique or parameter, an asset of the wrong kind in a slot, a file that does not exist or is not a readable image, a `style` that is not in the registry, a `timing`, `audio` or asset path that is not a file inside the project). The save path never writes a document that cannot be opened again.
- **Coordinates** are in source pixels of the shot's image. A point is a region name or `[x, y]`. The camera is `cx, cy` (source pixels at the centre of the frame) and `zoom` (screen pixels per source pixel on the 1920-wide canvas). The visible box is therefore `1920/zoom` by `1080/zoom`.
- **`params`** must match the parameter definitions of the technique in `style/gae/techniques.json`. Unknown parameters are errors.
- **`transition_in`** is null for a hard cut, which is the channel's default. Otherwise it is `{"technique": "TR-01", "dur": 1.0, "params": {}}`. During the overlap the engine renders both shots.
- **`locked: true`** means a human fixed this item. Proposals and re-suggestions never change locked items. Any human edit in the page sets `source: "human"`.
- A context still that then returns to the painting is two shots, not one.

`timing.json`:
```jsonc
{"duration": 820.83,
 "words": [{"w": "Most", "s": 0.35, "e": 0.85}],
 "beats": [{"chapter": "COLD_OPEN", "text": "…", "start": 0.35, "end": 5.75, "w0": 0, "w1": 14}],
 "chapters": [{"name": "COLD_OPEN", "start": 0.0, "end": 74.3}]}
```
Title and chapter cards are shots (kind `card`), not timing data.

## 7. The technique registry (`style/gae/techniques.json`)

Built by R3. One entry per technique:
- `id`, `kind` (`base`, `overlay`, `transition` or `card`), `intents`
- `slots`, `params` (name, type, default, min, max, values)
- `timing`
- `engine.status` (`done`, `partial` or `missing`)
- `preview` clip and thumbnail

The fixed intent list is in R3's brief and in the file.

- The registry is the single list the page offers and the engine accepts. After R3, the engine role owns this file. It may correct `params` so that they match the real renderer, and it may add these parameter types: `point`, `box`, `camera`, `asset`, `text`. The file must stay valid against `techniques.schema.json`.
- `engine.status` records what the benchmark code could do. The engine role adds `engine.available` (true or false) to every entry: true only when the NEW engine (`bti.engine`) can render that technique today. It also sets `engine.impl` to the new renderer, and updates `techniques.schema.json` to allow the field.
- A technique with `engine.available` false (or absent) is shown in the gallery, greyed out, with the reason. It cannot be chosen. The registry has 71 entries: 56 catalogue records and 15 added `X-*` entries (R3).
- `style/gae/style.json` holds the global constants (label strip geometry, fonts, card timings, spotlight floor, pacing targets). The engine reads its defaults from there, not from literals.

## 8. Facades between roles

### 8.1 Engine facade (`bti/engine/api.py`): implemented by the engine role, called by the editor backend

```python
def open_project(project_dir: Path) -> "Project": ...

class Project:
    def storyboard(self) -> dict: ...
    def timing(self) -> dict: ...
    def resolve(self, storyboard: dict | None = None) -> dict: ...
    def validate(self, storyboard: dict | None = None) -> list[dict]: ...
    def use_draft(self, storyboard: dict | None) -> None: ...
    def frame_at(self, t: float, width: int = 960) -> "np.ndarray": ...
    def render_range(self, t0: float, t1: float, out_path: Path,
                     width: int = 640, fps: int = 15, on_progress=None) -> Path: ...
    def default_params(self, technique_id: str, context: dict) -> dict: ...
    def save(self, storyboard: dict) -> str: ...

def load_style(style_id: str) -> dict: ...
```

What each method does:
- `storyboard()` returns the saved document, unresolved.
- `resolve()` returns a copy with `_t`, `_t0` and `_t1` added. With no argument it resolves the saved document.
- `validate()` returns a list of issues, each `{"level": "error"|"warn", "path": "shots[3].overlays[0].start", "message": "..."}`.
- `use_draft()` swaps in an unsaved draft for `frame_at` and `render_range`. Passing None reverts to the saved document.
- `frame_at()` returns a BGR uint8 frame, 16:9.
- `render_range()` writes silent H.264.
- `default_params()` returns the starting params when a human picks a technique.
- `save()` validates, strips the `_` keys, writes atomically, backs up to `history/`, and returns the new revision (the sha256 of the canonical JSON).
- `load_style()` returns `{"style": ..., "techniques": [...], "intents": [...]}`.

The engine must be safe to keep alive in a long-running process: lazy image loading with an LRU cap, and cache keys that include size and font (R1 section 6.4).

### 8.2 Media facade (`bti/media/api.py`): implemented by the media role, called by the editor backend

```python
def search(query: str, source: str = "commons", kind: str = "image", limit: int = 24) -> list[dict]: ...
def import_candidate(project_dir: Path, source: str, source_id: str) -> dict: ...
def add_upload(project_dir: Path, file_path: Path, meta: dict) -> dict: ...
def check_licence(meta: dict) -> tuple[bool, str, str]: ...
```

What each function does:
- `search()` returns candidates, each with: `source`, `source_id`, `title`, `thumb_url`, `page_url`, `width`, `height`, `mime`, `author`, `licence`, `licence_ok`, `licence_reason`.
- `import_candidate()` downloads the file into `projects/<id>/media/`, runs the licence gate, and returns `{"asset_key": ..., "asset": <assets entry>}`. It raises `LicenceRejected(reason)` when the licence is not allowed.
- `add_upload()` adds a human-supplied file. `meta` must carry `licence`, `source_url` and `author` (or "unknown, PD").
- `check_licence()` returns `(allowed, licence_name, reason)`.

**Licence gate:** allow public domain, CC0, CC BY and CC BY-SA. Reject NC, ND, "fair use", unknown and missing (PLAN.md section 5). Every asset keeps `source_url`, `author` and `licence`.

### 8.3 Stubs

The backend wraps both facades in adapters (`bti/editor/engine_adapter.py`, `media_adapter.py`). If a facade cannot be imported, the adapter falls back to a stub:
- **Engine stub:** a grey 16:9 frame with the shot id, technique and time drawn on it.
- **Media stub:** a fixed candidate list.

`GET /api/health` reports which is in use. This lets the roles work in parallel.

## 9. HTTP API (backend to frontend)

JSON unless stated. The server binds to `127.0.0.1:8560`. Port 8550 belongs to the comic UI. `{pid}` is a project folder name, validated against `^[a-z0-9][a-z0-9_-]{0,63}$`. Every file path served is checked to be inside the project or style folder.

**Health and style**

| Method and path | Purpose |
|---|---|
| `GET /api/health` | `{ok, engine: "real"\|"stub", media: "real"\|"stub"}` |
| `GET /api/styles/{style}` | `{style, techniques, intents}` |
| `GET /style/{style}/previews/{file}` | static preview clips and thumbnails |

**Project and storyboard**

| Method and path | Purpose |
|---|---|
| `GET /api/projects` | `[{id, title, duration, updated_at}]` |
| `GET /api/projects/{pid}` | `{storyboard (resolved), timing, issues, rev, render_key}`; `render_key` covers storyboard, timing, style and media and is what `frame`/`thumb` take as `rev` to be immutable; 409 `{detail, data_error}` when timing or the storyboard file is unusable (`data_error`: `timing`, `storyboard`, `script`, `style`, `project` (project.json), `source` (a source text or dossier), `library`); `GET /api/projects` lists a damaged folder as a row `{id, title: <folder>, data_error, stage: null}`; a `RenderError` on `/frame`, `/thumb` and in a preview job is 422 `{detail, code: "render_failed", shot, overlay, technique}` (never 500); a JSON body nested deeper than 40 levels is 422 `code: "too_deep"`; `DELETE` is 409 `code: "project_busy"` when a save holds the project for more than 2 s |
| `PUT /api/projects/{pid}/storyboard` | body `{storyboard, base_rev}`; returns `{rev, storyboard (resolved), issues}`; 409 if `base_rev` is not the saved revision; 422 with `issues` if there are errors |
| `POST /api/projects/{pid}/validate` | body `{storyboard}`; returns `{issues}` |
| `POST /api/projects/{pid}/defaults` | body `{technique, context}`; returns `{params, slots}` |
| `POST /api/projects/{pid}/approve` | body `{rev}`; returns `{approvals}`; refused if there are error issues or `incomplete` warnings, or if `draw_check` finds an `undrawable` shot or overlay (422, `issues` listed, `undrawable: true`) |

**Frames, audio and previews**

| Method and path | Purpose |
|---|---|
| `GET /api/projects/{pid}/frame?t=&width=&rev=` | JPEG still of the saved storyboard (cacheable by `rev`) |
| `POST /api/projects/{pid}/frame` | body `{t, width, storyboard}`; JPEG still of an unsaved draft |
| `GET /api/projects/{pid}/thumb/{shot_id}?rev=` | small JPEG for the timeline block |
| `GET /api/projects/{pid}/waveform?bins=4000` | `{duration, peaks: [0..1]}` |
| `GET /api/projects/{pid}/audio` | the audio file, with HTTP range support |
| `POST /api/projects/{pid}/preview` | body `{t0, t1, width, fps, storyboard?}` (at most 30 s and 900 frames; an invalid document is a 422 with its issues); returns `{job_id}`; renders on a second engine instance, so stills never wait for it; renders a clip and muxes the matching audio slice |
| `GET /api/jobs/{job_id}` | `{state: queued\|running\|done\|error, progress, result_url, error}` |
| `GET /api/projects/{pid}/files/{path}` | a file inside the project (preview clips, media) |

**Assets and media**

| Method and path | Purpose |
|---|---|
| `GET /api/projects/{pid}/assets` | the assets map, each with a `thumb_url` |
| `PUT /api/projects/{pid}/assets/{key}/regions` | body `{regions}` |
| `POST /api/projects/{pid}/assets/upload` | multipart: `file`, `title`, `artist`, `year`, `licence`, `source_url`, `author` |
| `GET /api/media/search?q=&source=&kind=&limit=` | candidates (section 8.2) |
| `POST /api/projects/{pid}/assets/import` | body `{source, source_id}`; returns `{asset_key, asset}`; 422 with the reason if the licence is rejected |

**Proposals**

| Method and path | Purpose |
|---|---|
| `GET /api/projects/{pid}/proposals` | `{items: [{id, created_at, author, summary, n_changes}], skipped: [{file, reason}]}`; a file that cannot be read is named in `skipped` and never breaks the list |
| `GET /api/projects/{pid}/proposals/{id}` | `{proposal, changes: [{id, op, path, before, after, blocked_by_lock}]}` |
| `POST /api/projects/{pid}/proposals/{id}/apply` | body `{accept: "all" \| [change ids]}`; returns the same shape as the storyboard PUT |

**Proposals** are how an agent takes part without touching the storyboard directly:
- An agent writes `projects/<id>/proposals/<id>.json`. The file holds `{id, created_at, author, summary, base_rev, storyboard}`, where `storyboard` is the agent's full proposed document.
- The backend diffs it against the saved storyboard at the level of shots and overlays, matched by `id`. A change to a locked item is marked `blocked_by_lock`.
- The human accepts all or some of the changes in the page. A change marked `blocked_by_lock` is never applied.

Jobs run in a background worker, never inside a request. Each preview gets a unique file name so the browser cannot show a stale clip (the pattern is in R2).

## 10. The editing page

One page, desktop first (1280 px wide and up), plain HTML/JS/CSS with no build step.

```
┌ top bar: project · Lưu · Kiểm tra (n) · Hoàn tác/Làm lại · Đề xuất · Xem thử 10 giây ──────────┐
├──────────────────────────────────────────────┬─────────────────────────────────────────────────┤
│ Preview: true still from the engine          │ Inspector tabs: Shot · Lớp phủ · Hình · Lỗi     │
│  - camera start and end boxes, draggable     │  - technique (opens the gallery)                │
│  - overlay points and ellipses, draggable    │  - intent, slots, parameter form                │
│ transport: ◀ shot ▶ · time · current word    │  - start word, lock, note                       │
├──────────────────────────────────────────────┴─────────────────────────────────────────────────┤
│ Timeline: chapters · shots (thumbnail, technique badge, colour by intent) · overlays ·         │
│           words (when zoomed in) · waveform · playhead · zoom and scroll                       │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Behaviour:
- **Technique gallery.** Every registry entry is shown, grouped by kind and category, with its preview clip, Vietnamese label, English name, channel-usage badge and engine status. Entries with status `missing` are greyed out. Choosing an entry calls `/defaults` and fills the parameter form. The form is generated from the registry `params`; no form is hand-written per technique.
- **Templates with slots.** A comparison, a grid or an inset is a `base` technique with several slots. Each slot shows the chosen asset and a "choose" button that opens the media tab.
- **Preview.** Any edit redraws the still through `POST /frame` with the draft. Requests are debounced by about 150 ms, and out-of-date responses are dropped. Dragging a box or a point updates `params` live.
- **Timeline.**
  - Click to move the playhead.
  - Drag a shot boundary to retime it. It snaps to word starts; hold Alt to place it freely, which gives a `{"t": …}` anchor.
  - Drag an overlay chip to move it.
  - Split a shot at the playhead (S), merge with the previous shot, delete.
  - Lock (L).
  - Space plays the audio while stills refresh.
- **Media tab.** The project's assets, the region manager for an asset (named regions drawn on the image), search across sources with the licence shown, import, upload.
- **Issues tab.** The list from `validate`. Clicking an issue selects the item.
- **Proposals.** A list. Opening one shows the changes, with accept and reject for each.
- **Undo and redo** are client-side over the draft. Save sends the draft with `base_rev`.

Any edit by the human sets `source: "human"`. The page never invents a technique or a parameter that the registry does not define.

## 11. Proof that the engine is right

- The exporter turns the current Arnolfini build into `projects/arnolfini/storyboard.json` and `timing.json`. It also copies or links the media and extracts the final mix from `final_demo.mp4` for playback.
- **Equivalence test:** at 60 or more sample times spread over the episode, including every card and every overlay onset, the new engine's frame must match the old `frame_at` from the same machine with PSNR of 40 dB or more. Any exception is listed with its reason.
- **Speed targets on this Mac:**
  - warm still: under 150 ms
  - a 10-second preview at 640x360 and 15 fps: under 6 s

## 12. Later phases (not in this build)

1. The 39 reel-only techniques generalised as registry renderers, by family.
2. Gemini skills that write proposals: book profile, story card, script, storyboard draft.
3. You.com visual research and fact checks called live, with the owner's approval for each paid run.
4. Final render and audio on the Windows server, gated on `approvals`.

## 13. Calls made by the analyst (the owner can overturn any of them)

- Web page instead of Flet.
- Copy, do not import, comic code.
- Previews on the Mac only.
- Port 8560, bound to localhost.
- Vietnamese UI labels.
- Shots tile the timeline, and overlays belong to shots.
- Word-index anchors.
- Agents contribute through proposals that never override locks.
- Fonts stay as the current fallback until the owner picks a bundled face.
