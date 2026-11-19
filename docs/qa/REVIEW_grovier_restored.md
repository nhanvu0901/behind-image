# Review of the restored text of Grovier, "A New Way of Seeing" (`grovier_nws`)

Date: 2026-11-18. Reviewer: worker `grovreview` (independent: it did not write or run the restoration). Read this file first; the
details are in `library/restored/grovier_nws/review.json` (every finding, one record each) and
`library/restored/grovier_nws/review_fixes.json` (41 exact replacements for the coordinator to apply; nothing was applied by the reviewer).

## 1. The answer

**Can the book be used as a source at the trust level `restored`? Yes, for the body text of 55 of the 57 works, with strict
conditions. Not as a whole book, and not for works 2 and 54.**

- **Usable as they stand (26 works):** 1, 20, 22, 23, 24, 25, 26, 28, 31, 32, 33, 36, 37, 38, 40, 41, 42, 43, 44, 45, 47, 51, 52, 53, 55, 56.
- **Usable after the listed fixes (29 works):** 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 27, 29, 30, 34, 35, 39, 46, 48, 49, 50, 57. The fixes are in `review_fixes.json`
  (wrong dates and decades, a wrong museum, mangled names that were left unmarked, caption titles, a few places where the restorer
  changed a material or dropped a place name). After they are applied these works are as good as the first group.
- **Not usable (2 works):** 2 (The Parthenon Sculptures) and 54 (Back and Front).
  Work 2 was not restored: it is almost the machine text again, with at least ten mangled names in the prose ("Berkeley"
  where Pericles is meant, "Pantry" for Phidias, "King Eric Hughes", "Joseph Seven", "Count Elgin VII Thomas Bruce"). Work 54
  is faithful but 47 percent of its prose is marked unclear and the closing argument (the seventh panel) is lost.

What "usable" means here: the *unmarked* sentences of the body pages are a faithful, readable rendering of what the machine
text said, with the names right. It does not mean the book's statements are true: they are Kelly Grovier's interpretations and
claims, in a translated-and-back-translated text, and a few of them are wrong or doubtful in the source itself (section 4).

**What a script writer may take**
- The unmarked prose of a usable work (after fixes), as "the book says". The identification of the work, the artist and the
  names in the prose are right (404 corrections checked, 401 right, 1 wrong, 2 unsure).
- The book's central idea of each chapter (its "eye-hook"), where the chapter's unmarked sentences carry it: in 55 works they do.
- Dates in the `[meta]` line only after the fixes (five meta lines are garbled, section 4).

