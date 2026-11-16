# R5. How the comic pipeline gets from "topic chosen" to "approved narration with pictures"

Research only. Source repo (read-only): `/Users/nhanvu/Documents/code/comic-book-pipeline`. All paths below are relative to it unless stated. Line numbers are from the files as read on 2026-11-16. I did not run anything and did not open any `.env`.

## 0. Summary of the findings that change the plan

1. **There is no "dàn ý" step in the comic pipeline.** What the owner calls the outline is the **Gemini writer prompt**: a markdown file built by filling a template with the research data of the project. It contains no model output. It is produced by plain string replacement, costs nothing and takes no time. The closest thing to a real outline is in the sister pipeline `art_pipeline/outline.py` (an LLM call that splits facts into 4 or 5 chapters), which is not part of the comic flow.
2. **The paste-back is a very tolerant text parser, not a schema.** The owner pastes Gemini's whole answer (including hook options, audit tables, word counts). The importer extracts the text under a `FINAL SCRIPT` line, strips labels and audit tails, and maps paragraph N to answer item N. The only hard refusals are shape errors ("script does not fit the N items").
3. **All real confirmation happens in the Review Beats screen**, which sits after the narration is approved and before any audio is made. It is where text is edited, beats are split, merged, dropped or inserted, pictures are chosen, and the final Approve is stamped with a hash of `narration.json`.
4. **Pasted scripts get almost no content validation in code.** Word budgets, hook rules, banned phrases and the "spoken text" rules live in the prompt. Code only enforces structure (paragraph count, verbatim fragments) and converts digits and symbols to words at TTS time.
5. **The LLM paths in the comic repo exist but the Gemini paste screen uses none of them** ("0% Claude" is printed in the UI). Section B documents them for the new "write the narration" button.

---

## A. The narration workflow

### A1. The pipeline order and what the narration stage receives

UI stages (`ui/state.py:22-32`): 1 Research Scout, 2 Narration Script, 3 Download Comic, 4 Preprocess Pages, 5 Review Beats, 6 TTS Audio, 7 Review & Edit (skipped for Q&A projects, `s6_review.py:380`), 8 Final Video, 9 Mascot.

The narration stage (2) receives, from the research stage, files in `projects/<slug>/`:

- `answer_context.json`: `{"question": "...", "format": "list"|"direct", "answer_summary": "...", "items": [ {entity, how_or_why, source_comic, source_year, reader_url, drawable_moment, verification_note, surprise_level, stakes_why, relationships, ...} ]}`. Created by `stages/stage_1/answer_research.py::build_contexts` (item fields at lines 39-40). Items come from a You.com research call plus an OpenRouter "evidence gate" (`stages/research_scout/openrouter_gate.py`) and have a reader URL resolved by search.
- `comic_context.json` (title, series, `pipeline_mode`, `plot_source`, characters, `target_moment`), and for micro-moment projects `scout_candidate.json` (character, `what_visibly_happens`, `claim_citation`, `verbatim_sentence`, `evidence_urls`, `verdict`).
- The research session folder (`research_sessions/<id>/general/candidates*.json`, `specific/evidence_gate.v1.json`) which `_enrich_qa_context` (`stages/stage_3/gemini_prompt.py:174-475`) reads to add `story_arc`, `motivation_detail`, `claim_citation`, `evidence_urls`, `scout_verification`, `retrieved_source_excerpts` to the prompt copy only, and to backfill empty standard fields on disk.

The narration screen can be used **before** the comic is downloaded: with `allow_pending=True` the importer anchors every item to page 1 until the download exists (`_qa_item_anchors`, line 912); `reanchor_narration_to_pages` (line 1194) fixes the page references later, when Review Beats is opened (`build_candidates` calls it).

### A2. Question 1. The "outline" handed to Gemini

**What it is.** A markdown file `projects/<slug>/<slug>_writer_prompt.md` (`gemini_prompt.py:476-608`, written at line 603). Four templates, chosen by project mode: `prompts/gemini_qa_writer_template.md` (375 lines, the main Q&A format), `prompts/gemini_micro_moment_writer.md` (608 lines), `prompts/gemini_comic_vs_show_writer.md` (105), `prompts/gemini_topic_qa_writer.md` (353; constant defined, used for topic Q&A).

**Who generates it.** `generate_gemini_writer_prompt()` does `template.replace("{{QUESTION}}", ...)`, `{{SCOUT_JSON}}` (the numbered items as indented JSON, each with `"item_number": n` added to the prompt copy only), `{{STORY_CONTEXT}}`, then `fill_spoken_rules()` (inserts the shared `SPOKEN_TEXT_RULES` constant, `stages/stage_3/spoken_rules.py`) and `fill_opening_rules()` (`opening_rules.py`). No language model, no provider, no cost. If the "Fast Short < 35s" checkbox is on, a hard-override block (80 to 105 words) is inserted before the OUTPUT section (`FAST_SHORT_35S_OVERRIDE_BLOCK`, line 51).

**Where it appears in the UI.** `ui/screens/s3_narrate.py`, centre column top bar: button "Copy Gemini Prompt" (`copy_prompt_click`, line 213: generates, writes the file, copies to the clipboard, opens a dialog) and "Download Prompt to Mac (.md)" (`export_prompt_click`, line 242: triggers a browser download of `/<slug>/<slug>_writer_prompt.md` and also copies). The dialog (`_open_prompt_dialog`, line 172) shows the full prompt in a read-only selectable text box (needed because on the LAN address the clipboard is blocked; `BLOCKED_HINT` says so), with "Download to Mac (.md)", "Copy to Clipboard" and "Close". The right column lists the four steps ("Gemini-First Narration (0% Claude)").

**The text itself (template, Q&A format; long rule sections elided, headings real).** From `prompts/gemini_qa_writer_template.md`:

