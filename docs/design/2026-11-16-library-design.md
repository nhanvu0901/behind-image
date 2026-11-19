# Library: from a book to a project (contract note)

Front door of the pipeline: pick a BOOK, see every artwork it covers, open one, create a project. Deterministic, no LLM, no network. Private local tool (127.0.0.1); books are copyrighted, nothing is published or exported.

Code: `bti/library/` (config, parse, extract, catalogue, projects), `bti/editor/library_api.py`, page `bti/editor/static/library.html` + `js/library.js` + `css/library.css`. Build: `python -m bti.library build [book_id ...]`. Dependency added to `requirements.txt`: `pymupdf`.

## Books and ids
`payne_gae`, `hodge_aid`, `hagen_wgps`, `grovier_nws`, `brookehitching_mad`, `dasal_artcurious`. PDFs are found in `books/` by a file-name fragment (`bti/library/config.py`). Page numbers are 1-based PDF pages everywhere.

## Data shapes (all written under `library/`)
- `books/<id>/book.json`: `{id, title, author, file, pages, pdf_type: digital|scan, unit: chapter_per_artwork|fixed_spread|short_entries|themed_chapter, n_works, notes}`.
- `books/<id>/works.json`: list of `{id: "<book_id>/<nnn>", n, title, artist, year, headline?, pdf_pages:[first,last], words, n_images, headings[], artwork_key, rights:{status: pd_likely|copyright_likely|unknown, basis, estimate:true}}` plus helper fields `year_num`, `artist_death`, `artist_alive`, `artist_dates`, `pages_inferred`.
- `artworks.json`: `{artwork_key: {title, artist, year, works:[work ids]}}`, every work belongs to exactly one key (singletons included).
- `unparsed.json`: works missing title, artist or year.
- `overrides/<book_id>.json`: `{ "<work id or n>": {field: value} }`, fields `title, artist, year, headline, pdf_pages, artwork_key, rights, notes, artist_death, artist_alive`. Merged over the generated data on every read and during the build; created empty; the build never writes them. `rights` merges key by key. Re-run the build after correcting artist/title/year so matching and rights are recomputed.
- `cache/<book_id>/pages/<page>_<w>.jpg`, `cache/<book_id>/img/<xref>_<w>.jpg`.
- Text: `library/clean_text/<book_id>/page_<NNNN>.txt` (if present, owned by another engineer) is preferred per page, else the PDF text layer with soft hyphens repaired. `text_source` is `clean`, `mixed` or `layer`; `ocr: true` for scans. `library/text_audit/` is read-only for this module.

