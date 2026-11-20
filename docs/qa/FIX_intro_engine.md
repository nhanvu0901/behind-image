# FIX: the channel-name beat that also writes the video's title (worker `introengine`)

Date: 2026-11-20. Branch `wt/introengine` (worktree `.worktrees/introengine`). Nothing is committed; the files below are changed in the worktree.

## What was built

A new base technique **`ID-BRAND-03`** (class `BrandTitle` in `bti/engine/techniques/identity.py`, registry entry in `style/gae/techniques.json`, placed after
`ID-BRAND-02`). It is the beat the owner asked for: the picture dims, a band of light sweeps and writes the channel name, a pause, the band sweeps a second
time in the same direction and writes the video's title (italic, as given) with a small line under it (capitals, tracked); the name stays and does not move; a
hold to the end of the shot. `ID-BRAND-01` (class, params, registry entry, tests) is untouched; a guard test proves its frames are byte-identical to before.

Nominal timeline, seconds from the start of the shot (defaults, scaled like the other identity techniques when the shot is shorter, held when it is longer):

| from | for | what |
|---|---|---|
| 0 | `dim_s` 0.6 | the picture dims from 100 % to `floor` 0.12 |
| 0.5 | `sweep_s` 1.6 | the band crosses; the channel name is written along its path; behind the band the picture is at `wake` 0.26 |
| 2.1 | `name_hold_s` 2.4 | nothing moves except the camera's slow push |
| 4.5 | `title_sweep_s` 1.6 | the band crosses again; title and small line are written along its path; the name stays; the picture is at `wake` before and behind this band |
| 6.1 | `title_hold_s` 3.0 | everything held until the shot ends; nominal length 9.1 s |

No `title` and no `subtitle`: no second sweep, nominal length 4.5 s, the name at `y_alone_pct` 42. One line only: the second sweep writes that line at its own
place (`title_y_pct` 54 or `sub_y_pct` 62.5); the nominal length stays 9.1 s. Whitespace-only text counts as empty.

## Final params (name, default, range in the registry)

All names and defaults are exactly the contract's; nothing was renamed. No `CONTRACT:` line was needed in the status file.

| param | type | default | min .. max | unit |
|---|---|---|---|---|
| `camera` | camera | null (the applier writes the whole picture, 3 % push) | | |
| `shadow` | bool | true | | |
| `text` | string | "RAKING LIGHT" (from `identity.channel_name` of the style, drawn in capitals) | up to 120 characters | |
| `title` | string | "" (italic face, as given, not capitalised) | up to 120 characters | |
| `subtitle` | string | "" (regular face, capitals, tracked) | up to 120 characters | |
| `dim_s` | number | 0.6 | 0 .. 5 | s |
| `floor` | number | 0.12 | 0 .. 1 | x brightness |
| `wake` | number | 0.26 | 0 .. 1 | x brightness |
| `sweep_delay_s` | number | 0.5 | 0 .. 10 | s |
| `sweep_s` | number | 1.6 | 0.2 .. 20 | s |
| `name_hold_s` | number | 2.4 | 0 .. 20 | s |
| `title_sweep_s` | number | 1.6 | 0.2 .. 20 | s |
| `title_hold_s` | number | 3.0 | 0 .. 20 | s |
| `direction` | enum | "left_to_right" | right_to_left, left_to_right | |
| `band_width_pct` | number | 16 | 2 .. 60 | % W |
| `feather` | number | 0.4 | 0.05 .. 1 | ratio |
| `angle_deg` | number | 10 | -45 .. 45 | deg |
| `warm` | number | 0.14 | 0 .. 1 | alpha |
| `cap_pct` | number | 8.0 | 1 .. 20 | % H |
| `tracking_pct` | number | 25 | 0 .. 100 | % em |
| `y_pct` | number | 36 (centre of the name when a line follows) | 5 .. 95 | % H |
| `y_alone_pct` | number | 42 (centre of the name with no line) | 5 .. 95 | % H |
| `title_cap_pct` | number | 4.6 | 1 .. 20 | % H |
| `title_y_pct` | number | 54 | 5 .. 95 | % H |
| `sub_cap_pct` | number | 2.2 | 1 .. 20 | % H |
| `sub_tracking_pct` | number | 14 | 0 .. 100 | % em |
| `sub_y_pct` | number | 62.5 | 5 .. 95 | % H |

`timing`: `default_s` 9.1, `min_s` 1.5, `max_s` 30, anchor `shot_start`. The ranges, the 120-character limit of the three strings (the same as `ID-BRAND-01`'s `text`)
and the `usage_rule` / `description` are mine; the brief gave only the defaults.

## Defaults changed

**None.** I looked at the stills (below) and the brief's numbers read well: no lines collide, the title reads on a 640 px preview, and the group (name at 36 %,
title at 54 %, small line at 62.5 %) sits slightly above the middle of the frame, in the same spirit as the single name at 42 % of `ID-BRAND-01`. I tried to
find a reason to move `sub_cap_pct` (2.2 %) up and did not: it is the same size as the small line of `ID-OPEN-02` (design document) and is legible at 640 px.

