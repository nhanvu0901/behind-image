# The unified pipeline: one visual script, a composer in code (design, 2026-11-27)

Approved by the owner on 2026-11-27 ("gop", the merged option). This document is the contract every worker of the
refactor reads. Where it says MUST it is not a suggestion. Where it leaves a number open it says so.

## 1. Why (evidence gathered on 2026-11-26, project `arnolfini-v3`)

- The same decision had several authorities. Example "a name on the screen": the draft model's rule 15, the compiler's
  generated strips, a filter deleting the model's strips, five checks, and the viewer review's repairs. When two
  disagreed the output silently lost something. In the last draft the model wrote 17 marks and the compiler turned
  them into 63 (rings 6 to 29, spotlights 3 to 19, strips 2 to 8).
- The draft model's own notes (`proposals/*.json` field `notes`) said so in every run: it framed shots badly on
  purpose to stop the compiler adding a strip that another check would reject; it drew a ring to silence a check.
- Draft time went from 13 and 16 minutes (11-20, 11-21) to the 30-minute limit (11-22, 11-23, 11-26).
- Two model steps decided "what is on screen" in two documents with two units (59 lines, 117 shots). A re-run of the
  picture step lost pictures: lines with a borrowed picture went 13, 8, 8, 6, 5, 3, because a line cannot name a
  picture the project already has unless it shows nothing else.
- 3,877 unit tests pass; none looks at a picture. Every new rule first met real data when the owner watched.

## 2. Principles

1. **One authority per decision.** A model decides MEANING: what a moment is about, which picture shows it, what the
   viewer should be pointed at. Code decides FORM: lengths, camera path, kind and size of marks, text style and time.
   Neither rewrites the other's work.
2. **One document.** The visual script (`visual.json`) replaces the subjects table, the per-line picks and the draft
   specs. The storyboard is DERIVED from it by code.
3. **Right by construction.** The composer guarantees its own constraints, so there are no checks for a model to
   silence. What it had to bend it writes as a note for the owner.
4. **A re-run loses nothing.** Pictures found once stay in the project's pool and any moment may use any of them.
5. **The video is the test.** Every compose makes a scorecard and contact sheets; nothing is delivered without them.

## 3. The steps

| step | who decides | what happens |
|---|---|---|
| 1 to 3 | as today | painting and sources, outline, narration, title, voice |
| 4a visual script | a model, one session | writes cast, wanted pictures and moments (section 4) |
| 4b search | code | searches once per wanted picture, free sources then the web round; results go to the pool |
| 4c choose | a model, short session | picks among candidates, writes each picture's caption and whom it shows; a wanted picture nobody found is recorded with every wording tried |
| gate `picks` | owner (or the automatic run) | sees the script line by line with thumbnails |
| 5a compose | code, seconds | visual script + timing + style -> storyboard (section 5) |
| 5b viewer review | a model looking at contact sheets | findings are fixed by editing MOMENTS (and by a targeted search when a picture is missing), then composing again; two rounds at most |
| 5c owner | owner | the request box edits the visual script; hand edits of shots stay possible and lock the shot |
| music, export | as today | with the mix of section 7 and the scorecard of section 6 |

## 4. The documents

### 4.1 The picture pool
The pool is `picks.json` `assets` (as today) with, per picture that is not the main painting: `caption` (plain English,
at most 60 characters, written by the choose session; rules of `docs/qa/FIX_written_captions.md`), `shows` (list of
cast ids the picture shows), `period` (`"then"`, `"later"`, `"today"` or null). A re-plan NEVER removes a picture from
the pool; a picture no moment uses is simply unused.

