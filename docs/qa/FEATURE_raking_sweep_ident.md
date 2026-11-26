# Feature QA: `ID-BRAND-04` Raking Light Sweep Ident (Variant B Default)

## Summary

- **Engine technique (`ID-BRAND-04`, `BrandRakingSweep`)**: Implemented in `bti/engine/techniques/identity.py` and registered in `style/gae/techniques.json` (total catalogue: 87 techniques). Computes cached multi-scale luminance relief gradients across the canvas, illuminates with a grazing raking light, adds cut-letter contour bevels on the channel name (`RAKING LIGHT`), wipes/fades the video title (`eb_italic`, kerned), and slides up the museum label subtitle (`eb_regular`, uppercase tracked).
- **Variant B as the default `raking` ident**:
  - `style/gae/style.json` sets `identity.styles.raking.brand = "ID-BRAND-04"`, `brand_params = {"variant": "B"}`, and `earlier.brand = ["ID-BRAND-01", "ID-BRAND-03"]`, while keeping `nominal.brand.dur_s = 9.1` s so voice silences do not move.
  - `style/gae/techniques.json` sets `ID-BRAND-04` defaults `variant = "B"`, `nominal_s = 9.1`, `timing = {"default_s": 9.1, "min_s": 1.5, "max_s": 20.0}`, and keeps `A` and `C` selectable in `variant.values`.
  - Saved `dim` choices remain untouched; manual `"A"` or `"C"` overrides already set on an `ID-BRAND-04` shot are preserved across re-application.
- **How existing projects pick up the new ident**: A project adopts `ID-BRAND-04` Variant B automatically on a fresh `draft` compile, on `storyboard.retime`, or when re-applying style `"raking"` (e.g. `PUT /identity` or title update). Stored storyboards holding `ID-BRAND-01` or `ID-BRAND-03` under `"raking"` render cleanly with zero `identity_technique_mismatch` warnings.
- **Automatic rest-region selection (`bti.identity.choose_rest_region`)**:
  1. If `picks` give the cold open's final sentence (question) line a picture that is a region of `main_asset`, rest on that region (on read-only `arnolfini-v3`, selects `DOORWAY_FIGURES`);
  2. Else if a cold-open line is `about` a subject of kind `person` or `thing`, rest on the first such subject's `tight: true` region on `main_asset`;
  3. Else use `region: null` (spotlight rests cleanly on the centre of the painting).
  Wired through `bti/identity/apply.py` (with `camera` kept on `main_asset` / `whole_keys` when switching from non-main shots or when the region falls outside the previous crop) and `bti/draft/compile.py`.
- **Region clearance & bright-painting legibility**:
  - `BrandRakingSweep.__init__` computes the spotlight's vertical rest footprint (`rest_box_pct`) and keeps the channel name (dimmed), video title, and museum label all visible at rest across tall, wide, and square paintings, clear of the lit region and of each other (split above/below for upper-mid/centre regions, all three below top-edge spots, or all three above low spots).
  - `_two_tier_glyph_shadow` / `_build_raking_ink` add a two-tier dark glyph halo without any card, box, or strip, preserving legacy `GOLDEN` hashes on older `ID-*` techniques.

## Visual Inspection & Render Deliverables

- Rendered under `.scratch/agy_tasks/introsweep/out/`:
  - Prototypes: `intro_A.mp4` (8.0s), `intro_B.mp4` (8.5s), `intro_C.mp4` (8.0s) and `intro_{A,B,C}_{start,middle,rest}.png`
  - Pipeline demo from read-only `arnolfini-v3` metadata: `intro_B_pipeline.mp4` (`1920x1080`, `30/1` fps, `9.1` s, silent, auto-picked `DOORWAY_FIGURES`) + `intro_B_pipeline_{start,middle,rest}.png`
  - Registry preview: `style/gae/previews/ID-BRAND-04.mp4` (`640x360`, `30/1` fps, `9.1` s) + `style/gae/previews/ID-BRAND-04.jpg`
  - Synthetic layout/contrast rest frames: `check_tall.png` (`1000x2000`), `check_wide.png` (`2400x1000`), `check_square.png` (`1400x1400`, `region=None`), and `check_bright.png` (`240/255` cream canvas at `wake=0.86`) — all visually inspected via `read_file` with zero text-region overlap and readable serif typography.

## Verification

- **Server tests (`winbox-cmd`, `snapshot_test.sh introsweep`)**:
  - After final `fade_name_at_rest = False` layout fix (`bti/engine/techniques/identity.py` + `tests/engine/test_identity_raking_sweep.py`):
    - `tests/engine/test_identity_raking_sweep.py tests/engine/test_identity.py tests/engine/test_identity_brand_title.py -q`: `96 passed in 91.64s`
    - `tests/identity -q`: `106 passed in 4.44s`
  - Prior full-repo pass on default Variant B / auto rest-region / docs parity:
    - `tests/engine -m "not slow" -v --tb=short`: `840 passed, 14 skipped, 168 deselected in 423.52s`
    - `tests/cli -q`: `132 passed in 49.44s` (after regenerating `skills/storyboard/SKILL.md` with `bti.cli.docgen`)
    - `tests/draft -q`: `616 passed in 174.75s`
    - `tests/auto -q`: `263 passed in 96.34s`
    - `tests/output/test_shotwords.py -q`: `9 passed in 0.50s`
    - `tests/editor/test_retime_route.py -q`: `22 passed in 8.65s`
    - Doc/ops/hints checks (`snapshot_py.sh`): `bti.cli.docgen --check`, `bti.ops.doc --check`, `bti.editor.hints --check` all exited `0`.
- **Mac JS checks (`node`)**:
  - `UPDATE_GOLDEN=1 node --test tests/output/shotsentence_parity.test.mjs`: `146 cases, 87 techniques`, passed
  - `node --check bti/editor/static/js/labels.js bti/editor/static/js/camgeom.js` + `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/output/*.test.mjs`: `494 passed, 0 failed, 1 skipped`