```
GEMINI PROMPT — Q&A NARRATION WRITER (Gen-Z voice), GROUNDED

Run settings: Gemini 3.8 / Gemini 3.1 Pro. Temperature 1.0 (default — do not lower it).
Google Search grounding ON. Thinking level HIGH. Runs in two turns: let it
finish PHASE 1, then reply WRITE.

Operator note: after reviewing the audit, paste only the spoken lines under
FINAL SCRIPT into the Stage 3 UI. ...

You write the narration for a YouTube Short that answers one comic-book question.
I paste the finished text straight into my video pipeline. This job runs in two phases.
Do not start PHASE 2 until I type WRITE.

THE QUESTION:
{{QUESTION}}
{{STORY_CONTEXT}}
THE SCOUT JSON — one object per answer item:
```json
{{SCOUT_JSON}}
```
Read each object like this:
item_number -> the item's fixed position. Your script keeps this order.
entity / source_comic / source_year / how_or_why / drawable_moment / relationships ...
reader_url -> pipeline data, never narrated

Every item goes in the video, in item_number order. Never skip, merge or reorder one ...

PHASE 1 — GROUND EACH ITEM   (source tiers table 1/2/3; 2-3 sourced beats per item,
                              each with a Tier 1/2 URL and a verbatim quote;
                              stop conditions: write NO INFO and name the item)
PHASE 2 — WRITE THE SHORT (only after I type WRITE)
   SOURCE AND ORDER / THE STORY ENGINE (ANSWER, CONTEXT, DEVELOPMENT, RESULT cards) /
   HOOK (3 options, 7-18 words, 20 hard max) / SCRIPT / READING LEVEL (IELTS 6.5) /
   HOUSEHOLD NAMES ONLY / VOICE / SENTENCE LENGTH (15-26 target, 32 max) /
   ## OPENING RULES {{OPENING_RULES}}   ## SPOKEN TEXT RULES {{SPOKEN_TEXT_RULES}}
   HUMOR / LENGTH AND SOURCE CHECK (110-160 words at 2.9 words per second) /
   ANTI-FLATNESS CHECK / BEFORE OUTPUT checks 16-25

OUTPUT EXACTLY IN ENGLISH, WITH NO PREFACE
HOOK OPTIONS
1. <concrete sourced hook>   2. ...   3. ...
CHOSEN HOOK: <number>
SPOKEN WORD COUNT: <actual count of FINAL SCRIPT only>
FACT TRACE
S1 | <first few words> | Item <n>, Beat <n>
...
UNSUPPORTED FACTS: none
OPENING CHAIN: ...   ISSUE MENTION CHECK: ...   FLOW CHECK: ...

FINAL SCRIPT
<chosen hook>

<item 1 paragraph>

<item 2 paragraph>
<one paragraph per remaining item in input order>
```

**A real filled example** (from `tests/test_gemini_micro_moment_prompt.py:20-60`, micro template; the SCOUT JSON block is the research data):

```
MOMENT:        Batman / Bruce Wayne — Batman is trapped in a collapsing vault and Annika reveals her true identity. — Batman #5 (2026)
SCOUT JSON — the single confirm object from stages/youcom_scout:
{ "character": "Batman / Bruce Wayne", "series_issue_year": "Batman #5 (2026)",
  "what_visibly_happens": "Batman is trapped in a collapsing vault and Annika reveals her true identity.",
  "claim_citation": {"title": "CBR Review", "url": "https://www.cbr.com/batman-5-review/", "quote": "The twist ending redefines Annika's motives completely."},
  "verbatim_sentence": "...", "source_url": "...", "evidence_urls": ["..."], "verdict": "CONFIRMED" }
```

**Two-turn contract.** Turn 1 (paste prompt): Gemini researches with Search grounding and returns a Phase 1 fact sheet (audit). The owner reads it, then types `WRITE`. Turn 2: Gemini returns the output blocks above. The owner copies the answer (the importer tolerates everything above `FINAL SCRIPT`, but the template's operator note advises pasting only the spoken lines, because the on-screen word counter counts any pasted audit text).

**Cost.** Prompt generation: zero. Gemini runs in the owner's own account, by hand. The research data inside it did cost money upstream (You.com plus the OpenRouter gate).

### A3. Question 2. The paste back

**Where.** Same screen, a multi-line text box `script_area` (`s3_narrate.py:96-112`, 16 to 30 lines, hint text shows a three-paragraph example), then "Approve & Continue →" in the right column. "Clear" empties the box. It is pre-filled from `saved_script_for_editor()` (`gemini_prompt.py:964`) = the saved narration rebuilt as one paragraph per beat (hook, one paragraph per item, closing line), else `master_narration.md`, else the last script that failed (`load_last_script`, status note "Restored the script you last tried to approve.").

**Accepted format.**

- Plain text. Paragraphs separated by blank lines (single newlines also work if every line ends a sentence).
- Optional hook line, then exactly one paragraph per answer item in item order, then optional closing line.
- It may contain Gemini's whole reply. `_read_script` (line 693) handles: text after the last `FINAL SCRIPT` line (regex `^[\W_]*FINAL\s+SCRIPT[\W_]*$`); `HOOK OPTIONS` blocks and `CHOSEN HOOK: n` (resolves "Hook 2" to its text); labelled `Hook:` / `Outro:` / `Closing:` / `Loop closer:` lines; markdown headings, horizontal rules, code fences (all become paragraph breaks); `*`, `__` emphasis stripped; list markers and `Item 3:` / `Story:` prefixes stripped; label-like short lines without end punctuation dropped; an audit tail ends the script (`Word Count`, `Fact Trace`, `Audit`, `Sources`, `Notes`, and the template's own labels `OPENING CHAIN`, `FLOW CHECK`, `UNSUPPORTED FACTS`, ...).

**Parsing into scenes** (`parse_and_save_script`, line 1056). For items projects: `_split_qa_script` finds the hook and closing line (a first or last paragraph of 20 words or fewer, `_SHORT_WORDS=20`; item paragraphs must have 8 or more words, `_MIN_ITEM_WORDS`), drops a hook the story repeats (similarity ratio 0.85, `_restates`), and requires exactly `n_items` body paragraphs. Each body paragraph is split into sentences (`split_sentences` from `provided_narration.py`); **each sentence is one scene**, with `beat_id = item number`, `page_ref` = first page of that item's downloaded chapter. The hook is one scene `is_intro` (beat 0), the closing line one scene `is_outro` (beat n+1). For projects without items (recap, micro), paragraphs are spread proportionally across the story pages and every scene gets its own beat. No language model is involved: even the visual fragments come from `split_hook_fragments` (pure regex and word lists, `beat_split.py:100`) applied to every scene, and fall back to `[text]` if not verbatim. (The LLM splitter `split_visual_beats` in the same file is not called on this path.)

**Validation and exact messages** (all `ScriptMappingError`, a `UserFacingError`, so the UI shows the message alone):

- `"Narration text is empty."`
- `"Could not extract any narrative scenes from the input."` (no-items path)
- `"Found {n} hook options but no chosen one. Keep only the hook you want (or paste just the part under FINAL SCRIPT)."`
- The main one (line 880):
  ```
  The script does not fit the {n} answer item(s). Expected an optional hook line, then exactly ONE paragraph per item in item order, then an optional closing line — separated by blank lines.
  Hook found: "<hook>"
  Found {k} paragraph(s):
    [1] 14 words: "Nobody out-heals Deadpool. It costs him."
    [2] 47 words: "Deadpool heals from literally anything you throw at him. But there i…"
  Merge an item that was split, restore one that was dropped, or regenerate the script with the current prompt.
  ```
  The listing is the key design: it shows the owner exactly what the parser saw.
