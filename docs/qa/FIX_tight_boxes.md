# FIX tightbox: tight detail bounding boxes via full-resolution second look

Date: 2026-11-21
Worker: `tightbox` (worktree `.worktrees/tightbox`, branch `wt/tightbox`)

## 1. What was built

### Production modules
- `bti/picks/auto/tighten.py` (new): core second-look geometry, rendering, and validation engine:
  - `surface_box`, `region_to_rough_px`, `cutout_geom`, `cutout_to_stored`, `stored_to_cutout`, `stored_box_to_region`
  - `render_cutout` (crops from full-resolution source image, scales long side to `1024` px up or down, draws 100-px dual-tone grid with dark-backed yellow coordinate badges on top and left edges), `render_check_sheets` (clean cut-outs without grid, bright green + black outline box, tiles up to `6` per JPEG with name, stored pixel dimensions, `thing` / `what`, and cut-out `[x0,y0,x1,y1]`)
  - `check_cutout_box`, `check_regions_response`, `check_tighten` (enforces `tight` | `drop` | single-use `wider` `+40%`, refuses out-of-cutout / `< 8 px` stored side / full-cutout box when rough box `<= 45%` of painted surface, manages `look/tighten_state.json`, generates `look/check_*.jpg`, permits at most 1 box correction after check sheet, requires `confirmed: true`).
- `bti/picks/auto/shapes.py`: raised `MAX_REGIONS` from `20` to `30`; added `clean_thing` & `_allows_and_in_thing` (2–8 English words, refuses Vietnamese marks and `"X and Y"` unless colour/material modifiers, collective nouns, known single units, or narration phrase); extended `PlanCtx` (`line_texts`) & `check_plan`; extended `ChoiceCtx` (`cutouts`) & `check_choice` (routes cutout regions through `tighten.check_regions_response` while retaining legacy `keep`/`adjust`/`drop` path when `cutouts` is empty).
- `bti/picks/auto/inputs.py`: added `content_box` on `Painting` in `_main` (populated via `pcb.ensure` / `pcb.box_of`), preserved existing `tight`/`thing`/`rough`/`raw` on regions, passed `line_texts` in `PlanCtx`.
- `bti/picks/auto/workspace.py`: added `plan_regions_to_tighten` (all newly planned regions whose rough boxes overlap the painted surface, plus any referenced existing non-tight region on main painting) and `_copy_full_painting` (copies full-res painting into `inputs/main_full<ext>` before `build_choose`); updated `build_choose` to cut gridded 1,024-px full-res cut-outs; added `build_tighten` for standalone `picks.tighten`.
- `bti/picks/auto/helper.py`: added `"tighten"` mode (`out/tighten.json`) and `allow_unconfirmed` parameter on `run_check`.
- `bti/picks/auto/job.py`: raised `EST_SECONDS["choose"] = 600`, `PLAN_LIMITS = Limits(minutes=30, steps=140, repairs=1)`, `CHOOSE_LIMITS = Limits(minutes=45, steps=280, repairs=2)`; `regions_of(plan)` selects `plan_regions_to_tighten`; `run_choose` falls back once to `run_check(..., allow_unconfirmed=True)` if check failed only on unconfirmed boxes so valid picks are never lost; records `regions_tight`.
- `bti/picks/auto/write.py`: updated `final_regions` and `region_ops` to write confirmed tight boxes with `tight: True`, `thing`, `rough` (updating existing non-tight regions in place), store unconfirmed new planned regions with rough boxes and `tight: False`, and record `regions_tight` in `run_state` and result.
- `bti/picks/auto/texts.py`: added `TIGHTEN_PART_TITLES`, `VI["tighten_nothing_to_do"]`, and `tighten_sentence`.
- `bti/picks/auto/tighten_job.py` (new) & `bti/picks/auto/__init__.py`: standalone `picks.tighten` 2-part long job (`tighten`, `write`), `start`, `active_job`, `overview` (`kind="picks"`, `meta.action="tighten"`), exported as `tighten_job`.
- `bti/picks/doc.py`: added `THING_MAX = 120`, `_rough`, optional `tight`/`thing`/`rough` in `_region` and `doc_problem`, `_scale_rough_boxes` called inside `load()` after `_mediaassets.reconcile_sizes`, and `non_tight_regions`. Preserves exact legacy dict shape and revision hash when absent.
- `bti/picks/service.py`: updated `check_regions` to validate optional `tight`, `thing`, `rough` against stored image dimensions.
- `bti/ops/picks_ops.py`: added optional `tight`, `thing`, `rough` schema/example/bounds checks on `set_region`.
- `bti/output/sheets.py`: updated `regions_sheet` to draw crisp rectangles for `tight: True` regions, append `(khít)` in the legend, and count `(N khít)` in the header.
- `bti/editor/tighten_api.py` (new) & `bti/editor/app.py`: mounted `tighten_router` at line 960 (`POST /api/projects/{pid}/picks/tighten`, `GET /api/projects/{pid}/picks/tighten`).
- `bti/editor/state_api.py`: added `Spec("picks.tighten", ...)` (`cost=("model", "about 5 minutes")`, `long_job=True`, `role="picks"`), `Ctx.non_tight_regions`, `_load_picks`, `_load_agent_jobs` (`meta.action in ("auto", "tighten")`), `b_picks_tighten` (`advances=False`), and added `"picks.tighten"` to `RUN_MANUAL` and `BUILDERS`.
- `bti/editor/hints.py`, `bti/editor/static/js/labels.js`, `bti/editor/static/js/errmsg.js`: added `tighten_nothing_to_do` hint/message, `write_refused` sentence in `STAGE_CODES.picks`, and `PICKS_TIGHTEN_LABELS`.
- Documentation: regenerated `docs/OPS.md`, `docs/AGENT_API.md`, `skills/picks/SKILL.md`; updated `docs/APP_GUIDE.md`; updated `skills/picks_auto/PLAN.template.md` and `CHOOSE.template.md`; created `skills/picks_auto/TIGHTEN.template.md`.

