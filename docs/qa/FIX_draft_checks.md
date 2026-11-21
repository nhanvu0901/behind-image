# FIX: a first storyboard draft that does not need twenty corrections, and checks that catch what a viewer would see (worker fixdraft)

Brief: `.scratch/agy_tasks/fixdraft/TASK.md` (main checkout). Evidence: `.scratch/arnrun/` (the run of the project `arnolfini-opus`, 2026-11-19). No model was
called (no `agy`, no `claude`), nothing in the server's main folder or its app was changed; the only contact with `arnolfini-opus` was `scp` of two of its
storyboards' history copies (`changes/batch_0015.before.json`, `batch_0020.after.json`, `batch_0040.after.json`, `batch_0044.after.json`), `timing.json`,
`picks.json` and the painting, read-only, trimmed into `tests/engine/fixtures/viewer/` (250 KB; the painting is a 192-pixel copy).

## 1. What was wrong, in one measurement

On the first draft of the real run (`changes/batch_0015.before.json`, 109 shots, 764.5 s) the checks I wrote find:

| what the owner saw | the check | on the first draft |
|---|---|---|
| the whole painting small between two black bars | `upright_whole_share` | 41 shots, 205 s = 26.9% of the video (limit 6%); worst `s0088` 10.9 s, `s0089` 10.2 s, `s0008` 9.9 s, `s0019` 8.1 s, `s0078` 8.1 s |
| a spotlight that blacks the screen | `highlight_too_dark` | 8 of 18 layers (mean luma 19 to 31, scale 16 to 235) |
| the lit spot outside the frame | `highlight_off_frame` | 2: `s0076/o1` (spot 28% above the frame at 528.9 s), `s0077/o2` (96% down) |
| pictures no line uses | `asset_not_in_lines` | 3: the squirrel (`s0030`), the pine marten (`s0036`), the pigment (`s0092`) |
| a base explanatory component in the first half minute | `explainer_early` | 1: the time axis `s0003`, 14.8 s to 25.6 s |
| text nobody wrote | `text_not_in_narration` | 1: DOC-01 `s0066` reads "Van Eyck was present", the narration says "was here" |

The other three (a shot under 1.5 s, a placeholder caption, a map label the narration does not carry) were not in the plain draft: they came with the owner's first
six requests (`batch_0020.after.json`, 112 shots), where the checks find `shot_short` `s0073` (1.1 s), `caption_placeholder` 3 (`s0112` "UNKNOWN AUTHOR UNKNOWN
AUTHOR, 1950", `s0036` "Source: an estimate cited in the narration", `s0089` "JAN VAN EYCK, 1434" under "Wedding"), `text_not_in_narration` 4 (`s0013` the label "Belgium"
and the sea names, `s0036`, `s0066`). The state before round 3 (`batch_0040.after.json`, 17 spotlights, after the cameras were corrected) raises 3 `highlight_off_frame`
and 7 `highlight_too_dark`: the three black stretches of the exported file (`s0145` the candle, `s0097` the orange, `s0159` the oranges) are among them.
**The final storyboard (`batch_0044.after.json`, rev `efdeaa7d`) raises none of the nine.** (`tests/engine/test_viewchecks.py` pins all of this.)

## 2. The briefings

### 2.1 Size (characters; bytes in brackets)

| file | before | after | change |
|---|---|---|---|
| `skills/storyboard_draft/TASK.template.md` | 23,600 (23,693) | 26,730 (26,823) | +3,130 (+13.3%) |
| `skills/storyboard_edit/FAST.template.md` | 7,714 (7,868) | 9,023 (9,177) | +1,309 (+17.0%) |

The old test `tests/draft/test_explainers_briefing.py::test_the_briefings_stay_short` pinned the draft task under 23,950 bytes; it is now 27,000 (with the reason written in
its docstring), and `tests/draft/test_fixdraft.py` pins both increments. The fast briefing's rendered size on the box fixture (`tests/draft/test_box_briefing.py`, limits 26,000
to 36,000) is unchanged in kind: it also loses the pictures that no line uses, which more than pays for the bullets on a project with stock photographs.

