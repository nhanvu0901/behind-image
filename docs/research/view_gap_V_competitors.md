# V_competitors — video forensics, phase 1 (10 competitor Shorts)

Files: `vmetrics.py` (measurements + sheets), `mdtable.py` (this table), `rubric_competitors.csv` (scores), `out_competitors/` (JSON per video, `metrics_competitors.csv`, `hook_*`, `sheet_*`, `end_*`, `hooks_all_competitors.jpg`), `synthetic/` (calibration clips).
Rerun: `python3 vmetrics.py <folder> --out <dir> --label <name> [--manifest csv] [--srt-dir dir]`.

## Read this first: what the numbers can and cannot carry

- **The view counts mostly measure age.** The views were fetched on Nov 3, about 17:53 UTC (the time comes from the metadata file times). In every channel pair the low-view video is the younger one. Two of them were **1.3 h and 1.8 h old** (c15V… and KfZf…), so their views say nothing about how well they perform. Only the ComicCandid pair (41 h vs 16 h) and the ComicsUnlocked pair (127 h vs 31 h) are even roughly comparable, and age still confounds both. This is n=10 with no retention data. Treat everything in the high-vs-low section as a hypothesis.
- All 10 files are YouTube **360x640, 30 fps, about 350-440 kbit/s**. By default, vmetrics converts any taller input to the same kind of proxy before measuring. **For phase 2, analyse the published YouTube downloads**, not the pipeline renders: the CapCut captions and the mascot exist only in the published file.
- **Measured**: everything in table 1. **Judged by eye**: table 2 and the house templates. **Not assessed**: whether the voice is human or TTS (I could not listen to the audio).

## Method notes and calibration (synthetic clips with known truth)

| Measure | How | Calibration / limits |
|---|---|---|
| Image changes | ffmpeg scene score ≥0.30 (cuts <0.25 s apart merge), **plus** block-matching "unexplained change" events (whip, glitch and slide transitions). A scene cut is dropped when motion explains it | A 50 %/s pan gave 10 false scene cuts; after the filter it gave 0. Plain scene cuts missed 61 of 74 image changes in a comiczyt video (blur-whip transitions) |
| Speed (`speed_bm`) | 12x12 block matching on 108x192 gray, frames 0.2 s apart. Unit: % of frame width per second | Synthetic pans of 8.3 and 50 %/s read as 9.3 and 50.9. Resolution is 4.6 %/s and values cap near 55 %/s. **A slow Ken Burns push (1.00→1.10 over 4 s) reads 0**. The gradient estimator `speed grad` resolves it at about 2 |
| Framing (`sharp art`) | Tile grid 6x16; Laplacian variance ≥60 means sharp, a dark flat tile counts as black | Bands covering 36.5 % and 26 % of the frame read as 0.44 and 0.30, so it overestimates by about 7 points. Flat real art reads as blur; captions or stickers on blur read as sharp |
| Loudness | ebur128 (I, LRA, true peak) on the whole video, the first 2 s, and the rest. `floor` = 5th percentile of 20 ms RMS | A floor above about −43 dBFS means something keeps playing under the pauses (a music/SFX bed) |
| Speech | Word count from the SRT over the cue span | The SRTs are machine transcripts. **Every first cue starts at 0.000**, so the SRT cannot give the time of the first word; use `1st sound` instead |
| Loop | Best correlation between frame 0 and any frame in the last 1 s | Frames grabbed later than duration−0.3 s returned the *opening* frame, a seek artifact that I caught and fixed |

## 1. Metrics (measured)

> Phase-2 note: framing was later re-measured at 1 fps plus a 0-3 s window (script v2), and both sides were re-run. Where the framing columns below differ from `out_competitors/metrics_competitors.csv`, the CSV is current.

