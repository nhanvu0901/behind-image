# FIX comp_join: the join of `compbase` (TIME-01, TREE-01, STATE-01) and `compover` (KEY-01, NUM-01, DOC-01)

Worker `compjoin`, worktree `.worktrees/integ`, branch `integ`, merge of `wt/compover`. No git command that writes was run: the files are edited and not staged.
85 techniques now: 71 of the channel's look, the seven `ID-*`, `TIME-01`, `TREE-01`, `STATE-01`, `MAP-01`, `KEY-01`, `NUM-01`, `DOC-01` (in that order in the registry);
74 `done`, 11 `partial` (counted from `style/gae/techniques.json`). There are fourteen parameter types.

## 1. The seven conflicted files

| File | Resolution |
|---|---|
| `bti/engine/README.md` | One conflict (the sentence on `test_validate_draw_sweep.py`): "all 85 techniques and all fourteen param types" (the base side said fourteen, the overlay side thirteen). Both documentation parts are kept, in the order base techniques (`TIME-01`, `TREE-01`, `STATE-01`), the map, the overlays. |
| `docs/APP_GUIDE.md` | One conflict (the "Chưa có" bullet on the library): both sides' minimum lengths are kept (`MAP-01`, `TIME-01`, `TREE-01`, `STATE-01`, `NUM-01`, `DOC-01` not saveable below 3 s; `KEY-01` below 2.5 s), count 85, 74 `done`, 11 `partial`. The three-part order (base techniques, map, overlays) merged by itself and is right. |
| `tests/deep/test_sweep.py` | Two conflicts: docstring (the union of the ids that have no reference in technique_lab) and the count test (renamed `test_registry_has_85_techniques`, `== 85`, comment names every family). Both sides' reference shots are kept. A cross-check found a real collision, see 3.6. |
| `tests/engine/identity_lab.py` | One conflict, the docstring: 85 ids, "the seven ID-* ones, then TIME-01, TREE-01 and STATE-01, then MAP-01, which came later still, then the overlays KEY-01, NUM-01 and DOC-01". The functions of both sides (`append_explain_base_shots`, `append_map_shot`, `append_explain_shots`) merged by themselves and `add_to_project_dir` calls all four, in that order. |
| `tests/engine/test_issue_codes.py` | One conflict: both helpers kept (`_compbase_codes` and `_explain_codes`); the test that uses them merged by itself and uses both (`| _explain_codes()` on the line that builds `used`, `used |= _compbase_codes()` on the next). |
| `tests/engine/test_registry_complete.py` | One conflict: the technique-lab check excludes the prefixes `ID-`, `MAP-`, `TIME-`, `TREE-`, `STATE-`, `KEY-`, `NUM-`, `DOC-`; the count in the other test is 85. |
| `tests/engine/test_validate_draw_sweep.py` | One conflict, the docstring: 85 techniques, the reference ones named from both sides, fourteen types (including `at`). |

A line-by-line check against both parents confirmed that every line either side added is still in each of the seven files, except the lines changed on purpose (the counts, the wording of the unions, the id fix in 3.6).
No conflict marker is left anywhere in the repository (searched in every tracked and untracked file for `<<<<<<< `, `>>>>>>> ` and a line of `=======`).

## 2. Where the count changed (82 or 79 became 85; nothing unrelated was touched)

* `bti/engine/README.md` (the sentence in "Validate, draw and the registry").
* `docs/APP_GUIDE.md` ("Cả 85 kỹ thuật ...; 74 `done`, 11 `partial`": it said 71 and 11 for 82).
* `tests/deep/test_sweep.py` (docstring, test name, assertion), `tests/deep/sweep.py` (docstring, it still said 78).
* `tests/engine/identity_lab.py` (docstring), `tests/engine/test_validate_draw_sweep.py` (docstring).
* `tests/engine/test_registry_complete.py` (`len(b.techniques) == 85`), `tests/engine/test_default_params.py` (two places), `tests/engine/test_explain_over.py` (`len(ids) == 85`; both workers had written 82 and it merged silently).
* Left as they are on purpose: `docs/qa/FIX_comp_base.md`, `docs/qa/FIX_comp_over.md` (reports of the two workers, each true for its own checkout), `tests/editor/test_integration_real.py` (`>= 78`, a lower bound), the `82` of `docs/WINDOWS.md` and `docs/qa/ROUND*` (shots, not techniques), `bti/editor/static/mock/techniques.json` (an old mock with 71 entries).

## 3. What the two workers could not see of each other

