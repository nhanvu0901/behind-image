# Pipeline capability audit for new niches (code audit, 2026-11-12)

Scope: read-only audit of `/Users/nhanvu/Documents/code/comic-book-pipeline` (local `main`, a few commits behind GitHub). Nothing was run. Paths are relative to the repo.

## 1. Capability map

| Module | In → Out | Class | Notes (file / function) |
|---|---|---|---|
| `stages/stage_1/` agent, `answer_research.py`, `comicvine.py`, `batcave_verifier.py`, `tools/fetch_fandom.py` | idea → `comic_context.json` / answer context | COMIC | Fandom, ComicVine, batcave. `tools/web_search.py` and `fetch_wiki.py` (Wikipedia) are generic. |
| `stages/stage_1/screen_research.py` `research_screen` | question → `screen_context.json` items {entity, event, adaptation_title, year, summary, visual_query, source_urls} | GENERIC except the prompt | You.com evidence only; invented URLs are removed; the prompt asks for film or TV items. Best template for any fact niche. |
| `stages/research_scout/` | scout, evidence gate, done-ledger | PARTLY | `youcom.py`, `openrouter_gate.py`, `ledger.py` (SQLite, append-only) are generic. Comic-tied parts: `ledger._ISSUE_RE`, `MODES={micro,qa,recap}`, `issue_identity.py`, `issue_pages.py`, `router_rules.py`, `research_policies/source_profiles.v2.json` (lists of Fandom/CBR sites), `research_prompts/*.md`. |
| `stages/stage_2/` | batcave URL → pages → Magi panels + OCR + VLM descriptions | COMIC | `url_mode.py`/`download.py` only accept batcave; `utils/comic_scraper/readcomiconline.py`. `panel_detect.sort_western_reading_order` (L331, called L230) is left-to-right only. `vlm_extract.py` prompts are written for comics. |
| `stages/stage_3/` `write_script.py`, `micro_moment.py`, `explore_answer.py`, `gemini_prompt.py`, `prompts/*.md` | context → `narration.json` | COMIC | Every prompt says "comic" or "issue"; scenes carry `page_ref`/`panel_ref`. |
| `stages/stage_3/screen_qa.py` `write_screen_qa` | screen_context → narration (mode `screen_qa`) | PARTLY | `_validate_screen_scenes` requires an "In the YEAR film Title" citation (`_cites`). |
| `stages/stage_3/provided_narration.py`, `beat_split.split_visual_beats`, `spoken_rules.py` | finished prose → scenes + verbatim visual beats | GENERIC (English) | Minimal-LLM path that splits a script you supply. |
| `stages/stage_4/` | narration → `audio.wav`, `word_timestamps.json`, `scene_timings.json` | GENERIC (English) | Chatterbox runs locally; Cartesia and Resemble are optional hosted voices. Timings are spread evenly within each sentence (`chatterbox_tts._even_words`). |
| `stages/review_gate.py` + `ui/screens/s_review_gate.py` | panel candidates → `review/locks.json` (approved + narration sha) | PARTLY | Candidate building (panel thumbs, money-shot OCR) is comic. Lock storage, `custom_image` locks and the approval gate are generic. |
| `ui/custom_image.py` `add_custom_image` | any image → `review/custom/` + sidecar | GENERIC | This is the place to feed in any image per beat. |
| `stages/stage_5/shots.py` comic `build_shots` | pages + narration → Shots | COMIC | Matcher, cold-open panel, bubble inpaint, Magi character boxes. |
| `stages/stage_5/shots.py` `render_shot`, `_prepare_panel_frame`, `_zoompan_expr` | one image → Ken Burns MP4 | GENERIC | Already reused by `art_pipeline` and `screen_shots`. |
| `stages/stage_5/clips.py` + `stages/clip_fetch.py` | YouTube URL/in-out → 9:16 clip shot | GENERIC | You.com search + yt-dlp; picking is manual per beat (`/moments_review`, `ui/web_routes.py`). |
| `stages/stage_5/screen_beats.py`, `screen_shots.py` `run_screen_qa_pipeline` | narration + clips/stills per beat → `final.mp4` | GENERIC | Fallback chain per beat: clip → backup clip → still → text card. It reads no comic page. |
| `stages/stage_5/pipeline.py` assembly, `audio.mix_audio`, outro card; `stages/music_sync.py`; `stages/mascot/` | shots → final.mp4, two-pass loudnorm, beat-synced music, sticker narrator | GENERIC | |
| `stages/panel_walk/` | comic pages → long-form 16:9 narration | COMIC | Exempt from the review gate. |
| `art_pipeline/` + `art_ui/` | Met object IDs → museum video (Short or long-form) | PARTLY | `sources/met.py` behind the `ArtSource` protocol; `regions.py` (VLM proposes zoom regions in an image); `hunt.py` (Claude SDK finds related web images); `longform_tts.py` (per chapter); chapter cards + SRT in `assemble.py`. Prompts are art-specific. |

