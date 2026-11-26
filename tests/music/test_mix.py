import math
import re
import shutil
import subprocess
import wave

import pytest

from bti.music.mix import mix_command

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg unavailable")


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def tone_level(path, start, end, frequency):
    with wave.open(str(path), "rb") as audio:
        rate = audio.getframerate()
        channels = audio.getnchannels()
        audio.setpos(int(start * rate))
        data = audio.readframes(int((end - start) * rate))
    import struct
    samples = struct.unpack("<%dh" % (len(data) // 2), data)[::channels]
    real = sum(x * math.cos(2 * math.pi * frequency * i / rate) for i, x in enumerate(samples))
    imag = sum(x * math.sin(2 * math.pi * frequency * i / rate) for i, x in enumerate(samples))
    return math.hypot(real, imag) / len(samples)


def test_real_mix_ducks_music_and_normalises_programme(tmp_path):
    voice, music, out, decoded = [tmp_path / name for name in ("voice.wav", "music.wav", "mix.m4a", "decoded.wav")]
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000:duration=8",
        "-af", "volume=0:enable='between(t,2,4)+between(t,6,8)'", "-y", str(voice))
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=200:sample_rate=48000:duration=8", "-y", str(music))
    cue = {"start": 0, "end": 8, "offset": 0, "level_db": -14, "fade_in": 0, "fade_out": 0}
    run(*mix_command(["ffmpeg"], voice, [(music, cue)], out, 8))
    run("ffmpeg", "-v", "error", "-i", str(out), "-c:a", "pcm_s16le", "-y", str(decoded))
    speech = tone_level(decoded, 0.6, 1.6, 200)
    pause = tone_level(decoded, 3, 3.8, 200)
    assert pause > speech * 1.5, (speech, pause)
    assert tone_level(decoded, 0.6, 1.6, 1000) > speech * 10
    measure = run("ffmpeg", "-hide_banner", "-i", str(out), "-filter_complex", "ebur128=peak=true", "-f", "null", "-").stderr
    loudness = float(re.findall(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS", measure)[-1])
    peak = float(re.findall(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", measure)[-1])
    print("measured mix: %.1f LUFS, %.1f dBTP; music speech %.1f, pause %.1f" % (loudness, peak, speech, pause))
    assert -15 <= loudness <= -13
    assert peak <= -1
