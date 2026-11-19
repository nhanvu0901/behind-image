# Second review of the restored Grovier text: work 2 redone and the 48 names changes (`grovier_nws`)

Date: 2026-11-19. Reviewer: worker `grovreview2` (independent of the restorer and of the first reviewer). Records:
`library/restored/grovier_nws/review_pass2.json` (78 findings, per-work counts). Fixes: `review_pass2_fixes.json` (7 exact
replacements, each `find` occurs once in its page; nothing was applied by me). The first review is `docs/qa/REVIEW_grovier_restored.md`.

## 1. The answer

- **Work 2 (The Parthenon Sculptures): `usable_after_fixes` (was `not_usable`).** It is now a real restoration. No sentence, name,
  date or number was added; 16 passages (780 characters, 19.8 percent of the prose; before 4 and 3.8 percent) are marked where the
  machine text is garbled, none smoothed; 10 of the 11 name pairs are right on evidence. One pair is not verified: `Pantry => Phidias`
  (see section 2). Apply fix G001 (mark `Phidias's` as unclear) and it is usable. Conditions: speak no quotation (Keats, Wordsworth and
  Severn are back-translations; two Keats phrases are verifiably not his words); the plate caption on page 0027 is still mangled.
- **The 48 changes: 47 right, 0 wrong, 1 unsure (C029).** All 36 pages equal their backup plus exactly the listed changes; nothing else
  on any page changed. 28 are corrections (25 rest at least partly on a web reference, 3 on the book's own pages), 20 are passages
  wrapped as unclear (all really garbled; nothing readable lost, the text stays inside the marker).
- **Work 12 (citron): right.** Every `fragrance` that meant the citron is now `citron` or `etrog` in unmarked prose or is inside a marker
  (the 4 remaining `fragrance` words are each inside a marker). Work 12 can move to `usable`.
- **Verdicts from the first review:** work 2 changes (above); work 12 can become `usable`; no work should be lowered. Work 54 stays
  `not_usable` only because of its lost closing argument: its marked share is 32.7 percent by a plain count, not 46.6 (section 3).
- **Counts:** the pages hold **1,135 passages and 61,769 marked characters**; `report.json` sums to 1,104 and 60,779 (18 works stale, listed in the JSON).

## 2. The `unsure` and `wrong` findings

1. **`Pantry => Phidias` (work 2, page 0024), unsure, low confidence.** Basis claimed: own knowledge. The book does not support it:
   the index (pages 0406-0421) has no Phidias and no Pantry, although it lists Elgin, Keats, Severn, Wordsworth and Pericles on print
   page 19; `Fiedras 48` in the index is Phaedrus (page 0069: "the Roman poet Fedras"). `Pantry` does not sound like Phidias, while the
   machine's other garbled names in this chapter follow the sound. Wikipedia credits the Parthenon sculpture to Phidias's workshop only
   as a possibility. Missing: the original English sentence. Fix G001 wraps the name; it does not assert it is wrong.
2. **C029 (work 20, page 0145), unsure.** `Julius Library` was wrapped as unclear. It may be exactly right (the Stanza della Segnatura was
   Julius II's library, where the Pope signed documents, as the parenthesis says). Harmless; missing: the original sentence.
3. **Residual, not a wrong change: page 0357 (work 53).** After C048 the caption sentence "two years after the first show of Campbell's
   Soup Cans in 1962, Andy Warhol created a series of 32 ... paintings" reads fluently but is false (the 32 paintings are the 1962 show;
   MoMA). Fix G005 marks it. Also unsure and left: `in the Episode` (page 0092, probably Eve's panel) and `The monks of Volmar;`
   (page 0077). The name Volmar itself is right.

**Special care, as asked.** *Work 12:* C012 (`now called citron`), C013, C015 (`etrog`) are right on the chapter's own clues ("near-relative of
a rare lemon", "not an apple", "Adam's Apple", "trog", bitter, aroma) and on Snyder 1976 / museum guides (web, secondary summaries);
C011, C014, C016, C017 keep or widen markers for places where `fragrance` may be a scent or incense; none of the four remaining
`fragrance` words is outside a marker. *Page 0350 (C046):* right. The chapter heading on page 0347 reads exactly "Study after Velazquez's
Portrait of Pope Innocent X"; the notes and index carry machine forms of the same title; digits unchanged. The restorer is also right that the tool's own
check (a structural line may change only by a name, similarity at least 0.75; this edit scores 0.72) would reject it, so a forced re-run of work 52 would undo it:
protect that page or apply the change again. *Corrections resting on the restorer's knowledge alone* (Whistler's Black Lion Wharf, Matisse's Joy of Life, Society of
Independent Artists, Campbell's Soup, sibyls, Seurat's remark, mahlstick): all checked, all right (web or the book's own pages).
*Weak spots even where right:* C047 drops the fragment `-nose` (probably the soup flavour); C002 `a pasta painting` is wrapped while C046 corrects
the same machine word, so treatment is inconsistent but safe.

## 3. Counts (from the pages as they stand, tool's marker pattern)

| Item | Number |
|---|---|
| Marked passages / characters, now | 1,135 / 61,769 (before pass 2: 1,105 / 60,658; first review: 1,092 / 60,145) |
| `report.json` | 1,104 / 60,779 (stale for works 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 18, 20, 26, 32, 35, 38, 39; work 2 is current) |
| Marker on a plate page, unbalanced marker | 0, 0 |
| Share of all prose marked | 21.7 percent (first review's method: 23.6) |

I reproduced the first review's 57 prose lengths and shares exactly, and found its method: it counts the marked characters of all
paragraphs but leaves out of the prose total every paragraph that **begins** with a marker (work 54: 1,304 characters), so its shares are
too high (work 54: 46.6 against 32.7 plain; work 20: 37.8 against 24.7; work 55: 48.9 against 37.0). Both measures are per work in the JSON.

| Work | Passages | Marked chars | Plain share % | First-review method % | First review % |
|---|---|---|---|---|---|
| 2 | 16 | 780 | 19.8 | 19.8 | 3.8 |
| 55 | 23 | 1,954 | 37.0 | 48.9 | 48.9 |
| 51 | 31 | 1,927 | 36.7 | 40.5 | 40.5 |
| 56 | 19 | 1,504 | 34.7 | 41.8 | 41.8 |
| 54 | 21 | 1,427 | 32.7 | 46.6 | 46.6 |
| 35 | 27 | 1,714 | 34.1 | 39.0 | 35.6 |

**No work newly passes the first review's line.** By its own method the works at or above 40 percent are 51, 54, 55, 56, as before (pass 2
did not touch them); the nearest below are 35 (39.0, from review fix F027) and 20 (38.2). Work 55 was already above work 54 and was judged
usable (thin), so the percentage cannot be a hard line. The largest move from pass 2 is work 2 (3.8 to 19.8), then work 9 (12.8 to 15.6).

## 4. Fixes (`review_pass2_fixes.json`)

G001 mark `Phidias's` (work 2). G002-G004 plate caption of work 2 (Marc Quinn, Alison Lapper Pregnant, Trafalgar Square; the plate rule copies
plates, so optional). G005 mark the Warhol sentence (page 0357). G006-G007 `lasagna` to `oil on canvas` on body-page captions that pass 2 missed
(Demoiselles d'Avignon, page 0276; Monet, page 0299). Page 0191 (plate, `Pasta Painting`) is noted, not fixed. After applying, the unclear
counts in `report.json` need updating (G001 +1 passage, 11 characters; G005 +1, 159).

## 5. What I could not check; what each verdict rests on

- **The original English text** was not found online, so "faithful" means faithful to the machine text. The place of the British consul in
  work 2 ("in Kythera"), the book's own dates (444 B.C., about 1165, about 1410), the number "thirty ancestors", "24 scenes" in work 12 and every
  interpretation are the book's claims and were not tested. I did not re-read the other 51 works, the content of the 1,135 marked
  passages, or the closing argument of work 54.
- **The book's own pages:** Pericles (index "Berkeley 19"), Severn (index "Joseph Sevan 19"), Erechtheus (endnote Connelly 1996), Lord Elgin, Volmar, Scivias,
  Book of Divine Works, citron (same chapter), Bacon's title (chapter heading), Matisse (credits and index), `lasagna` = oil on canvas (Guernica caption).
- **A web reference** (Wikipedia, museum and library pages, Hudson Review, Bryn Mawr Classical Review, Smarthistory, MoMA, Barnes, V&A, Britannica;
  several are secondary summaries, and I did not open Snyder 1976 itself): Eglen (one page only), Kythera, Severn's words, Keats's sonnet title,
  Scivias and Liber divinorum operum, Stone of Unction, Fra Angelico's Deposition (dates differ by source), sibyls, Laura Cumming's words, mahlstick,
  Black Lion Wharf, Seurat's remark (second hand), La Grande Jatte size, Joy of Life, Society of Independent Artists, McKeeby, Hattie, Campbell's Soup I and the 1962 show.
- **My own knowledge alone:** only the wording of some wraps (that mule trains, Sanctuary = altarpiece, Goya's easel self-portrait are likely meanings) and C029; none of these is used to assert a reading.
- **Judgement, not evidence:** that a wrapped passage "really was unclear" rests on reading the passage (19 of 20 wraps).
