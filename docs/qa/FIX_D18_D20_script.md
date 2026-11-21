# Fix report: D18 and D20 (Script stage)

Written by worker `dscript` on 2026-11-18.

---

## D18. Step 2: any book can be left out as a source

### 1. Cause
Previously, brief options only supported `include_low`, which allowed ticking in low-trust (machine-translated) books. Trusted books were always included and could not be ticked out. Furthermore, outline validation did not distinguish between citations of excluded sources and unknown source ids. Approving an outline also validated with `brief=None`, so sources could not be checked during approval. On the page, the "Nguồn" column only displayed an inclusion checkbox for low-trust books.

### 2. Changes Made
- `bti/script/brief.py`:
  - `OptionsError` (`bti/script/brief.py:111-115`): Added `code` field (default `"options_error"`).
  - `_options_from` (`bti/script/brief.py:102-109`): Added `"exclude"` parsed as a list of strings (`[str(x) for x in exc if isinstance(x, (str, int))]`).
  - `check_options` (`bti/script/brief.py:117-147`): Added validation for `"exclude"` ensuring it is a list of strings (`book_id`, `work_id`, or `source_code`) and returns a sorted deduplicated list. Raises `OptionsError("exclude must be a list of strings (book ids, work ids or source codes)")`.
  - `save_options` (`bti/script/brief.py:150-180`): Validates that at least one source remains included after applying options. If all project sources would be excluded, raises `OptionsError("at least one source must stay", code="at_least_one_source")`.
  - `build_brief` and `_build_brief` (`bti/script/brief.py:217-295`): Added `exclude: list[str] | None = None` parameter. Determined `is_excluded = e["book_id"] in excluded or e["work_id"] in excluded or code in excluded`. Set `included = (not is_excluded) and ((not low) or is_low_included)`. Added `"excluded": is_excluded` to source entries. `brief["options"]` returns sorted `"exclude"`.
- `bti/script/validate.py`:
  - `validate_outline` (`bti/script/validate.py:62-95`): When `brief` is provided, separates `active_paras` from `excluded_paras`. For each fact, if it cites an excluded source and at least one non-excluded source remains, emits warning `source_excluded`. If every cited source is excluded, emits error `source_excluded` (blocking approval). Emits `unknown_source_id` only for paragraphs not present in any source.
- `bti/editor/script_api.py`:
  - `put_brief_options` (`bti/editor/script_api.py:166-173`): Passes `library_root=library_root` to `save_options`. Catches `OptionsError` and raises `ApiError(422, str(e), code=e.code)`.
  - `outline_approve` (`bti/editor/script_api.py:253`): Calls `validate.validate_outline(o, brief_for(d))` so that `source_excluded` errors block approval.
- `bti/editor/static/js/errmsg.js`:
  - Under `/* worker dscript */`:
    - Added `[/at least one source must stay/i, 'Phải giữ lại ít nhất một nguồn sách.']` to `CATALOG` (`bti/editor/static/js/errmsg.js:65-66`).
    - Added `at_least_one_source: () => 'Phải giữ lại ít nhất một nguồn sách.'` to `BY_CODE_HTTP` (`bti/editor/static/js/errmsg.js:268-269`).
    - Added `source_excluded` builder to `BUILD` (`bti/editor/static/js/errmsg.js:350-351`) for validation issue messages in Vietnamese.
- `bti/editor/static/js/views/script.js`:
  - In `srcBody` (`bti/editor/static/js/views/script.js:324-332`): Rendered "Dùng sách này làm nguồn" checkbox for every source (checked if `src.included`), keeping low-trust warning / description visible.
  - Added `toggleSource(src, box)` (`bti/editor/static/js/views/script.js:377-393`) to update `include_low` and `exclude` sets and call `setOption`.
  - In `loadModels` (`bti/editor/static/js/views/script.js:927-945`): Simultaneously fetches `/api/models` and `/api/settings/models`, storing role models for `script.outline` and `script.narration`. Preselects the model using role settings.
  - In `runDialog` (`bti/editor/static/js/views/script.js:673-678`): Uses role model setting for `script.outline` or `script.narration` when opening the generation dialog.

### 3. Neighbouring Cases Covered
- Excluding by book id (e.g. `"payne_gae"`), work id (e.g. `"payne_gae/002"`), or source code (e.g. `"PAY"`).
- Ensuring paragraph IDs of remaining sources do not change.
- Facts citing both excluded and active sources receive a warning `source_excluded` and are not blocked from approval.
- Facts citing only excluded sources receive an error `source_excluded` and block approval in `outline_approve`.
- Attempting to exclude all sources raises 422 with `code: "at_least_one_source"`.
- Syntax validation on `exclude` option (must be list of strings).

