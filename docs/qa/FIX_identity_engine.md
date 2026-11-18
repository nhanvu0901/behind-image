# FIX: the seven identity techniques in the engine (worker idengine)

Date: 2026-11-18. Contract: `docs/design/2026-11-18-identity-raking-light.md` sections 2 to 4, the style block of section 5, the engine line of section 9.
Moving mock-ups: `docs/design/2026-11-18-d13-identity-mock.html`. Code: `bti/engine/techniques/identity.py`, `bti/engine/vfx.py` (fonts, `Band`).
Everything below was run on the Windows server in the private snapshot `idengine` (never the main folder, never the app on 8560).

## What each technique does

All times are nominal seconds from the start of the element (overlay, or shot for a base technique). A shorter element scales every time by
actual / nominal; a longer one keeps the nominal times. The four base techniques derive from `camera.MatteShot`: the picture is exactly CAM-01's
(same `camera` keys, slot `image`, `shadow`, same `view()`), then light and text. Text sizes are cap heights in % of the frame height (font size
from the real glyph H of EB Garamond: cap ratio about 0.654); a line wider than 88 % of the frame is made smaller, never wrapped.

| id | kind | what it draws | params (default; every number has min and max in the registry) |
|---|---|---|---|
| `ID-OPEN-01` | overlay | black 0.4 s, picture rises to `floor` by 1.2 s, band of light right to left 1.5 s to 7.5 s (ahead `floor`, inside 100 % plus warm tint, behind `wake`), whole picture rises to 100 % by 9.0 s. Only light; the shot's camera is untouched | `floor` .10, `wake` .45, `black_s` .4, `rise_s` .8, `sweep_start_s` 1.5, `sweep_s` 6.0, `direction` right_to_left, `band_width_pct` 14, `feather` .4, `angle_deg` 10, `release_s` 1.5, `warm` .14 |
| `ID-LABEL-01` | overlay | two lines bottom left, no strip: title italic (cap 3.0 %), "Artist, year" (cap 2.3 %), left margin 4 %, second baseline at 92 %, first baseline two cap heights of the second line above; fades 0.5 s in, 0.5 s out; soft shadow | `title`, `artist_year`, `x_pct` 4, `bottom_pct` 92, `title_cap_pct` 3.0, `second_cap_pct` 2.3, `fade_in_s` .5, `fade_out_s` .5, `shadow` true, `nominal_s` 4.5 |
| `ID-OPEN-02` | overlay | frame dims to `dim` in 1.0 s (smoothstep); title italic (cap 5 %) at 78 % fades in over 0.8 s ending when the dim ramp ends; 0.4 s after it starts, "ARTIST · YEAR" (capitals, tracking +14 %, cap 2.2 %) at 85.5 %; in the last 1.0 s text fades and light returns | `title`, `sub`, `dim` .45, `ramp_in_s` 1.0, `ramp_out_s` 1.0, `title_cap_pct` 5.0, `title_y_pct` 78, `sub_cap_pct` 2.2, `sub_y_pct` 85.5, `sub_tracking_pct` 14, `title_fade_in_s` .8, `sub_delay_s` .4, `sub_fade_in_s` .6, `sub_opacity` .9, `nominal_s` 5.0 |
| `ID-BRAND-01` | base | picture dims 100 % to `floor` in 0.6 s; band left to right 0.6 s to 3.0 s; RAKING LIGHT (capitals, medium, cap 8 %, tracking +25 %, centre of capitals at 42 %) revealed along the band's path and stays; behind the band `wake`; holds until the hard cut | `camera`, `shadow`, `text` "RAKING LIGHT", `dim_s` .6, `floor` .12, `wake` .26, `sweep_delay_s` .6, `sweep_s` 2.4, `direction` left_to_right, `band_width_pct` 16, `feather` .4, `angle_deg` 10, `warm` .14, `cap_pct` 8.0, `tracking_pct` 25, `y_pct` 42, `nominal_s` 5.0 |
| `ID-BRAND-02` | base | picture dims to `dim` in 0.8 s and stays; text fades in over 1.0 s from 0.4 s, holds, fades out over the last 0.6 s of the shot | `camera`, `shadow`, `text`, `dim` .25, `ramp_in_s` .8, `text_in_delay_s` .4, `fade_in_s` 1.0, `fade_out_s` .6, `cap_pct` 7.0, `tracking_pct` 25, `y_pct` 46, `nominal_s` 4.0 |
| `ID-MARK-01` | base | first picture of the chapter at `floor`; band left to right 0.1 s to 2.1 s writes "N. Title" (cap 4.5 %, centre 50 %), behind the band `wake`; from 2.5 s the picture rises to 100 % over 0.7 s and the text fades out over 0.4 s | `camera`, `shadow`, `title`, `floor` .12, `wake` .55, `sweep_delay_s` .1, `sweep_s` 2.0, `direction` left_to_right, `band_width_pct` 18, `feather` .4, `angle_deg` 10, `release_at_s` 2.5, `release_s` .7, `text_fade_out_s` .4, `cap_pct` 4.5, `y_pct` 50, `warm` .14 |
| `ID-MARK-02` | base | picture dims to `dim` in 0.6 s; text fades in 0.3 s to 0.7 s; from 2.4 s the text fades out over 0.4 s and the picture returns to 100 % over 0.6 s | `camera`, `shadow`, `title`, `dim` .40, `ramp_in_s` .6, `text_in_delay_s` .3, `text_fade_in_s` .4, `text_out_at_s` 2.4, `text_fade_out_s` .4, `release_s` .6, `cap_pct` 4.5, `y_pct` 50 |