**What a script writer may not take**
- Anything inside `[[? ... ?]]` (1,092 passages; they are the machine's wording, not restored).
- **Any plate caption and any `[caption]` line on a body page.** They were copied or only partly touched: 62 mangled names on plates in
  47 works ("Albrecht Schiller" for Dürer, "Robert Lawsonberg" for Rauschenberg, "Mark Queen" for Marc Quinn,
  "lasagna" for oil on canvas), wrong sizes and units, and captions that run into commentary.
- **Any quotation** (poems, diaries, letters, remarks of artists): they are back-translations. Munch's diary, Dickinson's
  poem, Duchamp's defender and Teresa of Avila are not in the original words. Quote the published source, never this text.
- Any number or date that the book gives and that the restorer was not allowed to change, without checking it (section 4: about 15 places).
- A claim about a named person that has no source in the book (for example the sentence about Whistler's behaviour towards
  African Americans, work 35) without checking it first.

## 2. How the review was done

- Every body paragraph of all 57 works was compared **word by word** with the unrestored page (a word-level diff, so no change
  could hide), not only a sample of three paragraphs. Every `[caption]` line and every plate caption was read. Where a work showed
  added content the whole work had already been compared.
- All 404 name corrections of `report.json` (390 distinct pairs) and all 73 reading records (72 distinct) have a record; a script
  checked that none is missing.
- Evidence order as asked: the book's own pages (contents page, chapter titles, captions, credits, index), the passage itself, a web
  reference, then my own knowledge. About 15 points were checked on the web (listed in section 7); the rest of the "knowledge" verdicts
  were not.
- The unclear marker is `[[? ... ?]]` (tool `checks.py`). The report's counts are true: I counted again over the restored pages
  and got 1,092 passages and 60,145 characters inside the markers, per page and per work exactly as in `report.json`; markers occur only
  on body pages and are balanced. `unclear_chars` counts the characters inside the markers, not the markers.

## 3. The numbers

| Item | Number |
|---|---|
| Name corrections (occurrences / distinct pairs) | 404 / 390 |
| Right | 401 occurrences (387 pairs) |
| Wrong | 1: `Mylekerun => [[? Mylekerun ?]]` (work 5; the marker is not on the page, the phrase was replaced by an invented one) |
| Unsure | 2: `Luga => Luke` (work 25), `São Paulo => Saint Paul` (work 21; Paul the Hermit is meant) |
| Basis of the 404 verdicts | the book's own pages 223, the passage's own content 54, web reference 20, **own knowledge only 107** |
| Names left mangled (records) | 132: 70 in body pages (prose or a caption line on a body page), 62 on plate pages |
| Works with a mangled name left in a body page | 35 of 57 |
| Readings (records / distinct) | 73 / 72: **sound 62, invented 0, unsure 11** |
| Works with added or changed content beyond wording | 4 (works 3, 4, 5, 6), plus work 2 (not restored) and smaller undeclared readings in 1, 23, 54 |
| Faithfulness records | 28 (high 1, medium 7, low 20) |
| Facts checked | 88: right 63, wrong 9 (and 4 garbled `[meta]` dates in the names-left-mangled list), unsure 16 |
| Unclear passages | 1,092; share of the body prose that is marked: 23.0 percent overall |
| Marked share by group | works 1-6 and 39 (restored by claude-sonnet-4-6): 1.2 percent; works 7-19: 16.2 percent; works 20-38 and 40-57 (written by hand by Claude workers): 29.8 percent |
| Works with verdict usable / usable after fixes / not usable | 26 / 29 / 2 |
| Fixes in `review_fixes.json` | 41 |

Reading of the marking: it is honest in works 20-57 (a garbled sentence is marked, not smoothed), thin in works 1-6 (a restorer
that smoothed instead of marking: work 5 has 0 marked passages, work 6 has 0, and each has places where a phrase was invented),
and in between for works 7-19. High marking means a safe text, but also a thin one: 15 works have more than 33 percent of their
prose marked, and four (51, 54, 55, 56) more than 40 percent.

## 4. The worst findings, with evidence

1. **Work 2 is not a restoration.** Pages 0024-0026 differ from the machine text by "the", "sunken" and four marked phrases. The names
   list is empty. The prose still reads "the Greek politician Berkeley" (the Pericles who commissioned the Parthenon), "Pantry's
   sculpture", "King Eric Hughes' daughter" (Erechtheus), "Joseph Seven" (Severn), "Captain William Egren" (the captain of the
   brig Mentor was William Eglen; web: Wikipedia and museum pages), "Gisila Island / Kisira" (Kythera, where the Mentor sank; web: Wikipedia),
   and the plate caption "Mark Queen, Alison Lapa" (Marc Quinn, Alison Lapper).
2. **Wrong numbers and dates are kept in the prose, because the restorer may not change digits** (about 15 places, in `review_fixes.json`
   and `review.json`): Rembrandt "lost his wife ... in the 1940s ... bankruptcy in the 1950s ... the 1960s" (1640s, 1650s, 1660s; work 29);
   a natural philosopher "well known in the 1960s" in a painting of 1768 (work 30); Grünewald "almost 300 years ago" next to "more than 500 years"
   (work 21); Turner's influence "in Paris in the 1970s and 1980s" (1870s-80s; work 34); Surrealists "in New York in the 1920s" (1940s; work 49);
   *The Artist Is Present* "at the New York Metropolitan Museum of Art" while the caption of the same chapter says Museum of Modern Art (work 57);
   `[meta]` lines "(27-68 BC)" for Laocoön (27 BC to AD 68; web: Wikipedia; work 5), "(About 60 B.C. - 50 years ago)" (work 4), "(approximately 800 years)"
   (work 7), "(approximately 1,000 years)" (work 8), "(approximately 1503-1506 years)" (work 17); the caption "50 cm x 700 cm" for a tapestry that the text
   calls 70 metres (work 9); "Eng fuga verterunt Angli" for the Latin "Et fuga ..." (work 9; web).
