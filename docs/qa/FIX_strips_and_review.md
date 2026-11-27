# Subject name strips: narration-phrasing drop and one strip per subject

> Scope note: per coordinator (`t104`), item 3 (viewer review follow-up and `review_incomplete`) was reassigned to worker `reviewfix`. `bti/draft/review.py` and all shared UI/check lists were left untouched.

## Cause of missing strips (#1)

`_subject_overlays` in `bti/draft/compile.py` emitted subject `X-ANN-01` strips through `_Compiler.build_overlay`, which ran `screen_text_check` (meant for agent-written specs) and rejected any overlay whose `params` matched 5 or more consecutive narration words (`copies_narration`, `NARRATION_GRAM = 5`), emitting a `narration_on_screen` error and returning `None`. Because `giovanni_arnolfini` (`sub`: `"probably the merchant Giovanni Arnolfini"`) and `costanza_trenta` (`sub`: `"probably Costanza Trenta, or a later second wife"`) have `sub` phrases matching the narration verbatim, both strips were dropped on `s0105` and `s0320` (leaving 3 `narration_on_screen` errors in `proposals/draft_20261126-151859.json`).

## What changed

- **`bti/draft/compile.py`**:
  - `_Compiler.build_overlay` gained `check_narration: bool = True` (defaulting to `True` so agent-written overlays in `build_doc` are still checked and rejected by `screen_text_check`).
  - `_Compiler._subject_overlays` passes `check_narration=False` when building compiler-generated `X-ANN-01` subject strips from `picks.subjects`.
  - `_Compiler._subject_overlays` now tracks `names_seen` and `planned_keys` by subject identity (`sub.get("id") or tuple(VC.tokens(sub.get("name")))`) rather than `(sub_id, name_tokens)`, and sorts `name_events` by `(word_index, -len(name_tokens))`, so each subject receives at most one strip in a video at the first moment one of its names is spoken while visible.
- **`tests/draft/test_subject_beats.py`**:
  - Added `test_subject_strip_with_narration_phrasing_in_sub_is_not_dropped` (reproducing #1 with invented data) and `test_subject_with_five_word_proper_name_is_not_dropped`.
  - Added tests for one-strip-per-subject: `test_subject_with_two_names_in_one_sentence_gets_one_strip`, `test_later_alias_on_later_shot_gets_no_second_strip`, and `test_alias_spoken_first_while_visible_uses_spoken_alias_and_suppresses_canonical_name`.
  - Updated the four earlier alias-per-strip tests (`test_each_proper_alias_is_shown_once_and_descriptions_are_not_names`, `test_alias_is_only_introduced_once_when_repeated`, `test_short_name_inside_full_name_waits_until_spoken_on_its_own`, `test_subject_strips_do_not_overlap_when_two_names_are_spoken`) to match the one-strip-per-subject rule.

## Read-only verification on `arnolfini-v3`

Re-compiling the decompiled `draft_20261126-151859` specs with `arnolfini-v3` inputs (read-only inside snapshot):
- `narration_on_screen` count: `0` (was 3).
- `Giovanni Arnolfini` gets 1 strip (`s0478` / `s0105`, `t=12.23`, `dur=3.20`) and no second `"Hernoul le Fin"` strip later.
- `Costanza Trenta` gets 1 strip (`s0478` / `s0105`, `t=18.08`).
- `Philip the Good` gets 1 strip (`s0494` / `s0433`, `t=95.07`, `dur=3.13`) and no `"Duke of Burgundy"` strip.
- `Jan van Eyck` gets 1 strip (`s0493` / `s0319`, `t=91.68`) and no second `"van Eyck"` strip at `340 s`.

## Verification

- `tests/draft`: `637 passed, 1 warning in 217.32s (0:03:37)`
- `tests/picks`: `492 passed, 1 warning in 142.45s (0:02:22)`
- `tests/editor`: `534 passed, 1 warning in 284.07s (0:04:44)`
- `tests/auto`: `269 passed, 1 warning in 109.08s (0:01:49)`
- `tests/ops`: `556 passed, 1 warning in 207.08s (0:03:27)`
- `tests/cli`: `132 passed, 1 warning in 60.11s (0:01:00)`
- `tests/export`: `87 passed, 2 skipped, 1 warning in 62.14s (0:01:02)`
- `tests/identity`: `106 passed in 4.59s`
- `tests/engine -m "not slow"`: `854 passed, 14 skipped, 168 deselected in 424.73s (0:07:04)`
- Generators (`bti.cli.docgen --check`, `bti.ops.doc --check`, `bti.editor.hints --check`): exited `0`
- Mac Node tests (`node --test tests/editor_frontend/*.test.mjs tests/picks/*.test.mjs tests/output/*.test.mjs`): `tests 504`, `pass 503`, `fail 0`, `skipped 1`
