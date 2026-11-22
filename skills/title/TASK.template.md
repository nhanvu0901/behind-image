# Task: write the title of a video about one painting

You work for the channel **{{CHANNEL}}**, which makes twelve-minute videos, each about one painting. The narration of
this video is written and approved; it is in `inputs/narration.json`. You write the video's **title**: the one line a
stranger reads before deciding to watch, and the line that appears on screen under the channel's name after the cold
open, written by a sweep of light.

You write one JSON file, `out/title.json`. The owner sees your first choice on the video and your other candidates on
the page, and may pick another one.

Your folder holds three files to read (this paragraph is about files, not about rules): `inputs/narration.json` (the
narration, line by line, with the ids you cite), `inputs/outline.json` (the thesis and the opening hook the outline
chose) and `inputs/painting.json` (the painting's title, painter and year). The last two only help you see what the
video is about; a word that is in them and not in the narration is never used in a title (rule 3).

## 0. Your task in numbers
- The painting: **{{TITLE}}** by {{ARTIST}}, {{YEAR}}. The narration: {{N_LINES}} lines in {{N_CHAPTERS}} chapters.
- At most **{{MAX_STEPS}} steps** and **{{MAX_MINUTES}} minutes**.
{{#OWNER_NOTE}}
- **The owner's request for this title**, in their own words: {{OWNER_NOTE}}
{{/OWNER_NOTE}}

## 1. What the title is for
The person who sees it has never seen this painting, does not know the painter and did not come for art history. The
title has one job: **make that person want the answer.** It does this by naming, in words anyone can picture, the most
surprising TRUE thing this video shows. It is a promise, and the video must keep it: a viewer who clicks and does not
get what the title promised leaves, and the channel pays for it.

## 2. Rules, and why each one exists
1. **Work only inside this folder**; write only `out/title.json`; run `{{CHECK_CMD}}` until it prints `0 error(s)`.
2. **Read the whole narration before you write a word.** The title comes from the video, not from the painting's
   fame or from what you know about it. Why: a title about something the video does not show is a lie to the viewer.
3. **Every word is true to the narration.** Each candidate lists the lines (`lines`, their ids) that make it true.
   What the narration leaves uncertain ("probably", "could be", "maybe") is never stated as a
   fact in a title; a question or "might" keeps it honest. Nothing is taken from outside the narration. A title that
   is true to the letter and leaves a false picture is a lie too ("I Bought a Ferrari for $1", said over a toy car):
   if a viewer who believed the title would be wrong about what the video shows, strike it.
4. **Concrete words.** At least one thing a person can picture: a saint, a ring, a skull, a shop sign, a poisoned
   cup. Two abstract labels set against each other mean nothing to someone who has not watched yet.
5. **It stands alone.** No painter's name, no painting's title, no date is needed to understand it (the small line
   under the title carries those, and the program writes it). A name everyone knows may be used when the narration
   turns on it.
6. **It opens a gap and does not close it.** After reading it one must want to know how or why. Do not give the
   whole answer away; do not be so vague that the line could sit on any video ({{VAGUE_PHRASES}} are never titles here).
7. **No borrowed excitement.** No {{BORROWED_WORDS}}, unless the narration itself says exactly that and gives its reason.
   Do not reach for shock — death, secrets, crimes, "forbidden" — when the narration's own question is calmer; let
   the video's real open question carry the intrigue in plain words.
8. **Short and plain.** {{BEST_MIN}} to {{BEST_MAX}} characters is best, {{MAX_CHARS}} is the limit (longer is cut off on a phone and does not fit one
   line on screen); {{BEST_MAX_WORDS}} words or fewer is best (shorter is better; the owner's example below is {{BEST_MAX_WORDS}} words), {{MAX_WORDS_TEXT}} words at most; Title Case; one line; no colon and second half, no brackets, no emoji, no word
   in capitals, at most one question mark, no quotation marks unless the words are written in the painting itself.
9. **The language of the narration.** The reasons you give (`why`) are Vietnamese, with all their accents, one short
   sentence each: the owner reads them.

## 3. How to find it
1. **Collect.** From the narration, note for yourself: the question the cold open asks; the answer the closing gives;
   the five facts a stranger would repeat to a friend, with their line ids; the oddest thing one can SEE in the picture.
2. **Find the tension.** Good titles for this kind of video come from one of these:
   - the video's real open question, where both sides are concrete human things a person can picture (a sacred feast, or a public scandal);
   - two things that should not go together and do (a saint, and an advertisement);
   - something in plain view that nobody notices (a distorted skull stretched across the floor);
   - a small thing with a large consequence (a ring on a pair of scales);
   - something that should not be there, or is wrong (shelves that break the rules of perspective);
   - what the picture really was for (a shop sign, a contract, a bribe, a warning);
   - a number that is hard to believe and is in the narration (a salt cellar worth two hundred years of wages).
3. **Write at least {{WRITE_AT_LEAST_TEXT}} candidates, in at least {{FORMS_AT_LEAST_TEXT}} different forms.** The forms: the contradiction ("The Saint
   Who Was Also an Advertisement"); the question a stranger cannot answer yet ("Why Is a Saint Weighing a Ring?");
   the thing hidden in plain sight ("The Skull Stretched Across the Floor"); what it really is ("This Painting Was a Shop
   Sign"); the object with a past ("The Ring on the Scales"); the hard number. Do not write twelve variations of one.
4. **Test each one against the rules of section 2 and strike every one that fails any rule.** Be strict on rule 3 and
   rule 6: most first ideas fail one of them.
5. **Score the survivors** from 1 to 5 on: `curiosity` (does a stranger want the answer), `concrete` (can one picture
   it), `central` (is this what the whole video is about, or one passing fact), `clear` (understood at first reading).
   A title that scores under {{FIRST_CENTRAL_MIN}} on `central` is not the first choice however curious it is: it would promise a
   sentence, not the video. A title that manufactures shock or clickbait where the narration is calmer scores low on
   `clear` and `central`: it sells a stunt, not the video. Between two honest titles of equal intrigue, the shorter,
   plainer one wins.
6. **Choose.** The highest total is first. Between equals, take the one whose promise the cold open starts to keep
   within the first minute.

## 4. Three real verdicts of the owner (learn from them)
For the video on Petrus Christus's panel of St. Eligius, whose narration asks whether the picture is a prayer or a
shop sign and answers "both":
- **Rejected: "A Prayer or a Shop Sign?"** The owner: "not intriguing or interesting or capture the essence of the
  video". Why it fails: two labels, no thing one can picture; the question means nothing before watching (rules 4, 6).
- **Accepted: "The Saint Who Was Also an Advertisement"**. Why it works: two concrete things that contradict each
  other; it is the video's own answer in one line; it is true to the narration (the saint, the advertisement for the
  goldsmiths, "it is both"); a stranger wants to know how a saint can be an advertisement.

For the video on Paolo Veronese's *The Feast in the House of Levi*, whose narration weighs whether the painting was a sacred
banquet or a public scandal that drew the Inquisition, and closes with "Was Veronese turning a sacred feast into theatre,
or hiding everyday Venice inside a Bible story?":
- **Rejected: "Did This Forbidden Banquet Almost Put Him on Trial?"** (9 words). Why it fails: it reaches for clickbait
  shock ("Forbidden", "Trial") and packs two dramatic clauses into nine words when the narration's own open question is
  calmer and cleaner (rules 7, 8).
- **Preferred direction: "A Sacred Feast or a Public Scandal?"** ({{BEST_MAX_WORDS}} words). Why it works: it holds the
  video's real open tension in plain words, short and clear, with no clickbait; both sides are concrete human moments a
  stranger can picture at once, and the clash between them makes one want the answer.

What separates **"A Prayer or a Shop Sign?"** (rejected) from **"A Sacred Feast or a Public Scandal?"** (wanted): both
have the same "A or B?" shape, but the first sets two dry categories against each other with no human stake, while
the second puts two human scenes — a sacred meal and a public scandal — in tension, so a stranger immediately feels
why the answer matters.

## 5. The file you write
```json
{
  "schema": "bti.title.choice/1",
  "candidates": [
    {"text": "The Saint Who Was Also an Advertisement", "form": "contradiction", "lines": ["b0004", "b0005", "b0060"],
     "scores": {"curiosity": 5, "concrete": 5, "central": 5, "clear": 4},
     "why": "Hai thứ trái ngược mà đều đúng với bức tranh: một vị thánh và một tấm biển quảng cáo."}
  ]
}
```
`candidates`: at least {{MIN_CANDIDATES_TEXT}} and at most {{MAX_CANDIDATES_TEXT}}, the best first (the first one is your choice); every one has passed
every rule; no two say the same thing in other words. `form` is one of {{FORMS_LIST}}. `lines` are ids of narration
lines that make the title true (at least one). The check refuses: a title over {{MAX_CHARS}} characters or over {{MAX_WORDS_TEXT}}
words, a banned phrase of rules 6 and 7 (a word of rule 7 passes only when a line the candidate cites says it too), a
colon or another second half, brackets, an emoji, a word in capitals, more than one question mark, a number in digits
that none of the cited lines holds, an unknown line id, a reason that is not Vietnamese, fewer than {{MIN_CANDIDATES_TEXT}}
candidates (or more than {{MAX_CANDIDATES_TEXT}}), two candidates of the same text, a score outside 1 to 5, and a file that
is not shaped as above. It only warns about a length outside the best range, more than {{BEST_MAX_WORDS}} words, quotation marks, a title that is not in
Title Case, a first choice that is not the highest total or scores under {{FIRST_CENTRAL_MIN}} on `central`, and a
title none of whose words is in the lines it cites.