### Tests
- `tests/picks/test_tighten.py` (new) & `tests/picks/test_tighten_real_mapping.py` (new).
- Updated `tests/picks/auto_helpers.py` (`PLAN`, `CHOICE`, `FakeAgent.fit`, `FakeAgent.run`), `tests/picks/test_auto_*.py`, `tests/picks/test_join_box_auto.py`, plus new tests in `tests/ops/test_picks_ops.py`, `tests/state/test_state.py`, and `tests/auto/test_run_joined.py`.

## 2. Where the second look runs and why
- **Inside `picks.auto`'s choosing session (`mode == "choose"`)** via shared engine `bti/picks/auto/tighten.py`. Keeping `picks.auto` at its two model sessions (`plan` + `choose`) preserves the existing CLI/job contract (including `tests/cli/test_cli_picks_agent.py` without modifying unowned CLI files), avoids a third cold-start session overhead, and lets the choosing session inspect candidates alongside full-res region cut-outs in one context.
- **`picks.tighten` (standalone `mode == "tighten"`)** runs the exact same `tighten.py` validation, 1,024-px gridded cut-outs, `wider` re-cuts, and 6-per-sheet check confirmation flow on pre-existing non-tight regions without touching beat picks.

## 3. Steps, minutes, and new limits
- Project baseline observed on `eligius` (61 lines, 20 boxes, 21 wants): `plan` took 36 steps / 210 s; `choose` took 51 steps / 120 s.
- With `MAX_WANTS = 60` and `MAX_REGIONS = 30`:
  - **Planning (`PLAN_LIMITS`)**: 30 regions (with fewer exploratory `crop` calls because boxes stay rough; only grid/spot-checks) -> `session.Limits(minutes=30, steps=140, repairs=1)` (up from `120` steps; `EST_SECONDS["plan"] = 600`).
  - **Choosing (`CHOOSE_LIMITS`)**: 60 wants + 30 gridded 1,024-px cut-outs (~30 steps) + up to ~6 `wider` re-cuts (~12 steps) + up to 5 6-per-sheet check sheets and final confirmation writes/reads (~8 steps) adds ~50 steps and ~4–5 minutes -> `session.Limits(minutes=45, steps=280, repairs=2)` (`repairs=2` covers the check-sheet confirmation round plus one optional box correction; `EST_SECONDS["choose"] = 600`, up from `40 min / 220 steps / 1 repair`).
  - **Standalone tighten (`TIGHTEN_LIMITS`)**: focused only on non-tight regions (no want sheets) -> `session.Limits(minutes=25, steps=120, repairs=2)`, `EST_SECONDS = {"tighten": 240, "write": 15}`.

