# Draft shot plan: final_demo.mp4 (times are estimates; real times come from TTS beat durations)

Canvas 1920x1080, 30 fps, supersampled sub-pixel cv2.warpAffine (INTER_CUBIC/LANCZOS4) from full-res sources, raw frames piped to ffmpeg libx264 yuv420p.
Backdrop for the vertical painting: near-black (#0b0b0d) radial gallery vignette + painting with soft drop shadow and thin dark frame edge (reads as the channel's black matte, no raw bars).
Sources: Commons Van_Eyck_-_Arnolfini_Portrait.jpg 4386x6000 (PD, logged), Commons Jan_van_Eyck_069.jpg 4169x3249 (Van der Paele, PD),
PDF detail images p25 dog, p30 mirror/roundels, p31 hands, p26 pattens, p29 Van der Paele (fallback).
Timing: 0-3.5 s title card (blurred painting bg, title / artist / 1434, fade 0.5 s in, hard cut out as the channel does); narration starts 3.5 s; 0.35 s gap between beats.

| Time (s) | Beat | Visual | Catalogue |
|---|---|---|---|
| 3.5-9.4 | B1a | Empty-room plate (figures removed by layer) on near-black gallery matte; figures slide in from both sides at larger scale (HI-02 figure reveal / CAM-02 relative motion) | HI-02, CAM-02, STATIC-01 |
| 9.8-12.8 | B1b | Slow decelerating pull-back (0.33x over ~14s, ease-out) to the full vertical painting on matte | CAM-03, STATIC-01 |
| 13.1-20.3 | B2a | Matte full painting zooms in until it fills width (ease-in), then continues push into dress; label GREEN GOWN / Jan van Eyck, 1434 | CAM-01, CAM-06, STATIC-02 |
| 20.6-26.5 | B2b | Continuing slow pan down the dress (linear ~3% frame-height/s) with zoom-out drift; label FUR LINING | CAM-04, CAM-05, STATIC-02 |
| 26.9-33.7 | B2c | Cut-in (TR-04) to dog/hem crop (PDF p25 detail), slow push; label DOG | TR-04, CAM-01, STATIC-08 |
| 34.0-41.2 | B2d | Dissolve (TR-01) back to full painting on matte; centred year text 1433 (STATIC-09) over dimmed painting | TR-01, STATIC-09 |
| 41.5-48.7 | B3a | SPOTLIGHT (HI-01) on mirror: surround dims to ~35% over 0.5 s starting at beat start, simultaneous push-in on mirror (CAM-05 zoom+shift, 3.5x) | HI-01, CAM-05 |
| 49.0-52.8 | B3b | Detail-label ART DETAIL 'PASSION ROUNDELS'; two circles drawn (AN-01) around two roundels, draw 0.5 s | AN-01, STATIC-02 |
| 53.2-57.4 | B3c | Pan to the right-hand half of the ring, spotlight shifts (HI-01 reposition); AN-02 outline of the roundels on her side | HI-01, AN-02 |
| 57.8-63.7 | B4a | TR-02 slide-in of Van der Paele from right into LAY-01 two-panel split-screen; captions at bottom | TR-02, LAY-01, STATIC-02 |
| 64.0-69.1 | B4b | Both panels push in to the two rugs/cloth (CAM-05) with synced slow zoom | CAM-05, LAY-01 |
| 69.5-73.7 | B4c | Split dissolves out to full painting, push toward the joined hands; DIA-less | TR-01, CAM-05 |
| 74.0-79.1 | B4d | SPOTLIGHT on joined hands (HI-01) starting at beat start; hands crop (PDF p31 + Commons crop) slowly pushing; label 'HANDS' | HI-01, CAM-01 |
| 79.5-82.5 | B5a | Spotlight releases (0.5 s), long ease-out pull-back to full painting on matte (closing pull-out ref: 5.8x over 40 s, scaled to ~9 s) | CAM-03, STATIC-01 |
| 82.8-90.4 | B5b | Hold on full painting, slow fade to dark; end title | STATIC-01 |

Subtitles: burned with libass on the server (Century Gothic GOTHIC.TTF is available there as a Futura-like face), plus subtitles.srt. Detail labels in the Futura-like strip style are in final_demo as in channel (not corner labels).
Music: locally numpy-synthesised soft pad (A minor drone + slow filtered noise), -26 dB under voice; no external file. Loudness target -15 LUFS, TP <= -1 dBTP via two-pass loudnorm.
Sync: every visual event is scheduled at a beat start (beats are separate TTS calls so starts are exact); words inside a beat are not relied on. Optional forced alignment (faster-whisper in own venv) only if you approve a model-load job.
Estimated total about 91 s (190+ words with pauses): slightly over the 90 s guide; I will trim a clause if atempo 1.20 is not enough.

# Plan: technique_reel.mp4 (56 records, ~4.5-6 s each, ordered by ID, corner label e.g. "CAM-01 Push-in", about 5 min)

Status: B = build on Arnolfini/Van der Paele, S = stand-in (substitute material, labelled in report), X = skip. SHORT-* records are vertical: shown as a 608x1080 (9:16) panel centred on the same gallery backdrop with blurred ambient fill on the sides, label in corner.
Needed prep (Mac, still images): grabCut masks for the couple, dog, mirror; approximate empty-room plate via cv2.inpaint + wall/floor synth (partial quality, flagged).

| ID | Status | Plan |
|---|---|---|
| CAM-01 | B | push-in 1.14x/6 s near-linear on dress/hands |
| CAM-02 | B/S | layered relative motion: couple cut-out vs room plate, opposite scale rates (cut-out from grabCut, room plate synthesised = stand-in for the clean plate) |
| CAM-03 | B | pull-back 1.31x ease-in 8 s from mirror to full painting |
| CAM-04 | B | pan up 19 px/s linear over legs->face |
| CAM-05 | B | zoom+shift 1.5x with 15% shift |
| CAM-06 | B | hold on matte, white label pop at +6 s |
| TR-01 | B | dissolve 1.0 s between Arnolfini and Van der Paele (dissolve length from excerpt about 1.0 s) |
| TR-02 | B | slide-in/out of 2nd image into two-panel 0.8 s ease |
| TR-03 | S | panel opening: painting split into two shutter panels in perspective that open to reveal inner image (no real triptych; uses Arnolfini halves + Van der Paele inside) |
| TR-04 | B | hard cut full -> crop |
| LAY-01 | B | two panels |
| LAY-02 | B | four-detail grid with connecting lines |
| LAY-03 | S | five columns: five crops of the same painting / colour states |
| LAY-04 | B | inset window over crop (inset shows Van der Paele rug) |
| LAY-05 | S | subject held centre while backgrounds change (cut-out couple over varying backgrounds) |
| LAY-06 | B | semi-transparent vertical strips montage |
| LAY-07 | B | grid of 4 crops plus semi-transparent overlay (mirror) |
| LAY-08 | B | symmetric repeated mirror roundel kaleidoscope |
| HI-01 | B | spotlight surround 0.35, 0.5 s ramp, feathered |
| HI-02 | B/S | figures reveal onto room plate (stand-in plate) |
| HI-03 | B | colour kept on couple, rest greyscale |
| AN-01 | B | two circles, stroke 0.7% W, 0.5 s draw, hold 2 s, fade 0.4 s |
| AN-02 | B | white outline traced around couple silhouette (from mask contour) |
| AN-03 | B | perspective rays converging on the vanishing point near the mirror |
| AN-04 | S | map arrow: procedural stylised map (Bruges to Lucca) as stand-in - no map asset |
| AN-05 | B | dimension ruler 60 cm / 82 cm with arrows |
| AN-06 | B | grid + triangle/areas overlay |
| AN-07 | B | dot field densifying into painting colours |
| TXT-01 | B | chapter title over blurred painting |
| TXT-02 | B | sliding italic text lines (own text) |
| STATIC-01 | B | designed near-black matte (vignette+shadow) |
| STATIC-02 | B | small white source label lower-left |
| STATIC-04 | B | quote over image (own wording, not channel's) |
| STATIC-05 | S | interviewee name tag over placeholder crop (generic text, no real person) |
| STATIC-06 | S | stylised map + route |
| STATIC-07 | B | multi-cell circular diagram of symbols |
| STATIC-08 | B | name labels near figures |
| STATIC-09 | B | centred year 1434 over blurred image |
| DIA-01 | S | grid + projecting rays diagram applied to the room perspective (no skull) |
| DIA-02 | S | two views of one object: frontal mirror vs oblique perspective warp |
| DIA-03 | S | synthetic paint cross-section schematic with gold light rays |
| DIA-04 | S | figure, dog, mirror cut-outs separated on black |
| DIA-05 | S | silhouette fill/outline of couple beside crop (process footage absent) |
| DIA-06 | S | simple room diagram plus false-colour "UV-style" simulated crop, labelled simulated |
| DIA-07 | S | optical diagram of convex mirror (instead of eye) |
| CMP-01 | B | grey and colour of same region |
| CMP-02 | S | simulated stages left, finished right |
| CMP-03 | B | white/sepia/colour versions |
| CMP-04 | B | colour-block mosaic beside crop |
| CMP-05 | B | PDF-print vs Commons scan colour states (real two states) |
| FOOT-01 | S | palette cards and material swatches from painting with labels; no real footage |
| SHORT-01 | B | vertical 3 strips (9:16 panel) |
| SHORT-02 | S | vertical changing-view (mirror warp) |
| SHORT-03 | B | large type changing on painting (vertical) |
| SHORT-04 | B | small text on yellow box (vertical) |
| SHORT-05 | S | colour wheel from painting palette (vertical) |

Tally: build 37, stand-in 17, build-with-stand-in-material 2 (CAM-02, HI-02), skip 0 (nothing skipped yet; STATIC-05, FOOT-01 are weakest stand-ins and would be the first to drop).
Render estimate: about 5 min x 30 fps = 9000 frames, one heavy lock, about 15-30 min on 6-8 threads.