### 4. Tests and Exact Counts
- `tests/script/test_brief.py`: 7 passed (including `test_exclude_option_and_source_omission`). Ran on Windows server via `tools/deploy/snapshot_test.sh dscript`.
- `tests/script/test_validate.py`: 27 passed (including `test_outline_source_excluded`). Ran on Windows server via `tools/deploy/snapshot_test.sh dscript`.
- `tests/editor/test_script_api.py`: 16 passed (including `test_brief_options_exclude_and_approval_gate`). Ran on Windows server via `tools/deploy/snapshot_test.sh dscript`.
- `tests/editor_frontend/errmsg.test.mjs`: 13 passed on Mac.
- `tests/editor_frontend/no_null_children.test.mjs`, `no_raw_text.test.mjs`: 4 passed on Mac.

---

## D20. The model's narration sentences are too long (median 23 words)

### 1. Cause
Prompt guidelines lacked an explicit, strict sentence length rule (previously allowing mostly 8 to 22 words with vague permission for "a few longer"). There were no concrete examples demonstrating how to split a long, complex sentence into shorter spoken units. In validation, there was no check warning about beats with sentences over 28 words, nor a summary line reporting the median sentence length of the script.

### 2. Changes Made
- `prompts/rules_voice.md` (`prompts/rules_voice.md:27-36`):
  - Updated section 6 target: "Most sentences must be 8 to 18 words, and none over 28: one idea per sentence, written for the ear."
  - Added two short before/after examples of splitting a 30+ word sentence into two clean 14-17 word spoken sentences.
- `prompts/script.md` (`prompts/script.md:19`):
  - Added explicit target sentence length rule under `HOW TO FOLLOW THE OUTLINE`: "Target sentence lengths for the ear: most sentences 8 to 18 words, none over 28, one idea per sentence. Split longer ideas into clean, separate sentences."
- `bti/script/validate.py`:
  - Imported `sentences` from `.stats` (`bti/script/validate.py:10`).
  - In `validate_narration` (`bti/script/validate.py:185-192`): Checks every beat's sentences using `sentences(b.text)`. Emits warning `long_sentence` naming the beat and chapter if any sentence exceeds 28 words: `Beat {b.id} in {c.id} has a sentence with {max_w} words (more than 28); split it.`.
  - Added summary line (`bti/script/validate.py:214-216`): Emits info issue `sentence_median` with `Median sentence length: {med} words (target 8 to 18, none over 28).`.
- `bti/editor/static/js/errmsg.js`:
  - Added under `/* worker dscript */`:
    - `long_sentence` builder in `BUILD` (`bti/editor/static/js/errmsg.js:366`): `Dòng {beat} có câu dài ... từ (trên 28 từ); nên tách ra.`.
    - `sentence_median` builder in `BUILD` (`bti/editor/static/js/errmsg.js:374`): `Độ dài câu trung vị của kịch bản: ... từ.`.
- `tests/script/script_helpers.py` (`tests/script/script_helpers.py:19-35`):
  - Updated `words(n)` fixture generator so that long dummy text splits into natural sentences of <= 14 words with capital letters and period stops, while keeping total words exactly `n` and exactly one trailing `end.`. This allows tests expecting clean narrations to not trigger spurious `long_sentence` warnings while preserving assertions on word count and `end.` occurrences.

### 3. Neighbouring Cases Covered
- Beats with multiple sentences where only one exceeds 28 words correctly trigger `long_sentence` with the maximum word length reported.
- Sentences of exactly 28 words do not trigger a warning.
- Float and integer median sentence lengths in the summary line formatting.
- `long_sentence` issues correctly appear on the page under each affected beat via `issueHint` and in the Check dialog (`checkDialog`).

### 4. Tests and Exact Counts
- `tests/script/test_prompts.py`: 9 passed (including `test_sentence_length_targets_and_split_examples`). Ran on Windows server via `tools/deploy/snapshot_test.sh dscript`.
- `tests/script/test_validate.py`: 27 passed (including `test_warning_long_sentence_and_median_summary`). Ran on Windows server via `tools/deploy/snapshot_test.sh dscript`.
- Full test suite `tests/script`: 135 passed, 6 skipped in 10.07s on Windows server via `tools/deploy/snapshot_test.sh dscript`.
- `tests/editor/test_script_api.py`: 16 passed in 4.93s on Windows server via `tools/deploy/snapshot_test.sh dscript`.
- `tests/editor_frontend/errmsg.test.mjs`: 13 passed on Mac.
- `tests/editor_frontend/no_null_children.test.mjs`, `no_raw_text.test.mjs`: 4 passed on Mac.

---

## 5. Needs Another Worker
- In `bti/editor/draft_api.py`, 9 error codes were added by another worker (A-core): `bad_action`, `not_needs_choice`, `turn_data_lost`, `already_undone`, `turn_not_applied`, `undo_unavailable`, `undo_conflict`, `undo_failed`, `escalate`. To satisfy `tests/editor_frontend/stages_words.test.mjs`, Vietnamese translations for these 9 codes need to be added to `STAGE_CODES.draft` in `bti/editor/static/js/errmsg.js`.

---

## 6. Objections
- None. All requirements implemented according to `docs/qa/DEBTS_2026-11-18_decisions.md`.

---

## 7. Anything Left Open
- None. Both D18 and D20 are complete and verified with passing snapshot tests on the Windows server and JavaScript tests on the Mac.
