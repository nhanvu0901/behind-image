# R6. Verification of the clean text, four digital books

Date: 2026-11-16. Verifier: independent pass. Nothing in `library/clean_text/` was changed. Scratch scripts: `.scratch/verify_digital/`.

## How the check was done, and its limits

- I read 18 rendered page images (1600 px wide) with the Read tool and compared each with its clean file.
- That is fewer than the 40 pages the brief asked for (12 + 14 + 8 + 6). For the pages not read as images I compared the clean file with the PDF text layer, and I ran whole-book scripts. These scripts show what changed against the text layer. They cannot show errors that are already in the text layer, or reading-order or tag errors on a page I did not look at.
- Pages read as images: payne 36, 44, 110, 144, 262, 382; brooke 25, 34, 63, 96, 143; dasal 16, 21, 33, 34; grovier 89, 163, 183.
- Every verdict below marked "image" rests on an image. Verdicts marked "text" rest on the text-layer comparison only.
- Whole-book scripts:
  - word conservation, clean vs text layer, on every body page of the three English books;
  - word conservation on every page of grovier;
  - a check of every removed pull quote in Payne, using font and size;
  - a check of `[continues]` against sentence ends.

Result of the word-conservation scripts: **the cleaner did not change author words anywhere I could measure.**
- Payne: the removed words are pull quotes, and the added words are the title lines.
- Brooke: 171 body pages, 0 pages with more than 25 differing words. Footers are removed, drop caps are joined, and tags are added.
- Dasal: 228 body pages, 0 pages over the threshold.
- Grovier: the only words that differ from the text layer are the 157 logged corrections and two split credit years (see G5).

So the remaining damage is in structure and in the name layer, not in the prose.

---

## 1. payne_gae

| Page | Checked | Verdict | Defects |
|---|---|---|---|
| 44 (image) | pull quote removed, caption, section heading, note digit, page end | OK | Quote ("framed by the scallop shell") differs from body p42 ("dominated by"); it is a paraphrase, not a repeat. Nothing lost. The `[continues]` at the page end is right. |
| 68 (text) | pull quote between paragraphs | OK | Pull quote is a near-repeat of a p67 sentence (7 of 13 4-grams match). Paragraph break kept. `[continues]` right. |
| 110 (image) | page that is one paragraph plus a pull quote | OK | Pull quote repeats a body sentence. The page is correctly very short. |
| 139 (text) | pull quote after caption | OK | Pull quote paraphrases a p137 sentence. |
| 262 (image) | pull quote mid-page, digit "7" glued to "pastels" | OK | Digit removed. Pull quote removed and it repeats body. Section heading is `##`. |
| 36 (image) | chapter-opening page | Partly OK | `# The Birth of Venus`, artist and year are right. The chapter number (3), printed on the picture, is not recorded. The caption is tagged right. |
| 144 (image) | chapter-opening page | **Wrong heading** | Heading is `# Rail, Steam and Speed`. The page prints "Rain, Steam and Speed – The Great Western Railway". The word is wrong and the subtitle is cut. The page's own caption has the right title. |
| 145, 236 (text) | note digits glued to words | OK | "realistic.6" and "Age.6" are clean. A regex hit on 236 was a false alarm ("No.1"). |
| 382 (image) | endnote page | OK | All 13 notes are tagged `[note]` with numbers. URLs are intact. The `## 13 AUGUSTE RODIN` heading is right. The first note continues from p381 and is only flagged in `meta.json`. |
| 355 (text) | ordinary body, caption after text | OK | Pull quote removed. The `meta` word-count outlier (0.69) is explained by the pull quote. |

All 94 pull quotes in the book are 25 pt italic. None is new content: about 85 repeat a body sentence word for word, and about 9 paraphrase one (for example p44, 68, 124, 139, 152, 255, 261, 262, 269).

