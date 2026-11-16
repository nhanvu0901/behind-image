# Behind the Image — architecture and build plan

**Status:** plan only, no code yet. Written 2026-11-12 by the architect, for an implementing agent.
**Owner:** Master (Vu Trong Nhan). Reply to Master in Vietnamese; code, comments and commits in English.

## Tóm tắt cho Master (tiếng Việt)

- Project mới, tách khỏi `comic-book-pipeline`, làm Shorts 15–35 giây kể chuyện thật đằng sau một bức tranh hoặc ảnh cũ, cho một kênh mới. Sau đó ghép nhiều Short thành video dài.
- Không chép code cũ. Repo comic được gắn vào làm "engine" (git submodule, ghim một commit). Chỉ một file `bti/engine.py` được gọi sang engine. Nhờ vậy các bản sửa bên comic (PR #20, #21 và PR hình ảnh) chỉ cần nâng commit là có.
- Dùng lại: giọng Chatterbox, bộ render hình và âm thanh, phụ đề, bộ tìm vùng zoom trong tranh, nguồn ảnh The Met, phần ghi công trong mô tả.
- Viết mới: nguồn ảnh Wikimedia Commons, cổng lọc giấy phép ảnh, bộ tìm chuyện, bộ viết kịch bản ngắn, bước duyệt, sổ ghi chuyện đã làm.
- 6 giai đoạn, khoảng 4–5 ngày công cho bản chạy được (giai đoạn 0–5). Giai đoạn 0 là xem và đo video của các kênh mẫu trước khi chốt định dạng.
- Vẫn giữ nguyên tắc của Master: không chạy giọng đọc hay render trước khi Master duyệt.

---

## 1. Goal and evidence

Make 15-35 second faceless Shorts that tell the true story behind ONE famous painting or old photograph, on a new channel, then compile them into long-form videos.

Why: two independent studies (2026-11-12) found new channels under 6k subscribers in this niche with median 10k-37k views per Short (@artloris 29.5k, @WorldUncoveredIn30 37k, @HistoryByArthur 10k, @TheArtBehind 12k-292k). Our comic channel has a 1.6k median. Caveats: the sample contains only channels found through their hits; about 5% of Shorts from channels under 1k subscribers reach 10k views; nobody has watched the reference videos yet (phase 0 fixes that). Reports are in `docs/research/`.

## 2. Architecture

```
            ┌──────────────────────── behind-the-image (this repo) ────────────────────────┐
 seeds ──▶  scout ──▶ fetch + licence gate ──▶ ground ──▶ script ──▶ plan ──▶ REVIEW ──▶ voice ──▶ render ──▶ describe
            (new)      (new, sources/*)        (new)      (new)     (new)   (new gate)      │         │
            └───────────────────────────── bti/engine.py (facade) ───────────────────────────┼─────────┘
                                                   │ only importer                            ▼
                                 engine/  = git submodule of comic-book-pipeline, pinned commit
                                 stage_4 TTS · stage_5 render/mix/captions · art_pipeline regions · LLM chain
```

**Decision: reuse the comic repo as a pinned engine. Do not fork it and do not copy files out of it.**

- `engine/` is a git submodule of `https://github.com/nhanvu0901/comic-book-pipeline`, pinned to one commit.
- `bti/engine.py` is the ONLY module allowed to import engine code. Everything else imports `bti.engine`.
- Never edit anything under `engine/`. An engine change goes as a PR to the comic repo, then a pin bump here.
- Why not copy: the render and voice code is being fixed right now (comic PR #20 audio start and pace, PR #21 script rules, and a render-motion PR in progress). A pin takes those fixes with one commit bump. A copy diverges immediately. `art_pipeline/` inside the comic repo already works this way (imports `stages.*` read-only, overrides module attributes at call time).
- Pin to a commit that includes PR #20 and the render-motion PR once Master merges them. Until then pin current `main` and record the gap in `docs/ENGINE_PIN.md`.

### 2.1 Facts about the engine the facade must handle (verified in code on origin/main)

1. **`.env` loading.** `engine/config.py` calls `load_dotenv()` at import. The facade must call `load_dotenv(<repo>/.env)` itself BEFORE importing any engine module, so our own `.env` is the one in force.
2. **Project root is bound by value in several modules.** `config.PROJECTS_ROOT` is `engine/projects` and is created at import. These modules hold their own module-level copy: `stages.stage_4.pipeline`, `stages.review_gate`, `stages.stage_5.pipeline`. `stages.stage_5.shots` reads `config.PROJECTS_ROOT` inside a function at call time. The facade provides one context manager, `engine_root(path)`, that sets `PROJECTS_ROOT` on `config` and on each of those three modules and restores all of them in `finally`. Before using any other engine module, grep it for `PROJECTS_ROOT` and add it to the list if it binds a copy. Model: `engine/art_pipeline/tts.py::synthesize_art` (save, set, restore).
3. **Hard review gate.** `stages.stage_4.pipeline.synthesize_project` calls `review_gate.ensure_reviewed(project)`, which raises `SystemExit` unless `<project>/review/locks.json` has `approved: true` and a `narration_sha1` equal to the sha1 of the current `narration.json` bytes. Do NOT set `REVIEW_GATE=0`. This project has its own review step (section 6) that writes that file in the same schema, so the engine's gate passes because Master really approved. Note: `art_pipeline`'s own TTS wrapper predates the hard gate and does not handle it; do not call `synthesize_art`.
4. **Art helpers resolve their own folder.** Project-level functions in `art_pipeline` (`process_artworks`, `fetch_artworks`, `assemble_art_video`) write under `engine/art_projects/`. Call the path-level functions instead: `regions.propose_regions_vlm(image_path, label)`, `regions.build_page_dict(...)`, `regions.filter_regions`, `regions.grid_fallback_regions`, `assemble.plan_shots(...)`, `assemble.build_srt(...)`.
5. **Render switches for real artworks.** Set on `stages.stage_5.shots` for the duration of a render and restore after: `MIRROR_PANELS = False` (never mirror a real artwork), `INPAINT_BUBBLE_TEXT = False` (it could erase a signature). Model: `engine/art_pipeline/video.py::assemble_art`. `MIRROR_PANELS` is a name imported into `shots` from `config` (default already off; an env variable can turn it on), so set it on `shots` explicitly, and have the contract test check it with `hasattr` rather than looking for a definition.
6. **Known render weaknesses** (measured against competitors): pan/zoom is too slow by default (`ZOOM_AMPLITUDE=0.06`, `PAN_ZOOM=1.15` in `stages/stage_5/shots.py`), and an image with aspect 1.7 or wider is letterboxed over a blurred copy (`LANDSCAPE_COVER_MAX_ASPECT`, `PANEL_FIT_MODE="contain"`). Comic PR #22 (`fix/render-motion-fullbleed`, open, not merged on 2026-11-12) fixes both for still images: a full-bleed moving camera behind `FULLBLEED_MOTION=1` (`CAMERA_SPEED_MIN/MAX=16/40` % of width per second, `FULLBLEED_MAX_ASPECT=3.5`, so a wide image is panned across instead of letterboxed), measured at 22-23 % of width per second and 0.000 frozen share on still shots. Prefer a pin that includes it and use those switches. Until the pin includes it, override them from `bti/config.py`. All four are read from environment variables of the same name when `shots` is first imported, so the facade must put the values into `os.environ` before the first engine import (same place as the `.env` load); after import, set the module attribute instead. Verify the result with `tools/vmetrics.py` (phase 4 acceptance).
7. **Mac ffmpeg lacks one filter** used by caption or card rendering (`utils.ffmpeg_filter.has_filter`). Tests that need it must skip on machines where `has_filter` is false; they pass on the Windows server.

### 2.2 Engine surface used (exact signatures)

| Purpose | Engine symbol |
|---|---|
| Voice | `stages.stage_4.pipeline.synthesize_project(project_name, *, speed=1.0, volume=1.0, emotion=None, flat=False, voice_id=None, model=None, provider=None, post_atempo=None, skip_review=False, ...)` reads `narration.json`, writes `audio.wav`, `word_timestamps.json`, `scene_timings.json`, `caption_chunks.json` |
| Spoken form | `utils.spoken_text.to_spoken(text)`; rules text `stages.stage_3.spoken_rules.SPOKEN_TEXT_RULES` |
| Narration schema | `stages.stage_3.schema.Narration`, `Scene` |
| One shot | `stages.stage_5.shots.render_shot(shot, out_path, *, work_dir=None, progress=None, corner_logo=None)` with `stages.stage_5.schema.Shot(shot_id, scene_id, duration_seconds, panel_bbox{x,y,w,h}, source_image, motion, is_intro, fit_fill, keep_contain, no_mirror, ...)` |
| Join, mix, encode | `stages.stage_5.pipeline._concat(shot_paths, out_path)`, `stages.stage_5.audio.mix_audio(tts_wav, out_path, *, bg_music_path=None, progress=None)`, `stages.stage_5.pipeline._final_encode(silent_video, audio_mixed, out_path)` |
| Captions | `stages.stage_5.captions.build_ass(word_timestamps, total_duration, caption_pop=None) -> str` (burn with ffmpeg as `art_pipeline/assemble.py` does) |
| Zoom regions | `art_pipeline.regions.propose_regions_vlm(image_path, artwork_label, *, log) -> (regions, summary, model)`; percent boxes, grid fallback |
| Shot planning model | `art_pipeline.assemble.plan_shots(narration, plan, pages_by_number, scene_timings, *, audio_duration)` (read it; reuse or mirror for the short format) |
| LLM with fallbacks | `stages.stage_3._llm.call_with_chain(*, system, user, models=None, max_tokens=2000, progress=None, label="llm", validator=None) -> (text, model)` |
| Museum source | `art_pipeline.sources.met` (`search`, `fetch_meta`, `fetch_image`, `validate_cc0`, `parse_candidate`) |
| Review state | `stages.review_gate.load_state`, `save_state`, `narration_sha1` (same file format as ours) |

The contract test (`tests/test_engine_contract.py`) imports each symbol and checks its parameters with `inspect.signature`, so a pin bump that changes one fails the test.

**Not reused** (comic-bound or wrong for this niche): comic Stage 1-3; `stages/research_scout/ledger.py` (modes and keys are comic issue numbers, and writes are locked to the comic server); `art_pipeline/hunt.py` (no licence gate by design); the calm sleep-voice settings and 165-270 word budgets in `art_pipeline/config.py`.

## 3. Repository layout

```
behind-the-image/
  PLAN.md  README.md  .env.example  .gitignore  pyproject.toml (or requirements.txt)
  engine/                     git submodule (pinned)
  bti/
    __init__.py  __main__.py  cli.py
    config.py                 every setting, env-overridable, with clamps
    engine.py                 the facade (section 2)
    sources/__init__.py       ImageSource protocol
    sources/commons.py        Wikimedia Commons
    sources/met.py            wraps the engine's Met adapter
    licence.py                hard licence gate
    scout.py  ledger.py       candidate stories, done-ledger (own SQLite)
    ground.py                 claims with sources
    script.py                 prompts, validators, Gemini prompt export and script import
    plan.py                   beats to visuals
    review.py                 review sheet + approval
    voice.py  render.py       through the facade
    describe.py               title, description, credits
    longform.py               phase 6
  prompts/                    writer.md, scout.md, title_templates.json
  tools/vmetrics.py           video measuring tool (copied from the research)
  tests/  docs/research/  docs/FORMAT_SPEC.md  docs/ENGINE_PIN.md
  projects/                   one folder per video (git-ignored)
```

## 4. Data contracts

`projects/<slug>/story.json`
```json
{"slug": "cadaver-synod", "format": "reveal", "series": "behind-the-painting",
 "images": [{"id": "img1", "file": "raw/img1.jpg", "source": "commons",
             "source_id": "File:Jean_Paul_Laurens_Le_Pape_Formose_et_Etienne_VI_1870.jpg",
             "source_url": "https://commons.wikimedia.org/wiki/File:...", "author": "Jean-Paul Laurens",
             "licence": "PD", "licence_url": "", "credit_line": "...", "width": 4000, "height": 3000}],
 "claims": [{"id": "c1", "text": "In 897 a dead pope was put on trial.",
             "sources": ["https://en.wikipedia.org/wiki/Cadaver_Synod"], "quote": "..."}]}
```
- `narration.json`: the engine's Scene schema, unchanged (Stage 4 reads it). Extra data never goes into it.
- `visual_plan.json`: one entry per scene: `{"scene_id", "image_id", "region": {x,y,w,h in percent} | null, "motion"}`. Follow `art_pipeline/visual_plan.py`.
- `preprocessed/page_NNN.json`: one per image, the engine's page schema, built with `regions.build_page_dict` (one image = one page, regions = panels).
- `review/locks.json`: `{"approved": bool, "approved_at": iso | null, "narration_sha1": str | null, "locks": {}}` (the engine's schema).
- `ledger.sqlite` (repo root, git-ignored): `stories(key PRIMARY KEY, title, image_source_id, status, created_at, published_url)`. Key = normalised subject plus image id.

## 5. Rules enforced in code (not only in prompts)

1. **Licence gate (`licence.py`).** Allow only: public domain, CC0, CC BY, CC BY-SA. Reject NC, ND, "fair use", unknown, or missing metadata, with a message that names the licence found. An image cannot enter a project without `source_url`, `author` (or "unknown, PD") and `licence`. British Museum images (CC BY-NC-SA) must be rejected. The gate runs in `fetch` and again in `render` (defence in depth).
2. **No AI-generated images of real history.** This project has no image-generation code.
3. **Fact gate.** Every sentence in the script carries one or more claim ids (the writer returns them alongside the text); `script.validate` rejects a sentence with none, or with an id that is not in `story.json`. A claim needs at least one source URL and a supporting quote. No source, no sentence.
4. **Credits.** `describe.py` lists author, licence and URL for every image (required by CC BY and CC BY-SA), plus the fact sources.
5. **Originality.** The script explains and gives context; it never reads a source paragraph back. YouTube's "inauthentic content" policy excludes slideshows with little narrative.
6. **Review before spend.** `voice` and `render` refuse to run without Master's approval of the current script (section 6). Never bypass.
7. **General rules only.** No rule may name a specific painting, person or story.

## 6. Review step (the owner's gate)

- `bti review <slug>` writes `review/review.html`: the script with claim sources, each beat next to its image and zoom region, the licence line per image, the title and description. No audio or video is made before this.
- `bti approve <slug>` writes `locks.json` with `approved=true` and the sha1 of `narration.json`. Any later edit to the script makes the approval stale (the engine checks the sha).
- An automated agent run stops after `review` and reports to Master. Only Master runs `approve`, unless Master explicitly says otherwise for that run.

## 7. Formats (defaults; phase 0 measurements override them)

- **reveal** (default): ONE famous image. Sentence 1 states the surprising fact as a statement. 3-5 beats, each zooming to the region that shows what the sentence says. 15-35 s, 45-110 words, pace about 3.5 words per second.
- **carousel**: 3-5 old photographs, one fact each, the same series title every time. Up to 30 s.
- One fixed title template per series (`prompts/title_templates.json`), because the breakout channels reuse one template.
- First frame is the image, bright and filling the screen; sound from frame 0; captions of 1-3 words; no spoken subscribe line; the last line connects back to the first image so the loop works.

## 8. Phases

Each phase ends with: tests passing, a commit on a branch, and a short report (what was built, what was measured, what is unverified).

**Phase 0 — format study (0.5 day).** Download 8 reference Shorts (2 each from @artloris, @WorldUncoveredIn30, @HistoryByArthur, @TheArtBehind) with yt-dlp, one at a time with sleeps, no cookies; stop on HTTP 429. Run `tools/vmetrics.py`, build frame sheets, LOOK at them, and write `docs/FORMAT_SPEC.md`: length, number of images, how a landscape painting is framed in 9:16 (full-height pan, or image with a text band), caption style and position, title text on screen, image changes per 10 s, first sound time, voice type if it can be told, ending. If the spec contradicts section 7, the spec wins and section 7 is updated.

**Phase 1 — skeleton and facade (0.5 day).** `git init`, add the submodule, `bti/engine.py` with `engine_root()` and the artwork render switches, `bti/config.py`, CLI, contract test, `.env.example`. Acceptance: `python -m bti doctor` prints the engine commit, ffmpeg version, whether the Chatterbox venv was found, and whether the caption filter exists; contract test passes; importing `bti` does not create files outside this repo except `engine/projects/` (unavoidable, git-ignored there).

**Phase 2 — sources and licence gate (1 day).** `ImageSource` protocol: `search(query, limit)`, `fetch_meta(source_id)`, `fetch_image(meta, dest)`, `licence(meta) -> (allowed, name, reason)`, `credit(meta)`. `commons.py` uses the MediaWiki API (`prop=imageinfo`, `iiprop=url|size|extmetadata`; licence from `LicenseShortName`, `License`, `UsageTerms`; author from `Artist`); set a descriptive User-Agent; minimum short side 1200 px. `met.py` wraps the engine adapter. `bti fetch <slug> --commons "File:..."` and `--met <id>`. Acceptance: fixture-based tests (recorded JSON, no network) for PD, CC0, CC BY, CC BY-SA accepted and NC, ND, missing rejected; credits generated; too-small image refused.

**Phase 3 — story, script, plan, review (1.5 days).**
- `ground.py`: build `claims` from Wikipedia extracts of the artwork, the artist and the event (reuse the approach of `art_pipeline/grounding.fetch_wikipedia_extract`), each with URL and quote; a web-research fallback only behind an explicit flag because it costs money.
- `script.py`: writer prompt (embeds `SPOKEN_TEXT_RULES`, the format rules and the claims list; asks for JSON `[{text, claim_ids, image_id, look_at}]`); validators (word budget, sentence 1 is a statement with a concrete fact within 10 words, fact gate, no digits or symbols after `to_spoken`, no subscribe line); retry with the validator's message; writes `narration.json`. Also `bti prompt <slug>` (exports one prompt Master can paste into Gemini) and `bti import-script <slug> <file>` (takes Master's text, maps sentences to claims, fails loudly on unmapped facts). Master often writes scripts with Gemini, so both paths are first-class.
- `plan.py`: regions per image through the facade (`propose_regions_vlm`, grid fallback when the VLM is unavailable), map each beat's `look_at` to a region, pick motion so consecutive shots differ.
- `review.py`: section 6.
- Acceptance: offline tests with fixtures and a fake LLM; no paid call in tests; a script with an unsourced sentence is rejected; an edited script invalidates approval.

**Phase 4 — voice and render (1 day).** `voice.py` calls `synthesize_project` inside `engine_root()` (gate must pass). `render.py`: Shots from `visual_plan.json` (see `plan_shots`), `render_shot` per shot, `_concat`, burned captions from `build_ass`, `mix_audio` with an optional music file, `_final_encode`; then `describe.py`. Acceptance on one real story, measured with `tools/vmetrics.py`: duration 15-35 s; first sound under 0.05 s; apparent motion at least 15% of frame width per second; frozen share under 0.02; sharp share in the first 3 s at least 0.9; loudness between -16 and -13 LUFS; every image credited in the description; a frame sheet attached for Master.

**Phase 5 — scout and ledger (1 day).** `scout.py` proposes stories from seed lists (Commons featured pictures by topic, Wikipedia lists of famous paintings and historic photographs, "on this day"), scores them (famous image, one surprising verified fact, a licence-cleared image at 1200 px or more) and writes candidates to the ledger; `bti next` creates the next project. Acceptance: 20 candidates, none repeated, each with a cleared image and at least one sourced claim.

**Phase 6 — long-form compiler (later, 2-4 days).** Stitch 8-12 finished stories into one 16:9 video with chapter cards and an SRT, reusing the art long-form assembler (`_concat_xfade`, chapter cards, `build_srt`); visuals are re-planned for 16:9, not letterboxed. Reason (confirmed on the YouTube Blog, 2026-11-12): from 2027-02-01 a channel must keep 10M qualified Shorts views over the last 90 days to earn Shorts ad and Premium revenue, and new applicants need 8,000 watch hours in 365 days or 20M Shorts views in 90 days. Below the Shorts line a channel still earns on long-form. Of the five comic competitors measured, only one would clear 10M, so long-form is the realistic income path and Shorts are the funnel. Public-domain images make long-form legally safe here, unlike narrated recaps.

## 9. Runtime and limits

- Develop and test on the Mac. The Mac has no Chatterbox; voice runs on the Windows server (`ssh winbox-cmd`, comic repo at `D:\code\comic-book-pipeline`, venvs `.venv` and `.venv-chatterbox`; set `CHATTERBOX_VENV`). That server is production for the comic channel: do not install, deploy or change anything there without Master's approval, and never run two heavy jobs at once (Magi or Chatterbox or a render).
- Own `.env` (Master copies the keys). Never print, log or commit secrets.
- Tests never call paid APIs or YouTube. Ask Master before any paid call in a live run and state the expected cost.
- Work on a branch, open a PR, do not push to main. Commit messages end with the attribution trailer the session provides.

## 10. Risks

| Risk | Mitigation |
|---|---|
| The format assumptions are wrong | Phase 0 measures real videos before templates are written |
| Engine pin breaks on bump | Contract test; one facade file to fix |
| Landscape paintings look small in 9:16 | Phase 0 decides the layout; render PR in the engine; vmetrics acceptance |
| Wrong or missing licence slips through | Gate at fetch and at render; allow-list, not deny-list |
| A false "fact" | Fact gate with source and quote; Master reviews before voice |
| Channel flagged as templated slideshow | Real narration with analysis, varied stories, credits; keep a structure log like `art_pipeline/video.append_variety_log` |
| Word timings are spread evenly inside a sentence (no aligner) | Fine for 1-3 word captions at this length; note as a later improvement |

## 11. Decisions Master must make

1. Channel name and narrator voice sample (the comic voice and the calm art voice are both wrong here).
2. Default script path: automatic writer, or the Gemini paste workflow.
3. Whether Bible stories on Doré and Tissot engravings become series 2 (same engine; sensitive topic).
4. Merge of comic PRs #20, #21 and the render-motion PR, so the engine pin can include them.

## 12. Kickoff prompt for the implementing agent

> Read `PLAN.md` fully, then `docs/research/outliers.md`, `public_domain.md` and `pipeline_capability.md`. Execute phase 0, then phases 1 to 5 in order, one branch and one PR per phase. Follow sections 2.1, 5, 6 and 9 as hard rules. After each phase, report what you built, what you measured and what is unverified. Stop and ask Master when a decision in section 11 blocks you, before any paid API call, and before touching the Windows server. Never approve a review on Master's behalf.