## 4. Verbatim text added to the templates

### `skills/picks_auto/PLAN.template.md`
1. Header planning note:
```markdown
- You have at most **{{MAX_STEPS}} steps** (every command you run and every file you open is a step) and **{{MAX_MINUTES}} minutes**. A session that goes over is stopped, and then only a file that already passes the check is kept. Plan your steps: read the inputs (about 4 steps), look at the painting and its grid (2), check a few rough boxes with a crop if unsure of where a detail sits, write `out/plan.json` (1), run the check (1 or 2).
```
2. Example `regions`:
```json
   {"name": "MIRROR", "box": [0.43, 0.37, 0.59, 0.59], "what": "Tấm gương lồi ở phía sau", "thing": "convex mirror on back wall"},
   {"name": "SIGNATURE", "box": [0.39, 0.29, 0.63, 0.38], "what": "Dòng chữ ký phía trên gương", "thing": "Latin signature above mirror"}],
```
3. `regions` field specification:
```markdown
- `regions` lists the boxes you add to the main painting (at most 30); each is used by at least one line (an unused one is dropped). **One region is one thing**: a line that names two distinct objects gets two regions, not one shared box. Fields:
  - `name`: capital letters, digits and `_` (`HEAD`, `LEFT_HAND`, `CARVED_SAINT`). It must not use the name of a region the painting already has.
  - `box`: `[x0, y0, x1, y1]`, a ROUGH location box in fractions from 0 to 1 (0 = left or top edge) with some air round the thing (`x0 < x1`, `y0 < y1`, at least 0.02 on each side, not nearly the whole painting). The second session will cut it out at full resolution and measure its tight pixel edges.
  - `what`: a few Vietnamese words on what the box shows (shown to the owner).
  - `thing`: two to eight English words using the narration's own words for that ONE thing (`"carved woman standing on a dragon"`, `"only lit candle in brass chandelier"`). Large parts of the painting (a face, a figure, the bed) are valid things too. The check refuses `"X and Y"` in `thing` unless the narration itself names them as one unit (such as a pair of pattens, joined hands, or `"Virgin and Child"`).
```
4. Section 6:
```markdown
## 6. Boxes: rough location with air round the thing

Your `box` here is a **rough location box**, not the final tight crop. Put generous air round the thing so it is not clipped (`[x0, y0, x1, y1]` in fractions of the painting), especially for tiny details where the 1,568-px view cannot resolve clean edges. The choosing session will cut each rough box out of the **full-resolution stored painting** with a 100-px coordinate grid and measure the tight box touching the thing itself.

Use `{{CROP_CMD}} --grid -o look/grid.jpg` to read rough coordinates accurately; use `{{CROP_CMD}} --box x0,y0,x1,y1 -o look/NAME.jpg` only when a location is hard to spot on `images/main.jpg`. A box thinner than 0.02 of the painting cannot show anything; one over 0.90 is the whole painting. A `fallback` that is a `detail` needs a box too. Remember: **one region = one thing**, named in English in `thing`.
```

