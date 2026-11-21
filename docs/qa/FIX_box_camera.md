# The program places the camera from the region; the storyboard model writes no camera numbers

Worker `boxcam` (2026-11-21). Three sessions wrote the code and were cut off by service errors and quotas; a fourth
session checked it, fixed what the last full test run showed, took the numbers on the stored Arnolfini documents and
wrote this report from the code as it stands. Every number below comes from a command run on the final tree (the
test lines are the last run of each folder).

## Why
The owner watched the Arnolfini video and wrote: "in 04:32 dont show the woman stand on dragon the camera fail to move
to that position fast enough". Shot `s0042` (4.51 s, `CAM-05`) had camera keys the storyboard model wrote by eye
(from (2300, 1900) zoom 1.0 to (2480, 1300) zoom 1.5, linear over the whole shot). The carved woman's tight box
(2425, 934 to 2519, 1149) is wholly inside the frame for **0.00 s** of the shot and at its end the frame still misses the
box by 6 px (the loose stored region `CHAIR_SAINT` by 47 px). The owner then decided: the PROGRAM places the camera from
the region; the model says which region and what kind of move, never numbers.

## What was built (files and main functions)
- `bti/engine/viewchecks.py` (the one frame rule and the two checks): constants `FRAME_FILL`, `SHARP_ZOOM`,
  `MATTE_HEADROOM`, `WHOLE_FIT_PCT`, `ARRIVE_MIN_S`, `ARRIVE_MIN_SHARE`; functions `region_box`, `region_point_box`,
  `sharp_limit`, `whole_painting_frame`, `fit_frame_to_box`, **`region_frame`** (the frame rule), `region_frame_info`
  (the shares of the frame, used by the draft's helpers), `box_inside_frame`, `_region_framing` (the checks
  `camera_off_region` and `thing_arrives_late`, called from `check`), `CODES` and `HINTS` entries.
- `bti/draft/camera.py` (new): **`build_main_camera`** (the keys for `CAM-01`, `CAM-03`, `CAM-04`, `CAM-05`,
  `STATIC-01` on the main painting), `naming_overlay_time` (the start of the spotlight or label that names the thing),
  `_arrive_time`, the two speed measures `_travel_speed_fw`, `_zoom_rate` and the constants (below).
- `bti/draft/compile.py`: `region_camera` uses the frame rule; `build_shot` keeps `slots.image.region`, reads the shot's
  `from`, refuses an unknown `from` region (`from_unknown_region`), marks a `params.camera` the model wrote on the main
  painting (`camera_not_allowed`, an error) unless it is the stored camera of an unchanged shot in an edit (carried
  over, as before); `build_doc` calls `build_main_camera` shot by shot and carries the end frame of the last shot on the
  picture as the `previous` frame (a card, a title, an identity shot or a cutaway to another picture breaks the chain);
  `summary_text` lists the two new warnings among the ones the owner rejects.
- `bti/draft/spec.py` (the `from` key and its shape check; a region's extra fields `tight`, `thing`, `rough` pass through
  unchanged), `decompile.py` (`from` and the slot's `region` survive a round trip), `workspace.py` (the regions reach
  `inputs/assets.json` with every field), `boxops.py` (`_clean_slots`: typed operations never carry a `region` in a slot).
- The model's helpers: `defaults.py` (`--from`, `--dur`; prints "compiler end frame"), `crop.py` (`--region NAME`; prints
  the compiler's frame for the box), `still.py` (prints the frame's centre, zoom and rectangle).
- `bti/draft/run.py`: `other_agent_job` counts a `picks` job whose `meta.action` is `tighten` as holding the project's one
  agent run, like `auto` (tested).
- Text: `skills/storyboard_draft/TASK.template.md`, `skills/storyboard_edit/FAST.template.md`,
  `skills/storyboard/SKILL.md`, `style/gae/techniques.json` (the `HI-01` sentence only), `bti/draft/techniques_md.py`,
  `docs/AGENT_API.md`, `docs/APP_GUIDE.md` (a Vietnamese paragraph), `bti/engine/README.md`.
- `bti/auto_run/checks.py`, `bti/editor/static/js/errmsg.js`, `bti/editor/static/js/labels.js` (a block of its own at the
  end of each, Vietnamese).

