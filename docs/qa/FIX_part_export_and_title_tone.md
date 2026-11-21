# Fix Report: Incremental Per-Part Export (`partexport`) and Plain Title Tone

Date: 2026-11-21
Branch / Worktree: `wt/partexport`

## 1. Summary

- **Part A (Incremental ~60 s export parts):** Replaced storyboard-revision-wide part filenames with content-based keys (`bti/export/partkey.py`) hashed only from inputs that affect frames in `[spec.f0, spec.f1)`. Lowered default `part_seconds` from `240` s to `60` s so a small visual edit re-renders ~60 s instead of a whole 4-minute segment or whole video. Updated post-export cache cleaning (`bti/output/clean.py`) to retain the current manifest's `cache/export/parts/` MP4 files across exports while deleting stale parts, `video_all.mp4`, and temporary files; surfaced rendered vs. reused part counts across jobs, manifest, `README.md`, `state.json`, `bti status` hints, and JS labels.
- **Part B (Plain title tone & third owner verdict):** Added the Arnolfini owner verdict (`"Is This a Wedding or a Memory?"`, 7 words vs. rejected `"Was She Already Dead When He Signed the Wall?"`) and the explicit contrast against `"A Prayer or a Shop Sign?"` to `skills/title/TASK.template.md`, tightened Rules 7–8 / Section 3 against manufactured shock/clickbait, and added `BEST_MAX_WORDS = 7` soft warning in `bti/title/rules.py` and `bti/title/check.py` while keeping `MAX_WORDS = 9` as the hard cap.

## 2. Files Changed and Main Symbols

### Part A — Backend, Output & State
- `bti/engine/__init__.py`: added `RENDER_VERSION = 1`.
- `bti/export/partkey.py` (new): `engine_render_version`, `asset_file_signature`, `style_signature`, `resolve_storyboard`, `part_key_payload`, `part_key`, `part_keys`.
- `bti/export/plan.py`: `plan_parts(target=60.0)`, `part_key` accepting storyboard dicts via `partkey.part_key` with bare-string fallback.
- `bti/export/settings.py`: `Settings.part_seconds = 60.0`.
- `config/server.json`: `"part_seconds": 60` in both `"windows"` and `"default"`.
- `bti/export/render.py`: updated `render_part` log/progress notes (`"Đã có sẵn, dùng lại"` / `"Đã dựng mới"`).
- `bti/export/run.py`: `_timing_sig`, `_part_ready`, `part_keys_for`, `_plan_note_vi`, `_done_summary_vi`, `plan_for`, `state`, `start`, `build_parts` (`prepare`, `join`, `finish` writing `parts_total`, `parts_rendered`, `parts_reused` into manifest/result and unlinking stale parts at join).
- `bti/output/clean.py`: removed `"export"` from `CACHE_DIRS`; added `current_export_part_files`, `_export_targets`, `_kept_export_stats`, `_prune_empty_export_dirs`; updated `targets` and `clean_project` to keep current parts and record `kept_parts` and `kept_parts_bytes`.
- `bti/output/parts.py`: `_part_counts`, `video_facts`, `write_export` adding `parts_total`, `parts_rendered`, `parts_reused`.
- `bti/output/readme.py`: added `Các đoạn dựng` row in `readme_md`, updated `NEXT_TEXT["export"]` and `Dọn dẹp thư mục làm việc` kept-parts summary.
- `bti/output/facts.py`: `_job_row` appends rendered/reused part counts for done export jobs.
- `bti/editor/state_api.py`: updated `Spec("export.start").when`, `cost_about(spec, c)` (shows `"only changed ~60 s parts (full export: about 25 minutes)"` when prior export/parts exist), and `_action`.
- `bti/editor/hints.py`: updated `HINTS["approval_stale"]` and `HINTS["part_missing"]`.
- `bti/editor/static/js/labels.js` & `bti/editor/static/js/errmsg.js`: updated `OUTPUT_LABELS.hint`, added `PARTEXPORT_LABELS` merged into `EXPORT_LABELS`, updated `STAGE_CODES.export.approval_stale`.
- `skills/export/SKILL.md`, `docs/AGENT_API.md`, `docs/APP_GUIDE.md`: updated docs + generated hints rows.