3. **The restorer invented or changed content, and did not always declare it.** Work 5: "an undisturbed attack in Mylekerun" became "the attack
   at its most acute moment" and the names list claims a marker that is not on the page. Work 6: a "rocky basket" became a "wicker basket"
   (a material was read differently, which the prompt forbids) and the ending about the statue of St Peter was recast into a new claim. Work 4:
   "pine nut" became "pine cone" and "the reflect dent of the drinker" became "the reflection of a drinking cup". Work 3: "mannequins" and "non-military
   figures" were added. Declaring is also uneven: works 20-31 declare no reading at all, yet pronouns were corrected (he to she) and "screens" became "panels"
   (work 54) without a line in the readings list. **The 72 readings are therefore not the complete list of places where the restored text says more than
   the machine text did.**
4. **Mangled names and terms left unmarked in the prose.** 35 works have at least one. The worst is work 12, where the object of the whole chapter is
   still called "fragrance" about twelve times (it is the citron in Eve's hand: the chapter itself says "a near-relative of the lemon", "Adam's Apple"
   and "trog" = etrog; web: James Snyder 1976 and museum pages). Others: "Clarice, the god of the west wind" (Chloris, work 16), "Mysterious screw" (spira
   mirabilis, work 16), "the Great Monk Convergence" (the guild of crossbowmen, work 13), "Association of Independent Artists" (Society of Independent
   Artists, work 45), "the Chicago Academy of Arts" (Art Institute of Chicago, work 46), "Maria Agustina Samito Sotomayor" (Sarmiento; web: Museu Picasso).