### `skills/picks_auto/CHOOSE.template.md`
1. Header planning note:
```markdown
- You have at most **{{MAX_STEPS}} steps** (every command you run and every file you open is a step) and **{{MAX_MINUTES}} minutes**. A session that goes over is stopped, and then only a file that already passes the check is kept. Plan your steps: read `inputs/wants.json` and `inputs/regions.json` (2), open one contact sheet per wanted picture (one step each), open each gridded cut-out `images/d_<NAME>.jpg` (one step each), write `out/choice.json` (1), run `{{CHECK_CMD}}` (produces any `wider` cut-outs or `look/check_*.jpg` sheets), open every check sheet and confirm (or correct once) in `out/choice.json`, then run `{{CHECK_CMD}}` until `0 error(s)`.
```
2. `inputs/regions.json` row in section 2:
```markdown
| `inputs/regions.json` | The regions used by the plan (new ones and any non-tight existing ones), each with `thing` (English), `what` (Vietnamese), the lines that use it, `cutout_size` `[w, h]`, and `cutout`: the file `images/d_<NAME>.jpg` — cut from the full-resolution painting (+15% margin, inside the painted surface), scaled to 1,024 px long side, with a 100-px coordinate grid in the cut-out's own pixels. |
```
3. Region measurement and check-sheet verification section in section 3:
```markdown
For each **region** in `inputs/regions.json` (the second look at full resolution):

Open its gridded cut-out (`images/d_<NAME>.jpg`), read `thing`, `what`, `cutout_size`, and the lines that use it. Measure in the **cut-out's own pixels** (using the 100-px yellow grid along the top and left edges — never convert to the main painting's coordinates, the program does that for you):

- `tight`: give `box: [x0, y0, x1, y1]` in cut-out pixels (`0 <= x0 < x1 <= w`, `0 <= y0 < y1 <= h`). **Its edges touch `thing` itself, with NO air around it** — do not include neighbouring objects or half the rough box when the thing is smaller. Do not set `confirmed` on your first pass (leave `confirmed` out or `false`).
- `wider`: ONLY if `thing` is partly cut off by the edge of the cut-out. Give a short Vietnamese `reason` and run `{{CHECK_CMD}}`; the program writes one wider cut-out enlarged +40% (`look/d_<NAME>_wider.jpg`). Open that wider cut-out and answer `tight` (or `drop`) in the wider cut-out's pixels. Only one `wider` request per region is allowed.
- `drop`: ONLY if `thing` is not actually inside the painting/cut-out at all (never drop just to keep a loose frame). Give a Vietnamese `reason`; lines using it fall back to the whole painting.

**Check sheet verification (mandatory before a region becomes tight):**

1. After you give `tight` (and no region waits on `wider`), run `{{CHECK_CMD}}`. The program draws every tight box as a bright green rectangle on a clean cut-out (no grid) and tiles up to 6 per sheet (`look/check_1.jpg`, `look/check_2.jpg`, ...), labelled with region name and stored pixel size.
2. **Open every `look/check_*.jpg` sheet.** Inspect each green rectangle against `thing`:
   - If the green box fits `thing` tightly with no air and clips nothing important, add `"confirmed": true` to that region in `out/choice.json`.
   - If the green box is slightly off, you may give a corrected `box` **once** together with `"confirmed": true` (or answer `drop`).
3. Run `{{CHECK_CMD}}` again until it prints `0 error(s)`. Any region never confirmed after inspecting a check sheet is NOT stored as tight.

Never answer a box you have not measured on its cut-out, and never confirm a box you have not visually checked on `look/check_*.jpg`.
```
4. Section 4 format (`regions`):
```markdown
  "regions": [
   {"name": "CARVED_SAINT", "action": "tight", "box": [298, 162, 398, 392], "confirmed": true,
    "reason": "Khung sát tượng thánh khắc trên thành ghế, bỏ phần bàn chải và ghế xung quanh."},
   {"name": "WRONG_DETAIL", "action": "drop",
    "reason": "Chi tiết này không có trong vùng tranh như lời dẫn nêu."}]}
```
```markdown
- `regions`: one entry for each region in `inputs/regions.json`. `action`: `"tight"` (with cut-out pixel `box` `[x0, y0, x1, y1]`, and `"confirmed": true` after checking `look/check_*.jpg`), `"wider"` (once, with Vietnamese `reason`), or `"drop"` (with Vietnamese `reason`).
```

### `skills/picks_auto/TIGHTEN.template.md`
Focused standalone second-look prompt (schema `bti.picks.tighten/1`, `out/tighten.json`), enforcing `tight` | `wider` | `drop`, no coordinate conversion by model, `thing` (2–8 English words) for existing regions lacking a clear `thing`, and mandatory `look/check_*.jpg` visual confirmation.

## 5. Stored fields and real stored example
On `picks.json -> assets.<key>.regions.<NAME>`:
- Existing fields updated to the tight box: `x`, `y`, `rx`, `ry` (stored painting pixel centre and half-extents computed by `tighten.stored_box_to_region`), `label` (Vietnamese).
- New optional fields:
  - `tight`: `true` (present ONLY when explicitly confirmed after check-sheet inspection; omitted when not tight).
  - `thing`: short English description (2–8 words from narration, up to 120 chars).
  - `rough`: `[x0, y0, x1, y1]` integer stored-painting pixels of the rough box before tightening (scaled by `doc._scale_rough_boxes` when stored image size is corrected).