- Item/download mismatches (line 944): `"Cannot place the script on the downloaded comics:\n  - item #2 Black Panther: its comic (url) was not downloaded — run Download Comic (Stage 3)"`, or `"... chapter 2 on disk is X, but the item now cites Y — re-download (Stage 3) and preprocess (Stage 4)"`, or `"... no preprocessed pages for chapter N — run preprocessing (Stage 4)"`.
- UI wrappers (`s3_narrate.py`): `"Please paste or write narration script before continuing."`, `"No project selected."`, and for any non-user error `"Stage 2 was not approved; retry Approve & Continue. {exc}"`.
- **Gap found:** `_read_script` detects a `NO INFO` reply from Gemini (line 704-706) but the variable `note` is never used, so there is no dedicated message. The test `test_no_info_from_the_writer_is_reported` only passes because the mapping error's paragraph listing happens to contain the words "NO INFO". The new pipeline should raise a real message (the template tells Gemini to answer `NO INFO` and name the failing item).

**On failure.** Nothing is written (`parse_and_save_script` raises before any file write). Before parsing, the screen saves the pasted text with `save_last_script` and appends it to the project's stage log (`s3_narrate.py:295-299`), so a refused script is never lost; the first line of the message goes in the red status line, the full log below it. The owner edits the text box in place and presses Approve again. There is no inline editing of paragraphs elsewhere in this screen; the box is the editor.

**On success.** Writes `narration.json`, `narration.tts.sha256` (hash of scene texts) and `master_narration.md` (the raw paste, audit record only; later edits do not update it). Then: `state.approved.pop("2")`, records a milestone in the production ledger (`record_milestone`), computes `sha256(narration.json bytes)`, `state.mark_approved(2, narration_sha256=...)`, jumps to the next stage. Status text: "Narration approved: N words, M scenes."

**Live counter** (`_update_counter`, line 126): "`{wc} words · ~{wc/2.9:.1f}s estimated · {paragraphs} paragraph(s) (need {n_items}, plus an optional hook and closing line)`", warning past 58 s (or past 35 s in the short mode). It counts blank-line paragraphs, the same unit the parser maps.

### A4. Question 3. `narration.json`

Written by the importer (`gemini_prompt.py:1130-1170`; dataclass reference `stages/stage_3/schema.py`, which the LLM writers use and which adds `mode`, `banner_title`). Real shape for a Q&A project with 3 items:

```json
{
  "title": "<question or comic title>",
  "hook": "Nobody out-heals Deadpool. It costs him.",
  "scenes": [
    {"scene_id": 1, "text": "Nobody out-heals Deadpool. It costs him.",
     "page_ref": 1, "panel_ref": -1, "word_count": 7, "target_seconds": 2.41,
     "connective": null, "beat_id": 0, "is_intro": true, "is_outro": false,
     "visual_beats": ["Nobody out-heals Deadpool.", "It costs him."]},
    {"scene_id": 2, "text": "Deadpool heals from literally anything you throw at him.",
     "page_ref": 1, "panel_ref": -1, "word_count": 9, "target_seconds": 3.1,
     "connective": null, "beat_id": 1, "is_intro": false, "is_outro": false,
     "visual_beats": ["Deadpool heals from literally anything you throw at him."]}
  ],
  "total_word_count": 170,
  "estimated_duration_seconds": 58.62,
  "words_per_second": 2.9,
  "source_project": "<slug>",
  "llm_model": "manual (Gemini Master-written)",
  "beats": [
    {"id": 1, "function": "COLD_OPEN", "name": "Deadpool", "page_refs": [1], "key_panels": [],
     "summary": "<how_or_why>", "characters_active": ["Deadpool"], "cause": "<how_or_why>"}
  ],
  "glossary": {"characters": {}},
  "answer_items_signature": "<sha1[:16] of entity+source_comic+reader_url list>"
}
```

Notes: beat `function` is `COLD_OPEN` for item 1, `LANDING` for the last item, `SETUP` otherwise (recap or micro projects use `BODY`). `word_count` is `len(text.split())`; `target_seconds = round(word_count/2.9, 2)`. `visual_beats` are verbatim fragments (an element is a string; in micro mode written by an LLM it may be `{"text","page","panel"}`). `scene_id` is stable and never renumbered. `answer_items_signature` lets the editor refuse to pre-fill a script written for a different item list (`saved_script_for_editor`). The optional spoken subscribe line (`ending.py`, `SPOKEN_SUBSCRIBE_CTA`, default off) is appended or stripped and counts resynced.

The UI-added fields later: Review Beats edits `scenes[].visual_beats`, `text`, `word_count`, `target_seconds`, and the totals, in place.

### A5. Question 4. The confirmation points, in order

| # | Screen (stage) | Owner sees | Owner can change | Locked afterwards | What makes the approval stale |
|---|---|---|---|---|---|
| 1 | Research Scout (1) | Candidate questions or moments with evidence verdict, audit, audience data | Select candidates, rescout, edit evidence, reject | The selection becomes `answer_context.json` / `scout_candidate.json` | `return_to_research` marks every later approval dirty (`ui/state.py:83`) |
| 2 | Narration Script (2) | The writer prompt; the paste box; word counter | Everything in the box, then Approve | `narration.json` is written; `state.approved["2"]` plus `approved_narration_sha256` | Any new save pops the stage-2 approval first (`s3_narrate.py:317`). The stored hash is recorded but I found no reader of it other than the state itself |
| 3 | Download and Preprocess (3, 4) | Logs only; no creative choice | Rerun | Pages and panel JSON | Item/chapter mismatch makes the importer refuse (messages above) |
| 4 | **Review Beats (5)** | One card per narration fragment: editable text, source citation chips, "Looking for:" hint, candidate gallery, selected area, badges | Text of any fragment; split; merge; drop line; insert scene; delete beat; pick 2 to 5 panels (or 1 on fragment, intro, outro rows); custom image; MP4 clip; hide a panel project-wide; import intro image; music choice | `review/locks.json` with `approved: true`, `approved_at`, `narration_sha1` (sha1 of narration.json bytes) | **Any** structural or text op sets `approved=false` immediately in the UI (every handler writes `locks_doc["approved"]=False`). At the render, `ensure_reviewed` (`stages/review_gate.py:320`) raises `SystemExit` if not approved, or if `narration_sha1` no longer matches: "narration.json changed since '{project}' was approved (approval is stale). Re-review and re-approve in Stage 5 (Review Beats)." Hard gate for all modes (`REVIEW_GATE` env can turn it off; `--skip-review` is ignored) |
| 5 | TTS Audio (6) | Audio player (play, seek) | Voice, regenerate | `state.mark_approved(6)` | `narration.tts.sha256` (hash of scene texts) differs, so audio is regenerated automatically rather than shipped stale (`stage_4/pipeline.py:256-277`) |
| 6 | Review & Edit (7) | Storyboard of scenes with panel and editable text | Text, panel via picker, re-render | Skipped for Q&A projects | n/a |
| 7 | Final Video (8) | Render and preview | Rerender | `final.mp4` | n/a |

Approvals cascade: `AppState.mark_dirty(stage)` flags every later approved stage dirty.

