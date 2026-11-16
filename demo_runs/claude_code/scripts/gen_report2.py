import json, os, sys, re
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{H}/scripts")
from cap_rows import R
reel = {s["id"]: s for s in json.load(open(f"{H}/ref/server/technique_reel_segments.json"))}
shots = json.load(open(f"{H}/v2/shots_final.json")); T = json.load(open(f"{H}/v2/timing2.json"))
rd = lambda p: open(f"{H}/{p}").read().strip() if os.path.exists(f"{H}/{p}") else "(not available)"
mmss = lambda t: "%d:%02d" % (t // 60, t % 60)
by = {}
for s in shots:
    for i in s["ids"]:
        by.setdefault(i, []).append(s["t0"])
rows = []; cnt = {"done": 0, "partial": 0, "not done": 0}
for id_, (st, method, refm, mine, fin, rate, block) in R.items():
    cnt[st] += 1; r = reel[id_]
    w = "reel %s-%s" % (mmss(r["t0"]), mmss(r["t1"]))
    if id_ in by:
        ts = by[id_]; w += "; final_demo: " + ", ".join(mmss(t) for t in ts[:5]) + (" (+%d more)" % (len(ts) - 5) if len(ts) > 5 else "")
    else:
        w += "; not in final_demo"
    rows.append("| %s | %s | %s | %s | %s | %s | %d | %s |" % (id_, st, method, refm, mine, w, rate, block or "-"))
rt = json.load(open(f"{H}/ref/server/render_times2.json"))
md = f"""# Capabilities report (claude_code agent) - v2 long-form episode

Deliverables (Mac folder `demo_runs/claude_code/`): `final_demo.mp4` ({T['end']/60:.1f} min = {T['end']:.0f} s, 1920x1080, 30 fps, H.264 + AAC + a soft mov_text subtitle track, NO burned-in subtitles), `subtitles.srt` (sidecar), `script.txt`, `sources.md`, `timeline.json`, `contact_sheet_NN.jpg` (every 10 s, pages of 40), `reference_compare.jpg` (13 pairs), `technique_reel.mp4` (unchanged from v1, 56 segments), this report. v1 (90 s) is preserved in `v1_90s/`.

## Counts (56 catalogue records; unchanged reel statuses, see table)
**done {cnt['done']}, partial {cnt['partial']}, not done {cnt['not done']}.** The reel was not re-rendered. "Where" shows both the reel segment and every place the technique appears in the new `final_demo.mp4` (timestamps from `timeline.json`).

## Catalogue table
Rating 1-5 (5 = indistinguishable from the channel).

| Record | Status | Method / libraries | Reference (measured) | Mine | Where | Rating | Blocker / what it would take |
|---|---|---|---|---|---|---|---|
""" + "\n".join(rows) + f"""

## What the long-form edit does (v2) and how it matches the reference
- **Structure:** cold open from frame 0 on the couple (push-in 1.14x then the 3.0x ease-out pull-back), main title card after the cold open (2.6 s), then six black chapter cards and a closing without a card. Chapter cards follow the measured spec: black, 2.0 s, text pops over 0.1 s at +0.2 s and leaves at +1.7 s, hard cut, centred caps at y 88 %.
- **Labels:** detail strip at the measured position (y 79-93 %, about 80 % opacity, right end fades, text at x = 7 %). Single line for details of the main painting (GREEN WOOL GOWN, MINIVER LINING ...); two lines (title / ARTIST, YEAR) only for other works (e.g. MAN IN A BLUE CHAPERON / JAN VAN EYCK, C.1430). No subtitles on screen, so no layout conflict remains.
- **Annotations:** AN-05 dimension annotation (82 cm / 60 cm lines, OIL ON OAK PANEL) at the size-and-medium sentence (dimensions from the National Gallery page, cited in sources.md); AN-01 circles with the measured spec (diameter 23 % W scaled to zoom, stroke 0.7 % W, 0.5 s draw, ~2 s hold, 0.4 s fade) on the dog, the settle carving, the brush, the orange, the Passion roundels, and on the lit and the snuffed-out candle; spotlights with surround floor 0.20 (reference about 15-25 %), 0.5 s ramps.
- **Closing:** recap labels as plain white text without strip (DOG, ROUNDELS, CANDLE, MOURNING DRESS?) synced to the words, with the 5.8x ease-out pull-out over 40 s.
- **Opening plate decision:** I kept the clean detail-drift opening and did NOT use the room-then-figures reveal in the episode (the v1 inpainted empty-room plate was smeared at 1080p; no attempt this round beat that, so the reveal stays in the reel only as a partial).
- **No dissolve** in the main episode (none in the reference episode); all cuts are hard cuts.
- **Context images (all Commons, PD/CC0):** Ghent Altarpiece, Berlin portrait of the man, Man in a Blue Chaperon, Man in a Red Turban, Rogier woman, Bruges etching, Mary of Burgundy tomb (dog at the feet), Massys Moneylender, Dürer 1500, Las Meninas. Author/licence/URL in `sources.md` and `timeline.json`.

## Pacing and camera speeds as actually rendered vs the channel (measured on the delivered mp4)
```
{rd('ref/qa_pacing2.txt')}
```
Reference numbers: shot-length median 7.0 s (mean 15.9 s), stills in sequence 4.0 s each, hard cuts, opening pull-back 3.0x/17.9 s ease-out, matte-to-fill-width 1.59x/4.9 s ease-in, mirror push 3.57x/~11 s ease-in-out, closing pull-out 5.8x/40 s ease-out. My median is longer than the channel's because my narration holds one image over several sentences more often than the channel's cut detector counts shots (the reference detector also misses slow moves), and I did not cut more to force the number.

## Audio and sync
- **TTS:** local Chatterbox through `synthesize()` in three jobs (chapter groups), exaggeration 0.35, cfg_weight 0.5, temperature 0.7 (module default), seed 42, voice machiavelli_ref.wav, one lock per job with expected end time in owner.txt: job 1 {rd('v2/voice/tts1.log').splitlines()[-3] if False else ''}1069 s, job 2 943 s, job 3 1005 s (92 beats, 1,971 words).
- **atempo = {T['atempo']}.** The model's raw speech is already {T['wpm_speech_only']} wpm, faster than the 135-145 target, and atempo cannot go below 1.0. I therefore fixed atempo at 1.0 and reached the target by pauses: 0.65 s between beats, 0.8 s around chapter cards, 3.0 s of title/card gaps. Measured speech rate first word to last word including pauses and cards: **{T['wpm_first_to_last_incl_pauses_and_cards']} wpm**; speech-only {T['wpm_speech_only']} wpm.
- **Sync method:** beat starts are exact chunk boundaries (chunking equals the beat list, asserted before each job); word times come from forced alignment (faster-whisper small.en, int8, CPU) run on the Mac with the venv and model cache inside the workspace (deleted afterwards): {T['alignment']['matched']} of {T['alignment']['total']} script words matched ASR words, the rest interpolated. Chatterbox's even-spread estimates differ from alignment by a median 0.27 s, p90 0.67 s, max 1.37 s, so they would NOT have met the +-0.25 s target.
- **Highlight onsets measured in the delivered mp4 (onset = 10 % of the change):**

{rd('ref/qa_sync2.txt')}

- **Loudness** (ffmpeg ebur128 on final_demo.mp4):
```
{rd('ref/loudness2.txt')}
```
- **Music:** numpy-synthesised pad + room tone (no external file), -24 dB under voice RMS, ducked 4 dB under speech; two-pass loudnorm to -15 LUFS / -1.5 dBTP.

## Smoothness (jitter)
Per-frame ECC affine residual vs a Savitzky-Golay fit, in 1080p-equivalent pixels:
```
{rd('ref/qa_jitter2.txt')}
```

## vmetrics
{rd('ref/vmetrics2.txt')}

## Timing
{rd('ref/timing_table2.md')}

## Problems and limits (honest)
{rd('ref/problems2.md')}
"""
open(f"{H}/capabilities_report.md", "w").write(md)
print("report written", len(md))
