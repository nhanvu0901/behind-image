# FIX_script_voice: the narration sounds like a narrator, keeps to its length and never speaks a note meant for the owner

Worker `fixscript`, 2026-11-19, branch `wt/fixscript`. Evidence: the first video made end to end with a real model (project `arnolfini-opus`, agent Opus): three
narrations of the same outline (v1: 95 author names in 2,060 words and a remark of the outline spoken twice; v2: 64 names and "the books"; v3: the accepted one),
and `.scratch/arnrun/LOG.md` findings F2, F3, F4, F6, F7. Trimmed copies are the fixtures of the tests: `tests/script/fixtures/arnrun/`.

## 1. The prompts: the old rule is gone, the new one is said once and in the prompts' manner

The cause of F3 was in the prompts themselves. The old wording (all removed, a test searches every prompt file, the brief's notes and the built prompts for it):

* `prompts/script.md`: "Where a fact has a conflict note, say plainly that the sources differ and name them by author." and "Sources marked RESTORED ... say whose they are."
* `prompts/rules_voice.md`: "with the author named when it matters ("Payne notes", "Hodge points out")", "a proposal, with its owner and its weak point", "disputed facts are told as a dispute: who says what", "say so, name both".
* `prompts/outline.md` 5: "use their ideas ... as the author's own, named once".
* `bti/script/brief.py` (it is part of the prompt): `RESTORED_NOTE` said `say "{who} argues"`, `CARE_NOTE` said "the narration says whose claim it is".

The new wording:

* `prompts/script.md`, "HOW TO FOLLOW THE OUTLINE":
  * "Each chapter's budget is a CEILING: do not go over it. Aim for 90 to 100 percent of it. A chapter over its budget is cut and written again, so cut it yourself while you write. The whole narration comes to {{TARGET_WORDS}} words or fewer."
  * "You are the narrator, not a reviewer of books. The fact table and its conflict notes say who said what, for the owner; the viewer has never heard of the books. NEVER speak the name of an author of a source, and never say "the books", "both books", "the sources", "this source", "that passage" or "the book says"."
  * "Where a fact has a conflict note, tell the disagreement as two readings of the same object, in your own voice ("one reading sees ..., another sees ...", "some historians think ..., others ..."). A dispute that does not serve the video's question is dropped, or said once without ceremony. A claim only one writer makes may be given as "one historian argues" or "it has been suggested", a few times in the whole narration."
  * "Name a person only when the person belongs to the story: the painter, the sitters, a patron, a scholar whose proposal is itself part of the painting's history (such as Panofsky in 1934)."
  * "Never speak a remark meant for the owner or about the quality of a source ("check this before it is used", "that passage may describe a different painting"). Leave the fact out of the narration instead."
  * "Sources marked RESTORED give readings of the painting, never established facts: tell their ideas as one reading among others, never in the author's name. Take no number, date or quotation from them unless the fact table also cites another source for it, and never guess what a […] mark hides." (the substance of the old rule is kept; only the author's name is out)
  * the task lines now say "- c02 THE ROOM: at most 230 words (aim for 207 to 230)".
* `prompts/rules_voice.md`: layer 2 "what is known: ... told as what happened or what was found ..., never as what a book says"; layer 3 "disputed facts are told as two readings of the same object, in your own voice ... A dispute that does not serve the question of the video is dropped, or stated once without ceremony"; a new rule 8, "THE VIEWER HAS NEVER HEARD OF YOUR SOURCES" (the coordinator's note, in the prompts' words: no author names, never "the books"/"the sources"/"this source"/"that passage"/"the book says", name a person only when he belongs to the story, "one historian argues" a few times, a remark that is not about the picture is never spoken); quotes: "Never quote a book about the painting."
* `prompts/outline.md`: step 4 "say what each source says, by its paragraph ids or its author: the fact table keeps the exact attributions for the owner. Say only what the sources say. A conflict is never a remark to the owner or an instruction ... a remark placed there gets spoken."; step 5 RESTORED "as readings, never stated as established fact (give such a fact the certainty likely at most, and word its claim as a reading)"; step 6 "never plan a chapter as a comparison of the books"; step 7 "Each budget is a ceiling"; a new step 8 for the NOTE line.
* `bti/script/brief.py`: `RESTORED_NOTE` "may be used as readings of the picture, never as established fact and never in the author's name: tell them as one reading among others"; `CARE_NOTE` "the narration tells it as a reading, not as an established fact". `restored_note()` lost its author parameter (the note no longer says the name).

**Notes for the owner (decision).** The outline had no place for a remark to the owner, so the model put one inside a fact's conflict text, from where the narration spoke it. Smallest sound way: a separate line kind. `NOTE: one sentence` anywhere in the outline layout is parsed into an optional list `notes` of the outline document (at most 5 of at most 600 characters, the prompt asks for 3), written to `outline.json` only when there are some (an outline without notes keeps its revision and its approval, so nothing on the server goes stale), shown among the checks of the page as the warning `outline_note` ("Ghi chú của mô hình cho bạn: ..."), and NOT rendered into the narration prompt (`render_outline` does not print it; a test pins this). The alternative "a rule that remarks go to an existing notes field" does not work for the outline: it has no such field (`purpose` and `conflict` are exactly what the narration is written from), while the narration does have one (the `note:` part of a `>>` line, "private, not read aloud"), and `rules_format.md` now says so for the narration. Cost: one optional field, one parser line, one check; no change to a page view (a page that saves the outline sends the notes back unchanged: the merge is key-generic; a box to edit the notes would be a change of `views/script.js`, see "Needs another worker").

## 2. The checks

New code `bti/script/sourcenames.py` (pure strings; the app's checks and the bench criterion read the same functions). Codes, where they are raised, their Vietnamese sentences (`errmsg.js` block `fixscript` at the end, `Object.assign(BUILD, ...)`, node --check ok; labels in `labels.js` block `fixscript`), and their place in the automatic run (`bti/auto_run/checks.py`, with the reason, and the generated table of `docs/AGENT_API.md` through `python -m bti.editor.hints`):

| code | gate | what | stops the run? | why |
|---|---|---|---|---|
| `source_author_named` | narration, per line | a surname of an author of a source book of the project (every source of the brief, included or not) as a whole word with its capital | **yes** | the voice that follows is about an hour of machine time and says every word; a name is a ten-second edit before the gate and an hour after it; the viewer has never heard of the books |
| `source_talk` | narration, per line | the line speaks about the sources themselves ("the books", "both books", "two of the books", "the sources", "this source", "that passage may ...", "this paragraph") or carries a doubt or a remark meant for the owner ("may describe a different painting", "unreliable translation", "the owner should check", "before it is used", TODO) | **yes** | same reason: it is the second half of "a review of books", and it is how the leaked remark was caught |
| `fact_for_owner` | outline, per fact | a fact's claim or conflict text addresses the owner or gives an instruction ("the owner should ...", "check ...", "before it is used", "should be checked", TODO) | **yes** | the narration is written from the fact table: a remark left there gets spoken (it did, twice); deleting it is cheap before the outline gate, and the stop comes before a model call |
| `outline_note` | outline, per NOTE line | the model's own remark to the owner | no (tolerated, logged with its count) | the narration never sees it and the outline already handled what it talks about; the page shows it among the checks. It is a warning, not info, so that it counts in the badge and in the run log. One line to move it to `STOPS` |

Counts on the real material (`tests/script/test_sourcenames.py`, run on the server):

| narration | lines | `source_author_named` | name mentions | `source_talk` |
|---|---|---|---|---|
| v1 (95 names, the leaked remark) | 71 | 57 lines | 95 (Payne 48, Hodge 31, Brooke-Hitching 16) | 8 lines: the two remarks ("that passage may describe a different painting / another painting") and 6 x "the sources" / "all three sources" |
| v2 (64 names) | 65 | 47 lines | 64 (36, 17, 11) | 7 lines: "the books" x 3, "Two of the books" x 3, "Both books" |
| v3 (accepted) | 62 | 0 | 0 | 0 (the "Book of Exodus" line is not a hit; no warning at all of any kind) |

The 95 and the 64 are the numbers the operator counted by hand. On the outline of the video, `fact_for_owner` flags exactly one fact of 55: `f10` ("the owner should check it before it is used").

False-hit decisions (all tested, in `test_sourcenames.py`):

* the surname must stand as a whole word with its capital: "Hodges", "hitching a ride" are not hits; the possessive "Payne's" is; a double surname is found by its last part too ("Brooke-Hitching", "Brooke Hitching", "Hitching's");
* a historical person who shares a surname: when another capitalised word stands before the surname inside a sentence ("Sir Thomas Hodge", "the sculptor John Payne") it is somebody else, and an article before it ("The Hagen family") is not an author either. The word before does NOT save the hit when it is the author's own given name ("Susie Hodge"), an initial ("J. Payne"), a title of a modern writer (Dr, Prof, Mr, Mrs, Ms) or the first word of its sentence ("Then Hodge says", "Both Payne and Hodge"). Known limit: a later bare "Hodge" for that other person is a false hit; the check is a warning for a person to read;
* "the Book of Exodus", "the books on the table", "the books and the globe", "He opens the book", "the only source of light", "two sources of light", "a source of income", "the passage in Exodus about holy ground" are not hits: plural "the books" counts only when no place or relation word follows, singular "the book" only when it SAYS something ("the book argues"), "sources" never before "of";
* the titles of the books are not looked for (some are plain phrases: "A New Way of Seeing"); the author field is parsed for "Rose-Marie and Rainer Hagen", "Payne, James", lists and suffixes; a surname under 3 letters is not looked for;
* Panofsky is not an author of a source and is never flagged (a test).

`narration_approve` now validates with the brief too, so a refused approval lists the same warnings as `GET .../narration`.

## 3. Length that binds

* The prompt states each chapter's budget as a ceiling (section 1). The mock provider now writes within the ceiling.
* `bti/script/generate.py`: after a chapter parsed and passed its format check, if it has more than `CUT_OVER_SHARE` = 10% over its budget and fewer than `MAX_CUTS` = 4 chapters of the job were already rewritten, the job calls the model ONCE more with `prompting.cut_note`: "YOUR PREVIOUS ANSWER IS TOO LONG. It has 310 words and the budget of this chapter is 250, a ceiling. Write the chapter again with at most 250 words (aim for 238): that is 72 words fewer. Keep its order, its best lines and the facts it rests on; cut the least necessary detail first ... Add nothing new. Here is your previous answer: <the chapter in the layout>". The rewrite replaces the first text only when it can be used (same format check) AND is nearer to the budget; otherwise the first text stays and the checks warn as before (`chapter_off_budget` at 30%, `words_off_target` at 15% of the target). A failed call (any error but a cancel) leaves the first text and the job goes on; a cancel cancels the job and writes nothing of the chapter. At most one retry per chapter, never a second one.
* Visible: the chapter's line in the progress says `đã cắt từ 310 xuống 247 từ (ngân sách 250)` (or `giữ bản đầu 310 từ, vượt ngân sách 250: ...`), `attempts` is 2 and the state is `retrying` while it runs; the job's `result` carries `"shortened": [{"chapter","words","budget","after","kept":"rewrite"|"first","why"?}]` (only when there is something to say, so the result of an ordinary job is unchanged).
* Cost: one model call more per rewritten chapter, at most 4 per job: a whole narration is 6 to 8 calls, at most 4 more. Said in `skills/script/SKILL.md`, `docs/APP_GUIDE.md` 5.2 and the bench's cost sentence (`bti/evals/driver.py` `COST`).
* On the real v1 (chapters +8, +21.7, +21.2, +23.2, +18.8, +16.1, +20.0, +3.6 percent) the rule retries the six chapters over 10%, but the cap lets only the first four (c02 to c05) have the second call. If each rewrite only comes down to its budget, 2,060 words become 1,848 (5.6% over the target of 1,750); if each stops at +10%, about 1,930 (10%): either way under the 15% line of `words_off_target`, and with the ceiling in the prompt the first answers are expected to be much nearer already (v3 came out within +4%). Arithmetic on the real numbers, not a model run.
* The skill document says what an operator does with a narration that is too long (section "A narration that is too long").

## 4. The one sentence limit

It was 28 in the prompts and in `long_sentence`, but 25 in the sentence profile and in the documents (`share_over_25`, "a quarter over 25") and 32 for the 90th percentile; a 26-word sentence passed silently. Now `bti/script/stats.py` `MAX_SENTENCE_WORDS = 25` is the only place: the prompts say `none over {{MAX_SENTENCE_WORDS}}` and `prompting.py` fills the word in (a test: no "28" and no literal 25 in the prompt files), `long_sentence` and the `sentence_median` message use it, the profile's `STYLE_TARGETS` lost the two vaguer limits (`p90_max` 32, `share_over_25_max`) and notes any sentence over the limit, the bench criterion `narration.max_sentence_words` and the case `narration-short-sentences` use 25, `errmsg.js` `long_sentence` reads the number from the message, `skills/script/SKILL.md` and `docs/APP_GUIDE.md` say 25.

## 5. The bench

`narration.no_source_author_named` (needs `narration` and `brief`; the narration driver now also reads `GET .../brief`): fails when a line names an author of the brief's sources or, with `talk` (default true), speaks of "the books" or "the sources". New case `evals/cases/narration/narration-no-source-names.json` (the narration cases are now 11). `narration.chapter_budgets` got `max_over` (the budget is a ceiling) and the case `narration-chapters-near-budget` uses 0.15. `narration.max_sentence_words` defaults to the app's limit.

## 6. Decisions where the brief was silent

* The outline notes (section 1): a document field `notes`, absent when empty.
* Three of the brief's four checks became two narration codes: the "books/sources" phrases and the reliability talk are one `source_talk` (one prompt rule, one decision, one sentence), the authors are `source_author_named`; the outline's conflict check also reads the claim and is called `fact_for_owner`; `outline_note` is new.
* The check reads the authors of ALL sources of the brief, included or not.
* No retry for author names or source talk: the brief asked a bounded retry for length only. It would cost one call per offending chapter and would make the automatic run self-repairing; it is a small extension of `_cut_once` (a second reason, a combined note) if the coordinator wants it after the real run.
* The rewrite is kept only when it is nearer to the budget (not merely shorter), because a rewrite that overshoots to half the budget is worse than the first text.
* `MAX_CUTS` is 4 and `CUT_OVER_SHARE` 10% (the target warning is at 15%, so a job whose chapters all stay under 10% over cannot trigger `words_off_target`).
* `chapter_off_budget` stays at 30% (the brief says "the existing warning").
* The sentence limit is 25 (the brief says a 26-word sentence passing silently was the defect), not 28.
* `fact_for_owner` and the two narration codes stop the run, `outline_note` does not.

## Needs another worker

* `bti/editor/static/js/views/script.js`: an optional box under the outline to show and edit `outline.notes` (today they are shown only among the checks; a page save keeps them).
* `bti/editor/state_api.py`: the `cost` of `narration.generate` still reads "model: a few minutes"; the extra calls are said in the documents, not in the action's cost text.

## Test results (server snapshot `fixscript`, fake agents only, no `-m slow`; one folder per run)

```
tests/script   352 passed, 7 skipped in 32.53s      (the 7 skips were there before: no time-zone database, demo_runs/claude_code/script.txt missing)
tests/state    295 passed, 1 warning in 183.56s (0:03:03)
tests/auto     194 passed, 1 warning in 73.86s (0:01:13)
tests/evals    63 passed, 1 warning in 11.04s
tests/cli      127 passed, 1 warning in 44.45s      (the first run had 1 failure, a word in code ticks of SKILL.md that the app does not have: fixed)
tests/editor   491 passed, 1 warning in 237.68s (0:03:57)
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs : tests 440, pass 439, fail 0, skipped 1
python -m bti.editor.hints --check / python -m bti.cli.docgen --check: exit 0 (the generated documents are fresh)
node --check bti/editor/static/js/errmsg.js, labels.js: ok
```

New tests: `tests/script/test_sourcenames.py` (the three real narrations and the real outline: flag, flag, pass; the false hits), `tests/script/test_cut.py` (the rewrite happens once and only for the chapters over the share, the cap, a rewrite that fails or cannot be used or is not shorter, a cancel during the rewrite), `tests/auto/test_script_checks.py` (every warning of the script step is sorted into STOPS or TOLERATED, has a Vietnamese sentence, the new ones a label), the NOTE lines in `test_parse.py`, the prompt tests in `test_prompts.py` (old wording gone, new rules there, one sentence limit), the bench criterion in `tests/evals/test_criteria.py`, three API tests in `tests/editor/test_script_api.py`, and a Node test of the new sentences. The mock provider writes within the ceiling and has the markers `[mock:long cNN]`, `[mock:alwayslong cNN]`, `[mock:cutbad cNN]`, `[mock:cutfail cNN]`, `[mock:cutslow]`.

## What only a real model run can show

* Whether Opus (and Gemini) obey the new prompts: author names and "the books" in a first narration written WITHOUT any note, how many lines the two new warnings flag, and whether the first answers now stay under the ceiling (the unit tests prove the checks and the job, not the model).
* Whether the cut note makes a model cut instead of rewriting freely, and how often `shortened` says `"kept": "first"`.
* Whether the outline model uses the NOTE line, and no longer leaves a remark inside a fact (`fact_for_owner` count on a fresh outline).
* Whether the false-hit decisions hold on other paintings (a surname shared with a person of the story).

The call to make (a fresh project, the one named `arnolfini-opus` is not to be touched): create `arnolfini-opus2` from the same artwork (`POST /api/library/projects {artwork_key: eyck-the-arnolfini-portrait, slug: arnolfini-opus2}`), set the target (`PUT .../brief/options {target_words: 1750}`), choose the same agent, then with NO note: `bti do arnolfini-opus2 outline.generate --yes-cost --wait`, read `GET /api/projects/arnolfini-opus2/outline` (`notes`, and `issues`: `outline_note`, `fact_for_owner`), approve, then `bti do arnolfini-opus2 narration.generate --yes-cost --wait` and read the job result (`shortened`), `GET .../narration` (`issues`: count `source_author_named` and `source_talk`; `stats.chapters` words against budgets). To measure it more than once: `python -m bti.evals run --step narration --case narration-no-source-names --case narration-chapters-near-budget --case narration-short-sentences --agent opus --repeat 3 --yes-cost` (about 8 to 12 calls per repeat).
