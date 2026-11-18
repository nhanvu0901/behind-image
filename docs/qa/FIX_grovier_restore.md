# Restore the machine-translated Grovier book into proper English (tool, phase 1)

Date: 2026-11-18. Worker: dgrovier. Status: the tool is built and tested with the `mock` provider only. It has NOT been run
on the real book with a real model; the analyst does that.

## What it does

`grovier_nws` ("A New Way of Seeing", 57 works) exists only as a machine translation back into English. The tool puts one work
(chapter) at a time into proper English through ONE call of the project's single-turn model provider (`bti/script/providers`,
model id from `bti.settings.model_for("library.restore")`, default `agy:gemini-3.8-flash-high`). Only the pages of type `body`
are sent; every other page (plates and so on) is copied as it is. The model's answer is checked by code; if any check fails the
work is retried once with the problems listed in the prompt, and if it fails again the work is left unrestored and reported.
Nothing of a work is written before its answer passes every check.

Files (all new): `tools/clean_text/restore/` (`PROMPT.md`, `pages.py`, `checks.py`, `run.py`, `__main__.py`),
`tests/clean_text/` (`test_restore.py`, `restore_helpers.py`), role `library.restore` in `config/agents.json`,
`library/restored/` in `.gitignore`.

## Commands

Run from the repository root, with `BTI_NO_REAL_MODELS` NOT set (with `BTI_NO_REAL_MODELS=1` a real model is refused, exit code 3,
before anything is read or written; `--model mock` always works).

```
# 1. look first: lists works, body pages, prompt sizes; calls no model, writes nothing
python -m tools.clean_text.restore --book grovier_nws --work 39 --dry-run --print-prompt

# 2. one work (here 39, The Scream); also  --work 5,7  and  --work 10-20
python -m tools.clean_text.restore --book grovier_nws --work 39

# 3. the whole book (57 works, one after another)
python -m tools.clean_text.restore --book grovier_nws
```

Other options: `--model <id>` (default: role `library.restore`), `--out DIR` (default `library/restored/grovier_nws`),
`--clean-dir DIR` (default `library/clean_text/grovier_nws`), `--force` (redo works that are already done).
Run one instance at a time (they share `report.json`). Stop with Ctrl-C at any time: the report is rewritten after every work.
Exit codes: 0 all selected works restored or already done; 1 at least one work failed (run the same command again to retry
exactly those); 2 bad arguments or setup; 3 real models switched off.

Expected time (an estimate, not measured: no real model was run): the body pages of a work are 2,500 to 6,600 characters
(about 600 to 1,600 words), so one call is small. Plan on 1 to 3 minutes per work with the agy CLI (start-up plus generation), twice
that when a work is retried. The whole book: roughly 1.5 to 3 hours. Time the first work (`--work 39`) and extrapolate.

## Three kinds of damage, and the readings block (added after the first real runs)

The first real runs of work 39 showed two models behaving differently where the machine translation has the WRONG MEANING
("an example of sexual anxiety" for existential anxiety): one kept it literally, the other replaced it silently. The prompt now
separates three cases: (1) clumsy wording, fixed silently; (2) wrong meaning that the passage itself makes clear: the model
may write the intended meaning and MUST declare it as a line `literal form in the input => what you wrote` in an optional second
closing block `=== readings ===` (after `=== names ===`); (3) cannot tell: the most literal reading wrapped in `[[? ... ?]]`.
Rules given to the model: a reading only from the chapter's own context, never from outside knowledge of the artwork; a number,
date, name, place, material or other specific is never read differently; in doubt, case 3. The prompt also tells the model to keep
quotation marks and dashes as in the input.

Checks on the readings block (optional; when present): every line is `old => new`; old and new differ; the old form occurs in the
input of the work; the new form occurs in the restored text (comparison ignores case and spacing). Any violation REJECTS the
answer (so it is retried with the problem listed). Warnings only: more than 12 readings in one work; readings covering more than
3 percent of the input characters (the model is rewriting, not restoring); a straight double quote in the result where the input
had only curly ones.