## 2. Minimal generic core

**The `screen_qa` path is already the generic core.** `stages/stage_5/pipeline.assemble_project` hands off to `screen_shots.run_screen_qa_pipeline` when `narration.mode == "screen_qa"`. That runner needs only:
1. a `narration.json` in the Scene schema, with `visual_beats` = [{text, query}];
2. visuals per beat key (`intro`, `<sid>`, `<sid>:<frag>`): `review/clips/clips.json` and/or `review/custom/custom_images.json` + `review/locks.json` `{"custom_image": ...}`;
3. `locks.json` `approved=true` with the narration sha (`review_gate.ensure_reviewed`);
4. Stage 4 audio.

The run is: Stage 4 → Stage 5 → `final.mp4`, with music sync, outro card and logo. `art_pipeline/assemble.plan_shots` is a second working path, but it is older: no clips, no music sync, burned-in captions.

**Missing glue (about 1 day, S):**
- (a) A `generic_beats` CLI that takes a script plus an ordered list of images or clips and writes narration.json. It would reuse `provided_narration.split_sentences` and `beat_split.split_visual_beats`, set the mode to `screen_qa` or a new mode name, then call `add_custom_image` or `clips.upsert_beat_clip` per beat and approve the locks.
- (b) Make the `_cites` film check depend on the mode.
- (c) `screen_card` fallback cards read `adaptation_title`/`year`, so they need neutral defaults.

## 3. Adapters per source type

| Type | Effort | What is needed | Main risk |
|---|---|---|---|
| a. Manga (right-to-left, black and white) | **M** | Magi v3 was built for manga, so panels and OCR fit. Add a right-to-left switch to `sort_western_reading_order` and the `gutter_split` sort (L111). Add a manga source scraper (only batcave and readcomiconline exist). Reword the VLM and writer prompts; use a manga wiki for facts. Black and white is fine: subject framing reads ink by brightness (`SUBJECT_INK_MAX_LUMA`), and mirroring is already off. | Legality of the page source (scanlations). Raw Japanese vertical text is not OCR'd, so bubble erasing misses it. |
| b. Vertical webtoon / manhwa | **M–L** | A slicer that cuts a very tall strip into page-sized pieces at white gaps (extend `gutter_split`). A true scroll motion: today `_prepare_panel_frame` cover-crops a tall strip to a single 9:16 window and `pan_down` only travels 15% (`PAN_ZOOM` 1.15) inside that window. | Large white gaps between panels; Magi trained on page grids; same source-rights issue. |
| c. Loose images (fan art, public domain, museum APIs, NASA) | **S** (local folder) / **M** (search APIs) | The glue from section 2 plus a source adapter per API following `art_pipeline/sources` (`ArtSource` protocol); `regions.py` for zoom-ins into high-resolution images; `hunt.py` for web image search. | Rights for fan art; landscape images get the blurred letterbox (section 5). |
| d. AI illustration per beat | **S–M** | No image generation exists anywhere in the code. Plug point: after narration, for each `visual_beat.query` → generator → PNG → `ui/custom_image.add_custom_image(root, png, beat_key)` + lock. A paid API is required (no strong GPU on either machine). | Cost; YouTube's "inauthentic content" policy; keeping a character consistent across images. |
| e. Movie / TV / anime clips | **S** to use, **M** to fix framing | Already end to end: `stages/screen_pipeline.py` research → narrate → tts → render, with picking via `clip_fetch` and `/moments_review`. Limits: `clips.clip_filter_graph` letterboxes every 16:9 clip (blurred background) unless a manual `crop {"cx"}` is set. A 1080p clip fills only 1080×608 of the frame. `CLIP_MAX_UPSCALE`=2.0 blocks fill-crop on 720p sources. There is no automatic subject tracking. Clip audio is always dropped; clip speed is limited to 0.8–1.25×. One manual pick per beat. yt-dlp gets 403 errors on the prod box. | Content ID claims and the reused-content policy (the highest of all types). |
| f. Another narration language | **M** per language | The Chatterbox worker loads the English `ChatterboxTTS` (`_chatterbox_worker.py` L62/L80). Cartesia takes a `language` setting (`cartesia_tts.py` L54, default "en") but is paid. `utils/spoken_text.to_spoken` (English number words) runs on every line in `stage_4/pipeline._normalize_for_tts`. `SPOKEN_TEXT_RULES` and every prompt are English. The sentence-split regexes need a capital letter or digit after a full stop (`chatterbox_tts._SENT_END`, `chunker._split_sentences`). Word timings split on spaces, which breaks Chinese, Japanese and Thai. The "action word" list (`_ACTION_WORDS`) is English. Captions are made in CapCut, so caption chunking hardly matters. | Voice quality in the new language and a new voice sample. There is no forced aligner, so timings drift inside each sentence. |
| g. Long-form (10+ min) from many short stories | **M** | Nothing joins finished projects. 16:9 output only exists for `LONGFORM_MODES=("panel_walk",)` (`shots.py` L30) and for the art long-form override (`art_pipeline/video.py` L96-107). Plan: add a long-form switch and re-render each story at 16:9 (`render_shot` and `clip_filter_graph` read `OUTPUT_W/H` at run time), then stitch with art's `_concat_xfade`, chapter cards and `build_srt`. | Visuals picked for 9:16 (tall panels) letterbox badly at 16:9; retention over 10+ minutes. |

