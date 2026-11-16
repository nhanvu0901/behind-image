# From a chosen painting to a storyboard: script, voice and picks

Date: 2026-11-16. Status: contract v1 for the script stage; outline level for the voice and picks stages.

Inputs to this design:
- `docs/design/2026-11-16-owner-decisions.md`
- `docs/design/research/R5_comic_narration_workflow.md`
- `docs/design/2026-11-16-editor-engine-design.md`
- `docs/design/2026-11-16-library-design.md`

## 1. The stages of a project

| Stage | What exists in `projects/<id>/` | Who acts |
|---|---|---|
| `selected` | `project.json`, `source/` (the dossier snapshot and source texts) | The owner picked the painting in the library |
| `outlined` | `script/outline.json`, approved | A model drafts the outline ("dàn ý"); the owner edits and approves |
| `script` | `script/narration.json`, approved | A model writes the narration; the owner edits, cuts and approves |
| `voiced` | `audio/mix.m4a`, `timing.json` | The Windows server speaks it. Meanwhile the owner chooses pictures. |
| `picked` | `picks.json`, approved | The owner chose what is shown for each beat and added scenes |
| `storyboard` | `storyboard.json` (drafted as a proposal, then edited) | The existing editing page |
| `approved`, `rendered` | approvals, the final video | The owner approves; the server renders |

**Each approval is tied to a hash.** An approval stores the sha1 of the approved file. Any later edit makes the approval stale, and later stages refuse to run on a stale approval. This is the comic pipeline's rule.

**Ids are never renumbered** (also a comic rule). A new beat gets a fresh id. A deleted id is not reused.

## 2. The script stage

The owner's wish: it should feel like the comic pipeline, where the system prepares the material and a model writes the narration. In the UI a button does this, with a dropdown to choose the model. Copy and paste stays as a second path. Both paths go through the same prompt templates and the same parser, so they produce the same data.

### 2.1 The brief (deterministic, no model)

Built from `projects/<id>/source/` on demand:
- **The painting card:** title, artist, year, and whatever `[meta]` lines the sources carry (medium, size, location).
- **The sources.** Each source text is cut into numbered paragraphs. A paragraph id is `<SRC>-<NN>`, where `<SRC>` is a short code per source: `PAY` for `payne_gae`, `HOD` for `hodge_aid`, `HAG` for `hagen_wgps`, `MAD` for `brookehitching_mad`, `DAS` for `dasal_artcurious`, `GRO` for `grovier_nws`. For example `PAY-07`. The mapping from code to `work_id` is stored in the brief.
- **Named details:** the detail headings from Hodge and the section headings of the other sources, as a list `D1 …`. These are candidates for what the camera can point at.
- **Conflicts** between sources on title, artist or year, taken from the dossier.
- **Trust.** Low-trust sources are included only if the owner ticked them, and are marked as such in the prompt.

### 2.2 The outline ("dàn ý"): `script/outline.json`

```jsonc
{"schema": "bti.outline/1",
 "source": {"kind": "model|paste|manual", "model": "…", "created_at": "…"},
 "thesis": "one sentence: the question this video answers",
 "hook_options": [{"id": "h1", "text": "…"}, {"id": "h2", "text": "…"}, {"id": "h3", "text": "…"}],
 "hook_choice": "h1",
 "chapters": [
   {"id": "c01", "role": "cold_open|chapter|closing", "title": "COLD OPEN", "card": false,
    "purpose": "what this chapter does for the argument",
    "word_budget": 190,
    "facts": ["f03", "f07"],
    "show": ["D2", "the inscription above the mirror"]}
 ],
 "facts": [
   {"id": "f03", "claim": "one checkable statement",
    "sources": ["PAY-07", "HOD-02"],
    "certainty": "established|likely|disputed",
    "conflict": null}
 ],
 "target_words": 2000,
 "approval": {"approved": false, "sha1": null, "approved_at": null}}
```

`conflict` is null, or text describing how the sources disagree.

- A `chapter` with `"card": true` gets a chapter card in the video. The title card follows the cold open.
- `facts` is the model's fact table. Every fact cites the source paragraphs it rests on. A conflict between books is surfaced here for the owner to decide; it is never resolved silently.
- The owner can edit everything, choose the hook, reorder, add or remove chapters, change the budgets, and then approve.