## Parsing rules per book
- Payne (30): PDF TOC entries `N Artist: Title year`; chapter runs to the page before the next entry; chapter 30 ends before "Notes" (p.374). Arnolfini = 23-35.
- Hodge (100, scan): no TOC. The list is the "Index of artworks" (PDF 428-429, text before the general index). Each entry is `Artist (dates) Title (year) a-b` split on the page range; artist flipped to `First Last`; death year from the dates (`1909-92`, `b.1945` = alive). Book page = PDF - 4, always 4 pages per entry but NOT evenly spaced (gaps for section pages, e.g. PDF 58-59 between Primavera and the Garden of Earthly Delights), so the index start pages are authoritative. Arnolfini = 22-25.
- Hagen (80, scan): 6 pages each from PDF 12 (book p.8), `12 + 6(n-1)`. Contents on PDF 9-11 are two columns whose headline (size >= 9.2) and detail lines interleave: per page and column, headline lines are grouped by vertical gap, details are grouped at `Artist: Title`, the k-th headline pairs with the k-th detail. Two headlines on the same line (page 9, entries 2-3) are ordered by word overlap with the entries' first pages. Soft hyphens `¬` are removed.
- Grovier (57): TOC `NN  Artist, Title`; no artist when the text before the first comma is absent or starts with "The ". No year in the TOC (a trailing `, 1950` in a title becomes the year). Ends before "Sources and Further Reading".
- Madman's Gallery (61 entries from "Introduction" to "Select Bibliography"): `Title (year)[, Artist][ and ...]`; year may be `c.1600 bc`, `38,000-33,000 bc` or "eighteenth century"; text after the year in brackets becomes `headline`; `Name's Title` gives an artist; a few artists are set by an explicit table `MADMAN_EXC` in `parse.py`.
- ArtCurious (12): chapters from the TOC, title = the 25 pt spans on the chapter's first page; `headline` holds the part name; no artist/year, rights `unknown`, excluded from cross-book matching.

## Cross-book matching (conservative)
Normalise (accents, case, punctuation, leading articles). Two entries of different books merge when artists match (surname token of one occurs in the other, particles ignored) AND titles match (equal, ratio >= 0.88, or one is a whole-word prefix of the other with >= 3 words) AND years, when both known, are within 25 years. With an unknown artist only an identical title (>= 2 words) merges. A group never holds two entries of the same book. Merging is transitive through union-find. The Kiss (Rodin) and The Kiss (Klimt) differ by artist; The Kiss and The Thinker (Rodin) by title.

## Rights estimate (a hint, always labelled "ước lượng")
`pd_likely`: artist died >= 71 years ago, or the work is dated before 1900 (death year unknown). `copyright_likely`: artist alive, died < 71 years ago, or work after 1955 with unknown death year. `unknown` otherwise. Death years come from the Hodge index, shared with the same artist in other books. A missing year is taken from the artwork group.

## Endpoints (`/api/library`, all read-only except POST)
- `GET /books`: books plus `n_with_project`, `cover_url`.
- `GET /books/{book_id}/works?q=&century=&rights=&multi=`: rows with `thumb_url`, `century`, `also_in[]`, `projects[{id,stage,has_storyboard}]`.
- `GET /books/{book_id}/cover.jpg?w=`
- `GET /works/{book_id}/{n}`: row + `text`, `ocr`, `text_source`, `pages[]`, `images[]` (digital), `headings`.
- `GET /works/{book_id}/{n}/page/{pdf_page}.jpg?w=` (only pages of that entry, w 64..2400), `GET /works/{book_id}/{n}/image/{xref}.jpg?w=`
- `GET /artworks/{artwork_key}`
- `POST /projects` `{work_ids, slug?}` -> project.json; 409 if the folder exists, 422 for bad ids or slug (`[a-z0-9][a-z0-9_-]{0,63}`, not `lab_`/`demo_`), at most one entry per book.
- `GET /api/projects` now lists every project folder with `project.json` or `storyboard.json` and adds `stage` and `has_storyboard`. Stage is inferred from files: `selected` < `script` (script.md/txt/json) < `voiced` (audio/ or timing.json) < `storyboard` < `approved` (approvals.storyboard set) < `rendered` (an .mp4 in render/, output/, out/ or the folder). Every id and path is validated; only `books/`, `library/`, `projects/` are touched.

## Project folder
`projects/<slug>/project.json` = `{id, title, artist, year, stage:"selected", created_at, sources:[{work_id, book_id, pdf_pages}], artwork_key}` (+ `mixed_artwork_keys` if the chosen works belong to different keys) and `source/<book>_<nnn>.txt|.json`. No storyboard is created.

## Known exceptions
- Hodge: the Michelangelo entry has an OCR-damaged page range (`(1508-12) 75`), placed by the only free 4-page slot (`pages_inferred`). Frankenthaler's death year reads `201` (OCR), left unknown. OCR typos fixed by `OCR_FIX` (e.g. `Land the Village`). Estes, Kiefer, Rego, Freud are alive or recent: `copyright_likely`.
- Hagen: "Artist unknown" (Bayeux Tapestry) gives artist null. `Jan Eyck` is corrected to `Jan van Eyck`. A few first pages are image-only, text starts on the next page.
- Grovier: no years and about 15 entries without an artist (monuments, anonymous works).
- Madman's Gallery: many entries are groups ("... and Other ..."), 26 without an artist.
- Payne spells chapter 12 "Rail, Steam and Speed" (Hodge: "Rain"); they still merge through the Hodge/Grovier title.

---

# Update: artwork-centred library (owner decision: one painting per video)

The default page view is now "Tác phẩm" (`#/`): every artwork merged across books. The bookshelf is the second tab (`#/books`). Rights are information only: the badge is always shown and never hides, disables or warns-blocks anything.

## Commands
`python -m bti.library build` (catalogue + `regroup`), `regroup` (artwork groups, keys and rights from works.json, no PDF), `dossiers [artwork_key ... | --book BOOK_ID]` (re-runnable at any time; picks up new clean pages; `--book` rebuilds only the dossiers that hold a work of that book), `trust BOOK_ID` (read-only: the trust level of every work of a book and why).

