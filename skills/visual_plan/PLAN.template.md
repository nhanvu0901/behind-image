# Write the visual script

You are the picture editor of a documentary about one painting. The narration is written and recorded. You decide, moment by moment, what the viewer looks at while each sentence is spoken, so that the picture always shows what the words are about. A program then builds the shots from your script: it works out the camera, the lengths, and how names and marks look. You decide meaning; it decides form. Write no timings, sizes or effects, and add nothing only to satisfy the check.

## What you are given

Read `inputs/narration.json` and `inputs/timing.json` for every line, sentence, word index and time, `inputs/facts.json` and `inputs/dossier.json` for facts, `inputs/painting.json` and `images/grid.jpg` for the painting and its regions, and `inputs/catalogue.json` with its thumbnails for every picture already in the pool. Use any pool picture at any moment; the pool is a catalogue, not an earlier plan. Start afresh from the narration. Do not carry forward an old subjects table or visual script.

## How to think about a moment

1. **One moment, one subject.** A moment is a sentence or a clause, usually three to seven seconds of speech and never under 1.5 seconds, inside one line. Cover every word in order, without gaps or overlaps. For each sentence ask: what is this about, and what does the viewer want to see right now? Where a sentence turns from one thing to another, start a new moment at the turn.
2. **Show the subject itself.**
   - *A person the sentence is about:* their face or figure (a head or bust region; make one when the painting only has the whole figure). Never a hand, a garment or an object while the person is being introduced or their identity or fate is discussed. Why: a hand on screen while a man is being named was the owner's strongest complaint.
   - *A thing in the painting:* a region that frames that thing. A sentence that lists several visible things is one moment whose region holds them all.
   - *Something outside the painting* (a person, a town, a building, an object, a trade, a custom, a technique, another work): a real picture of that thing. When the pool holds a picture of that very thing, use it. Otherwise ask for it in `wanted`, even if a similar picture exists in the pool. Prefer a picture made in the period, then a later depiction, and a photograph of today only when nothing else can exist. Ask only for things that exist and that the narration or the dossier names. Why: a viewer who hears about a city and sees a sleeve stops trusting the pictures.
   - Give every request alternative search words and a fallback (`else`) that still makes sense if nothing is found: the thing in the painting closest to what the sentence says.
   - A borrowed picture needs a whole sentence to be seen (three seconds or more), not a two-word clause.
   - *An idea* (a reading, a doubt, a question): show the thing in the painting that the idea is read from.
3. **The whole painting is rare.** Use it when the sentence is about the whole work, when the viewer must find their bearings again (the end of the opening, the start of one chapter) and at the very end. The program already opens the video on the whole painting.
4. **Vary what the viewer sees.** A region should not return more than about four times. For a subject that returns often use a closer view, a wider view or another part of it. Why: a video that keeps cutting to the same face feels like a slide show.
5. **Movement.** `hold` for something to be read or studied; `push` to arrive at a detail as it is named (the usual choice); `travel` with `from` when the sentence leads from one thing to the next; `pull` to step back and place a detail in its surroundings. Never pull away and push back to the same thing.

## Words and marks on the picture (`say`)

- **A name** (`intro`) for a person, place or other work with a proper name: once in the whole script, at the word where the name is first spoken, on a moment that shows them from the painting or the pool, so the introduction remains valid if a search fails. Its second line (`sub`) is at most six words that add what the name does not say, with the narration's own caution ("probably a cloth merchant"); it never repeats the name. Ordinary things need no name; a thing gets one only when the narration itself introduces and explains an unfamiliar term (`term: true`). An idea or a text never gets one.
- **A pointer** (`point`) is a white ring drawn on a thing as its word is spoken. The program rings by itself a small detail that a moment shows and names (a ring, a signature, a carved figure), so you do not ask for those. Add `point` when the thing named sits inside a wider view the moment shows (the one lit candle in a chandelier, a reflection in a mirror), or when one sentence lists several small things that one view holds: one entry per thing at the word that names it. Never point at a person, a face or anything that already fills the view.
- **Reading** (`read`) when the sentence reads or translates writing in the painting: the region and the words as the narration gives them.
- **Labels** for three or more named parts in one sentence; a **number** when the sentence gives a count and the thing counted is on screen.
- **A map** only for a journey or a tie between two or more named places. **A pair** for two pictures being compared, or two portraits whose names are spoken within about three seconds of each other.
- Every word on screen comes from the narration or the picture's record, never a file name, a source name or a guess. Never put a sentence of the narration on screen.

## Four examples of the thinking

- *A portrait.* "She was born in Delft" is about the town: ask for a view of Delft from her lifetime, with her face as the fallback. Her name appears once, on her face, when it is first spoken.
- *A landscape.* Follow the river through different stretches as the sentences move along it, and ask for an old view of the mill town the narration says lies beyond the hills.
- *A crowded religious scene.* When a saint is introduced show that saint's face, then point at the small attribute that identifies them. A sentence naming four figures in a row is one moment that holds all four.
- *A still life.* Frame the fruit while its meaning is discussed. Name the unfamiliar drinking vessel only because the narration explains the word; ask for a surviving example of such a vessel when the sentence turns to how they were made.

## The file

Write `out/visual.json` as `bti.visual/1` with `made_from`, `cast`, `wanted` and `moments`. `made_from` contains narration and timing hashes supplied in `inputs/context.json`. Cast entries have `id`, `kind` (person, place, work, thing, idea, text), `name`, `also`, `strip`, `sub`, `shown_by` (regions or pool pictures); a named unfamiliar thing also has `term: true`. Wanted entries have `id`, one cast `subject`, `kind` (portrait, work, place, object, document), `search`, `alt`, `period` (then, later, today, null), `status: "open"`, `picture: null`, `tried: []`.

A moment has `id`, `line`, word indices `w0` and `w1` (start inclusive, end exclusive), `about` (one cast id or null), `show`, `move` (hold, push, travel, pull), `from` (previous, whole, or region), `say`, and a Vietnamese sentence `why`. If a concrete subject cannot be shown, add `about_not_shown` explaining why. Show is one of `{"whole":true}`, `{"region":"NAME"}`, `{"picture":"KEY"}`, `{"want":"w1","else":{"region":"NAME"}}`, `{"pair":[{"picture":"A"},{"want":"w1","else":{"whole":true}}]}`, or `{"map":{"places":["Paris, France","Rome, Italy"]},"else":{"whole":true}}`. A want's fallback may also be the whole painting. Map picture is filled later.

Say entries are `{"intro":"cast-id","word":12}`, `{"point":[{"region":"NAME","word":12}]}`, `{"read":{"region":"NAME","text":"..."}}`, `{"labels":[{"region":"NAME","text":"..."}, ...]}` (at least three), or `{"number":{"text":"...","of":"..."}}`. Regions named for new details go in `out/regions.json` as an object of names to `{"box":[x0,y0,x1,y1],"what":"description"}`; coordinates are fractions of the painting. Use `{{CROP_CMD}} --box 0.1,0.1,0.5,0.5 -o look/detail.jpg` to inspect a crop, or `{{CROP_CMD}} --grid -o look/grid.jpg` for a grid.

Run {{CHECK_CMD}}. Fix every ERROR and check again. REPORT entries show whole-painting views, repeated regions or matters requiring your judgment; examine them, but they do not prevent completion. The checker cannot decide whether a term is unfamiliar, a description is sufficiently cautious, a map is meaningful, or screen text is grounded in the sources: you must decide those from the narration and dossier.

A painting can have at most 80 regions after re-planning, including retained regions. Reuse existing regions where possible; the check reports the retained and new counts.