### 4.2 `visual.json` (schema `bti.visual/1`)
```
{ "schema": "bti.visual/1",
  "made_from": {"narration": "<hash>", "timing": "<hash>"},
  "cast": [ {"id": "giovanni", "kind": "person|place|work|thing|idea|text", "name": "Giovanni Arnolfini",
             "also": ["Giovanni"], "strip": true, "sub": "probably a merchant from Lucca",
             "shown_by": [{"region": "MAN_HEAD"}, {"region": "MAN_FIGURE"}, {"picture": "<asset key>"}]} ],
  "wanted": [ {"id": "w1", "subject": "bruges", "kind": "portrait|work|place|object|document", "search": "...",
               "alt": ["..."], "period": "then", "status": "open|found|none", "picture": "<asset key>|null",
               "tried": ["..."]} ],
  "moments": [ {"id": "m0001", "line": "b0130", "w0": 0, "w1": 12, "about": "giovanni|null",
                "show": <SHOW>, "move": "hold|push|travel|pull", "from": "previous|whole|<REGION>",
                "say": [<INTENT>, ...], "why": "one Vietnamese sentence for the owner"} ] }
SHOW    = {"whole": true} | {"region": "NAME"} | {"picture": "<asset key>"}
        | {"want": "w1", "else": {"region": "NAME"} | {"whole": true}}
        | {"pair": [{"picture": "a"}, {"picture": "b"}]} | {"map": {"places": ["Lucca, Italy", "Bruges, Belgium"]}}
INTENT  = {"intro": "<cast id>", "word": <index>}            a name strip at that spoken word
        | {"point": [{"region": "NAME", "word": <index>}]}   one entry: a small thing; several: a list
        | {"read": {"region": "NAME", "text": "..."}}        an inscription and what it says
        | {"labels": [{"region": "NAME", "text": "..."}]}    three or more named parts
        | {"number": {"text": "2,000", "of": "..."}}
```
Validity (checked when the model writes it, with messages a model can act on; nothing is silently dropped):
- V1 moments cover every word of the narration once, in order; `[w0, w1)` lies inside its `line`.
- V2 a moment is at least 1.5 s of speech; the usual moment is one sentence or clause (3 to 7 s).
- V3 `about` is one cast id or null; when it is a person, place, work or thing, `show` MUST be one of that cast
  member's `shown_by` (or a `want`/`pair`/`map` for it), or the moment says `"about_not_shown": "<reason>"`.
- V4 `{"want"}` names an entry of `wanted`; every `wanted` entry has one `subject`; after the choose session a `want`
  whose status is `none` resolves to its `else`.
- V5 `intro` appears at most once per cast member in the whole script, on a moment whose `show` shows that member;
  `word` is where the name (or an `also`) is spoken. The planner writes it; the composer never invents one.
- V6 `strip` is true for a person, place or other work with a proper name, and for a thing ONLY when the narration
  uses an unfamiliar term for it and explains it (owner, 2026-11-27: "weird word must have"); never for an idea or text.
- V7 `sub` is at most 6 words, does not contain the name or an `also`, never claims more certainty than the narration.
- V8 `point` regions lie inside the moment's frame (the composer frames the union for a list); never a person.
- V9 `whole` is for a moment that is about the whole painting, the end of the cold open, one chapter opening, the last
  moment. The scorecard counts it.
- V10 the same region as `show` on more than four moments is reported to the planner (use a closer or wider region of
  the same thing, or another thing of the sentence).
- V11 `map` only for a journey or a tie between two or more named places; `pair` for two pictures compared or two
  portraits whose names are spoken within 3 s of each other.
- V12 text on screen (`sub`, `read.text`, `labels`) comes from the narration or the picture's record; never a file
  name, a source name or a guess.

### 4.2a What the validator proves and what stays a judgment (added after the first worker's report, 2026-11-27)
The validator (`bti/visual/validate.py`) proves the mechanical part of each rule and says so; the rest is the
planner's judgment, examined by the viewer review, never "proved" by matching text.
- V1: a moment lies inside one line; a picture that runs over two lines is two moments with the same `show` (the
  composer joins neighbours that show the same thing, rule C1).
- V6: a thing with `strip: true` MUST carry `"term": true` on its cast entry (the planner's statement that the
  narration uses an unfamiliar word for it); an idea or a text with `strip: true` is refused. Whether the word really
  is unfamiliar is judgment.
- V7: at most 6 words and no name or `also` inside: proved. "No more certainty than the narration": judgment.
- V8: a `point` region exists on the main painting and is not a `shown_by` region of a cast member of kind person:
  proved. Whether it lies in the frame is not the planner's concern: the composer frames the union of a list's targets.
- V9, V10: counted and reported with the moments; not refused.
- V11: a `map` has two or more places and a `pair` two pictures of the pool (or wants): proved. "A journey" is judgment.
- V12: a text that equals an asset key, a file name, a pattern such as `DSC04385` or "image 872", or a bare domain is
  refused; where the words come from is judgment.
- **A map is resolved by the search step, like a wanted picture.** The planner writes `{"map": {"places": [...]},
  "else": <region or whole>}`; step 4b resolves the places to a map record of the pool exactly as the present picture
  job does for a map (the OpenStreetMap import, with its coordinates) and writes its key into the script:
  `{"map": {"places": [...], "picture": "<pool key>"}, "else": ...}`. The composer draws MAP-01 from that pool
  record. A map with no `picture` (not resolved) is shown as its `else`, with a note. Nothing guesses a coordinate.
- `map` and `pair` are forms of SHOW, not intents. A SHOW is never "unknown": the planner always decides; the
  converter of old projects writes `{"whole": true}` with a `why` that says the region was not recorded.