## The frame rule and its two numbers
`region_frame(region, w, h, box)`: centred on the region's centre; the zoom makes the region take `FRAME_FILL` = **0.62** of
the frame's width or height, whichever is reached first; never more than `SHARP_ZOOM` = **2.0** screen pixels for one pixel
of the stored picture (`SMALL_PICTURE_MAX_ZOOM` for a picture under 1000 px on its long side); never less than the
whole-painting fit; the frame stays inside the painted surface (`content_box`, through `contentbox.fit_frame`). One
function: the compiler, both checks and the helpers call it.

Why those numbers (the brief's starting values, kept after the stills below were looked at, and the base's spotlight rule
`SMALL_ON_SCREEN` = 0.40):
- 0.62 lets a large thing fill most of the frame and leaves a margin round it; in the stills the carved figure sits wholly
  inside the frame with room on every side.
- At zoom 1.5 the carved woman is sharp but small; at **2.0** the stored picture is a little soft and still clean; at 2.5
  it is visibly softer and blocky (stills `woman_zoom_1.5.jpg`, `woman_zoom_2.0.jpg`, `woman_zoom_2.5.jpg`).
- The two numbers fit the spotlight rule. On the real picture (3840 x 5253): the carved woman (94 x 215 px) is capped at
  zoom 2.0 and takes 9.8 % of the frame's width and 39.8 % of its height, so it stays under 40 % and the base's `HI-01`
  rule applies; the gargoyles (94 x 152 px) take 9.8 % and 28.1 %; the bench cushion (405 x 350 px) is bigger and
  takes 40.4 % of the width and 62.0 % of the height at zoom 1.91314, so it is NOT "small" and needs no spotlight.
- One more rule at the boundary (`MATTE_HEADROOM` = 1.04, found in this session): on a SMALL stored picture the tight fit
  of a region can exceed the sharp limit, so the frame is kept in the matte band (a frame at least 1.25 times as wide as
  the painting, which the validator does not judge). It used to sit exactly on the edge of the band (zoom 1.9199 on the
  800 x 1200 fixture); now it keeps 4 % of room, so the 3 % drift that the identity gives the channel-name beat after it
  stays in the band. See "What I found".

## What the model writes now
The model names the region the shot ENDS on (`slots.image.region`; no region = the whole painting; a framing that is not one
thing, such as the left half or both figures, is a region too) and may name where the move STARTS: `"from": "previous"`
(where the previous shot on the same picture ended: the default when there is one), `"from": "whole"` or
`"from": "<REGION>"`. It writes no `camera` on the main painting: a `params.camera` there is refused with
`camera_not_allowed`, whose message says to name a region and to add a tight region measured with `./crop` to
`out/regions.json` when the thing has none. Another picture and the explainers keep their defaults and their own rules.
A stored storyboard keeps its numbers (the page, the typed operations and `storyboard.retime` are untouched).

The new text of `skills/storyboard_draft/TASK.template.md`, in full (the lines that changed):

- Rule 14: "**Light each small detail.** Whenever a detail sentence names a thing small on screen, use HI-01 on the thing,
  including consecutive shots and near views. Start on the naming word and hold to the end of the shot, at least 2.5 s; a
  strip for an unfamiliar name accompanies the light, never stands alone. Use a tight region of the thing itself, measured
  with `./crop` and added to `out/regions.json` when needed. Leave the thing under about 40% of both frame dimensions:
  compiler zoom cap keeps tight small regions under 40%. Keep the centre 5% inside every edge throughout and `floor` /
  `surround_floor` at least 0.6. Use AN-01 only to distinguish one of several similar things so close a light would cover
  them all. Never light the opening shot or channel-name beat, the whole picture, a face, figure or something outside the
  painting; never use two spotlights at once or a ring on the same thing."
- The `slots` bullet: "`slots`: `{"asset": "A"}` from `assets.json`. On main painting, `"region": "MIRROR"` names where
  the shot ENDS (omitted = whole painting; multi-thing/half-painting framing is a region too). Omitting `image` takes the
  beat's first pick or main painting."
- A new `from` bullet: "`from` (main painting, optional): start frame — `"previous"` (default after a main-painting shot),
  `"whole"`, or `"<REGION>"`."
