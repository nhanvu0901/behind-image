# V_compare — our 8 published Shorts vs the 10 competitor Shorts

**Measured**: tables 1 and 3 (`vmetrics.py`, `compare_table.py`, `out_ours/`, `out_competitors/`). **Judged by eye**: table 2, the mascot section and the bubble findings (`rubric_ours.csv`, `rubric_competitors.csv`).
**Comparison sheets for the owner**: `compare/compare_openings_0_1_2s.jpg`; `compare/pair1_spiderman_monster_ours_vs_ComicsUnlocked.jpg`; `compare/pair2_fantastic_four_ours_vs_comiczyt.jpg`; `compare/pair3_captain_america_ours_vs_ComicEscape.jpg` (extra).

## Read this first

- **The script changed once and both sides were re-run with the same code.** Framing is now measured at 1 frame per second plus a separate 0-3 s window, instead of 12 frames. The 12 frames missed short letterboxed stretches. New columns: `padded_time_frac`, `sharp_frac_0_3s`, `luma_mean_0_3s`, `dark_time_frac`.
- **The files are not the same quality.** Ours were downloaded at 608x1080 and 0.36-0.57 Mbit/s; the competitors at 360x640 and about 0.2 Mbit/s. vmetrics converts ours to the competitors' format before measuring.
- **There are no transcripts for our videos.** The download of the YouTube auto-captions failed with HTTP 429 for all 8, so speech rate and words in the first 3 s are **not measured** on our side.
- **Voice type** (human or TTS) was not judged on either side, because I could not listen.
- **Sample and age.** 8 vs 10 videos. Our ages are 1-39 days, theirs 1 h to 5 days. Views are not used as evidence of cause anywhere in this file.

## 1. Metrics (measured; flag = our median outside the competitor range)