Approve in Review Beats first saves any pending typed edits (`_toggle_approve` calls `_save_narration_text`, `s_review_gate.py:2520`), so a typed but unsaved change cannot be approved by accident. There is also an explicit "Save narration edits" button; there is **no autosave**: edits live in sparse in-memory dicts (`edited_text`, `frag_edits`) until Save or Approve.

### A6. Question 5. "Choosing what is on the scene"

**Candidates are not ranked.** `build_candidates` (`stages/review_gate.py:750`) lists **every panel** of the eligible pool for each row, sorted by `(page, panel)`, with `score: 0.0` ("manual-first": the owner picks by eye; docstring line 32-34). The shape per row in `review/candidates.json`:

```json
{"scene_id": 5, "beat_key": "5:1", "unit": "fragment", "narration_text": "...",
 "page_ref": 12, "panel_ref": null,
 "source": {"title": "...", "issue": "...", "url": "...", "research_urls": ["..."],
            "drawable_moment": "...", "verified": true, "verify_note": "..."},
 "pre_selected": [{"page": 12, "panel": 3}],
 "candidates": [{"page": 1, "panel": 0, "score": 0.0, "thumb": "review/thumbs/p001_0.jpg",
                 "desc": "", "dialog": "OCR text", "panel_source": {"title": "..."}}]}
```

Rows ("beats" in the review sense, keyed in `locks.json`): `intro`, `outro`, `<scene_id>` (a scene with no fragments), or `<scene_id>:<frag_idx>` (`bookend_row_keys`, `review_beat_rows`). A hook or closing with 2 or more fragments becomes ordinary `<sid>:<i>` rows with a `bookend` marker so the card is labelled "INTRO (cold-open) · mảnh n".

**Pools.** List-format Q&A scopes each item's rows to its own issue; direct Q&A, recap and micro get the whole project pool; intro and outro always get the whole pool. `pre_selected` = the scene's own anchor (or `narration.cold_open_lock`, or a writer-picked pin) and seeds a lock (`source: "pre_selected"`) if none exists.

**How many may he choose.** `MIN_PANELS = 2`, `MAX_PANELS = 5` (`s_review_gate.py:~104`). A `unit == "scene"` row is multi-select up to 5 ("Max 5 panels per beat." snack; warning chip "pick at least 2" if fewer and no custom image or clip). Fragment, intro and outro rows are single-select: click replaces, click again clears. The chip shows "n/cap selected".

**Zero candidates.** The card shows "No candidates — dùng Custom image hoặc Rebuild." with a "Rebuild candidates" button that reruns `build_candidates(project, 0)` in a worker thread (slow, "may take a few minutes"), then reloads. Inserted scenes avoid this by cloning the neighbour's pool (see A7). A beat left with no pick is not an error: badge "auto" and the render falls back to its anchor panel ("Beats left on auto fall back to their grounded anchor panel").

**Lock shapes in `review/locks.json`:** `{"locks": {"<beat_key>": {"panels": [{"page","panel","src"}], "source": "batcave"} }}` (v2; v1 single `{"page","panel"}` still read); custom image `{"custom_image": "review/custom/<file>", "source": "custom"}` (exclusive with panels). `src` stamps the source image basename so a page renumber can be repaired (`remap_locks_by_src`). `splice_locked_orphans` re-adds a tile for any locked panel missing from the candidate list so a pick never silently disappears.

**Custom images** (`ui/custom_image.py`): the "add image" icon opens a file picker (jpg, jpeg, png; in the web mode the bytes come from the browser); the file is stored under `review/custom/`, listed first in that beat's gallery with a CUSTOM chip, and described by a VLM in the background (fire and forget, never blocks the UI). **Intro image import** (`ui/intro_import.py`) injects an external image as the cold-open picture.

**Video clips** (only when `ENABLE_VIDEO_CLIPS=1`, default 0, and only when the UI runs with `--lan`): a video icon on each card opens `/moments_review?project=&beat=` (web route, `ui/web_routes.py`) where the owner picks a YouTube moment; a job downloads and cuts it to the beat's measured duration (`POST /api/pick_moment`, `GET /api/pick_status`, `GET /api/clip_preview`). A clip entry lives in `review/clips/clips.json` and replaces the panel selection on that card (MP4 badge, inline video preview, rollback icon with confirm).

**Project-wide hide** ("Ẩn panel này khỏi MỌI beat", `review/hidden_panels.json`): pure UI filter over `candidates_all`, winning over a lock; "Hiện lại tất cả" undoes it.

### A7. Question 6. Insert scene, split, merge, drop fragment, delete beat

All live in `ui/screens/s_review_gate.py` as pure helpers plus handlers. The common rule: **the op rewrites `narration.json` immediately, remaps `locks.json` keys, clips and custom images, un-approves, asks the background TTS to re-plan, and rebuilds only the affected cards** (`_rebuild(..., dirty=keys)`). Existing `scene_id`s are never renumbered.

- **Split** (`split_fragment_at`, line 371; dialog `_open_split_dialog`, line 2078). The icon on the "+" row between cards opens a dialog showing the fragment as words with a scissor between every pair; suggested cut points (after a comma or dash, or before and/but/then/so/yet/however/meanwhile) are drawn in the accent colour. Both halves inherit the fragment shape (a micro dict keeps its page and panel pin). Locks at higher indices shift +1 (`remap_fragment_locks`); the new second half gets a clone of the sibling's candidate pool and no lock. Narration text is unchanged, so only fragments change.
- **Merge** (`merge_fragment_into_prev`, 396; handler `_delete_fragment`, 1955; icon CALL_MERGE, tooltip "Gộp mảnh này vào mảnh kề (giữ chữ, bớt 1 panel)"). Folds the fragment's words into the previous one (the next one if it is first). The survivor keeps its own pin and lock; the folded lock is dropped unless the survivor had none (then inherited, `merge_survivor=True`). Later fragment keys shift -1. No confirm (no words lost).
- **Drop a fragment line** (`drop_fragment`, 439; handler `_drop_fragment_line`, 2010; trash icon on a fragment card, tooltip "Xóa dòng này"). Deletes the words. `scene["text"]` is redefined as the concatenation of the survivors, so the verbatim invariant that Stage 5 depends on holds by construction; `word_count` and `target_seconds` are re-derived (a stale count once desynchronised Stage 4 timing, per the docstring at 419). Locks, clips and custom images shift -1. If it was the last fragment of the scene it escalates to delete beat, behind a confirm ("Xóa dòng cuối của beat NN?").
- **Delete beat** (`_delete_beat`, 1903; trash icon on a non-fragment card). Confirm dialog; removes the scene from `narration.json`, its locks (key equal to the beat key, the scene id, or starting `sid:`), clips and custom images; totals recomputed.
- **Insert scene** (`insert_scene_at`, 565; dialog `_open_insert_scene_dialog`, 2190; the circle-plus icon on every "+" row, including above the first and below the last card). The owner types the text. If the boundary is between two fragments of the same scene, or above the hook, or below the closing line, the text is inserted as a **new fragment** of that scene (so narration order and review order agree). Otherwise a **new scene** is created with `scene_id = max+1`, `page_ref` and `beat_id` copied from the neighbour, `panel_ref -1`, `visual_beats = [text]`. In both cases the neighbour's candidate pool and source are cloned so it can be picked immediately; it starts with no lock ("auto").
- **Edit text in place** (`apply_fragment_edits` 463, `apply_scene_text_edits` 520). Each card has an editable text box (fragment cards edit their own clause). Blanking a fragment box deletes it (and remaps everything after it). Blanking a whole scene is ignored: "that is the trash icon's job". A save that changed nothing about scene ids, texts and fragments does not trigger a resync (`_narration_fingerprint`, line 124).
- **Audio already made.** TTS is chunk-cached by `sha256(text|voice|exaggeration|cfg|seed|atempo[|temperature])` in `projects/<p>/cache/tts/<hash>.wav`, so after any edit only the sentences whose text changed are synthesised again (`request_resync`). A clip is cut to a beat's exact duration, so when `ENABLE_VIDEO_CLIPS` is on a **narration change that shifts the timeline** is meant to clear all locks and clips (`clear_project_locks_and_clips`, line 97; I did not trace every caller of it, but the structural handlers above remap instead of clearing).

