# Task: plan what is on screen for each line of the narration of a documentary video

You work for a channel that makes ten-minute art documentaries in the style of Great Art Explained: one painting, a narrator, and a picture on screen that always fits the sentence being spoken. The narration is written and approved, and it is cut into **lines** (a line is one short paragraph of narration). Someone now has to decide, for each line, **what the line does and what is on screen while it is spoken**: a detail of the main painting, the whole painting, another picture that gives context (a portrait of the painter, a related work, a view of a place, an object, a page of a document), a map, or, rarely, a short clip. That someone is you, for the {{N_TARGETS}} lines marked `target: true`. The owner will look at your proposal on a page and correct it, so make it sensible on a first look.

The owner's rule, in his own words: **"Don't just show the painting too much. Find the image that captures the narrative the most, in a way that the viewer can understand."** When the narrator talks about the guild rules, a king, a harbour or a battle, those things are not in the painting, and the viewer must see a real picture of them. When the narrator talks about a place, show a simple picture of the place, not a map.

You do not search for the pictures and you do not choose among them: a program searches the picture sources for what you ask (the free ones, and the web), and a second short session of yours looks at what it found and chooses. Your job now is the **plan**: one JSON file that says, line by line, what the line does and what should be on screen, with a box for every detail of the main painting you want to show. A program turns your plan into the real picks, and checks it first. You run the check and fix what it reports.

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
4. **Every one of your lines has exactly one entry in `lines`, with its `kinds`.** A line whose picture before it is still the right one gets `"show": []` (only a line that points at the painting may do that; see section 5). Why: the owner must never see a line the agent forgot, and the next step reads `kinds` to know what each line is for.
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
2. Read `inputs/narration.json` chapter by chapter. For each of your lines ask: *what is this sentence doing?* Naming a part of the painting, telling a fact about the painter, comparing two works, describing a place or a journey, giving a number, quoting a document, or telling a story that happens elsewhere? The answer is the line's `kinds` (section 5, rule 1).
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
    "kinds": ["whole"], "show": [{"type": "whole"}]},
   {"beat": "b0002", "reason": "Lời dẫn nói về tấm gương: đi vào đúng chi tiết đó.",
    "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
   {"beat": "b0003", "reason": "Nói về họa sĩ, không phải về tranh: cần chân dung của ông.",
    "kinds": ["outside"],
    "show": [{"type": "context", "search": "Jan van Eyck portrait", "alt": ["Man in a Red Turban Van Eyck National Gallery"], "kind": "portrait",
              "entity": "Jan van Eyck", "period": "then", "what": "Chân dung Jan van Eyck"}],
    "fallback": {"type": "detail", "region": "MIRROR"}
   },
   {"beat": "b0004", "reason": "Dòng này nói cái gương nằm ở đâu và ai ký tên: hai chi tiết nối nhau.",
    "kinds": ["detail", "inscription"], "show": [{"type": "detail", "region": "MIRROR"}, {"type": "detail", "region": "SIGNATURE"}]},
   {"beat": "b0005", "reason": "Câu này kể chuyến đi từ Bruges đến Lisbon: một bản đồ nối hai nơi.",
    "kinds": ["journey"], "show": [{"type": "map", "places": ["Bruges, Belgium", "Lisbon, Portugal"], "what": "Hành trình từ Bruges đến Lisbon"}]},
   {"beat": "b0006", "reason": "Vẫn cùng ý với đoạn trước, không cần hình mới.", "kinds": ["idea"], "show": []}]}
