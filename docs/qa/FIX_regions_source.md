# A new full draft takes its regions from the pictures step, not from the storyboard saved before

Worker `regionsrc` (2026-11-21). Short report.

## What went wrong
A real run on a copy of `arnolfini-v3`: the pictures step (`picks.tighten` and a new plan) gave the main painting 35 regions, each one thing
with a tight box. `draft.start` then wrote a new full draft over the storyboard the project already had, and the storyboard that came out had
47 regions of which none had the box the pictures step measured (`CHAIR_SAINT` was still the old loose 538 x 736 box, so the box camera ended on
it at zoom 0.91; the model was shown only the loose boxes and measured tight regions of its own under new names). Cause: when a storyboard
exists, the saved copy of each asset replaced the picks' asset (`_Compiler._merge_assets` / `_saved_asset`), and only the facts of the file and,
for a draft, `content_box` came from the picks; the work folder (`workspace.build`) and the helpers did the same.

## The rule
One function for every place that needs "the assets this draft works from": `bti/draft/assetmerge.py`, `merged_assets(picks_assets, saved_assets, edit=...)`
and `saved_asset(saved, pick, edit=...)`.
- The facts of the stored file (`FILE_FACTS`) always come from the picks (as before).
- **A full draft** (`edit_shots is None`): `content_box` (as before) and every region the PICKS hold come from the picks, each region whole (its box and its
  fields `tight`, `thing`, `rough`, `label`), replacing the saved region of the same name. A region only the saved storyboard has (an earlier draft, or a
  person, added it) is kept. A saved region of a copy whose declared size was stale is scaled to the file's size first (the same as before), then the
  picks' regions are laid over it (they are already in the file's size). The picks' regions come first in the dictionary, the saved-only ones after them.
  The model's `out/regions.json` adds regions as before and still never overwrites a name that exists (`region_exists`, a warning).
- **An edit** (`edit_shots` is a set): the saved asset is kept as it is (shots outside the scope come back identical), apart from the facts of the file.

## Functions changed
- `bti/draft/assetmerge.py` (new): `FILE_FACTS`, `saved_asset`, `merged_assets`.
- `bti/draft/compile.py`: `_Compiler._merge_assets` calls `merged_assets`; `_saved_asset` is gone (its body moved to `assetmerge.saved_asset`, with the region
  rule added); `FILE_FACTS` stays on the class as an alias; the unused `scale_regions` import is removed.
- `bti/draft/workspace.py`: `build` writes `inputs/assets.json` from `merged_assets` (so the model is shown exactly the regions the compiler will use,
  with `tight`, `thing`, `rough` passed through); for a full draft `inputs/compile_input.json` carries the same regions in `current.assets` (the helpers merge
  `picks` and `current` again, and the saved-only regions must be the ones the model was shown); `workspace_compile` (what `./check` compiles) uses `merged_assets`.
- `bti/draft/defaults.py` (`./defaults`) and `bti/draft/still.py` (`./still`): the asset record and the regions come from `merged_assets` (they used to let the
  saved copy replace the picks' asset). `./crop` reads `inputs/assets.json`, so it follows the work folder.
- `bti/draft/run.py`: the two `read_out(...)` calls (the agy path of `run` and the deep edit path) validate `out/regions.json` against `merged_assets`
  (they used `{**picks, **saved}`, so a stale saved size could judge the model's coordinates).

## Every other place I checked
- `bti/draft/inputs.py` (`load_inputs`, `resolve_edit_scope`): no region logic; when there is no `picks.json` the picks ARE a copy of the saved assets, so nothing differs.
- `bti/draft/decompile.py` (`scope_violations`, the "asset record was changed" check): edit only; an edit still keeps the saved asset, so it still agrees.
  `decompile.shot_to_spec` writes the region names the saved shots use into `inputs/current/*.json`; those names exist in the merged assets (the same name from the picks,
  or kept because only the storyboard has them).
- `bti/draft/providers/auto.py` (the fake provider): reads the picks' assets already.
- `bti/draft/fastedit.py`, `picksedit.py`, `describe.py`, `merge.py`, `boxops.py` (the prompt-box turns and the deep edit): edits; they read the saved document on purpose.
- The fix-draft path (repair turns, `run.py`) compiles from the same `DraftInputs`, so it takes the merged assets from the compiler.
- Not changed, to be aware of: a draft of ONE chapter (`load_inputs(project, chapters)`) has `edit_shots is None`, so it follows the full-draft rule and the
  shots of the other chapters (copied through as they are) are drawn against the picks' regions at render.
- Locked shots (and the shots a one-chapter draft keeps): a locked shot is copied through as it is, so its camera numbers (written for the old box) stay. Its
  spotlight names the region and the engine reads the box from the assets of the storyboard at render, so it now lights the picks' tight box while the camera
  still frames the old one; the viewer check `camera_off_region` may say so. Left as it is (rare; the owner unlocks the shot to have both redone). A test pins it.

## Existing test that asserted the old precedence
`tests/draft/test_compile.py::test_assets_merge_storyboard_wins_and_regions_are_added` said "storyboard wins" (the saved MIRROR with `rx` 123 kept in a full
draft). It is now `test_assets_merge_picks_regions_win_in_a_full_draft_and_the_models_regions_are_added`: the picks' MIRROR (`rx` 80) wins, a region only the
storyboard has is kept, the model's region is still added without overwriting. No other test changed.

## Tests
New: `tests/draft/test_regions_source.py` (10 tests): the rule on assets (full draft, edit, copies, order); a full draft over a stored storyboard whose saved region
differs from the picks' of the same name compiles the camera from the PICKS' box and carries it in the written storyboard's assets; a region only the saved
storyboard has is kept; `tight`, `thing`, `rough` reach the written storyboard and `inputs/assets.json`; the spotlight is sized from the picks' box; a project with
no storyboard is as before; an edit keeps the saved region (and the shots outside the scope come back identical); the model's `out/regions.json` never overwrites a
name; the work folder of a draft and of an edit; `./defaults`, `./crop`, `./still` see the same regions; a locked shot keeps its numbers. With the old rule the four
compile-level tests fail (checked by putting the old rule back for one run).

Last run of each folder after the last code change (snapshot `regionsrc`, one folder per run, never `-m slow`):
| folder | last run, exactly as printed |
|---|---|
| `tests/draft` | `545 passed, 1 warning in 161.93s (0:02:41)` |
| `tests/editor` | `530 passed, 1 warning in 240.63s (0:04:00)` |
| `tests/state` | `321 passed, 1 warning in 222.06s (0:03:42)` |
| `tests/auto` | `242 passed, 1 warning in 93.30s (0:01:33)` |
| `tests/ops` | `536 passed, 1 warning in 130.03s (0:02:10)` |
| `tests/engine -m "not slow"` | `777 passed, 14 skipped, 166 deselected in 353.30s (0:05:53)` |

Node on the Mac (`node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`):
`tests 496`, `pass 495`, `fail 0`, `skipped 1`. Generator checks (`tools/deploy/snapshot_py.sh regionsrc -m ... --check`): `bti.cli.docgen` exit 0,
`bti.ops.doc` exit 0, `bti.editor.hints` exit 0.

## What I could not verify
- No real `draft.start` on the copy of `arnolfini-v3` (no model call, and the project is the coordinator's): the fix is tested on the synthetic project and by
  the same merge function in every place that read the saved regions.
- A page or an export of a storyboard drafted with the new rule was not looked at.
