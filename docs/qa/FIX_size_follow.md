# FIX: the "recorded size = stored file's pixels" rule, carried into the draft, the storyboard check and two page messages (worker sizefollow)

Brief: `.scratch/agy_tasks/sizefollow/TASK.md`. Background: `docs/qa/FIX_media_size.md`. No request was sent to Wikimedia or any other
site by me or by any test (fakes only; `BTI_NO_REAL_MODELS=1` in the snapshot). I did not touch `bti/identity/**`, the other workers'
uncommitted files, the server's main folder or its app. Line numbers below are the working tree at the end of this task.

## 1. What each change does

1. **The draft corrects the picks' sizes** (`bti/draft/inputs.py` 16, 256, 276, 295-305). `load_inputs` now calls
   `bti.media.assets.reconcile_sizes(picks["assets"], project_dir)` instead of `fill_sizes`: a declared size that disagrees with the
   stored file becomes the file's size, the regions of that asset are scaled with it, the old size is kept as
   `original_width` / `original_height`, and a missing size is filled (the same function `bti.picks.doc.load` uses). It happens in
   memory, so a draft built before the corrected `picks.json` was written back compiles from the right size, and loading twice
   gives the same picks and the same hash. Two deliberate limits:
   - `current["assets"]` (the saved storyboard's own copy) still goes through `fill_sizes` only (line 305), as briefed.
   - When editing with no usable `picks.json`, the picks are a copy of the storyboard's assets (`picks_from_file = False`, line 276);
     they keep `fill_sizes` (line 301) so they agree with the storyboard they were copied from. Reconciling that copy would have shown
     the agent one size while the compiler used another, which is the hazard the brief names. (A small addition to the brief: it
     says "the picks' assets"; this is the one place where they are not the picks file's.)
2. **A storyboard that carries a wrong size says so** (`bti/engine/storyboard.py`). New warning `asset_size_mismatch`
   (`ISSUE_CODES` line 438; emitted at line 608-612 in `_validate`, in the same branch that already checks an asset's file; helper
   `size_mismatch` at line 354). It fires only when `project_dir` is given, the asset is an image (or a mask, see 4), its file
   exists and is intact (no `asset_file_*` error), it declares a positive `width` and `height`, and the stored pixel size
   (`bti.media.assets.stored_size`, header only) differs from either. Level `warn`, path `assets.<key>`, args `asset`, `width`,
   `height`, `stored_width`, `stored_height`. Nothing is rewritten. No new cache: `stored_size` already remembers sizes per (path,
   modification time, file size) (`assets.py` 123-141), and a test proves five validations measure each unchanged file once.
3. **The sentence** (`bti/editor/static/js/sbissues.js` 276-278, in `BY_ARGS`, inside a block marked `sizefollow`):
   `Hình "scream" được ghi là 6703 x 8322 nhưng tệp đã lưu là 3840 x 4767, nên khung hình sẽ lệch.` The brief's example ended with
   "Hãy dựng lại bản nháp ở bước 5." I left that sentence out on purpose, see section 3 (a re-draft would not clear the warning).
   The existing unit test that compares `ISSUE_CODES` with the page's templates (`sbissues.test.mjs`) passes with the new code.
4. **Step 4 search banner** (`bti/editor/static/js/views/picks.js` 14, 26, 338): an entry with `code === 'source_rate_limited'` shows
   `sourceLimitText(e)` (minutes, or "Thử lại sau." when unknown), every other code shows what it showed before. The expression is a
   one-line exported helper `searchErrorText` (line 26) used by the banner line (338), so a Node test can reach it without a browser
   (the view itself cannot be mounted in Node).
5. **The older import path** (`bti/editor/media_adapter.py` 85-89, `_translate`): a `MediaHTTPError` whose `rate_limited` is true is
   answered `503` with `code: "source_rate_limited"`, `retryable: true` and the real `retry_after` (whole seconds, `null` when the
   source gave none; same shape as `bti.picks.service`). 502, 504, a 503 without a time, and an unknown status keep today's sentence
   and `retry_after=10`; other statuses keep `502`. The page shows the minutes on this path too: `media.js` search (line 201) and
   import (line 216) both call `errorToast`, which calls `describeError` (`util.js` 59-61), which looks up `BY_CODE_HTTP` first and so
   gets `sourceLimitText`. A Node test checks both the body -> sentence and that the two call sites use `errorToast`. No page change was
   needed.

## 2. Tests

New files (fakes only):
- `tests/engine/test_asset_size_mismatch.py` (13): code documented, level, path, args and message; size that agrees, either side
  wrong, only the named asset, missing file, unreadable file, no project folder (also `None`), no declared size and an invalid one,
  a video asset (never compared), a mask, the answer follows a replaced file, an unchanged file is measured once over five
  validations, nothing is rewritten.
- `tests/draft/test_size_follow.py` (12): picks that declare another size than the file are corrected in the inputs (size,
  regions scaled, old size kept); the compiled storyboard's asset has the stored size and the scaled regions; a draft from the old
  wrong record equals a draft from a correctly written project (assets and shots); reading writes nothing; two loads give the same
  picks and hash; a missing size is filled; a missing or unreadable file leaves the declared size; the saved storyboard's own copy is
  not rescaled; the picks are corrected even when a storyboard exists; picks taken from the storyboard stay its own copy; the
  validator names a stale storyboard's picture; and a test that documents the finding of section 3.
- `tests/editor/test_media_adapter_limit.py` (14 cases): `_translate` with a wait (429 with 3, 600, 3600 s; 503 with a time), with no
  time (null, not ten seconds), whole-second rounding, the unchanged answers (503/502/504/None, 403, not-found, other exceptions),
  and through the real routes (import, search with and without a wait, a 503 with no time).
- `tests/editor_frontend/sizefollow.test.mjs` (9): the sentence, its table entry, a click on it leads to the picture; the banner
  text with a wait, without, and for every other code; the banner line uses `searchErrorText`; the body of the older import path
  shows minutes; both call sites of the picture tab use `errorToast`.

No existing test needed a change.

Run in my snapshot `sizefollow` on the server (summary lines as printed; `-q`):

```
tests/draft           : 243 passed, 1 warning in 85.05s (0:01:25)
tests/engine -m "not slow" : 304 passed, 14 skipped, 150 deselected in 180.69s (0:03:00)
tests/identity        : 77 passed in 0.92s
tests/media           : 274 passed in 1.28s
tests/picks           : 88 passed, 1 warning in 8.32s
tests/editor          : 449 passed, 1 warning in 199.98s (0:03:19)
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs
                      : ℹ tests 276 / ℹ pass 276 / ℹ fail 0
```
(Before my files the same node command gave 267 and tests/editor gave 435 (`FIX_media_size.md`); 267 + my 9 = 276 and 435 + my 14 = 449.)

## 3. Finding that changes the advice: a re-draft does not clear the warning

`bti/draft/compile.py` `_merge_assets` (129-137) copies the picks' assets and then lets the saved storyboard's own copy of every key
override them. I checked it with a probe on the synthetic project (storyboard saved with A declared 1600 x 2400, picks corrected to
the stored 800 x 1200): a whole re-draft and a one-chapter re-draft both still compile `assets.A` at 1600 x 2400 with the region in
that space. So the warning stays after a re-draft, and the brief's advice ("Hãy dựng lại bản nháp ở bước 5") would send the owner
round in a circle. I did not edit `compile.py` (not in my list) and I did not rescale the storyboard's copy (the brief rules it out:
camera keys of locked shots would move). `tests/draft/test_size_follow.py::test_a_redraft_still_carries_the_saved_storyboards_asset_size_today`
pins today's behaviour and fails when the compiler changes; the comment in the test and in `sbissues.js` says to add the advice back
to the sentence then. Decision needed from the owner of that code: what a re-draft should do with a stored copy whose size is wrong
(for example take the stored size for an asset that no locked shot uses, or add an explicit "adopt the stored size" action).

## 4. Smaller notes and choices

- Masks are compared like images (`reconcile_sizes` and `fill_sizes` treat both kinds alike); the brief named only images. Videos
  are never compared (their size is not a picture size the camera maths use).
- `picks.js` exports one more name (`searchErrorText`); the router still imports only `mount`.
- `docs/qa/FIX_media_size.md` section 5 items 1, 2 (the load-time reconcile of `sb["assets"]`), and 3 are not done here: 1 only for the
  picks (as briefed), 2 only as a warning (as briefed), 3 checked and not needed (see below).
- `bti/identity/apply.py` and `bti/editor/identity_api.py`: I did not change them. `identity_api.py` reads only `main_asset` from
  `picks.json` (re-read: no size). `apply.py` takes sizes from the storyboard's assets (`apply.py` `whole_keys`, 222-226), which a fresh compile
  builds from the corrected picks, but a storyboard that still carries a wrong size (section 3) gives the identity builder that same wrong
  size; the warning is how that is shown. Nothing was found that contradicts the brief's "not needed".

## 5. What I could not verify

- The real app in a browser: the banner and the warning sentence were checked by Node unit tests and by reading the call sites, not
  by looking at a mounted page.
- A real 429 from Commons (forbidden by the brief): the adapter was tested with a `MediaHTTPError` raised by fake media modules.
- The owner's real projects (never read): I cannot say which of them will show `asset_size_mismatch` once this runs on the server.
- The 14 skipped engine tests (listed with `-rs`): all need reference data that is not in the snapshot (`test_render.py:89` old reference copy, `test_t1_layouts_compare.py:219, 259` `.scratch/r1` and `lab_layouts`, `test_t2_annot_highlight.py:384` x9 reel copy or lab project, `test_t3_text_cards_footage.py:137`, `test_t4_diagrams_shorts.py:113`). None is in a file I touched; I could not run them.

## 6. Needs another worker

- `bti/draft/compile.py` `_merge_assets` (see section 3): the decision about what a re-draft does with a storyboard copy whose size
  disagrees with the file. After it changes, the sentence in `sbissues.js` can get its advice back and one test flips.