## Dossier: `library/dossiers/<artwork_key>/dossier.json` + `sources/<book_id>_<nnn>.txt`
`{artwork_key, kind: artwork|theme, identity:{title,artist,year}, variants:{title|artist|year:[{value,works}]}, conflicts:[{field,values:[{work_id,value}]}], sources:[{work_id, book_id, n, pdf_pages, words, text_source, ocr, title, artist, year, headline?, file, trust, trust_note, outline:{headings:[{level,text,page}], captions:[{page,text}], meta[], details? (hodge_aid: the `##` headings, the named details)}, pages_clean, pages_total}], totals:{books, sources, words, words_normal, words_restored, words_low, pages_clean, pages_total}, images:[{work_id,xref,page,width,height}], details[], rights, only_low_trust, no_normal_source, text_source}`; `trust` is `normal`, `restored` or `low` (see Trust).
- Identity prefers Payne, Hodge, Brooke-Hitching, Hagen, Grovier. A conflict is a different normalised title, an artist that does not match, or years more than 5 apart. Spelling or case differences only (`Jan Van Eyck`/`Jan van Eyck`) are not conflicts.
- Source text files hold body text only: headings (`#`, `##`), paragraphs, quotes (`> `). Metadata, captions, credits, notes and non-body page types (front, contents, notes, credits, index, back, blank) are excluded; captions and meta stay in the outline.

## Clean text (`bti/library/clean.py`)
Parses `[page-type]`, `# `/`## ` headings, `[meta] [caption] [credit] [note] [quote]` and `[continues]` (the last paragraph joins the first paragraph of the next page within the entry). A page uses `library/clean_text/<book>/page_NNNN.txt` when present, otherwise the text layer (soft hyphens repaired; digital layer text gets its outline from font-size headings). `text_source` per source and per dossier: `clean`, `mixed`, `layer`, `restored` (a work at trust level `restored`, built from `library/restored/`, see Trust). `[sic]` is not a tag (it occurs inside quoted text).

## Trust
Every source carries a trust level, and since the restoration of Grovier's book it has three values, decided per **work**, not per book: `normal`, `restored`, `low`.

| Level | What the text is | The model | The owner's page |
|---|---|---|---|
| `normal` | a book that is not machine-translated | a source as any other | no tag |
| `restored` | a machine-translated work whose text was restored and then reviewed by an independent reader (`library/restored/<book>/`) | a source, in with the restrictions below | "Bản khôi phục" and the note |
| `low` | machine-translated and not restored (or a restoration the review did not pass) | "not a basis for facts"; left out until the owner ticks it | "bản dịch máy, không dùng làm nguồn sự kiện" |

**How a work gets its level** (`catalogue.work_trust`, reasons through `python -m bti.library trust BOOK_ID`). `library/overrides/books.json` (created by the build if missing, never rewritten) holds `{book_id: {trust: normal|restored|low, trust_note, force?}}`; its starting point is `grovier_nws` = `low`, the others `normal` (`catalogue.book_trust` is still the level of the BOOK).
1. The entry **forces** the level of the book when it has `"force": true` or names a level other than the built-in one of the book. Every work of the book then gets that level and no review is asked. (`normal` for Grovier: trusted by the owner. `low` for Grovier with `"force": true`: the restoration is switched off. `restored`: every work that has its restored page files is `restored`, the review is not consulted, the owner vouches for it; a work without those pages is `low`.) An entry that only repeats the built-in level is not a decision: `build()` writes one for every book, so the existing `grovier_nws: low` does not switch the restoration off.
2. Otherwise a `low` book's work is `restored` when `restored.check` says yes, else it keeps `low`. Otherwise the work keeps the level of its book.

`restored.check(work)` says yes only when all of this holds, and every doubt (a missing or damaged file, a missing record) is a no: the book has a folder `library/restored/<book_id>/` with a readable `review.json`; the review has a verdict for the work and it is `usable` or `usable_after_fixes`; every fix the review lists for the work (its `fix_ids` and the entries of `review_fixes.json` for the work) is in `review_fixes.applied.json`, and a `usable_after_fixes` verdict lists at least one; every page of the work has a `page_NNNN.txt` in the folder; and, when `report.json` is there, it lists the work as not failed with exactly the pages the catalogue gives (a catalogue rebuild that moved a page range stops it). Review files are read once and cached by size and time of change.

**The text of a restored work** (`clean.entry(work, restored=True)`, used by `dossiers.build_one`): built from the restored pages and nothing else; every `[[? ... ?]]` passage is replaced by the mark `[…]` (a marker that is not closed makes its whole line one mark); plate pages are left out and no caption is kept (the review found captions still machine text, `outline.captions` is empty); headings and the `[meta]` line stay; the word counts count what remains (the marks, and punctuation left beside them, are not words). The unrestored text is not given for that work any more. The library's own view of a book's page text (`/works/<book>/<n>`) is unchanged: it shows the book as it is.