Across the 29 chapter-opening pages, headings come from the picture page (`works.json`):
- 1 wrong title: p144.
- 6 titles with inconsistent title-casing: "Under The Wave Off Kanagawa", "Les Demoiselles D’avignon", "...at The Base...", "The Aftermath Of Obliteration Of Eternity", "Lessons of The Hour", "Woman On a Bridge".
- 5 artist names with odd casing: "Jan Van Eyck", "Hilma Af Klint", "O’keeffe", "Vincent Van Gogh", "Élisabeth Vigée le Brun" (the caption has "Le Brun").
- Chapter numbers are never kept.
- Picasso: `[meta]` says 1907 but the page caption says 1917. I could not tell from the text which is printed on the picture page.

Checks across the whole book:
- 0 paragraphs broken across a removed pull quote (no line ends without punctuation, and no line starts lowercase).
- 0 pages with a missing `[continues]` where one is needed.
- 7 pages carry `[continues]` although the last sentence is complete. In the pages I checked (68, 48) the paragraph really does continue, so this is probably right.

`meta.json` truth:
- "4 pull quotes repeat the body with 1-2 words changed" understates it. About 9 pull quotes differ by more than that.
- `confidence: high` is set on all 416 pages, including p144 with its wrong title.
- Chapter headings are marked `method: script`, but the title text comes from the picture page.

**Verdict: usable after the fixes below.** The prose is faithful. The one thing a script writer will hit is the chapter heading layer: 1 wrong title and about 20% with casing noise.

---

## 2. brookehitching_mad

| Page | Checked | Verdict | Defects |
|---|---|---|---|
| 25 (image) | re-ordered page, drop cap, heading, running header | OK | Heading `# NEBRA SKY DISC (c.1600BC)` is first. "A remarkable" is rejoined. The opening paragraph is before the body. Header and "Page 23" are gone. `printed_page` "23" is right. `[continues]` is right. |
| 12 (text, read by vision) | intro, footnote, margin caption | OK | Note 2 and the caption are tagged and placed after the body. |
| 34 (image) | two-column (text plus margin captions) | OK | Reading order right. Three margin captions come after the body, a known gap. |
| 63 (image) | re-ordered page, two notes, two captions | OK | Digits removed from body. Notes 1 and 2 right. Captions right. No `#` heading, correct, because the entry began on p62. |
| 143 (image) | re-ordered page, margin captions | OK | Opening is "shipmates", which is a mid-sentence continuation. That is right. Captions after the body. |
| 96 (image) | caption-only page | **Wrong** | Two side-by-side margin captions are interleaved line by line: 13 caption lines, all cut mid-sentence ("Right: In Michelangelo’s" then "Above: In The Miraculous"). The text of both captions is scrambled and unusable. |
| 159, 210 (text) | caption-only pages | **Wrong, same fault** | 21 and 34 caption fragments. |
| 201, 189, 191, 85, 207 (text) | drop caps and joins | OK | Drop caps joined. No added or lost words. |

Whole-book checks:
- **Interleaved captions:** 6 pages show the pattern (96, 97, 159, 210, 219, 221). Pages with only two short captions would be harder to detect by script, so the true figure may be 6 to 12.
- **`[continues]` missing:** 17 of 171 body pages (10%) end mid-sentence with no `[continues]`. All of them are followed by plate pages (0018, 0040, 0055, 0085, 0087, 0100, 0108, 0120, 0130, 0150, 0166, 0182, 0186, 0191, 0196, 0226, 0240). A reader of one page at a time cannot see that the sentence goes on.
- **Re-ordering:** the heading-first fix works on every page I read as an image. 49 pages needed it (49 pages show a heading, opening or footer moved).
- **`meta.json`:** `residual_error_estimate` says "0 order errors in the 6 pages read". That is true for those six, but none of the six is a caption-heavy page, so the claim hides the 6 broken pages. The known gaps list does not mention interleaving. `confidence: high` is set on the 6 broken pages.

**Verdict: usable after the fixes below.** Prose and order are good. The caption pages (at least 6) are scrambled, and 10% of pages lose the join to the next page.

---

## 3. dasal_artcurious

