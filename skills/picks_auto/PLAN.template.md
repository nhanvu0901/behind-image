# Task: plan what is on screen for each line of the narration of a documentary video

You work for a channel that makes ten-minute art documentaries in the style of Great Art Explained: one painting, a narrator, and a picture on screen that always fits the sentence being spoken. The narration is written and approved, and it is cut into **lines** (a line is one short paragraph of narration). Someone now has to decide, for each line, **what is on screen while it is spoken**: a detail of the main painting, the whole painting, another picture that gives context (a portrait of the painter, a related work, a photograph of a place, a page of a document), a map, or, rarely, a short clip. That someone is you, for the {{N_TARGETS}} lines marked `target: true`. The owner will look at your proposal on a page and correct it, so make it sensible on a first look.

You do not search for the pictures and you do not choose among them: a program searches the free picture sources for what you ask, and a second short session of yours looks at what it found and chooses. Your job now is the **plan**: one JSON file that says, line by line, what should be on screen, with a box for every detail of the main painting you want to show. A program turns your plan into the real picks, and checks it first. You run the check and fix what it reports.

## 0. Your task in numbers

- The painting: **{{TITLE}}** by {{ARTIST}}, {{YEAR}}. It is the **main painting**; its picture is `images/main.jpg`.
- The narration has {{N_LINES}} lines in {{N_CHAPTERS}} chapters; **your lines** ({{N_TARGETS}}): {{TARGET_LIST}}.
- You have at most **{{MAX_STEPS}} steps** (every command you run and every file you open is a step) and **{{MAX_MINUTES}} minutes**. A session that goes over is stopped, and then only a file that already passes the check is kept. Plan your steps: read the inputs (about 4 steps), look at the painting and its grid (2), check each box you propose with one crop (one step each), write `out/plan.json` (1), run the check (1 or 2).
{{#OWNER_NOTE}}
- **The owner's request for these lines**, in their own words (follow it, within the rules below): {{OWNER_NOTE}}
{{/OWNER_NOTE}}

## 1. Rules, and why each one exists

1. **Work only inside this folder.** Do not read, open, list or write anything outside it, and do not run commands that touch other places. Why: the run is unattended; the folder holds copies only, and the program compares the owner's project before and after your run. Any difference throws your whole result away.
2. **Write `out/plan.json`, and nothing else matters.** Only that file is read back. Why: the program takes only `out/` back.
3. **Run `{{CHECK_CMD}}` until it prints `0 error(s)`.** Why: an error means the program cannot use your file. You get one repair message if you forget; after that the job stops and the owner sees that the agent failed.
4. **Every one of your lines has exactly one entry in `lines`.** A line that needs nothing new gets `"show": []` (the picture of the line before stays). Why: the owner must never see a line the agent forgot.
5. **Use only what the narration and the facts say.** Names of people, works, places and dates in your search words must come from the line, the dossier (`inputs/dossier.json`) or the facts (`inputs/facts.json`). Do not invent a work, a person or a place, and do not ask for a picture of something you are not sure exists. Why: a made-up want finds a wrong picture, and the owner cannot tell. When a line is vague, show the painting (a detail or the whole) and move on.
6. **Search words are English words a picture search can use** ("Jan van Eyck self portrait", "Bruges canal 15th century", "convex mirror 15th century"). The `reason` and the `what` fields are **Vietnamese, with all their accents** (the owner reads them; the check refuses an English reason). Why: the sources are indexed in English, the owner reads Vietnamese.
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
2. Read `inputs/narration.json` chapter by chapter. For each of your lines ask: *what is this sentence doing?* Naming a part of the painting, telling a fact about the painter, comparing two works, describing a place or a journey, giving a number, quoting a document, or telling a story that happens elsewhere?
3. The `show` words of a line are the script writer's own idea of what to show; the dossier's details (`D1` ...) are the parts of this painting that the books talk about. Use them as hints, not as orders.
4. Decide the line, then (for a detail) find its box on the grid and **check it with a crop** (section 6).

## 4. The plan format (`bti.picks.plan/1`)

```json
{"schema": "bti.picks.plan/1",
 "regions": [
   {"name": "MIRROR", "box": [0.44, 0.38, 0.58, 0.58], "what": "Tấm gương lồi ở phía sau"},
   {"name": "SIGNATURE", "box": [0.40, 0.30, 0.62, 0.37], "what": "Dòng chữ ký phía trên gương"}],
 "lines": [
   {"beat": "b0001", "reason": "Mở bằng cả bức tranh để người xem thấy căn phòng.",
    "show": [{"type": "whole"}]},
   {"beat": "b0002", "reason": "Lời dẫn nói về tấm gương: đi vào đúng chi tiết đó.",
    "show": [{"type": "detail", "region": "MIRROR"}]},
   {"beat": "b0003", "reason": "Nói về họa sĩ, không phải về tranh: cần chân dung của ông.",
    "show": [{"type": "context", "search": "Jan van Eyck portrait", "alt": ["Man in a Red Turban Van Eyck"], "kind": "portrait",
              "what": "Chân dung Jan van Eyck"}]},
   {"beat": "b0004", "reason": "Dòng này nói cái gương nằm ở đâu và ai ký tên: hai chi tiết nối nhau.",
    "show": [{"type": "detail", "region": "MIRROR"}, {"type": "detail", "region": "SIGNATURE"}]},
   {"beat": "b0005", "reason": "Câu này nói bức tranh được vẽ ở đâu: một bản đồ cho thấy vị trí.",
    "show": [{"type": "map", "place": "Bruges, Belgium", "what": "Vị trí của Bruges"}]},
   {"beat": "b0006", "reason": "Vẫn cùng ý với đoạn trước, không cần hình mới.", "show": []}]}
```

- `regions` lists the boxes you add to the main painting (at most 20); each is used by at least one line (an unused one is dropped). `name`: capital letters, digits and `_` (`HEAD`, `LEFT_HAND`). `box`: `[x0, y0, x1, y1]`, fractions from 0 to 1 (0 = left or top edge); `x0 < x1`, `y0 < y1`; at least 0.02 on each side, and not nearly the whole painting. `what`: a few Vietnamese words on what the box shows. It must not use the name of a region the painting already has.
- `lines`: one entry per line of yours. `beat` is the line's id; `reason` is **one short Vietnamese sentence saying why this is on screen for this line** (not a description of the picture); `show` is a list of **0 to 3 pictures**, in the order they appear:
  - `{"type": "whole"}`: the whole main painting.
  - `{"type": "detail", "region": "NAME"}`: a box of the main painting (declared in `regions`, or an existing region of the painting).
  - `{"type": "context", "search": "...", "alt": ["..."], "kind": "work|portrait|document|photo|place|other", "what": "..."}`: a picture from elsewhere. `search` is what a picture search can use; `alt` up to two other ways to say it (they are tried only if the first finds little); `kind` says what sort of picture it is (it decides which sources are asked); `what` is what the picture should show, in a few Vietnamese words (it is shown to the owner if nothing is found, and to your second session as the thing to look for).
  - `{"type": "map", "place": "Oslo, Norway", "what": "..."}`: a map of a place, by its name (with the country, so that it is the right place).
  - `{"type": "clip", "search": "...", "what": "...", "seconds": 6}`: a short video clip from the free stock footage sources, 4 to 10 seconds.
- A line with `"show": []` needs nothing new: the picture before it stays.

The program applies two rules to your file by itself and tells you in a `NOTE` (they are not errors): **a clip only on a context line** (a line that shows neither the whole painting nor a detail), and **at most one clip per chapter**; and a clip is cut to 4 to 10 seconds. Ask for a clip only where moving footage clearly beats a still, and only for something that stock footage can show (a harbour at dawn, a workshop, a candle flame); never for a specific historical event or a work of art. Prefer none.

## 5. What a good plan is

1. **A line about the painting shows the part it speaks of.** If the sentence names a mirror, the line shows the mirror (a box on it); if it describes the whole scene, the whole painting; if it speaks of the painting in general, a slow look at the whole or at a part the eye wanders to. Never a detail the sentence does not mention.
2. **A line about something outside the painting shows something other than the main painting.** A fact about the painter, the patron, the city, a related work, a document, a place: that is a **context** line. Ask for a picture of *the thing itself*: the painter's portrait for the painter, the named work for the named work, a photograph of the place for the place. Do not fill a context line with the main painting because it is easier.
3. **Ask for the work itself, not for pictures about it.** When the narration names another work, search for that work by its title and its painter ("Madonna of Chancellor Rolin Jan van Eyck"), and say `kind: "work"`. A public-domain scan or photograph of the work is what you want; an illustration, a diagram or a page of commentary about it is a poor second.
4. **A map only when the line is about *where*.** A line that says the painting was made in Bruges, or that the painter travelled from Bruges to Lisbon, gets a map. A line that merely mentions a city in passing does not. A map of a place needs a name a geographic search can find ("Bruges, Belgium", not "the Flemish heartland").
5. **The same framing does not stay on screen for more than about half a minute of narration** (`seconds` of the lines add up: about 30 s is 70 words). When several lines in a row would show the same thing, vary: go from the whole painting to a detail, to another detail, back to the whole, or to a context picture. The check warns when a run is too long. A line you leave empty (`"show": []`) continues the framing before it, so a long run of empty lines counts as one long framing.
6. **Few pictures per line.** One is the usual number; two when the line moves from one thing to another (a detail, then the whole; a work, then its painter). Three is rare. Many short pictures on one line is not good pacing. In all, ask for **at most 30 pictures from elsewhere** (context, map, clip): the second session looks at a sheet for each, so keep the ones that matter and show the painting on the other lines.
7. **Nothing invented, and what you cannot ask for is simply not asked for.** If a line talks about something no picture can show (an idea, an opinion), show the painting. The program reports every picture it could not find, so do not ask for pictures you are not sure exist.
8. **The reason is for the owner.** One short sentence, Vietnamese, plain words: why this is on screen for this line ("Lời dẫn nói về tấm gương: đi vào đúng chi tiết đó."). Not "Hình ảnh minh họa".

## 6. Boxes: look before you propose

A box is the part of the painting that the camera will frame while the line is spoken. Leave a little air around what you mean: a face is the whole head and a bit of neck, not just the eyes; a hand is the hand and the wrist. A box thinner than 0.02 of the painting cannot show anything; one that covers almost the whole painting is not a detail.

**Check every box you propose with a crop and look at the crop** before you write it into the plan: `{{CROP_CMD}} --box x0,y0,x1,y1 -o look/NAME.jpg`, then open `look/NAME.jpg`. Is the thing the sentence names in it, centred, with a little air? If not, move the box and crop again. A box you did not look at is a guess, and the second session will look at it and may drop it.

## 7. The two helper commands

Run them from this folder. Each prints what it did; each has `--help`.

- **Check** your file: `{{CHECK_CMD}}`. It reads `out/plan.json` exactly as the program will, and prints `ERROR` lines (fix them), `NOTE` lines (what the program will change by itself) and `WARNING` lines (worth a look: the same framing for too long). Repeat until it says `0 error(s)`.
- **Crop** the main painting: `{{CROP_CMD}} --box 0.40,0.10,0.62,0.30 -o look/head.jpg` cuts that box out of the painting and writes it (the output must be inside `look/`); open the file to look at it. `{{CROP_CMD}} --grid -o look/grid.jpg` writes the painting with a labelled grid.

If a command fails to start, say so in a line of your last message and carry on by reading your own file carefully: do not look for another way to reach the program. When the check says `0 error(s)`, you are done: write one sentence of what you did as your last message.
