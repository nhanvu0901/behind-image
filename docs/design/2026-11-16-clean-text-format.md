# Clean book text: format and rules

Date: 2026-11-16. Basis: `docs/design/research/R4_book_text_audit.md`.

## Purpose

The text layer of the six book PDFs is what a language model will read to build story cards and scripts. The audit found the body prose almost error-free, but the structure is damaged:
- garbled headings, artist names and years (Hodge)
- lost accents (Hagen)
- wrong reading order (Brooke-Hitching)
- lost first letters at chapter openings (Dasal, Brooke-Hitching)
- pull quotes, captions, credits and notes mixed into the body (Payne, Grovier)

The clean text fixes these.

## Fidelity rule

The clean text restores **what is printed on the page**. It is a correction of extraction errors, not an edit of the book.
- Never paraphrase, shorten, modernise or improve the author's wording, grammar or spelling.
- When the text layer and the page image disagree, the page image wins.
- When a word cannot be read with confidence, keep the best reading and record the doubt in `meta.json`. Do not guess silently.
- **Exception, `grovier_nws` only.** That PDF is itself a machine-translated edition, and some proper names are mangled in the print (for example "Dintoreto"). A mangled proper name may be corrected only when the right name is certain from the same book (its table of contents, captions or index) or is the unmistakable name of the artist or work under discussion. Log every such change in `meta.json` under `corrections`. Leave unclear sentences as printed and list them under `issues`.

## Files

`library/clean_text/<book_id>/page_<NNNN>.txt`: UTF-8, one file for EVERY PDF page of the book (1-based, zero-padded to 4 digits), so the numbering is continuous.

`library/clean_text/<book_id>/meta.json`: one per book.

```json
{"book_id": "hodge_aid", "generated": "2026-11-16T12:00:00Z", "format": 1,
 "pages": {"0022": {"type": "body", "printed_page": "18",
                    "method": "script|script+vision|read",
                    "read_by_model": false, "confidence": "high|medium|low",
                    "issues": [], "corrections": [{"from": "", "to": "", "reason": ""}]}},
 "summary": {"pages": 440, "by_type": {}, "by_method": {}, "read_by_model": 0,
             "residual_error_estimate": "…", "known_gaps": []}}
```

## Page file format

- **Line 1** is always the page type: `[page-type] <type>`, where `<type>` is one of `body`, `plate` (a picture only), `blank`, `front`, `contents`, `notes`, `credits`, `index`, `back`.
- **Headings.** `# ` marks the title of a chapter or an entry (the work's title). `## ` marks a section heading inside it, including the detail headings in Hodge.
- **Entry metadata printed under a title** (artist, year, medium, size, location): one line each, as `[meta] <text>`.
- **Body.** One paragraph per line with no hard wraps, and a blank line between paragraphs. Paragraphs are in reading order. Words broken across lines are rejoined, and soft hyphens are removed.
- **Tagged lines:**

  | Tag | Use |
  |---|---|
  | `[caption] <text>` | a picture caption |
  | `[credit] <text>` | a picture credit or source line |
  | `[note] <text>` | a footnote, endnote or bibliography entry |
  | `[quote] <text>` | an epigraph or a block quotation that is part of the content |

- **Removed:**
  - running headers and footers
  - printed page numbers (the number goes in `meta.json` as `printed_page`)
  - pull quotes that repeat a body sentence
  - note-reference digits glued to words ("get.2" becomes "get.")
  - text that OCR produced from inside a picture
- **Continuation.** If the last paragraph continues later, the last line of the file is `[continues]`. "Later" means the next page of type `body`: a paragraph that jumps over one or more plate pages still gets the marker. A reader joins it to the first paragraph of the next body page.
- **Sidebars and boxed asides** are content, but they are not part of the main flow. Wrap them between a line `[sidebar-start] <title or empty>` and a line `[sidebar-end]`. A reader that wants only the main argument can skip the block.
- **Headings are what the page prints.** A chapter or entry title is taken from the page itself, never from a table of contents or a catalogue file. If the page prints a chapter number, keep it as `[meta] CHAPTER n` (or the printed form).
- **Margin captions.** When two captions share a margin, each is its own `[caption]` line with its own words. Never interleave them line by line.
- **Drop caps** are rejoined to their word.
- **Not restored:** italics and other typographic emphasis.

## Checks every cleaner must run

- A file exists for every page.
- No `¬` remains.
- No line longer than 4,000 characters, unless it really is one paragraph.
- The word count of each body page is within a sensible margin of the text layer, once the removed elements are accounted for. Explain the outliers.
- A sample of at least 30 cleaned pages per book, spread over the book, is compared with the page images by reading them. The residual error estimate and what remains wrong are reported honestly.
