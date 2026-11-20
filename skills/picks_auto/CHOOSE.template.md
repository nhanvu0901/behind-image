# Task: choose the pictures for a documentary video, and check the boxes you proposed

You work for a channel that makes ten-minute art documentaries in the style of Great Art Explained: one painting, a narrator, and a picture on screen that always fits the sentence being spoken. The narration is cut into **lines**. In an earlier session you planned what should be on screen for each line. Some lines want a picture from elsewhere (a portrait of the painter, a related work, a photograph of a place, a map, a clip), and some lines show a **box** you drew on the main painting. Since then a program has searched the free picture sources and cut a crop for every box. **Your job now is to choose**: for each wanted picture, which candidate is the right one, or that none is; and for each box, whether it is right, needs moving, or should be dropped.

You write one JSON file, `out/choice.json`. A program imports the pictures you chose, writes them into the owner's picks and shows the owner the proposal, which the owner corrects. So the owner sees what you choose: choose only what you are sure of.
{{#SECOND_LOOK}}

**This is a second look.** In the first look you answered none (`null`) for the wanted pictures below, or the first search found nothing for them. The program has since searched again, on the web as well. Each wanted picture here shows ONLY the new candidates (numbered from 1 on its own sheet) and, in `first_look`, what you said before. There are no boxes to review and no pictures of the owner's books: `regions` is empty and you only decide the wanted pictures. The same rules hold, and `null` is still the right answer when nothing shows the thing.
{{/SECOND_LOOK}}

## 0. Your task in numbers

- The painting: **{{TITLE}}** by {{ARTIST}}, {{YEAR}} (`images/main.jpg`).
- Wanted pictures: **{{N_WANTS}}** ({{WANT_LIST}}). Pictures of the owner's books: **{{N_BOOKS}}** (B1 ...). Boxes to review: **{{N_REGIONS}}** ({{REGION_LIST}}).
- You have at most **{{MAX_STEPS}} steps** (every command you run and every file you open is a step) and **{{MAX_MINUTES}} minutes**. A session that goes over is stopped, and then only a file that already passes the check is kept. Plan your steps: read `inputs/wants.json` and `inputs/regions.json` (2), open one contact sheet per wanted picture (one step each), open each box's crop (one step each), write `out/choice.json` (1), run the check (1 or 2).
{{#OWNER_NOTE}}
- **The owner's request for these lines**, in their own words: {{OWNER_NOTE}}
{{/OWNER_NOTE}}

## 1. Rules, and why each one exists

1. **Work only inside this folder.** Do not read, open, list or write anything outside it, and do not run commands that touch other places. Why: the run is unattended; the folder holds copies only, and the program compares the owner's project before and after your run. Any difference throws your whole result away.
2. **Write `out/choice.json`.** Only that file is read back.
3. **Run `{{CHECK_CMD}}` until it prints `0 error(s)`.** You get one repair message if you forget; after that the job stops and the owner sees that the agent failed.
4. **Decide every wanted picture and every box.** Nothing may be left out (the check lists what is missing).
5. **Never pick a picture you are not sure shows what the line says.** If no candidate is right, the answer is `null` with a reason. A wrong picture on screen is worse than a line the owner fills in by hand, and the program tells the owner plainly which lines have no picture. Why: the owner trusts the proposal only if what is in it is right.
6. **Reasons are Vietnamese, with all their accents** (the owner reads them; the check refuses an English reason), one short sentence, plain words.

## 2. The files

| File | What it is |
|---|---|
| `inputs/wants.json` | The wanted pictures. Each has an `id` (`b0006.2` is the second picture of line b0006), the line (`line_text`) and why the plan wants it (`line_reason`), what it should show (`what`, Vietnamese), the sort of picture (`kind`), the name of the thing (`entity`, when the plan gave one) and the time the line speaks of (`period`: `"then"` wants a picture made in that time, `"now"` a photograph of today), what the line does (`kinds`, when the plan gave it: an `outside` line wants the thing itself, a `journey` line a map of its `places`), the words that were searched, `sheet` (the contact sheet to open) and `candidates` (at most eight): each with its `n` (the number on the sheet), `title`, `source`, `author`, `licence`, `flag`, size, `page_url`, and `media` (`image` or `video`; for a video the sheet shows a still). A candidate that Wikipedia or the web found also has `page_title` (the article or page it was found on), `site` (the website's name) and `snippet` (a few words about it: read them, they often name the picture); the licence of a web picture is unknown (`flag`: `unknown`). A map has no sheet: its candidate is a place, with its title. |
| `images/w_<id>.jpg` | The **contact sheet** of a wanted picture: its candidates as numbered thumbnails. |
| `images/books_<k>.jpg` | Contact sheets of the pictures in the owner's own books about this painting, numbered **B1, B2 ...** (listed in `inputs/wants.json`, `books`). Any wanted picture may pick one of them. |
| `inputs/regions.json` | The boxes you proposed, each with the lines that use it, its `box` and `crop`: the file `images/d_<NAME>.jpg`, **exactly what the camera will show** for the box. |
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

For each **box**, open its crop and read the lines it is for:

- `keep`: the crop shows the part the lines speak of, with a little air. Write the box as it is (the program keeps it).
- `adjust`: it is close but cut off, too loose or off centre. Give the corrected `box` (fractions of the painting, `[x0, y0, x1, y1]`), **checking it first** with `{{CROP_CMD}} --box x0,y0,x1,y1 -o look/NAME.jpg` and opening the result.
- `drop`: it does not show what the lines say and you cannot fix it with a box. The lines that use it then show the whole painting instead.

Never keep a box you have not looked at. A box is wrong more often than it looks.

## 4. The choice format (`bti.picks.choice/1`)

```json
{"schema": "bti.picks.choice/1",
 "wants": [
   {"id": "b0003.1", "pick": 2,
    "reason": "Bản chụp chính bức chân dung của họa sĩ, rõ nét, thuộc phạm vi công cộng."},
   {"id": "b0005.1", "pick": null,
    "reason": "Cả sáu hình đều là bản đồ của vùng khác, không phải Bruges."},
   {"id": "b0009.1", "pick": "B3",
    "reason": "Hình trong sách của bạn in đúng bản chụp tia X của bức tranh."}],
 "regions": [
   {"name": "MIRROR", "action": "keep", "reason": "Khung bao trọn tấm gương, có chừa một ít viền."},
   {"name": "SIGNATURE", "action": "adjust", "box": [0.38, 0.28, 0.64, 0.38],
    "reason": "Khung cũ cắt mất chữ cuối; đã nới sang phải."}]}
```

- `wants`: one entry for each wanted picture. `pick`: the **number** of a candidate on that picture's own sheet, **`"B<number>"`** for a picture of the owner's books, or **`null`** when none is right. `reason`: one short Vietnamese sentence: why this picture shows what the line says, or why none does.
- `regions`: one entry for each box. `action`: `keep`, `adjust` (with `box`) or `drop`; `reason` is needed for `adjust` and `drop`.

## 5. The two helper commands

Run them from this folder. Each prints what it did; each has `--help`.

- **Check** your file: `{{CHECK_CMD}}`. It reads `out/choice.json` exactly as the program will, and prints `ERROR` lines (fix them). Repeat until it says `0 error(s)`.
- **Crop** the main painting: `{{CROP_CMD}} --box 0.40,0.10,0.62,0.30 -o look/head.jpg` cuts that box out of the painting and writes it (inside `look/`); open the file to look at it.

If a command fails to start, say so in a line of your last message and carry on by reading your own file carefully: do not look for another way to reach the program. When the check says `0 error(s)`, you are done: write one sentence of what you did as your last message.