Real example produced by running `tighten_job` on `arnolfini.jpg` (`3840 x 5253`) into `T01_carved_woman` (from `.scratch/tightbox/proof/mapping_check.json`):
```json
"T01_carved_woman": {
  "x": 2472,
  "y": 1042,
  "rx": 47,
  "ry": 108,
  "label": "Tượng thánh khắc thành ghế",
  "tight": true,
  "thing": "carved woman standing on a dragon",
  "rough": [
    2227,
    893,
    2765,
    1629
  ]
}
```
Regions without `tight` retain their exact original dictionary shape and SHA-1 revision hash through `doc.normalize` and `doc.save`.

## 6. Effect of `picks.tighten` on picks approval and existing storyboards
- **Picks approval**: `picks.tighten` writes via `ops_runner.run_batch` on `PicksAdapter` (`doc.save`), which recomputes `doc.revision(d)` without `approval`. Because moving `x, y, rx, ry` / adding `tight`, `thing`, `rough` changes the picks revision, **any prior picks approval is automatically dropped** (the owner approves again, matching every edit of picks).
- **Existing storyboard**: `picks.tighten` touches ONLY `picks.json` regions on the main painting (never beats and never `storyboard.json`). Any previously drafted/saved `storyboard.json` remains intact with its own shot camera coordinates (`x, y` / `box`) until the owner re-drafts or updates shots, following the existing rule for changed regions (with `doc.approval` dropped on `picks`, draft readiness / re-draft warnings reflect edited picks).

## 7. Decisions where `TASK.md` was silent
1. **Order / workflow enforcement for check sheets**: `check_regions_response` enforces a state machine in `look/tighten_state.json`. Premature `"confirmed": true` on pass 1 is refused (`[check_sheet_ready]`) while writing `look/check_*.jpg` so the model must inspect the clean sheet and re-run check; after inspection, at most one box correction (`[correction_limit]`) is permitted.
2. **Fail-safe when an agent exhausts step/repair budget before confirming**: `job.py:run_choose` and `tighten_job.py:run_tighten` fall back once to `helper.run_check(..., allow_unconfirmed=True)` instead of discarding valid picture choices; unconfirmed tight boxes are stored with rough coordinates (`picks.auto`) or left untouched (`picks.tighten`), never stamped `tight: true`.
3. **Dropping an existing region in `picks.tighten` that is referenced by a beat**: `remove_region` in `bti/ops/picks_ops.py` refuses removing a region still referenced by beats; rather than deleting beat picks (`picks.tighten` must never touch chosen pictures), `tighten_job` leaves in-use `drop` regions untouched (`dropped_in_use`) and removes only unreferenced `drop` regions.
4. **"X and Y" exceptions in `thing`**: `shapes._allows_and_in_thing` permits `"X and Y"` without false positives for colour/material adjective pairs (`"black and white"`), collective phrases (`"pair of ..."`, `"set of ..."`), known single units (`"Virgin and Child"`, `"cup and saucer"`), and singular noun phrases appearing verbatim inside the referencing beat's narration text.
5. **Ground-only rough boxes vs `content_box`**: `workspace.plan_regions_to_tighten` skips newly planned regions whose entire box falls outside `surface_box` (`pcb.clamp_region(...) is None`) so no degenerate `1x1` border cut-out is generated, and `write.region_ops` drops them as before so beats fall back to the whole painting.
6. **`surface_box` compatibility with `contentbox.box_of`**: `tighten.surface_box` accepts both `content_box` dicts and 4-sequence `(x0, y0, x1, y1)` tuples returned by `bti.media.contentbox.box_of`.