### Part B — Title Rules, Checker & Prompt Template
- `bti/title/rules.py`: added `BEST_MAX_WORDS = 7`, exported `BEST_MAX_WORDS` / `BEST_MAX_WORDS_TEXT` in `template_values()` and `"best_max_words"` in `public()`.
- `bti/title/check.py`: `_title_problems` emits a non-blocking warning when candidate word count exceeds `R.BEST_MAX_WORDS` (`7`) while `> R.MAX_WORDS` (`9`) remains an error.
- `skills/title/TASK.template.md`: updated Rule 7, Rule 8, Section 3 step 2 & step 5, Section 4 (three owner verdicts + prayer-vs-wedding explanation), and Section 5 warning documentation.

### Tests Added / Updated
- `tests/export/conftest.py`, `tests/export/fakelongjob.py`, `tests/export/test_settings.py`, `tests/export/test_plan.py`, `tests/export/test_job.py`
- `tests/output/output_helpers.py`, `tests/output/test_clean.py`, `tests/output/test_hooks.py`, `tests/output/test_api.py`, `tests/output/test_docs.py`, `tests/output/test_stays_working.py`
- `tests/longjob/test_longjob_config.py`, `tests/state/test_state.py`
- `tests/title/test_title_check.py`, `tests/title/test_title_rules.py`, `tests/title/test_title_routes.py`
- `tests/editor_frontend/partexport.test.mjs`

## 3. What Goes Into `part_key` — and What Is Left Out

Every `PartSpec` (`[f0, f1)` at `fps`) is hashed via `partkey.part_key_payload` (12-char SHA-1 prefix of canonical sorted JSON):

| Included in `part_key` | Why |
|---|---|
| `KEY_SCHEMA_VERSION`, `engine_version` (`bti.engine.RENDER_VERSION`) | Any renderer semantics change or schema upgrade safely invalidates cached parts. |
| `style` id + `style_sig` (`style.json`, `techniques.json` + patches, font & serif signatures, `geo` dir stamp) | Global look/typography/technique defaults affect rendered frames across parts. |
| `[spec.f0, spec.f1, spec.fps]`, `width`, `quality` | Output geometry, frame slice, cadence, and encoder preset change output bytes. |
| Active shots in `[f0, f1)` (`_t0`, `_t1`, `technique`, `slots`, canonical visual `params`) + overlapping `overlays` | Every shot and overlay whose time span intersects the part contributes pixels to its frames. |
| Preceding shot (`role="prev"`) when incoming shot at `f0` has `transition_in.dur > 0` overlapping `[f0, f1)` | Cross-fades/dissolves at a boundary read pixels from the outgoing shot. |
| `asset_file_signature(project_dir, asset["file"])` + `kind`, `width`, `height`, `aligned_to`, `content_box`, referenced `regions` geometry (`x`, `y`, `rx`, `ry`), and recursive `aligned_to` mask assets for **only** assets/regions referenced by included shots/overlays | Catches image/video replacements, dimension/box tweaks, and region crop changes strictly for parts that show them. Files `<= 2 MiB` use full SHA-1; larger media use `size + mtime_ns + 64 KiB head/tail SHA-1`. |
| `timing["words"][i]["s"]` for word anchors referenced in included shots/overlays or the next shot / `end` boundary | Changing word timings shifts shot/overlay cuts (`_t` resolution) only where those words govern time spans. |
| `identity` only when an included shot/overlay uses an `ID-*` technique | Identity title card changes invalidate the title-card part without touching the rest of the video. |
| `end` fade (`[end_t, fade_s]`) only when the end fade window overlaps the part | Ending fade touches only the trailing part(s). |

Deliberately excluded so unrelated edits never invalidate unchanged parts:
- Storyboard-level metadata: `sb["title"]`, `approvals`, `project`, `schema`.
- Non-visual shot/overlay/region fields: `shot["id"]`, `shot["note"]`, `shot["locked"]`, `shot["source"]`, `shot["intent"]`, `shot["beat"]`, `asset["credit"]`, `region["label"]` (plus `title`/`artist`/`year` asset metadata, which are only editor-time defaults).
- Unused `assets`, unused `regions` on used assets, unused `words` in `timing.json`, and audio file changes (audio is muxed after joining parts, so audio-only changes never re-render video parts).

## 4. Part Length, Dependencies & Cleaning Disk Budget