**The band** (`vfx.Band`): a strip with straight edges tilted 10 degrees ("/"), a plateau of full light and smoothstep shoulders, moving at constant speed
along the axis perpendicular to its edges, from just off the canvas to just off the canvas with the mock-up's 13 % run-in (the mock-up's -22 % to 122 %).
`band_width_pct` is the width at half brightness; `feather` the share of it taken by one shoulder (0.4 here, the mock-up is about 0.5). Gain at a pixel with
signed distance `s` ahead of the centre line: `ahead + (wake - ahead) * smoothstep(-s / half)`, then brought to 1 by the strip's own profile; the warm tint is a screen
blend of amber (255, 205, 140) at `warm` inside the strip. The gain is a map at 1/4 resolution enlarged bilinearly (as `vfx.spotlight` does).
**Revealed by the band**: text opacity = `1 - smoothstep((s - core/2) / edge)`, the closed form of "the largest value the mask has had so far" for a band moving one
way at constant speed (checked against the running maximum in `test_revealed_means_the_largest_value_the_band_had_so_far`). A frame is a pure function of time.

**The dim style's entry transition** (TR-01, 0.75 s) is not in the technique: it is `transition_in` of the mark shot, written by the applier from
`style.json` `identity.styles.dim.mark_transition`.

## The `identity` block of `style/gae/style.json` (read by the applier, worker idapply)

`identity.channel_name` "RAKING LIGHT"; `identity.default_style` "raking"; `identity.styles.<raking|dim>` with `label_vi`, `open`, `label` (null for dim), `brand`, `mark`
(technique ids), `mark_transition` (`null`, or `{"technique": "TR-01", "dur": 0.75}`) and `nominal.<role>` = `{start_s, dur_s}` (`start_s` = seconds from the start of the
video for the opening overlays: 0.0 and 6.2 for raking, 7.0 for dim; `dur_s` = 9.0/4.5/5.0/3.2 and 5.0/4.0/3.0); `identity.min_element_s` 1.5.

## Fonts

EB Garamond static files from the official repository `https://github.com/octaviopardo/EBGaramond12` (the source Google Fonts builds from), commit
`e608414f52e532b68e2182f96b4ce9db35335593`, folder `fonts/ttf/`, in `style/gae/fonts/` with `OFL.txt` (same commit):