### A8. Question 7. Timing and the background TTS

- Order: narration approved, download, preprocess, then Review Beats. **Audio is not made before the owner's review is done** in the normal flow. Stage 4 (`ensure_reviewed`) refuses to start until Review Beats is approved and not stale.
- **Background TTS** (`stages/stage_4/background_tts.py`, only when `config.ENABLE_VIDEO_CLIPS` is true, default off). `start_background_tts(project)` is called when the Review Beats screen is built (`s_review_gate.py:~873`). It reproduces Stage 4's exact Chatterbox path (normalise text, chunk one per sentence up to 280 chars, `POST_ATEMPO`, even word spread) and synthesises chunk by chunk into the same cache Stage 4 will read, publishing `review/tts_status.json`: `{"completed", "beat_durations": {beat_key: seconds}, "beat_windows", "scene_durations", "chunks_total", "chunks_done", "narration_sha", "error"}` (`stages/stage_4/tts_status.py`). **Why it exists:** (a) every beat card can show its exact spoken length, which is the length a picked video clip must fill; (b) Stage 4 later finds the audio already cached and only synthesises what changed. A priority bump (`bump_priority_beat`, when the owner opens a beat's clip picker) or a narration edit stops the current batch, keeps finished chunks, and re-plans. It never calls `ensure_reviewed` on purpose.
- The duration chip (`…s` until measured, then `4.2s`) is refreshed by `_poll_beat_durations`, an async task polling `tts_status.json` every 2 seconds (stops after 5 failed mount checks). `GET /api/beat_tts_status` serves the same data to the web page.
- How timings reach the edit: `beat_timing.py` walks the same word stream Stage 4 builds (`chunker.align_scenes_to_words` consumes exactly `word_count` words per scene, hence the insistence on resyncing `word_count` after every text edit) and cuts a scene's span into fragments by word position.

### A9. Question 8. Script rules: enforced in code versus only in prompts

**In code (on the paste path).**

- Structure: one paragraph per item, hook and closing recognised by length (20 words or fewer), item paragraph of at least 8 words, hook options need a choice (`gemini_prompt.py`).
- Cleanup: remove labels, audit tails, emphasis, code fences; drop a hook repeated in the story (ratio 0.85) and a closing line repeated at the end.
- Verbatim fragments: `_verbatim_ok` (word tokens of fragments equal the sentence) and fragment size 4 to 10 words, anti-dangling-word moves (`beat_split.py:20-60`); fragments only produced if the sentence has 12 or more words.
- Sentence-per-scene split.
- At TTS time: `_normalize_for_tts` -> `utils/spoken_text.to_spoken` converts digits, years, issue numbers and symbols to words deterministically and idempotently (`stage_4/pipeline.py:480`). So "no digits" is partly self-healing even if the writer breaks it.
- Optional spoken subscribe line appended or stripped (default stripped).
- Counter warns above 58 s (35 s short mode); never blocks.

**Only in prompts (not checked at import).** Word budget (110 to 160 words, hook 7 to 18, 20 hard max), sentence length (15 to 26 target, 32 max), the 15-line spoken-text block (`spoken_rules.py`: numbers in words, no symbols, no all-caps, no parentheses, colons, semicolons, ellipses or em dashes, pace by commas and periods, no standalone fragment under 4 words), opening rules (event within the first ten words; no question unless the source is hypothetical; citation after the first event, within the first third), reading level IELTS 6.5, household-names-only, banned phrases ("insane", "epic", "unbelievable"; no meme slang), source tiers and fact tracing, no-final-twist-spoiler in the hook, no echo of the hook. `tests/test_spoken_rules.py` and `tests/test_opening_rules.py` only assert that the shared blocks are present and identical in every template (anti-drift), not that scripts obey them.

**In code, but only for the LLM-written path** (`stages/stage_3/write_script.py`, not used by paste): `_validate`, `_detect_hallucinations`, wiki cross-check, `_lint_*` retention rules, hook bands (`_HOOK_MIN_WORDS=8`, `_HOOK_MAX_WORDS=26`, `_INTRO_MIN/MAX=4/14`), critical versus soft errors and best-draft selection (`tests/test_narration_retention_rules.py`).

### A10. Question 9. Small conveniences to keep

Narration screen: prompt saved to the project folder, copied, offered as download, and shown in a selectable box (clipboard is blocked over the LAN); live counter in the same unit the parser maps; the failed script is restored after reload; the saved narration reopens as one paragraph per beat; a script written for other items is withheld with a note; drafting allowed before the comic is downloaded; the parser's refusal lists every paragraph with its word count and first 70 characters; log panel with a copy-all button and per-project log file; red/amber/green status line; no hidden state (the whole paste is kept in the log).

Review screen: Approve auto-saves pending edits; every edit un-approves with a clear amber message ("Đã lưu narration — cần re-approve trước khi render."); per-card badges `auto`, `duplicate panel`, `MP4`, `pick at least 2`, count chip `n/cap`; live duration chip per card; source citation as clickable chips with research links and a loud "UNVERIFIED" chip when the cross-check fails; "Looking for: <drawable moment>" hint; gallery that opens automatically up to a tile budget (4000) and lazily beyond it; jump-to-page field, up and down page-scroll buttons; click a tile for a larger preview; project-wide hide and one-click unhide; split dialog with suggested cut points; "+" rows between all cards; distinct merge versus delete icons with explanatory tooltips; confirms only on destructive actions; card reuse on rebuild so deleting one beat does not re-send thousands of thumbnails; locked panel always shown even if not in the pool; ids never renumbered; atomic JSON writes and quarantine of a corrupt `locks.json` instead of silently resetting; empty state with "Build candidates" button, spinner with elapsed seconds, and the failure reason; list of other projects ready to review; music genre saved on change (no Save button); labels mix English and Vietnamese ("mảnh" = fragment, "Ẩn", "Thêm scene mới").