**What the model is told** (`bti/script/brief.py`): a restored source is in the brief by default (a `low` one needs the owner's tick). Its line in the source list and its header carry `[RESTORED]` with the note (the author's name comes from `book.json`): "restored and reviewed rendering of a machine-translated book: its unmarked prose says what the book says, names corrected. Its ideas and readings of the picture may be used as Kelly Grovier's own: say "Kelly Grovier argues" or the like once, never as established fact. NO number, date or quotation may be taken from it unless another source of this dossier confirms it. […] marks a passage that could not be restored: never guess what it said." When none of the sources the model is given is `normal` the brief adds one paragraph, "NO FULLY TRUSTED SOURCE ...", telling it that every fact needs care (`established` only for a plain description of what the picture shows, otherwise `likely` at most, and say whose claim it is). The Vietnamese note on the page is `TRUST_NOTE_RESTORED` in `config.py` ("Bản khôi phục từ bản dịch máy, đã rà soát: dùng được cho ý và mô tả; số liệu, năm và trích dẫn phải có nguồn khác xác nhận.").

**Numbers and flags.** The dossier totals split `words_normal`, `words_restored`, `words_low` (they add up to `words`). `only_low_trust` keeps its meaning: every source is `low`. `no_normal_source` is new: there is a source and none is `normal` (restored and/or low). The script step never read `only_low_trust`; what it does is stop when no source is included (the page shows "Chưa có nguồn nào được dùng" and refuses to start the outline), which is the case for a project with only `low` sources that were not ticked. `no_normal_source` does not refuse anything (a restored source is usable): the brief computes it over the sources the model is actually given (`brief.no_normal_source`, so excluding the normal source of a project turns it on) and says so to the model; the page says "Chưa có nguồn tin cậy đầy đủ cho tác phẩm này." in the artwork list, the dossier, the artwork step and the script step.

**Everywhere trust is read.** `catalogue.book_trust` (the level of a book; `book.json`, the shelf), `catalogue.work_trust` (a work), `catalogue.source_rank` (the catalogue's title, artist and year of an artwork: a `restored` book ranks like `low`, restored text does not make the catalogue's names more trusted), `dossiers.build_one` (the work's level, text and numbers), `dossiers.live_trust` (below), `projects.create_project` (default exclusion: `low` sources only, `normal` and `restored` stay), the editor's `library_api` (`low_trust_books`, `restored_books`, `words_restored`, `no_normal_source` on the artwork rows; each dossier source shows its level live), `brief.py` (`_level`: a missing level is `normal`, a word that is none of the three is `low`, and `restored` is believed only from the project's own dossier, never from the book table), and the page (`labels.js`, `trust.js`, `views/library.js`, `views/script.js`, `views/artwork.js`).

**Live labels.** An edit of `books.json` shows at once on the dossier page (`dossiers.live_trust`), but a source is never shown as `restored` unless the text in its dossier was built from the restored pages: a dossier that was not rebuilt after a review keeps the text it has and is labelled for it. Projects keep the copy of the dossier made at creation, so a project made before the restoration keeps its `low` Grovier text.

**Rebuilding** after a restoration folder is added or a review changes: `python -m bti.library dossiers --book grovier_nws` (only the dossiers that hold a work of that book).

## Manual merge and split: `library/overrides/artworks.json`
`{"merge": [[work ids that are one artwork], ...], "split": [work ids that stay alone]}`. A forced merge ignores the one-entry-per-book rule; a split work is never auto-matched. Both write the file, run `regroup` and rebuild the affected dossiers (stale dossier folders are removed). Artwork keys are derived from the group, so a merge or split can change a key; projects keep their copy of the dossier.

## Endpoints added
`GET /api/library/artworks?q&century&has_project&min_sources&kind=artwork|theme|&rights&sort=sources|words|title|year` (rows: title, artist, year, century, books, n_sources, words, words_normal, words_restored, words_low, only_low_trust, no_normal_source, low_trust_books, restored_books, text_source, n_conflicts, rights, projects, thumb_url); `GET /artworks/{key}` now also returns `dossier` (with source `text_url`, `pages`, image `url`); `GET /artworks/{key}/source/{book_nnn}` (body text); `POST /artworks/merge {key, with}`; `POST /artworks/split {work_id}`; `POST /projects {artwork_key, exclude?, slug?}` (or `{work_ids, slug?}` as before).

## Project from an artwork
`project.json` adds `artwork_key`, `dossier: "source/dossier.json"`, `library_dossier`. `source/` holds `dossier.json` (identity recomputed for the chosen sources) and `<book>_<nnn>.txt` as they were at creation. No storyboard.
