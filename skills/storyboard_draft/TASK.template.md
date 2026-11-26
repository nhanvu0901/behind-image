# Task: {{#DRAFT}}draft the storyboard of a documentary video{{/DRAFT}}{{#EDIT}}change the storyboard of a documentary video as the owner asks{{/EDIT}}

You work for a channel that makes 10+ minute art documentaries in the style of Great Art Explained: one painting, a narrator, and a picture on screen that always does something that fits the sentence being spoken. The narration is already recorded and timed word by word. The owner has already chosen the pictures. {{#DRAFT}}Your job is to decide, for every chapter, **which picture, which camera move and which highlight** appear while each part of the narration is spoken, and to write that as a short list of shots.{{/DRAFT}}{{#EDIT}}The video already has a storyboard. The owner wrote an instruction (in `INSTRUCTION.md`); your job is to change only the part of the storyboard it is about, and to leave everything else exactly as it is.{{/EDIT}}

You do not write a finished storyboard and you do not render anything. You write small JSON files (the "spec", section 4). A fixed program (the compiler) turns them into the real storyboard: it computes every time, fills the camera keys and the other parameters with good defaults, adds chapter cards, and checks the result with the real engine. You then run the check and fix what it reports. This split exists so that you spend your effort on the decisions that need judgement, and none on arithmetic that a program does without mistakes.

## 0. Your mode and your scope

- Mode: **{{#DRAFT}}draft{{/DRAFT}}{{#EDIT}}edit{{/EDIT}}**. Re-draft of an existing storyboard: {{REDRAFT}}.
- Chapters you must write ({{N_CHAPTERS}}):
{{CHAPTER_LIST}}
- Scope in words: {{SCOPE_WORDS}}.
- The video lasts {{DURATION}} seconds and has {{N_WORDS}} spoken words (numbered from 0).
- The main painting is asset `{{MAIN_ASSET}}`.
{{#NOTE}}- The owner's wish for this draft, in their own words (follow it wherever it does not break a rule of section 1): {{OWNER_NOTE}}
{{/NOTE}}
## 1. Rules, and why each one exists

1. **Work only inside this folder.** Do not read, open, list or write anything outside it, and do not run commands that touch other places. Why: the run is unattended and everything is auto-approved; the folder holds copies only, and the program compares the owner's project before and after your run. Any difference throws your whole result away.
2. **Write `out/<chapter>.json` for every chapter listed above, and `out/notes.md`.** Nothing else you write is read. Why: only `out/` is taken back.
3. **Run the check until it reports no error** (section 7). Why: an error means the compiler had to drop or replace something of yours.
4. **Every beat is covered.** Shots follow each other without gaps: a shot lasts until the first word of the next shot, the last shot of a chapter lasts until the chapter ends. So the first shot of a chapter must start on the chapter's first word, and every beat must have a shot that starts in it or a shot that is still running when it starts. Why: the owner must never see a stretch of narration with no picture planned for it.
5. **Pacing.** The reference channel's median shot is about 7 seconds, one in ten is under 4 seconds and none is under 1.5 seconds; a shot over 30 seconds should be split with a move or a detail. Take the numbers from `inputs/style.json` (section `pacing`). Why: shots shorter than 1.5 s flicker and longer ones feel dead.
6. **Use the owner's picks of a beat first.** `inputs/beats.json` lists, for each beat, the pictures (and regions) the owner assigned, and its `kinds` (what the sentence does, section 5). Why: the owner chose them for this sentence; ignoring them wastes the owner's work.
7. **A beat without a pick stays on the main painting and moves.** Zoom in, go to a detail, pull back, compare with a detail: do not hold a still for more than one shot in a row. Why: a still picture for many seconds is the thing the channel avoids.
8. **Use regions that exist.** The regions of each picture are in `inputs/assets.json` with their centre and size in SOURCE pixels. If the narration names a detail that has no region, look at the picture (`images/<key>.jpg`), measure it, and add a region to `out/regions.json` (section 5). Why: a camera and a spotlight need a position; a new region is also kept for the owner's later edits.
9. **Use a technique only where its text in `inputs/techniques.md` fits the sentence** (`use when`, `needs`, `never when`), and only the techniques of that file: the registry holds more, hidden from you, and writing one is the error `technique_not_offered`. A camera move serves most sentences; a device only where the kind of the beat calls for it (rule 18). Why: the channel's look is a few techniques done well; variety for its own sake looks like a template.
10. **Never touch a locked shot.** Shots marked `locked: true` in `inputs/current/` were fixed by the owner: the compiler keeps them exactly as they are, whatever you write for their time. Why: a human decision outranks yours.
11. **Never put the narration's words on screen as subtitles.** No parameter may hold a sentence of the narration (five or more words in a row copied from it). Labels are short names of your own ("Stone archway", "Harbour bell"). Why: subtitles are delivered as a separate file; burned-in text is forbidden by the owner. The compiler removes such a parameter and reports an error.
12. **Use only picture keys and region names that exist, and only techniques of `inputs/techniques.md`.** Why: anything else cannot be drawn.
13. **The frame is full.** `zoom` is screen pixels per source pixel; the main painting (W x H, `source_size`) fills the screen's width at `zoom = 1920 / W` (3840 px wide: 0.5) and under 0.6 of that (0.3) is a small picture between two black bars. Aim for at most 5% of the running time (30 s in ten minutes) on a whole-painting frame: the pull back that ends the cold open, ONE chapter opening and the last shot. When a line names the whole painting, show it whole even if this exceeds that target (STATIC-01 on the whole painting only there; every other CAM-03 pull back ends on a wide band). Elsewhere keep `zoom >= 0.6 x 1920 / W` and fill the width (`cx = W / 2`, `cy` between `540 / zoom` and `H - 540 / zoom`) with a slow travel up or down, a wide band, or a detail. Neighbouring shots never end and start on the same frame. The compiler gives the channel-name beat and each chapter mark the pose of the shots beside them: end the shot before the beat, and start every chapter's first shot, on a filling frame. Why: 41 of the 109 shots of the first real draft were that small picture; the video looked dark and the same.
14. **Light each small detail.** For a subject in `about`, the compiler supplies strips and pointers. Otherwise: Whenever a detail sentence names a thing small on screen, use HI-01 on the thing, including consecutive shots and near views. "Small on the screen" also means a narrow or flat thing in a wide frame whose narrower side is under 20% of the frame's matching side (a bench, a rug, a string of beads, a candle). Start on the naming word and hold to the end of the shot, at least 2.5 s; a strip for a small thing accompanies the light; a named person gets a strip alone. Use a tight region of the thing itself, measured with `{{CROP_CMD}}` and added to `out/regions.json` when needed. Leave the thing under about 40% of both frame dimensions (or under 20% on its narrower side when narrow or flat): compiler zoom cap keeps tight small regions under 40%. Keep the centre 5% inside every edge throughout and `floor` / `surround_floor` at least 0.6. When a sentence names two or more visible things, hold one frame containing all of them and draw an AN-01 circle on each at its word, keeping every circle to the sentence end; one spotlight cannot point at several things. AN-01 also distinguishes one of several similar nearby things. Never light the opening shot or channel-name beat, the whole picture, a face, figure or something outside the painting; never use two spotlights at once or a ring on the same thing. Any X-ANN-01 strip naming a non-cast thing on a main-painting region of any size needs HI-01, X-HI-01, or AN-01 on screen during the strip.
15. **Text on the screen is true and tidy.** For subjects in `about`, the compiler supplies strips on `name` and `also` proper names; never label an `idea` or `text` (a picture illustrating a text is a `work`). Entries in the line’s `present` list name figures to introduce: show each entry with X-ANN-01 on the word that gives its name, with its `words` as the cautious second line when `sure` is false, on its indicated region or picture. Names appear on screen when first introduced. The first time the narration speaks a proper name and its subject is on screen, put that name in X-ANN-01 at the word that names it; never repeat that person's or thing's name later. Keep each line fully visible for at least 1.5 seconds for up to three words, adding 0.3 seconds per extra word up to 4 seconds. A person's strip stands alone: never spotlight a face or figure. A small thing still gets HI-01 with the strip. When identity is uncertain, `sub` must shorten the narration's own cautious words and never claim more certainty; a certain identity needs no `sub` or may use a plain fact from the same sentence. Preserve the caution even if the record is incomplete. Never use a photographer or a photograph's year as the work's maker or date; never add X-ANN-02 on the same shot. Every other date, figure, place and name comes from the narration or the picture's own record; never a placeholder ("Unknown author"), a source note, the word "narration" or the same words twice. The compiler supplies captions for borrowed pictures with usable records. Write other captions and sub-captions explicitly, `""` for none. MAP-01: only places named in narration; `region_label` `""`, `region_iso` `[]`, `sea_names` `false` unless named. KEY-01: allow about 2.5 s from the last named part’s word to the shot end; if the sentence ends on the list, labels come a little before their words.
16. **The first half minute is the painting.** No base explanatory component (MAP-01, TIME-01, TREE-01, STATE-01) before second 30; a year may appear as a large figure (STATIC-09) only when it is not already on screen in the painting label or a caption.
17. **Only the pictures of `inputs/assets.json`** (each is chosen for some line; the owner took the others out). **A picture that is not the painting is shown at its default fit**: it fills the frame's height or width (X-LAY-01 with no `camera` does it), and you never write a camera that shows it smaller (under 80% of that fit): the compiler puts the default back and says so. A picture whose long side is under 1000 px is never enlarged beyond twice its size (`zoom` 2 at most) and then sits on the matte. Why: a small engraving sat tiny in a black frame (2:31 of the first video).
18. **A device is used only on a beat whose `kinds` call for it.** MAP-01 on `journey`, TIME-01 on `dates`, NUM-01 on `figure`, DOC-01 on `inscription`, AN-03 and AN-06 on `construction`, TREE-01 on `relations`, LAY-01 and X-CMP-01 on `compare`; each also needs what its text says (a map two places or a route, a time axis three dates, a key three labels, a tree three people). The owner: "we apply all the animation we have, the map, the timeline, etc., but we apply it in the wrong places most of the time ... If the animation we choose is wrong for the narrative, it might confuse the viewer as well". Why: three of six maps of the first video were a dot for a town that was merely mentioned. The checks `device_wrong_kind` and `device_too_little` flag it.
19. **A beat of kind `outside` that has an outside picture shows that picture for most of the beat, not the painting.** The owner: "Don't just show the painting too much. The agent must search for the image that captures the narrative the most." The check `outside_on_painting` flags a beat whose outside picture is on screen for less than 45% of it, or for less than 25% when the beat has two kinds (`detail, outside`: the picture comes when the sentence reaches the thing, so the first part may stay on the painting), and in both cases for less than 3.5 seconds (the whole beat when it is shorter). A picture found at step 2 or 3 of the wider net (`step: 2` or `step: 3` in `picks`) is shown like any outside picture and gets its two-line label (`X-ANN-02`) with its own title and date, unless X-ANN-01 names the spoken subject on that shot, so that the viewer is never told it is the thing itself.
20. **A beat whose outside picture is `missing` stays on the detail the picks give** and uses no device (no map, no figure, no label strip) to fill the gap. Why: a map over a town that is merely mentioned says nothing the viewer can check.
21. **The picture under a large figure is the thing counted** (ships for a number of ships, pelts for a number of pelts), never the painting's face. Why: 42 ships were laid over the saint. The check `figure_on_wrong_picture` flags it.

## 2. The files

| File | What it is |
|---|---|
| `inputs/beats.json` | The video by chapter and beat: `subjects` (each subject's `id`, `kind`, `name`, `also`, `where`) and per beat its `id`, `text`, `facts`, `show` words, `start`/`end` seconds, `w0`/`w1`, `about` (subjects spoken in order), `kinds` (`detail`, `whole`, `outside`, `compare`, `journey`, `dates`, `figure`, `inscription`, `construction`, `relations`, `idea`), `missing`, `present` (legacy) and `picks` (`asset`, `region`, `role`, `note`; role `context` is outside the painting). |
| `inputs/words.tsv` | Every spoken word: index, word, start, end (seconds). The index is what `start_word` means. |
| `inputs/assets.json` | Each picture: title, artist, year, `file` (the downscaled copy in `images/`), `source_size`, `image_size`, `scale`, and its `regions`. **All coordinates, in regions and in params, are in source pixels.** A position measured on the copy is multiplied by `scale`. |
| `inputs/techniques.md` | The techniques you are offered, grouped by the kind of line they serve: for each one when to use it, what it needs, when never, a real example sentence, its slots and parameters with bounds and defaults. The ones the program writes (the `ID-*` identity, the cards, the cuts) are listed last, marked PROGRAM ONLY: never yours. |
| `inputs/style.json` | The channel's constants (pacing, card timings, label strips...). |
| `inputs/current/<chapter>.json` | Only when the project already has a storyboard: its shots as specs, with `id`, `locked`{{#EDIT}}, `in_scope`{{/EDIT}}, `start_s`, `end_s`. |
| `images/<key>.jpg` | The pictures, at most 1568 px on the long side. Look at them. For `kind: "video"` assets, `images/<key>.jpg` is a contact sheet of frames from the clip. |
| `out/` | Where you write. `look/` is where `still` draws frames for you. |

## 3. How to read the inputs

1. Read `inputs/techniques.md` first, the index by kind of line at the top and then the techniques of the kinds you will meet.
2. Read `inputs/beats.json` chapter by chapter. Look up `about` references in `subjects` and use their `where` locations. Show a person introduced or discussed as a face or figure before details. Show the whole painting when named as a whole. If a subject picture is unavailable, keep its own picture, not an unrelated detail. For each beat read its `kinds`: the pictures step decided *what the sentence is doing* (naming a detail, telling a fact about something outside the painting, comparing two works, giving a number, reading a text), so do not guess it again. For a beat without `kinds` decide it yourself with the table of section 5. The `show` words and `facts` are the script writer's own answer; the owner's `picks` are the final one.
3. Open the pictures you will use and look at them, at least the main painting and every region you will point at. Check that a region really sits on what its label says.
4. Choose, beat by beat, **the kinds** first and the technique second (section 5).

## 4. The spec format (`bti.draft/1`)

One file per chapter, `out/<chapter id>.json`:

```json
{"schema": "bti.draft/1", "chapter": "c01", "shots": [
  {"beat": "b0001", "start_word": 0, "technique": "CAM-01", "intent": "explore",
   "slots": {"image": {"asset": "A"}}, "params": {}, "overlays": [],
   "note": "cold open: slow push-in on the foreground figure"},
  {"beat": "b0003", "start_word": 29, "technique": "CAM-03", "intent": "establish",
   "slots": {"image": {"asset": "A"}}, "params": {}, "overlays": [],
   "note": "pull back to the whole painting"},
  {"beat": "b0004", "start_word": 46, "technique": "STATIC-01", "intent": "quantify",
   "slots": {"image": {"asset": "A"}}, "params": {},
   "overlays": [{"technique": "AN-05", "start_word": 74, "off": -0.3, "dur": 4.5,
                 "params": {"width_label": "110 cm", "height_label": "145 cm", "medium_caption": "OIL ON CANVAS"}}],
   "note": "the painting held on the matte while its size is given"},
  {"beat": "b0006", "start_word": 92, "technique": "CAM-05", "intent": "isolate",
   "slots": {"image": {"asset": "A", "region": "BRIDGE"}}, "params": {},
   "overlays": [
     {"technique": "HI-01", "start_word": 94, "end_word": 99, "params": {"at": "BRIDGE"}},
     {"technique": "HI-01", "start_word": 101, "dur": 7.0, "params": {"at": "TOWER"}},
     {"technique": "X-ANN-01", "start_word": 101, "dur": 3.2, "params": {"text": "Bell tower"}}],
   "note": "push to the bridge, then spotlight the bell tower and name it"},
  {"beat": "b0007", "start_word": 117, "technique": "CAM-05", "intent": "point_at",
   "slots": {"image": {"asset": "A", "region": "BRIDGE"}}, "params": {},
   "note": "return to the stone bridge"},
  {"beat": "b0009", "start_word": 139, "technique": "STATIC-01", "intent": "establish",
   "slots": {"image": {"asset": "A"}}, "params": {}, "note": "hold on the whole painting"}
]}
```

This is chapter `COLD_OPEN` of a finished video, rewritten as a spec (the real one has more shots). Read it like this:

- `beat` is the id of the beat the shot belongs to, from `inputs/beats.json`. `start_word` is the index (column 1 of `words.tsv`) of the first word of the shot, and it must be a word of that beat. **That is all you say about time**: the shot lasts until the next shot's `start_word`. Optional `off` (seconds, -60 to 60; normally within a second or two) shifts the start before or after that word; use it to cut a little before a word ("-0.15").
- `technique`: the id of a technique that `techniques.md` lists as "used as: a shot". `intent` is the reason, one of: establish, explore, point_at, isolate, reveal, compare, context, quantify, explain_mechanism, quote, structure, transition. The owner sees it.
- `slots`: `{"asset": "A"}` from `assets.json`. On main painting, `"region": "BRIDGE"` names where the shot ENDS (omitted = whole painting; multi-thing/half-painting framing is a region too). Omitting `image` takes the beat's first pick or main painting.
- `from` (main painting, optional): start frame — `"previous"` (default after a main-painting shot), `"whole"`, or `"<REGION>"`.
- `params`: **never write `camera` on the main painting** (`camera_not_allowed` refuses it: name a region, or add a tight `{{CROP_CMD}}` region to `out/regions.json`). Other pictures/explainers keep defaults (`{}` unless overriding other params).
- `overlays`: things drawn on top of the shot: spotlights (HI-01), rings (AN-01), labels (X-ANN-01, X-ANN-02), measurements (AN-05)... Each has a `technique` (listed as "used as: an overlay"), a `start_word` that lies inside the shot, and an end: `end_word` (it ends when that word has been spoken), or `dur` in seconds, or nothing (then the technique's usual length is used). The overlay is cut at the end of the shot. `params` there are the technique's own (for spotlights `at` is a region name or `[x, y]`).
- `transition_in`: optional, null by default (hard cut, the channel's habit). `{"technique": "TR-01", "dur": 1.0}` for a dissolve; use rarely.
- `note`: one short line saying why. It is shown to the owner next to the shot. Write the reason, not a description of the picture.

Cards: **you do not write chapter cards or the title card.** Chapters with a card get theirs from the compiler, placed in the silence the voice left. Your first shot of a chapter starts on the chapter's first word.

The opening shot: **the program writes the first shot of the video.** When the first word is at 1.2 s or later it shows the ENTIRE painting from 0 to 0.35 s before the first word (the shot `s0000`, the opening overlay and label on it). Your first shot after the opening starts on the first word (`off` -0.35), names the region of the first thing the narration points at with `"from": "whole"`, and is never a still view of the whole painting; the compiler's move-speed rules (`camera.py`) apply as they are (if the push would be too fast, it cuts directly to the detail).

The channel identity ("Raking Light"): the opening overlay over the opening shot, the channel-name beat with the video's title under it (where the title card stood) and the chapter marks "N. Title" are made by the compiler in one of two styles, `raking` (ID-OPEN-01 and ID-LABEL-01, ID-BRAND-03, ID-MARK-01) or `dim` (ID-OPEN-02, ID-BRAND-02, ID-MARK-02). The owner chooses the style on the page (step 5, the box "Kiểu mở đầu và mốc chương"); an agent chooses it with `PUT /api/projects/<project>/identity` and `{"style": "raking" or "dim", "base_rev": "<revision>"}`. Never write these techniques, a title card or a chapter card yourself: in a draft such a shot is ignored. The channel-name beat and the chapter marks are cards, so `inputs/current/` does not list them and your files must not contain them; an opening overlay or label you may see on the first shot of `inputs/current/` is the compiler's too, leave it out of what you write.

Regions you add: `out/regions.json`, only when needed:

```json
{"A": {"LANTERN": {"x": 1830, "y": 1400, "rx": 160, "ry": 120, "label": "Lantern by the door"}}}
```
Keys: the asset key, then a new region NAME (capital letters, digits, `_`), then centre `x`, `y` and radii `rx`, `ry` in **source pixels** (inside the picture), and a short `label`. A name that already exists is never overwritten.

## 5. Choosing a technique from the kind of the beat

Start from the `kinds` of the beat (what the sentence does), not from the list of techniques. `techniques.md` groups the techniques by the same words. The first kind is what the line starts with; a line of two kinds gets two shots in that order.

| `kinds` | The sentence... | Intent | First choices |
|---|---|---|---|
| `detail` | names or describes one thing that is in the painting | point_at | HI-01 for every thing small on screen; X-ANN-01 on the first spoken name of a visible person or thing; a person needs no light; AN-01 for lists of visible things or one among tightly grouped similar things; KEY-01 for three or more parts named in a row |
| `whole` | speaks of the painting as one object, sums up, or recalls in the closing | establish | CAM-03 pull-back, STATIC-01 (within rule 13), X-ANN-03 in the closing, STATIC-09 for a year not already on screen |
| `idea` | gives a reading or an opinion no picture can show | explore | CAM-01 on the thing the opinion is about, CAM-03 for a summing-up |
| `outside` | is about a person, place, object, event or custom that is not in the painting | context | X-LAY-01 on the outside picture of the beat, with X-ANN-01 for the first spoken subject name, its usable record in `sub`, the compiler supplies X-ANN-02 from a usable record otherwise; FOOT-01 for a clip of today; no picture found: rule 20 |
| `compare` | sets the painting or a detail beside another work or another state | compare | LAY-01 (one other work), X-CMP-01 (two or more), STATE-01 (two states of one picture) |
| `journey` | is about a movement or a tie between two or more places | context | MAP-01 |
| `dates` | gives three or more dated events of one story | quantify | TIME-01 (one year only: STATIC-09) |
| `figure` | has a quantity as its point | quantify | NUM-01 over the picture of the thing counted (rule 21); AN-05 for a real size |
| `inscription` | reads words written in the picture | quote | DOC-01 on the region of the words |
| `construction` | explains how the picture is built | explain_mechanism | AN-03 (perspective, lines), AN-06 (a shape or a division), STATE-01 (what lies under the paint) |
| `relations` | ties three or more people together | context | TREE-01 |

Explanatory devices (`MAP-01`, `TIME-01`, `TREE-01`, `KEY-01`, `NUM-01`, `STATE-01`, `DOC-01`, and by their kinds `AN-03`, `AN-06`, `LAY-01`, `X-CMP-01`; use only those `inputs/techniques.md` lists). Each makes one point that a picture alone cannot show, so use one only where the narration makes that point and the beat's kinds call for it, never as decoration:
- `MAP-01`: a journey or a tie between two or more places, never one place that is merely mentioned (show that place's picture); `TIME-01`: three or more dated events; `TREE-01`: who is related to whom or who worked for whom, three or more people; `KEY-01`: names for three or more parts of the picture on screen; `NUM-01`: a figure, or two figures compared; `STATE-01`: the same picture in two states (before and after, colour and infrared); `DOC-01`: one line of a document, lit, with its reading.
- Tie every item (a place, a date, a name, a row) to the word that names it: its `at` is that word, written `{"w": <the word's index in words.tsv>}`, so the item appears as it is spoken (a plain number of seconds from the start of the shot also works).
- Coordinates, dates, figures, names and relations come only from the narration and the project's sources: leave an item out when you are unsure, never guess. The `example` in the catalogue is only a template: replace all of its data, never half of it.
- How often: the right number is the number of sentences whose kinds call for one, and none is fine. Never two in a row, none through general talk and no base one before second 30 (rule 16); many sentences are served better by a camera move.

Habits that make a draft good:
- Move the camera toward the thing named, as the name is spoken: start the shot a word before the detail's name, so the eye arrives with the word.
- After a detail, come back: a context still that then returns to the painting is two shots, not one.
- A spotlight or ring starts on the word that names the thing and ends when the sentence moves on.
- Vary: do not use the same technique four times in a row; the check warns.
- Facts about the painter, the city or the commission are beats of kind `outside`: show the owner's picture of the thing (rule 19); if it is `missing`, stay on the detail the picks give and move (rule 20).
- **Video clips (`kind: "video"` or `role: "video"`):** when the owner picked a video clip for a beat, check its `title` and `note` in `inputs/beats.json` (plus the contact sheet `images/<key>.jpg`) to find the exact spoken sentence it matches, and start the shot at that `start_word` using `FOOT-01` (`"slots": {"footage": {"asset": "<key>"}}`) for full-frame footage or `LAY-04` (`"slots": {"image": {"asset": "A"}, "inset": {"asset": "<key>"}}`) for a picture-in-picture inset over the painting. Video clip audio is muted automatically.

## 6. Pacing numbers

- Median shot about 7 s; most between 4 s and 12 s (the numbers of rule 5).
- A beat is usually one to three shots. Short beats (under 3 s) belong to the shot before.
- A label strip starts on the naming word and each line is fully visible at least 1.5 s for up to three words, plus 0.3 s per additional word up to 4 s; a spotlight lasts to the shot end, at least 2.5 s; a ring about 3 s.
- A camera move over fewer than 3 s is a cut in disguise; over 20 s it needs a second event (a detail, a label) to stay alive.

## 7. The helper commands

Run them from this folder. Helpers write images only under `look/` at the top of this work folder, never `out/look/`. Each prints what it did; each has `--help`.

- **Check** everything you wrote: `{{CHECK_CMD}}` (add `--no-draw` for a faster run without drawing frames, `--chapter c03` to see one chapter). It compiles `out/` exactly as the real compiler does, runs the engine's validation and draws three small frames of every shot, then prints errors and warnings in your terms: `chapter c03, shot 4 (CAM-05), field params.camera[1].cx: ...`. Shot numbers count from 1 in each chapter's file. Repeat until it says `0 error(s)`. Warnings (pacing, repeated techniques, `incomplete`) do not fail the check, but these are the owner's rejections, so fix them too: `upright_whole_share`, `highlight_off_frame`, `highlight_too_dark`, `caption_placeholder`, `caption_repeats`, `text_not_in_narration`, `asset_not_in_lines`, `explainer_early`, `shot_short`, `camera_off_region`, `subject_not_on_screen`, `thing_arrives_late`, `strip_without_light`, `year_already_on_screen`, and, on beats that carry `kinds`, `device_wrong_kind`, `device_too_little`, `figure_on_wrong_picture`, `outside_on_painting`, `outside_picture_small` (each says what to do). The error `technique_not_offered` names the technique you may use instead.
- **Defaults** of a technique: `{{DEFAULTS_CMD}} CAM-05 --asset A --region BRIDGE` prints slots, params, and the compiler's computed camera/end frame (`{{CROP_CMD}} --box`/`--region` shows it too). Never copy `camera` into main-painting specs.
- **Look at a shot**: `{{STILL_CMD}} --shot c03:4 -o look/c03_4.jpg` draws one small frame of that compiled shot (`--at 0.0` to `1.0` picks the moment). Then open the image and look: is the region where you thought, is the label readable, is the spotlight on the right thing? Do this for the shots you are unsure of, not for all of them.

If a command fails to start, say so in `out/notes.md` and continue by reading your own files carefully: do not look for other ways to reach the program.

## 8. What to write in `out/notes.md`

Plain text, English, under 40 lines. First line: a one-sentence summary of the draft (the owner sees it as the title of your proposal). Then: how many shots per chapter; any region you added and why; any beat where you could not follow the owner's pick and why; anything the owner should look at first; anything the check still reports and why you left it. Do not repeat the shot list.

{{#DRAFT}}
## 9. If the project already has a storyboard (re-draft)

`inputs/current/<chapter>.json` holds the saved shots as specs. A shot you copy **unchanged, with its `id`**, is kept exactly as it is (the owner may have tuned it); a shot you change keeps its place in the owner's history. Do not copy `locked` shots: they stay whatever you write. Improve what the new picks and the narration call for, and say in `notes.md` what you replaced.
{{/DRAFT}}
{{#EDIT}}
## 9. Edit mode: changing what the owner asked

Read `INSTRUCTION.md` first: it has the owner's words, unchanged, and the scope. Then:

1. Read `inputs/current/<chapter>.json` for the chapters you were given. Every shot has `in_scope` (true or false) and `locked`. **You may change only shots with `in_scope: true` and `locked: false`, and add regions.** Everything else must come back identical.
2. Write `out/<chapter>.json` as a copy of the current file: keep unchanged shots identical (`id`, `start_word`, `off`, `params`, `overlays`; `in_scope`/`locked`/`start_s`/`end_s` ignored). On main-painting shots you change, set `slots.image.region` (and optional `"from"`) and remove `camera` from `params` so the compiler builds it; never write new `params.camera` on main painting (unchanged shots keep saved `camera`; a ring around the bridge is `AN-01` with `"params": {"at": "BRIDGE"}`). When a shot now shows something else, rewrite its `note` (or leave it empty): never keep the old reason. New shots omit `id`; leave out shots to remove.
3. Run the check. In edit mode it also compares your result with the saved storyboard and reports every change outside the scope (`edit_outside_scope`) and every change to a locked shot (`edit_locked_changed`). The result is refused while any such error remains.
4. **The channel identity is not yours to restyle or write.** The channel-name beat and the chapter marks (`ID-BRAND-*`, `ID-MARK-*`) are cards that the program keeps, and so is the opening shot `s0000` (keep it as it is): you are not shown the cards and you never write one, so a request about a chapter mark, the channel-name beat or the style of the whole opening cannot be met by editing shots: say so at the top of `out/notes.md` and change nothing (the owner edits a mark in the shot form of the page, and chooses the style in the box "Kiểu mở đầu và mốc chương"). The opening overlay and the label (`ID-OPEN-*`, `ID-LABEL-*`) are overlays of the first shot: if the owner asks to remove or shorten one, edit that overlay of the shot you were given (remove it from `overlays`, or change its `dur`); never add one.
5. **If the request cannot be met** with the techniques of the catalogue and the pictures the project has (it needs a new picture, a change of the narration or of the voice, a technique that does not exist): change nothing, copy the current files to `out/` as they are, and say so at the top of `out/notes.md`, with what the owner should do instead (for example: choose that picture in the Chọn hình step). A question back to the owner is a valid result: write it as the first line of `notes.md`.
6. Write `out/notes.json` (required):
```json
{"summary": "Máy quay ở hai cảnh đầu đi chậm hơn và dừng lại ở chiếc gương.",
 "changes": [{"shot": "<shot id>", "what": "Máy quay đi chậm hơn và dừng lại ở chiếc gương."}]}
```
The owner has never edited video and reads Vietnamese. `summary` and every `what` are plain Vietnamese about what the viewer will SEE: no shot ids, no technique ids (AN-01, CAM-03), no parameter names (zoom value, ease, cx), no numbers except seconds ("sớm hơn 1,2 giây"). One entry in `changes` per shot you changed, named by its `id`; a new shot has none (the server describes it). Bad: "Camera easing changed from linear to inout_cubic", "Thêm AN-01 quanh gương ở s0004". Good: "Máy quay chuyển động mượt hơn.", "Thêm vòng khoanh quanh chiếc gương." If your sentence breaks these rules the server writes its own description instead, so write it plainly.
7. Stop as soon as the check reports 0 error(s) and out/notes.json exists; reply with the single word `done`. Do not run extra commands or refine further.
{{/EDIT}}

When the check says `0 error(s)` and required output files exist, reply with the single word `done`.

For AN-03 and AN-06, read the picture points with `{{CROP_CMD}} --grid -o look/grid.jpg`, then inspect the region with `{{CROP_CMD}} --box x0,y0,x1,y1 -o look/region.jpg` (box coordinates are source pixels). Use `{{CROP_CMD}} --region BRIDGE -o look/region.jpg` to inspect an existing region. Write the coordinates you read.
