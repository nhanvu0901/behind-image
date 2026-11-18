# Fix D17: Voice parts overrun & True-Peak Limiter

## Cause
1. **Part overruns (31, 37, 30 minutes)**:
   - Parts were previously sized by a fixed character count (`part_chars: 4000`), which was based on an outdated estimate formula (`chars / 15.0 * 4.1 + 60`).
   - On the real server hardware, model loading took ~120s and synthesis cost was ~0.55s per character. Sizing 4000 characters resulted in `120 + 4000 * 0.55 = 2320` seconds (~38.6 minutes), causing parts to overrun the server's 30-minute rule.
   - There was no rolling feedback mechanism to adapt to real machine performance, and no clean-stop threshold before the hard timeout.
2. **True peak too high (-1.06 dBTP vs target <= -1.5 dBTP)**:
   - Although ffmpeg `loudnorm` targeted TP=-1.5, in `linear=true` mode loudnorm applies static gain across the file and does not dynamically limit peaks that exceed target TP.
   - Subsequent AAC lossy perceptual compression (`-c:a aac -b:a 192k`) introduces inter-sample peaks (and decompression reconstruction peaks) that overshoot by 0.2 to 0.5 dB, pushing the final true peak to -1.06 dBTP.
   - The assembly step had no true-peak limiter after loudnorm and treated true-peak excess as a non-error.

## Changes Made
- `config/voice.json:7-8`: Removed `part_chars: 4000`. Set `target_minutes: 18`, `max_part_minutes: 25`, and `estimate: {"load_seconds": 120, "seconds_per_character": 0.55, "chars_per_audio_second": 15.0}`.
- `bti/voice/config.py:26-35`: Updated `_BUILTIN` defaults to match `target_minutes: 18`, `max_part_minutes: 25`, `load_seconds: 120`, `seconds_per_character: 0.55`.
- `bti/voice/stats.py:1-68` (new file): Implemented `load_stats`, `record_part_stats`, and `get_effective_estimate`. Maintained rolling window of the last 20 parts and computed rolling medians for `load_seconds` and `seconds_per_character`. Stored in `run/voice_stats.json`.
- `bti/voice/planner.py:46-128`: Reimplemented `group_parts` to size parts by compute estimate `load_seconds + chars * seconds_per_character` targeting 18 minutes, capping every planned part at 25 minutes. Supported legacy `part_chars` parameter when explicitly passed. Reimplemented `estimate_seconds` using `get_effective_estimate`.
- `bti/voice/status.py:127-129`: Updated parts count calculation in `describe()` to pass `cfg` to `planner.group_parts`.
- `bti/voice/providers/fake.py:41-72`: Added injectable `clock` and `part_stop_seconds` (default 28*60). When `clock() - t0 >= part_stop_seconds`, finished the current chunk, set `self.stopped_cleanly = True`, and stopped.
- `bti/voice/providers/chatterbox.py:60-115`: Added `part_stop_seconds` check in `on_line`. When elapsed time >= 28 minutes, finished current chunk and signaled clean stop. Avoided raising `voice_worker_failed` on clean stop.
- `bti/voice/run.py:65-145`: In `synth_run`, detected clean stop. Unspoken chunks are not marked as failures; instead, a new continuation part is added dynamically to the job (`synth-{k}b`). Added stats recording after parts.
- `bti/voice/assemble.py:148-195`: In `normalise`, added an `alimiter` filter with `level=false` and a margin to prevent AAC overshoot. In `assemble`, verified measured true peak <= -1.5 dBTP; raised `VoiceError("voice_assemble_failed")` if peak exceeds -1.5 dBTP.
- `tests/voice/test_planner_plan.py:18-87`: Updated estimate speed test; added tests for 18-minute targeting, 25-minute cap, rolling median of 20 parts, and learning from stats.
- `tests/voice/test_assemble.py:76-102`: Added tests for true-peak limiter holding mix <= -1.5 dBTP, and mix exceeding -1.5 raising `voice_assemble_failed`.
- `tests/voice/test_run.py:277-318`: Added `test_clean_stop_past_28_minutes_finishes_sentence_and_creates_new_part`.

## Neighbouring cases covered
- Chunks that individually fit well below the 25-minute cap.
- Tail chunks joining the last part only when the resulting estimate stays under the 25-minute cap and tail is small (<25% of target).
- Rolling median handles odd and even counts (up to 20 parts), drops older samples beyond 20.
- Missing or corrupted `run/voice_stats.json` cleanly falls back to config defaults.
- Clean stop past 28 minutes creates continuation parts both in long-job context (`ctx._job`) and preserves deferred chunks in direct test runners.
- True-peak limiter applies an adaptive margin retry if AAC encoding slightly overshoots, ensuring strict enforcement.

## Numbers requested by contract
- Target part time: **18 minutes** (1080 s)
- Hard planned part cap: **25 minutes** (1500 s)
- Defaults: `load_seconds: 120`, `seconds_per_character: 0.55`
- Rolling stats window: **20 parts**
- Clean stop threshold: **28 minutes** (1680 s)
- True peak limit: **<= -1.5 dBTP** (error if exceeded)

## Tests and Results
- Environment: Windows server (`winbox-lan`) executed via `tools/deploy/snapshot_test.sh dvoice -- tests/voice -q` inside isolated snapshot `D:\code\behind-the-image\run\snap-dvoice\`.
- Result: **79 passed, 1 skipped, 1 warning in 67.70s**.
  - `tests/voice/test_speak.py`: 17 passed.
  - `tests/voice/test_chunks.py`: 9 passed.
  - `tests/voice/test_planner_plan.py`: 9 passed (including speed estimate, 18-minute targeting, 25-minute cap, 20-part rolling median, and stats learning).
  - `tests/voice/test_assemble.py`: 10 passed (including true-peak limiter <= -1.5 dBTP and assembly error on exceeding peak).
  - `tests/voice/test_run.py`: 20 passed (including clean stop past 28 minutes and dynamic part continuation).
  - `tests/voice/test_align.py`: 6 passed.
  - `tests/voice/test_api.py`: 8 passed.
  - `tests/voice/test_chatterbox_provider.py`: 4 passed.
  - `tests/voice/test_server.py`: 1 skipped (marked server).

## Needs another worker
- None.

## Objections
- None.

## Anything left open
- None.