---

## B. How the comic pipeline calls language models (added at the owner's request)

### B1. Call sites (found by search; I opened the central helper, the SDK wrapper, the scout gate and the art-pipeline callers, and read the list of the rest by grep)

All text LLM calls except the scout and a few raw HTTP ones go through **`stages/stage_3/_llm.py::call_with_chain`**:

- Stage 3 writers and checkers: `stages/stage_3/write_script.py` (about 20 call sites: beats, glossary, scenes, wiki check, coherence, retry-fix, critics), `micro_moment.py`, `explore_answer.py`, `screen_qa.py`, `propose_modes.py`, `provided_narration.py` (trim, frame), `story_architect.py`, `story_verify.py`.
- Other: `stages/stage_1/screen_research.py`, `stages/panel_walk/narrate.py`, `art_pipeline/outline.py`, `art_pipeline/narrate.py`, `art_pipeline/narrate_longform.py`, `art_pipeline/dedupe.py`.
- Different transports: `stages/research_scout/openrouter_gate.py` (raw `urllib`, JSON-schema output), `planner.py`, `editorial_assessor.py`, `qa_semantic_check.py`, `media_router.py` (raw HTTP to OpenRouter), `stages/beat_split` (`_call_with_deadline` directly, `BEAT_SPLIT_MODELS`), `stages/stage_1/llm.py` and `answer_research.py` (You.com research API, `_research_with_youcom`), vision calls in `stages/stage_2/vlm_extract.py`, `identity_check.py`, `cluster_namer.py`, `money_shot.py`, `stage_5/verify_frames.py`, `ui/custom_image.py`, music brief (`MUSIC_BRIEF_MODELS`), `stages/clip_fetch.py`.
- Not an LLM call: the Gemini paste screen (`s3_narrate.py`), and `ui/bridge.py::run_stage_3_propose` / `run_stage_3_write` (lines 935-950), which wrap `propose_modes` and `write_script` for the older LLM flow; nothing in the UI calls them any more (search shows no caller outside tests).

### B2. Providers, model ids, fallback, and how a model is chosen

- **OpenRouter** through the `openai` Python client (`base_url` from config, headers `HTTP-Referer` and `X-Title`), for `call_with_chain`. Raw `urllib` to the same endpoint for the scout gate, planner and others.
- **Claude Agent SDK** (`stages/_claude_sdk.py`): wraps `claude_agent_sdk.query` with the local Claude Code login (checks `~/.claude.json` for an `oauthAccount`). Default model id `claude-sonnet-4-6` (`CLAUDE_SDK_MODEL`). Disabled by default (`CLAUDE_SDK_ENABLED` default `0`, "Master 2026-09-23: Clear all Claude Code CLI calls").
- **You.com** research API for the scout.
- **Switch:** `config.FREE_MODEL` (`config.py:102`, env `FREE_MODEL`, **default true**; the comment block above it still says "default False": the code and the comment disagree, the code wins). `False` means SDK only and no OpenRouter fallback (an SDK failure raises); `True` means skip the SDK and use the OpenRouter chains.
- **Default chains** (all comma-separated env overrides, `config.py:75-165`):
  - `LLM_MODELS`: `minimax/minimax-m2.5:free`, `deepseek/deepseek-chat-v3.1:free`, `meta-llama/llama-3.3-70b-instruct:free`, `google/gemini-2.5-flash-lite`.
  - `CREATIVE_LLM_MODELS` (the narration writer chain): `deepseek/deepseek-v4-flash:free`, `deepseek/deepseek-v4-flash` (paid, $0.10 in and $0.20 out per million tokens per the code comment), `qwen/qwen3-next-80b-a3b-instruct`, `google/gemini-2.5-flash-lite`. A long comment lists models rejected for the writer (CoT leakage, empty content under load, hallucinated memes).
  - `FIDELITY_LLM_MODELS` (fact check): `arcee-ai/trinity-large-thinking:free`, `nvidia/nemotron-3-super-120b-a12b:free`, `google/gemini-2.5-flash-lite`.
  - Scout: `SCOUT_EVIDENCE_MODEL` default `deepseek/deepseek-v4-flash`; `SCOUT_PLANNER_MODEL` defaults to it.
- **How a model is chosen.** The caller passes `models=` (a chain) or `call_with_chain` uses `LLM_MODELS`. Each writer picks its chain by purpose (creative, fidelity, ...). **There is no UI control and no per-project setting for the model.** The only knobs are environment variables read at start-up. (The only dropdowns in the UI are pipeline mode, music genre, publisher and confidence.) A model selector is therefore new work in the new project.

### B3. Mechanics

**`call_with_chain(system, user, models, max_tokens=2000, progress, label, validator) -> (content, model_used)`** (`_llm.py:83`).