### 2.2 Each rule, as written (`TASK.template.md`, section 1, new rules 13 to 17; the fast briefing's bullets are further down)

13. **The frame is full.** `zoom` is screen pixels per source pixel; the main painting (W x H, `source_size`) fills the screen's width at `zoom = 1920 / W` (3840 px wide: 0.5) and under 0.6 of that (0.3) is a small picture between two black bars. That whole-painting frame may total at most 5% of the running time (30 s in ten minutes): the pull back that ends the cold open, ONE chapter opening and the last shot, nowhere else (STATIC-01 on the whole painting only there; every other CAM-03 pull back ends on a wide band). Elsewhere keep `zoom >= 0.6 x 1920 / W` and fill the width (`cx = W / 2`, `cy` between `540 / zoom` and `H - 540 / zoom`) with a slow travel up or down, a wide band, or a detail. Neighbouring shots never end and start on the same frame. The compiler gives the channel-name beat and each chapter mark the pose of the shots beside them: end the shot before the beat, and start every chapter's first shot, on a filling frame. Why: 41 of the 109 shots of the first real draft were that small picture; the video looked dark and the same.
14. **Highlights are rare and stay lit.** HI-01 and X-HI-01: at most one in two minutes, none in the first minute; only on a wide frame to point at an object, never when the camera already frames it closely. The region's centre stays inside the frame, 5% in from every edge, from the layer's start to its end (look at both camera keys); `floor` / `surround_floor` 0.6 or more (the default 0.2 left the screen almost black, three times for five seconds).
15. **Text on the screen is true and tidy.** Every date, figure, place, name and map label comes from the narration ("twenty-three" is 23); labels of your own are short names of details. A caption is the narration's word, the picture's own title, or nothing: never a placeholder ("Unknown author"), a source note, the word "narration" or the same words twice. Write every caption and sub-caption you rely on, `""` for none (an empty `*_sub` is filled from the picture's file). MAP-01: only places the narration names; `region_label` `""`, `region_iso` `[]`, `sea_names` `false` unless it names that country or sea.
16. **The first half minute is the painting.** No base explanatory component (MAP-01, TIME-01, TREE-01, STATE-01) before second 30; dates go as large figures on the picture (STATIC-09). A line about where gets MAP-01 even when the owner's pictures for it are street-map tiles.
17. **Only the pictures of `inputs/assets.json`** (each is chosen for some line; the owner took the others out). A small picture (long side under 1000 px) at `zoom` 2 at most, in a panel, never full screen.

Also in `TASK.template.md`: section 0 carries the owner's note (`{{#NOTE}}- The owner's wish for this draft, in their own words (follow it wherever it does not break a rule of
section 1): {{OWNER_NOTE}}{{/NOTE}}`, only when there is one); section 6 loses the sentence that repeated rule 5; the explanatory-devices "How often" bullet adds "no base one before second 30 (rule 16)";
section 7 says that the nine codes are "the owner's rejections, so fix them too"; the edit-mode step 2 says "When a shot now shows something else, rewrite its `note` (or leave it empty): never keep the old reason".

`FAST.template.md` (the request box), four bullets under "How the usual requests turn into operations":

- **the frame stays full**: `zoom` is screen pixels per source pixel. The main painting (width `W`, listed below) fills the screen at `zoom = 1920 / W`; under 0.6 of that it is a small picture between black bars: write no such key, except for the pull back that ends the cold open, one chapter opening and the last shot (5% of the video at most). Fill the width (`cx` = `W / 2`, `cy` between `540 / zoom` and `H - 540 / zoom`); a shot does not end where the next begins.
- **after you move a camera, look at its highlights** (`HI-01`, `X-HI-01`): `at` must stay inside the frame, 5% in from every edge, from the layer's start to its end, else `remove_overlay` it (also when the camera now frames it closely). Never a `floor` / `surround_floor` under 0.6.
- **text on the screen**: only what the narration says or a picture's own title; no placeholder, no word "narration", nothing twice; a caption you have nothing for is `""`. `MAP-01`: `region_label` `""`, `region_iso` `[]`, `sea_names` `false` unless the narration names that country or sea. Before second 30 no `MAP-01`, `TIME-01`, `TREE-01`, `STATE-01`: dates go as large figures on the picture (`STATIC-09`).
- **pictures**: only those listed below (each is chosen for some line); a small one (long side under 1000 px) at `zoom` 2 at most, in a panel.

The briefing states a stricter number than the check (5% against 6%; `floor` 0.6 against the luma 32) so that an agent that obeys never trips it.

### 2.3 What the agent is given

- **Only pictures that a line uses.** `bti/draft/workspace.py` offers (`inputs/assets.json`, `images/`, the `compile_input.json` the helper commands compile from) the main painting, the
  pictures that a line of the narration still has (a beat in the timing, not skipped) and, in a re-draft or an edit, the pictures that the saved storyboard still shows but no line has,
  marked "keep the shots that show it as they are, never use it in a new shot". The pictures stay in the project (`picks.json` is not touched). When the picks say nothing about lines (the
  picks made from a saved storyboard's own assets), nothing is hidden. The fast box lists "Other pictures of the project" by the same rule (`fastedit.assets_block`). New helpers:
  `bti.draft.inputs.line_assets`, `shot_assets`.
- **The owner's note** (section 5).
- **The looks the owner rejects go back to the agent**, not only the errors: `bti/draft/run.py` `check(turn)` now also returns the compiler's report when a warning with one of the nine
  codes is in it, with the sentence "The warnings ... are looks the owner rejects (see section 1, rules 13 to 17): fix them too". The agent's run already allowed two repair turns
  (`max_repairs=2`); a clean draft costs nothing more. The compiler carries the issue's `hint` into its own issue (`compile.map_issue`).

## 3. The checks (`bti/engine/viewchecks.py`, called at the end of `storyboard.validate`)

All nine are **warnings** (`level: warn`, never an error: each is a look, and an error would stop a save the owner may want). Each issue has a `code`, `path` (the shot, or the overlay), `args`,
a `hint` (one English imperative sentence) and a `message` (what is wrong, then the hint), and appears in `ISSUE_CODES` with "(warning)". Because they are in `validate`, the page, `GET
/api/projects/{pid}`, `bti do ... storyboard.validate`, the draft's `check` command and the compile of every draft show them. Cost, measured on the Mac: 0.04 to 0.11 s for the 110-shot storyboard
(0.01 s when no highlight needs the painting's grey copy; the first call reads the copy); the grey copy of a picture (96 pixels wide) is read once per file version.

| code | threshold | raises on | what it cannot see |
|---|---|---|---|
| `shot_short` | a shot of 0.2 s (the engine's error floor) up to 1.5 s (the briefing's minimum) | `s0073` 1.1 s (after round 1) | nothing: it is arithmetic. |
| `upright_whole_share` | the main painting (the picture on screen longest as the main image of a shot with a camera) covers under 60% of the 1920x1080 frame (width and height both counted) for more than 6% of the running time; a clip under 60 s is never judged; sampled every 0.25 s along the eased camera | first draft 26.9%, 41 shots; final 3.0% (22.9 s in 5 shots: the opening, the cold-open pull back, the chapter 6 mark and opening, the last shot): clean | pictures in the panels of `LAY-01`, `X-CMP-01` (a small whole painting in a split is not counted), a different main picture per chapter, and the look of the matte itself. It is "small between bars" for any painting, not only upright ones: a 2:1 painting at full width is 89% and clean. |
| `highlight_off_frame` | the centre of an `HI-01` / `X-HI-01` region, in screen pixels at five moments of the layer's window, is nearer an edge of the frame than 5% (or outside) | first draft: `s0076`, `s0077`; before round 3: `s0126`, `s0076`, `s0158` | the size of the lit ellipse (a huge one around a centre at the edge still lights something); a layer with `hold_s` shorter than the overlay. |
| `highlight_too_dark` | estimated mean luma of the frame (16 to 235) under 32 at one of three moments of the hold **and** under 0.75 of what it is without the highlight (so a frame that is dark for another reason is not blamed on it); `floor_needed` is the floor, in steps of 0.05, that would reach 32 (null: none would) | first draft 8 of 18 layers, before round 3 7 of 17 | a base shot that is already dark is judged only if the highlight takes a quarter of its light; overlays that are not spotlights (NUM-01 dims the picture to 0.38 and STATIC-04 its background: two of the run's remaining stretches under 30 were those, the third the chapter 2 mark, by design; KEY-01 and DOC-01 dim too); text drawn over the frame. Skipped silently when the picture cannot be read. |
| `caption_placeholder` | any on-screen text param (string, text, lines, the string fields of items) that contains "unknown author", "anonymous author", "lorem ipsum", "placeholder", "sample narration", "todo", "tbd", the word "narration" / "narrator" / "voice-over", or is just "unknown", "n/a", "none", "null", "untitled"...; or (LAY-01) a `caption_*_sub` that is only "artist, year" of the panel's picture file under a main caption that is neither that picture's title nor its artist | after round 1: `s0112`, `s0036`, `s0089` | a caption that is wrong in a way no word list sees (a real title on the wrong picture); the example text left in a catalogue param (`BLUE UNDERGARMENT`) when it is plausible. |
| `caption_repeats` | the same 1 to 4 words said twice in a row (`UNKNOWN AUTHOR UNKNOWN AUTHOR`; a repeated number or a 1 to 2 letter word is not) | (caught as a placeholder first in the real run; raised alone in the unit tests) | repeats separated by other words. |
| `text_not_in_narration` | the figures (digits; English number words: "twenty three", "a hundred", "six hundred") of `NUM-01` `value`, `TIME-01` dates, `STATIC-09` `year`; the words of `MAP-01` `region_label` and place names, `TREE-01` node names (none missing), `NUM-01` `source` and `DOC-01` `reading` (a quarter of a sentence of more than four words may be the model's own); `MAP-01` `sea_names` on while the narration has no sea word (sea, ocean, gulf, bay, strait, atlantic...). What the picture itself says (title, artist, year of the pictures the shot shows) is allowed | first draft `s0066` ("present"); after round 1 `s0013` "Belgium" and the sea names, `s0036`, `s0066` | text inside a picture; the names a map draws from its own data (it cannot know which seas show, so `sea_names` is judged by the narration's words); free labels (X-ANN-01, KEY-01 and the like are the model's own words, as the briefing allows); a country shaded with no label; a number said in another form ("a dozen", ordinals); the narration of a language the number words do not cover. |
| `asset_not_in_lines` | a picture in a slot of a shot or overlay that no line has in `picks.json` (not skipped) and that is not the main painting; one issue per picture, with the shots | first draft: squirrel, pine marten, pigment; final: clean | needs `picks.json` in the project folder (the helper commands' scratch workspace has none: they are protected by the catalogue instead; the final compile of the draft, on the real project, runs it). |
| `explainer_early` | a shot of kind base whose technique is `MAP-`, `TIME-`, `TREE-` or `STATE-` starts before second 30 | first draft `s0003` (time axis, 14.8 to 25.6 s) | the same shot at second 31 (the rule is a count of seconds, not a feeling). |

### How the darkness estimate compares with the measured luma of the seventeen layers

For each layer, the estimate at the middle of its window (geometry of the shot's camera at that moment, the region, `rx`, `ry`, `floor`, `feather`, a 96-pixel grey copy of the painting, the
spotlight's own formula) against the luma measured in the exported file (`ffmpeg signalstats`, 16 to 235; the log of the run, "ROUND 3"):

| layer | measured | estimated | | layer | measured | estimated |
|---|---|---|---|---|---|---|
| `s0005/o2` HANDS | 37.8 | 38.5 | | `s0076/o1` SIGNATURE | 28.0 | 28.6 |
| `s0126/o25` WOMAN_FULL | 39.9 | 40.2 | | `s0158/o50` OVERSHOES | 27.4 | 27.9 |
| `s0023/o1` WOMAN_HEAD | 41.9 | 42.4 | | `s0159/o51` WOMAN_FULL | 39.7 | 40.2 |
| `s0026/o1` SKIRT_HAND | 36.2 | 36.7 | | `s0159/o52` ORANGES | 24.8 | 25.3 |
| `s0046/o1` BED | 39.6 | 40.2 | | `s0080/o2` SIGNATURE | 35.5 | 36.2 |
| `s0145/o37` LIT_CANDLE | 22.9 | 23.3 | | `s0083/o1` ROUNDELS_RIGHT | 31.2 | 31.8 |
| `s0153/o46` X-HI-01 MIRROR | 27.6 | 28.0 | | `s0097/o1` ORANGE_SILL | 23.2 | 23.8 |
| `s0068/o1` MIRROR_FIGURES | 27.7 | 28.3 | | `s0102/o1` SIGNATURE | 35.6 | 36.2 |
| `s0069/o1` ROUNDELS_RIGHT | 30.8 | 31.5 | | | | |

Mean absolute error 0.56, largest 0.71, always slightly high (+0.56: text and the soft shadow of the picture are not in the estimate). The test
`test_the_brightness_estimate_agrees_with_the_luma_measured_in_the_exported_file` demands at most 2.0 for each layer and 1.0 on average. The threshold 32 is the coordinator's number
("frame mean luma not under about 32"): at 32, 10 of the 17 layers raise (7 `highlight_too_dark` plus 3 `highlight_off_frame` in that state; the coordinator removed 15 and
softened 2). The two layers he kept with `floor` 0.6 (`s0145` candle 34.6 measured, `s0153` mirror 44.3) are clean in the final storyboard.

### Why each check is where it is in the automatic run's quality bar (`bti/auto_run/checks.py`, gate `storyboard`)

| code | list | reason |
|---|---|---|
| `upright_whole_share`, `highlight_off_frame`, `highlight_too_dark`, `caption_placeholder`, `caption_repeats`, `text_not_in_narration`, `asset_not_in_lines`, `explainer_early` | `STOPS` (with an English and a Vietnamese reason) | each is a look the owner rejected in the first video made end to end with a real model, and the export that follows takes 15 to 25 minutes; the run stops and the owner asks for the fix with one request (`draft.edit`) instead of finding it in the finished video. `text_not_in_narration` also guards the owner's rule that facts come only from the narration. |
| `shot_short` | `TOLERATED` | a shot of 1.1 s is a flash, not a defect of substance; the video is still watchable and the owner sees it in the list. |

`tests/auto/test_run_joined.py` (every warning code is in one list) passes unchanged; `tests/auto/test_viewer_checks_bar.py` pins the sorting and the sentences.

## 4. The Vietnamese sentences (`bti/editor/static/js/errmsg.js`, block `fixdraft` at the end of the file)

`FIXDRAFT_SENTENCES` (one function per code, taking the issue's `args`) is merged into the table `issueText` consults first (`Object.assign(BUILD, ...)`), so a storyboard issue of these codes
reads as one plain sentence that names the shot, gives the numbers and says what to do (no technique id; the shot's id is kept as everywhere else). Examples (from `tests/editor_frontend/fixdraft.test.mjs`):

- `upright_whole_share`: "Bức tranh chính hiện nhỏ giữa hai dải đen trong 27% video (205 giây, 41 cảnh; mức cho phép là 6%). Chỉ giữ cả bức ở cuối cảnh mở đầu, ở một đầu chương và ở cảnh cuối; các cảnh còn lại cho tranh lấp đầy màn hình. Nặng nhất: s0088 (10,9 giây), s0089 (10,2 giây)."
- `highlight_too_dark`: "Cảnh s0145: lớp rọi sáng vùng "LIT_CANDLE" làm cả khung hình gần như đen (độ sáng trung bình 23, thấp hơn mức 32). Bỏ lớp rọi sáng nếu máy quay đã gần sát chủ thể; nếu không thì nâng độ sáng của phần còn lại lên khoảng 0,5."
- `caption_placeholder`: "Cảnh s0112: dòng chữ "UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950" là chữ giữ chỗ hoặc lời nhắn cho người đọc, không nên hiện lên hình. Xóa nó, hoặc thay bằng chữ lấy từ lời dẫn hay tên của chính bức hình."

I added no word to `labels.js` (nothing new is a label). The existing `sbissues.test.mjs` (every `ISSUE_CODES` code has a Vietnamese template) now also accepts `FIXDRAFT_CODES`
(it needs `.venv/bin/python` and is skipped on the Mac). `tests/editor_frontend/editlogic.test.mjs` lists the two note codes as whole-video start codes.

## 5. The owner's note of `draft.start`

`POST /api/projects/{pid}/draft/start` takes `note` (text, at most 600 characters after trimming; `null` or empty is none). More than 600: `422 draft_note_too_long`; not text: `422
draft_note_invalid` (both with a hint in `bti/editor/hints.py`, a Vietnamese sentence in `bti/draft/run.py` `VI` and in `errmsg.js` `STAGE_CODES.draft`). Nothing starts when it is refused.
The job keeps it in `meta.note`; `workspace.build(..., note=...)` writes it into `TASK.md` as one line (spaces folded; `{{` and `}}` made harmless so that the owner's words can never be read as
a template key; cut at 600): "- The owner's wish for this draft, in their own words (follow it wherever it does not break a rule of section 1): ...". The provider `auto` (no agent) ignores it.
The state answer's action `draft.start` has `body: {"provider": "agy", "note": null}` (the CLI drops a null, so `bti do <project> draft.start --set note="..."` adds it) and its `when` says so; the
documents are `docs/AGENT_API.md` (generated action table and the example answer), `skills/storyboard/SKILL.md` (generated table and the sentence) and `docs/APP_GUIDE.md`. The page has no box for
the note (that needs `bti/editor/static/js/` views that are not in my list): **Needs another worker: a one-line text field next to "Dựng bản nháp" in the simple step-5 page that sends `note`.**

## 6. After an edit and the progress line

- **A shot's note after an edit** (`bti/ops/sb_ops.py`): the note is the reason a shot was written ("over the squirrel photo"). The smallest sound rule: an operation that changes what the shot
  shows, `set_technique` and `set_slot` on the shot's main picture (to another picture), **clears** the note (to `""`); camera, parameter and overlay changes, a cut and a merge keep it, because
  the reason still holds. It is in the operations' summaries (so `docs/OPS.md` says it), one batch, undone with the batch. In the deep edit's workspace the briefing says the same ("rewrite its
  `note` or leave it empty"). A split copies the note to both halves as before.
- **"9/8 chapters"**: `out/` also holds `regions.json` (and `notes.json` in an edit), and the progress counted every `*.json`. `bti/draft/run.py` `_chapters_written` counts only the in-scope
  chapters' own files and never more than the number of chapters.

## 7. Decisions where the brief was silent

1. **Warnings, not errors**, for all nine (the brief allowed an error only with an argument; I found none: each depends on an estimate or a taste).
2. **The share is by coverage of the screen (under 60%), not by "upright"**, so that a landscape painting is judged by the same rule and an upright one at full width is clean; the code name keeps the
   brief's word. The numbers: 60% is zoom 0.3 for a 3840-pixel painting (the whole painting is 0.21); the limit 6% is between the final storyboard's 3.0% and the first draft's 26.9%.
3. **Short clips are not judged for the share** (under 60 s): the made-up storyboards of the existing tests are 20 s long.
4. **`highlight_too_dark` also needs the highlight to take a quarter of the light** (0.75): of the 18 layers of the first draft this drops 2 whose frame was already about 30 without the highlight
   (the small painting between bars, which `upright_whole_share` reports).
5. **`caption_placeholder` covers the metadata line** ("JAN VAN EYCK, 1434" under "Wedding") only for `LAY-01`, where the compiler fills an empty `*_sub` from the picture; the other techniques
   have no such default I could verify.
6. **The year, title or artist of a picture the shot shows is allowed on screen** even when the narration does not say it (the coordinator accepted "Man in a Red Turban 1433", "Durer 1500"...).
7. **Where the unused-picture check reads `picks.json`:** the engine's `validate` has the project folder and already reads its files, so the check lives there (one JSON read).
8. **The repair loop sends the nine codes back** (not every warning): pacing and repeated-technique warnings stay advice, as before.
9. **No check for "a picture flagged small is shown no larger than its pixels allow"**: it is in the briefings (rule 17 and the fast bullet) only; the brief lists no check for it. A
   check would be `zoom` over 2 on a picture under 1000 px; I did not add it.
10. **The chapter marks and the brand card**: they are made by `bti/identity/apply.py` from their neighbours' poses (not on my list), so the briefing asks the agent to end and start the neighbouring
    shots on filling frames instead of changing the applier. In the real run they were on the small picture because the neighbours were.
11. **Fixtures:** the real storyboards are the history copies of the batches, trimmed (derived keys, notes, credits, `source`/`locked`/`intent` of shots and overlays removed; params kept).

## 8. Files

New: `bti/engine/viewchecks.py`; `tests/engine/test_viewchecks.py`, `tests/engine/fixtures/viewer/` (first_draft, after_round1, before_round3, final, timing, picks, painting, hi_luma);
`tests/draft/test_fixdraft.py`; `tests/auto/test_viewer_checks_bar.py`; `tests/editor_frontend/fixdraft.test.mjs`; this report.
Changed: `bti/engine/storyboard.py` (2 lines: import, the call, `ISSUE_CODES.update`), `bti/auto_run/checks.py` (a marked block), `bti/draft/{workspace,inputs,run,fastedit,compile}.py`,
`bti/editor/{draft_api,state_api,hints}.py`, `bti/ops/sb_ops.py`, `bti/editor/static/js/errmsg.js` (block at the end), the two briefings, `skills/storyboard/SKILL.md`, `docs/APP_GUIDE.md`,
generated: `docs/AGENT_API.md`, `docs/OPS.md`; tests updated (not deleted): `tests/engine/test_issue_codes.py` (the codes of `viewchecks.py` are scanned too), `tests/engine/test_map.py` (its fixture's map is the first shot: it
ignores `explainer_early`), `tests/draft/test_explainers_briefing.py` (the size pin), `tests/draft/test_box_briefing.py` (the "other pictures" are now only those of a line: the test puts C on a
line and checks D is left out), `tests/auto/test_loop.py` (the lists' codes are looked up in `viewchecks.py` too), `tests/editor_frontend/sbissues.test.mjs` and `editlogic.test.mjs`,
`tests/ops/test_sb_ops.py` (+5). The worked session of `skills/storyboard/SKILL.md` (played against the ops fixture by `tests/cli/test_cli_docs.py`) now prints "0 error(s), 3 warning(s)":
the fixture's storyboard shows pictures that none of its lines has.

## 9. Findings and one thing for another worker

- **The default `floor` of a spotlight is what blackens the screen.** `HI-01`'s `floor` default is `style/gae/style.json` `spotlight.surround_floor_benchmark_final` = 0.2 (`X-HI-01`'s `surround_floor` takes
  the same number). A spotlight that the agent adds without writing a `floor` gets it, and on a typical dark painting that is a mean luma around 23 to 31: the fake draft of the draft tests (a `HI-01` with
  default parameters on the fixture picture) is sent back twice by the new repair loop for exactly that (`test_a_clean_draft_is_not_sent_back_and_a_default_spotlight_is`). The briefings now say "0.6 or more" and the
  check says what to do, but the cause is one number in a file that is not on my list: **Needs another worker (or the owner's decision): `style/gae/style.json` `spotlight.surround_floor_benchmark_final`
  0.2 to about 0.6 (the coordinator kept 0.6 on the two spotlights that stayed), after which a plain default spotlight passes `highlight_too_dark` on most pictures.** (The measured reference 0.15 to 0.25 is
  "estimated by eye" in the style file.)
- The chapter marks and the channel-name beat are the identity applier's (`bti/identity/apply.py`): they copy the neighbours' camera poses, so they are as small as the neighbours. Nothing to change there if the
  neighbours fill the screen (rule 13 says so).
- The page has no box for the owner's note (section 5).

## 10. What only a real draft by a model can show

- Whether the new rules make a model write fewer shots on the small painting: the rules and the repair loop are tested with fake agents only (the loop is tested by a fake that writes a placeholder
  caption: three prompts, the second naming the code).
- Whether a model that is told to keep `zoom >= 0.6 x 1920 / W` also gets the chapter marks right (they follow their neighbours: the compiler's behaviour is unchanged).
- How often `text_not_in_narration` raises on a draft that is right (a reading or a label worded a little differently); the limits (a quarter of a sentence, the picture's own words) are from one real run.
- The time the extra repair turn costs a real agent (one more model turn, only when a look is raised).
- Whether 5% / 6% and 32 / 0.75 are the owner's numbers: they come from one video.

## 11. Test summary lines (exactly as printed)

On the server, snapshot `fixdraft` (`BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_test.sh fixdraft -- <folder> -q`, one folder per run, never `-m slow`), after the last code change:

```
tests/draft                          438 passed, 1 warning in 154.15s (0:02:34)
tests/engine -m "not slow"           615 passed, 14 skipped, 164 deselected in 318.05s (0:05:18)
tests/deep   -m "not timing"         231 passed, 4 skipped, 1 deselected, 1 warning in 274.54s (0:04:34)
tests/state                          295 passed, 1 warning in 164.10s (0:02:44)
tests/auto                           198 passed, 1 warning in 68.33s (0:01:08)
tests/ops                            473 passed, 1 warning in 97.05s (0:01:37)
tests/editor                         488 passed, 1 warning in 239.00s (0:03:59)
tests/cli                            127 passed, 1 warning in 39.45s
```

On the Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs`: `ℹ tests 455`, `ℹ pass 454`, `ℹ fail 0`, `ℹ skipped 1`
(the one skipped needs `.venv/bin/python`); `node --check` of `errmsg.js` and `labels.js`: ok.

The first full pass (before the last fixes) had 8 failures, all in tests or documents, none in behaviour: `tests/draft` 4 (the "other pictures" assertion of `test_box_briefing.py`, which my filter
rightly changes; my own `test_fixdraft.py`: a `}}` in the JSON example of the task, a wrong guess about the fake's prompt type, and the finding of section 9), `tests/auto/test_loop.py` (the lists' codes are
searched in `storyboard.py` and `registry.py` only), `tests/ops` (my test put a picture without the region its overlay needs), `tests/cli` 2 (a word with an underscore in a code tick of `SKILL.md`; the worked
session of that document prints 3 warnings now). Each was fixed and the whole folder run again; the lines above are those runs. `tests/engine` alone ran 614 passed on the first pass (the one failure it showed before
that, `test_map.py`, was the new check meeting a fixture whose map is the first shot).

Not run: `-m slow` and `-m timing` (forbidden by the brief), and no real model, no render, no network.
