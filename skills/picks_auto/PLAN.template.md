# Task: plan what is on screen for each line of the narration of a documentary video

You work for a channel that makes ten-minute art documentaries in the style of Great Art Explained: one painting, a narrator, and a picture on screen that always fits the sentence being spoken. The narration is written and approved, and it is cut into **lines** (a line is one short paragraph of narration). Someone now has to decide, for each line, **what the line does and what is on screen while it is spoken**: a detail of the main painting, the whole painting, another picture that gives context (a portrait of the painter, a related work, a view of a place, an object, a page of a document), a map, or, rarely, a short clip. That someone is you, for the {{N_TARGETS}} lines marked `target: true`. The owner will look at your proposal on a page and correct it, so make it sensible on a first look.

The owner's rule, in his own words: **"Don't just show the painting too much. Find the image that captures the narrative the most, in a way that the viewer can understand."** When the narrator talks about the guild rules, a king, a harbour or a battle, those things are not in the painting, and the viewer must see a real picture of them. When the narrator talks about a place, show a simple picture of the place, not a map.

You do not search for the pictures and you do not choose among them: a program searches the picture sources for what you ask (the free ones, and the web), and a second short session of yours looks at what it found and chooses. Your job now is the **plan**: one JSON file that says, line by line, what the line does and what should be on screen, with a box for every detail of the main painting you want to show. A program turns your plan into the real picks, and checks it first. You run the check and fix what it reports.

## 0. Your task in numbers