- Request: `client.chat.completions.create(model, max_tokens, messages=[{"role":"system",...},{"role":"user",...}])`. No temperature, no `response_format`, no streaming. JSON is requested in the prompt text and parsed by the caller (`extract_json`).
- Timeout: 90 s per request (`_REQUEST_TIMEOUT_S`) with `max_retries=0`, **plus a hard wall-clock deadline**: the call runs in a daemon thread and is abandoned after 90 s (keep-alive bytes from OpenRouter reset httpx's read timer, so the client timeout alone was not enough). The orphaned thread is left to die.
- Retry and fallback per model: rate limit (HTTP error or inline error text in the body, `_is_rate_limited`, `_detect_inline_rate_limit`) means next model immediately; timeout means next model with no same-model retry; any other error means sleep 2 s and one retry on the same model, then next model; empty content means next model; **validator returns False (or raises) means next model**. After the last model: `RuntimeError("[label] all N models exhausted: model: reason | ...")`.
- SDK path (`FREE_MODEL` false): up to 3 attempts; each `sdk_complete` call has a 330 s deadline, thinking disabled (first token about 7 s), `max_turns=2`, no tools, streaming deltas, transient 529 or per-minute 429 retried with backoff 5, 12, 25 s, an account usage cap surfaced at once; rate-limit text, empty output, or validator failure counts as an attempt; failure raises with the last reason ("Claude SDK failed after 3 attempts - last reason: ...").
- Scout gate (`openrouter_gate.review`): `urllib` POST with `response_format: {"type":"json_schema","json_schema":{"strict":true,...}}` and `provider.require_parameters: true`, timeout 180 s, **no transport retry**, exactly **one repair request** whose prompt appends "Your previous response was not valid EvidenceGate JSON. Return only valid JSON matching the requested schema." On any failure it degrades to `EvidenceGate(verdict="inconclusive", reason=...)` rather than raising; a missing key gives `"OPENROUTER_API_KEY is not set"`.

**Validate and retry with the validator's message.** The chain-level validator is boolean only (it just moves to the next model). The **message-carrying** retry lives in callers, most clearly in the art pipeline, which is the closest to the new project (`art_pipeline/outline.py:185-202`, `narrate_longform.py:421-445`):

```python
for attempt in (1, 2, 3):
    raw, model_used = call_with_chain(system=system, user=user, models=CREATIVE_LLM_MODELS,
                                      max_tokens=3500, progress=log, label=f"art-outline#{attempt}",
                                      validator=lambda c: extract_json(c) is not None)
    try:
        outline = build_outline_from_raw(raw, ctx, mode_key)   # raises ValueError with a readable reason
        ...; return outline
    except ValueError as exc:
        user += f"\n\nYOUR PREVIOUS ATTEMPT FAILED VALIDATION: {exc}. Fix exactly that."
raise ValueError(f"outline failed after 3 attempts: {last_err}")
```

The long-form writer does this per chapter (5 attempts), one call per chapter because "small calls stay reliable, a single 1,500-word call does not" (module docstring), feeds each chapter the previous chapter's tail, the lines already said, the forbidden subjects and the verbatim facts of that chapter only, runs a total-words floor gate (1360 words, one automatic redraw, then an error), then a de-duplication pass and cross-chapter validation. The outline validator checks that every fact is a verbatim substring (or at least 80 percent token overlap) of the grounded facts, which is the anti-hallucination device. `write_script.py` uses a heavier version (validate, grounding check, coherence check, retry-fix with the error list, up to 4 passes, best-draft selection).

### B4. Configuration names (names only)

Keys: `OPENROUTER_API_KEY`, `YDC_API_KEY` (You.com; the scout module also falls back to reading it from the `.env` file itself), `CARTESIA_API_KEY`, `RESEMBLE_API_KEY`, `COMIC_VINE_API_KEY`. Claude SDK uses the local login, no key variable.
Endpoints and switches: `OPENROUTER_BASE_URL`, `FREE_MODEL`, `CLAUDE_SDK_ENABLED`, `CLAUDE_SDK_MODEL`.
Model lists: `LLM_MODELS`, `OPENROUTER_MODEL`, `CREATIVE_LLM_MODELS`, `FIDELITY_LLM_MODELS`, `VLM_MODELS`, `VLM_MODEL`, `VLM_MODELS_BATCH`, `BEAT_SPLIT_MODELS`, `MUSIC_BRIEF_MODELS`, `SCOUT_EVIDENCE_MODEL`, `SCOUT_PLANNER_MODEL`.
Behaviour flags seen in this research: `ENABLE_LLM_BEAT_SPLIT`, `ENABLE_VIDEO_CLIPS`, `CHATTERBOX_SEED`, `SPOKEN_SUBSCRIBE_CTA`, `REVIEW_GATE`, `MONEY_SHOT_PIN`, `ART_LF_SAID_LINES_MAX`, `ART_LF_DEDUP_THRESHOLD`, `ART_LF_DEDUP_MAX_PASSES`.

### B5. How a long call is shown in the UI

Flet desktop UI. Pattern (`s3_narrate.py`, `art_ui/screens/a4_narrate.py`): the handler sets `running.visible = True` on an indeterminate `ProgressRing`, sets an amber status line ("Writing narration…"), disables the button, runs the blocking function with `await run_blocking(fn, ...)` (`asyncio.to_thread`, `ui/bridge.py:44`), passing `push_log` as the `progress` callback so every `[label] try 1/4 model=...`, `rate-limited ... falling back`, `validator rejected` line from `call_with_chain` appears live in a log panel (`log_list`, also appended to a per-project log file). On success a green status; on failure a red one-line status plus the formatted traceback in the log (`format_exception`: `UserFacingError` shows only its message, anything else keeps its traceback). **There is no cancel**: no cancellation token, abandoned threads on timeout, the user can only wait or navigate away. (`bridge.cancel()` in `s1_identify.py` belongs to the Stage 1 chat bridge, not to narration.) Per-call token streaming exists only in the Stage 1 chat view (`on_token`).

### B6. Recommendation for a "write the narration" button with a model selector (FastAPI + plain JS)

Copy:

1. The `call_with_chain` contract: ordered chain, per-request hard deadline (daemon thread or `asyncio.wait_for` plus a subprocess/thread for sync SDKs), rate-limit and timeout mean "next model", one same-model retry for unknown errors, empty or invalid output means "next model", a final error naming each model's reason, and the `progress` callback and `label` for observability.
2. The per-chapter writing loop from `narrate_longform.py` for the 2,000 word target (one call per chapter, previous chapter tail and said-lines as context, forbidden-repeat list, facts of that chapter only, a total-words floor), and the **validator-message retry** (`"YOUR PREVIOUS ATTEMPT FAILED VALIDATION: {exc}. Fix exactly that."`, 3 to 5 attempts). Add the outline step of `art_pipeline/outline.py` as a first call; its verbatim-fact check is cheap and strong.
3. The JSON-schema strict output with `require_parameters` from the scout gate where a provider supports it, plus one repair retry.

Change:

- A **model registry** in config (id, label, provider, cost note, `supports_json_schema`, context size, default for "creative") read at start, served by `GET /api/models`; the dropdown posts the chosen id, stored per project so the choice is recorded (`narration.json: "source": {"kind": "model", "model": "<id>"}` instead of the string `"manual (Gemini Master-written)"`). Keep the fallback chain behind the chosen model as "then fall back to the registry default" and show which model finally answered (`model_used` is already returned).
- **Job model instead of a blocking call.** `POST /api/projects/{id}/narration/generate {model}` returns a job id; a background worker runs the chapters; `GET /api/jobs/{id}` (poll every 1 to 2 s from plain JS, or SSE) returns `{state, chapter k/n, attempt, log_lines[], model_used, error}`. Show chapter progress rather than an indeterminate ring. Add `POST /api/jobs/{id}/cancel` that sets a flag checked between attempts and chapters (the comic has none), and a visible log with a copy button.
- Errors: show the one-line user message prominently and the log below (same split as `UserFacingError`), and keep any partial result (finished chapters) so a retry resumes from the failed chapter instead of redoing all.

Where copy and paste remains better: when the owner wants Gemini's Search-grounded Phase 1 research and fact trace with the source tier rules (a model called through an API without search will not produce a sourced fact sheet, and the new pipeline has a dossier instead); when he wants to read the Phase 1 audit and say `WRITE` after judging it (a human checkpoint the button removes); for quality-sensitive first drafts of a new series, and when API keys or credit are unavailable. Keep the button as "draft fast, then edit" and paste as "research-grade".

**One data shape for both paths.** Make the model write the *same text format* the paste path accepts (chapter headings, then paragraphs), not JSON, and run it through the **same** `parse_script(raw_text, dossier) -> narration` function, with the same validation and the same error messages. Then both paths differ only in who produced `raw_text`, and record that in `source`, `master_narration.md`-style raw record, and an optional `llm_model`. Run the validator-message retry against the parser's error (the parser's readable listing is already a good retry message). Never let the model path write `narration.json` directly.