### 2.3 The narration: `script/narration.json`

```jsonc
{"schema": "bti.narration/1",
 "project": "…", "title": "…", "language": "en",
 "source": {"kind": "model|paste", "model": "…", "created_at": "…"},
 "chapters": [
   {"id": "c01", "role": "cold_open", "title": "COLD OPEN", "card": false,
    "beats": [
      {"id": "b0001",
       "text": "One paragraph of narration, one to three sentences, exactly as it will be spoken.",
       "facts": ["f03"],
       "show": ["the convex mirror"],
       "locked": false, "note": ""}
    ]}
 ],
 "approval": {"approved": false, "sha1": null, "approved_at": null}}
```

- **A beat** is the unit the owner confirms, cuts and later gives pictures to. It is one paragraph.
- **`show`** is a hint in plain words of what should be on screen. It is not a technique. Techniques are chosen later.
- **`text`** holds only words to be spoken: no tags, no stage directions, no headings.

### 2.4 The text format the model writes, and the tolerant parser

The model does not write JSON. It writes text in a fixed layout, and one function, `parse_script`, turns that text into `narration.json`. A pasted script goes through the same function.

```
FINAL SCRIPT

## c01 COLD OPEN
Paragraph of narration.
>> facts: f03, f07 | show: the convex mirror; the inscription above it

Next paragraph.
>> facts: f02 | show: the whole painting

## c02 THE MERCHANT CITY
…
```

**Parser rules (tolerant, as in the comic pipeline):**
- Take the text after the LAST line `FINAL SCRIPT`. If there is none, take all of it.
- Drop code fences, hook-option lists, audit tables, word counts and commentary lines.
- A `## ` line starts a chapter. It is matched to the outline by id, or failing that by title. Unmatched chapters are reported.
- Each paragraph is a beat. A `>> ` line after a paragraph is its metadata, and is optional. Unknown fact ids are reported and do not abort the parse.
- If the text cannot be placed, nothing is written. The error lists each paragraph with its word count and first 70 characters, so the owner can see where it went wrong.
- A failed paste is kept in `script/last_paste.txt` and restored into the box on reload.

**The outline is written the same way.** The model writes it under a line `OUTLINE` in a fixed text layout, and `parse_outline` reads it.

### 2.5 Prompts

Templates live in `prompts/` at the repo root and are filled by string replacement. The same filled text is what the "copy prompt" button gives.
- `prompts/outline.md` is phase 1. From the brief it produces the thesis, three hook options, the fact table with source paragraph ids, certainty and conflicts, and the chapter outline with budgets.
- `prompts/script.md` is phase 2. From the brief and the APPROVED outline it writes the narration in the layout above. Through the API it runs chapter by chapter, with the previous chapters given as context.
- Shared rule blocks:
  - `prompts/rules_voice.md`: how this channel narrates. It is distilled from `docs/research/great-art-explained/NARRATION_ANALYSIS.md`, `narration/language-style.md` and `narration/structure-longform.md`, plus the spoken-text rules of the comic pipeline.
  - `prompts/rules_format.md`: the output layout.

### 2.6 Models

`config/models.json` lists the models the dropdown offers:

```json
[{"id": "gemini-4-argon", "label": "Gemini 4 Argon", "provider": "gemini",
  "model": "gemini-4-argon", "key_env": "GEMINI_API_KEY", "default": true}]
```

- **Providers** are small modules with one function, `complete(model, system, user, *, timeout, on_progress, cancel) -> text`.
  - `gemini`: the Google Generative Language REST API.
  - `openrouter`: chat completions, as the comic pipeline uses.
  - `mock`: canned text for tests and for trying the page without a key.
- **Keys.** A model whose key is not set is listed but disabled, with the name of the missing variable. Keys come from the environment or from this project's own `.env` (never the comic repo's). They are never logged or returned by the API.
- **Calls** run as background jobs with progress per chapter, a cancel button, and a hard timeout. On a timeout or a rate limit, the job offers the next model; it does not switch silently.
- **Validation retry.** A chapter that fails validation is retried once, with the validator's message appended. The chapters already written are kept.

### 2.7 Validation

Errors block approval:
- a chapter of the outline is missing from the narration
- an empty beat
- markup or metadata left inside `text`
- total words under 70% of the target
- a stale outline approval