- The `params` bullet: "`params`: **never write `camera` on the main painting** (`camera_not_allowed` refuses it: name a
  region, or add a tight `./crop` region to `out/regions.json`). Other pictures/explainers keep defaults (`{}` unless
  overriding other params)."
- The check bullet lists `camera_off_region`, `thing_arrives_late` among the warnings the owner rejects.
- The defaults bullet: "**Defaults** of a technique: `{{DEFAULTS_CMD}} CAM-05 --asset A --region MIRROR` prints slots,
  params, and the compiler's computed camera/end frame (`./crop --box`/`--region` shows it too). Never copy `camera` into
  main-painting specs."
- Edit mode, step 2: "Write `out/<chapter>.json` as a copy of the current file: keep unchanged shots identical (`id`,
  `start_word`, `off`, `params`, `overlays`; `in_scope`/`locked`/`start_s`/`end_s` ignored). On main-painting shots you
  change, set `slots.image.region` (and optional `"from"`) and remove `camera` from `params` so the compiler builds it; never
  write new `params.camera` on main painting (unchanged shots keep saved `camera`; a ring around the mirror is `AN-01` with
  `"params": {"at": "MIRROR"}`). When a shot now shows something else, rewrite its `note` (or leave it empty): never keep the
  old reason. New shots omit `id`; leave out shots to remove."
- `techniques_md.py` (the generated `techniques.md`): "For shots on the main painting you NEVER write `params.camera` (name
  `slots.image.region` — omitted means the whole painting — and optional `"from"`, and the compiler builds the camera keys)."
- `skills/storyboard_edit/FAST.template.md`: "set the camera wider or use a tighter region when it fills too much of the frame
  ... If a tight region must be measured, answer `escalate` (deep mode uses named regions, never `params.camera`)."
- `style/gae/techniques.json`, `HI-01` "needs": "... Leave room to darken: the thing occupies less than about 40% of both
  frame width and height; the compiler caps camera zoom at the sharp limit so tight small regions stay under 40%
  automatically. ..." (it said: "end a closer camera a little wider").