---

## C. Recommendation for the painting documentary (one page)

**Keep as is (copy the behaviour, not the code):**

1. The outline-and-paste loop: a deterministic template fill (no model), saved as a `.md` in the project, one button that copies it, a download, a selectable text box fallback, and a two-turn prompt (Phase 1 research and fact sheet, owner types `WRITE`, Phase 2 writes). Keep the "Run settings" header for Gemini (Search grounding on, thinking high).
2. The tolerant importer: take what is under the last `FINAL SCRIPT` marker; ignore hook options, audit tables, word counts; strip labels, headings, fences, emphasis; on a shape mismatch refuse with a listing of what was found (index, word count, first 70 characters) and an instruction. Add the missing `NO INFO` message.
3. The failed-script safety net (save the paste before parsing, restore on reload) and the saved narration reopening in the same paste format.
4. The review-gate design: one card per fragment with editable text; split with suggested cut points; merge (keeps words) versus drop (deletes words) as separate icons; insert at any boundary; delete beat with confirm; stable ids; every op rewrites the narration, remaps locks, un-approves; approval stamped with a hash of the narration and enforced as a hard gate before audio and render; sparse pending edits, Approve saves them first.
5. Live per-beat duration chips from background TTS and the chunk cache keyed by text and voice settings, so edits only re-synthesise changed sentences.
6. The conveniences list in A10.

**Must change:**

- **The unit of mapping.** The comic maps paragraph N to item N (one comic issue each). A painting video has chapters, not items. Make the mapping *chapter to chapter*: the outline lists chapters with ids and titles; Gemini must return the chapter headings (e.g. `## Chapter 3: <title>`), and the importer maps by heading when present and by paragraph groups otherwise. Validate: number of chapters equals the outline, each chapter within its word band (the art pipeline uses 150 to 340 words per chapter, 1600 to 1700 total; the owner's 2,000 words implies about 5 chapters of 350 to 450 words, and the `ART_LF_*` constants must be re-derived, not copied), total near 2,000 words, no sentence over 32 words.
- **Beats are regions and images, not panels.** The outline should hand over a numbered **visual catalog** (region ids with a short label, the painting's other images, maps, portraits, documents), and ask Gemini to tag each sentence with a visual hint (`[R4]`, `[IMG2]`, `[MAP]`, `[BROLL: short phrase]`). Parse the tags into `visual_beats[].pin` (the comic's micro mode already supports `{"text","page","panel"}` pins and `pre_selected`), and strip them from spoken text. Untagged sentences get the review screen's "auto" state.
- **Candidates ranked, not page-sorted.** There are far fewer comic-style "all panels of the issue" and far more heterogeneous media (region crops, other paintings, stock, You.com finds, OSM maps). Rank by keyword and region-label match with the beat text, show the top 12 plus "show all", keep the manual-first rule (never auto-lock) and the `pre_selected` mechanism, and let the You.com step fill beats that have fewer than N candidates (owner decision 11).
- **The review screen is the existing storyboard editor**: reuse its shots, overlays, timeline, media picker, proposals with locks. The comic's lock file (`beat_key -> panels/custom_image/clip`) maps onto *proposals with locks*; keep the same key scheme (`<scene>:<fragment>`), the remap-on-split/merge/drop rules, and the "any edit un-approves, hash stamped at approval" rule. Add the chapter as a grouping level in the card list.
- **No download or preprocess stage** sits between narration and review, so the staleness checks (items versus downloaded chapters) become a check that the dossier version used for the outline is still the current one (hash of dossier plus region catalog in `narration.json`, like `answer_items_signature`).
- **Validation in code for what matters for 2,000 words**: total and per-chapter word bands, max sentence length, no digits or symbols (or normalise them as `to_spoken` does), banned phrase list, hook within the first N words, no repeated opening. Warn (amber) for style, refuse only for structure, as the comic does.
- **Speaking rate.** The comic estimates 2.9 words per second; the art pipeline measured 2.88 at the channel voice. Use the measured figure from the new voice and show the duration estimate in the counter; 2,000 words is about 11.5 minutes, comfortably over 10.

**What the outline handed to Gemini should contain** (same two-turn shape, English):

1. Run settings (Search grounding on, thinking high) and the role (documentary narrator, the channel voice).
2. The painting card: title, artist, date, museum, dimensions, one-line why it matters.
3. The **dossier merged from the books**, as numbered fact entries with source and a verbatim quote and, when books disagree, both versions flagged `CONFLICT` (the comic's rule: a claim without a Tier 1 or 2 source is not a beat; conflicting sources cannot become a script without saying so).
4. The **chapter outline (the real dàn ý)**: ordered chapters with id, working title, role (cold open, backfill, evidence, twist, resolution, per the art pipeline), target words, the fact ids assigned to it (each fact in one chapter only), the question it answers, and whether it must end on a re-hook.
5. The **visual catalog** (region ids with labels and approximate content; other images; maps) and the tag syntax to use.
6. The writing rules (a version of `SPOKEN_TEXT_RULES`, opening rules, sentence length 15 to 26 and 32 max, reading level, banned phrases, no unsupported claims) inserted from one shared constant, with a test that all templates carry it unchanged.
7. Phase 1: verify each chapter's facts, list gaps, stop with `NO INFO` naming the chapter if it cannot be grounded. Phase 2 after `WRITE`: output blocks `CHAPTER HEADINGS`, `FINAL SCRIPT` (chapter headings plus paragraphs plus visual tags), with the audit blocks after it, which the importer ignores.

Files read for this report: `ui/screens/s3_narrate.py`, `stages/stage_3/gemini_prompt.py`, `beat_split.py`, `ending.py`, `schema.py`, `spoken_rules.py`, `opening_rules.py`, `_llm.py`, `prompts/gemini_*_writer*.md`, `ui/screens/s_review_gate.py`, `ui/screens/s4_tts.py`, `s6_review.py` (header and structure), `stages/review_gate.py`, `stages/stage_4/background_tts.py`, `tts_status.py`, `beat_timing.py`, `chunker.py`, `ui/bridge.py`, `ui/state.py`, `stages/_claude_sdk.py`, `stages/research_scout/openrouter_gate.py`, `art_pipeline/outline.py`, `narrate_longform.py`, `config.py`, `README.md`, `CLAUDE.md`, and the Gemini-related tests. Not read in full: `write_script.py` (4,788 lines), `micro_moment.py`, `explore_answer.py`, `provided_narration.py` (sentence splitter), `ui/web_routes.py`, `ui/custom_image.py`, `ui/intro_import.py`, `research_scout/workflow.py`, `s1_research_scout.py`.
