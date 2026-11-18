# R9 - Openings and chapter marks in real, human-edited art videos

Question: what do openings and chapter marks look like in videos cut by a human editor, what makes them read as "video" and not as "a slide", and which treatments can "Raking Light" use that are its own?

How to read this report. Every claim carries one of three tags.
- **[frame]** I saw it in extracted frames, or measured it from the video file (time codes and file names given).
- **[read]** I read it on a web page (URL given).
- **[infer]** My reasoning from the above. Not verified.

All frame numbers are for 1280x720 sources. Percentages are of frame height (H) or width (W). "Cap height" is the height of a capital letter (top of T or L to the baseline), measured by thresholding white pixels and reading the row profile. At 1080p multiply cap % by 10.8 to get pixels.

Working files: `.scratch/d13_research/` (contact sheets in `sheets/`, OCR logs in `ocr/`, measuring scripts in `tools/`). Other channels' segments are in `research_media/other/` (first 120 s each, git-ignored). All times are in seconds from the start of the file unless written m:ss.

---

## 0. Summary of what the frames show

1. In every GAE video from 2021 to 2026 (nine measured) there is **no title card for the painting**. The film opens cold on the picture, which is already moving. The painting's name appears as a small two-line label (title in italic, then artist and year) 6 to 16 s in, over the moving picture, with no box.
2. The thing that works as "the opening title" is a **5 s brand sting** ("GREAT ART EXPLAINED" in translucent letters over a filmed close-up of The Starry Night). It comes after a hook of 67 to 184 s and is followed at once, by a hard cut, by chapter mark 1.
3. A **chapter mark** (2021 to 2026) is: a hard cut to a heavily defocused version of the first picture of the next chapter, one line of small centred text "N. Title" on it, 3.0 to 3.6 s long, then the picture snaps sharp. The narration stops 0 to 1.5 s before the cut (median about 1 s) and comes back as the picture sharpens. Music only in between.
4. The same template was used for six years with only the typeface changing (sans caps in 2021-22, a Times-like serif in title case from 2023). In 2020 the chapter marks were different (white card, black card, lower-third strips) and the sting was a different one ("GREAT PAINTINGS EXPLAINED" over a Rothko).
5. The other makers I looked at (two TV series, a museum talk, a museum-education film, a cinema trailer, two essayists) all put titles **on the picture or on live footage**, in small type, with fades, and with sound doing part of the work. None of them uses a panel, a label card with a shadow, or a coloured ground, except the museum's plain black card and the cinema trailer's big gold type.

The rejected mock-ups break most of these. Section 3.3 goes trait by trait.

---

## 1. The reference channel, measured from frames

### 1.1 What I measured

Eleven full-length videos, spread over the channel's years. I built contact sheets (1 fps, first 120 s, 6x5 tiles with time codes) for all of them, ran text recognition (macOS Vision, `tools/ocr`) on every second of every video to find every chapter mark, and then built 4 fps sheets and frame-by-frame difference/blur/text curves around chapter marks and the sting. Audio level was measured as RMS dBFS per 0.25 or 0.5 s window with ffmpeg (`tools/audio.py`).

| Short name | File | Uploaded | Length |
|---|---|---|---|
| 2020 Guernica | `qJLH7JAsBHA.mp4` | 2020-06-16 | 821 s |
| 2020 Arnolfini | `T15Kv6dtYO0.mp4` | 2020-08-30 | 940 s |
| 2021 Kiss | `SNhmSdLDmto.mp4` | 2021-10-05 | 911 s |
| 2022 Scream | `d50FbuyswAU.mp4` | 2022-05-20 | 983 s |
| 2023 O'Keeffe | `83ggxS21mFM.mp4` | 2023-04-15 | 965 s |
| 2024 Wanderer | `c3NmCvrUYUA.mp4` (59.94 fps) | 2024-01-05 | 907 s |
| 2025a Velasco | `3wfWuVne0LU.mp4` | 2025-03-21 | 886 s |
| 2025b Napoleon | `Bgo6H0tzszA.mp4` | 2025-10-26 | 1405 s |
| 2026a Potato Eaters | `2zfjf4uD94s.mp4` | 2026-01-14 | 1242 s |
| 2026b Ambassadors | `ceKSyMJjniU.mp4` | 2026-09-01 | 1648 s |
| 2026c Matisse | `unla1jTwXdY.mp4` | 2026-10-17 | 1492 s |

Deviation from the task text: I did not build a 2 fps sheet for every one of the first 120 s. I used 1 fps for the 120 s (enough to find the events) and 4 fps for the events themselves. The YouTube chapter lists in the `.info.json` files for 2021 onward are machine-made and do not match the burned-in marks by title; they are ignored. Chapter marks were found by reading the pixels.

### 1.2 Opening: what comes before the title, and the title itself

"Sting" = the brand shot. "Label" = the small two-line name tag of the painting. The sting time is when the Starry Night shot begins; I aligned it to the 2024 file by cross-correlating 8 s of frames (`tools/alignsting.py`; error about +-0.3 s).

| Video | Before the sting (what the screen shows) [frame] | First label of the painting [frame] | Sting shot starts | Chapter 1 cut |
|---|---|---|---|---|
| 2020 Guernica | 0-21 s archive film of Picasso signing; 22-40 montage of paintings, name captions bottom centre in caps; | caps captions bottom centre, 0:22-0:41 | "GREAT PAINTINGS EXPLAINED" over a Rothko, 0:44-0:47 (older sting, see 1.3) | no numbered mark; white card "THE COMMISSION" 1:42 |
| 2020 Arnolfini | 0-35 s painting on a black matte, pull-back; 35-48 montage with 3D tilt and captions | caption "JAN VAN EYCK WAS HERE" after sting | Rothko sting 0:51.0-0:54.0, hard cut 0:54.2 | lower-third strips (see 1.4) |
| 2021 Kiss | 0-87 s cold open: close-up of the Kiss, long pull-back; hook montage 1:13-1:27 (Wave, Marilyn, Mona Lisa, Frida) | 0:06-0:10, top left, caps "THE KISS / GUSTAV KLIMT, 1907"; music credit top right 0:51-0:54 "SYMPHONY NO.5 / GUSTAV MAHLER, 1901" | 87.5 s | 93 s ("1 VIENNA") |
| 2022 Scream | 0-48 s on the Scream (slow push); 49-67 montage (Wave, Marilyn, Mona Lisa, Dali, Frida) | 0:16-0:20 bottom left, italic "The Scream / Edvard Munch, 1893" | 67.4 s | 72.0 s |
| 2023 O'Keeffe | 0-28 s silent-film footage of the artist; 28-62 the painting; montage 1:00-1:08 | 0:32-0:36 bottom left, italic | 68.9 s | 73.8 s |
| 2024 Wanderer | 0-44 s push through the painting; 44-52 perspective rays drawn over it; 53-60 two other Friedrich paintings (labels); montage 1:25-1:38 | none found for the Wanderer itself in 0-50 s; labels for other works from 0:53 | 99.5 s | 104.4 s |
| 2025a Velasco | 0-4 s photograph of the artist; 4-11 s collage of paintings assembling; 12 s landscape | 0:13-0:17 bottom left | 131.4 s | 136.4 s |
| 2025b Napoleon | 0-30 s ad for the channel's book (reviews over page turns) | n/a | 183.6 s | 188.5 s |
| 2026a Potato Eaters | 0-11 s sponsor card and web page; then cold open on a van Gogh | 0:17-0:20 bottom left | 148.1 s | 153.0 s |
| 2026b Ambassadors | film clips with credit lines (0:14); | credit lines top/bottom left | 105.7 s | 110.7 s |
| 2026c Matisse | 0-10 s book ad; 0:10 cold open | 0:10-0:14 bottom left | 143.4 s | 148.4 s |