Warnings are shown and do not block:
- total words outside ±15% of the target
- a chapter outside ±30% of its budget
- a beat over 90 words
- a fact id that is not in the outline
- a beat with no `show` hint

Information only:
- words, and estimated minutes at the measured voice rate
- sentence-length profile against the style targets
- the share of each source used
- overlap with the source texts (the owner has said copyright is not a blocking concern, so this is never a gate)

### 2.8 HTTP API (prefix `/api/projects/{pid}`)

| Method and path | Purpose |
|---|---|
| `GET /brief` | the brief (section 2.1) |
| `GET /prompt?phase=outline\|script` | the filled prompt as text, for copy and paste |
| `POST /outline/generate` | body `{model, notes}`; `model` is REQUIRED (400 without it: no default model is ever started silently, a real model uses the owner's quota); returns `{job_id}`; 409 while another model job of the project runs |
| `POST /outline/import` | body `{text}`; parses a pasted outline |
| `GET /outline`, `PUT /outline` | read; save with `{outline, base_rev}`, returning `{rev, outline, issues}` |
| `POST /outline/approve` | body `{rev}` |
| `POST /narration/generate` | body `{model, chapters?, notes}`; returns `{job_id}`. `chapters` limits the run to some chapters, so one chapter can be rewritten with a note. |
| `POST /narration/import` | body `{text, merge?, force?}`; parses a pasted script; 409 with the locked beat ids (and the paste kept) when it would replace locked beats, unless `force` |
| `GET /narration`, `PUT /narration` | read; save with `{narration, base_rev}`, returning `{rev, narration, issues, stats}` |
| `POST /narration/approve` | body `{rev}` |

Global:
- `GET /api/models`
- `GET /api/jobs/{id}`
- `POST /api/jobs/{id}/cancel`

### 2.9 The page: "Kịch bản" (`script.html`)

Same look and conventions as the editing page. Vietnamese labels.

```
┌ top: project · model [dropdown] · Lập dàn ý · Viết lời dẫn · Sao chép prompt · Dán · Kiểm tra (n) · Duyệt ┐
├───────────────────────────┬───────────────────────────────┬──────────────────────────────────────────────┤
│ NGUỒN                     │ DÀN Ý                         │ LỜI DẪN                                      │
│ tabs per book, numbered   │ thesis · hook options (pick)  │ chapters, each with its beats; text editable │
│ paragraphs, named details,│ chapters: title, purpose,     │ in place; per beat: facts, show hint, lock,  │
│ conflicts, trust badge,   │ budget, facts, show           │ note; split · merge · drop · insert ·        │
│ search                    │ fact table with sources       │ rewrite this chapter                         │
└───────────────────────────┴───────────────────────────────┴──────────────────────────────────────────────┘
 status: words · estimated minutes · per-chapter budget bars · job progress with cancel
```

- Clicking a fact or a source id highlights the source paragraph on the left.
- "Sao chép prompt" opens a dialog with the text in a selectable box and a copy button. Clipboard access can be blocked, so the box must always be selectable.
- "Dán" opens a box for the model's answer. A failed parse shows the paragraph list.
- Undo and redo. Save with a revision check. Any edit drops the approval.

## 3. The voice stage (outline level; contract to follow)

- Runs on the Windows server with the comic channel's narrator voice (Chatterbox, `machiavelli_ref.wav`), under the heavy-job rules.
- Speech is cached per sentence, keyed by the hash of the spoken text and the voice settings. After an edit, only the changed sentences are synthesised again.
- Numbers and symbols are converted to spoken words at this stage, not in the script.
- Word times come from forced alignment on the Mac.
- Output: `audio/mix.m4a` and `timing.json` in the engine's format. Beats and chapters map onto word ranges.
- Starts when the narration is approved. The owner chooses pictures while it runs.

## 4. The picks stage (outline level; contract to follow)

- One card per beat with a tray of candidates:
  - regions of the main painting
  - images found from the beat's `show` hints (Wikimedia Commons, museums)
  - suggestions from You.com research, for beats with too few pictures
  - the owner's own images and clips
- The owner picks, adds scenes and cuts. Then a draft storyboard is generated as a PROPOSAL for the editing page.
- A draft may use any of the 71 techniques.
- The licence gate is advisory: it records and warns, and does not block.