5. **Claims and quotations that cannot be spoken as they stand.** Work 35: "Whistler himself had beaten African Americans in public and used racist
   nicknames and slapped abolitionists" (no source in the book, garbled voice; web search found nothing). Work 15: the Virgin Mary anoints Christ with perfume
   (the Gospel gives it to Mary Magdalene; the same paragraph calls the jar Mary Magdalene's). Work 39: Munch's diary lines contain "a strangulation running through the heavens"
   (Munch's own word is a scream); work 51: Dickinson's poem in machine wording. The fixes for works 15, 35 and 39 mark these as unclear; work 51 has no fix (a poem must be quoted from its published text).

Also noted: the `model` field of `report.json` says `mock` for 38 works. They were written by Claude workers and accepted through `--model mock`
(`from_saved`, no model call), so the field does not name the writer; the audit trail of who wrote which work is only in
`.scratch/agy_tasks/grovier/`.

## 5. The two works with caption problems

**Work 48 (Guernica).** In `report.json` as it stands the `warnings` list of work 48 is empty (the brief expected a warning; the tool does not check captions on plate pages, and the name pairs are applied to prose only), so the caption problems below were found by reading.
What is wrong: the body-page caption on page 0322 reads "Guernica (1937), lasagna, 349.3 cm x 776.6 cm": the size is right, "lasagna" is the machine's
word for "oil on canvas" (fix F030). The plate caption on page 0323 runs three captions into one ("Bull Head (1942), Bicyclic saddles and hoods (felt and
metal), 33.5 cm x 43.5 centimetres Mix19cm Bullhead is simply ..."): it should be *Bull's Head* (1942), bicycle seat and handlebars, 33.5 x 43.5 x 19 cm, plus a separate
commentary. Page 0324: "Gjon Milli, 1968" (the photographer is Gjon Mili; the year looks wrong: not checked on the web). The text also refers to "p. 147", a page of the printed
English edition.

**Work 50 (Kahlo).** The report warns that the corrected title "still occurs 1 time" and it does, twice: the two caption lines on page 0337 carry the
machine title: `Frida Kahlo, "A self-portrait and a hummingbird with rose necklaces" (1940), oil on canvas, 61.2 cm x 47 cm` and `Frida Kahlo, "A self-portrait with a rose necklace and a hummingbird."`.
Only the name Kahlo was corrected; the title should be *Self-Portrait with Thorn Necklace and Hummingbird* (the chapter title; the text speaks of a "thorny crown";
date and size are right). Fixes F032 and F033. Plate pages 0339-0341 keep machine captions too ("Strength is the eighth card of the Grand Secret Tarot", "Oscar Dominguez, Freud, Mage de reve-Etoile ...
Marsetaro grass", and a Pollock caption that belongs to the next chapter).

## 6. Works by verdict

`marked %` is the share of the body prose inside `[[? ?]]`. Fix ids refer to `review_fixes.json`.

| Work | Title | Verdict | marked % | Fixes | Note |
|---|---|---|---|---|---|
| 1 | The Lion Hunt of Ashurbanipal | usable | 1.0 | - | Faithful, light restoration, 3 marked passages, no body-text name left mangled except two marked passages. Three small undeclared word replacements, none carries a... |
| 2 | The Parthenon Sculptures | not_usable | 3.8 | - | The chapter was left almost as the machine translation wrote it, with at least ten mangled names still in the body text (Berkeley for Pericles, Pantry for Phidias,... |
| 3 | The Terracotta Army of Qin Shi Huang | usable_after_fixes | 1.8 | F007 | Readable and mostly faithful; one name, one fix for an added word (mannequins); a few small undeclared readings. Plate captions (Gomley, 'man named Ma') stay mangled. |
| 4 | The Frescoes of the Villa of the Mysteries, Po | usable_after_fixes | 1.2 | F001, F002 | Readable; many context-based readings (18). One real defect: the date line '50 years ago'. Two readings are unsure (drinking cup; subordinate state) and should be... |
| 5 | Laocoön and His Sons | usable_after_fixes | 0.0 | F003, F004, F005 | Good restoration of a clumsy text; fix the date line (27 BC - AD 68) and mark the Mylekerun sentence as unclear. |
| 6 | Trajan's Column | usable_after_fixes | 0.0 | F006, F008 | Mostly good; two places where the restorer invented (wicker; the St Peter ending) should be marked. |
| 7 | The Book of Kells | usable_after_fixes | 11.5 | F009 | Good restoration, honest marking (15 passages). Fix the date line (approximately AD 800); plate captions are still mangled. |
| 8 | Travelers among Mountains and Streams | usable_after_fixes | 26.2 | F010 | Honest marking (a quarter of the text); body names corrected; fix the date line. Plate and caption lines stay garbled. |
| 9 | The Bayeux Tapestry | usable_after_fixes | 12.8 | F011 | Good restoration; fix the Latin 'Eng' to 'Et'; the opening 1064 scene sentence still reads nonsense; the dimension caption is wrong. |
| 10 | The Cosmic Man | usable_after_fixes | 9.0 | F012 | Faithful restoration, light marking. Left mangled in body text: 'Architectural Monograph 10th Century BC' (wrong date), 'Dean of the Pontifical convent'; both should... |
| 11 | The Expulsion of Adam and Eve | usable_after_fixes | 16.0 | F040, F041 | Good restoration; two names left in the body (birth name, poem title) that should be corrected or marked. |
| 12 | The Ghent Altarpiece | usable_after_fixes | 10.3 | F035, F036, F037, F038, F039 | Good restoration of a clumsy text; the main weakness is the object of the chapter, 'fragrance' for citron, left in about 12 places (some inside marked passages); a... |
| 13 | The Descent from the Cross | usable_after_fixes | 24.9 | F013 | The central argument is readable; mangled names left in body: Great Monk Convergence, Treskin Ill Book (unsure), The Undercarriage of Christ. Mark them. |
| 14 | The Annunciation | usable_after_fixes | 28.6 | F014 | Names well corrected; marked share is high (29 percent) but the account of the fresco is readable. Fix the Piero title in the caption. |
| 15 | The Lamentation over the Dead Christ | usable_after_fixes | 17.8 | F015 | Faithful and readable, but three names/terms left mangled in the body (ginsomnia, Oiled Stone, Maria Daran) and a wrong attribution of the anointing; mark the last. |
| 16 | The Birth of Venus | usable_after_fixes | 16.2 | F016, F017 | Faithful; 5 names corrected correctly; but 'Mysterious screw' (spira mirabilis), 'Clarice' (Chloris) and 'Hebei' remain mangled in the body. |
| 17 | Mona Lisa | usable_after_fixes | 16.7 | F018 | Good restoration, three name corrections right. One stray word in the date line. Rauschenberg caption mangled. |
| 18 | The Garden of Earthly Delights | usable_after_fixes | 6.7 | F019 | Faithful, 17 corrections all right; one machine title left ('Human Gardens') and an unclear word 'Sanctuary'. |
| 19 | The Sistine Chapel Ceiling | usable_after_fixes | 13.5 | F020 | Good restoration, all name corrections right; a ratio '5.4' and 'prophets and witches' left; the unmarked part of the 5:4 argument is the book's own claim. |
| 20 | The School of Athens | usable | 37.8 | - | Names right, restoration faithful, and honest marking; but 38 percent of the prose is marked, so only the unmarked sentences may be used (about 62 percent). |
| 21 | The Isenheim Altarpiece | usable_after_fixes | 20.4 | F021 | Names right; fix 'Almost 300 years ago' (500). |
| 22 | Bacchus and Ariadne | usable | 21.0 | - | Names right; faithful; 21 percent marked, among them the key plant, so the chapter's central point is partly lost. |
| 23 | Self-Portrait | usable | 34.2 | - | Names right; faithful; one third marked; use only unmarked sentences. |
| 24 | The Crucifixion | usable | 35.0 | - | Names right; faithful; one third marked. |
| 25 | The Supper at Emmaus | usable | 36.2 | - | Names right (Luke is unsure); faithful; 36 percent marked. |
| 26 | The Ecstasy of Saint Teresa | usable | 27.2 | - | Names right; faithful; about 27 percent marked. |
| 27 | Las Meninas | usable_after_fixes | 20.2 | F022 | Names right; one unmarked mangled name (Maria Agustina Samito Sotomayor) and one probable one (Laura Carmines). |
| 28 | Girl with a Pearl Earring | usable | 18.9 | - | Names right (one by outside knowledge, correct); faithful. |
| 29 | Self-Portrait with Two Circles | usable_after_fixes | 35.3 | F023, F024 | Names right; the decades are wrong (1940s/1950s/1960s for 1640s/1650s/1660s); apply the two fixes. |
| 30 | An Experiment on a Bird in the Air Pump | usable_after_fixes | 35.6 | F025 | Names right; one wrong decade (1960s for 1760s). |
| 31 | The Nightmare | usable | 24.5 | - | Names right; faithful. |
| 32 | The Third of May 1808 | usable | 21.9 | - | Names right; faithful; captions on body page 0228 keep machine words. |
| 33 | The Hay Wain | usable | 29.5 | - | Names right; faithful; 30 percent marked. |
| 34 | Rain, Steam and Speed – The Great Western Rail | usable_after_fixes | 27.3 | F026 | Names right; one wrong decade (Paris 1970s and 1980s) to fix. |
| 35 | Arrangement in Grey and Black No. 1 (Portrait  | usable_after_fixes | 35.6 | F027 | Names right; one unsourced serious claim about Whistler should be marked unclear before any use. |
| 36 | The Thinker | usable | 25.3 | - | Names right; faithful. |
| 37 | A Bar at the Folies-Bergère | usable | 23.1 | - | Names right; faithful. |
| 38 | Bathers at Asnières | usable | 29.9 | - | Names right (19 corrections); faithful; 30 percent marked. |
| 39 | The Scream | usable_after_fixes | 1.0 | F028 | The most polished work; names right. Two unsure readings (sexual to existential; radio wave to radiation) and a diary quotation left garbled; mark the quotation. |
| 40 | The Large Bathers | usable | 27.2 | - | Names right; faithful. |
| 41 | The Ten Largest, Group IV, No. 7, Adulthood | usable | 27.1 | - | Names right (13); faithful. |
| 42 | The Kiss | usable | 32.1 | - | Names right; faithful; a date in the 1907 protest sentence is doubtful (book's claim). |
| 43 | Dance | usable | 26.6 | - | Names right; faithful. |
| 44 | Water Lilies | usable | 32.4 | - | Names right; faithful. |
| 45 | Fountain | usable | 25.5 | - | One name correction (right); faithful; the exhibition society's name stays mangled in the text but the story can be told without it. |
| 46 | American Gothic | usable_after_fixes | 33.8 | F029 | Names right; fix the exhibition name (Art Institute of Chicago). |
| 47 | The Persistence of Memory | usable | 16.1 | - | Names right (14); faithful; a low share (16 percent) is marked. |
| 48 | Guernica | usable_after_fixes | 33.6 | F030 | Names right; the body-page caption 'lasagna' and the plate captions are mangled (the report shows no warnings for this work: the tool did not check captions on... |
| 49 | The Elements of Natural History | usable_after_fixes | 33.6 | F031 | Names right (17); fix one wrong decade (1920s for 1940s). |
| 50 | Self-Portrait with Thorn Necklace and Hummingb | usable_after_fixes | 28.3 | F032, F033 | Names right; the two caption lines on page_0337 still carry the machine title; fix both. |
| 51 | One: Number 31 | usable | 40.5 | - | Names right; faithful; but about 40 percent is marked, so only the clear sentences may be used. |
| 52 | Study after Velázquez's Portrait of Pope Innoc | usable | 30.5 | - | Names right; faithful. |
| 53 | Brillo Boxes | usable | 24.8 | - | Names right; faithful. |
| 54 | Back and Front | not_usable | 46.6 | - | Names right and the unmarked text is faithful, but 47 percent is marked and the chapter's closing argument (the seventh panel) is lost; the usable facts are thin... |
| 55 | Betty | usable | 48.9 | - | Names right; faithful; thin: half of the text is marked. |
| 56 | Maman | usable | 41.8 | - | Names right; faithful; thin: 42 percent marked. |
| 57 | The Artist Is Present | usable_after_fixes | 35.0 | F034 | Names right; fix the museum (Metropolitan Museum of Art to MoMA). |

## 7. What I could not check, and what each kind of verdict rests on

- **The original English text of the book** was not available, so "faithful" means faithful to the *machine* text, and the
  machine text may itself have changed a number, a name or a claim. Where the machine text is plainly wrong (decades, museum) I say so; where it is
  merely doubtful I say `unsure`.
- **Verdicts that rest on the book's own pages (223 name corrections):** the contents page, chapter titles and captions of the same
  chapter give the artist and the title in correct English; all titles of the 57 works and their artists are checked this way. The
  `[meta]` and caption comparisons inside a chapter (for example work 9, 4) also rest on the book.
- **Verdicts that rest on a web reference (about 15 checks):** Laocoön dating (Wikipedia), the Mentor shipwreck and its captain (Wikipedia, museum pages), Xu Fu
  (Wikipedia), Ripanda in the basket (Wikipedia, RIHA Journal), the Bayeux Tapestry inscription and size (Wikipedia), Fan Kuan's scroll (National Palace Museum and
  other museum records), the citron of the Ghent Altarpiece (Snyder 1976 and museum pages), the maid in *Las Meninas* (Museu Picasso, Smartify), Masaccio's birth name
  (Wikipedia, Britannica), Bergson's Lucretius of 1884 (Footprint 2014, archive.org), Latour-Marliac and Monet's order of 1894, Chevreul, candles and Clichy for *Bathers at Asnières*, Jessie Lightfoot
  (Bacon's nanny), Black Lion Wharf. A search for the Marie Harel statue of 1928 and Millerand found nothing either way.
- **Verdicts that rest on my own knowledge alone (107 name corrections and most of the 88 fact checks):** for example Marc Quinn, Rauschenberg, Mariotte, Isambard Kingdom Brunel, Schrödinger,
  Millerand, Boisard, Janson, d'Amelia, Festa, Chevreul as the colour theorist, the dates and sizes of most paintings. They are well-known facts, but I did not look them up.
- **Not judged:** the content of the 1,092 marked passages (I did not test whether each is "the most literal reading", only that the marker is balanced and the count is true);
  every plate with no text; the introduction (pages 11-15) and the end matter (notes, credits, index: all machine text, not part of the catalogue); the book's own interpretations (for
  example the fly in Pollock's *One: Number 31*, the 5:4 ratio in the Sistine ceiling, the citron as "eye-hook") which are Grovier's claims and were not tested against the pictures.
- **A reviewer's limit:** the comparison was done by reading diffs, one work at a time; a subtle change of meaning inside a rewritten sentence can have escaped me. The readings I called
  `sound` are sound against the chapter's own context, not against the original English.

## 8. Suggested next steps for the coordinator (not done by the reviewer)
1. Apply `review_fixes.json` (41 replacements; each `find` was checked to occur exactly once in its page), then update the unclear counts in `report.json` for the fixes that add `[[? ?]]` markers.
2. Re-restore work 2 and, if wanted, work 54 (its unmarked part is faithful).
3. Add the name pairs of `names_all` to a one-time pass over the plate captions, then re-check the captions by hand; until then give no caption to a script writer.
4. Give the script step the rule: use only unmarked prose, never quote, verify every number and date against a second source, attribute interpretations to Grovier.