## 8. Needs another worker (unowned files)
1. `bti/draft/run.py:280` (`other_agent_job`): checks `(rec.get("meta") or {}).get("action") == "auto"` rather than `in ("auto", "tighten")`. As a result, while `picks.tighten` refuses to start whenever a draft/edit/auto/title job runs, `draft.start` / `draft.edit` / `picks.edit` do not treat a running `picks.tighten` job as holding the one agent slot.
2. `tests/e2e/picks_auto/launch_picks_auto.py`: its inline `make_plan` (`MIRROR`, `HEAD`) omits `thing`, and `make_choice` emits legacy `"action": "keep"` entries. Verified via `tests/picks/test_auto_e2e_launcher_plan.py` (asserts raw `make_plan` fails specifically on `thing_missing`).
3. `bti/picks/__init__.py:26`: `state()` checks `auto.active_job(pdir.name)` only (`meta.action == "auto"`), so while `picks.tighten` runs the stepper falls back to `"Đang tìm gợi ý hình."` instead of a tightening-specific label.

## 9. Mapping check on the six real reference boxes
From `.scratch/tightbox/proof/mapping_check.json` (verified against `/Users/nhanvu/Documents/code/behind-the-image/.scratch/agy_tasks/tightbox/data/vlm_boxes.json` and asserted in `tests/picks/test_tighten_real_mapping.py`):

| Region | Painting (`W x H`) | `content_box` | Rough px `[x0,y0,x1,y1]` | Crop px (+15%) | Scale / Cut-out | Cut-out box | Mapped stored px | Expected (`vlm_boxes.json`) | Max delta (px) | Tight size |
|---|---|---|---|---|---|---|---|---|---|---|
| `T01_carved_woman` | `arnolfini.jpg` (`3840x5253`) | `null` | `[2227, 893, 2765, 1629]` | `[2147, 783, 2845, 1739]` | `1.07113` / `748x1024` | `[298, 162, 398, 392]` | `[2425, 934, 2519, 1149]` | `[2425, 934, 2519, 1149]` | `0` | `94x215` |
| `T02_gargoyle` | `arnolfini.jpg` (`3840x5253`) | `null` | `[1728, 1891, 2496, 2627]` | `[1613, 1781, 2611, 2737]` | `1.026052` / `1024x981` | `[595, 172, 692, 328]` | `[2193, 1949, 2287, 2101]` | `[2193, 1949, 2287, 2101]` | `0` | `94x152` |
| `T04_lit_candle` | `arnolfini.jpg` (`3840x5253`) | `null` | `[1382, 0, 2534, 1050]` | `[1210, 0, 2706, 1207]` | `0.684492` / `1024x826` | `[262, 176, 304, 300]` | `[1593, 257, 1654, 438]` | `[1593, 257, 1654, 438]` | `0` | `61x181` |
| `T16_shark_teeth` | `eligius.jpg` (`3469x4000`) | `{100,106,3363,3900}` | `[2671, 1240, 3053, 1720]` | `[2614, 1168, 3110, 1792]` | `1.641026` / `814x1024` | `[338, 372, 458, 634]` | `[2820, 1395, 2893, 1554]` | `[2820, 1395, 2893, 1554]` | `0` | `73x159` |
| `T13_coins` | `eligius.jpg` (`3469x4000`) | `{100,106,3363,3900}` | `[2637, 3040, 3053, 3480]` | `[2575, 2974, 3115, 3546]` | `1.79021` / `967x1024` | `[258, 226, 784, 842]` | `[2719, 3100, 3013, 3444]` | `[2719, 3100, 3013, 3444]` | `0` | `294x344` |
| `T18_buckle` | `eligius.jpg` (`3469x4000`) | `{100,106,3363,3900}` | `[2428, 920, 2810, 1240]` | `[2371, 872, 2867, 1288]` | `2.064516` / `1024x859` | `[280, 158, 744, 762]` | `[2507, 949, 2731, 1241]` | `[2507, 949, 2731, 1241]` | `0` | `224x292` |

## 10. Test results (exact summary lines printed)

Windows snapshot tests (`export BTI_SSH_HOST=winbox-cmd && tools/deploy/snapshot_test.sh tightbox -- <folder>`, one folder per run, without `-m slow`):
- `tests/picks`: `429 passed, 1 warning in 137.32s (0:02:17)`
- `tests/ops`: `535 passed, 1 warning in 140.62s (0:02:20)`
- `tests/state`: `321 passed, 1 warning in 207.98s (0:03:27)`
- `tests/auto`: `237 passed, 1 warning in 102.83s (0:01:42)`
- `tests/output`: `78 passed, 1 warning in 25.08s`
- `tests/editor`: `530 passed, 1 warning in 252.49s (0:04:12)`
- `tests/cli`: `131 passed, 1 warning in 55.17s`