1. **Words of the page.** `labels.js` and `sbissues.js` hold both blocks and `sbissues.js` has no code twice (a script that evaluates `labels.js` with a hook on `Object.assign` found exactly two words defined twice with two meanings): the row field **`side`** (TIME-01: above or below the axis, "Phía"; KEY-01: the side of the detail where the text goes, "Phía đặt chữ") and **`label`** (TIME-01 and the TREE-01 connector: the text, "Chữ ghi"; NUM-01: the small caption of a figure, "Nhãn nhỏ"). The later block silently replaced the earlier, so TIME-01's fields would have read "Nhãn nhỏ". Fixed: `labels.js` keeps the general words and has a table `ITEM_FIELD_OF` keyed by the name of the list param (`labels`: side, `rows`: label); `itemFieldLabel(name, list)` takes the list as an optional second argument and `formui.js` passes `d.name`. The hook now finds no word defined twice. A script on the Mac (the node test of the issue codes is skipped there because there is no `.venv/bin/python`) compared the 139 codes of `ISSUE_CODES` with the templates of `sbissues.js`: none missing, none extra, every sentence Vietnamese.
2. **Registry.** `style/gae/techniques.json`: valid JSON, 85 entries, ids unique, order `TIME-01`, `TREE-01`, `STATE-01`, `MAP-01`, `KEY-01`, `NUM-01`, `DOC-01` at the end, valid against `techniques.schema.json` (checked with `jsonschema` on the Mac; `test_default_params` checks it again on the server).
3. **Previews.** All six new techniques (and MAP-01) have a clip and a thumbnail on disk, tracked or staged, each above 7 KB.
4. **Catalogue the draft agent reads.** `techniques_md.EXPLAINER_FAMILIES` has all seven prefixes and prints a filled example for each of `MAP-01`, `TIME-01`, `TREE-01`, `STATE-01`, `KEY-01`, `NUM-01`, `DOC-01` (each example validates against the registry). `tests/draft/test_explainers_briefing.py` only covered the four of the base side: it now runs for all seven, asserts the default examples of `KEY-01`, `NUM-01`, `DOC-01` and that they appear in the intent index (`point_at`, `isolate`, `context`, `quantify`); its docstring no longer says "in the other checkout". Both briefing templates already name all seven.
5. **`focus_s` (TIME-01) and `reading_at` (DOC-01) are now of the parameter type `at`.** Small change for both, so both were switched: registry (`"type": "at"`, same default, min and max), renderers (`self.focus_s = R.at_seconds(p["focus_s"], self.t0, 6.0)` in `explain_base.py`, `self.reading_at = R.at_seconds(p["reading_at"], self.t0, 2.4)` in `explain_over.py`; seconds from the start of the shot or overlay, as before, or a word anchor), docstrings, README (the section "One moment" names the three users; `focus_s` is no longer "seconds only"), the guide (both sentences say "số giây, hoặc bấm *= đầu phát*"). The page needed no new words: the `at` widget, its sentences and the codes (`param_bad_at`, `stale_anchor`, `anchor_invalid`) are generic. New tests: `test_focus_s_is_a_param_of_type_at_...` (`tests/engine/test_explain_base.py`), `test_reading_at_is_a_param_of_type_at_...` (`tests/engine/test_explain_over.py`) (a word and its time in seconds draw the same frame, stale and gone anchors, bad values), and in `tests/editor_frontend/at_param.test.mjs`.
6. **Shot ids of the deep sweep collided.** In `tests/deep/test_sweep.py` the three base techniques' shots and the three overlays' host shots were both `s9300` to `s9302`. The overlay hosts are now `s9400` to `s9402`.
7. **Overlays on STATE-01.** The overlays were written before STATE-01 existed. `NeedsCamera.check_base` is generic (any base whose renderer provides `view()`), and STATE-01 does, so KEY-01 and DOC-01 may sit on it. New test `test_the_overlays_sit_on_a_two_state_base_and_follow_its_camera`: with a still camera the three overlays draw the same pixels as on a CAM-05 shot, and with a moving camera (STATE-01 bends the camera's clock) a label stays beside its detail where `view(t)` of the base puts it. (My first version of the test compared a moving camera with CAM-05 and failed: that was the test's mistake, not the engine's.)
8. **Layout table of the engine README** listed only `identity` and `maps` among the modules of `techniques/`: now also `explain_base` and `explain_over`.

## 4. Tests (snapshot `compjoin`, one folder per run; `-q`)

| Run | Result line, as printed |
|---|---|
| `tests/engine -m "not slow"` | `578 passed, 14 skipped, 164 deselected in 315.59s (0:05:15)` |
| `tests/deep -m "not timing"` | `231 passed, 4 skipped, 1 deselected, 1 warning in 269.55s (0:04:29)` |
| `tests/draft` | `358 passed, 1 warning in 139.48s (0:02:19)` |
| `tests/editor` | `481 passed, 1 warning in 214.99s (0:03:34)` |
| `tests/identity` | `77 passed in 1.30s` |
| `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs` (Mac) | `ℹ tests 342`, `ℹ pass 341`, `ℹ fail 0`, `ℹ skipped 1` |

Earlier runs of `tests/engine` on the way: `577 passed, 14 skipped, 164 deselected in 383.90s (0:06:23)` (before the test of item 7), then `1 failed, 577 passed, 14 skipped, 164 deselected in 316.16s (0:05:16)` (the first version of that test), then the last line of the table. The deep, draft, editor and identity runs were made before the last edit of `tests/engine/test_explain_over.py` (the only file that changed after them).

## 5. Not verified

* The slow-marked sweep `tests/engine/test_validate_draw_sweep.py` was not run (`-m slow` is refused). Its docstring and its fixture (`identity_lab.add_to_project_dir`) were changed or checked by reading only; the non-slow `tests/deep/test_sweep.py` draws all 85 techniques through the API and passed.
* The skipped node test (`sbissues.test.mjs`, needs `.venv/bin/python`) was replaced by the script of item 1 (139 codes), which is not part of the repository.
* Nothing was looked at on a rendered page in a browser; the page words are checked by node tests only. The guide and the README were read, not rendered.
* Nothing is staged: files with conflicts are still listed as unmerged in `git status` until the coordinator stages them.