| file | source URL | sha256 |
|---|---|---|
| `EBGaramond-Regular.ttf` | https://raw.githubusercontent.com/octaviopardo/EBGaramond12/e608414f52e532b68e2182f96b4ce9db35335593/fonts/ttf/EBGaramond-Regular.ttf | `9a976a3e4b61a1eef1db06d4ee8a9f4c547a6550be50f199fdea661de33b350a` |
| `EBGaramond-Italic.ttf` | .../fonts/ttf/EBGaramond-Italic.ttf | `76fab0d73445f2e5c5b5c6cacdff47dc9f7cbad664efc10ed7f2c7ee832e5a29` |
| `EBGaramond-Medium.ttf` | .../fonts/ttf/EBGaramond-Medium.ttf | `697f8839ef1c2abfe5bb99d90fe732b96065cf3e73a7c8ef4b6eaf2842df51a2` |
| `OFL.txt` | .../OFL.txt | `6f9e3a1c51f617e7b110862426204ec7a56d8c6d2f731373b5de6b8d069099b6` |

(The google/fonts repository has no static files for this family, only the variable ones, so the upstream repository was used.) Cap height of the face: 650 per 1000 em in
OS/2, the glyph H reaches 654 (`vfx.cap_ratio` measures the glyph). The three kinds `eb_regular`, `eb_italic`, `eb_medium` in `vfx.font` load these files on every machine; a missing or damaged file raises
`vfx.BundledFontError` naming the file and the folder, never a fallback. The hashes are pinned in `tests/engine/test_identity.py`.

## Cost per frame (measured on the Windows server)

1920x1080 frame through `Project.frame_at(t, 1920)`, mean of 24 frames spread over the element, caches warm, fastest of 4 passes (the server is shared; single passes
vary by +-5 ms). "Extra" is against the same shot drawn by CAM-01 with no technique; `HI-01` (the existing spotlight overlay) is measured the same way for comparison.

| technique | ms per frame | same shot without it | extra |
|---|---|---|---|
| ID-OPEN-01 | 31.3 | 27.3 | +3.9 |
| ID-LABEL-01 | 27.3 | 26.7 | +0.6 |
| ID-OPEN-02 | 29.3 | 27.4 | +1.9 |
| ID-BRAND-01 | 33.2 | 27.6 | +5.6 |
| ID-BRAND-02 | 29.8 | 27.3 | +2.4 |
| ID-MARK-01 | 32.3 | 28.3 | +4.0 |
| ID-MARK-02 (after its 0.75 s dissolve, which renders two shots) | 27.6 | 27.6 | 0.0 |
| HI-01 spotlight (reference) | 47.7 | 30.9 | +16.8 |

So every identity technique costs less than the existing spotlight. (A first version with a full-frame broadcast multiply cost +19 to +22 ms; the gain is now applied
only to the columns where it varies, with `cv2` multiply, and the text reveal mask is computed at 1/4 resolution.)

## Tests

Run on the Windows server in the snapshot `idengine` (`BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_test.sh idengine -- <args>`), one run at a time, summary lines as printed:

| run | result |
|---|---|
| `tests/engine/test_identity.py -q` (the new file) | `50 passed in 38.75s` |
| `tests/engine -q` (everything, including the slow-marked sweep over all 78 techniques and every numeric bound; no `-m`) | `441 passed, 14 skipped in 1032.05s (0:17:12)` |
| `tests/engine -q -m "not slow" -rs` | `291 passed, 14 skipped, 150 deselected in 187.79s (0:03:07)`; the 14 skips are the old ones: reference copies (`.scratch/r1`, reel, `projects/lab_layouts`) are not in the snapshot |
| `tests/editor -q -x` (to see that the longer registry breaks nothing there; includes the files of `idapply` as they were at that moment) | `435 passed, 1 warning in 217.09s (0:03:37)` |
| `tests/draft -q` (same purpose) | `9 failed, 214 passed, 1 warning in 83.63s`: 7 in `test_compile.py` and 2 in `test_edit_routes_e2e.py`, all because the draft compiler of `idapply` now ends with the applier, so title and chapter cards come out as `ID-BRAND-01` / `ID-MARK-01` / `ID-LABEL-01` where the old tests expect `X-CARD-02` / `X-CARD-01`; none comes from my files (they draw fine) |
| `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs` (Mac) | first `tests 260, pass 258, fail 2` (the editor's camera table `camgeom.js` had no entry for the four new base techniques); after `idapply` added them: `tests 260, pass 260, fail 0` |

What the 50 tests of `tests/engine/test_identity.py` check (all frames are real frames of a project whose picture is flat grey, or black, and fills the canvas, so brightness is the light alone):

- registry: seven entries available, every number with `min`/`max`/unit and default inside, `timing.min_s` 1.5 and the nominal as `default_s`, slots and kinds, preview files on disk; the `identity` block of style.json (styles, roles, kinds, nominal start and length, the dim mark's TR-01 0.75 s, `min_element_s`).
- fonts: the three files and the licence are the pinned sha256 files; `vfx.font` returns EB Garamond from `style/gae/fonts`; cap ratio 0.64 to 0.66; a missing font dir raises a `FileNotFoundError` that names the file and the folder and caches nothing; the signature says "missing"; a damaged file names the file.
- band: geometry, constant speed, direction, width at half brightness equals `band_width_pct`, plateau equals `core`; "revealed" equals the running maximum of the mask over earlier times (401 steps, 15 probe pixels).
- `ID-OPEN-01`: black at 0.2 s; uniform `floor` level at 1.3 s; three zones at 4.5 s (ahead 12.8, behind 57.6, inside the tinted 100 %: measured against the screen-blend formula); level at 8.0 s; frames at 9.0, 9.5, 11.0 s are byte-identical to the plain picture and 8.999 s is within 1 level; band centre on the row y = 540 at 3.0, 4.5, 6.0 s equals the hand-worked 1720.3, 960.0, 199.7 px (+-5); the edge tilt over 880 rows equals -155 px (+-4); `left_to_right` swaps ahead and behind.
- text written by the band (`ID-MARK-01`, `ID-BRAND-01`, with a band narrower than the text): the same frames with and without text are compared; ahead of the band the difference is exactly zero; behind it the text equals its final self; ink pixel counts only grow; after the sweep the text stays and does not change; `ID-MARK-01` text fades out 2.5 to 2.9 s and the picture returns to the plain one (within 1 level at 3.199 s).
- levels: `ID-BRAND-01` (starts on the plain picture, 12 % at 0.6 s, 12 % ahead and 26 % behind at mid sweep, 26 % after); the three dim styles (45 % / 25 % / 40 %, smoothstep ramps, release at the end for `ID-OPEN-02` and `ID-MARK-02`, none for `ID-BRAND-02`); the text envelopes (`ID-MARK-02` 0.3 s delay, 0.4 s in, 0.4 s out; `ID-OPEN-02` title at 78 %, small line joins 0.4 s later at 85.5 %, ends clean).
- text: cap height is 3.0, 4.5, 7.0 % of the frame height (+-2.5 px), centre of capitals at `y_pct`, centred; capitals for lower-case brand input, wide tracking; a 95-character title is made smaller to 88 % of the width, one line; empty, blank, accented, Vietnamese, 120-character and CJK text draw; the label sits bottom left with a 4 % margin between 80 % and 94 % of the height and nothing is drawn elsewhere (no strip).
- time scaling: half-length overlay frames equal nominal frames at twice the time (byte-identical) for `ID-OPEN-01`, and for the four base techniques in a shot of half the nominal length; a longer overlay keeps the nominal times and is plain afterwards; label fades scale; the brand fade-out is anchored at the end of the shot for lengths 4.0, 6.0 and 2.0 s.
- picture: the four base techniques with neutral light and no text give frames byte-identical to CAM-01 with the same camera keys (moving camera, gradient picture on the matte) and the same `view()`; a ring (AN-01) can sit on a base identity technique.
- purity: frames drawn in a different order and after clearing the caches are byte-identical.
- params: every number at its registry `min` and at its `max`, and every enum value, one at a time, draws at three moments of the element (all seven techniques).
- defaults: `default_params` take the title, artist and year from the asset, the channel name from style.json, a 3 % push camera from the picture's size, and validate.
- the sample project `arnolfini` with one item per technique appended validates and draws.

Existing tests changed because of the seven new ids: `test_default_params.py` (71 -> 78, twice), `test_registry_complete.py` (78; the technique-lab check compares with the registry without the ID family, because the lab predates it), `test_validate_draw_sweep.py` (its copy of `technique_lab` gets one item per ID technique from the new helper `tests/engine/identity_lab.py`, so the validate/draw sweep and the numeric-bound sweep cover all 78). The sweep passes for all seven.

## Stills

`.scratch/idengine/stills/<technique>_<seconds>.jpg` (960 px wide, the sample project `arnolfini`, each technique on the shot at its nominal length; the temporary storyboard is
built by `.scratch/idengine/idlab.py` in the snapshot, no tracked project file is touched) and one contact sheet per technique `sheet_<technique>.jpg`. Times as asked: ID-OPEN-01 at 0.8, 3.0, 5.0,
7.0, 8.6 s (ID-LABEL-01 is on from 6.2 s: visible at 7.0 and 8.6); ID-OPEN-02 at 0.5, 1.5, 3.0, 4.8; ID-MARK-01 at 0.05, 0.6, 1.1, 1.8, 2.4, 3.1; ID-MARK-02 at 0.2, 0.8, 1.6, 2.6, 2.95;
ID-BRAND-01 at 0.3, 1.2, 2.0, 3.5; ID-BRAND-02 at 0.4, 1.2, 2.5, 3.8; plus ID-LABEL-01 alone at 0.25, 2.0, 4.25.

What I saw (looked at every sheet and at the full-size frames of the key moments):

- `ID-OPEN-01` (`sheet_ID-OPEN-01.jpg`): 0.8 s almost black (the rise to 10 % has hardly begun); 3.0 s a lit strip with soft edges and a "/" tilt has entered at the right edge, the picture ahead of it (to the left) is at about 10 %, behind it about 45 %; 5.0 s the strip is left of centre, a visibly brighter band with a slight warm cast, right of it the picture is evenly lit at 45 % (the woman, the mirror, the chandelier), left of it still nearly black; 7.0 s the band has left, the whole picture is at 45 % and the label is on; 8.6 s the picture is at about 90 % on its way to 100 %, label still on. The camera drifts slowly in all frames (the shot's own push), nothing else moves.
- `ID-LABEL-01` (inside the OPEN-01 stills at 7.0 and 8.6, and alone in `sheet_ID-LABEL-01.jpg` at 0.25, 2.0, 4.25 s): two lines bottom left, "The Arnolfini Portrait" in italic over "Jan van Eyck, 1434" in regular, readable over the dark coat with only a soft shadow; no strip or box. Half faded at 0.25 s and at 4.25 s.
- `ID-OPEN-02` (`sheet_ID-OPEN-02.jpg`): 0.5 s the frame is already dimming and the italic title is half in; 1.5 s and 3.0 s the picture is at 45 %, the title in italic at 78 % of the height, the "JAN VAN EYCK . 1434" line in tracked capitals under it, both clean; 4.8 s both lines fade (about 20 %) while the picture is almost back to full light.
- `ID-MARK-01` (`sheet_ID-MARK-01.jpg`, the mirror close-up): 0.05 s the first picture is dark (12 %); 0.6 s a band enters from the left, the part it has passed is at 55 %, the rest dark; 1.1 s "5. The Mirror" is written up to the band's trailing edge, the last letter ("r") is half-lit at the band's leading shoulder, the right part of the picture is still dark; 1.8 s and 2.4 s the band has gone, the whole line stands in the picture at 55 %; 3.1 s the line is gone and the picture is nearly at full light.
- `ID-MARK-02` (`sheet_ID-MARK-02.jpg`): 0.2 s the dissolve from the previous picture is visible (two pictures overlaid); 0.8 s and 1.6 s the new picture at 40 % with the line "5. The Mirror" in the middle; 2.6 s the line is fading while the light comes back; 2.95 s plain picture.
- `ID-BRAND-01` (`sheet_ID-BRAND-01.jpg`, the hands): 0.3 s the picture is dimming; 1.2 s the band is at the left edge and has written only the "R"; 2.0 s "RAKING LIG" is written and the band is at about 60 % of the width ("T" half-lit); 3.5 s the whole name stands in tracked capitals at 42 % of the height on a picture settled at 26 %.
- `ID-BRAND-02` (`sheet_ID-BRAND-02.jpg`): 0.4 s dimming, no text yet; 1.2 s the name is half in; 2.5 s the name at full strength on the 25 % picture; 3.8 s the name is fading out before the cut.

Compared with the mock-up's logic (light that travels, text that sits on the picture, nothing boxed) these match: the band and the writing behave as in `rakingOpen`, `rakingMark`, `rakingBrand`; the dim frames as in `dimOpen`, `dimMark`. Two things looked off at first and were fixed before this report: the band cost 19 to 22 ms (now 4 to 6), and in my first still set the shots were longer than the nominal length, which hid the fade-out of the brand beat (the stills are now taken on shots of exactly the nominal length).

## Deviations from the contract, and why

1. **Enum values `right_to_left` / `left_to_right`** instead of `rtl` / `ltr`. The contract allows adapting names; the editor's `labels.js` already has Vietnamese labels for these two words and a JS test requires a label for every enum value of the registry, so no shared label file had to change.
2. **`band_width_pct` is the width at half brightness** and `feather` (0.4) the part of it that one shoulder takes. The contract does not define the width of a soft strip; the mock-up's strip (gradient 6 % shoulders + 6 % plateau, about 13 % of the canvas width at half brightness) is what 14 % reproduces.
3. **Mark release.** The mock-up (`rakingMark`) keeps the picture behind the band at `max(0.55, b)`, so it only starts to brighten at about 2.85 s. The contract says "from 2.5 s the picture rises to 100 % in 0.7 s". I followed the contract: both the ahead and the wake level rise by a smoothstep over `release_s` from `release_at_s`. Same rule for `ID-OPEN-01` (release starts at the end of the sweep).
4. **Params added** beyond the contract's table, all with min, max and default: `shadow` on the four base techniques (CAM-01 has it and `MatteShot` reads it); `direction`, `feather`, `angle_deg`, `warm` on `ID-BRAND-01` (the table lists them only for the two other band techniques); `nominal_s` on `ID-LABEL-01`, `ID-OPEN-02`, `ID-BRAND-01`, `ID-BRAND-02` (the length at which their times hold; `ID-OPEN-01` and `ID-MARK-*` derive it from their own times); `text_in_delay_s` on `ID-BRAND-02` (the contract gives the fade length, not its start; 0.4 s, half the dim ramp, as the mark's 0.3 s); `sub_fade_in_s` (0.6) and `sub_opacity` (0.9) on `ID-OPEN-02` (the mock-up's values). In `ID-OPEN-02` the title starts at `ramp_in_s - title_fade_in_s` (0.2 s) so that its fade ends when the dim ramp ends, as in the mock-up.
5. **Text fitting and limits** that the contract does not mention: a line wider than 88 % of the frame is made smaller (never wrapped); string params are limited to 120 characters by a `pattern` with a Vietnamese hint (so the registry rule "whatever validate accepts can be drawn" holds); the channel name and the small-capitals line are upper-cased by the renderer.
6. **`style/gae/techniques.schema.json`** (not in my file list) got one change: the id pattern accepts `ID-OPEN-01` (three parts). Without it `test_registry_file_is_valid_and_consistent` fails.
7. **Registry categories and intents** (the contract is silent): `ID-OPEN-01` highlight, `ID-OPEN-02` and `ID-LABEL-01` text, `ID-BRAND-*` and `ID-MARK-*` card (so the gallery needs no new category); intents establish (openings), context (label), structure (beat and marks, which is what the applier looks for). `preview.reel_end` is the clip length.
8. **Previews** are 640x360 at 30 fps like the existing ones, made by `Project.render_range` (the tool of the README) and as long as the nominal timeline (9.0, 4.5, 5.0, 5.0, 4.0, 3.2, 3.0 s), not 6 s: a shorter clip would cut the sweep. Thumbnails are 640x360 jpg at the most telling moment. 14 new files, about 490 KB of mp4 in all.
9. **The warm tint** is part of the band pass; when the picture is at full light everywhere (`floor` = `wake` = 1) nothing is applied, tint included.
10. **Not done: "shorter than 1.5 s is a validation error".** Validation lives in `bti/engine/storyboard.py`, which `idapply` edits and I may not. The registry carries the number (`timing.min_s` 1.5 on all seven, and `identity.min_element_s` 1.5 in style.json) and the renderers scale any length above zero without failing, so nothing breaks below 1.5 s; see "Needs another worker".

## Needs another worker

- **Validation of the 1.5 s minimum** (`bti/engine/storyboard.py`, file of `idapply`): in `_validate`, for a shot whose technique starts with `ID-` and for an overlay of that family, `error` code `element_too_short` (args `min`, `got`) when `(t1 - t0) < spec["timing"]["min_s"] - EPS`; the number is in the registry, nothing else is needed. The code must be added to `ISSUE_CODES`.
- **The technique catalogue for the draft agent** (`bti/draft/techniques_md.py` writes `inputs/techniques.md` from the registry) now lists the seven ID techniques; the briefing (`idapply`) should say that the agent never picks them by hand (contract section 7).
- **`tests/deep/test_sweep.py`** asserts `len(reg) == 71` (and the lab sweep of that folder has no item for the ID family); `tests/e2e/storyboard/techniques71.mjs` and `docs/APP_GUIDE.md` ("Cả 71 kỹ thuật") say 71; `bti/editor/static/mock/techniques.json` is an old copy of the registry. None is in `tests/engine`; I did not touch them.
- `tests/draft/test_compile.py` (7) and `test_edit_routes_e2e.py` (2) fail against the draft compiler as `idapply` has changed it (cards are now `ID-*`); theirs to update.
- Seen resolved by `idapply` while I worked: the camera table entries for the four base techniques in `bti/editor/static/js/camgeom.js`.

## What I could not verify

- **Motion.** I looked at stills and contact sheets only; I cannot play video. The preview clips were made and probed (`ffprobe`: h264, 640x360, yuv420p, 30 fps, exact nominal length), not watched. Band speed, smoothness of the ramps and the feel of the fades are verified by numbers (tests), not by eye in motion. The mock-up's own picture and sound files are not in the repository, so no side-by-side with it.
- **A real video.** No full-length or final-quality (1920 px, 30 fps) render, no audio, no narration silence: only frames through `Project.frame_at` and 640 px previews. Behaviour inside a real storyboard (shots and silences of the real lengths, the applier's cameras) is `idapply`'s and the owner's look in the contract's last acceptance line.
- **The Mac.** Nothing was run there (rule). The fonts load by a path relative to the style root, so they should behave the same; untested. Text layout (kerning through libraqm or not) depends on the Pillow build of each machine, so letter positions could differ by a pixel between machines; frame logic does not.
- **Cost numbers** come from a shared server and are the fastest of four passes; a single pass varies by +-5 ms.
- **Vietnamese letters**: the font has them (checked in its cmap) and the tests draw them without errors, but I did not look at them.
- The `tests/draft` failures were not analysed beyond reading their messages.

## Files changed

Changed or new (nothing was `git add`ed):
- `bti/engine/techniques/identity.py` (new: the seven renderers)
- `bti/engine/vfx.py` (bundled font kinds, `cap_ratio`, `Band`, `smoothstep`, `gain_in_place`, `composite_layer_masked`)
- `bti/engine/README.md` (the family, the band, the font kinds, tests and previews)
- `style/gae/techniques.json` (seven entries, 71 -> 78), `style/gae/style.json` (block `identity`), `style/gae/techniques.schema.json` (id pattern)
- `style/gae/fonts/EBGaramond-Regular.ttf`, `EBGaramond-Italic.ttf`, `EBGaramond-Medium.ttf`, `OFL.txt` (new)
- `style/gae/previews/ID-*.mp4` and `ID-*.jpg`, 14 new files (seven techniques)
- `.gitignore` (`!style/gae/previews/*.mp4`; the 70 old clips now show as untracked and need `git add` by you)
- `tests/engine/test_identity.py` (new), `tests/engine/identity_lab.py` (new), `tests/engine/test_default_params.py`, `tests/engine/test_registry_complete.py`, `tests/engine/test_validate_draw_sweep.py`
- `docs/qa/FIX_identity_engine.md` (this file), `.scratch/agy_tasks/idengine/STATUS.md`
- scratch (not tracked): `.scratch/idengine/` (stills, contact sheets, the lab script `idlab.py`, the one-off scripts that wrote the registry and style entries); on the server `D:\code\behind-the-image\run\snap-idengine\_idtmp\` (my private snapshot only)