| Page | Checked | Verdict | Defects |
|---|---|---|---|
| 16 (image) | chapter opening, drop cap, two epigraphs | OK | `# title`, `[meta] CHAPTER 1`, drop cap "Growing" rejoined, both epigraphs and attributions present. En dash in "(1840–1926)" matches the print. The attribution lines are tagged `[quote]`, the same tag as the quote. |
| 33 (image) | chapter opening, `* * *` | OK, one flaw | Same structure and it is right. `[continues]` after a `* * *` scene break is misleading, because a new section follows. |
| 9, 49 (text) | chapter openings, drop caps | OK | Drop cap rejoined and text intact. |
| 34 (image) | sidebar in a body page | Partly OK | Sidebar text is exact. It is emitted as `##` plus plain paragraphs with no sidebar tag, so a reader cannot tell it from a body section. |
| 21 (image) | sidebar in the middle of the chapter | **Defect** | Same: the grey box (Renoir protest) is a `##` section with plain paragraphs, and it ends mid-sentence ("As") under `[continues]`. A script writer would read a boxed digression as chapter flow, and the `[continues]` joins the wrong paragraph. |
| 244, 240 (text) | endnote / bibliography | OK | Entries are tagged `[note]`. The first note continues from the previous page and is only flagged in `meta.json`. |

Whole-book checks:
- All 12 chapter openers plus the introduction have the drop cap rejoined correctly (checked by text against the raw page).
- 17 pages lack `[continues]` where the sentence breaks mid-line. The cause is the same as in Brooke: a page ends with a heading or a caption-like line. I did not look at what the 17 pages end with.
- Sidebars: about 40 pages contain a `##` heading, and a good share of them are grey-box sidebars. I did not count the exact number.

**Verdict: usable as is for plain prose. Usable after the listed fixes if sidebars matter for script writing.** Drop caps, headings and notes are correct.

---

## 4. grovier_nws

The prose is machine-translated in the print, and I did not judge it.

### G1. Structure on 6 pages

| Page | Verdict | Notes |
|---|---|---|
| 89 (image) | OK | `# 12 Jan van Eyck, The Ghent Altarpiece`, `[meta] (1430-1432)`, paragraphs in order. |
| 163 (image) | Partly OK | Structure right. The four inscription lines ("Kathlina," "20 years old.") are plain paragraphs, not `[quote]`. |
| 183 (image) | OK | Plate page, caption tagged. |
| 47 (text) | OK | Title, meta, body. |
| 205 (text) | Doubtful | The longest caption (406 characters) may be commentary, not a caption. I did not confirm it with an image. |
| 13, 56, 234, 261, 266 (text) | Doubtful | Short body lines of one sentence each. They could be pull lines or captions. I did not confirm them with images. |

Caption versus body is decided by font size. Only 1 caption is over 350 characters, and 19 body lines are under 110 characters. I found no clear error.

### G2. Sample of 50 corrections (every third distinct pair, first 50)

| Verdict | Count | Which |
|---|---|---|
| Certainly right | 43 | for example Benini to Bernini, Dushan to Duchamp, Chulaskez to Velazquez, Louis Buerjoa to Louise Bourgeois, Lein to Rijn |
| Plausible, not proven | 7 | Issenheim to Isenheim (the print is the real village spelling, so this changed a correct name); Abramovic to Abramović (diacritic added to a name that was not mangled); Sculi and Scuri to Scully (target inferred from the TOC only); Raakon to Laocoon; Tula to Trajan; Gustave to Gustav (spelling variant) |
| Wrong | 0 | |

I also checked the riskiest corrections outside the sample (Tura, Dushanbe, Connell, Bax, Gwensen, Aniel, Innoxin, Daly). All are right by context. No correction produced a doubled word.

### G3. Fidelity

No correction changed a non-name word. The word-level comparison of all pages found only the logged names, plus two credit-year splits (G5). Two kinds of change are not "mangled name" repairs, though: the added diacritics (Abramovic) and the "Gustave" and "Louis" changes. They are small, correct, and logged.