### 4.3 The storyboard
`storyboard.json` keeps its schema. A composed storyboard carries `made_from` (hashes of the visual script, the timing
and the style) and each composed shot its `moment`. A shot the owner edited by hand is `locked` and survives a
re-compose (as today).

## 5. The composer (`bti/compose/`): the only place where form is decided

Constants live in ONE table (the style's `compose` block); checks and the scorecard read the same table.
- C1 **Shots.** One shot per moment. Floor 2.5 s; a moment under the floor joins the neighbour that shows the same
  picture, else the previous one. A borrowed picture or map is on screen at least 3.0 s: it starts at the first word
  of its sentence, then takes time from the shot before while that keeps the floor, then from the shot after.
- C2 **Two pictures that cannot both have 3 s in one sentence** become one `pair` shot (both pictures side by side for
  the whole sentence, each with its strip). A picture is dropped only when nothing else works, with a note.
- C3 **Camera.** Computed from the region as today (`bti/draft/camera.py`), with: a region taller than the frame at
  width-filling zoom is travelled top to bottom (or held on its head end when the moment is short) instead of fitted
  as the small whole painting; the whole painting is shown only for `{"whole": true}`; chapter marks and the ident take
  a filling frame, never a half-way pose; two neighbouring shots on the same region keep the frame.
- C4 **Name strips** (X-ANN-01) only from `intro`: start at `word`, each line fully visible at least 1.5 s plus 0.3 s
  per word over three up to 4 s, about 3 s on the main painting, to the end of the shot on a borrowed picture.
- C5 **Captions** (X-ANN-02) under every borrowed picture from the pool's `caption`, for as long as the picture is on
  screen, unless that shot carries an intro strip. No caption in the pool: none shown, one note.
- C6 **Marks.** A white ring (AN-01) points at small `point` targets; a moment about a thing or inscription also rings its own shown region when its held-frame height is at most 45% of the frame. Other points retain the side and area limits in the compose table. Never mark a person's own named region or a target whose area overlaps a person's head, face or bust region by more than half. Figure and couple bounds do not by themselves identify an object as a person. Start at the target's spoken word, or the first word of the cast name or alias for a shown thing, falling back to the moment's first word. It lasts up to three seconds or the sentence end. Each region is ringed at most twice per video; the scorecard judges marks per minute. Radius stays between 1.2% of frame width and 15% of frame height; a larger shown object gets a maximum-size ring on its centre. The engine retains spotlight for hand edits.
- C7 **Devices** only from their intent: `read` DOC-01, `labels` KEY-01, `number` NUM-01, `map` MAP-01, `pair` LAY-01.
- C8 **Notes, not warnings.** Everything the composer had to bend (a moment joined, a picture shortened, a mark left
  out) is a `compose_note` with the moment id, shown to the owner and to the viewer review. The composer never fails
  on valid input and never loops.

## 6. The scorecard (`bti/scorecard/`)

Made after every compose and again after the export; shown on the page; kept in `output/<key>/`. With contact sheets
(one numbered frame per shot at the moment its marks are visible). First metrics and targets (open to tuning):
whole painting small between bars (share of time, target at most 6%); marks per minute; biggest mark against the
frame (target none over 30% of the frame height); marks on a person (0); name strips (count, any `sub` repeating the
name: 0, any strip on an ordinary thing: 0); borrowed pictures (count, seconds, longest stretch without one, any under
3 s: 0); shots under 2.5 s that are not program shots (0); the five most repeated regions; moments whose subject is
not shown (count and list); after export: programme loudness and the level of the music against the voice in pauses
and under speech. The golden set is `arnolfini-v3`, `eligius` and, once it has a narration and a voice, `rugen`.

## 7. Music
A cue's level is RELATIVE TO THE VOICE: the mix measures the voice and every recording, and puts a bed about 20 LU
under the voice, a swell or ident about 8 LU under it, an ending about 12 LU under it (the model may ask a step softer
or stronger); the music must be audible in every pause where a cue runs. Details in the worker's brief.

## 8. What goes away once the visual path wins on the scorecard
The draft agent for full drafts and its 23 rules, `inputs/techniques.md` for a model, `_subject_overlays`,
`ensure_borrowed_duration`, `_borrowed_caption`, the cast list `names`, most of the 27 view checks, the review's
repairs through `draft.edit`. Until then the old path stays behind the project setting `pipeline: "legacy"`.

## 9. Working rules of this refactor
One worker per module. Acceptance on the real data of the golden set, with frames looked at, not only unit tests.
A worker reads the notes a model left before explaining its output. Nothing is deployed while a project job runs.