What is the same in 2021-2026: the film starts on the picture or on archive footage, not on a title; the label sits at the left margin at x = 4.0 to 4.3 % (52 to 55 px) of W, block top at 83.9 to 85.1 % of H and bottom at 91.0 to 92.8 % of H (measured on 2022, 2023, 2026c: two lines together, 7.2 to 7.8 % of H, so each line has a cap height of about 2.3 %); it is on screen about 4 s (about 1 s fade in, 2-3 s hold, under 1 s fade out; read from 1 fps sheets, +-0.5 s); there is no box, strip or rule around it. The sting is preceded by a hook montage of the same sequence of paintings (Wave, Marilyn, Mona Lisa details, Frida, then Starry Night); the sting is the same asset in every video (the 2026 Ambassadors file matches the 2024 sting frame with mean squared error 1 on 96x54 grey frames, 2024 `c3NmCvrUYUA.mp4` 102.5 s vs 2026 `ceKSyMJjniU.mp4` 109.0 s).

What changed: the label moved from top-left caps (2021) to bottom-left italic title plus plain artist line (2022 onward). The hook before the sting got longer: 67 s (2022), 69 s, 88 s, 99 s, 131 s, 148 s, 143 s, 106 s, 184 s. Several 2025-26 films start with an advert (book, sponsor) before the cold open.

Where this contradicts or sharpens R3 (`docs/design/research/R3_style_inventory.md`): R3's `X-CARD-02` "Main title card ... centred over a blurred, darkened image" has no counterpart in the 2021-26 frames. GAE does not show the painting's name on a card. R3 records that "the channel opens cold on the image and puts the title card after the hook". What I see after the hook is the brand sting, not a card with title, artist and year.

### 1.3 The sting (the nearest thing to a title)

**2021-2026 sting** (`c3NmCvrUYUA.mp4` 99.5 to 104.45 s; sheets `c3Nm_sting_4fps.jpg`, `c3Nm_sting_emerge.jpg`) [frame]:
- It is one filmed shot of the Starry Night surface, about 4.95 s, ending in a **hard cut** to chapter mark 1 at 104.45 s.
- The letters are lit like a relief: translucent light-grey (looks like 60-70 % opacity), with the paint texture visible through them, set in perspective. At 99.5 s the end of "EXPLAINED" is at the top edge. The camera tilts up from the village to the sky; the letters sweep down into a flat, readable position by about 101.5 s and hold to 104.45 s (about 3 s).
- Letters: wide-tracked light sans capitals, two lines, a thin rule between the lines. "GREAT ART" caps about 70 px tall (9.7 % of H), "EXPLAINED" about 80 px (11 %); text block spans x = 26 to 76 % of W, y = 24 to 55 % of H (centre about 40 % of H), centred horizontally at about 51 %.
- The text is a 3D-tracked element on a filmed 3D shot. A 2D engine cannot copy it exactly. [infer] A 2D version would be a still with a tilt-like vertical pan and the text drawn flat on top.
- Sound: narration is silent about 6 s (2024: -12 to -14 dBFS before 101.5 s, -26 to -34 dBFS from 101.5 to 107.5 s, voice back at 107.5 s, three seconds into chapter 1). 2023: music only 66 to 75.5 s, voice back at 76.0 s (2.2 s after the chapter 1 cut at 73.85 s). 2026c: music only 141 to 151 s, voice at 151.5 s.

**2020 sting** (`T15Kv6dtYO0.mp4` 0:51.0 to 0:54.2; sheet `T15K_sting2020_4fps.jpg`) [frame]:
- Static Rothko still (no camera move seen) with a small caps caption "UNTITLED" at the bottom (0:48 to 0:50.75, cap about 5 %).
- 0:51.0 to 0:51.5: a thin rule (2 px) draws outward from the centre. 0:51.5: "GREAT PAINTINGS" fades in (about 0.5 s), 0:51.75 to 0:52.25: "EXPLAINED" fades in under the rule. Hold to 0:53.5, fade out 0:53.5 to 0:54.0, hard cut at 0:54.2.
- Thin geometric sans capitals, wide tracking, white, line 1 cap about 7.6 % of H (y 39.9 to 47.5 %), line 2 cap about 7-10 %, y 54.7 to 64.4 %, x 28 to 72 %.
- Narration: music level about -22 dBFS under, no pause detected at this point (`audio.py` 44-58 s, one-second windows; the voice is not separated from the music by this method).

### 1.4 Chapter marks

Every second of each video was read for text; a chapter mark is a centred line matching "N. Title". Counts are what 1 fps reading found (it can miss one: Velasco "3. Landscape" at 366 s and Matisse "2. A Kind of Paradise" at 244 s were found only by hand).

| Video | Marks | Times of the cut (s) | Look |
|---|---|---|---|
| 2020 Guernica | no numbers | topic words in caps lower centre ("PARIS" 2:00, "MATERIALS" 2:50); white card "THE COMMISSION" 1:42.0-1:44.0 | see below |
| 2020 Arnolfini | no numbers | lower-third strips ("BRUGES" 1:07.75 for 4+ s); black card "FASHIONS AND FABRICS" 2:59.25-3:01.25 | see below |
| 2021 Kiss | 4 numbered (+3 date captions) | 93, 121, 257, 819 | bold sans caps, 0.75 s cross-dissolve into a blurred picture |
| 2022 Scream | 5 | 72, 206, 356, 498, 909 | sans caps, hard cut to blurred footage |
| 2023 O'Keeffe | 8 | 74, 137, 222, 297, 434, 496, 639, 880 | Times-like title case, hard cut to blurred picture |
| 2024 Wanderer | 7 | 104, 228, 406, 499, 611, 729, 824 | same |
| 2025a Velasco | 5 | 136, 225, 366, 506, 808 | same |
| 2025b Napoleon | 9 | 189, 338, 440, 551, 664, 838, 931, 989, 1307 | same |
| 2026a Potato Eaters | 6 | 153, 337, 438, 574, 650, 1024 | same |
| 2026b Ambassadors | 10 | 111, 271, 388, 468, 612, 859, 1010, 1199, 1368, 1456 | same |
| 2026c Matisse | 8 | 148, 244, 398, 510, 616, 717, 1171, 1364 | same |

Gap between marks: 58 to 454 s; the typical gap is 100 to 150 s. A 15 to 25 minute film carries 4 to 10 marks. Smaller on-screen captions (dates "13 YEARS BEFORE THE KISS" at 481 s of the Kiss, place names "Christiania (now Oslo)" 76 s of the Scream, film credits) run over the footage and are not marks.

**Measured per mark (2021 onward)** [frame], from `tools/chapsum.py`, `tools/chapt.py`, `tools/measure_chapter.py`:

| Mark | File | Cut at (s) | Text starts after cut | Text full after cut | Text fading from / gone | Picture sharp again | Voice quiet (RMS < about -30 dBFS) | Cap height |
|---|---|---|---|---|---|---|---|---|
| 2021 "3. THE KISS" | SNhm | dissolve 256.5-257.5 | about 0.75 | about 1.0 | 259.75 | 260.0 | 256.0-259.0 | 34 px = 4.7 % |
| 2022 "2. PARIS" | d50F | 206.134 | 0.17 | 0.30 | 208.90 / 209.00 | 209.70 (+3.57) | 205.5-208.5 | 34 px = 4.7 % |
| 2023 "3. Stieglitz" | 83gg | 221.767 | 0.07 | about 0.3 | about 224.5 | about 224.5 (+2.8) | 221.0-224.0 | 29 px = 4.0 % |
| 2024 "3. The Sublime..." | c3Nm | 406.318 | 0.08 | 0.37 | 408.64 / 409.24 | 409.27-409.40 (+3.08) | 405.0-408.5 | 33-36 px = 4.6-5.0 % |
| 2025a "3. Landscape" | 3wfW | 365.634 | 0.13 | 0.40 | 368.37 | 368.50 (+2.87) | 364.5-368.5 | 31 px = 4.3 % |
| 2025b "3. Caravaggio" | Bgo6 | 439.534 | 0.10 | about 0.4 | about 442.4 | about 442.5 (+3.0) | 438.5-442.5 | 31 px = 4.3 % |
| 2026a "2. Christ of the Coal Mine" | 2zfj | 438.369 | 0.20 | 0.57 | 440.84 / 441.21 | about 441.3 | 439.0-441.5 | 31 px = 4.3 % |
| 2026c "3. The Wild Beasts" | unla | 398.0 | 0.17 | 0.33 | 400.64 | not measured | not measured | 33 px = 4.6 % |

(Where a column says "about", it was read from the 4 fps sheet, +-0.25 s.)

Numbers from these rows:
- Whole mark, cut to sharp picture: **2.8 to 3.6 s** (median about 3.1 s, 87 to 107 frames at 30 fps). Text on screen: 2.6 to 3.0 s.
- Text fade in: starts 0.07 to 0.20 s after the cut, full at 0.30 to 0.57 s (a fade of about 0.2 to 0.4 s). Fade out 0.15 to 0.6 s. In the 2024 file the text fades out over 0.6 s and the picture is then released.
- Text is never slid, typed or scaled. Position **never moves**. Centre of the text block: x = 49.3 to 50.1 % of W (first-pass readings of 45 % and 60 % came from bands that caught bright picture pixels and were re-measured on a narrower band), cap band 47.9 to 52.1 % of H (centre 50.0 %). Baseline at 52.1 %.
- Cap height 4.0 to 4.7 % of H (29 to 34 px at 720p; median 31 px = 4.3 %). Width of the line depends on the words: 14 % (3 words "Stieglitz") to 43 % of W.
- No box, rule, underline, shadow card, logo or background panel. The text is a plain white line directly on the picture; I did not look for a faint drop shadow (the frames show text on a blurred, dark-to-mid picture; a shadow is not needed there).
- Type: 2021-22 white bold sans capitals "2. PARIS", "3. THE KISS", slight tracking. 2023 onward a Times-like (Times New Roman look) roman in title case, **normal tracking**, "1. The German Landscape". The same typeface for the number and the words. I did not identify an exact font.
- The picture behind the text is the first picture of the *next* chapter, **defocused** (the image has lost nearly all detail: Laplacian variance of the picture region 1.4 to 3.0 against 250 to 2700 once sharp). 2022-2026: a hard cut into the blurred picture. 2021: a 0.75 s dissolve from the previous picture to the blurred one (4:16.5 to 4:17.5, `SNhm_chap3_4fps.jpg`). The blur is released in 0.15 to 0.7 s: 2024 in 9 frames at 59.94 fps (409.27 to 409.40 s); 2022 over 209.5 to 209.8 s. The release starts only after the text has gone.
- The picture under a mark is often a still that is **not moving** (2022 Paris, 2024 Sublime) and sometimes footage that moves (2024 chapter 1, drone footage). The blurred state itself is the "motion" of the mark: it ends in a focus pull.
- **Sound.** The voice stops 0 to 1.5 s before the cut, median about 1 s (2022: -15 dBFS at 205.0 s, -32 dBFS at 205.5 s, cut at 206.13 s, so 0.6 s; 2024: quiet from 405.0 s, cut 406.32 s, so 1.3 s; 2025a 364.5 vs 365.63; 2025b 438.5 vs 439.53; 2026a about 0) and returns as the text fades or the picture sharpens (2022: -22 dBFS at 208.5 s, -12 dBFS at 209.0 s). Under the mark the level is -30 to -37 dBFS (2021: -46 to -55 dBFS, almost silence), so a music bed 15 to 20 dB under the voice (voice -12 to -19 dBFS). The quiet span is 3.0 to 4.0 s. Exception: the first mark in 2022 (72 s): the voice starts 0.4 s after the cut and talks under the title.
- Several frames of the first mark of each file are followed by a label for the first picture (bottom left), so a mark and a label may follow each other within 3 s (2024: label "Hermannsdenkmal / Ernst von Bandel, 1875" at 107-111 s).

**2020 marks** [frame]:
- 2020 Guernica, 1:42.0-1:44.0 (`qJLH_chap_100_4fps.jpg`): a hard cut from the painting to a pure white frame; small grey caps "THE COMMISSION" at 85.6 to 88.5 % of H (cap about 3 %), x 30 to 70 %, fade in 0.25 s, fade out 0.25 s; hard cut at 1:44.0 to AP news footage. About 2 s.
- 2020 Arnolfini, 2:59.25-3:01.25 (`T15K_chap_fashions_4fps.jpg`): hard cut to a black frame; "FASHIONS AND FABRICS" in small grey-white caps at 85.4 to 90.6 % of H, x 24.1 to 76.1 % of W (52 % wide), fade in 0.25 s and out 0.25 s, hard cut to the next picture. About 2.0 s. R3 gives this card a width of about 35 % of W; I measure 52 %. The position (about 88 % of H) agrees with R3.
- 2020 Arnolfini lower-third strips (`T15K_bruges_4fps.jpg`, 1:07.75): a dark translucent strip across the bottom of the footage with small caps "BRUGES" at the left; stays 4 s or more while the footage runs. The film has 39 such labels (YouTube list) and no numbers.

### 1.5 Moving picture behind the type