```

- `regions` lists the boxes you add to the main painting (at most 20); each is used by at least one line (an unused one is dropped). `name`: capital letters, digits and `_` (`HEAD`, `LEFT_HAND`). `box`: `[x0, y0, x1, y1]`, fractions from 0 to 1 (0 = left or top edge); `x0 < x1`, `y0 < y1`; at least 0.02 on each side, and not nearly the whole painting. `what`: a few Vietnamese words on what the box shows. It must not use the name of a region the painting already has.
- `lines`: one entry per line of yours. `beat` is the line's id; `reason` is **one short Vietnamese sentence saying why this is on screen for this line** (not a description of the picture); `kinds` is **one or two words, in the order the line speaks**, from the table of section 5, rule 1; `show` is a list of **0 to 3 pictures**, in the order they appear:
  - `{"type": "whole"}`: the whole main painting.
  - `{"type": "detail", "region": "NAME"}`: a box of the main painting (declared in `regions`, or an existing region of the painting).
  - `{"type": "context", "search": "...", "alt": ["..."], "kind": "work|portrait|document|photo|place|object|event|other", "entity": "...", "period": "then|now", "what": "..."}`: a picture from elsewhere. `search` is what a picture search can use (rule 2 of section 5 says what a good one is); `alt` up to two other ways to say it (they are tried only if the first finds little); `kind` says what sort of picture it is (it decides which sources are asked): `work` another painting or sculpture, `portrait` a person, `document` a page, a charter, a manuscript, `photo` a photograph of a thing, `place` a view of a town, a building or a landscape, `object` a coin, a tool, a piece of jewellery, a ship, `event` a battle, a ceremony, a scene; `entity` is the name under which an encyclopedia knows the thing ("Philip the Good", "Noyon Cathedral", "Arnolfini Portrait"; leave it out when the thing has no such name); `period` is `"then"` when a picture made in the time the line speaks of is wanted (the usual case: a painting, a print, a manuscript page, an object) and `"now"` when a photograph of today is right (a building or an object that survives, or a line about today); `what` is what the picture should show, in a few Vietnamese words (it is shown to the owner if nothing is found, and to your second session as the thing to look for).
  - `{"type": "map", "places": ["Lübeck, Germany", "Bruges, Belgium"], "what": "..."}`: a map, for a journey only: two or more place names, each with its country, in the order of the journey.
  - `{"type": "clip", "search": "...", "what": "...", "seconds": 6}`: a short video clip from the free stock footage sources, 4 to 10 seconds.
- `fallback`: one item, `{"type": "whole"}` or `{"type": "detail", "region": "NAME"}`: what is shown for the line when none of the pictures it asks for is found. **Every `outside` line names one**: the part of the painting nearest to what the line says. It is not one of the 3 pictures of `show`.
- A line with `"show": []` needs nothing new: the picture before it stays. Only a line that points at the painting (`detail`, `whole`, `dates`, `inscription`, `construction`, `relations`, `idea`) may do that.

The program applies two rules to your file by itself and tells you in a `NOTE` (they are not errors): **a clip only on a context line** (a line that shows neither the whole painting nor a detail), and **at most one clip per chapter**; and a clip is cut to 4 to 10 seconds. Ask for a clip only where moving footage clearly beats a still, and only for something that stock footage can show (a harbour at dawn, a workshop, a candle flame); never for a specific historical event or a work of art. Prefer none.

## 5. What a good plan is

1. **Say what each line does.** Every line has `kinds`: one word, or two when the line does two things one after the other, in the order the line speaks. The check refuses a line whose pictures are not the ones its kinds need. The words:

   | kind | the line ... | what it must ask for |
   |---|---|---|
   | `detail` | points at a thing that is in the painting | a `detail` item |
   | `whole` | speaks of the painting as one object (its date, its size, where it hangs, its fate) | a `whole` item |
   | `outside` | is about a person, a place, an object, an event or a custom that is NOT in the painting | at least one `context` (or `clip`) item, and a line-level `fallback` (a `detail` or `whole` item shown when nothing is found) |
   | `compare` | sets the painting or one detail beside another work | a `context` item of kind `work` and a `detail` or `whole` item |
   | `journey` | is about a movement or a tie between two or more places | a `map` item with `places` (two or more names) |
   | `dates` | gives three or more dated events of one story | a `detail` or `whole` item (the storyboard adds the time axis) |
   | `figure` | has a quantity as its point | the picture of the thing counted: a `context` item when it is outside the painting, else a `detail` |
   | `inscription` | reads words that are visible in the picture | a `detail` item on the words |
   | `construction` | explains how the picture is built (perspective, geometry, a visible technique) | a `detail` or `whole` item |
   | `relations` | ties three or more people together (family, patrons) | a `detail`, `whole` or `context` item |
   | `idea` | gives a reading or an opinion that no picture can show | a `detail` or `whole` item |

   Worked examples, from the narration of a painting of Saint Eligius as a goldsmith (the regions are the ones that painting would have):

   - b0006: "Why can we see into this shop at all? Look at the counter along the front edge, open to the street. Goldsmiths had to work in full view like this, so customers could check that nobody was doctoring the metal." It points at a thing in the painting: `"kinds": ["detail"]`, `"show": [{"type": "detail", "region": "COUNTER_EDGE"}]`.
   - b0007: "These rules came from the guilds of 14th-century Netherlandish towns, which curbed ruinous competition and guaranteed good work. One document of that time even forbade goldsmiths to attract custom by sneezing or sniffling." Guilds and a document of the time are not in the painting: `"kinds": ["outside"]`, `"show": [{"type": "context", "search": "medieval goldsmith guild statutes manuscript Low Countries", "alt": ["goldsmiths at work medieval miniature"], "kind": "document", "entity": "Guild", "period": "then", "what": "Điều lệ phường thợ vàng thời Trung cổ"}]`, `"fallback": {"type": "detail", "region": "COUNTER_EDGE"}`.
   - b0008: "Behind all this lay a fear of fraud. Countries used different units of weight and measure, so merchants weighed their goods with special care. In 1282 the Hanse merchants even had their own scales, built in Lübeck, set up in Bruges." Something outside, then a tie between two places: `"kinds": ["outside", "journey"]`, `"show": [{"type": "context", "search": "Hanseatic merchants weighing goods medieval illustration", "alt": ["medieval balance scales museum"], "kind": "event", "entity": "Hanseatic League", "period": "then", "what": "Thương nhân Hanse cân hàng"}, {"type": "map", "places": ["Lübeck, Germany", "Bruges, Belgium"], "what": "Lübeck và Bruges"}]`, `"fallback": {"type": "detail", "region": "SCALES"}`.
   - b0028: "On one day in 1457 its harbour held 42 British caravels and three Venetian galleys. Italian banks ran their northern branches here." The point is a number, and the thing counted is outside the painting: `"kinds": ["outside", "figure"]`, `"show": [{"type": "context", "search": "Bruges harbour 15th century ships", "alt": ["caravel ship 15th century painting", "Venetian galley 15th century"], "kind": "place", "entity": "Bruges", "period": "then", "what": "Bến cảng Bruges thế kỷ 15"}]`, `"fallback": {"type": "detail", "region": "SHOP_FRONT"}`.
   - b0045: "Jan van Eyck painted such a mirror in his Arnolfini portrait, and it is presumed to hold his own reflection. So one reading sees a quotation here, and the falconer as Petrus Christus himself." It sets the painting's mirror beside another work: `"kinds": ["compare"]`, `"show": [{"type": "detail", "region": "MIRROR"}, {"type": "context", "search": "Arnolfini Portrait Jan van Eyck National Gallery", "alt": ["Arnolfini Wedding mirror detail"], "kind": "work", "entity": "Arnolfini Portrait", "period": "then", "what": "Chân dung Arnolfini của Jan van Eyck"}]`.
   - b0049: "He was born at Baerle, probably in 1415. He became a citizen of Bruges on 6 July 1444. Seven years after joining a brotherhood in 1462, he was named a distinguished member of the painters' guild." Three dated events of one life: `"kinds": ["dates"]`, `"show": [{"type": "detail", "region": "INSCRIPTION"}]` (the storyboard draws the time axis over it).
   - b0048: "Drop your eye to the bottom edge of the panel, where a line of Latin runs along it. Translated, it reads, Petrus Christus made me in the year 1449." Words that can be read in the picture: `"kinds": ["inscription"]`, `"show": [{"type": "detail", "region": "INSCRIPTION"}]`.
   - b0043: "Look at the shelves behind the saint. Their angles suggest the painter did not know the new laws of perspective from Florence." How the picture is built: `"kinds": ["construction"]`, `"show": [{"type": "detail", "region": "SHELVES"}]`.
   - b0022: "So one reading sees the saint as a man who turns a girl away from worldly marriage. Another sees a guardian of marriage and of the wedding-ring trade, a profitable line for goldsmiths." A reading, no picture shows it: `"kinds": ["idea"]`, `"show": [{"type": "detail", "region": "RING"}]` (the thing the readings are about).

2. **A line about something outside the painting shows something other than the main painting: the picture of the thing itself, and it never stays on the painting for lack of one.** A fact about the painter, the patron, a king, a city, a building, a ship, a battle, a custom, a document, a related work: that is an `outside` line. Ask for the thing itself with `entity` and `period` (rule 6 says how), and name the `fallback` that the viewer sees if nothing is found: the part of the painting nearest to what the line says. Do not fill an outside line with the main painting because it is easier: the program counts the lines about something outside the painting that end up on the painting, and a run with too many of them stops for the owner. For a place, ask for a view of the place (`kind: "place"`), not a map (rule 4). For the past, a picture made in that period comes first (a painting, a print, a manuscript page, an object: `period: "then"`); a photograph of today only when nothing else can exist or the line is about today (`period: "now"`: a cathedral that still stands, where the painting hangs now).
3. **Ask for the work itself, not for pictures about it.** When the narration names another work, search for that work by its title and its painter ("Madonna of Chancellor Rolin Jan van Eyck"), and say `kind: "work"`. A public-domain scan or photograph of the work is what you want; an illustration, a diagram or a page of commentary about it is a poor second. Never ask for the main painting itself (its title and painter in `search`): it is already on screen.
4. **A map only when the line is about *where* something travels or is tied between places: a `journey`.** A line that says the painter travelled from Bruges to Lisbon, or that a scale was built in Lübeck and set up in Bruges, is a journey or a tie between two or more places: its map names every place in `places`, each with its country ("Bruges, Belgium", not "the Flemish heartland"). A place that is merely mentioned is **not** a journey: "born at Limoges", "Bruges was the commercial capital of northern Europe" are `outside` lines and want a view of the place (`kind: "place"`, `entity: "Limoges"`), not a map. The check refuses a map on a line without `journey` and a `journey` with fewer than two places.
5. **The same framing does not stay on screen for more than about half a minute of narration** (`seconds` of the lines add up: about 30 s is 70 words). When several lines in a row would show the same thing, vary: go from the whole painting to a detail, to another detail, back to the whole, or to a context picture. The check warns when a run is too long. A line you leave empty (`"show": []`) continues the framing before it, so a long run of empty lines counts as one long framing.
6. **One picture per line is the usual number; every `outside` line asks for one.** Two when the line moves from one thing to another (a detail, then the whole; a work, then its painter; something outside, then a journey). Three is rare. Many short pictures on one line is not good pacing. In all you may ask for **at most 60 pictures from elsewhere** (context, map, clip): the second session looks at a sheet for each, so spend them on the lines that are about something outside the painting and leave the lines about the painting itself on the painting.
   **A good `search`** is the name of the thing and what kind of picture, in English: "Philip the Good portrait Rogier van der Weyden" finds the duke, "duke portrait" finds a hundred dukes; "Noyon Cathedral facade" finds the building, "cathedral" finds the first one the search knows. Put the name from the line (or the dossier) first. The two `alt` are **different in kind** from the `search` and from each other, so that if the first finds nothing the others look somewhere else: a period view ("Noyon Cathedral 14th century engraving"), an object in a museum ("gold rider coin Philip the Good Royal Library of Belgium"), a work of art that shows it ("Saint Eligius shoeing a horse miniature"). Never put the main painting's own title in a search.
7. **Nothing invented, and a vague line is not stretched.** If a line talks about something no picture can show (an idea, an opinion), its kind is `idea` and it shows the painting. Do not turn a vague line into an `outside` line to get a picture: ask for a picture only when the line names a person, a place, an object, an event or a custom that can be looked up. The program reports every picture it could not find, so do not ask for pictures of things you are not sure exist; ask for the nearest thing that does (the town instead of its lost guildhall, a surviving object of the kind instead of the lost one).
8. **A line about the painting shows the part it speaks of.** If the sentence names a mirror, the line shows the mirror (a box on it); if it describes the whole scene, the whole painting; if it speaks of the painting in general, a slow look at the whole or at a part the eye wanders to. Never a detail the sentence does not mention.
9. **The reason is for the owner.** One short sentence, Vietnamese, plain words: why this is on screen for this line ("Lời dẫn nói về tấm gương: đi vào đúng chi tiết đó."). Not "Hình ảnh minh họa".

## 6. Boxes: look before you propose

A box is the part of the painting that the camera will frame while the line is spoken. Leave a little air around what you mean: a face is the whole head and a bit of neck, not just the eyes; a hand is the hand and the wrist. A box thinner than 0.02 of the painting cannot show anything; one that covers almost the whole painting is not a detail.

**Check every box you propose with a crop and look at the crop** before you write it into the plan: `{{CROP_CMD}} --box x0,y0,x1,y1 -o look/NAME.jpg`, then open `look/NAME.jpg`. Is the thing the sentence names in it, centred, with a little air? If not, move the box and crop again. A box you did not look at is a guess, and the second session will look at it and may drop it. A `fallback` that is a `detail` needs a box too.

## 7. The two helper commands

Run them from this folder. Each prints what it did; each has `--help`.

- **Check** your file: `{{CHECK_CMD}}`. It reads `out/plan.json` exactly as the program will, and prints `ERROR` lines (fix them), `NOTE` lines (what the program will change by itself) and `WARNING` lines (worth a look: the same framing for too long). An error about `kinds` names the line and says what to add: a picture of the thing itself for an `outside` line, a `fallback`, the places of a journey, the other work of a comparison. Repeat until it says `0 error(s)`.
- **Crop** the main painting: `{{CROP_CMD}} --box 0.40,0.10,0.62,0.30 -o look/head.jpg` cuts that box out of the painting and writes it (the output must be inside `look/`); open the file to look at it. `{{CROP_CMD}} --grid -o look/grid.jpg` writes the painting with a labelled grid.

If a command fails to start, say so in a line of your last message and carry on by reading your own file carefully: do not look for another way to reach the program. When the check says `0 error(s)`, you are done: write one sentence of what you did as your last message.