Windows generator checks (`export BTI_SSH_HOST=winbox-cmd && tools/deploy/snapshot_py.sh tightbox -m ...`):
- `bti.cli.docgen --check`: exit code `0` (`ALL_GENERATOR_CHECKS_OK=0`)
- `bti.ops.doc --check`: exit code `0` (`ALL_GENERATOR_CHECKS_OK=0`)
- `bti.editor.hints --check`: exit code `0` (`ALL_GENERATOR_CHECKS_OK=0`)

Mac JS checks and tests (`node --check bti/editor/static/js/labels.js bti/editor/static/js/errmsg.js && node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`):
```text
ℹ tests 495
ℹ suites 0
ℹ pass 494
ℹ fail 0
ℹ cancelled 0
ℹ skipped 1
ℹ todo 0
ℹ duration_ms 991.927292
```

## 11. Proof pictures and visual inspection
Generated into `.scratch/tightbox/proof/` via `.scratch/tightbox/make_proof.py` on full-resolution `arnolfini.jpg` (`3840x5253`) and `eligius.jpg` (`3469x4000`, `content_box {100, 106, 3363, 3900}`), and inspected directly:
- `T01_carved_woman_grid.jpg` (`748x1024`): dark oak bedpost/shadows beside white headdress; thin yellow/black lines and dark-backed yellow badges (`0..700` across top, `0..1000` down left) are crisp and legible over both dark oak and light linen; carving stands cleanly between `x=300..400` and `y=160..390`.
- `T02_gargoyle_grid.jpg` (`1024x981`): red cushion/drapery and joined hands; top/left badges (`0..1000` across top, `0..900` down left) read cleanly on dark wool sleeve and grey plaster; grotesque carving on armrest sits cleanly near `x=600..700`, `y=170..330`.
- `T04_lit_candle_grid.jpg` (`1024x826`): brass chandelier against dark beams/wall; top/left yellow-on-black labels (`0..1000` across top, `0..800` down left) remain clear even on dark beams and `800` badge does not obscure the Latin signature; lit candle stands cleanly at `x=262..304`, `y=176..300`.
- `T16_shark_teeth_grid.jpg` (`814x1024`): pale plaster ground beside red coral and gilt vessel; dark-backed grid numbers (`0..800`, `0..1000`) stay sharp against light plaster; the two mounted fossil teeth sit cleanly at `x=338..458`, `y=372..634`.
- `T13_coins_grid.jpg` (`967x1024`): warm wooden table and crimson bowl/drapery; top/left labels (`0..900`, `0..1000`) read cleanly; foreground stack + right pile + top background trio of coins span `x=258..784`, `y=226..842`.
- `T18_buckle_grid.jpg` (`1024x859`): ivory shelf, gilt handle, dark cloth, coral beads; top/left labels (`0..1000`, `0..800`) read clearly without masking details; jeweled buckle fills `x=280..744`, `y=158..762`.
- `check_all_6.jpg`, `arnolfini_check_1.jpg`, `eligius_check_1.jpg`: clean check sheets (no grid), dark header bars with `NAME  WxH px` and `thing  [x0,y0,x1,y1]`, bright green rectangle with black outer casing hugging each object cleanly (`T01` `94x215`, `T02` `94x152`, `T04` `61x181`, `T16` `73x159`, `T13` `294x344`, `T18` `224x292`; on `T13_coins`, the green box frames all three coin groups together as `[258,226,784,842]`, matching `vlm_boxes.json`).

## 12. What could not be verified
- No live VLM (`agy`, `claude`, `codex`) call was executed (prohibited by task limits); model behavior is verified with `FakeAgent` and static proof coordinates only.
- Storyboard camera calculation from `tight` regions belongs to the concurrent camera worker (unowned `bti/draft/**`, `bti/engine/**`, `style/**`) and was not modified or tested against live video rendering here.
- No live browser DOM interaction test was run against a running server process for `picks.tighten` UI triggers.