The prompt template is now part of the input hash (`input_hash` in `run.py`: the hash of the template text plus the input pages). Any
change to `PROMPT.md` therefore makes every work count as changed, and the next run restores it again; `prompt_sha` in the report
shows which prompt produced the last report update. Results made with the old prompt (for example work 39 in
`library/restored/grovier_nws/`) are redone by the next run without `--force`.

## Round 3: which problems reject a work, which only warn (after the first real runs)

Rejections (the answer is retried once, then the work fails) are only for what makes the text unusable: pages missing, doubled or
out of order; structural lines or the paragraph sequence changed; length out of range; a number added; prompt text leaking;
unbalanced `[[?` / `?]]`. The `names` and `readings` blocks are audit lists and NEVER reject:

- A readings or names line that is malformed, whose old form cannot be found in the input, whose new form cannot be found in the
  output (readings), or whose two sides are equal is left out of the list and recorded with the line itself: in
  `works.<n>.readings_dropped` / `names_dropped` (`{"line", "why"}`) and as a warning; `summary.readings_dropped` and
  `summary.names_dropped` count them. Look at them: many dropped lines mean the model does not give forms exactly as in the input.
- Finding a form is tolerant: case, runs of whitespace, curly versus straight quotes, apostrophes and dashes, surrounding quotation
  marks and final punctuation are ignored; an ellipsis (`...` or the single character) in the middle of a long form splits it into a
  part before and a part after, found in this order.
- The warning "readings cover more than N percent of the input" is now 8 percent (was 3); more than 12 readings still warns.

Every attempt is recorded: `works.<n>.attempt_problems` is a list with one list of problems per rejected attempt (a failed model
call counts as one), kept also when a later attempt passes, `[]` when the first answer passed. The log line of a rejected attempt
prints the problems (shortened). Use it to see which checks reject real answers.

A saved answer is not paid for twice: a failed work keeps its raw answers in `_failed/work_NNN_tryK.txt`. On the next run, when the
report says the work failed for the same input hash (same pages AND same prompt), those answers are checked with the current checks
first (the later try first); one that passes is used without a model call, and the report has `from_saved: true`, `saved_file` and
`attempts: 0`. `--dry-run` shows read-only, per failed work, whether the saved answers would pass now.

## How to read the readings list

Open `report.json` and read `summary.readings_all` first: every declared reading as `literal form => what the model wrote`, with the
number of works that have it, next to `summary.names_all`. This is the one place where a person reviews every place where the
restored text says something the machine text did not literally say. For each line ask: does the same chapter really make the
intended meaning clear, and is it a wording only (never a number, name, place or material)? To find the sentence, search the
restored pages for the "to" text; `works.<n>.readings` lists them per work. A work with a `warnings` entry about "more than 12
readings" or "percent of the input" deserves a full read: the model rewrote instead of restoring. Undeclared changes of meaning
cannot be detected by code, so a sample read against the cleaned pages is still needed. To undo a reading, edit the restored page by
hand (a work with `ok` and the same hash is then not touched by later runs) or add the phrase to the prompt as a thing not to change.

## Output

`library/restored/grovier_nws/page_NNNN.txt`: same format as `library/clean_text/` (restored pages for body pages, byte copies for
the others). Only the works of the catalogue are covered (pdf pages 17-380); the front matter, the introduction (already natural
English) and the end matter are not part of it. `library/restored/grovier_nws/report.json`: the report. `library/restored/grovier_nws/_failed/work_NNN_tryK.txt`:
the raw answers of a work that failed, for you to read (removed when the work later succeeds).

## Reading `report.json`

Top: `summary` (`ok`, `failed`, `not_run`, `unclear_passages`, `name_corrections`, and `names_all`: every `old => new` pair with
the number of works that used it; read this first, one wrong pair here is a wrong correction everywhere), `prompt_sha`, `updated`.
Under `works.<n>`:

| field | meaning |
|---|---|
| `ok`, `result` | `true` / `ok`, or `false` and a reason: `failed_checks`, `failed_model_call`, `input_missing: <page>`, `input_bad_first_line`, `no_pages_in_catalogue` |
| `failures` | for a failed work: the problems of the last attempt, in plain words. `first_attempt_failures`: those of the first attempt |
| `attempts`, `seconds`, `model` | 1 or 2 calls; time of all calls of the work; the model id used |
| `names` | the corrected names, `{"from","to"}`; only pairs whose old form really is in the input |
| `readings` | the declared readings of the work, `{"from","to"}` (see "How to read the readings list") |
| `unclear`, `unclear_by_page`, `unclear_chars` | count of `[[? ... ?]]` passages the model could not understand, per page, and their total characters; search the restored pages for `[[?` to read them |
| `length_ratio`, `page_ratios` | restored length / original length, for the work and per page (checks allow 0.6 to 1.5; pages under 300 characters 0.5 to 2.0) |
| `warnings` | things that do not reject a work but deserve a look (see below) |
| `new_capitalised_words` | capitalised words in the result that are neither in the input nor in the names block: the quickest way to spot an invented name |
| `input_hash` | hash of the prompt template and the input pages; a work with `ok` and the same hash is skipped on the next run |

Warnings to look at: a name listed as corrected that still occurs in the text (inconsistent correction); numbers of the original
missing from the result (a dropped sentence or a number turned into words); capitalised words not in the input; a names line
ignored because its old form is not in the input (the model invented a correction); text before the first marker (ignored).

## The checks (by code, per work, before anything is written)

1. The same body pages come back, once each, in order; a `=== names ===` block follows the last page and nothing follows it.
2. Every page has the same line structure as the original: same sequence of structural lines (`[page-type]`, `# `, `## `,
   `[meta]`, `[caption]`, `[credit]`, `[note]`, `[quote]`, `[continues]`, `[sidebar-start]`, `[sidebar-end]`) and prose paragraphs;
   so the number of paragraphs per page is the same, and no tag was invented. The blank-line layout of the answer is discarded
   and the original's is used, so only content can fail.
3. A structural line may change only by a name: its digits must be identical and it must stay at least 0.75 similar; the
   `[page-type]` line must be identical.
4. Length per page: 0.6 to 1.5 of the original (0.5 to 2.0 under 300 characters). Per paragraph (original at least 200
   characters): 0.4 to 2.0.
5. No line of the prompt (instructions, example, retry text) appears in the answer or in the names block (a line that the input itself has is exempt).
6. No number that is not in the original prose was added (dropped numbers are only a warning).
7. `[[?` and `?]]` are balanced on every line.
8. Names block lines look like `old => new`; lines whose old form is not in the input are dropped with a warning.
9. The optional readings block (see above): malformed lines, an old form not in the input or a new form not in the output reject the answer.

## Weak points to expect on the real text

- Plate pages (about 160 of the 364 pages) are copied as they are, so the captions on them keep their mangled names ("Edward
  Monk"). Only captions on body pages are corrected. A later step could apply the `names_all` pairs to plate captions.
- The model may rewrite short structural lines (headings, `[meta]`) more than names; that fails the 0.75 similarity check and costs
  a retry. If it happens a lot, loosen `STRUCT_SIMILARITY` in `checks.py`.
- Number words: a model that writes "twenty thousand" for "20,000" is a dropped-number warning, and one that writes "1,889" for
  "1889" is fine (commas are ignored); a digit it adds is a rejection.
- Poems and diary quotations given as many one-line paragraphs: merging them fails the paragraph count.
- Added knowledge is only partly detectable: the checks catch added numbers, big length changes and new capitalised words. Added
  adjectives or explanations of normal length pass. The analyst's read of a sample (and of every `[[?` passage) is still needed.
- Name corrections are the model's judgment; the book's table of contents line is given to it as a hint, not as truth.