## The move the compiler builds
Constants in `bti/draft/camera.py`: arrive at the latest `ARRIVE_BEFORE_WORD_S` = 0.3 s before the naming word, else by
`ARRIVE_DEFAULT_FRAC` = 45 % of the shot; hold at least 2.0 s or 55 % of the shot (whichever is shorter) with the thing wholly
inside; `HOLD_PUSH_PCT` = 4 % push after arrival; `MIN_TRAVEL_S` = 0.6 s; `MAX_TRAVEL_SPEED` = 0.35 frame-widths/s;
`ZOOM_RATE_MAX` = 1.0 octave/s; `SAME_REGION_PUSH_PCT` = 8 %; `PULL_START_PCT` = 18 %; `STATIC_DRIFT_PCT` = 3 %.
- **Three keys** where a move travels: start (from `from`), the arrival key at the time above (the end frame 4 % wider,
  so the hold is a push of 4 %), the end key (the frame rule's end frame). The middle key is anchored by `rel` of the shot
  (`{"at": {"rel": ...}}`): a shot the voice makes longer or shorter keeps its shape, and `storyboard.retime` and a tempo
  change need no new code (tested; the key list stays sorted and the engine validates it).
- `CAM-05` (zoom and shift): travel from `from` (default `previous`, else the whole painting) to the end frame, eased
  `inout_cubic`.
- `CAM-01` (slow push-in): with `from`, the same travel (`inout_sine`); without it, from the previous frame when that frame
  already holds the region and is not tighter than the end frame; otherwise it starts 8 % wider on the end region and pushes in.
- `CAM-03` (pull-back): from `from`, else the previous frame when it is tighter than the end frame by more than 4 %, else
  18 % tighter on the end region. To the whole painting it pulls back over the entire shot; to a region it arrives early
  (the arrival key is 2 % tighter than the end frame, so it ends with a 2 % pull-back).
- `CAM-04` (vertical glide): on the whole painting the frame's centre glides from 72 % to 28 % of the painting's height at the
  width fit (its length limited by the sideways speed); on a region a glide up along it (25 % of the region's height at most,
  30 % of the frame's height at most), arriving by the time above and then holding with the 4 % push.
- `STATIC-01`: no travel; a 3 % drift (it starts 3 % wider on the end region).
- **No race.** A move that would be too fast does not travel: the shot starts on a slightly wider frame of the SAME end
  region (8 %) and pushes in. "Too fast" is either of two measures over the time the move has to arrive (never below
  0.6 s): the sideways way over `MAX_TRAVEL_SPEED` frame-widths a second (the way is measured in the width of the frame at
  the geometric mean of the two zooms), or the zoom change over `ZOOM_RATE_MAX` octaves a second (`abs(log2(end zoom /
  start zoom))` divided by the seconds). `CAM-03` pulling back to the whole painting obeys the zoom rate by starting nearer.
  In either direction (zoom in and zoom out) the fallback is a start a little wider on the end region and a push in.
- Where the limits come from: the stored Arnolfini storyboard's 78 moving segments on the main painting run at 0.000 to
  **0.292** frame-widths/s sideways (median 0.023, p75 0.081, p90 0.124) and 0.000 to **0.555** octaves/s in zoom (median
  0.074, p75 0.124, p90 0.173); no stored move is above either limit. 0.35 frame-widths/s sits just above the fastest move
  of the video the owner watched; 1.0 octave/s was given by the coordinator (about twice the fastest stored zoom).

## The five real shots, old and new (s0040 to s0044; lines at 4:18 to 4:45)
Regions: the bench cushion `SETTLE_CUSHION` (1790, 2295 to 2195, 2645, measured with `./crop`: centre (1992.5, 2470), radii
202.5 and 175), the gargoyles `GARGOYLE` (2193, 1949 to 2287, 2101) and the carved woman `CARVED_WOMAN` (2425, 934 to 2519,
1149). Compile-level only (`build_main_camera` shot by shot with the previous end frame carried as the compiler does; no
model). `s0039` is a cutaway, so `s0040` starts from the whole painting.

| shot | old keys (seconds) | new keys (seconds) | why |
|---|---|---|---|
| `s0040` `CAM-05`, 258.58 to 264.45 s (5.87 s), the cushion; label `settle,` at 261.23 s | 258.58 s (1920, 2600) z 0.6 to 264.45 s (2050, 2350) z 1.1, linear | 258.58 s (1992, 2470) z 1.7714 `inout_sine` to 264.45 s (1992, 2470) z 1.9131 | **cut**: whole painting to the cushion in the 2.35 s it may take is 3.285 octaves = 1.398 oct/s, over 1.0 |
| `s0041` `CAM-01`, 264.45 to 269.87 s (5.42 s), the gargoyles; label `gargoyles,` at 264.98 s | 264.45 s (2150, 2150) z 1.4 to 269.87 s (2201, 2050) z 1.9, linear | 264.45 s (2240, 2025) z 1.8518 `inout_sine` to 269.87 s (2240, 2025) z 2.0 | no travel: the label comes 0.53 s into the shot, so the time to arrive (0.23 s) is under 0.6 s (not a speed limit) |
| `s0042` `CAM-05`, 269.87 to 274.38 s (4.51 s), the carved woman; no overlay | 269.87 s (2300, 1900) z 1.0 to 274.38 s (2480, 1300) z 1.5, linear | 269.87 s (2472, 1042) z 1.8518 `inout_sine` to 274.38 s (2472, 1042) z 2.0 | **cut**: from the gargoyle frame it is 1.053 frame-widths in 2.03 s = 0.519 frame-widths/s, over 0.35 |
| `s0043` `X-LAY-01`, 274.38 to 279.59 s | (960, 695) z 0.7304 to z 0.7742 | unchanged | another picture (the camera of other pictures keeps its default) |
| `s0044` `X-LAY-01`, 279.59 to 283.08 s | (1500, 2000) z 0.2538 to z 0.269 | unchanged | another picture |

The three shots that are on the main painting: **two of the three cut instead of travel because of the two limits** (`s0040`
by the zoom rate, `s0042` by the sideways speed), the third (`s0041`) does not travel because the naming word comes too soon.
None of the three travels. `s0042` with a spotlight on the word `carved` (word 708, 272.28 s) or with `"from": "whole"` gives
the same keys (the whole painting to the carved woman is 3.35 octaves in 2.03 s: 1.65 oct/s). The carved woman is wholly
inside the frame for **4.51 of 4.51 s** with the new keys (0.00 s with the old keys, which also miss the box by 6 px at the
end).

On the whole storyboard (88 shots on the main painting; 79 of them use an offered camera technique and are not the opening
or an identity shot: 35 `CAM-01`, 30 `CAM-05`, 7 `CAM-03`, 6 `CAM-04`, 1 `STATIC-01`), each rebuilt with the same rule (the
region: the slot's own, else the one region its overlays name, else the one region the detail picks of its line name, else
none = the whole painting; 48 shots have a region, 31 do not) and the default `from`:
- **27** travel in three keys (25 of them with a region);
- **5 cut because of the limits** (each was built four times with the same inputs: both limits on, only one, none):
  `s0042` and `s0082` by the sideways limit (0.519 and 0.564 frame-widths/s), `s0040` and `s0074` by the zoom rate (1.398 and
  1.195 oct/s), `s0080` by either (0.511 frame-widths/s and 2.214 oct/s); no `CAM-03` pull-back to the whole painting needed a
  nearer start;
- 47 never tried to travel: 28 have no region (the whole painting), 2 have a time to arrive under 0.6 s (`s0041` is one), 17
  are already on the region or are a native push (`CAM-04`, `STATIC-01`, `CAM-01` with no frame to start from).
- The two checks on the rebuilt storyboard: **0** `camera_off_region`, **0** `thing_arrives_late`, 0 `frame_off_painting`.
  The stored storyboard has 21 and 23 (next section).

## The two checks: every shot of the stored Arnolfini storyboard they flag
`camera_off_region` (a shot whose line points at a region, the slot's region or the line's one `detail` pick: at the end
of the shot the region's box is not wholly inside the frame, 1 source px of tolerance) and `thing_arrives_late` (the region
is wholly inside the frame for less than 2 s AND less than 55 % of the shot; sampled every 0.05 s). Both use the stored
(loose) regions. On the stored hand-written storyboard: **21** shots `camera_off_region`, **23** `thing_arrives_late`
(26 different shots, 18 in both). `s0042` is in both.

| shot | region | `camera_off_region`: end frame (centre, zoom), the box misses it by | `thing_arrives_late`: wholly inside for |
|---|---|---|---|
| s0009 | MAN_HEAD | not flagged | 0.45 of 6.45 s (7.0 %) |
| s0010 | MAN_HEAD | (1114, 990) zoom 1.35, 65.0 px | 1.39 of 7.41 s (18.8 %) |
| s0013 | WOMAN_HEAD | not flagged | 1.60 of 4.75 s (33.7 %) |
| s0014 | WOMAN_HEAD | (3034, 1287) zoom 1.4, 8.3 px | not flagged |
| s0022 | GREEN_SKIRT | (2773, 2300) zoom 0.9, 252.0 px | 0.00 of 7.63 s (0.0 %) |
| s0024 | GREEN_SKIRT | (3040, 2350) zoom 1.2, 352.0 px | 0.00 of 9.43 s (0.0 %) |
| s0026 | BLUE_HEM | (2496, 4050) zoom 1.45, 210.6 px | 0.00 of 4.69 s (0.0 %) |
| s0027 | WOMAN_HEAD | not flagged | 1.34 of 7.52 s (17.9 %) |
| s0028 | TABARD | (1371, 2300) zoom 0.7, 1235.6 px | 0.00 of 5.28 s (0.0 %) |
| s0029 | TABARD | (1150, 3400) zoom 0.85, 1503.7 px | 0.00 of 5.58 s (0.0 %) |
| s0030 | TABARD_FUR | (768, 3550) zoom 1.25, 229.0 px | 0.00 of 6.18 s (0.0 %) |
| s0038 | BED | (2700, 1900) zoom 0.85, 1562.7 px | 0.00 of 8.01 s (0.0 %) |
| s0041 | JOINED_HANDS | (2201, 2050) zoom 1.9, 292.8 px | 0.00 of 5.42 s (0.0 %) |
| s0042 | CHAIR_SAINT | (2480, 1300) zoom 1.5, 47.0 px | 0.00 of 4.51 s (0.0 %) |
| s0045 | RUG | (2074, 3550) zoom 1.0, 113.0 px | 0.00 of 4.80 s (0.0 %) |
| s0048 | BEADS | (1613, 1600) zoom 2.2, 93.5 px | 0.00 of 4.16 s (0.0 %) |
| s0049 | WINDOW | (960, 1350) zoom 1.0, 810.0 px | 0.00 of 5.54 s (0.0 %) |
| s0050 | WINDOW | (565, 1400) zoom 1.7, 1082.4 px | 0.00 of 4.02 s (0.0 %) |
| s0051 | ORANGES | not flagged | 0.05 of 5.47 s (0.9 %) |
| s0052 | ORANGES | (480, 2370) zoom 2.0, 406.0 px | 0.00 of 5.10 s (0.0 %) |
| s0053 | ORANGES | not flagged | 0.00 of 4.23 s (0.0 %) |
| s0065 | MIRROR | (1800, 1500) zoom 1.8, 118.0 px | 0.60 of 4.59 s (13.0 %) |
| s0080 | CHANDELIER | (1900, 850) zoom 0.8, 175.0 px | 0.00 of 6.57 s (0.0 %) |
| s0081 | JOINED_HANDS | (2050, 2245) zoom 1.6, 44.5 px | not flagged |
| s0082 | DOG | (1882, 4700) zoom 1.2, 103.0 px | 0.00 of 3.38 s (0.0 %) |
| s0096 | BEADS | (1613, 1576) zoom 2.0, 45.0 px | not flagged |

Do the warnings stop the automatic run? **Yes**, like `small_detail_not_lit`: both are in `STOPS["storyboard"]` of
`bti/auto_run/checks.py` (not in `TOLERATED`), with a sentence in English and in Vietnamese; `tests/auto/test_viewer_checks_bar.py`
holds them in its list of stopping codes. They also reach the draft's own check (`summary_text` lists them among the
warnings "the owner rejects") and the page (`errmsg.js` `BOXCAM_SENTENCES`, `labels.js` `BOXCAM_LABELS`, Vietnamese).

## What I found and fixed in this session
1. **The failing editor test**: `tests/editor/test_retime_route.py::test_a_storyboard_that_fits_the_voice_is_left_alone_and_no_revision_is_written`.
   A real defect of the new code. On the 800 x 1200 fixture picture the cap-bound branch of `fit_frame_to_box` put the
   `MIRROR` end frame (shot `s0002`) exactly on the edge of the matte band (zoom 1.9199: a frame 1.25 times as wide as the
   painting, the first zoom at which the validator does not judge the sides). The identity gives the channel-name beat after
   it a 3 % push of that frame (zoom 1.9775), which leaves the band; the compile's `fit_to_box` then tightened the beat to zoom
   2.4, while `storyboard.retime` runs the identity again (without that step) and wrote 1.9775: the retime "changed" shot
   `s0003` of a storyboard that fits the voice. Fix in the code: `MATTE_HEADROOM` = 1.04 in `fit_frame_to_box` (the frame keeps
   4 % of room inside the band; the Arnolfini frames are not affected: the branch runs only when a picture is so small that the
   tight fit would pass the sharp limit). A regression test (`test_small_picture_end_frame_keeps_room_for_the_beats_drift`)
   was added; the route test itself is unchanged and passes.
2. **The zoom-rate limit** (`ZOOM_RATE_MAX`) read critically: the travel fallback (`travel_to_end`: the rate is measured over the
   time to arrive, with the end frame, so it is slightly stricter than the keys, which end on the arrival key 4 % wider) and the
   `CAM-03` pull-back to the whole painting (`z_pull_max` = end zoom times 2 to the power of rate times shot length; the start
   is clamped to it, through `fit_frame_to_box` whose cap branch keeps it) do what the task says. One defect found: the power
   `2 ** (ZOOM_RATE_MAX * dur)` overflows for a shot longer than 1024 s (and for a limit of 1e9, which the analysis script
   used to switch the limit off): the exponent is now capped at 30 octaves (far past any zoom cap, so no result changes);
   test added. Test coverage: `test_zoom_rate_limit_both_directions` did not isolate the zoom rate in the zoom-out case (the
   sideways limit fired too, 0.45 frame-widths/s), so `test_zoom_rate_limit_alone_with_no_sideways_way_in_both_directions` was
   added (same centre, so only the zoom rate decides: zoom in and zoom out, `CAM-05`, `CAM-01` and `CAM-03` to a region; too
   fast gives two keys, the same move over 8 s gives three keys at or under 1.0 octave/s).
3. `bti/draft/run.py` (`other_agent_job` counts `tighten`): present and tested (`test_other_agent_job_covers_picks_auto_and_tighten`,
   three cases).
4. Existing tests that asserted the old behaviour the brief changes on purpose (updated by the earlier sessions; named here):
   `tests/draft/test_panelbox_compile.py` (four tests used a hand-written `params.camera` on the main painting in the model's
   spec: it is now refused, so they test the stored camera of an unchanged shot in an edit, and the default-camera test names
   `"from": "whole"`), `tests/draft/test_catalogue_compile.py::test_the_main_painting_is_never_refitted` (now asserts
   `camera_not_allowed`), `tests/draft/test_compile.py::test_defaults_are_filled_and_regions_aimed` (two or three keys),
   `tests/draft/test_fixdraft.py` (the dark spotlight's `floor` 0.2 became 0.1: the new camera frames the region differently, so
   0.2 no longer made a too dark frame), `tests/auto/test_viewer_checks_bar.py` and `tests/editor_frontend/sbissues.test.mjs`
   (the two new codes).

## Decisions where the brief was silent
- `from` with no previous shot on the picture is the whole painting; a cutaway, a card, a title or an identity shot breaks the
  chain of previous frames.
- With no region the shot ends on the whole painting (the end frame of the whole-painting fit with a small drift); a model that
  gives an `image` slot with the main painting and no region gets the whole painting. The beat's first image pick supplies a
  region only when the model writes no `image` slot at all.
- A `params.camera` on the main painting is an ERROR (`camera_not_allowed`), except the unchanged stored camera of an unchanged
  shot in an edit (the same region, no `from`): it is carried over so that an old storyboard keeps its numbers.
- The ease of a travelling move is `inout_cubic` (`CAM-05`, `CAM-03`) or `inout_sine` (`CAM-01`, `CAM-04`); the arrival and end
  keys are linear. The limits are measured on the AVERAGE speed; an `inout_cubic` move has a peak of up to 3 times the average
  (`inout_sine`: 1.57 times), so the peak zoom speed can reach 3 octaves/s at the limit: not checked by eye (see below).
- The checks take the region from the slot or, when the line has exactly one `detail` pick on the main painting, from that pick;
  the opening shot (`s0000`) and `structure` shots are not judged; a region with no radii is judged as a point.
- `region` stays out of typed operations (`bti/ops/sb_ops.py` forbids it in a slot): `boxops._clean_slots` strips it.

## Tests (last run of each folder, snapshot `boxcam`, after the last code change)
Python on the server (`tools/deploy/snapshot_test.sh boxcam`, one folder per run, never `-m slow`), every folder run after the
last code change (`bti/draft/camera.py`, the overflow guard). After that run one test was added in `tests/draft`
(`test_a_stored_storyboard_with_hand_written_camera_numbers_still_validates`) and one sentence in `bti/engine/README.md`
(no generator or test reads it); `tests/draft` was run again after both (the line below), the other folders were not.

| folder | last run, exactly as printed |
|---|---|
| `tests/draft` | `535 passed, 1 warning in 156.62s (0:02:36)` |
| `tests/engine -m "not slow"` | `777 passed, 14 skipped, 166 deselected in 351.33s (0:05:51)` |
| `tests/ops` | `530 passed, 1 warning in 126.01s (0:02:06)` |
| `tests/editor` | `530 passed, 1 warning in 240.65s (0:04:00)` (the coordinator's run before this session: 1 failed, 529 passed) |
| `tests/state` | `320 passed, 1 warning in 222.92s (0:03:42)` |
| `tests/auto` | `241 passed, 1 warning in 85.35s (0:01:25)` |
| `tests/output` | `78 passed, 1 warning in 20.56s` |
| `tests/cli` | `132 passed, 1 warning in 49.02s` |

Node on the Mac, `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs
tests/output/*.test.mjs`: `tests 496`, `pass 495`, `fail 0`, `skipped 1`; `node --check` of `errmsg.js` and `labels.js` is clean.

Generator checks (`tools/deploy/snapshot_py.sh boxcam -m ... --check`): `bti.cli.docgen` exit 0, `bti.ops.doc` exit 0,
`bti.editor.hints` exit 0.

New tests: `tests/draft/test_box_camera.py` (17 tests: the frame rule on a large region, a small one at the sharp limit, a region
at the edge of the painted surface and a small stored picture; the room a small picture's frame keeps for the beat's drift;
region fields passing through; `from` previous / whole / region / absent, with and without a previous shot, and the cutaway
reset; an unknown `from`; `params.camera` refused on the main painting and accepted on another picture; the five camera
techniques and early arrival with a spotlight's start word and without; the no-race case; the zoom-rate limit in both directions,
alone and with the sideways way, and a very long shot; three keys through `storyboard.retime` and a tempo change; the helpers;
`other_agent_job` and `tighten`) and `tests/engine/test_box_camera_checks.py` (both checks firing and not firing, the
threshold, the edge tolerance, no kinds). A stored storyboard with hand-written numbers on the main painting still validates without an error (a test of its own), and is also covered by the edit-mode tests in
`tests/draft/test_panelbox_compile.py` (the stored camera of an unchanged shot is carried over and still moved back into the
painting) and by the unchanged engine and `tests/state` runs.

## Pictures (`.scratch/boxcam/stills/`, rendered with `python -m bti.engine still` on a fixture project on the snapshot)
I opened every picture. The three `s0042_*_compare.jpg` show three panels each: OLD keys, NEW keys (the default: no
travel, the frame already on the carved woman, 1.8518 pushing to 2.0), and a third panel "NEW from='whole' 3-key".
- `s0042_start_compare.jpg` (0.01 s): old: the mirror, the joined hands and the lady's body, the carved figure is not on the
  screen; new: the frame is centred on the carved praying figure, wholly inside, a small figure in the middle of a brown wall
  with the chandelier at the top left and the lady's face at the right edge; third panel: the whole painting small between black
  bars (the start of a travel from the whole painting).
- `s0042_arrival_compare.jpg` (2.11 s): old: the mirror at the left, the lady's torso, the carved figure not on screen; new and
  third panel: the carved figure wholly inside, the same as at the start with a slight push.
- `s0042_end_compare.jpg` (4.49 s): old: the lady's face, the mirror's edge, and only the lower part of the carved figure at the
  top edge (its head is out of the frame, as the 6 px miss says); new and third panel: the carved figure wholly inside with the
  lady's eyes at the right edge.
- `woman_zoom_1.5.jpg`, `woman_zoom_2.0.jpg`, `woman_zoom_2.5.jpg`: the same end frame at the three sharp limits. 1.5: crisp but
  the figure is small; 2.0: a little soft, clean enough; 2.5: pixelated. This is the basis of `SHARP_ZOOM` 2.0.
- `woman_zoom_2.0_spotlight.jpg`: the end frame with the base's `HI-01` on the tight region: the figure is lit and the wall round
  it darkened; the figure takes 39.8 % of the height, so it stays under the 40 % of the spotlight rule.
- **One does not look right any more**: the third panel of the three compare pictures was rendered BEFORE the zoom-rate limit
  existed, and shows a three-key travel from the whole painting. With the final code the same call (`s0042`, 4.51 s,
  `"from": "whole"`) cuts to the same two keys as the middle panel (3.35 octaves in 2.03 s is 1.65 oct/s). The panel still shows
  what a travelling shot looks like at the three moments, but it is not what the compiler writes for this shot now. I did not
  render them again.

## What I could not verify
- No motion was looked at: the stills are single frames, no video was rendered, so the pace of a travel, the peak speed of the
  eases and how the cuts of `s0040` and `s0042` feel are unseen.
- No real draft: whether the storyboard model names regions and `from` well, and how often it meets `camera_not_allowed`.
- On the whole Arnolfini storyboard the regions of the shots other than `s0040` to `s0042` come from a rule (the slot's, the
  overlays', the line's detail pick), not from a model's choice, and the rebuild calls `build_main_camera` shot by shot the way
  `build_doc` does, not a full `compile_specs` (the three stored documents are not a project folder); the full compile path is
  tested on the synthetic fixtures.
- A tempo change after the compile moves a shot's start and length; the arrival key is anchored by `rel`, so its time scales with
  the shot and may then be less than 0.3 s before the naming word: compile again after a new voice (the draft run does).
- Tests ran on the server (Windows) and Node on the Mac; nothing on the Mac for Python.