- The painting: **{{TITLE}}** by {{ARTIST}}, {{YEAR}}. It is the **main painting**; its picture is `images/main.jpg`.
- The narration has {{N_LINES}} lines in {{N_CHAPTERS}} chapters; **your lines** ({{N_TARGETS}}): {{TARGET_LIST}}.
- You have at most **{{MAX_STEPS}} steps** (every command you run and every file you open is a step) and **{{MAX_MINUTES}} minutes**. A session that goes over is stopped, and then only a file that already passes the check is kept. Plan your steps: read the inputs (about 4 steps), look at the painting and its grid (2), check a few rough boxes with a crop if unsure of where a detail sits, write `out/plan.json` (1), run the check (1 or 2).
{{#OWNER_NOTE}}
- **The owner's request for these lines**, in their own words (follow it, within the rules below): {{OWNER_NOTE}}
{{/OWNER_NOTE}}

## 1. Rules, and why each one exists

1. **Work only inside this folder.** Do not read, open, list or write anything outside it, and do not run commands that touch other places. Why: the run is unattended; the folder holds copies only, and the program compares the owner's project before and after your run. Any difference throws your whole result away.
2. **Write `out/plan.json`, and nothing else matters.** Only that file is read back. Why: the program takes only `out/` back.
3. **Run `{{CHECK_CMD}}` until it prints `0 error(s)`.** Why: an error means the program cannot use your file. You get one repair message if you forget; after that the job stops and the owner sees that the agent failed.
4. **Every one of your lines has exactly one entry in `lines`, with its `kinds`.** A line whose picture before it is still the right one gets `"show": []` (including an outside line that reuses a subject already shown; see section 5). Why: the owner must never see a line the agent forgot, and the next step reads `kinds` to know what each line is for.
5. **Use only what the narration and the facts say.** Names of people, works, places and dates in your search words must come from the line, the dossier (`inputs/dossier.json`) or the facts (`inputs/facts.json`). Do not invent a work, a person or a place, and do not ask for a picture of something you are not sure exists. Why: a made-up want finds a wrong picture, and the owner cannot tell. When a line is vague, show the painting (a detail or the whole) and move on.
6. **Search words are English words a picture search can use** ("Rembrandt self portrait", "Venice canal 18th century", "brass astrolabe 16th century"). The `reason` and the `what` fields are **Vietnamese, with all their accents** (the owner reads them; the check refuses an English reason). Why: the sources are indexed in English, the owner reads Vietnamese.
7. **Boxes are fractions of the painting**, not pixels. Why: the picture you look at is a scaled copy; fractions mean the same on every copy.

## 2. The files

| File | What it is |
|---|---|
| `inputs/narration.json` | The narration by chapter. Each line has `id`, `no` (its number as the owner sees it), `text`, `facts` (ids), `show` (the script writer's hint of what to show, in words), `words`, `seconds` (about how long it is spoken), and `target`. A line that is not a target and has `already` keeps what it has. |
| `inputs/facts.json` | The facts of the dossier, id to sentence. |
| `inputs/dossier.json` | The painting's title, artist, year and the named details of the dossier (`D1`, `D2` ...): good candidates for boxes. |
| `inputs/painting.json` | The main painting: its size, and the **regions it already has** with their `box`. You may use an existing region in a line by its name, without declaring it. |
| `images/main.jpg` | The main painting, scaled down to look at. Open it. |
| `inputs/context.json` | What the check compares your file with. Do not edit. |
| `out/` | Where you write `plan.json`. `look/` is where `{{CROP_CMD}}` writes the crops you look at. |

## 3. How to read the inputs

1. Read `inputs/dossier.json` and `inputs/painting.json`, then open `images/main.jpg` and look at the whole painting. Run `{{CROP_CMD}} --grid -o look/grid.jpg` and open `look/grid.jpg`: it has a grid labelled with fractions, so that you can read positions off it (0.5 is the middle).
2. Read `inputs/narration.json` chapter by chapter. For each of your lines ask: *what is this sentence doing?* Naming a part of the painting, telling a fact about the painter, comparing two works, describing a place or a journey, giving a number, quoting a document, or telling a story that happens elsewhere? The answer is the line's `kinds` (section 5, rule 1).
3. The `show` words of a line are the script writer's own idea of what to show; the dossier's details (`D1` ...) are the parts of this painting that the books talk about. Use them as hints, not as orders.
4. Decide the line, then (for a detail) find its box on the grid and **check it with a crop** (section 6).

## Subjects of the narration

Add a top-level `subjects` list: one entry for every person, thing, place, other work or idea the target narration is about. Use a stable `id` and reuse existing subjects from `inputs/narration.json` when applicable. Each has `id`, `kind` (`person`, `thing`, `place`, `work`, `idea`, `text`), `name` in the narration's terms, optional `also` listing other proper names of the same subject (empty when none), optional `sub` in the narration's own cautious words or a short gloss, `strip` (true for proper names and unfamiliar terms, false for ordinary words), and `where`: `{"region": "FIGURE"}` for a tight one-thing region of the main painting, `{"want": "b0003.1"}` for a requested picture (line id and one-based `show` position), or null when a subject has no picture of its own (including an idea). Each line has `about`: a list in spoken order of `{"id": "...", "words": "exact spoken words"}`; use [] when none. Use `text` for a book, scripture, document or law; neither `text` nor `idea` gets a strip. An illustrating picture is its own `work` subject. A description or pronoun in `about.words` is not an additional name. Do not invent identities or certainty.

Choose pictures for what the sentence is **about**, not every incidental noun. A sentence about a person's identity, actions or fate shows that person's face or figure (or a picture of them); a body part or object mentioned in passing cannot replace them. A sentence about the painting as a whole shows the whole painting. If an outside image is not found, the fallback must be the subject's own picture: for a person or thing in the painting, its own region, never an unrelated detail. Do not reuse a region as the image for unrelated subjects. Draw a tight region around each individual subject, not a group or an accessory.

### Searches follow subjects

A subject visible in the painting gets its own tight `where.region` and no search. For each concrete subject outside the painting, request one primary picture for that subject, once for the whole plan: set `entity` to its subject id, choose the kind from `portrait`, `work`, `place`, `object` or `document`, and point the subject's `where.want` to that request. Other lines about it reuse the chosen picture. If a line explicitly needs a different aspect, request another picture with `aspect` set to the exact words for that aspect in the line. Prefer pictures made in the period; use a modern photograph only when no period picture exists. A map is only for a route or journey. Check that every chosen candidate actually depicts the subject. This subject-first plan avoids spending the search budget on the same person or object again for each line.

For a portrait, a line about the sitter's life uses the sitter's region, not a hand or clothing. In a landscape, the village uses its own region; a distant city named in the story gets one `place` search. In a crowded religious painting, each saint uses their own figure region; a separately named book may get a `document` search. An idea such as a technique, symbol or belief is searched only if a concrete depiction or document exists; otherwise show the concrete painting subject the line discusses.

If no search result is usable, fall back to the nearest concrete subject in this line or the preceding line, such as the person's own face or figure, or the whole painting for a line about the painting. Never substitute an unrelated detail; record the absent subject picture as missing.

## 4. The plan format (`bti.picks.plan/1`)

```json
{"schema": "bti.picks.plan/1",
 "subjects": [{"id": "village", "kind": "place", "name": "village", "strip": false, "where": {"region": "VILLAGE"} }],
 "regions": [{"name": "VILLAGE", "box": [0.2, 0.3, 0.5, 0.6], "what": "Ngôi làng bên sông", "thing": "village beside river"}],
 "lines": [{"beat": "b0001", "reason": "Đoạn này nói về ngôi làng.", "kinds": ["detail"],
            "about": [{"id": "village", "words": "the village"}], "show": [{"type": "detail", "region": "VILLAGE"}]}]}
```

- `regions` lists the boxes you add to the main painting (at most 30); each is used by at least one line (an unused one is dropped). **One region is one thing**: a line that names two distinct objects gets two regions, not one shared box. Fields:
  - `name`: capital letters, digits and `_` (`HEAD`, `LEFT_HAND`, `CARVED_SAINT`). It must not use the name of a region the painting already has.
  - `box`: `[x0, y0, x1, y1]`, a ROUGH location box in fractions from 0 to 1 (0 = left or top edge) with some air round the thing (`x0 < x1`, `y0 < y1`, at least 0.02 on each side, not nearly the whole painting). The second session will cut it out at full resolution and measure its tight pixel edges.
  - `what`: a few Vietnamese words on what the box shows (shown to the owner).
  - `thing`: two to eight English words using the narration's own words for that ONE thing (`"stone bridge over village river"`, `"open letter in sitter's left hand"`). Large parts of the painting (a face, a figure, the archway) are valid things too. The check refuses `"X and Y"` in `thing` unless the narration itself names them as one unit (such as a mortar and pestle, lock and key, or `"Virgin and Child"`).
- `lines`: one entry per line of yours. `beat` is the line's id; `reason` is **one short Vietnamese sentence saying why this is on screen for this line** (not a description of the picture); `kinds` is **one or two words, in the order the line speaks**, from the table of section 5, rule 1; `show` is a list of **0 to 3 pictures**, in the order they appear:
  - `{"type": "whole"}`: the whole main painting.
  - `{"type": "detail", "region": "NAME"}`: a box of the main painting (declared in `regions`, or an existing region of the painting).
  - `{"type": "context", "search": "...", "alt": ["..."], "kind": "portrait|work|place|object|document", "entity": "subject_id", "period": "then", "what": "..."}`: a picture from elsewhere. `entity` is the subject's id, not its display name; `search` and `alt` are English searches for that same subject. Match `kind` to the subject: a person is a portrait, a work is a work, a place is a place, an object is an object, and a document is a document. Search period pictures first; the chooser may choose a modern photograph only after no usable period picture exists. Never provide `wider` searches for a similar but different subject. `what` is a short Vietnamese description for the owner.
  - `{"type": "map", "entity": "route", "places": ["Florence, Italy", "Rome, Italy"], "what": "..."}`: a map, with `entity` set to the subject id, for a journey only: two or more place names, each with its country, in the order of the journey.
  - `{"type": "clip", "entity": "river", "search": "...", "what": "...", "seconds": 6}`: a short video clip with `entity` set to the subject id from the free stock footage sources, 4 to 10 seconds.
- `fallback`: one item, `{"type": "whole"}` or `{"type": "detail", "region": "NAME"}`: what is shown for the line when none of the pictures it asks for is found. **Every `outside` line names one**: the subject's own region when the subject appears in the painting. It is not one of the 3 pictures of `show`.
- A line with `"show": []` reuses its subject picture from `about` when available; an outside or journey line can do this too when that subject was already shown. An unrelated preceding picture is not a substitute.

The program applies two rules to your file by itself and tells you in a `NOTE` (they are not errors): **a clip only on a context line** (a line that shows neither the whole painting nor a detail), and **at most one clip per chapter**; and a clip is cut to 4 to 10 seconds. Ask for a clip only where moving footage clearly beats a still, and only for something that stock footage can show (a harbour at dawn, a workshop, a candle flame); never for a specific historical event or a work of art. Prefer none.

## 5. What a good plan is

1. **Say what each line does.** Every line has `kinds`: one word, or two when the line does two things one after the other, in the order the line speaks. The check refuses a line whose pictures are not the ones its kinds need. The words:

   | kind | the line ... | what it must ask for |
   |---|---|---|
   | `detail` | points at a thing that is in the painting | a `detail` item |
   | `whole` | speaks of the painting as one object (its date, its size, where it hangs, its fate) | a `whole` item |
   | `outside` | is about a person, a place, an object, an event or a custom that is NOT in the painting | one subject picture, or reuse an earlier picture of that subject; a new search has a line-level `fallback` |
   | `compare` | sets the painting or one detail beside another work | a `context` item of kind `work` and a `detail` or `whole` item |
   | `journey` | is about a movement or a tie between two or more places | a `map` item with `places` (two or more names) |
   | `dates` | gives three or more dated events of one story | a `detail` or `whole` item (the storyboard adds the time axis) |
   | `figure` | has a quantity as its point | the picture of the thing counted: a `context` item when it is outside the painting, else a `detail` |
   | `inscription` | reads words that are visible in the picture | a `detail` item on the words |
   | `construction` | explains how the picture is built (perspective, geometry, a visible technique) | a `detail` or `whole` item |
   | `relations` | ties three or more people together (family, patrons) | a `detail`, `whole` or `context` item |
   | `idea` | gives a reading or an opinion that no picture can show | a `detail` or `whole` item |

   Worked examples for a landscape, a portrait and a crowded scene (the relevant subjects are declared separately):

   - b0006: "The village sits beside the river." A landscape subject is on the main painting: `"kinds": ["detail"]`, `"show": [{"type": "detail", "region": "VILLAGE"}]`.
   - b0007: "The painter travelled to Rome." A portrait of the painter is outside this painting: `"kinds": ["outside"]`, `"show": [{"type": "context", "search": "painter portrait", "kind": "portrait", "entity": "painter", "period": "then", "what": "Chân dung họa sĩ"}]`, `"fallback": {"type": "whole"}`.
   - b0008: "The route leads from Paris to Rome." The route is a place subject: `"kinds": ["journey"]`, `"show": [{"type": "map", "entity": "route", "places": ["Paris, France", "Rome, Italy"], "what": "Hành trình đến Rome"}]`.
   - b0022: "The saint embodies hope." The belief is an idea: `"kinds": ["idea"]`, `"show": [{"type": "detail", "region": "RING"}]`.

2. **A line about something outside the painting wants a picture of the subject.** A fact about the painter, the patron, a king, a city, a building, a ship, a battle, a custom, a document, a related work: that is an `outside` line. Ask for the thing itself with `entity` and `period` (rule 6 says how), and name the `fallback` that the viewer sees if nothing is found: the subject's own region when the subject appears in the painting. Do not fill an outside line with the main painting because it is easier: the program counts the lines about something outside the painting that end up on the painting, and a run with too many of them stops for the owner. For a place, ask for a view of the place (`kind: "place"`), not a map (rule 4). For the past, a picture made in that period comes first (`period: "then"`); a modern photograph is considered only after no usable period picture is found.
   Search each subject once. Alternate searches must still depict that same subject. If none fits, use the nearest concrete subject from this line or the previous one.
3. **Ask for the work itself, not for pictures about it.** When the narration names another work, search for that work by its title and its painter ("The Night Watch Rembrandt"), and say `kind: "work"`. A public-domain scan or photograph of the work is what you want; an illustration, a diagram or a page of commentary about it is a poor second. Never ask for the main painting itself (its title and painter in `search`): it is already on screen.
4. **A map only when the line is about *where* something travels or is tied between places: a `journey`.** A line that says the painter travelled from Florence to Rome, or that a scale was built in Lübeck and set up in Antwerp, is a journey or a tie between two or more places: its map names every place in `places`, each with its country ("Antwerp, Belgium", not "the coastal lowlands"). A place that is merely mentioned is **not** a journey: "born at Limoges", "Bruges was the commercial capital of northern Europe" are `outside` lines and want a view of the place (`kind: "place"`, `entity: "limoges"` (the subject id)), not a map. The check refuses a map on a line without `journey` and a `journey` with fewer than two places.
5. **The same framing does not stay on screen for more than about half a minute of narration** (`seconds` of the lines add up: about 30 s is 70 words). When several lines in a row would show the same thing, vary: go from the whole painting to a detail, to another detail, back to the whole, or to a context picture. The check warns when a run is too long. A line you leave empty (`"show": []`) continues the framing before it, so a long run of empty lines counts as one long framing.
6. **One picture per line is the usual number; an `outside` line reuses its subject’s picture when possible.** Two when the line moves from one thing to another (a detail, then the whole; a work, then its painter; something outside, then a journey). Three is rare. Many short pictures on one line is not good pacing. In all you may ask for **at most 60 pictures from elsewhere** (context, map, clip): the second session looks at a sheet for each, so spend them on the lines that are about something outside the painting and leave the lines about the painting itself on the painting.
   **A good `search`**: the short name under which the thing is known (the title of the work, the name of the object) comes first and stands alone as the `search` when the thing has a name ("Moneylender and his Wife", "Royal Gold Cup", "Codex Behem"); descriptive words go to `alt`. For things without such a name, use the name of the thing and what kind of picture, in English: "Philip the Good portrait Rogier van der Weyden" finds the duke, "duke portrait" finds a hundred dukes; "Noyon Cathedral facade" finds the building, "cathedral" finds the first one the search knows. Put the name from the line (or the dossier) first. The two `alt` are **different in kind** from the `search` and from each other, so that if the first finds nothing the others look somewhere else: a period view ("Noyon Cathedral 14th century engraving"), an object in a museum ("gold rider coin Philip the Good Royal Library of Belgium"), a work of art that shows it ("Saint Eligius shoeing a horse miniature"). Never put the main painting's own title in a search.
7. **Nothing invented, and a vague line is not stretched.** If a line talks about something no picture can show (an idea, an opinion), its kind is `idea` and it shows the painting. Do not turn a vague line into an `outside` line to get a picture: ask for a picture only when the line names a person, a place, an object, an event or a custom that can be looked up. The program reports every picture it could not find, so do not ask for pictures of things you are not sure exist; ask for the nearest thing that does (the town instead of its lost guildhall, a surviving object of the kind instead of the lost one).
8. **A line about the painting shows the part it speaks of.** Show the subject the sentence is about: a person before details of them, or the whole painting when it speaks of the painting as a whole. Never a detail the sentence does not mention.
9. **The reason is for the owner.** One short sentence, Vietnamese, plain words: why this is on screen for this line ("Lời dẫn nói về cây cầu đá: đi vào đúng chi tiết đó."). Not "Hình ảnh minh họa".

## 6. Boxes: rough location with air round the thing

Your `box` here is a **rough location box**, not the final tight crop. Put generous air round the thing so it is not clipped (`[x0, y0, x1, y1]` in fractions of the painting), especially for tiny details where the 1,568-px view cannot resolve clean edges. The choosing session will cut each rough box out of the **full-resolution stored painting** with a 100-px coordinate grid and measure the tight box touching the thing itself.

Use `{{CROP_CMD}} --grid -o look/grid.jpg` to read rough coordinates accurately; use `{{CROP_CMD}} --box x0,y0,x1,y1 -o look/NAME.jpg` only when a location is hard to spot on `images/main.jpg`. A box thinner than 0.02 of the painting cannot show anything; one over 0.90 is the whole painting. A `fallback` that is a `detail` needs a box too. Remember: **one region = one thing**, named in English in `thing`.

## 7. The two helper commands

Run them from this folder. Each prints what it did; each has `--help`.

- **Check** your file: `{{CHECK_CMD}}`. It reads `out/plan.json` exactly as the program will, and prints `ERROR` lines (fix them), `NOTE` lines (what the program will change by itself) and `WARNING` lines (worth a look: the same framing for too long). An error about `kinds` names the line and says what to add: a picture of the thing itself for an `outside` line, a `fallback`, the places of a journey, the other work of a comparison. Repeat until it says `0 error(s)`.
- **Crop** the main painting: `{{CROP_CMD}} --box 0.40,0.10,0.62,0.30 -o look/head.jpg` cuts that box out of the painting and writes it (the output must be inside `look/`); open the file to look at it. `{{CROP_CMD}} --grid -o look/grid.jpg` writes the painting with a labelled grid.

If a command fails to start, say so in a line of your last message and carry on by reading your own file carefully: do not look for another way to reach the program. When the check says `0 error(s)`, you are done: write one sentence of what you did as your last message.