- **Part length (`60` s):** `config/server.json` (`"part_seconds": 60` for `windows` and `default`), `bti/export/settings.py` (`Settings.part_seconds = 60.0`), and `bti/export/plan.py` (`plan_parts(..., target: float = 60.0)`) all align on ~60 s parts (`30..90` s shot-aligned windows except when a single shot exceeds 90 s and is split cleanly at `60 * fps`).
- **Cleaning & disk footprint:** `bti/output/clean.py` keeps the files named in the current fresh `export/export.json` manifest's `parts` list inside `cache/export/parts/`. Unlisted/stale `part_*.mp4` files, `cache/export/video_all.mp4`, `cache/export/chapters.ffmeta`, and all other temporary dirs (`frames`, `thumbs`, `previews`, `uploads`, `picks_auto/runs`, `voice`, `longjobs/work`, longjob `.log`, `wave_*.json`) are still deleted when cleaning is enabled.
  - At typical 1080p final quality (~10 Mbps H.264), keeping current parts costs roughly **~840 MB per 689 s video** (less for calmer zoomed stills: ~4.09 MB for the 12 s real proof).
  - Audio is still re-muxed via `-c:v copy` on every export (fast, seconds, preserves exact audio changes without re-rendering frames).

## 5. Real Incremental Export Proof (Windows Snapshot `partexport`)

Executed with real `bti.engine`, real `ffmpeg` / `ffprobe`, real `arnolfini_commons.jpg` + 12 s AAC audio (`48 kHz`, `-16 dB`), 3 shots (`0–4 s`, `4–8 s`, `8–12 s`), `part_seconds=4.0`, 1920x1080 @ 30 fps (`360` frames total), `FakeManager` (never touched `_heavy.lock`), inside temporary snapshot folder cleaned afterward (`PROOF_CLEAN`):

| Run | Action | Wall Time | Output Probe | Parts Breakdown | Kept / Freed (`clean_project`) |
|---|---|---|---|---|---|
| **Run 1** | First clean export | **22.32 s** | `360` frames, `12.0` s | `3/3` rendered, `0` reused (`part_01_9af15941399f.mp4`, `part_02_8268d8bfeb05.mp4`, `part_03_21130cdd5971.mp4`) | `kept_parts=3` (`4,093,921` B), `freed_bytes=4,093,048` B |
| **Run 2** | Changed `s0002` overlay `X-ANN-01` text (`"First label"` -> `"Second label"`), re-approved | **7.80 s** | `360` frames, `12.0` s | `1` rendered (`part_02_bb84c177d341.mp4`), `2` reused (`part_01_9af15941399f.mp4`, `part_03_21130cdd5971.mp4`, identical mtime & size; old `part_02_8268d8bfeb05.mp4` removed) | `kept_parts=3` (`4,097,024` B), `freed_bytes=4,096,151` B |

## 6. Part B: Title Tone Updates & Updated Section 4 Verdicts

- `bti/title/rules.py` defines `BEST_MAX_WORDS = 7` alongside `MAX_WORDS = 9` and exposes `best_max_words` / `BEST_MAX_WORDS` / `BEST_MAX_WORDS_TEXT`.
- `bti/title/check.py` warns (non-blocking) when a candidate has `> 7` words (`<= 9`), while `> 9` remains a blocking error.
- `skills/title/TASK.template.md` Section 2 rules 7–8 and Section 3 steps 2 & 5 warn against shock/clickbait (`death`, `secrets`, `crimes`, `"already dead"`) when the narration is calmer, and highlight concrete open human-moment tension.
- **Full updated Section 4 of `skills/title/TASK.template.md`:**

> ## 4. Three real verdicts of the owner (learn from them)
> For the video on Petrus Christus's panel of St. Eligius, whose narration asks whether the picture is a prayer or a shop sign and answers "both":
> - **Rejected: "A Prayer or a Shop Sign?"** The owner: "not intriguing or interesting or capture the essence of the video". Why it fails: two labels, no thing one can picture; the question means nothing before watching (rules 4, 6).
> - **Accepted: "The Saint Who Was Also an Advertisement"**. Why it works: two concrete things that contradict each other; it is the video's own answer in one line; it is true to the narration (the saint, the advertisement for the goldsmiths, "it is both"); a stranger wants to know how a saint can be an advertisement.
>
> For the video on Jan van Eyck's Arnolfini Portrait, whose narration weighs whether the painting records a marriage or commemorates a wife who had already died, and closes with "So is this a wedding or a memory?":
> - **Rejected: "Was She Already Dead When He Signed the Wall?"** The owner: "I also don't like the name", and asked for "clear concise like is this a wedding or a mourning of a memory ? dont click bait be concise but still intrigue focus on the intriguing factor". Why it fails: it reaches for shock ("Already Dead") and packs two dramatic clauses into nine words when the narration's own open question is calmer and cleaner (rules 7, 8).
> - **Preferred direction: "Is This a Wedding or a Memory?"** ({{BEST_MAX_WORDS}} words). Why it works: it is the video's own real open question in plain words, short and clear, with no clickbait; both sides are concrete human things a stranger can picture at once, and the contrast between them makes one want the answer.
>
> What separates **"A Prayer or a Shop Sign?"** (rejected) from **"Is This a Wedding or a Memory?"** (wanted): both have the same "A or B?" shape, but the first sets two dry categories against each other with no human stake, while the second puts two human moments — a wedding and mourning a lost life — in tension, so a stranger immediately feels why the answer matters.