| ch | id | views | dur s | img chg/10s | med hold s | 1st chg s | chg <3s | scene cuts/10s | speed 0-3s | speed med | speed grad | static | LUFS | LRA | TP | first2s-rest LU | floor dB | 1st sound s | wps | words<3s | sharp art | blur | sat | loop r |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Comic_Escape | c15VutkhmCg | 1,054 | 82.5 | 3.03 | 2.92 | 4.90 | 0 | 3.03 | 13.9 | 27.8 | 28.6 | 0.00 | -18.1 | 2.1 | -4.0 | 1.4 | -37.5 | 0.00 | 3.36 | 9.9 | 0.97 | 0.03 | 0.45 | -0.09 |
| Comic_Escape | oeRw2J5GU9Q | 8,154 | 41.3 | 3.63 | 2.22 | 1.90 | 1 | 3.63 | 32.4 | 27.9 | 33.1 | 0.01 | -17.7 | 2.0 | -3.1 | -0.6 | -38.3 | 0.04 | 3.91 | 11.4 | 1.00 | 0.00 | 0.43 | -0.04 |
| ComicCandid | 9BLJ7Rb5jYI | 10,752 | 44.2 | 4.30 | 1.92 | 0.10 | 1 | 3.85 | 55.6 | 55.7 | 43.2 | 0.00 | -19.4 | 2.8 | -3.4 | 1.7 | -41.7 | 0.00 | 2.88 | 9.6 | 0.96 | 0.02 | 0.37 | 0.10 |
| ComicCandid | oOqAcwkS2oM | 2,409 | 45.6 | 5.05 | 1.85 | 2.27 | 1 | 4.61 | 55.6 | 55.6 | 40.6 | 0.00 | -19.4 | 3.9 | -3.8 | 2.4 | -40.8 | 0.00 | 3.33 | 11.1 | 0.92 | 0.04 | 0.29 | -0.12 |
| ComicsUnlocked | jobGQ5mmi-o | 5,002 | 48.2 | 4.77 | 1.72 | 1.10 | 1 | 4.77 | 47.2 | 32.4 | 27.1 | 0.00 | -22.1 | 1.5 | -3.6 | 1.5 | -38.2 | 0.00 | 3.49 | 7.7 | 0.96 | 0.03 | 0.29 | 0.03 |
| ComicsUnlocked | n_OJTdc09yM | 26,196 | 38.1 | 3.68 | 2.40 | 1.90 | 1 | 3.42 | 4.6 | 4.6 | 7.6 | 0.00 | -23.7 | 2.0 | -7.6 | 1.0 | -42.4 | 0.00 | 2.95 | 7.8 | 0.98 | 0.01 | 0.58 | -0.27 |
| comiczyt | bU2ylVNGaDI | 24,479 | 171.7 | 4.31 | 2.20 | 0.10 | 2 | 0.76 | 13.9 | 23.1 | 22.4 | 0.00 | -13.7 | 2.1 | +0.8 | 0.9 | -26.2 | 0.02 | 3.65 | 10.8 | 0.99 | 0.01 | 0.37 | 0.13 |
| comiczyt | KfZf5mJgGvI | 2,936 | 95.3 | 5.46 | 1.80 | 0.10 | 3 | 1.16 | 46.3 | 18.5 | 22.2 | 0.00 | -13.8 | 2.1 | +0.6 | 1.5 | -26.0 | 0.02 | 3.65 | 10.6 | 0.92 | 0.08 | 0.34 | -0.03 |
| GiyeSears | 5aB9-sS33sg | 7,015 | 60.0 | 8.66 | 1.00 | 0.47 | 4 | 11.0 | 58.6 | 35.8 | 69.2 | 0.00 | -18.2 | 2.1 | -1.9 | 1.0 | -28.4 | 0.00 | 3.56 | 10.0 | 0.50 | 0.47 | 0.56 | 0.43 |
| GiyeSears | tGAB5OhUh4c | 14,907 | 80.3 | 8.47 | 1.03 | 0.30 | 3 | 8.84 | 50.2 | 41.7 | 46.6 | 0.01 | -17.9 | 1.9 | -2.0 | 0.5 | -27.0 | 0.00 | 3.53 | 8.5 | 0.52 | 0.43 | 0.49 | 0.13 |
| **median** | | | 54.1 | 4.54 | 1.88 | 0.78 | 1 | 3.74 | 46.8 | 30.1 | 30.9 | 0.00 | -18.1 | 2.1 | -3.3 | 1.2 | -37.8 | 0.00 | 3.51 | 9.9 | 0.96 | 0.03 | 0.40 | 0.00 |

Age when the views were fetched (h): 1.3, 49.4, 40.7, 16.3, 31.3, 127.1, 25.9, 1.8, 38.9, 123.9 (same order as the table).

## 2. Rubric (judged by eye; 1 = weak/absent, 5 = strong)

| id | views | first_frame | hook_text | captions | framing | motion | variety | colour | audio* | ending | branding |
|---|---|---|---|---|---|---|---|---|---|---|---|
| c15V | 1.1k | 3 Cap+Spidey medium shot | 2 no title; 1-word caption at 0.5 s | 3 one green word, black stroke, mid-frame | 5 full-bleed | 3 slow slide in, first change 4.9 s | 3 panels only | 4 | 3 | 2 open story end, no loop | 3 watermark + subscribe pop-up |
| oeRw | 8.2k | 3 Sabretooth on a busy page | 2 | 3 same as c15V | 4 whole pages, small bubbles | 4 | 4 symbiote spreads, SFX | 4 | 3 | 2 | 3 |
| 9BLJ | 10.8k | 2 dark wide newsroom, Clark small | 2 2-3 white words | 3 2-3 white bold words, stroke | 5 | 5 fast pans/zooms, mirror transition | 4 face close-ups | 4 | 3 | 2 moral line | 3 "COMIC CANDID" top-right |
| oOqA | 2.4k | 1 empty doorway, Logan enters at 1 s | 2 | 3 | 5 | 5 | 4 | 2 grey/teal, sat 0.29 | 3 | 3 pun end | 3 |
| jobG | 5.0k | 5 body-horror cover | 2 1 word | 3 one white word, stroke | 5 | 4 | 4 | 3 | 2 quiet −22 | 4 cliffhanger "he's become a monster" | 3 faint watermark |
| n_OJ | 26.2k | 5 big cyan-armoured character | 2 1 word | 3 | 5 | 2 gentle zooms only | 4 | 5 sat 0.58 | 2 quiet −24 | 2 | 3 |
| bU2y | 24.5k | 3 glitch then team shot | 2 | 4 1-2 big words, colour-coded, heavy stroke | 5 | 5 whip/spin/glitch | 4 | 4 | 5 loud −14, dense bed | 3 | 2 style only |
| KfZf | 2.9k | 3 glitch then Silk falling | 2 | 4 | 5 | 5 | 4 | 4 | 5 | 3 | 2 |
| 5aB9 | 7.0k | 4 glowing Flash face | 5 title question in huge yellow comic type | 4 comic italic, yellow keyword, ~68 % height | 3 tilted cards over streak/blur | 5 | 5 animation clips + panels | 4 | 4 | 5 answers itself + visual loop | 3 caption font |
| tGAB | 14.9k | 5 Cyclops full figure | 5 "ALL OF CYCLOPS'S COMIC BOOK SUITS" | 4 | 3 | 5 | 5 new suit every 0.5 s, X-Men '97 clips | 4 | 4 | 4 "Part 1", new-chapter tease | 4 current-suit sticker top-right |

