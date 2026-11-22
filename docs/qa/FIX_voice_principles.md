# Voice as Principles and No Painting-Specific Rules (`voiceplain`)

## 1. The Four Principles (as written in `prompts/rules_voice.md`)

1. **ORIENT BEFORE INTRIGUE.**
   Say what the work is, who made it, and who or what is in it before puzzling the viewer. Give the listener solid ground first so every strange detail lands.
2. **ONE NARRATOR, THE CHANNEL'S OWN VOICE.**
   Tell the story as our own looking and reasoning, never as a review of books or camps of experts.
   - Facts that are certain (`established`) are said plainly.
   - What is uncertain (`likely`) is said by the narrator in plain words ("probably", "could be", "maybe", a question, "if ..., then ..."), once, without attributing it to "a reading", "historians", "scholars", "critics", "sources", "a book", or "some/others". Do not sprinkle "perhaps" everywhere, and never state a guess as certainty.
   - A disputed point (`disputed`) is told as the narrator weighing two possibilities directly ("it could be a celebration, or it could be a warning"), never as camps of people. Drop a dispute that does not serve the video's question, or note it once without ceremony.
   - Name a person only when that person is part of the story itself (the artist, the sitter, a patron), never as an authority for an interpretation.
3. **NEVER MENTION A GESTURE, OBJECT OR SIGN WITHOUT SAYING IN THE SAME SENTENCE WHAT IT IS OR MEANS.**
   Never drop a detail and leave the viewer wondering why it matters. Name the gesture, object, or sign and say what it does or means in the same sentence.
4. **PLAIN, COMPLETE SENTENCES UNDERSTOOD AT FIRST HEARING.**
   Write for the ear: one idea per sentence, most sentences 8 to 18 words, and none over `{{MAX_SENTENCE_WORDS}}`. Mix longer sentences that gather a scene with short ones that land a point. Choose plain verbs and concrete nouns, explain any technical term at once with something the viewer can picture, use a metaphor only when it makes the thing easier to see, and split long stacked clauses into clean separate sentences.

`prompts/outline.md` and `prompts/script.md` now refer to these four principles in `HOW THIS CHANNEL NARRATES` instead of repeating them, and the old literature-review directives (`"tell the disagreement as two readings ..."`, `"tell their ideas as one reading among others"`, `"told as a reading ('one reading sees ...')"`, `"most historians accept"`) were removed.

## 2. Examples' Paintings (Five Kinds, Zero Arnolfini)

- **Landscape**: *Hunters in the Snow* (Pieter Bruegel the Elder, 1565) — Principle 1 Bad -> Good (`prompts/rules_voice.md`), Cold Open Example 1 (`prompts/script.md`), and `style/gae/techniques.json` (`CAM-03`, `X-ANN-01`).
- **Still life**: *Still Life with Pewter and Lemons* (explicitly marked invented painting) — Principle 2 Bad -> Good (`prompts/rules_voice.md`); pewter dish / fly detail in `style/gae/techniques.json` (`AN-01`).
- **Crowded religious scene**: *The Calling of Saint Matthew* (Caravaggio, 1600) — Principle 3 Bad -> Good (`prompts/rules_voice.md`) and `style/gae/techniques.json` (`CAM-05`, `LAY-01`); *The Feast in the House of Levi* (Paolo Veronese, 1573) — Cold Open Example 2 (`prompts/script.md`) and third owner verdict (`skills/title/TASK.template.md`).
- **Portrait**: *The Ambassadors* (Hans Holbein the Younger, 1533) — Principle 4 Bad -> Good (`prompts/rules_voice.md`), skull clue (`skills/title/TASK.template.md`), and `style/gae/techniques.json` (`HI-01`, `X-ANN-01`, `X-ANN-03`).
- **Altarpiece**: *The Isenheim Altarpiece* (Matthias Grünewald, 1515) — Principle 4 Bad -> Good (`prompts/rules_voice.md`).
- Existing non-Arnolfini *St. Eligius* (Petrus Christus, 1449) and comparative examples (La Tour, Rembrandt) were kept or expanded in `skills/title/TASK.template.md` and `style/gae/techniques.json` (`NUM-01`, `X-CMP-01`).

## 3. Painting-Specific Text Removed or Generalised

