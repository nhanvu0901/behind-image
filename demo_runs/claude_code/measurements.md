# Reference measurements (T15Kv6dtYO0.mp4, 1280x720, AV1, 29.97 fps, 939.9 s) and effect excerpts

Method: ffmpeg `scene` detection (320x180, thr 0.15), 29.97 fps dense decodes with per-frame pixel statistics
(`scripts/measure_overlays.py`), and cv2 `findTransformECC` (MOTION_AFFINE, chained frame pairs at 10 fps, 320x180 gray,
`scripts/measure_motion.py`) for zoom/pan. Raw outputs: `ref/motion.txt`, `ref/overlays.txt`, `ref/scene_log.txt`.
All motion numbers are apparent content motion; "magnification" >1 = push-in, <1 = pull-back. Progress@25/50/75% = fraction of
total log-zoom reached at that fraction of the move's time (linear = .25/.50/.75).

## Framing and structure
- Vertical painting: shown full height, centred on a pure black matte (matte width = 100% - ~34% of frame at full height). No shadow/gradient.
  (Spec forbids raw black bars, so I use a near-black gallery gradient + soft shadow; same look, justified in report.)
- Details: full-bleed 16:9 crops, no matte.
- Cuts: 58 detections at thr 0.15 -> 59 shots; median shot 7.0 s, mean 15.9 s (a few long moves 30-70 s); 10th pct 4.0 s, 90th 37.6 s.
  Stock/reference stills in a sequence are held exactly 4.0 s each (cuts at 181.3, 185.3, 189.3, 193.3 s). All sampled cuts are HARD cuts
  (no dissolve seen at 181.3 card->image, 179.3 black->card); dissolves exist only in the effect excerpts (TR-01).
- Opening 0-35 s: empty room visible from frame 0 (no fade from black), static ~6.5 s; figure cut-outs slide in from left/right edges at ~2.2x
  scale 6.5-12 s; then decelerating pull-back (below) to full painting on matte at ~30 s, hold ~5 s, hard cut at 35.0 s to other paintings.

## Camera moves
| Move | Reference | Duration | Total | Easing (progress @25/50/75% t) | Used by me |
|---|---|---|---|---|---|
| Opening pull-back (figure layers) 12-30 s | ref_pullback_figures | 17.9 s | 0.334x (=3.0x out), vertical drift ~25 px/s@180 | ease-out .41/.67/.89 | B1b: 3.0x over ~9 s, ease-out cubic |
| Matte full painting -> fill width, 322.6-327.5 s | ref_matte_zoomin | 4.9 s | 1.59x, peak ln-rate .22/s | ease-in .10/.34/.65 | B2a: same 1.6x/4.9s ease-in (quad) |
| Dress pan down 334-347 s | ref_dress_pan | ~13 s | ~2 frame heights, ~16%/s of 180 px height at 320 px scale (about 17% frame height per s) with magnification drifting 1.35->1.03 | ~linear | B2b: linear pan, about 12%/s of crop height, 5 s |
| Mirror push 590-601 s | ref_mirror_push | ~11 s | 3.57x | S-curve: .08@2.1s .32@5.1s .69@8.1s .95@10.1s (ease in-out), peak ln-rate .15/s | B3a: 3.5x over 6 s ease-in-out cubic |
| Mirror drift 601-618 s | same | 17 s | magnification ~1.0, pan ~5.5 px/s @320 in both axes (1.7%/s) | linear w/ eased ends | drift 1.7%/s in B3b |
| Chandelier push 666-669 s | ref_chandelier | ~3 s | 1.49x then lateral pan 37 px/s@320 (11.5% width/s) | ease-out .49/.70/.85 | used in reel CAM-05 |
| Closing pull-out 888-928 s | ref_closing_pullout | 40 s | 5.8x out | ease-out .45/.71/.90 | B5a: 3.4x over ~9 s, ease-out |
| Excerpt push-in (CAM-01) | crCPVoPsTtk-815 | 5.9 s | 1.142x (ln-rate .0225/s) | ~linear, slight end ease .27/.55/.82 | 1.14x/6 s |
| Excerpt pull-back (CAM-03) | 83ggxS21mFM-31 | 9.9 s | 0.762x | ease-in .17/.40/.71 | 1.31x out/9 s ease-in |
| Excerpt pan-up (CAM-04) | lAjVuUB9AkI-930 | 9.4 s | 16.6% of frame height (180 px@1080), 19 px/s, magnification 1.03 | linear .24/.48/.74 | 19 px/s linear |
| Excerpt zoom+shift (CAM-05) | TU3dRcqik3I-1011 | 9.4 s | 1.51x with 15%W/14%H shift, ln-rate .044/s | ~linear .22/.45/.72 | 1.5x with same shift |

## Overlays / text (hard timings at 29.97 fps)
- Detail label ("BLUE UNDERGARMENT", 327.5-330.9 s): text pops in over 2 frames (110 px -> 3737 px white at 327.5->327.6; 0.1 s), stays 3.2 s, disappears in
  <0.2 s. Strip: full-width semi-opaque near-black band (~80% opacity), y = 79.4%-93.3% of frame height (100 px of 720), text left-aligned at x = 7.0% of width,
  white geometric sans (Futura-like) all caps, cap height ~30 px of 720 (4.2% H), text in upper part of strip (single-line case), 2nd smaller line (artist, year) below.
  Strip right end fades out (gradient over the right ~20%).
- Chapter card "FASHIONS AND FABRICS": black bg 2.0 s; text pops over 0.1 s at +0.2 s, leaves at +1.7 s (fade <=0.15 s), then HARD cut. Text centred x, y ~88% of height, small caps width ~35% of frame.
- Dimension annotation (174.5-179+ s, over a gallery-photo with viewers): white 5-6 px (at 720p) rectangle lines + "60cm" top-centre, "82cm" left-middle, "OIL PAINTING / ON OAK PANEL" bold sans top-right
  (x 68-95%, y 10-23%); everything appears within 0.2 s (white px 126 -> 349 -> 10729 at 175.6/175.7/175.8 s), held >3.2 s.
- Circle annotation (662.4-664.8 s): two light-grey rings (about 190/255, ~75% opacity), diameter ~300 px of 1280 (23.4% W), stroke ~9 px (0.7% W), appear 662.4-662.9 s
  (90% of pixels in 0.5 s - a fast draw-on/pop), held ~2.0 s, fade ~0.4 s (~664.8-665.2) as the camera push starts.
- Closing: recap labels (CANDLE, ROUNDELS, MOURNING DRESS, DOG) as plain white text without strip over the black matte; end credit centred bottom.
- No fade-from-black at video start; scenes are hard cut.

## Spotlight (excerpt 9x0tsuS4dk0-1352)
Tiles at 1 fps: whole fresco dimmed with small bright rectangular accent lights, hard cut to crop of feet, then a vignette spotlight (feathered ellipse) on a seated figure over a
near-black surround. I use surround brightness 0.35 and 0.5 s ramp (as the brief example) with feathered mask; reference surround appears ~15-25% brightness (measured by eye only).

## Not measured / limits
Pixel colours of dim levels in the excerpts only estimated visually; scroll-text/slide-in/panel-opening timing from 1 fps tiles (+/-0.5 s). The reference clips have no audio sync info.
