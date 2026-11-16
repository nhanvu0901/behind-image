import json, os, sys, csv
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{H}/scripts")
from cap_rows import R
seg = {s["id"]: s for s in json.load(open(f"{H}/ref/server/technique_reel_segments.json"))}
T = json.load(open(f"{H}/timing.json"))
rows = []
cnt = {"done": 0, "partial": 0, "not done": 0}
for id_, (st, method, refm, mine, fin, rate, block) in R.items():
    cnt[st] += 1
    s = seg[id_]
    where = "reel %d:%02d-%d:%02d" % (s["t0"] // 60, s["t0"] % 60, s["t1"] // 60, s["t1"] % 60) + ("; " + fin if fin != "reel only" else "")
    rows.append("| %s | %s | %s | %s | %s | %s | %d | %s |" % (id_, st, method, refm, mine, where, rate, block or "-"))
lj = open(f"{H}/ref/qa_jitter.txt").read().strip().splitlines()
sync = open(f"{H}/ref/qa_sync.txt").read()
loud = open(f"{H}/ref/loudness_final.txt").read()
render = json.load(open(f"{H}/ref/server/render_times.json"))
md = f"""# Capabilities report (claude_code agent)

Deliverables: `final_demo.mp4` (1920x1080, 30 fps, H.264+AAC, {T['end']:.1f} s), `technique_reel.mp4` (1920x1080, 30 fps, {sum(s['t1']-s['t0'] for s in seg.values()):.0f} s, 56 segments), `timeline.json`, `script.txt`, `subtitles.srt`, `contact_sheet.jpg`, `reference_compare.jpg`.

## Result counts (56 catalogue records)
**done {cnt['done']}, partial {cnt['partial']}, not done {cnt['not done']}.**  "Partial" = built with substitute material or a rough asset (reason in the last column); synthesised material (maps, UV-style view, silhouettes, cross-section) is labelled simulated here, not on screen.

## Catalogue table
Quality self-rating 1-5 (5 = indistinguishable from the channel). Reference numbers are measured in `T15Kv6dtYO0.mp4` or the effect excerpts (`measurements.md`, `ref/motion.txt`, `ref/overlays.txt`).

| Record | Status | Method / libraries | Reference (measured) | Mine | Where | Rating | Blocker / what it would take |
|---|---|---|---|---|---|---|---|
""" + "\n".join(rows) + f"""

## Extras not in the catalogue
- Sub-pixel virtual camera with area-averaged pyramid + cv2.warpAffine cubic (no zoompan), log-space zoom keyframes, per-segment easing (linear, in/out quad/cubic, sine).
- Analytic anti-aliased painting alpha + designed near-black gallery matte with soft drop shadow (replaces raw black bars).
- Burned libass subtitles in a reserved layout zone (see Layout rule) with an SRT export.
- Automated measurement tooling: ECC zoom/pan estimator (`scripts/measure_motion.py`), overlay timing (`scripts/measure_overlays.py`), jitter and sync QA on the rendered mp4.
- Locally synthesised music pad + room tone with narration ducking, two-pass loudnorm.
- Mac-side forced alignment (faster-whisper small.en, int8 CPU) to place highlights at spoken words.

## Layout rule (labels, captions, subtitles never overlap)
Content area y 0-70 %; channel-style label strip / split-screen captions occupy y 70-83 % (strip: y 756-896 px) ; subtitles occupy y >= 86 % (bottom margin 44 px, <= 2 lines). The reference strip sits at y 79-93 %; I raised it to 70-83 % so the subtitles can live below it. Checked on `contact_sheet.jpg` (no overlaps in any frame).

## Structure decisions
- Title card is placed after the hook (B1a/B1b play from frame 0 over the couple), as the channel opens cold on the image and puts titles later. Title card 2.6 s at {T['title'][0]:.1f}-{T['title'][1]:.1f} s.
- Hard cuts in the final (no dissolves in the reference episode); dissolve, slide, panel opening exist only in the reel.
- Opening plate: the inpainted empty-room plate was smeared when inspected (reel CAM-02/HI-02 stills), so the final uses a slow drift across the couple from a detail crop and a decelerating pull-back to the full painting; the empty-room figure reveal (HI-02/CAM-02) is in the reel only (partial, rating 2-3).
- Matte: the reference uses pure black; the spec forbids raw bars, so I use #1e centre -> #06 edge radial gradient with grain and a soft shadow. At normal viewing it reads like the channel matte.

## Timing
| Phase | Approx. wall time |
|---|---|
| Research, reference reading, measurements, extraction | about 8 min (01:00-01:08 UTC) |
| Script + checkpoint 1 (script v1) | about 3 min |
| Script v2, TTS job (server), alignment (Mac) | TTS job 343 s on server; alignment 11 s; ~13 min wall incl. waiting for another agent's lock |
| Editing code (lib/vfx, build_final, build_reel, stills, QA tools) | about 20 min of wall clock while TTS/lock wait ran in parallel |
| Rendering (server) | preview 47 s; final_demo render 155.7 s for 81 s (1.9 min render per output minute at 1080p, one render thread budget 4); reel {render['reel_total_s']:.0f} s for {render['reel_out_s']:.0f} s output ({render['reel_ratio']:.1f} min per output minute) |
| QA | about 6 min |

## Audio and sync
- TTS: local Chatterbox (stages.stage_4.chatterbox_tts.synthesize) with machiavelli_ref.wav, exaggeration 0.35, cfg_weight 0.5, temperature 0.7 (module default, no env override), seed 42. One synthesize() call (one model load) for all 15 beats; each beat is its own chunk, so beat starts are exact chunk boundaries (verified chunking == beats). Raw speech 76.9 s.
- **atempo = {T['atempo']}** (chosen only to land the measured speech rate: {T['wpm_first_to_last_incl_pauses']} wpm from first word to last word including the pauses and the title-card gap; speech-only rate {T['wpm_speech_only']} wpm; 185 words).
- Gaps: 0.28 s inside a section, 0.5 s between sections, 3.15 s around the title card; voice cut per beat and placed on the final timeline by `server/audio_job.py` (voice atempo, 8 ms fades).
- Sync method: beat starts exact from TTS chunks + word starts from forced alignment (faster-whisper small.en, 182 of 185 words matched, 3 interpolated) run on the Mac. Even-spread estimates from Chatterbox deviate from alignment by median 0.19 s, p90 0.48 s, max 0.85 s (alignment_table.md), so highlights use aligned words.
- Highlight onsets measured in the rendered mp4:

{sync}

- Loudness of final_demo.mp4 (ffmpeg ebur128 on the delivered file):
```
{loud}
```
  Target -15 LUFS, TP <= -1.5 dBTP in the mix; delivered file: I = -15.0 LUFS, true peak -1.4 dBTP (after AAC; spec limit -1 dBTP).
- Music: numpy-synthesised sine pad (Am-F-C-G) + low-passed noise room tone generated on the server, -24 dB re voice RMS and ducked 4 dB under speech. No external file.

## Smoothness (jitter) measurement
Per-frame ECC affine on 640x360 frames; residual after a Savitzky-Golay fit (window 9, order 3), reported in 1080p-equivalent pixels:
```
{chr(10).join(lj)}
```
All camera moves in the final have translation residual <= 0.2 px and scale residual <= 0.23 px at the frame edge, i.e. sub-pixel; the channel clips measured the same way give 0.02-0.05 px (their encode is lower resolution so the numbers are not strictly comparable).

## vmetrics
`tools/vmetrics.py --no-normalize` runs on the 16:9 file but is designed for 9:16: it resizes to a fixed 360x640 working size (stretching 16:9) and its letterbox/"padded" metrics are meaningless here. LUFS and true peak agree with ffmpeg (-15.0 / -1.4). Scene-cut counts (it reported 0 for a video with 8 hard cuts) are unreliable at its default thresholds, so I treat only the audio numbers as valid. Output in `ref/vmetrics/`.

## Problems and honest limitations
- Server: another agent's TTS held the lock about 14 minutes (waited with a 60 s poll; never touched their lock). First preflight call failed on cmd quoting; switched to scp'd .ps1 files. Port 8550 had no listener during my runs (not touched). `git status --short` is identical before/after TTS, preview, final and reel jobs (`ref/server/git_*`), apart from the baseline untracked entries.
- Production ffmpeg detection: first preflight regex matched steamwebhelper command lines (false positive); the guard script uses Name = ffmpeg.exe outside D:\\bench.
- GrabCut cut-outs are rough (a patch of wall stays attached to Giovanni); plate for the empty room is a stand-in. This limits CAM-02, HI-02, LAY-05, HI-03, AN-02, DIA-04, DIA-05.
- No footage, maps, interview or UV material exists locally: AN-04, STATIC-05/06, FOOT-01, DIA-06 are stand-ins.
- Reel is longer than the 4-8 s/segment x 56 minimum (some segments 4.5-7 s, fine) but the segments only use the Arnolfini/Van der Paele images.
- Pull-backs in the final are 2-5x faster than the channel's because of the 90 s budget.
- The last frame of final_demo is black by design (0.9 s fade-out), so a strict "no black frame" check sees one.
- The reference strip font (Futura-like) is approximated with Century Gothic; the on-screen strip position was moved (see Layout rule).
"""
open(f"{H}/capabilities_report.md", "w").write(md)
print("report written")
