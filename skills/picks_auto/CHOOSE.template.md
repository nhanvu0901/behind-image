# Task: choose the pictures for a documentary video, and check the boxes you proposed

You work for a channel that makes ten-minute art documentaries in the style of Great Art Explained: one painting, a narrator, and a picture on screen that always fits the sentence being spoken. The narration is cut into **lines**. In an earlier session you planned what should be on screen for each line. Some lines want a picture from elsewhere (a portrait of the painter, a related work, a photograph of a place, a map, a clip), and some lines show a **box** you drew on the main painting. Since then a program has searched the free picture sources and cut a crop for every box. **Your job now is to choose**: for each wanted picture, which candidate is the right one, or that none is; and for each box, whether it is right, needs moving, or should be dropped.

You write one JSON file, `out/choice.json`. A program imports the pictures you chose, writes them into the owner's picks and shows the owner the proposal, which the owner corrects. So the owner sees what you choose: choose only what you are sure of.
{{#SECOND_LOOK}}

**This is a second look.** In the first look you answered none (`null`) for the wanted pictures below, or the first search found nothing for them. The program has since searched again, on the web as well. Each wanted picture here shows ONLY the new candidates (numbered from 1 on its own sheet) and, in `first_look`, what you said before. There are no boxes to review and no pictures of the owner's books: `regions` is empty and you only decide the wanted pictures. The same rules hold, and `null` is still the right answer when nothing shows the thing.
{{/SECOND_LOOK}}

## 0. Your task in numbers

- The painting: **{{TITLE}}** by {{ARTIST}}, {{YEAR}} (`images/main.jpg`).
- Wanted pictures: **{{N_WANTS}}** ({{WANT_LIST}}). Pictures of the owner's books: **{{N_BOOKS}}** (B1 ...). Boxes to review: **{{N_REGIONS}}** ({{REGION_LIST}}).
- You have at most **{{MAX_STEPS}} steps** (every command you run and every file you open is a step) and **{{MAX_MINUTES}} minutes**. A session that goes over is stopped, and then only a file that already passes the check is kept. Plan your steps: read `inputs/wants.json` and `inputs/regions.json` (2), open one contact sheet per wanted picture (one step each), open each gridded cut-out `images/d_<NAME>.jpg` (one step each), write `out/choice.json` (1), run `{{CHECK_CMD}}` (produces any `wider` cut-outs or `look/check_*.jpg` sheets), open every check sheet and confirm (or correct once) in `out/choice.json`, then run `{{CHECK_CMD}}` until `0 error(s)`.
{{#OWNER_NOTE}}
- **The owner's request for these lines**, in their own words: {{OWNER_NOTE}}
{{/OWNER_NOTE}}

## 1. Rules, and why each one exists

1. **Work only inside this folder.** Do not read, open, list or write anything outside it, and do not run commands that touch other places. Why: the run is unattended; the folder holds copies only, and the program compares the owner's project before and after your run. Any difference throws your whole result away.
2. **Write `out/choice.json`.** Only that file is read back.
3. **Run `{{CHECK_CMD}}` until it prints `0 error(s)`.** You get one repair message if you forget; after that the job stops and the owner sees that the agent failed.
4. **Decide every wanted picture and every box.** Nothing may be left out (the check lists what is missing).
5. **Never pick a picture you are not sure shows the subject itself.** For a subject-bound want, check the picture and its record; set `shows_subject: true` only for a confident match. Otherwise pick null. For each selected subject-bound context picture set `period_picture` to true for a period picture, or false for a modern photograph and also set `no_period_picture` to true only after no usable period picture remains. If no candidate is right, the answer is `null` with a reason (when a search finds nothing usable, the program automatically tries once more with a simpler or broader free wording before giving up). A wrong picture on screen is worse than a line the owner fills in by hand, and the program tells the owner plainly which lines have no picture. Why: the owner trusts the proposal only if what is in it is right.
6. **Reasons are Vietnamese, with all their accents** (the owner reads them; the check refuses an English reason), one short sentence, plain words.

## 2. The files

| File | What it is |
|---|---|
| `inputs/wants.json` | The wanted pictures. Each has an `id` (`b0006.2` is the second picture of line b0006), the line (`line_text`) and why the plan wants it (`line_reason`), what it should show (`what`, Vietnamese), the sort of picture (`kind`), the requested distinct `aspect` when present, the name of the thing (`entity`, when the plan gave one) and the time the line speaks of (`period`: `"then"` wants a picture made in that time, `"now"` a photograph of today), what the line does (`kinds`, when the plan gave it: an `outside` line wants the thing itself, a `journey` line a map of its `places`), the words that were searched, `sheet` (the contact sheet to open) and `candidates` (at most eight): each with its `n` (the number on the sheet), `title`, `source`, `author`, `licence`, `flag`, size, `page_url`, and `media` (`image` or `video`; for a video the sheet shows a still). A candidate that Wikipedia or the web found also has `page_title` (the article or page it was found on), `site` (the website's name) and `snippet` (a few words about it: read them, they often name the picture); the licence of a web picture is unknown (`flag`: `unknown`). A map has no sheet: its candidate is a place, with its title. |
| `images/w_<id>.jpg` | The **contact sheet** of a wanted picture: its candidates as numbered thumbnails. |
| `images/books_<k>.jpg` | Contact sheets of the pictures in the owner's own books about this painting, numbered **B1, B2 ...** (listed in `inputs/wants.json`, `books`). Any wanted picture may pick one of them. |
| `inputs/regions.json` | The regions used by the plan (new ones and any non-tight existing ones), each with `thing` (English), `what` (Vietnamese), the lines that use it, `cutout_size` `[w, h]`, and `cutout`: the file `images/d_<NAME>.jpg` — cut from the full-resolution painting (+15% margin, inside the painted surface), scaled to 1,024 px long side, with a 100-px coordinate grid in the cut-out's own pixels. |
| `images/main.jpg` | The main painting. |
| `inputs/narration.json`, `inputs/facts.json`, `inputs/dossier.json`, `inputs/painting.json` | As in the earlier session. |
| `out/` | Where you write `choice.json`. `look/` is where `{{CROP_CMD}}` writes crops. |

## 3. What a good choice is

For each wanted picture, open its contact sheet, read the candidates' details and the line it is for, and ask:

1. **Does it show the thing itself?** The named work, the named person, the named place, the named document, not something near it. If the line is about the painter, a portrait of *that* painter; if it names a work, a picture of *that* work. A picture that is "about" the topic (a diagram, a cartoon, a book cover, a map of something else, a collage, a modern artwork inspired by it) is not the thing.
2. **Prefer a public-domain reproduction of the named work** (a photograph or high-quality scan of the work itself: Google Art Project scans, museum open-access images) **over illustrations or pictures about it.** Prefer a full, clean, large picture to a crop, a photograph of a gallery wall with other things in it, a watermarked or captioned image, a small image, or one dominated by a frame.
3. **A line about the past wants a picture made in that period.** If the line speaks of the 15th century, the best picture is one made then: a painting, a drawing, a print, a manuscript page, a coin, a seal, an object in a museum. Prefer it to a modern photograph, a reconstruction, a film still or an illustration drawn recently. A **photograph of today** is right when the want says `"period": "now"`, for a building or an object that survives (a cathedral, a coin in a museum case), or when nothing else shows the thing; then say in the reason that it is a photograph of today. The title, the page it was found on (`page_title`, `site`) and its `snippet` tell you what a picture is and from when: read them, and open the sheet to check.
4. **Never a watermarked picture.** A stock agency's stamp, a print shop's name or a repeating mark across the image makes it unusable, however right the subject: look at the thumbnail, and answer for another candidate or `null`.
5. **A flagged picture** (`flag`: `rejected` = restricted licence, `unknown` = licence unknown, `small`) is a last choice: pick it only if nothing unflagged shows the thing, and say so in the reason. The owner sees the flag too. A picture found on the web always has `flag: unknown`; that alone does not make it a bad choice when it is plainly the thing, but a picture from Wikipedia, a museum or another picture source with a known licence wins when both show it equally well.
6. **A picture of a place** must be that place: read the title and the author's words, and look at the image; a different town with a similar name is wrong. **A map** must be a map of the place the line means (a title like "Bản đồ Oslo" for Oslo in Norway: if the narration means another Oslo, answer `null`).
7. **A clip** must show what the line is about, not just something moving; stock footage rarely fits a specific work or event, so `null` is a normal answer for a clip.
8. **A picture of the owner's books (B1 ...)** is the owner's own: very often exactly right for a detail, an X-ray, a related work or a portrait that the book prints. Use one when it is exactly right. **Never use the main painting itself** (a full view of it) for a context line: a context line shows something *other than* the main painting.
9. **When two candidates are right**, take the better reproduction. **When you are not sure**, answer `null`: say what you saw and why it is not enough.
10. **Say in the reason what the picture is and from when**, in Vietnamese and in one short sentence: "Chân dung Philip the Good do Rogier van der Weyden vẽ khoảng năm 1450." or "Ảnh chụp hôm nay của nhà thờ Noyon, vì không có hình nào thời đó." The owner reads it to see at once why this picture is on screen.
11. **Older plans may have wider-search candidates marked step 2 or 3.** For a subject-bound want, a candidate is right only when it shows that same subject, never merely something similar. A photograph of an actual historical object in a museum still depicts that historical object; classify a modern photograph of people or places as modern. A modern image may be chosen only after no usable period image exists.

For each **region** in `inputs/regions.json` (the second look at full resolution):

Open its gridded cut-out (`images/d_<NAME>.jpg`), read `thing`, `what`, `cutout_size`, and the lines that use it. Measure in the **cut-out's own pixels** (using the 100-px yellow grid along the top and left edges — never convert to the main painting's coordinates, the program does that for you):

- `tight`: give `box: [x0, y0, x1, y1]` in cut-out pixels (`0 <= x0 < x1 <= w`, `0 <= y0 < y1 <= h`). **Its edges touch `thing` itself, with NO air around it** — do not include neighbouring objects or half the rough box when the thing is smaller. Do not set `confirmed` on your first pass (leave `confirmed` out or `false`).
- `wider`: ONLY if `thing` is partly cut off by the edge of the cut-out. Give a short Vietnamese `reason` and run `{{CHECK_CMD}}`; the program writes one wider cut-out enlarged +40% (`look/d_<NAME>_wider.jpg`). Open that wider cut-out and answer `tight` (or `drop`) in the wider cut-out's pixels. Only one `wider` request per region is allowed.
- `drop`: ONLY if `thing` is not actually inside the painting/cut-out at all (never drop just to keep a loose frame). Give a Vietnamese `reason`; lines using it fall back to the whole painting.

**Check sheet verification (mandatory before a region becomes tight):**

1. After you give `tight` (and no region waits on `wider`), run `{{CHECK_CMD}}`. The program draws every tight box as a bright green rectangle on a clean cut-out (no grid) and tiles up to 6 per sheet (`look/check_1.jpg`, `look/check_2.jpg`, ...), labelled with region name and stored pixel size.
2. **Open every `look/check_*.jpg` sheet.** Inspect each green rectangle against `thing`:
   - If the green box fits `thing` tightly with no air and clips nothing important, add `"confirmed": true` to that region in `out/choice.json`.
   - If the green box is slightly off, you may give a corrected `box` **once** together with `"confirmed": true` (or answer `drop`).
3. Run `{{CHECK_CMD}}` again until it prints `0 error(s)`. Any region never confirmed after inspecting a check sheet is NOT stored as tight.

Never answer a box you have not measured on its cut-out, and never confirm a box you have not visually checked on `look/check_*.jpg`.

## 4. The choice format (`bti.picks.choice/1`)

```json
{"schema": "bti.picks.choice/1",
 "wants": [
   {"id": "b0003.1", "pick": 2, "shows_subject": true, "period_picture": true,
    "reason": "Bản chụp chính bức chân dung của họa sĩ, rõ nét, thuộc phạm vi công cộng."},
   {"id": "b0005.1", "pick": null,
    "reason": "Cả sáu hình đều là bản đồ của vùng khác, không phải Venice."},
   {"id": "b0009.1", "pick": "B3",
    "reason": "Hình trong sách của bạn in đúng bản chụp tia X của bức tranh."}],
 "regions": [
   {"name": "BELL_TOWER", "action": "tight", "box": [298, 162, 398, 392], "confirmed": true,
    "reason": "Khung sát tháp chuông ở xa, bỏ phần mái nhà và mây xung quanh."},
   {"name": "WRONG_DETAIL", "action": "drop",
    "reason": "Chi tiết này không có trong vùng tranh như lời dẫn nêu."}]}
```

- `wants`: one entry for each wanted picture. For each selected subject-bound picture include `"shows_subject": true` after checking the image and its record, and for a subject-bound context picture include `"period_picture": true` (or `"period_picture": false, "no_period_picture": true` when choosing a modern photograph after confirming no usable period picture exists). `pick`: the **number** of a candidate on that picture's own sheet, **`"B<number>"`** for a picture of the owner's books, or **`null`** when none is right. `reason`: one short Vietnamese sentence: why this picture shows what the line says, or why none does.
- `regions`: one entry for each region in `inputs/regions.json`. `action`: `"tight"` (with cut-out pixel `box` `[x0, y0, x1, y1]`, and `"confirmed": true` after checking `look/check_*.jpg`), `"wider"` (once, with Vietnamese `reason`), or `"drop"` (with Vietnamese `reason`).

## 5. The two helper commands

Run them from this folder. Each prints what it did; each has `--help`.

- **Check** your file: `{{CHECK_CMD}}`. It reads `out/choice.json` exactly as the program will, and prints `ERROR` lines (fix them). Repeat until it says `0 error(s)`.
- **Crop** the main painting: `{{CROP_CMD}} --box 0.40,0.10,0.62,0.30 -o look/head.jpg` cuts that box out of the painting and writes it (inside `look/`); open the file to look at it.

If a command fails to start, say so in a line of your last message and carry on by reading your own file carefully: do not look for another way to reach the program. When the check says `0 error(s)`, you are done: write one sentence of what you did as your last message.