| metric | ours median | ours range | comp median | comp range | flag |
|---|---|---|---|---|---|
| duration_s | 49.7 | 32.2 to 68.4 | 54.1 | 38.1 to 171.7 | 2/8 outside |
| image_changes_per_10s | 3.57 | 3.07 to 4.90 | 4.54 | 3.03 to 8.66 | 0/8 |
| median_image_hold_s | 2.48 | 1.83 to 3.17 | 1.88 | 1.00 to 2.92 | 2/8 |
| first_image_change_s | 2.00 | 0.10 to 3.50 | 0.78 | 0.10 to 4.90 | 0/8 |
| image_changes_first_3s | 1 | 0 to 2 | 1 | 0 to 4 | 0/8 |
| cuts_per_10s (scene ≥0.30) | 3.11 | 2.49 to 5.29 | 3.74 | 0.76 to 11.0 | 0/8 |
| speed_pct_w_per_s_0_3s (gradient) | 5.1 | 2.8 to 13.6 | 35.6 | 6.8 to 70.5 | **OUTSIDE**, 6/8 |
| speed_pct_w_per_s_median | 5.2 | 2.6 to 7.3 | 30.9 | 7.6 to 69.2 | **OUTSIDE**, 8/8 |
| speed_bm_0_3s (block matching, 4.6 quantum) | 4.6 | 0 to 19.1 | 46.8 | 4.6 to 58.6 | 3/8 |
| static_frac_0_3s | 0.07 | 0 to 0.38 | 0.00 | 0 to 0 | **OUTSIDE**, 6/8 |
| static_frac_all | 0.13 | 0.07 to 0.22 | 0.00 | 0 to 0.01 | **OUTSIDE**, 8/8 |
| lufs_I | −13.6 | −14.6 to −13.4 | −18.1 | −23.7 to −13.7 | **OUTSIDE (louder)**, 5/8 |
| lra_LU | 1.85 | 1.4 to 2.0 | 2.10 | 1.5 to 3.9 | 1/8 |
| true_peak_dbtp | −2.65 | −3.8 to −2.1 | −3.25 | −7.6 to +0.8 | 0/8 |
| lufs_first2_minus_rest | 0.3 | −0.3 to 0.9 | 1.2 | −0.6 to 2.4 | 0/8 |
| rms_db_first_100ms | −58.4 | −75.9 to −40.8 | −18.2 | −38.5 to −10.8 | **OUTSIDE**, 8/8 |
| first_sound_s | 0.21 | 0.06 to 0.24 | 0.00 | 0 to 0.04 | **OUTSIDE**, 8/8 |
| rms_db_p05 (level under pauses) | −36.2 | −69.9 to −33.2 | −37.8 | −42.4 to −26.0 | 2/8 (no bed) |
| floor_gap_db | 19.8 | 16.9 to 52.4 | 15.7 | 7.6 to 18.7 | **OUTSIDE**, 5/8 |
| words_per_s / words_first_3s | n/a | — | 3.51 / 9.9 | 2.9-3.9 / 7.7-11.4 | not measurable |
| sharp_frac_0_3s | 0.88 | 0.22 to 0.99 | 0.93 | 0.22 to 1.00 | 0/8 (3/8 < 0.36; pure-comic competitors' min is 0.81) |
| sharp_frac_med | 0.93 | 0.48 to 0.98 | 0.96 | 0.46 to 1.00 | 0/8 |
| padded_time_frac | 0.30 | 0.13 to 0.53 | 0.07 | 0 to 0.95 | 8/8 above every pure-comic competitor (max 0.095); only GiyeSears is higher (0.88-0.95, with animated backgrounds) |
| dark_time_frac (luma < 50) | 0.06 | 0 to 0.21 | 0.00 | 0 to 0.12 | 3/8 |
| luma_mean_0_3s | 90.9 | 25.2 to 106.9 | 102.6 | 63.1 to 177.3 | 3/8 darker |
| saturation_med | 0.42 | 0.30 to 0.44 | 0.40 | 0.23 to 0.57 | 0/8 |
| contrast_std_med | 69.4 | 55 to 75 | 71.0 | 60 to 83 | 1/8 |
| loop_first_last_corr | 0.08 | −0.20 to 0.97 | 0.00 | −0.27 to 0.43 | 2/8 loop (x1zX 0.97, F0lz 0.71) |

## 2. Rubric (judged by eye, 1-5; evidence per video in `rubric_ours.csv`)

| item | ours mean (range) | comp mean (range) | evidence |
|---|---|---|---|
| first_frame | **2.4** (1-5) | 3.4 (1-5) | The three newest videos open on a dark film or animation clip letterboxed over blur. Only x1zX opens on a clean full-bleed hero |
| hook_text | 2.9 (1-4) | 2.6 (2-5) | Our captions spell out the premise by 2-4 s ("WHAT IF CAPTAIN AMERICA STAYED FROZEN"); 8 of 10 competitors show one word at a time |
| captions | 2.9 (1-4) | 3.4 (3-4) | Ours: yellow comic italic, 3-6 words over up to 3 lines, at about 65 % of the height; xqW0 uses white with a cyan keyword; x1zX has none. Theirs: 1-3 words |
| framing | **2.4** (1-4) | 4.5 (3-5) | 13-53 % of seconds padded. Erased, **empty speech bubbles** are visible in all 8 |
| motion | **2.1** (1-3) | 4.3 (2-5) | Zy0C barely moves (3.2 %/s) and has no image change until 3.5 s |
| variety | 3.4 (3-4) | 4.1 (3-5) | Film and animation clips help, but no close-ups or whip transitions |
| colour | 3.1 (2-4) | 3.8 (2-5) | Dark film clips; saturation is equal |
| audio | 2.8 (2-3) | 3.4 (2-5) | Loud enough; 0.2 s of silence at the start; no music bed in 2 of 8 |
| ending | 2.6 (2-5) | 3.0 (2-5) | 6 of 8 end on a spoken + captioned "Make sure to subscribe for more content" (competitors: 0 of 10) |
| branding | 2.0 (2-2) | 2.9 (2-4) | Small semi-transparent logo top-right only |

## 3. Gaps ranked by likely effect on swipe-aways and early exits

1. **Weak, dark, padded opening frame** (Stage 5: cold-open choice and clip framing). In F0lz, H3Qo and n2bj the art is only 22-35 % sharp in the first 3 s, and the average brightness in those seconds is 25-55, below every competitor (min 63). Each opens on a movie or animated clip in a letterboxed strip; see `compare_openings_0_1_2s.jpg`. 90sx opens on a machine with Superman cut off.
2. **The picture barely moves** (Stage 5 Ken Burns). Apparent speed is 5 % of width per second, against 31 for competitors, and all 8 of ours are below the slowest competitor (7.6). The picture is frozen 13 % of the time, against ≤1 %. In 6 of 8 videos it is frozen for part of the first 3 s.
3. **Empty erased speech bubbles** (Stage 5: `INPAINT_BUBBLE_TEXT = True`, shots.py:109; the code itself calls this "empty bubble slop"). White or pink blank shapes appear in all 8, and in the first frame of 90sx and nlXR (8 boxes). All competitors keep the original lettering.
4. **Letterbox and blur for a third of the video** (Stage 5 contain+blur and clip framing). `padded_time_frac` is 0.30, against ≤0.095 for the 8 pure-comic competitors. GiyeSears pads too, but behind tilted cards with moving streak backgrounds.
5. **0.2 s of silence at t=0** (Stage 5 audio / TTS lead-in). The first sound comes at 0.21 s and the first 100 ms sit at −58 dBFS. On the competitors, sound starts at 0.00 s and the first 100 ms sit at −18 dBFS.
6. **Slower first image change and longer holds** (Stage 5 shot length). The first change comes at 2.0 s against 0.78 s, and images hold 2.5 s against 1.9 s. Both are still inside the competitor range, so this is the lower-confidence gap.
7. **Captions** (CapCut). Phrases of 3-6 words over several lines, compared with 1-3 words; the style changes between videos; x1zX has no captions at all.
8. **No music bed in 2 of 8** (Zy0C and x1zX: −65 and −70 dB during pauses). Every competitor has a bed (Stage 5 music).
9. **Subscribe CTA at the end** of 6 of 8 (script/narration, not Stage 5).

## 4. The crow mascot

**I could not find a crow in any of the 8 published files.** I checked every hook strip, 2-second sheet and end strip, plus the bottom-left quarter of the frame every 3 s in all 5 videos from Nov 7 onward (`mascot/bottomleft_strips.jpg`).
- The only overlay that repeats is the hooded-figure channel logo, top-right. It is about 31x31 px of 608x1080 (about 5 % of the width and 0.15 % of the area), semi-transparent, and also present in the October videos (`mascot/corners.jpg`).
- The logo does not touch the captions (they sit at about 60-67 % of the height) and only grazes art in the corner.
- So the mascot effect **cannot be tested on these files**.
- Splitting by date instead (5 videos from Nov 7 onward vs 3 older), the newer ones open on letterboxed clips more often (3/5 vs 0/3) and all have a music bed (5/5 vs 1/3). With n=5 vs 3, this says nothing about a mascot.

## 5. Keep: things we already match or beat

- **Loudness.** −13.6 LUFS: as loud as comiczyt, the loudest competitor, and 4.5 LU above the competitor median (the July −24.6 gap is fixed). YouTube turns loud videos down but never turns quiet ones up, so do not lower it.
- **Saturation and contrast** match.
- **Image-change rate.** 3.6 per 10 s, inside the competitor range and level with Comic_Escape.
- **Duration.** About 50 s, the right band.
- **Premise.** The spoken premise reaches the screen by 2-4 s.
- **Seamless loop** where used (x1zX 0.97, F0lz 0.71; the competitor maximum is 0.43).
- **Logo** small and out of the way.

## 6. Inside our 8: the two best vs the two weak (n=2 vs 2, ages 4 / 39 / 14 / 10 days)

- **Best H3Qo (8,216).** The darkest, most padded opening of all, but the strongest premise and the most motion of ours in the first 3 s (13.6 %/s, from a moving film clip).
- **Best x1zX (7,460).** The best first frame (a full-bleed hero), no captions, a seamless loop and no CTA. It is 32 s long and has no music bed.
- **Weak Zy0C (1,528).** Near-still (3.2 %/s) for 3.5 s before the first change (the latest of ours), the longest video (68 s), 37 % padded, no music bed, and a B-tier subject shown as a brown mass.
- **Weak nlXR (1,379).** A cluttered first frame with about 8 erased-bubble boxes.
- **What the two best share:** an A-tier hero and a big premise ("What If… 2099", "snipes a planet"), and no long near-still opening. The two weak videos share neither a format nor a metric that sets them apart; loudness, saturation and change rate are all the same.
- Topic and age explain more than any edit setting.