- **`prompts/rules_voice.md`**: removed Arnolfini split-sentence examples (*The Arnolfini Portrait*, *Bruges*, *1434*, *Jan van Eyck*, *Duke Philip the Good of Burgundy*, *convex mirror*, *clandestine wedding ceremony*, *private bedchamber*, *wealthy merchant granting legal authority to his wife*), *Panofsky in 1934*, and `"1434", "82 centimetres"` (replaced with `"1565", "117 centimetres"`).
- **`prompts/outline.md`**: replaced `"argued among historians"`, `"as readings ... word its claim as a reading"`, `"sets two readings of the picture side by side"`, `"as two readings of one object"`.
- **`prompts/script.md`**: removed Arnolfini cold-open worked example & counter-example (*The Arnolfini Portrait*, *Jan van Eyck*, *1434*, *Giovanni Arnolfini*, *Bruges*, *Costanza*, *1433*, *mirror*, *single candle*, *shoes*, *Costanza Trenta*, *ornate*, *sits uneasily*, *close looking*) and literature-review phrasing (*one reading sees*, *some historians think*, *one historian argues*, *it has been suggested*, *Panofsky in 1934*).
- **`prompts/rules_format.md`**: replaced `BUDGET: 190` -> `120`, `the inscription above the mirror` -> `the distant mountain peaks`, `## c02 THE MERCHANT CITY` -> `## c02 THE SETTING`, `the convex mirror; the inscription above it` -> `the open window; the signature on the table`.
- **`skills/title/TASK.template.md`**: removed `"one reading among others"`, `"one reading sees"`, `"already dead"`, `(a wedding, or a memory)`, `(two strangers watching from a mirror)`, `"The Two Strangers in the Mirror"`, and the *Arnolfini Portrait* / *Jan van Eyck* verdict block (`"Was She Already Dead When He Signed the Wall?"` / `"Is This a Wedding or a Memory?"`).
- **`style/gae/techniques.json`** (text fields only; 0 changes to technique ids, slots, params, defaults, timings, previews, or evidence): removed all 36 non-param/non-evidence Arnolfini/van Eyck/Costanza/Giovanni/1433/1434 mentions and Arnolfini object/dimension references across `CAM-03.example`, `CAM-04.usage_rule`, `CAM-05.{usage_rule,use_when,example}`, `TR-01.{usage_rule,use_when}`, `LAY-01.{use_when,example}`, `HI-01.example`, `AN-01.example`, `AN-05.{description,use_when}`, `STATIC-09.usage_rule`, `X-TR-01.usage_rule`, `X-ANN-01.example`, `X-ANN-03.{description,example}`, `X-CMP-01.example`, `TIME-01.usage_rule`, `TREE-01.{usage_rule,example}`, `MAP-01.usage_rule`, `KEY-01.usage_rule`, `NUM-01.{usage_rule,use_when,needs,example}`, `DOC-01.usage_rule`, `DIA-07.engine.notes`.
- **`bti/script/`**: generalised comments/docstrings in `cold_open.py` (`Costanza's`, `van Eyck's`, `Jan van Eyck was here, 1434`, `The Arnolfini Portrait`), updated `brief.py` (`RESTORED_NOTE`, `CARE_NOTE`), `validate.py` (`source_talk`), and `prompting.py` (`cut_note`).

## 4. Check Codes and Repair Behaviour

- **New warning code**: `attribution_phrase` (`bti/script/sourcenames.py` `ATTRIBUTION_PHRASES` + `find_attribution`, emitted at most once per beat anywhere in the narration by `bti/script/validate.py`). Checks `"one reading"`, `"another reading"`, `"a reading"` (with guard against `"a reading room/desk/lamp/table/stand/glass/glasses"`), `"has been read as"`, `"is read as"`, `"some see"`, `"others see"`, `"historians"`, `"scholars"`, `"critics"`, `"has been described as"`, `"according to"`, `"it has been suggested"`, `"is thought to"`, `"is believed"`.
- **Automatic run & UI wiring**: added `attribution_phrase` to `checks.STOPS["narration"]` (`bti/auto_run/checks.py`), `bti/editor/static/js/labels.js`, `bti/editor/static/js/errmsg.js`, and regenerated `docs/AGENT_API.md` via `bti.editor.hints`. Added `_deattribute` in `bti/script/providers/mock.py` so mock narration avoids echoing `"historians"` from test source files.
- **Cold-open checks kept**: `cold_open_missing_name`, `cold_open_late_name`, `cold_open_first_sentence_names`, `cold_open_first_line_long`, `cold_open_no_early_turn`, `cold_open_no_closing_question`, `cold_open_roadmap`, `cold_open_word_count`.
- **`STOCK_PHRASES` trimmed** (`bti/script/cold_open.py`): dropped `"sits uneasily"`, `"close looking"`, `"ornate"`, `"uncover"`, `"stands as"`, leaving the 11 general roadmap/cliché phrases (`"today we"`, `"in this video"`, `"let's find out"`, `"let's dive"`, `"join me"`, `"testament to"`, `"delve"`, `"tapestry of"`, `"hidden meaning"`, `"secrets of"`, `"more than meets the eye"`).
- **`narration.generate` repair**: reading `bti/script/generate.py` confirmed `run_narration` retries only `chapter_problems` (missing chapters / empty beats / markup) and chapters >10% over budget (`_cut_once`); it has no warning-repair loop.

## 5. Verification Summaries (exact printed lines)

- `tests/script`: `384 passed, 7 skipped, 1 warning in 40.11s`
- `tests/title`: `198 passed, 1 warning in 50.86s`
- `tests/auto`: `257 passed, 1 warning in 98.45s (0:01:38)`
- `tests/draft`: `556 passed, 1 warning in 190.75s (0:03:10)`
- `tests/engine -m 'not slow'`: `802 passed, 14 skipped, 166 deselected in 432.27s (0:07:12)`
- `bti.cli.docgen --check`: `docgen --check OK` (exit 0)
- `bti.editor.hints --check`: `hints --check OK` (exit 0)
- `python3 -m json.tool style/gae/techniques.json > /dev/null`: `json.tool OK` (exit 0)
- `node --test tests/editor_frontend/errmsg.test.mjs tests/editor_frontend/labels_registry.test.mjs`: `tests 26 | pass 26 | fail 0`
  *(Note: running all JS tests `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs` reports `tests 489 | pass 487 | fail 1 | skipped 1`, where the 1 failure is pre-existing `tests/editor_frontend/idfix.test.mjs` from `worker listmark` in `errmsg.js:908` overwriting `strip_without_light`.)*