## 4. Research and script stages

Fact research and writing are the most comic-bound parts: Stage 1 comic agents, `write_script.py` (4.8k lines), every Gemini prompt, the source domain lists and the issue-number ledger keys. Three pieces generalize:
- `screen_research.py` (web evidence → items, with URL verification);
- `openrouter_gate` (evidence check);
- `ledger.py` (key/label/entities events).

A new niche needs:
1. a **prompt pack**: a research prompt like `research_prompts/*.v2.md`, a writer prompt like `prompts/gemini_*`, and a viral-angle file like `prompts/viral_topic_angle_skill.txt`;
2. a **verified-fact source**: a domain list in `source_profiles` plus a context schema like `screen_context` — rename `adaptation_title`/`year` to source/date;
3. a **done-ledger key**: a new mode in `ledger.MODES` plus a key normaliser to replace `_ISSUE_RE`, and a ban list.

Estimate: M per niche, mostly prompt writing and testing.

## 5. Render weaknesses that follow every niche

| Weakness | Where in code | How hard to change |
|---|---|---|
| Slow, small pan/zoom | `shots.py` L223 `ZOOM_AMPLITUDE=0.06` (calm push +6%, smoothstep), L224 action 0.13, L232 `PAN_ZOOM=1.15`; `_zoompan_expr` L3149. Its docstring still says 1.10 (out of date). Long holds: `MAX_SHOT_SECONDS=9999` L237 and `SHOT_MAX_SECONDS=0` L266 turn sub-shot splitting off. | **S**: environment settings; one renderer shared by every path. |
| Blurred letterbox on stills | `_should_blur_bg` L3473: blur when the cover scale is above 2.5 (`_BLUR_FALLBACK_SCALE` L3236) or aspect ≥ 1.7 (`LANDSCAPE_COVER_MAX_ASPECT` L254); `PANEL_FIT_MODE="contain"` L278; GaussianBlur radius 40 and foreground capped at 2× in `_prepare_panel_frame` L3543. A 16:9 image (aspect 1.78) always letterboxes. | **S** to set `PANEL_FIT_MODE=fill` or raise the 1.7 limit; **M** for subject-aware filling of non-comic images (Magi character boxes are absent; the brightness-based fallback is tuned for ink). |
| Blurred letterbox on clips | `clips.clip_filter_graph` L698, `CLIP_MAX_UPSCALE` (top of clips.py), `crop_region` L677; the `cx` crop is only set by hand (`clip_fetch.py` L1095). | **S** to default to a centre `cx` crop; **M** for automatic face/saliency reframing. |
| Speech-bubble erasing | `INPAINT_BUBBLE_TEXT=True` `shots.py` L109; `_crop_panel` L3787 → LaMa `_lama_clean` L3649 / cv2 fallback L3882; `_bubble_clean_audit` L574. Comic and manga only; custom images skip it (`_load_custom_panel` L3700). | Not relevant outside comics and manga; for manga it works on English scanlations only. |
| About 0.2 s silence at the start | No trimming exists. Chatterbox chunks are joined raw, each with its own model silence (`chatterbox_tts.py` ~L291-305; `background_tts._concat_wavs` L654). Words are spread across each chunk *including* that silence (`_even_words` L134). `stage_5/audio.mix_audio` has no `silenceremove`. | **S**: trim the start and end of each chunk before offsets are computed (this also tightens timings). |
| Dissolve between scenes | `config.py` L373 `XFADE_TRANSITION="dissolve"` (default), `XFADE_ROTATE` L383. | **S** (environment setting). |