\*audio = loudness, bed and pace only. Voice type was not judged. No video has a spoken CTA. Topic, hook sentence and swipe-stop tactic per video are in `rubric_competitors.csv`.

## 3. High vs low views (small, age-confounded sample)

No measured metric separates high from low. n_OJ, the top video, has the *slowest* motion and is the second-quietest. jobG and KfZf, both low, have strong openings. Visual and audio settings are nearly constant **within** each channel, so the variation in views inside a channel comes from topic and age, not from the edit. The few defensible contrasts:
- The highs are A-tier characters with **concrete stakes or a comparison in the title** ("Is Dying From Kryptonite", "Makes Wolverine Look WEAK", "Bonds With Venom"). oOqA, the only low in a comparable pair, opens on mood ("on a lonely path"), an empty first frame and the least saturated palette.
- The only two videos that put the title **on screen as large type** are both GiyeSears (7k/15k); this is not a high/low contrast.
- The edit is the shared **entry ticket** of the niche, not what decides which video wins. It is what phase 2 should compare against.

## 4. House templates

- **Comic_Escape**: full-bleed crops of whole pages with continuous pans; one green word at a time mid-frame; "COMIC ESCAPE" watermark at the bottom; subscribe-button pop-ups mid-video; about 3 images per 10 s; −18 LUFS.
- **ComicCandid**: fast pan/zoom across full-bleed panels (at the 55 %/s cap) with extreme face close-ups; 2-3 white bold words centred; "COMIC CANDID" top-right; −19 LUFS; about 45 s.
- **ComicsUnlocked**: the strongest single image (cover/splash) at t=0; one white word centred; faint watermark; quietest of the set (−22/−24 LUFS); 38-48 s.
- **comiczyt**: a 0.13 s glitch intro, whip/spin-blur transitions about every 2 s, big colour-coded 1-2 word captions, loud (−14 LUFS, peaks above 0 dBTP), long (95-172 s), no watermark.
- **GiyeSears**: the title as huge yellow comic type within 3 s; animated-series clips mixed with tilted panel cards over streaky blurred backgrounds; an image change every 1.0 s; comic-italic captions with a highlighted keyword in the lower third.

## 5. Phase-2 checklist (compare each item with the competitor median or range)

1. Published file analysed (CapCut captions + mascot present), proxied to 360p.
2. `first_image_change_s` ≤ 2 (median 0.78) and `image_changes_first_3s` ≥ 1.
3. `median_image_hold_s` ≤ about 2.4 (median 1.88; range 1.0-2.9).
4. `speed_bm_median` > 4.6, meaning visible motion rather than a sub-pixel Ken Burns push (median 30; lowest 4.6; a synthetic 1.10 push reads 0).
5. `sharp art` ≥ 0.9 (8 of 10 are ≥0.92). If it is about 0.5, are the blurred bands animated like GiyeSears or static?
6. `LUFS` between −14 and −24 (median −18.1); `floor dB` > −43 (a bed under the pauses); `1st sound s` = 0.
7. `wps` around 3.5 and about 10 words in the first 3 s.
8. t=0 frame: one big recognisable A-tier subject, no empty or dark wide shot (look at `hooks_all`).
9. A caption visible by 0.5 s; 1-3 words; centred; size and stroke compared with the sheets.
10. Title on screen as large type in the first second? Only GiyeSears does this. Is ours missing, small, or present?
11. Ending: loop (`loop r` > 0.4), cliffhanger, or a flat stop?
12. Mascot: area, position, and whether it covers art or captions (compare with GiyeSears's content-linked sticker).
13. Saturation ≥ about 0.35 (median 0.40).