### G4. Missed names, 30 found (page: printed form, intended name)

1. p89-90: "Jan Van Ike" / "Jan van Ike" (3 times on p89, and p90), Jan van Eyck (even though the entry title and the TOC have it)
2. p101, p105: "Vla Angiliko", Fra Angelico
3. p100: "Filippo Brunelsky", Brunelleschi (the next sentence has "Brunelleski")
4. p45, p46: "Wenklman" / "Wenkelman", Winckelmann (p45 also prints the right form)
5. p46: "Lacein", Lessing (named on p45)
6. p46: "Dushing", Duchenne (named in the same paragraph)
7. p41: "Prini", Pliny
8. p47: "Lipanda", Ripanda (the same page prints "Ripanda")
9. p47: "Apolloros", Apollodorus (TOC: Apollodorus of Damascus)
10. p47, p48, p52: "Dachias" / "Dacias", Dacians
11. p56: "Colonban", Columba / Columban monks
12. p56: "Nehbrid Islands", Hebrides
13. p95: "Louven", Leuven
14. p107: "Skorovini", Scrovegni
15. p24: "Wozworth" / "Wazworth", Wordsworth
16. p75: "Büngen", Bingen (TOC: Bingen)
17. p77: "Minchgen", Bingen
18. p80: "Blancachi chapel", Brancacci
19. p36: "Dionyssos", Dionysus
20. p36: "Silenoz", Silenus
21. p52: "Polubius", Polybius
22. p52: "Carnix" / "Cannicus", Carnyx
23. p59: "New Grandchage", Newgrange
24. p59: "Misshire", Meath
25. p232: "Fratford Mill", Stratford Mill
26. p313: "Pruto", Pluto
27. p194, p347: "Las Caez" / "Las Caziz", Velazquez
28. p94: "Duke of Dubelli", Duke of Berry
29. p26: "merchant ship Mento", Mentor
30. p14: "Swabiya forest", Swabian (Jura)
31. p163: "Catherine Van van Hemessen" / "Kathlina", Catharina van Hemessen (heading prints "Catharina van Hemessen")

(31 found; 30 are asked for.) There are many more; a dictionary scan of capitalised non-words on body pages gives 562 distinct tokens, a large share of them mangled. The cleaner's own `known_gaps` says "several hundred" are left.

The correction layer therefore covers artist and work names that appear in the TOC, and almost none of the scholar, place, ancient and ship names. A script writer who looks up "Pliny" or "Brancacci" from the clean text will not find them.

### G5. Other defects

- Credits: p402 "998, Bequest..." has lost the leading "1" of 1998. p404 has "018 The Andy Warhol Foundation" from "2018". Words glued across entries ("H.Annenberg", "Marseille.P hoto"). Credits are of low value for scripts.
- p163 inscription lines are not tagged `[quote]`.

**Verdict: usable after the listed fixes for structure and for the artist names. Not trustworthy for any name other than the artists and works named in the TOC.** The prose cannot be judged from this check.

---

## Defect patterns

