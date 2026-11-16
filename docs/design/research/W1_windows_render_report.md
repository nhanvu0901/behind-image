# W1: engine on the Windows server

Date 2026-11-16. Host DESKTOP-4V6D49N, reached via `winbox-lan` (Tailscale was down on the Mac, `winbox-cmd` gave "Network is unreachable"). Snapshot `engine_snapshot_v2.tgz` deployed to `D:\bench\bti\`. Python: comic `.venv` (3.14, numpy 2.5.2, OpenCV 4.13, Pillow 12.3). No venv created, nothing pip-installed. Scripts are in `tools/server/`.

## Result
The engine works on Windows with no changes. `validate` = 0 errors, 0 warnings. Full 1080p render done in 3 parts under the lock.

## Render timing (`--quality final --threads 4`)
| Job | Output s | Wall s | s per output s |
|---|---|---|---|
| timing sample 300-320 | 20 | 60.2 | 3.01 (an overlay-heavy stretch) |
| part1 0-273.6 | 273.6 | 592.7 | 2.17 |
| part2 273.6-547.2333 | 273.63 | 569.7 | 2.08 |
| part3 547.2333-820.8333 | 273.6 | 498.4 | 1.82 |
| total | 820.83 | 1660.8 (27.7 min) | 2.02 = **2.0 min per output minute** |

Old code: about 1.9 min per output minute. The new engine is about 6 % slower overall. Each part took 8.3-9.9 min, well under the 30 min limit. The 20 s sample over-estimated by about 40 %, so measure on a longer range next time.

## Join check
Frame boundaries (frame-exact): 0 / 8208 / 16417 / 24625. Parts hold 8208, 8209 and 8208 frames. The concat (demuxer, stream copy) has **24625 frames = round(820.8333*30)**, duration 820.833333 s.
Frames j-2..j+1 at each join compared with Mac stills at t=i/30 (1920 px): PSNR 37.3-37.5 dB at join 8208 and 38.4-38.8 dB at join 16417, the same level as frames away from the joins (this is the x264 crf 15 loss). At join 16417 each frame matches its own still about 7 dB better than the previous frame's still. At join 8208 motion is very slow, so this test discriminates less. Neighbouring-frame PSNR is smooth (32-51 dB), with no repeated or skipped frame.

## Cross-platform stills (16 times, 960 px)
Times: 5, 17, 32, 43, 75.5, 78.5, 90, 110, 177, 196, 258.5, 310, 510, 580, 805, 818.
| t | PSNR dB | note |
|---|---|---|
| 5 | 99 (identical) | no text |
| 17 | 92.3 | no text |
| 32 | 95.1 | ruler text |
| 90 | 99 | |
| 818 | 92.3 | closing, no text |
| 43 | 24.3 | label strip text |
| 75.5 | 19.9 | title card |
| 78.5 | 23.7 | chapter card |
| 110 | 38.5 | map labels |
| 177 | 28.0 | names |
| 196 | 25.6 | year text |
| 258.5 | 26.4 | label strip, ring |
| 310 | 24.9 | label strip |
| 510 | 24.3 | split-screen captions |
| 580 | 26.2 | diagram caption |
| 805 | 25.7 | recap labels |

Every pixel above a threshold of 12 lies inside a text bounding box (label strip, card, caption). Everything else is identical to 1 level. **The differences are text only.**

## Fonts (`vfx.font_signature()`)
- Windows: `bold=GOTHICB.TTF; reg=GOTHIC.TTF; sans_bold=arialbd.ttf; serif_it=georgiai.ttf` (Century Gothic, found).
- Mac: `bold=Futura.ttc; reg=Futura.ttc; sans_bold=Arial Bold.ttf; serif_it=Georgia Italic.ttf`.
Looking at the stills: Century Gothic is a lighter, slightly narrower geometric face; Futura (index 0) is heavier. The layout is the same (centred, same tracking). The new Windows render uses the same Century Gothic as the old code, so text matches the reference.

## Comparison with `final_demo.mp4` (looked at by eye and PSNR)
27 times (3, 15, 35, 55, 63, 85, 105, 125, 160, 215, 240, 285, 330, 405, 470, 525, 570, 600, 650, 700, 745, 790, 812, plus 80.0, 80.5, 170, 169): PSNR 40.2-99 dB, with 99 (bit-identical decode) on 15 of 27 frames and no frame below 40 dB. Mean luma is the same. Black frames at 80.0 and 170.0 match the reference (card/sequence fades). I found no visible difference. The re-anchored onsets did not fall on any sampled time.

## Mux and QA
`demo_runs/engine_v1/final_engine_v1.mp4` (908 MB) plus `subtitles.srt`.
- Streams: h264 1920x1080 30 fps 24625 frames; aac 820.833 s (stream copy of `mix.m4a`, 38478 frames); mov_text soft subtitle (308 cues). No subtitle burned in.
- Loudness: integrated -15.0 LUFS, LRA 3.6 LU, identical to the reference (-15.0 / 3.6).
- 83 contact-sheet frames (every 10 s, 4 pages in `.scratch/w/sheets/`) looked at: no wrong images and no burned-in subtitle. Black frames occur only at the card positions (80 s, 170 s) and match the reference. The chapter-card and recap labels are present.
- Observation (not an engine bug): at 180 s the name label "GIOVANNI DI NICOLAO ARNOLFINI" overlaps the painting's head, and the label at 805 s partly overlaps the painting. This is the same layout as on the Mac and the earlier code.

## Server problems and notes
1. `winbox-cmd` unreachable (Tailscale off on Mac); `winbox-lan` worked.
2. A first command that wrote a helper file to `D:\bench\` (outside `D:\bench\bti\`) was blocked by my own permission guard and nothing was written; all files then went to `D:\bench\bti\`.
3. The tgz was made on macOS, so it contains `._*` AppleDouble files (`projects\arnolfini\._storyboard.json`, `._timing.json`) that tar unpacked as stray files. They did not affect the engine. Pack with `COPYFILE_DISABLE=1` next time.
4. The agent was interrupted by a usage limit after part 2 had been launched. I checked `p1.log`/`p2.log`: both ended EXIT=0 and LOCK_RELEASED, then ran only part 3.
5. zsh `echo` expands `\b` in Windows paths; write .bat files with Python (`tools/server/mkjob.py`).
6. No production process was seen at any point; free virtual memory was 19-21 million KB; D: had 327 GB free.

## Changes the engine needs for Windows
None. No hot-fix was applied to the server copy (no diff). Suggestion only: label positions for Futura vs Century Gothic differ in width (about 6 %), so any layout fitted on the Mac should be checked on the Windows stills.

## Clean-up
Lock released (`no lock` at the end); `git status --short` of the comic repo equals the baseline (6 untracked entries, unchanged); no python/ffmpeg process of mine is running. `D:\bench\bti\` was left in place (including `out\part*.mp4`).