Measured with feature matching between frames 4 s apart (`tools/camrate.py`), cold-open segments: zoom changes of 0.2 to 5 % per second (median across files about 2.4 %/s; Scream push 1.4 %/s, O'Keeffe 2.4 %/s, Wanderer 1.0 to 2.5 %/s, Velasco 0.4 %/s), centre drift of 0.05 to 1.7 % of the frame per second (median about 0.9 %/s). These are slow: a person does not see a move, they feel the picture breathe. [frame]

### 1.6 What is the same, what changed

Same in all of 2021-2026: no title card for the painting; label bottom left, no box; brand sting 5 s followed by a hard cut into mark 1; numbered marks, one centred line at 50 % of H, cap about 4.3 %; defocused next picture; 3 s; narration pause with a music bed.

Changed: 2020 white card, black card, lower-third strips and the Rothko sting; 2021 sans caps, 0.75 s dissolve in, top-left label; 2022 sans caps, hard cut; from 2023 the serif title case; hook length 67 to 184 s; ads in front from 2025.

---

## 2. Other human-edited work, for contrast

Evidence is my own first 120 s of each (`research_media/other/<id>.webm`, `.info.json` beside it) and the sheets named below, unless marked [read]. I did not see chapter marks beyond 120 s in any of them, so chapter marks are only reported where one fell inside 120 s.

| # | Maker, file | Opening title [frame] | Chapter mark or section mark [frame] | What it teaches |
|---|---|---|---|---|
| 1 | **Nerdwriter1**, "The Death of Socrates: How To Read A Painting" (2015), `rKhfFBbVtFg.webm`, sheets `other_rKhfFBbVtFg_open60_1fps_1.jpg` | 0-2.9 s the channel's animated cup logo; fade to black; 4.0 s "Understanding Art" fades in (1.5 s) over a **dimmed** painting; 5.5 s "CASE STUDY:" (small caps); 7.0 s "The Death of Socrates" in pale yellow; "JACQUES-LOUIS DAVID" small caps under it; all fade out 10.5-11.0 s. Four lines, stacked, centred, y = 24-70 % of H, painting at about 25-30 % brightness [infer from tiles] and static | 0:17-0:22 a date "1787" at cap about 11 % of H over the picture, then "NEOCLASSICAL" in small caps beneath it from 0:20; no cards in the first 120 s | Titles staggered line by line (each one 1.5 s apart), over a dimmed picture; a big date as a mark |
| 2 | **Smarthistory** (Khan Academy), "Rembrandt, The Night Watch" (2015), `0D_rc92g27w.webm`, sheet `other_0D_rc92g27w_open60_1fps_1.jpg` | 0-2 s Khan logo; 2-4 s series badge on black with one small line "A conversation with Dr. Steven Zucker and Dr. Beth Harris"; 4-18 s a filmed wide shot of the gallery with the painting lit on the wall; 18-19 s to black; 19-23 s the flat painting grows from about 25 % to 100 % of the frame; left-column caption in plain lower-case ("a group portrait of a militia company") and a source line bottom left | none in 120 s | The quietest model: tiny plain text, filmed room, no animation of the type |
| 3 | **The National Gallery**, "Turner: Painting The Fighting Temeraire" (2016), `8O-fna8HrWw.webm` | 0-2.5 s black card, three lines of plain left-set text ("Turner / 'The Fighting Temeraire' / #NGYouChoose") that fades; filmed talk; lower-third speaker name bottom right 6-12 s | none | A museum's own black card: plain and slide-like, but only 2.5 s long and followed at once by live footage |
| 4 | **Still Mind Gallery**, "The Night Watch Was Never Night" (2026-11), `KS1L6xlUFcE.webm`, sheets `other_KS1L6xlUFcE_open60_1fps_2.jpg`, `other_KS1L6xlUFcE_96-120_2fps.jpg` | 0-31 s no title: close-up push on the painting, a small dark caps tag "SHADOW" pinned to a figure (0:21-0:31). 0:32-0:41 (9 s): the picture steps back and darkens (vignette), then "The Night Watch" (serif, cap about 4.5 % of H) at y = 70-79 % and a wide-tracked small-caps line "REMBRANDT VAN RIJN, 1642 - RIJKSMUSEUM, AMSTERDAM" (cap about 2 %) at 80-83 %, centred, fade in about 1 s, fade out about 1 s. 0:46-0:56: the same text reduced to a three-line label at the left edge (x about 5 %, y 80-90 %) | **1:45-1:49**: the picture darkens (to about 40 % brightness [infer from tiles]) and a small serif "The order" appears at the centre of the picture for about 3 s, then the picture brightens and tiny name tags ("BENNINCK COCQ") pin themselves to figures. No card, no cut; the picture keeps moving | A chapter mark as *text over the continuing picture, dimmed*. Closest in spirit to GAE yet different in method (dim instead of defocus) |
| 5 | **BBC "Great Paintings of the World with Andrew Marr"** (Banijay Art upload), `qc530RtZTUg.webm`, sheets `other_qc530RtZTUg_open60_1fps_2.jpg`, `other_qc530RtZTUg_60-120_1p5s.jpg` | Cold open of **92 s**: filmed gallery montage, presenter, experts; at 1:32.5-1:36 a three-line caps title "GREAT PAINTINGS / OF THE WORLD / WITH ANDREW MARR", cap about 6-7 % of H, centred at y = 35-65 %, composited *as a reflection on a shop window* of the Rijksmuseum entrance; 1:36.5-1:40: "THE NIGHT WATCH" in wide-tracked grey-white caps, centred, cap about 6 %, over the painting (which keeps moving); hard cut to Amsterdam street footage | none in 120 s | Title as an element *in the filmed world*; episode title faint and wide-tracked over the painting |
| 6 | **BBC "Civilisations"** (2018) "Colour and Light", as re-uploaded by a TV channel with Spanish subtitles and its logo (`Urm9xlklrOk.mkv`; the rip is a caveat, the titles are the BBC's), sheets `other_Urm9xlklrOk_open60_1fps_1.jpg`, `other_Urm9xlklrOk_60-120_1p5s.jpg` | 0-58 s cold open (cathedral rose window, pigment, hands, Hokusai, Titian). 1:00-1:25 (25 s) title sequence: letters of "CIVILISATIONS" **cut out of black like windows**, with artworks (Egyptian bust, Greek vase, sunflowers) moving inside them; resolves at 1:19 to small wide-tracked caps over a bust (cap about 4 % of H, x 17-82 %); 1:27-1:33 episode title "COLOR AND LIGHT" in two lines, centred at y about 45-55 %, grey-white and translucent, over a wide shot of Amiens cathedral; 1:34-1:38 "Narrated by LIEV SCHREIBER" lower third; 1:39-1:42 place caption bottom left "Amiens Cathedral, France" | none in 120 s | The most designed. Letters as masks over art. Place name as a bottom-left caption |
| 7 | **"Gauguin from the National Gallery" cinema trailer** (More2Screen), `zcl--Grwjws.webm`, sheet `other_zcl--Grwjws_open60_1fps_1.jpg` | 60 s trailer. Gold condensed caps (cap about 9-12 % of H) laid over slowly moving close-ups of paint: "GAUGUIN" with small white "From the National Gallery, London" at 0:08.5-0:11.5; each message 2-3 s; also kinetic text at 0:12-0:28 | none | Loud promotional type, a different job from the film itself |
| 8 | **Jacob Geller**, "Art in the Pre-Apocalypse" (2023), `O9N7Awpk9lE.webm` | 0-10.5 s a content-warning list in the top right over a game still, then game footage; no title | not in the first 120 s | Not an art-film opening: no use as a model, listed for completeness |

Also read: the Ravensbourne "BBC motion graphics archive" page for the 1969 *Civilisation* says the titles "were superimposed over live action shots" suited to each episode's location and that the designer "filmed top-lit and back-lit captions on a rostrum camera" [read: https://ravensbourne.ac.uk/bbc-motion-graphics-archive/civilisation-1969]. That is the oldest case of "title on the footage, lit". Searches for an Art of the Title page on the 2018 *Civilisations*, on Exhibition on Screen, or on a title-design article on art documentaries found no page on them [read: web search, no usable result]. I did not find a title-design article that would add measurements, so Part 3 rests on frames only.

What I could not verify for the others: chapter marks beyond 120 s; whether the BBC uploads were cut or re-timed by the uploader; sound levels (I did not measure them for the others).

---

## 3. What separates "edited video" from "slide"

### 3.1 Checked statements

Each statement from the task, verified or refuted. "n" is the number of GAE videos from 2021 to 2026 measured (8 with numbered marks).

| Statement | Verdict | Evidence |
|---|---|---|
| The title is set over the picture itself, never on a panel or card | **Mostly true.** Marks 2021-26 (8/8) and all labels: no panel, no box. Exceptions: GAE 2020 white and black card (2 s each, hard cut), the National Gallery's black card (2.5 s), the Smarthistory badge card (2 s) | 1.4, section 2 |
| The picture behind the title is always moving | **Refined.** Behind the sting, the camera tilts about 2 s then drifts; behind labels the picture moves 1-3 %/s zoom, about 0.9 %W/s drift; behind marks the picture is *defocused then released*, not always moving (2022 Paris and 2024 Sublime are stills) | 1.3, 1.4, 1.5 |
| Title text is smaller than X % of frame height | **True for marks and labels:** marks cap 4.0-4.7 % (median 4.3 %), label lines 2.3 %; BBC and Still Mind titles 4.5-7 %. **False for the sting:** cap about 10 %, and for Nerdwriter's date "1787" (about 11 %) | 1.3, 1.4, 1.2, section 2 |
| Nothing is boxed, ruled or underlined | **True for marks, labels and Still Mind/BBC titles.** Refuted for GAE's 2020 sting and the 2021-26 sting (a thin rule between the two lines) and for Still Mind's small caps tag "SHADOW" (a small dark pill on a figure) | 1.3, section 2 |
| The title appears N seconds into the film, after a cold open | **True.** The painting's label 6-16 s in (4 of 6 files measured); the brand sting 67-184 s in (hook 1-3 min); BBC Marr 92 s; Civilisations 60 s; Nerdwriter and Smarthistory 4 s (after a logo) | 1.2, section 2 |
| Chapter marks last under N frames | **They last 87-107 frames at 30 fps (2.8-3.6 s).** Not shorter | 1.4 |
| Type arrives by a fade of N frames, never by a slide | **True for fade in GAE:** 0.2-0.4 s (6-12 frames at 30 fps); text full at 0.30-0.57 s. Never a slide, never typed. Nerdwriter staggers four lines by 1.5 s each with 1-1.5 s fades. Exception in section 2: Civilisations letters as windows (motion design) and the Gauguin trailer | 1.4, section 2 |

### 3.2 The concrete traits (checkable)

T1. **The text sits on the picture.** Centre 49.3-50.1 % of W, cap band 47.9-52.1 % of H (marks); label block at x = 4.0-4.3 % left margin. Nothing else is on screen: no logo, no number graphic beside it.

T2. **One line, one face, one size per mark.** Cap 4.0-4.7 % of H. 14-43 % of W. Number and words together ("5. The Potato Eaters"), no second line, no kicker, no sub-title.

T3. **The ground is the next picture, in a changed state.** Defocused (2021-2026 GAE), dimmed (Still Mind, Nerdwriter), seen through glass (BBC Marr). Never a flat colour, never a gradient panel, never white (except the 2020 card).

T4. **The mark is part of an edit, not an object.** A hard cut in (frame-exact), and a release (focus snap in 0.15-0.7 s) out. The text appears 0.07-0.2 s *after* the cut so the cut is seen first.

T5. **Time.** 2.8-3.6 s per mark. Text on 2.6-3.0 s. Fades 0.2-0.6 s. Marks every 100-150 s.

T6. **Sound carries half of it.** Voice stops 0 to 1.5 s before the cut (median about 1 s), music only for 3-4 s (15-20 dB under the voice, or silence in 2021), voice returns with the release. A silent video of a mark would look like a still image with text; the sound makes it a beat in the film.

T7. **The film does not start with a title.** Cold open on a moving picture; the label comes 6-16 s in; the brand comes after a hook of 1-3 min and is followed at once by chapter 1.

T8. **Hierarchy is small.** Only one thing is large: the brand sting (cap 10 %). The painting's name is small (2.3 %). The mark is 4.3 %. Dates are big only as annotations ("1787").

T9. **The text is not drawn, it appears in a world.** Examples: letters lit like relief in the Starry shot; text reflected in a window (BBC Marr); letters as windows (Civilisations). In GAE 2021-26 marks the "world" is the defocused picture.

### 3.3 Where my three rejected mock-ups break these traits

Screenshots used: `scratchpad/d13/shot-a.png`, `shot-b.png`, `shot-c.png` (mock-up page `identity.html`). The page contains no animation (no `@keyframes`, no `animation:` property), so none of the time-based traits T4-T7 can be satisfied by a still and the page reads as a slide for that reason alone. Sizes below are my estimates from the screenshots (tile about 535 x 300 px), +-20 %.

| Trait | A "light streak" (dark) | B "museum label" (light wall) | C "poster" (blocks) |
|---|---|---|---|
| T1 text on the picture | **Breaks.** The painting is a framed rectangle on the left (about 90 % of H) and the text sits on a dark panel beside it. The chapter card has no picture at all, only dark ground and a "V" | **Breaks.** A white label card with shadow, rule and footer ("RAKING LIGHT, NO. 01") beside a framed picture. The chapter card is a white box beside a framed thumbnail | **Breaks.** A solid green block (about 45 % of W) holds the text, the painting is cut to the other half. Chapter: red ground, no picture |
| T2 one line, one size | **Breaks.** Four tiers on the opening (kicker "RAKING LIGHT", two-line title about 7 % cap, a rule, artist-year italic); chapter has kicker "CHAPTER FIVE", title about 10 % cap, ghost numeral "V" about 40 % of H | **Breaks.** Six tiers in the label (artist, dates, title, year, medium and place, footer line) plus rule; chapter has kicker, title with a green rule | **Breaks.** Number badge "01", three-line condensed title, small caption; chapter has "CHAPTER", title, giant ghost "05" (about 55 % of H) |
| T3 ground is the next picture | **Breaks (chapter).** Chapter ground is a dark gradient with a static diagonal streak | **Breaks.** The ground is a flat light-grey wall with a soft sheen, in strong contrast to the dark painting | **Breaks.** Flat green and flat red |
| T3 boxed/ruled | **Breaks.** A gold hairline under the title; thin gold frame around the picture; a kicker in a box on the detail label ("THE CONVEX MIRROR" in an outlined box) | **Breaks.** Card, drop shadow, rules, green square bullet | **Breaks.** A solid red box behind "MIRROR?" and behind the number badge; heavy block label on the detail |
| T4 hard cut and release | Cannot be shown by a still | same | same |
| T5 time (3 s, marks every 100-150 s) | Not specified in the page | not specified | not specified |
| T6 sound | not specified | not specified | not specified |
| T7 no title at frame 0 | The opening is a full title card as the first thing | same | same |
| T8 one thing large | Breaks: title and ghost numeral large at once | Breaks: the label card is a second large object next to the picture | Breaks: everything is large, and the headline is condensed bold in caps (poster/thumbnail grammar) |
| Hides the painting | Partly (the chapter card shows none) | Partly (label covers the picture's lower right in the opening) | Yes: the painting is cut to a half and tinted by a block |

Reading: A is closest (dark, light, picture) but still arranges picture and text as separate objects; B and C turn the opening into a layout (museum wall, poster). The trait that decides "video" is time: the cut, the 0.2-0.4 s fade, the defocus release, and the voice dropping out. A treatment has to be judged as a clip with sound, not as a frame.

---

## 4. Candidate treatments for "Raking Light"

### 4.0 Common rules (from Part 3, applied to all six)

- Opening = a cold open on the moving painting (no title at 0), label at 6-12 s, and later the **brand beat** (a 4 to 5 s "RAKING LIGHT" moment after the hook, followed by a hard cut into chapter 1, as GAE does). I list the brand beat where it differs between the treatments. Brand-beat time is the end of the hook, 60-150 s in; set by the script, not fixed here.
- Chapter mark = 3.0 to 3.4 s, text 4.0-4.8 % cap height, one line "N. Title" (title case, number then words), no box, no rule beyond what is named, fade in 0.3 s starting 0.1 to 0.2 s after the cut, fade out 0.3-0.5 s.
- Sound: music bed from frame 0 (about -32 dBFS equivalent, 15-20 dB under the voice). Voice stops about 1 s before a mark (GAE range 0 to 1.5 s), returns as the mark ends. Brand beat: voice silent for its whole length (about 5 s).
- Frame coordinates are percentages of W and H. Time is from the first frame of the piece.
- Typeface: not the GAE serif (Times-like, centred at 50 %). For ours, an old-style serif with real italics, numerals lining, normal tracking in sentences, +10-12 % tracking in small caps. Position differs per treatment (below).
- Engine terms: *covered* = an existing technique does it; *new* = needs something that is not in `style/gae/techniques.json`. Existing parts used: CAM-01 Push-in, CAM-03 Pull-back, CAM-05 Zoom and shift, TR-01 Dissolve, HI-01 Spotlight (soft ellipse, floor 0.2, ramp 0.5, feather 0.55), X-HI-01 Dim to isolate, TXT-01 Chapter title on blurred image (title, blur_sigma, darken, fade_in_s, font_kind, size_px 84, tracking_px 14, y_pct, shadow), X-CARD-02 main title card (blur 30, darken 0.42, fade 0.35, 2.6 s), X-CARD-01 chapter card on black (text_in_delay 0.2, pop 0.1, leave 1.7, fade_out 0.15, y 88), STATIC-09 year over image (fade_in 0.2, fade_out 0.25), X-ANN-02 two-line artwork label, AN-01 circle draw, AN-05 dimension ruler.
- Note for the engine: `TXT-01` and `X-CARD-02` default to *wide* tracking (14 px at size 84) on a blurred, darkened picture. The 2023-26 GAE mark is normal-tracked title case. Set `tracking_px` to about 0-2 for anything modelled on GAE marks. `X-CARD-02` produces a title card that GAE does not use, so do not use it as the opening.

### Treatment 1. "Raking Pass" (the flagship: light that travels)

Idea: the lamp of the conservator, made literal. A narrow bright band of light crosses the painting from the side, and what it passes stays lit. Text is written *by the light*: letters become visible only after the band has crossed them.

**Opening (cold open, 0-11 s)**
| Time | On screen | Sound |
|---|---|---|
| 0.00-0.40 | Black. | Music bed starts at 0.00. |
| 0.40-1.20 | Painting (whole work or the chosen opening crop) fades up from black to 10 % brightness in 0.8 s; slow push-in begins (CAM-01, 2 % zoom per second, drift 0.9 % of W per second) and continues through the whole piece. | |
| 1.00 | | Voice starts the hook line. |
| 1.50-7.50 | A band of light enters at the right edge (x = 115 %) and travels left to x = -15 % in 6.0 s. Band width 14 % of W, edges feathered over about 40 % of the band width, leading edge tilted about 10 degrees from vertical. Inside the band the picture is at 100 %; the wake behind the band settles to 45 % over 1.5 s; ahead of the band it stays at 10 %. Optional: inside the band a micro-contrast boost (relief emphasis) to suggest raking light. | |
| 6.20-6.70 | The two-line label fades in bottom left (x = 4 %, block 84-92 % of H: title in italic about 3 % cap, artist and year 2.3 % cap) as the band's trailing edge leaves the left side. The band has been the "reveal" for the label. | |
| 7.50-9.00 | The whole picture rises from 45 % to 100 %. | |
| 10.20-10.70 | Label fades out. | |

**Brand beat (about 5 s, after the hook)**: the current picture dims to 12 % over 0.6 s; a band crosses left to right in 2.4 s (starts 0.6 s, ends 3.0 s); the word "RAKING LIGHT" (capitals, tracking about +25 %, cap about 8 % of H, centred at 42 % of H, light grey at 85 %) is revealed along the band's path and **stays visible** (the letter alpha is the maximum of the band mask over time, so the word is drawn left to right and remains). Hold 1.5 s. Hard cut at 5.0 s into chapter 1. Voice silent for 5 s.

**Chapter mark (3.2 s)**
| Time | On screen | Sound |
|---|---|---|
| -1.0 | | Voice stops. |
| 0.00 | Hard cut to the first picture of the chapter at 12 % brightness (already in its slow push). | |
| 0.10-2.10 | A band of light sweeps left to right in 2.0 s (width 18 % of W). The text "N. Title" (cap 4.5 %, centred at 50 % of H, same position as GAE so it reads as a mark) is revealed *by the band, left to right*, and then stays. Behind the band the picture rises from 12 % to 55 %. | |
| 2.10-2.50 | Hold. | |
| 2.50-3.20 | Picture rises to 100 % over 0.7 s; the text fades out over 0.4 s starting at 2.50 s. | Voice returns at 3.20 s on the full picture. |

Differs from GAE: no defocus; light replaces blur; text written by a moving edge instead of a fade. Obeys T1-T7 (the type is small, on the picture, one line, 3.2 s, voice gap).

Engine: *covered*: CAM-01 push, text style from TXT-01 (set tracking to 0-2), HI-01/X-HI-01 brightness floor and ramps, X-ANN-02 label. *New*: a "band light" overlay (a rotated soft-edged strip that multiplies brightness: position, width, feather, angle, speed, floor, wake level, keyframed), a text reveal that takes its alpha from the band's accumulated mask, and (optional) a relief/contrast boost inside the band. A band is a gradient mask times the image, which a 2D engine can do.

### Treatment 2. "Dim and Name" (the quiet one: Still Mind and Nerdwriter logic)

Idea: no cut, no card. The running picture dims and a line appears on it; the next picture arrives under the dim.

**Opening (0-12 s)**
| Time | On screen | Sound |
|---|---|---|
| 0.00 | Hard start on a detail of the painting at full brightness, pull-back begins (CAM-03, about 2.4 % of the frame per second, decelerating). | Music from 0.00; voice at 0.5 s. |
| 7.00-8.00 | Whole frame dims to 45 % (X-HI-01 without the ellipse: whole-frame floor 0.45, ramp 1.0 s). | |
| 7.20-8.00 | Title (italic, cap 5 %, white) fades in centred at 78 % of H, 0.8 s. Under it from 7.60 s the artist and year in small capitals (cap 2.2 %, tracking +12 %), 0.6 s, at 84 %. | |
| 8.00-11.00 | Hold. Picture keeps moving under the type. | |
| 11.00-12.00 | Type fades 1.0 s; the picture returns to 100 % over 1.0 s. | |

**Brand beat (4.0 s)**: picture dims to 25 % over 0.8 s; "RAKING LIGHT" (capitals, cap 7 %, tracking +25 %) at 46 % of H fades in 1.0 s, hold 2.0 s, fades out 0.6 s while a hard cut at 4.0 s goes to chapter 1. Voice silent.

**Chapter mark (3.0 s)**
| Time | On screen | Sound |
|---|---|---|
| -1.0 | | Voice stops. |
| 0.00-0.60 | The running picture dims to 40 % over 0.6 s. | |
| 0.20-0.60 | The next chapter's first picture starts to cross-dissolve in under the dim (TR-01, 0.75 s; GAE 2021 used exactly this length). | |
| 0.30-0.70 | "N. Title" fades in (cap 4.3 %, centred at 50 % of H). | |
| 0.70-2.40 | Hold (picture moves at 1-2 %/s). | |
| 2.40-2.80 | Text fades out; picture rises to 100 % over 0.6 s from 2.40 to 3.00. | Voice returns at 3.00. |

Differs from GAE: the picture stays in the frame and is dimmed, not defocused. Closest evidence: Still Mind 1:45-1:49.

Engine: *covered*: X-HI-01 (set the shape to the whole frame, floor 0.4), TR-01 dissolve, STATIC-09-style fade text, CAM-03. *New*: nothing structural; a "full-frame dim" preset and the typographic settings.

### Treatment 3. "Margin Notes" (conservator's file)

Idea: the name is not a label but a note pinned to a detail by a thin line, as a conservator marks up a picture. The chapter mark is a measured line with ticks along the lower edge. No boxes.

**Opening (0-13 s)**
| Time | On screen | Sound |
|---|---|---|
| 0.00 | Painting, slow push-in (CAM-01, 1.5 %/s). | Music 0.00; voice 0.5 s. |
| 6.00-6.40 | A small circle (about 1.6 % of W) is drawn on a chosen detail (face, hands, signature) (AN-01). | |
| 6.40-7.00 | A thin leader line (2 px at 1080p, white 70 %) is drawn from the circle to the left margin, ending at x = 6 %, y = 82 %. | |
| 7.00-8.00 | At the line's end three lines fade in, left set: title (italic, cap 3 %), "Artist, year" (cap 2.3 %), "oil on oak - 82 x 60 cm - National Gallery" (small caps, cap 1.8 %, tracking +12 %). No box behind. | |
| 8.00-12.00 | Hold. | |
| 12.00-13.00 | Text fades 0.6 s; the line retracts over 0.4 s back into the circle; the circle fades. | |

**Brand beat (4.5 s)**: current picture dims to 30 % over 0.6 s; a horizontal line draws out from the centre at 52 % of H to a width of 38 % of W (0.6 s); "RAKING LIGHT" (capitals, cap 7 %) fades in above it (0.8 s); a small line "a film about <painting>" (cap 2 %, tracking +12 %) fades in below it. Hold 1.5 s; hard cut at 4.5 s. This repeats GAE's 2020 rule-and-two-lines logic (1.3 of this report), so it is the closest to a GAE original; use it only if the owner accepts that.

**Chapter mark (3.2 s)**
| Time | On screen | Sound |
|---|---|---|
| -1.0 | | Voice stops. |
| 0.00 | Hard cut to the first picture of the chapter at 70 % brightness, in slow push. | |
| 0.10-0.70 | A thin horizontal line draws from x = 8 % to x = 92 % at y = 86 % of H, with one tick per chapter (n total, the current one slightly longer, white; others 40 % grey). | |
| 0.40-0.80 | "N. Title" fades in above the current tick, left-aligned at x = 8 %, baseline at 82 % (cap 4.3 %). | |
| 0.80-2.60 | Hold. | |
| 2.60-3.20 | Text fades 0.4 s; line retracts 0.4 s; picture returns to 100 %. | Voice returns at 3.20. |

Differs from GAE: type is left-aligned low, with progress shown by ticks; the picture is seen, not blurred. Honest risk: ticks plus text are two elements; T2 asks for one line. Keep the ticks at 40 % grey and under 0.6 % of H tall so they read as texture, or drop them.

Engine: *covered*: AN-01 circle draw, AN-05 dimension ruler (line draw with labels), X-ANN-01/02 label, CAM-01. *New*: a leader-line draw between two points with a retract, a tick row with a highlighted tick (partial: AN-05 draws a ruler).

### Treatment 4. "Surface First" (texture before image)

Idea: the film begins inside the paint, as if the lamp were held almost flat to the surface, and pulls back to the picture. Each chapter starts with a macro crop of what the chapter is about. Needs a high-resolution still (see risk).

**Opening (0-14 s)**
| Time | On screen | Sound |
|---|---|---|
| 0.00 | Macro crop of paint texture, about 8 % of the image width (so about 12x), contrast raised (relief emphasis if available). | Music 0.00; voice 1.0 s. |
| 0.00-12.00 | Pull-back (CAM-03) from 12x to 1x with a strong ease-out (starts at about 8 %/s, finishes at under 1 %/s) while drifting 0.9 % of W per second. The whole picture is revealed at about 12 s. | |
| 11.50-12.30 | Label fades in bottom left (as Treatment 1). | |
| 12.30-15.50 | Hold. | |
| 15.50-16.00 | Label fades out. | |

**Brand beat (5 s)**: on the texture of the current picture at 6x, "RAKING LIGHT" (capitals, cap 8 %, tracking +25 %) fades in 0.8 s, hold 2.5 s, fades 0.6 s; hard cut at 5.0 s.

**Chapter mark (3.3 s)**
| Time | On screen | Sound |
|---|---|---|
| -1.0 | | Voice stops. |
| 0.00 | Hard cut to a macro crop (5x) of the region of the next picture that the chapter is about. | |
| 0.15-0.55 | "N. Title" fades in, centred at 50 % of H, cap 4.5 %, a soft dark shadow so it holds on the texture. | |
| 0.00-3.30 | The crop pulls back from 5x to 2x (about 1.5 %/s, constant speed). | |
| 2.60-3.00 | Text fades out. | Voice returns at 3.30 on the 2x framing. |

Differs from GAE: texture instead of blur. Same logic as GAE's mark (a changed image state under the type, released at the end) so it obeys T3 and T4.

Risk: a 12x crop and a 5x crop need sources of 4000 px or more on the long side. The engine pan/zooms stills, so quality depends on the picture file. Without enough pixels the crop is soft and reads as a mistake.

Engine: *covered*: CAM-03, CAM-05, TXT-01 (shadow on), TR-01. *New*: optional relief/contrast boost; a per-chapter macro-crop key chosen by the script.

### Treatment 5. "Through Black" (film punctuation)

Idea: the classic dip through black, but with the next picture already rising beneath the type, so it is not a card.

**Opening (0-12 s)**
| Time | On screen | Sound |
|---|---|---|
| 0.00-1.00 | Black. | Music or room tone only. |
| 1.00-3.00 | Painting rises from black in 2.0 s (linear exposure), slow push (CAM-01). | Voice at 1.5 s. |
| 8.00-8.80 | Title in wide-tracked small capitals (cap 3.5 %, tracking +25 %) centred at 76 % of H, over the picture, fades in 0.8 s (BBC Marr, Still Mind: same placement and tracking). | |
| 8.80-12.00 | Hold, picture moves under it. Artist and year small caps (cap 2 %) at 81 % from 9.2 s. | |
| 12.00-13.00 | Text fades out 1.0 s. | |

**Brand beat (5 s)**: the picture fades to black in 0.8 s; "RAKING LIGHT" in capitals, cap 7 %, tracking +25 %, centred at 46 % of H, fades in 1.0 s over black, hold 2.2 s, fades 0.6 s; hard cut to chapter 1 at 5.0 s.

**Chapter mark (3.4 s)**
| Time | On screen | Sound |
|---|---|---|
| -1.0 | | Voice stops. |
| 0.00-0.40 | The outgoing picture dips to black. | |
| 0.40-1.90 | The next picture rises from black to 35 % over 1.5 s. | |
| 0.60-1.00 | "N. Title" fades in (cap 4.3 %, centred at 50 % of H). | |
| 1.00-2.70 | Hold. | |
| 2.70-3.10 | Text fades out. | |
| 2.50-3.40 | Picture rises 35 % to 100 %. | Voice returns at 3.40. |

Differs from GAE: a dip. Closest to GAE 2020 black card, which lasted 2 s and used a hard cut; here the picture rises under the text so it is not a card.

Engine: *covered*: TR-01, fades, TXT-01, X-CARD-01 (partial: black card). *New*: a "dip" preset (fade to black, rise to a held level, hold, rise to 100 %).

### Treatment 6. "Lamp Pool" (the second light idea, spot instead of band)

Idea: a conservator's hand lamp. Where Treatment 1 uses a band for sweeps, this uses a soft pool of light that wanders to details; used only in the opening and in chapter marks where the next picture has a clear subject. Use T1 or T6, not both, in one film.

**Opening (0-13 s)**
| Time | On screen | Sound |
|---|---|---|
| 0.00-1.00 | The painting at 8 % brightness; slow push (CAM-01). | Music 0.00; voice 1.0 s. |
| 1.00-10.00 | A soft pool of light (ellipse about 28 % of W by 40 % of H, feather 0.55, centre brightness 100 %) travels a path over three or four details chosen by the script, dwelling 2 s on each (narration names them). Outside the pool: 8 %. | |
| 9.00-9.60 | When the pool rests on the last detail, the label fades in near the pool's edge (left margin if the detail is at the left). | |
| 10.00-12.00 | The pool widens to cover the whole picture (to 100 % over 2.0 s). | |
| 12.50-13.00 | Label fades. | |

**Chapter mark (3.1 s)**
| Time | On screen | Sound |
|---|---|---|
| -1.0 | | Voice stops. |
| 0.00 | Hard cut to the next picture at 8 % brightness. | |
| 0.10-0.60 | A pool of light fades on at the chapter's detail; "N. Title" fades in under the pool at 74 % of H (cap 4.3 %, centred). | |
| 0.60-2.40 | The pool holds and drifts by 1 % of W per second; the picture stays dark. | |
| 2.40-3.10 | The pool widens to the whole picture; text fades out 0.4 s. | Voice returns at 3.10. |

Differs from GAE: dark picture and a light pool, no blur. The text sits in the dark, so it needs a bright, large-enough face (cap 4.5 %).

Engine: *covered*: HI-01 spotlight (rx, ry, floor, ramp, feather). *New*: HI-01's point `at` is fixed; it needs a keyframed path (times and points) and an easing.

### 4.7 Choosing between them

| | Differs from GAE | Needs new engine work | Reading risk |
|---|---|---|---|
| 1 Raking Pass | strongly (light, written by light) | band overlay + masked text reveal | text invisible for the first moments of the mark: keep the band at under 2.0 s |
| 2 Dim and Name | moderately (dim instead of blur) | almost none | closest to Still Mind; plain |
| 3 Margin Notes | strongly (leader line and ticks) | line draw, tick row | a second element beside the title (ticks) |
| 4 Surface First | moderately (texture instead of blur) | relief option | source resolution |
| 5 Through Black | moderately (dip) | dip preset | resembles GAE 2020 black card |
| 6 Lamp Pool | strongly | keyframed spotlight path | text in the dark |

[infer] The name "Raking Light" is carried best by 1, then 6. 2 and 5 are the safest to build now.

### 4.8 What to avoid, with the reason from the evidence

1. **A panel, card, label with a shadow, a coloured block or a flat colour ground behind the title or mark.** In 8 of 8 GAE marks and in the BBC, Still Mind and Nerdwriter titles the text sits on the picture. The only cards seen are 2 to 2.5 s and are followed at once by live footage. The rejected mock-ups B and C are built on panels.
2. **A title card as the first thing in the film.** Every film measured starts on a moving picture or on archive footage; the painting's name arrives 6 to 16 s in (GAE) or 4 to 92 s in (others).
3. **A giant ghost numeral, a kicker line, a second sub-title line next to a mark.** GAE marks are one line at cap 4.0-4.7 %. The sting is the only large type (cap about 10 %), and it is the brand, not a chapter.
4. **A static frame under the type.** GAE's mark ground is the next picture defocused and then released; Still Mind's is a dimmed moving picture; the labels sit on pictures that move 1-3 % per second.
5. **Type that slides, types out or scales.** None of 8 marks moves; all fade in 0.2-0.4 s.
6. **A mark without the sound gap.** The voice stops about 1 s before the cut and returns as the mark ends. Without it a 3 s mark feels like a freeze.
7. **A mark that is longer than about 3.6 s or more frequent than about every 60 s.** Observed: 2.8-3.6 s and gaps of 58-454 s.
8. **Wide letter-spacing on a title-case mark.** GAE's 2023-26 marks are normal-tracked. Wide tracking appears on the sting, on the BBC title and on Still Mind's credit line (small caps), not on the chapter line. The engine defaults (`tracking_px` 14 on size 84) belong to the older, caps style.
9. **Using `X-CARD-02` as the opening.** GAE does not show the painting's title on a card; a card of title, artist and year is not in the evidence.

---

## 5. What I could not do or verify

- The sting's 3D camera move and relief lighting cannot be copied by a 2D engine; my 2D versions are replacements, not copies. Opacity of the sting letters is estimated by eye (60-70 %).
- Chapter marks were found by text recognition at 1 fps; counts can miss one mark per film. Cap height is measured from thresholded white pixels; on bright pictures the threshold fails (some frames gave 11-12 % and were discarded and re-measured on a narrower band). The blur-release time was measured with a sharpness curve and is exact only for 2022, 2024, 2025a.
- Narration gaps are from RMS level per 0.25-0.5 s window; voice and music are not separated. "Music bed 15-20 dB under the voice" means the level of the whole mix during the gap against the level during speech.
- The font of the 2023-26 marks is Times-like; I did not identify it. The label font and the sting font are not identified.
- The 2020 Guernica sting and chapter frames are from 1 fps and 4 fps sheets only.
- For other makers I looked at 120 s each (the allowed segment). I saw one chapter mark (Still Mind 1:45) and no marks for the others. Jacob Geller's file is a content-warning opening and tells nothing about art titles. The BBC *Civilisations* frames are from a re-upload with Spanish subtitles and a TV channel logo (the titles are the BBC's but I did not see an original file). Web search found no Art of the Title page or article for the art series I looked for.
- The rejected mock-ups were judged from three screenshots and from the page source (no animation); sizes are by eye.
- No sound design beyond level was examined; the proposed music levels are by analogy to GAE's measured gap and are not tested.