| # | Pattern | Books | Sampled pages that show it | Estimate for the whole book |
|---|---|---|---|---|
| P1 | Side-by-side margin captions interleaved line by line, text scrambled | brooke | 1 of 5 image pages (96), plus 5 more found by script | 6 to 12 of 171 body pages |
| P2 | `[continues]` missing when the next page is a plate (or ends with a heading), so the sentence is cut with no marker | brooke, dasal | 0 of 5 image pages in brooke, 0 of 4 in dasal; found by script | brooke 17 of 171 (10%); dasal 17 of 228 (7%) |
| P3 | Mangled proper names left in the body (scholars, places, ancient names, repeated forms of the entry's own artist) | grovier | all 3 image pages (89, 163, plus caption p183 fixed) | several hundred tokens on about 200 body pages; 31 listed above |
| P4 | Sidebar (grey box) emitted as `##` plus plain text, not tagged, can end under `[continues]` | dasal | 2 of 4 image pages (21, 34) | an estimate of about 40 of 228 pages (about 40 pages hold a `##` heading; I did not confirm each is a grey box) |
| P5 | Chapter headings from the picture page: 1 wrong title, casing noise, no chapter number | payne | 2 of 3 chapter pages (144 wrong; 36 no number) | 1 wrong title of 29 chapters; 6 titles and 5 artist names with casing noise; 29 numbers missing |
| P6 | Inscription or epigraph attribution lines not tagged distinctly | dasal, grovier | 3 image pages (dasal 16, 33; grovier 163) | all dasal chapter openers (13); a few grovier pages |
| P7 | Credit entries damaged (leading digit lost, words glued) | grovier | not sampled by image | about 9 credit pages |
| P8 | `meta.json` claims too strong: `confidence: high` on 100% of pages; residual estimates that do not mention P1, P2 or P4 | all | 4 of 4 books | whole file |

No pull quote with new content was removed. No author words were changed in the three English books.

---

## Fixes for the cleaner, ordered by damage to a script writer

1. **Grovier name layer (P3).** Extend the correction list to scholars, places and ancient names, with the same rule (certain from the same book). Start with the 31 above. Rewrite "Jan Van Ike" on pages 89-90 first, since it sits under the Van Eyck title. Re-run a dictionary scan of capitalised non-words and review the top 300 by hand.
2. **Brooke caption pages (P1).** Re-extract caption blocks by coordinates, one block per caption, on pages 96, 97, 159, 210, 219, 221, and scan the other caption-heavy pages for the same fault. Then drop the claim of "0 order errors".
3. **`[continues]` after plate pages (P2).** If a body page ends without sentence punctuation, add `[continues]` and say which later page continues. Do the same for pages ending in a heading. Remove it after `* * *` (dasal 33).
4. **Payne p144 title (P5).** Correct to "Rain, Steam and Speed – The Great Western Railway", and compare all 29 chapter headings with the caption on the same page. Keep the printed casing, or say in the format that casing is normalised. Add the chapter number.
5. **Dasal sidebars (P4).** Add a tag (for example `[sidebar]` before the `##` block, or `[box]`), and do not put `[continues]` inside it. Tag the epigraph attribution (P6) as `[quote]` with a different marker, or add `[attribution]`.
6. **Grovier inscriptions (P6).** Tag the indented lines on p163 and similar pages as `[quote]`.
7. **Grovier credits (P7).** Rejoin the split years ("998", "018"). Low priority.
8. **`meta.json` (P8).** Put real confidence values on the pages with the faults above, correct the pull-quote note in Payne ("about 9 differ by more than 2 words"), and list interleaved captions and missing continuation markers under `known_gaps`.

---

## Overall verdict per book

| Book | Verdict | Reason |
|---|---|---|
| `payne_gae` | Usable after the listed fixes | Prose and pull-quote handling are faithful and verified. Fix 4 (chapter headings, 1 wrong title) is needed before the heading layer is trusted. |
| `brookehitching_mad` | Usable after the listed fixes | Order and drop caps are right on every page I read except caption-only pages. At least 6 pages have scrambled captions, and 17 lose the join to the next page. |
| `dasal_artcurious` | Usable as is for body prose; usable after fixes 3 and 5 for structure | Drop caps, headings and notes are correct. Sidebars are not marked. |
| `grovier_nws` | Not trustworthy for names beyond the TOC list; usable after fix 1 for everything else | Structure is right on the pages I read, and no non-name word was changed. A name search on the clean text misses most scholars, places and ancient names. |

## What I could not decide

- Whether Payne p193 (Picasso) should say 1907 or 1917. The caption in the text layer says 1917, and I did not check the picture page.
- Whether the long Grovier caption on p205 and the single-sentence body lines on p13, 56, 234, 261, 266 are captions or commentary. I did not check them by image.
- The true number of brooke caption pages with only two short captions. The heuristic cannot see them.
- I read 18 images, not the 40 pages the brief asked for. The other verdicts rest on whole-book scripts against the text layer.
