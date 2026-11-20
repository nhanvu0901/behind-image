# FIX panelbox (2026-11-20): the camera never leaves the painted surface of the main painting

Worker `panelbox`, branch `wt/panelbox`. The first test video (`eligius`, the Met's photograph of the panel, 3469 x 4000 pixels, object 459052) let the camera of
about a dozen shots go past the edge of the painting: the picture has a black ground round the painted surface and a black band stood at one side of the frame. No
check noticed. This worker gives every picture its **painted area** (`content_box`), makes everything that frames the main painting use it, and adds the check
`frame_off_painting`.

## 1. How the box is found (`bti/media/contentbox.py`)

A box is `{"x0", "y0", "x1", "y1", "how", "note"?}` in pixels of the stored picture (the space of `width`, `height` and the regions: EXIF turn included). `how` is
`found`, `whole`, `unsure` or `set`. The finding is deterministic (no random number, no model, no network) and reads the picture once, at most 640 pixels on its long
side (a JPEG is decoded at 1/2, 1/4 or 1/8 by Pillow's `draft`), about 0.1 s for the 3469 x 4000 photograph. Remembered per (path, mtime, size).

In plain words, with the numbers (constants at the top of the module):

* A **line** (a row or a column, judged over what is left of the picture) is **ground** when it is uniform and either dark or light: the standard deviation of its
  grey values is at most **3.0** (2.0 for a middle grey) and its mean grey is at most **32** (dark: black cloth) or at least **225** (light: white ground). A middle grey is
  ground only when **three sides** have it. The real photograph's cloth is mean 1.5, standard deviation 0.5.
* Lines are taken away from each of the four edges inward while they stay ground: the mean may move at most 8 grey levels from the line before it and 30 from the outermost
  line of the band, a colour channel at most 24. Rounds repeat (at most four) because taking a band away changes what a row is judged over; in the later rounds a line must
  match the colour of the band that is already there, so that a flat part of a painting beside the band is never taken for more of it.
* The painting begins at the first line that is not ground, and the box starts **one scanned line further in** (the line where the cloth meets the panel is half cloth):
  no pixel of the cloth is inside the box, at most 6 pixels of the panel's own edge are outside it.
* A band under **1%** of its side is not a band (a scanner's dark hairline). No band at all: the box is the whole picture (`whole`), and nothing is written.
* The program is **not sure**, takes the whole picture and says so (`how: unsure`, `note` the reason) when: a band is on **one side only** (it could be a dark part of the
  painting itself), a band is thicker than **30%** of its side, the bands of different sides are not the same colour (40 grey levels), a middle-grey band is on fewer than three
  sides, or the box would be under **60%** of the picture.
* A picture of one colour, a damaged file, a file that is not a picture, a video: no finding (`whole`, or nothing).

Where it runs: **when a picture is imported or uploaded** (`bti/picks/service.py`: `_fetch_source`, `_fetch_book`, `upload`, so the routes, the typed operation `import` and the
automatic picks job all get it), **when the picks are saved** with a main painting that has none (`bti/picks/doc.py` `save`: `set_main`, `import ... as_main`, the page's
save, every batch), and **when it is first needed** without being written (the validator and the compiler read the file; a project made before the box existed gets it in the
storyboard on its next compile). The program writes a box only when it found something to take away (`found`) or was not sure (`unsure`): a document of a picture with no
ground band stays byte for byte what it was, and so does its revision. A person or an agent sets the box with the operation **`set_content_box`** (x0, y0, x1, y1 in pixels,
inside the picture, at least 5% of it on each side; `how: set`, and the program never replaces it) and clears it with **`clear_content_box`** (the program finds it again; the
undo of either gives back what was there). A box scales with its picture when the declared size was wrong (`reconcile_sizes`, with the regions). An unsure finding on the main
painting is the warning `content_box_unsure` of the picks (the automatic run lets it through: the whole picture is what it always was).

## 2. The real paintings (read-only copies of the server's files; I opened the pictures)

| picture | file | box found | what I saw |
|---|---|---|---|
| Petrus Christus, A Goldsmith in His Shop (project `eligius`, `goldsmith_his_shop_3bc1.jpg`) | 3469 x 4000 | **100, 106 to 3363, 3900** (`found`, about 100 px of black cloth taken from each side) | the green rectangle sits on the edge of the panel at all four sides: the painted surface with its own brown edge, none of the cloth |
| Van Eyck, Arnolfini Portrait (project `arnolfini-opus`, `van_eyck_arnolfini.jpg`) | 3840 x 5253 | **0, 0 to 3840, 5253** (`whole`, nothing to take away) | a full-bleed scan: the box is the picture |

## 3. What `frame_off_painting` is

A camera KEY of a shot whose main picture is the main painting (the project's `main_asset` of `picks.json` when the storyboard has it, else the picture on screen the
longest) shows **more than 1% of its frame outside the box**. Two kinds of frame are exempt, because there the black round the painting is the matte by design:

* a frame that **holds the whole painting** (the box inside the frame, 1% slack): the opening shot, a chapter mark, the pull back;
* along an axis where the frame is **a quarter wider than the painting or more and holds it** (a narrow painting in a wide frame, the look of a push in on the whole
  painting): bars at both sides are not counted, the other axis still is.

Only keys are judged: between two keys that are inside the box the camera is inside it too (the corners of the frame move on a concave and a convex curve), and a push in from
a whole view is by design partly outside. The issue is a warning with `args`: `shot`, `asset`, `key` (from 0), `share`, `limit`, `box`, `cx`, `cy`, `zoom`; the
validator (`storyboard.validate`) and the viewer checks run it with the file when the project folder is known and read the box from the asset when the storyboard has one. It is
in `STOPS["storyboard"]` of `bti/auto_run/checks.py`: **it stops the automatic run's storyboard gate**, with its sentence in English and Vietnamese. The page sentence is in
`errmsg.js` (block `PANELBOX_SENTENCES`).

## 4. Every place that now uses the box

| where | what |
|---|---|
| `bti/media/contentbox.py` (new) | the finder, the record, `box_of` / `ensure`, the geometry (`outside_share`, `fit_frame`, `whole_frame`, `clamp_region`) |
| `bti/media/assets.py` | `reconcile_sizes` scales the box with the picture |
| `bti/picks/doc.py` | `content_box` is kept by `normalize`, checked by `doc_problem`, found on `save` for the main painting, warned on `issues` when unsure |
| `bti/picks/service.py` | the box of a picture that is imported or uploaded |
| `bti/ops/picks_ops.py` | `set_content_box`, `clear_content_box` (+ `docs/OPS.md`, generated) |
| `bti/engine/viewchecks.py` | the check `frame_off_painting` |
| `bti/auto_run/checks.py` | `frame_off_painting` stops the storyboard gate; `content_box_unsure` is tolerated at the picks gate |
| `bti/draft/zones.py` | `whole_camera(..., box)`, `opening_shot`: the opening shot fits and centres the **box**, not the file |
| `bti/draft/compile.py` | a draft keeps the main painting's box in the storyboard's asset (the picks' box when they have one, else the finding; an edit leaves the asset exactly as it was); the defaults of the engine are made **for the painted area** (`box_local`: size, regions and keys moved by the corner of the box), the whole-painting end of `region_camera` is the box; a **final pass** (`fit_to_box`) moves or tightens every key of a shot on the main painting that shows more than 1% outside, after the identity, and says so (`frame_moved_into_painting`, a warning with the shot, the box, and each key before and after) |
| `bti/identity/apply.py` | `whole_keys` fits and centres the box; `in_box` fits the keys the beat and the marks get (a mark starts 4% wider than the shot it flows into) when the asset carries a box |
| `bti/picks/auto/write.py` | the regions of the pictures agent are cut to the box (point 3, below) |
| `bti/editor/static/js/errmsg.js`, `labels.js` | the Vietnamese sentences (blocks of my own at the end) |

The compiler's correction keeps the centre as near as it can and changes the zoom by no more than it must: the zoom is raised only as far as the frame needs to fit the box
along the judged axes (`1920 / box width`, `1080 / box height`, rounded up at the fifth decimal), then the centre goes to the nearest point from which the frame lies inside
(hundredths, towards the inside). A key that is right, or holds the whole painting, comes back unchanged (not even an int turns into a float). A **locked** shot, a shot the
compiler **keeps** (outside the scope of an edit) and, in an edit, every shot that is not one of the shots the person asked to change, are never touched: the validator still
flags a locked one, so its owner sees it.

### Regions of the main painting (point 3)

The boxes of the plan are **fractions of the picture the agent was shown**: the whole file, with the black ground round a museum photograph. `region_ops` turns them into
pixels as before and then **cuts the pixels to the box** (the region keeps its centre and radii as far as they stay inside the box and is made smaller where they do not, in
whole pixels, never past the box). A box of which **under half lies inside** the painted area was drawn on the ground: no region is made, and the lines that use it show the
whole painting (the same road as a box the agent dropped). A painting with no ground band gets exactly the regions it got.

## 5. Proof on the real documents (on the server, read-only, one run with the unchanged code of HEAD and one with the new code)

`validate()` of each stored storyboard, with the project's media folder, timing and picks:

| document | issues, unchanged code | issues, new code | everything but `frame_off_painting` identical | `frame_off_painting` |
|---|---|---|---|---|
| Eligius, the draft of 2026-11-19 (`projects\eligius\history\20261119T175212-c8385f01.json`; the first export's own storyboard in `output\` is the newer one, 138,037 bytes, the same as `storyboard.json`) | 53 | 109 | yes | **56 shots** |
| Eligius, the storyboard now stored (`projects\eligius\storyboard.json`) | 4 | 55 | yes | **51 shots** |
| Eligius, the finished video's storyboard of the repo fixture (`tests/engine/fixtures/catalogue/eligius/`, the first export) with the real photograph | `issues_before.json` | the same | yes | **59 shots** |
| Arnolfini (`projects\arnolfini-opus\storyboard.json`) | 1 | 1 | yes | **0: clean** |

The 59 shots of the first export, by how much of the frame was outside the box: 5 shots at 10% or more, 41 at 5 to 10%, 9 at 2 to 5%, 4 at 1 to 2%. The mirror close-ups the
owner named are the worst ones: **8:14 s0076 (7.7%) and 8:19 s0077 (10.3%)**, **8:53 s0082 (8.8%) and 9:01 s0083 (8.5%)**, **11:29 s0106 (10.3%)**; the five over 10% are s0077,
s0078, s0080, s0084, s0106 (the zoom 1.8 to 2.3 close-ups on the mirror at the right of the panel). The others are of two kinds: close-ups and pans that end 5 to 8% past the right
edge (the region cameras of the model), and the 21 framings at **the full width of the file** (zoom 0.5535 = 1920 / 3469) that show 100 pixels of cloth at each side (2.9% of the
frame on each side, 5.9% in all). The whole-painting views are not flagged (the pull back that ends the cold open, s0009, flags its first key, not its second).

Before and after, shot **s0077** (8:19 to 8:28, the close-up on the mirror, the frame at the end of the shot, `after` = the camera the compiler makes of it):
`.scratch/panelbox/out/still_s0077_before.jpg` shows a black band, 7% of the frame, at the right; `still_s0077_after.jpg` ends at the brown edge of the panel. The camera keys
went from centre 2930 / 2985 / 2985 / 2990 to 2829.7 / 2883 / 2883 / 2926.6, the zoom and the vertical centre unchanged.

Compiling the stored Eligius storyboard again (decompiled to specs, `compile_specs`): 45 shots get the warning `frame_moved_into_painting`, none keeps a `frame_off_painting`,
the box is kept in the storyboard's asset, and the 4 errors that the unchanged code also gives on that document (shots out of order, a duplicate id) are the same. The same
compile of the Arnolfini storyboard gives 3 chapter marks corrected (see decision 7).

## 6. Decisions where the brief was silent

1. **The record.** `content_box: {x0, y0, x1, y1, how, note?}`, integers. A box is written only for `found`, `unsure` and `set`; absent means the whole picture (and then the
   validator and the compiler read the file, which gives the whole picture again). The storyboard's asset gets the box in a **draft** compile (the picks' box when they have one, else
   the finding), never in an **edit** compile: `decompile.scope_violations` refuses an edit that changes an asset record, so an edit keeps the saved asset exactly and finds the box in
   the file when it needs it for a frame (tested on a storyboard made before the box existed).
2. **What "outside the box" means for a frame that is meant to show a narrow painting in a wide frame.** The literal reading (anything of the frame outside the box) flags every
   whole-painting view, among them five shots of the Arnolfini storyboard that the owner calls clean; it cannot be what the brief wants. The two exemptions of section 3 are mine; the first cut (any axis a quarter wider
   than the painting) flagged nothing past the edge when the frame was far off, so an axis is exempt only when the frame also **holds** the painting along it.
3. **Keys only**, not the interpolation (proved sufficient for keys inside the box); the main painting is the picks' `main_asset`.
4. **The compiler corrects a key by tightening, never by zooming out** (a frame that is almost the whole painting but not quite is tightened to fill the box, which is what the
   briefings ask: no painting small between bars).
5. **Defaults are made for the box.** The engine's default cameras (CAM-01/03/04/05, `fit_zoom`, the whole end of a region camera) are asked for the painted area and moved back, so
   the compiler's own frames are inside the box before the final pass; the final pass is for what the model wrote.
6. **A picture with no ground band has the whole picture as its box, and that still holds the camera**: a key that goes past the edge of the *file* is flagged and corrected too.
   This is a change for projects with no ground (the Arnolfini compile moves 3 chapter marks that start 4% wider than a full-width shot).
7. **The identity applier** fits the box only when the asset carries one (a storyboard compiled after this change with a box found does; an older one, or a picture with no ground, does
   not, and then the old numbers of the contract stay: `test_a_mark_flows_into_the_next_shot_on_resolved_numbers`). The compile's final pass fits whatever the identity wrote, with the
   box from the asset or from the file.
8. **The warning `content_box_unsure`** is for the main painting only and does not stop the run.
9. **`clear_content_box`** takes the record away; the next save of the main painting finds it again (a non-main picture is left with none).

## 7. What I could not verify

* The finder was tried on two real photographs only (a black cloth, and a full-bleed scan); the other cases (light ground, grey ground, one side only, letterbox, EXIF turn,
  thin bands, noise) are made-up pictures in `tests/media/test_contentbox.py`.
* No full render of an export: one still of one shot, before and after (a render of the changed shots is the owner's next step).
* The engine does not crop the picture to the box: in a whole-painting view (which the check allows) the black ground is still drawn round the painting, as a thin black ring on the
  engine's near-black matte. Cropping at render is `bti/engine/vfx.py`, not in this brief.
* The pages: the sentence of `content_box_unsure` is in `labels.js` but the simple picks page's switch in `views/picks_rows_logic.js` needs one `case` line (it falls back to the
  general warning sentence until then); nothing was clicked in a browser.
* `bti/editor/{identity,title,retime}_api.py` call `apply_identity` with no project folder: on a storyboard compiled before this change (no box in its asset) they write what
  they wrote before; the next compile gives the asset its box.

## 8. Needs another worker

* `bti/draft/workspace.py`: put the box into `inputs/assets.json` (the model works in file coordinates: `"content_box"` and a note that the camera stays inside it) and
  `skills/storyboard_draft/TASK.template.md`: add `frame_off_painting` and `frame_moved_into_painting` to the warnings the model is told to fix.
* `bti/editor/static/js/views/picks_rows_logic.js`: `case 'content_box_unsure': return W.issue.contentBoxUnsure;` (the label is in `labels.js`).

## 9. Tests

Python tests ran on the server only, in my snapshot `panelbox`, each folder on its own; the ssh session of a whole folder dropped ("Operation timed out") after two or three
minutes on several runs, so each folder was run **in chunks of two or three test files** (a chunk that dropped was run again whole), and the lines below are what pytest printed for
each chunk, in order. `-m "not slow"` for `tests/engine` and `tests/draft`. In `tests/state` the seven test ids `test_every_example_body_is_accepted_by_its_route[...picks.import_clip]`
hang on the server (the example body of the route that cuts a clip; a route I did not touch): they were deselected with `-k "not import_clip"` (`7 deselected` below); nothing else of
that folder is left out.

```
### tests/ops
[tests/ops/test_batch.py .. tests/ops/test_batch.py] 49 passed, 1 warning in 14.65s
[tests/ops/test_content_box_ops.py .. tests/ops/test_content_box_ops.py] 17 passed, 1 warning in 7.25s
[tests/ops/test_library.py .. tests/ops/test_library.py] 17 passed, 1 warning in 0.83s
[tests/ops/test_picks_ops.py .. tests/ops/test_picks_ops.py] 93 passed, 1 warning in 21.90s
[tests/ops/test_registry.py .. tests/ops/test_registry.py] 95 passed, 1 warning in 6.72s
[tests/ops/test_sb_ops.py .. tests/ops/test_sb_ops.py] 212 passed, 1 warning in 53.15s
[tests/ops/test_undo_log.py .. tests/ops/test_undo_log.py] 33 passed, 1 warning in 18.96s
### tests/media
[tests/media/test_api.py .. tests/media/test_clips.py] 28 passed in 0.47s
[tests/media/test_commons_rendition.py .. tests/media/test_contentbox.py] 130 passed in 4.92s
[tests/media/test_http.py .. tests/media/test_osm_place.py] 110 passed in 0.78s
[tests/media/test_osm.py .. tests/media/test_pixabay.py] 36 passed in 0.17s
[tests/media/test_privacy.py .. tests/media/test_safety_switch.py] 75 passed in 0.53s
[tests/media/test_stored_size.py .. tests/media/test_web.py] 51 passed in 0.71s
[tests/media/test_wikipedia.py .. tests/media/test_wikipedia.py] 10 passed in 0.14s
### tests/picks
[tests/picks/test_api.py .. tests/picks/test_auto_api.py] 29 passed, 1 warning in 16.66s
[tests/picks/test_auto_box.py .. tests/picks/test_auto_e2e_launcher_plan.py] 6 passed in 2.91s
[tests/picks/test_auto_job.py .. tests/picks/test_auto_kinds.py] 101 passed in 11.58s
[tests/picks/test_auto_runners.py .. tests/picks/test_auto_search.py] 52 passed in 19.97s
[tests/picks/test_auto_shapes.py .. tests/picks/test_auto_web.py] 44 passed in 4.65s
[tests/picks/test_auto_workspace.py .. tests/picks/test_box_picks.py] 35 passed, 1 warning in 15.97s
[tests/picks/test_content_box.py .. tests/picks/test_doc.py] 40 passed in 2.54s
[tests/picks/test_join_box_auto.py .. tests/picks/test_media_sources.py] 18 passed, 1 warning in 19.54s
[tests/picks/test_new_sources.py .. tests/picks/test_safety_switch.py] 10 passed, 1 warning in 1.59s
[tests/picks/test_size_repair.py .. tests/picks/test_suggest_state.py] 43 passed, 1 warning in 2.30s
### tests/identity
[tests/identity/test_apply.py .. tests/identity/test_validate.py] 94 passed in 1.74s
### tests/auto
[tests/auto/test_live.py .. tests/auto/test_loop.py] 114 passed, 1 warning in 3.55s
[tests/auto/test_reasons.py .. tests/auto/test_run_api.py] 48 passed, 1 warning in 41.25s
[tests/auto/test_run_command.py .. tests/auto/test_run_joined.py] 61 passed, 1 warning in 28.41s
[tests/auto/test_script_checks.py .. tests/auto/test_viewer_checks_bar.py] 9 passed, 1 warning in 0.18s
### tests/state
[tests/state/test_auto.py .. tests/state/test_docs.py] 55 passed, 1 warning in 21.05s
[tests/state/test_errors.py .. tests/state/test_ops_state.py] 38 passed, 1 warning in 8.45s
[tests/state/test_retime_state.py .. tests/state/test_state.py] 220 passed, 7 deselected, 1 warning in 145.19s (0:02:25)
### tests/cli
[tests/cli/test_cli_commands.py .. tests/cli/test_cli_docs.py] 74 passed, 1 warning in 29.75s
[tests/cli/test_cli_exitcodes.py .. tests/cli/test_cli_http.py] 46 passed, 1 warning in 10.74s
[tests/cli/test_cli_picks_agent.py .. tests/cli/test_retime_cli.py] 11 passed, 1 warning in 11.12s
### tests/editor
[tests/editor/test_agent_routes.py .. tests/editor/test_api.py] 81 passed, 1 warning in 8.33s
[tests/editor/test_backend_fixes.py .. tests/editor/test_box_routes.py] 159 passed, 1 warning in 124.42s (0:02:04)
[tests/editor/test_core_wiring.py .. tests/editor/test_identity_route.py] 32 passed, 1 warning in 5.13s
[tests/editor/test_integration_real.py .. tests/editor/test_library_api.py] 25 passed, 1 warning in 17.29s
[tests/editor/test_media_adapter_limit.py .. tests/editor/test_media_adapter_map.py] 16 passed, 1 warning in 1.51s
[tests/editor/test_pipeline_api.py .. tests/editor/test_pipeline_waiting.py] 29 passed, 1 warning in 2.49s
[tests/editor/test_proposals.py .. tests/editor/test_retime_route.py] 33 passed, 1 warning in 8.35s
[tests/editor/test_round2_fixes.py .. tests/editor/test_round3_approve_lock.py] 65 passed, 1 warning in 56.88s
[tests/editor/test_round3_scanners.py .. tests/editor/test_round3_shapes.py] 50 passed, 1 warning in 10.57s
[tests/editor/test_script_api.py .. tests/editor/test_settings_web_search.py] 36 passed, 1 warning in 7.75s
[tests/editor/test_shell_static.py .. tests/editor/test_shell_static.py] 3 passed, 1 warning in 0.91s
### tests/draft
[tests/draft/test_agent_choice.py .. tests/draft/test_agy.py] 42 passed, 1 warning in 23.81s
[tests/draft/test_api.py .. tests/draft/test_apply_undo.py] 11 passed, 1 warning in 3.42s
[tests/draft/test_auto.py .. tests/draft/test_box_briefing.py] 23 passed, 1 warning in 11.64s
[tests/draft/test_box_slow.py .. tests/draft/test_box_storyboard.py] 37 passed, 1 warning in 21.57s
[tests/draft/test_catalogue_compile.py .. tests/draft/test_claude_runner.py] 75 passed, 1 warning in 30.23s
[tests/draft/test_compile.py .. tests/draft/test_decompile.py] 30 passed in 7.52s
[tests/draft/test_describe.py .. tests/draft/test_e0_cards.py] 26 passed in 4.72s
[tests/draft/test_e9_e12_e13.py .. tests/draft/test_edit_routes_e2e.py] 12 passed, 1 warning in 7.82s
[tests/draft/test_edit.py .. tests/draft/test_explainers_briefing.py] 43 passed, 1 warning in 22.58s
[tests/draft/test_fastedit.py .. tests/draft/test_fixdraft.py] 65 passed, 1 warning in 14.34s
[tests/draft/test_helper_confinement.py .. tests/draft/test_identity_catalogue.py] 28 passed in 2.57s
[tests/draft/test_identity_compile.py .. tests/draft/test_intro_flow.py] 34 passed in 3.70s
[tests/draft/test_panelbox_compile.py .. tests/draft/test_run.py] 27 passed in 11.60s
[tests/draft/test_safety_switch.py .. tests/draft/test_size_follow.py] 21 passed in 2.84s
[tests/draft/test_spec_inputs.py .. tests/draft/test_workspace.py] 26 passed in 5.73s
### tests/engine
[tests/engine/test_asset_size_mismatch.py .. tests/engine/test_backend_fixes.py] 53 passed in 14.79s
[tests/engine/test_catalogue_real.py .. tests/engine/test_catalogue_registry.py] 27 passed in 3.78s
[tests/engine/test_d16_parallel_draw_check.py .. tests/engine/test_default_params.py] 17 passed in 74.38s (0:01:14)
[tests/engine/test_draw_check.py .. tests/engine/test_explain_base.py] 93 passed in 37.06s
[tests/engine/test_explain_over.py .. tests/engine/test_frame_off_real.py] 112 passed in 62.30s (0:01:02)
[tests/engine/test_guard.py .. tests/engine/test_helpers.py] 17 passed in 4.86s
[tests/engine/test_identity_brand_title.py .. tests/engine/test_identity.py] 81 passed in 69.88s (0:01:09)
[tests/engine/test_issue_codes.py .. tests/engine/test_map.py] 85 passed in 58.06s
[tests/engine/test_real_projects_draw.py .. tests/engine/test_registry_complete.py] 6 passed, 3 deselected in 4.45s
[tests/engine/test_render.py .. tests/engine/test_round3_engine.py] 50 passed, 1 skipped in 9.08s
[tests/engine/test_save_revision.py .. tests/engine/test_t1_layouts_compare.py] 21 passed, 2 skipped in 6.82s
[tests/engine/test_t2_annot_highlight.py .. tests/engine/test_t3_text_cards_footage.py] 43 passed, 10 skipped in 18.84s
[tests/engine/test_t4_diagrams_shorts.py .. tests/engine/test_timing_anchors.py] 16 passed, 1 skipped in 6.99s
[tests/engine/test_validate_draw_sweep.py .. tests/engine/test_validation.py] 19 passed, 163 deselected in 2.90s
[tests/engine/test_viewchecks_frame.py .. tests/engine/test_viewchecks_kinds.py] 56 passed in 1.71s
[tests/engine/test_viewchecks.py .. tests/engine/test_viewchecks.py] 37 passed in 1.20s
```

Two existing tests had to be told about the new things and were changed: `tests/auto/test_run_joined.py` (the picks tolerated list is now `asset_flag` and `content_box_unsure`) and
`tests/cli/test_cli_docs.py` (two words, `content_box` and `frame_moved_into_painting`, may be in code ticks), besides `tests/ops/test_registry.py` (the two new operations),
`tests/auto/test_viewer_checks_bar.py` (the new code is in the stopping list) and `tests/engine/test_catalogue_real.py` (the stored storyboard validates with the same issues apart
from `frame_off_painting`; with a flat stub for the picture the two chapter marks that go 3.8% past the file's edge are the only new rows). The fixture project of the operations tests gets
a painted area on its picture `D` so that the example of `clear_content_box` has something to clear.

New test files: `tests/media/test_contentbox.py` (35), `tests/engine/test_viewchecks_frame.py` (12), `tests/engine/test_frame_off_real.py` (4), `tests/draft/test_panelbox_compile.py` (16),
`tests/picks/test_content_box.py` (14), `tests/picks/test_auto_box.py` (4), `tests/ops/test_content_box_ops.py` (17), `tests/identity/test_panelbox_box.py` (6),
`tests/editor_frontend/panelbox.test.mjs` (4).

JavaScript, on the Mac (`node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`):

```
ℹ tests 495
ℹ pass 494
ℹ fail 0
ℹ skipped 1
```

The three generator checks, on the server: `python -m bti.cli.docgen --check`, `python -m bti.ops.doc --check` and `python -m bti.editor.hints --check` each exit 0 and print nothing.

## 10. The other pictures of the two projects (not opened by me except the two main ones)

`find` on the 50 pictures of the media folders of `eligius` (38) and `arnolfini-opus` (12): 44 `whole`, 4 `found` (the goldsmith, and three that I did not open: `37a306feb3e8846e4f184984.jpg`
0, 169, 719, 766; `default.jpg` 0, 25, 597, 683; `portret_van_dagobert.jpg` 38, 42, 1870, 2444), 2 `unsure` for one side only (`reliquary_journey_adorat.jpg`, `jacopo_della_quercia.jpg`).