## 7. Decisions Made Where the Brief Was Silent

1. **String fallback in `plan.part_key`:** Preserved string-revision compatibility for legacy unit tests when `plan.part_key` is called with a bare revision string instead of a storyboard dict, while production calls in `run.py` always use full `partkey.part_keys`.
2. **Stale part cleanup timing:** Kept partial render parts during active resume, removing superseded `part_*.mp4` files inside `join()` right after concatenation succeeds (and again during `clean_project` after successful publish).
3. **`BEST_MAX_WORDS = 7` enforcement level:** Implemented as a non-blocking warning in `bti/title/check.py` (keeping `MAX_WORDS = 9` error) so valid 8–9 word titles like the existing `test_title_check.py` fixture are flagged gently rather than rejected outright.
4. **Keeping `"parts"` dir when manifest lists parts vs. legacy `parts=[]`:** When `export.json` exists with `"report_status": "ok"` and non-empty `parts`, `clean_project` keeps only the listed `cache/export/parts/*.mp4` files and removes everything else under `cache/export`; when `parts` is empty (`parts=[]`), empty `cache/export/parts` and `cache/export` directories are pruned so existing output-cleaning fixtures stay clean.
5. **Transition boundary inclusion:** A shot starting at `spec.f0` with `transition_in.dur > 0` pulls its preceding shot (`role="prev"`) into that part's key so boundary dissolves never reuse stale outgoing frames.

## 8. Verification Results (Run After Final Code & Doc Edits)

### Windows Snapshot (`partexport`) Test Suites
- `tests/export`: `84 passed, 2 skipped, 1 warning in 46.54s` (`test_server.py` skipped without `--run-server`)
- `tests/output`: `81 passed, 1 warning in 20.98s`
- `tests/title`: `197 passed, 1 warning in 45.26s`
- `tests/longjob`: `69 passed, 1 skipped, 1 warning in 8.38s`
- `tests/auto`: `242 passed, 1 warning in 88.41s (0:01:28)`
- `tests/editor`: `530 passed, 1 warning in 242.58s (0:04:02)`
- `tests/engine -m "not slow"`: `783 passed, 14 skipped, 166 deselected in 356.58s (0:05:56)`
- `tests/state`: `322 passed, 1 warning in 205.59s (0:03:25)`
- `tests/cli`: `132 passed, 1 warning in 52.97s`

### Generator Checks (`tools/deploy/snapshot_py.sh partexport`)
- `python -m bti.cli.docgen --check` -> exit `0`
- `python -m bti.ops.doc --check` -> exit `0`
- `python -m bti.editor.hints --check` -> exit `0`

### Mac JS Checks (`node`)
- `node --check bti/editor/static/js/labels.js bti/editor/static/js/errmsg.js` -> exit `0`
- `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`: `tests 497` / `pass 496` / `fail 0` / `skipped 1`

## 9. What Could Not Be Verified

- Full ~12-minute production export on a real book project (`tests/export/test_server.py` marked `server`, skipped by default without `--run-server`) and real live `LongJobManager` GPU lock queueing.
- Live browser DOM rendering of the export view (`views/export.js` was outside task ownership).

## 10. Needs Another Worker

- `bti/longjob/config.py`: `ExportConfig.part_seconds` fallback default still reads `240` in code (overridden at runtime by `config/server.json`, which is now `60`). Left untouched because `bti/longjob/` is not in this task's file list.
- `bti/editor/static/js/views/export.js`: Wire `PARTEXPORT_LABELS.partsPlan` and `PARTEXPORT_LABELS.partsSummary` (already exported alongside `EXPORT_LABELS` in `bti/editor/static/js/labels.js`) into the export page UI so the browser displays rendered vs. reused part counts alongside the CLI/output docs. Left untouched because `bti/editor/static/js/views/` was outside this task's file list.
