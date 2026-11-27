# Music levels: Arnolfini acceptance

The follow-up uses the copied `arnolfini-v3` voice, timing and storyboard, and the same four real recordings. The cue sheet is `.scratch/agy_tasks/musicmix/followup-cues.json`: ident 50.731–60 s, a single 271 s bed from 63–334 s with offset zero, swell 400–412 s, and ending 610–672.727 s, all at `normal`. The bed is levelled before the pause envelope; the other roles retain their recordings' dynamics. Measurements use FFmpeg EBU R128. The stem column is measured before the common programme gain and limiter, so its difference from the voice shows cue placement.

| Interval, seconds | Voice alone LUFS | Music stem LUFS | Music relative to speech, LU | Finished mix LUFS |
|---|---:|---:|---:|---:|
| Speech 90–95 | -19.2 | -41.7 | -22.5 | -14.1 |
| Speech 170–175 | -18.8 | -39.4 | -20.2 | -13.6 |
| Speech 260–265 | -20.1 | -39.0 | -19.8 | -15.0 |
| Pause 140.7–143.7 | below gate | -33.9 | -14.7 | -28.6 |
| Pause 222.3–225.5 | -51.2 | -35.5 | -16.3 | -30.2 |
| Pause 306.4–309.3 | below gate | -32.3 | -13.1 | -27.0 |

All six sampled levels are within 3 LU of their role targets. The full levelled bed, before its intentional fades and pause boost, was scanned in 2,611 overlapping 10 s windows at 0.1 s starting intervals. The worst window was 21.8–31.8 s into the bed (84.8–94.8 s of the video), at **-21.7 LU relative to the voice**, a 1.7 LU deviation from its -20 LU target. The windows touching the one-second cue fades were also measured separately; their largest deviation was 0.9 LU. These scans use 0.1 s intervals for window starts, not every real-valued start. The same unsplit excerpt before levelling had a speech sample at -29.4 LU and pause samples at -18.6 and -17.2 LU relative to speech.

The dry speech measured -19.2 LUFS, and the unmastered programme -19.3 LUFS / -2.8 dBTP. One **+5.3 dB linear gain** followed by a 4× oversampled true-peak limiter (1 ms attack, 40 ms release, no make-up gain) produced **-14.2 LUFS / -1.3 dBTP**. Loudness range was **3.0 LU before and 3.0 LU after**. The largest measured limiter attenuation was **3.94 dB**, measured from pre/post limiter RMS in 1 ms stereo windows; repeating the scan down to -66 dBFS gave the same maximum. The voice alone also needs limiting: with the same stereo conversion and +5.3 dB gain its peak measured **+2.5 dBTP**, 3.5 dB above the -1 dBTP ceiling.

| Speech start | Voice short-term LUFS | Final short-term LUFS | Voice plus 5.3 dB | Difference |
|---|---:|---:|---:|---:|
| 90 s | -20.2 | -15.0 | -14.9 | -0.1 LU |
| 170 s | -18.3 | -13.2 | -13.0 | -0.2 LU |
| 260 s | -19.6 | -14.5 | -14.3 | -0.2 LU |

These 3 s short-term loudness readings indicate the three samples retain the speech level to within 0.2 LU after allowing for the common gain; the final mix also contains music. This is a measurement, not a listening test. Stereo music is retained when the voice is mono. The earlier peak-only linear normalization produced -21.0 LUFS; the limiter removes that regression while preserving the programme's overall loudness range.

## Wikimedia category run

The run used a new library inside the Windows snapshot, limited to 40 additions and 500 MB. It added 17 public-domain recordings and accounted for 181.4 MiB of downloads: 4 from `Audio files of the Open Goldberg Variations`, 5 from `Audio files of Open Well-Tempered Clavier, Book 1`, and 8 from `Musopen`. Five records explicitly identify Kimiko Ishizaka as performer from their own descriptions; unknown performers were omitted. Several files were skipped because their recording licence was missing or ambiguous, or the file exceeded 20 MiB. The run encountered 429/503 responses, including 600-second waits. It waited and resumed from its checkpoint; after the last wait the resumed run added one more file and stopped at the requested demonstration limit, preserving the remaining queue. The later configured categories, including the Musopen Kickstarter collection, remain queued rather than being claimed as tested. The snapshot was rebuilt for the follow-up, so its downloaded audio was removed; the fetched index and checkpoint remain in `.scratch/agy_tasks/musicmix/`. The first run used the original one-second retry delay when the server explicitly returned that value; the implementation now backs off progressively (at least 5 seconds) and waits at least 5 seconds between downloads.

## Verification

Windows snapshot, one folder per run: `tests/draft` 643 passed; `tests/picks` 506 passed; `tests/editor` 534 passed; `tests/auto` 270 passed; `tests/ops` 561 passed; `tests/cli` 132 passed; `tests/export` 89 passed and 2 skipped; `tests/identity` 106 passed; `tests/music` 52 passed; `tests/engine -m "not slow"` 854 passed, 14 skipped and 168 deselected. The two export skips are the separately marked server-render tests. All ten folders were run because the export and music modules are reached through the app and its shared project workflows.

The three Windows generator checks (`bti.cli.docgen`, `bti.ops.doc`, `bti.editor.hints`) passed. On the Mac the requested Node suites passed 505 tests with one skip; the skipped code-list test requires a worktree `.venv/bin/python`. No JavaScript was changed, and no new issue code was introduced. `git diff --check` passed.

Follow-up verification after the leveller and limiter changes: Windows `tests/music` **56 passed**; `tests/export` **89 passed, 2 skipped** (the separately marked server-render tests). `git diff --check` passed.