Two additions that are not params: the title and the small line are held to **84 %** of the frame width (`TITLE_MAX_W_PCT`; the name keeps the older 88 %), and the
**title is kerned** (next section).

## What happens to a long title

The two lines are one line each, never wrapped, never cut: `ink_layer` makes the font smaller until the line is at most 84 % of the frame wide (margins of 8 %).
At 1080p (title font 76 px, cap height 4.6 % of the frame height):

| title | font | cap height | width |
|---|---|---|---|
| 39 characters ("The Saint Who Was Also an Advertisement") | 76 px (not shrunk) | 4.6 % | 64.5 % of the width |
| 70 characters | 57 px (75 %) | 3.45 % | 83.5 % |
| 120 characters (the registry's limit) | 33 px (43 %) | 2.0 % | 83.3 % |

So a 70-character title is set at three quarters of the normal size and still reads on a phone-sized preview (checked at 640 px); 120 characters is legal but
small. The tests assert margins of at least 7 % on each side for 70-character titles (`W`x70, `i`x70, a real one) and 5 % for the longest the registry accepts.

**Kerning (not in the brief; I fixed it because a viewer would stumble on it).** With the first render the italic title read "Wh o W as": Pillow's basic layout
(the only one on the server, there is no libraqm) does not read the GPOS kerning of EB Garamond, so "Wa" had a gap of 10 px. I added a small reader of the font's
GPOS pair adjustments with the standard library (`_Kerning` in `identity.py`, no new dependency) and an optional `kern` flag on `ink_layer` / `_build_ink`
(default off, used only by the title of `ID-BRAND-03`). A face that cannot be read is set without kerning, never an error. The older techniques are unchanged
(proved by the guard test). The italic title of `ID-LABEL-01` / `ID-OPEN-02` has the same gap; I did not touch them (recommendation: pass `kern=True` there
in a separate change; it changes their frames, so their goldens would have to be made again).

## The stills (the Read tool was used on each)

Folder: `/Users/nhanvu/Documents/code/behind-the-image/.worktrees/introengine/.scratch/introengine/v3/` (the picture is the Virgin and Child with Canon van der
Paele from `projects/technique_lab`, 1920x1080, the camera the applier writes: whole painting, 3 % push; title "The Saint Who Was Also an Advertisement", small
line "St. Eligius · Petrus Christus, 1449"). Earlier renders, before the kerning, are in `v1/`.

- `contact_sheet_paele.png`: 12 frames over the 9.1 s (0.10, 0.91 ... 9.00 s). Frame 1 is the bright painting; at 0.91 s the picture is dim and the band is at the
  left edge with the first letter R written behind it; at 1.72 s RAKING LIGHT is written up to the band at the right; from 2.53 to 4.15 s the name is held with
  the picture at the wake; at 4.95 s the band is back at the left, lights the picture inside it, and only "The" of the title is written; at 5.76 s the title and
  the small line are complete and the band is leaving at the right; the last four frames are the hold.
- `still_name_alone.png` (t = 4.3 s): the dimmed painting, RAKING LIGHT in big tracked capitals at 36 % of the height, nothing below it.
- `still_second_sweep_mid.png` (t = 5.3 s): a vertical band of light crosses the centre and shows the painting bright inside it; to its left the title "The Saint
  Who Was Also an" and the small line "ST. ELIGIUS · PETRUS CHRI" are written, to its right nothing; the picture is dim on both sides of the band; the name is
  unchanged. The front of the writing is soft (the last letter is half transparent), as in the first sweep.
- `still_final_hold.png` (t = 8.9 s): name, then the italic title (kerned: "Was" is tight), then the small tracked capitals, centred, all over the dimmed picture;
  readable on the red and white parts of the painting too. The group is a little above the middle (name cap top at 32 %, small line baseline at about 64 %).
- `still_final_hold_70chars.png`: the 70-character title "The Goldsmith, the Bride and the Mirror That Saw Everything Behind Her" is one line,
  about 8.4 % margin left and right, visibly smaller than the 39-character one but clear; the small line is unchanged.
- Also: `still_first_sweep_mid.png` (name half written), `still_no_line_name_alone.png` (no lines: name at 42 %, as `ID-BRAND-01`),
  `still_arnolfini_second_sweep_mid.png`, `still_arnolfini_final_hold.png`, `still_arnolfini_title_only_final.png` (title but no small line: the title at its own place
  at 54 %, nothing below), and `phone_640.png` / `phone_640_70chars.png` in `v2/` (the final holds scaled to 640x360).
- The preview of the registry (`style/gae/previews/ID-BRAND-03.mp4`, 640x360, 30 fps, 9.1 s, H.264; `.jpg` is the final hold) shows the Arnolfini Portrait with the
  title "The Mirror in the Arnolfini Portrait" and the small line "The Arnolfini Portrait · Jan van Eyck, 1434". I looked at the `.jpg` and checked the `.mp4`
  with `ffprobe` (not played frame by frame).

`tests/engine/intro_stills.py` makes all of these (run with `tools/deploy/snapshot_py.sh introengine tests/engine/intro_stills.py out_introengine preview`).

## Files changed

- `bti/engine/techniques/identity.py`: `BeatState`, `BrandTitle` (`ID-BRAND-03`), `_Kerning`, the `kern` option of `ink_layer` / `_build_ink`, constant
  `TITLE_MAX_W_PCT`, module docstring. No existing class changed.
- `style/gae/techniques.json`: the entry `ID-BRAND-03` (86 techniques now); `style/gae/previews/ID-BRAND-03.mp4` and `.jpg` (new, tracked: `.gitignore` already
  un-ignores previews).
- `bti/editor/static/js/labels.js` (card map: `'ID-BRAND-03': 'Tên kênh và tựa video'`, `node --check` ok), `bti/editor/static/js/camgeom.js` (the camera of the
  new id, like the other base identity techniques), `bti/output/shotwords.py` (the Python twin of the card map), `tests/output/fixtures/shot_cases.json`
  (regenerated with `UPDATE_GOLDEN=1`; the only difference is the entry of the new id).
- `skills/storyboard/SKILL.md`: the generated technique table (`docgen --print` on the snapshot; only the new id and "86 techniques" differ).
- `bti/engine/README.md` and `docs/design/2026-11-18-identity-raking-light.md` (new section 4b).
- Tests: new `tests/engine/test_identity_brand_title.py` (31 tests with the parametrised ones) and `tests/engine/intro_stills.py`; counts 85 -> 86 and the
  new lab reference in `tests/engine/{test_registry_complete,test_default_params,test_explain_over,test_validate_draw_sweep,test_identity,identity_lab}.py`,
  `tests/deep/test_sweep.py`, `tests/deep/sweep.py`.

What the new tests check (same manner as `test_identity.py`, real frames of a flat grey or black picture): the registry entry and its defaults against the contract
table; `default_params`; `ID-BRAND-01`'s params unchanged; the nominal length with both lines, one line, none and custom times; the state of the beat (`BeatState`) at
0, 0.3, 0.55, 1.3, 2.11, 2.5..4.4999, 4.5001, 5.3, 6.11, 6.5..9.1 and on a longer shot; the light on a flat picture before, during and after each sweep (the wake on
both sides of the second band, a warm lift inside it); the scaled timeline on a half-length shot (frames equal at doubled times, with and without lines), a 3 s shot and
a 14 s shot; the name at 36 % / 42 % and unmoved between the phases (the same ink at 3.3, 4.6, 5.0, 5.3, 5.8, 6.5, 9.0 s); the lines at their params and set as given (italic,
not capitalised; the small line in capitals); one line alone at its own place; the reveal following the band (a narrow band: nothing ahead of it, everything behind
it fully written, the writing only grows); nothing of the lines before the second band; 70- and 120-character titles inside the frame; kerning read from the font and
used only when asked; a frame is a pure function of time; every number at its min and max (45 values); odd text; and the guard: SHA-256 of 19 frames of `ID-BRAND-01`
(two settings), `ID-MARK-01`, `ID-LABEL-01` and `ID-OPEN-02` are equal to the ones made with the code of git HEAD de426d3 (I put HEAD's `identity.py` and registry into
my snapshot to make them, then re-synced). That guard depends on the server's Pillow 13.0.0 / FreeType 2.14.3: if a library change moves a pixel and the pictures
still look right, make the values again with `golden_frames` (its docstring says how).

## Test summary lines (exactly as printed)

Snapshot `introengine`, one folder per run, never `-m slow`:

- `tests/engine -m "not slow"`: `646 passed, 14 skipped, 166 deselected in 389.73s (0:06:29)`
- `tests/identity`: `77 passed in 1.87s`
- `tests/draft`: `1 failed, 437 passed, 1 warning in 162.15s (0:02:42)`; the failure is `FAILED tests/draft/test_identity_catalogue.py::test_the_family_is_the_seven_techniques_of_the_block` (see "Needs another worker")
- `tests/editor`: `491 passed, 1 warning in 234.23s (0:03:54)`
- Also, because I touched what they check: `tests/output`: `77 passed, 1 warning in 18.23s`; `tests/cli/test_cli_docs.py`: `19 passed, 1 warning in 6.01s`;
  `tests/deep/test_sweep.py -k "ID-BRAND or test_registry_has or test_the_lab_has"`: `5 passed, 83 deselected, 1 warning in 7.29s`
- After a last one-line change (the kerning cache is keyed by file path), on the final tree: `tests/engine/test_identity_brand_title.py test_identity.py test_registry_complete.py test_default_params.py test_explain_over.py`: `203 passed in 110.53s (0:01:50)`
  (the whole `tests/engine` run above was made just before that edit; the other folders after it)
- On the Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`:
  `ℹ tests 460`, `ℹ suites 0`, `ℹ pass 459`, `ℹ fail 0`, `ℹ cancelled 0`, `ℹ skipped 1`, `ℹ todo 0`, `ℹ duration_ms 1048.157209` (the skipped one needs a `.venv` on the Mac).

## Needs another worker (what I saw in their files; I did not edit any of it)

1. **`tests/draft/test_identity_catalogue.py::test_the_family_is_the_seven_techniques_of_the_block` fails, caused by the new registry id.** `family(bundle)` collects every
   technique that `cfg.is_identity_technique` accepts, which includes anything with the prefix `ID-BRAND-` (`bti/identity/config.py`, `PREFIX`), so it now returns
   eight ids while the style block names seven. Not mine to fix (it is in `tests/draft`), and it cannot be fixed by `style.json` alone unless the block names both
   `ID-BRAND-01` and `ID-BRAND-03` (e.g. `raking` keeps `ID-BRAND-01` for another role or a new key) or the test is rewritten to "every named technique is in the family".
2. `style/gae/style.json`: `identity.styles.raking.brand` is `ID-BRAND-01` and `nominal.brand.dur_s` is 5.0. To use the new beat: `brand` becomes `ID-BRAND-03` and the
   nominal length 9.1 (with a title) or 4.5 (without); the formula is in `BrandTitle.nominal_s`: `sweep_delay_s + sweep_s + name_hold_s` plus `title_sweep_s + title_hold_s` when
   `title` or `subtitle` is non-blank. `tests/engine/test_identity.py::test_style_block_names_the_techniques_of_each_style` (mine to edit, not edited) asserts that the block names exactly the seven
   ids of `IDS` and that `nominal.dur_s == NOMINAL[tid]`; it will fail when `style.json` changes and has to be updated together with it.
3. `bti/identity/apply.py` (line ~418) writes `{"camera": keys, "text": channel_name}` for the brand shot; for `ID-BRAND-03` it must also write `title` and `subtitle` (both
   optional, up to 120 characters, one line each; a longer one is shrunk, not cut). `is_mismatch` / `is_family` already treat `ID-BRAND-03` as a brand technique by prefix, so a
   structure shot carrying it is a mismatch warning (`identity_technique_mismatch`) until the style names it.
4. `bti/draft/techniques_md.py` already lists any `ID-BRAND-*` as `PROGRAM ONLY` (by `is_identity_technique`), so the briefing needs no change; `tests/draft/test_box_briefing.py`
   line 86 lists `ID-BRAND-01` among the ids that must not appear in the small-edit catalogue; adding `ID-BRAND-03` there would make the test say the same about the new one.
5. `skills/storyboard_draft/TASK.template.md` line 175 says `ID-BRAND-*` are program-owned: still true, no change needed.

## What I could not verify

- The slow sweep tests (`tests/engine/test_validate_draw_sweep.py`, 166 tests deselected by `-m "not slow"`, never run by me): the lab now has a reference shot of `ID-BRAND-03`
  in `identity_lab.py` and the file's counts say 86, but that sweep (every parameter of every type replaced by odd values) has not been run for the new id. My own tests cover
  the min and max of every number and odd texts only.
- The beat inside the real editor page and in a real project: no page was opened, no project of the owner was touched, no export was made. The card sentence, the camera
  editor entry and the labels are covered by the unit tests only (the sentence of a shot with this technique reads "Tên kênh và tựa video: <title>").
- The preview `.mp4` was checked with `ffprobe` and by its `.jpg`, not played.
- The Vietnamese label "Tên kênh và tựa video" is the one the brief gave; the registry's `label_vi` "Tên kênh và tựa video: vệt sáng quét" follows `ID-BRAND-01`'s pattern; neither was read by the owner.
- Kerning is the GPOS pair adjustment of the two bundled faces only (no ligatures, no mark positioning); the other techniques' sentences are still set without kerning.
- The snapshot `D:\code\behind-the-image\run\snap-introengine\` still holds my output folder `out_introengine\` (stills, a lab with two copied pictures, the preview); nothing outside the snapshot was written.
