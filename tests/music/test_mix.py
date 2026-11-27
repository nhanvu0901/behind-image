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
    cue = {"start": 0, "end": 8, "offset": 0, "level": "normal", "role": "bed", "pauses": [{"start": 2, "end": 4}, {"start": 6, "end": 8}], "fade_in": 0, "fade_out": 0}
    run(*mix_command(["ffmpeg"], voice, [(music, cue)], out, 8))
    run("ffmpeg", "-v", "error", "-i", str(out), "-c:a", "pcm_s16le", "-y", str(decoded))
    speech = tone_level(decoded, 0.6, 1.6, 200)
    pause = tone_level(decoded, 3, 3.8, 200)
    assert 1.7 < pause / speech < 2.3, (speech, pause)
    assert 8 < tone_level(decoded, 0.6, 1.6, 1000) / speech < 12
    measure = run("ffmpeg", "-hide_banner", "-i", str(out), "-filter_complex", "ebur128=peak=true", "-f", "null", "-").stderr
    loudness = float(re.findall(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS", measure)[-1])
    peak = float(re.findall(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", measure)[-1])
    print("measured mix: %.1f LUFS, %.1f dBTP; music speech %.1f, pause %.1f" % (loudness, peak, speech, pause))
    assert -15 <= loudness <= -13
    assert peak <= -1


def test_voice_measurement_excludes_loud_audio_outside_speech(tmp_path):
    from bti.music.mix import _measure
    voice = tmp_path / "voice.wav"
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000:duration=8",
        "-af", "volume='if(between(t,2,6),4,1)':eval=frame", "-y", str(voice))
    whole, _ = _measure(["ffmpeg"], str(voice))
    speech, _ = _measure(["ffmpeg"], str(voice), speech=[(0, 1.8), (6.2, 8)], temp_dir=tmp_path)
    assert whole - speech > 7


@pytest.mark.parametrize("role,level,offset", [
    ("bed", "soft", -23), ("bed", "strong", -17),
    ("swell", "normal", -8), ("ident", "normal", -8), ("ending", "normal", -12),
])
def test_role_and_named_level_place_music_relative_to_voice(tmp_path, role, level, offset):
    voice, music, out, decoded = [tmp_path / name for name in ("voice.wav", "music.wav", "mix.m4a", "decoded.wav")]
    for path, freq in [(voice, 1000), (music, 200)]:
        run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration=4", "-y", str(path))
    cue = {"start": 0, "end": 4, "offset": 0, "level": level, "role": role, "fade_in": 0, "fade_out": 0}
    run(*mix_command(["ffmpeg"], voice, [(music, cue)], out, 4))
    run("ffmpeg", "-v", "error", "-i", str(out), "-c:a", "pcm_s16le", "-y", str(decoded))
    ratio = tone_level(decoded, 1, 3, 200) / tone_level(decoded, 1, 3, 1000)
    assert 0.8 < ratio / (10 ** (offset / 20)) < 1.25


def test_true_peak_limiter_preserves_programme_loudness_with_transient(tmp_path):
    voice, music, out = [tmp_path / name for name in ("voice.wav", "music.wav", "mix.m4a")]
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000:duration=20",
        "-af", "volume='if(between(t,2,2.02),8,1)':eval=frame", "-c:a", "pcm_f32le", "-y", str(voice))
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=200:sample_rate=48000:duration=20", "-y", str(music))
    cue = {"start": 0, "end": 20, "offset": 0, "level": "normal", "role": "swell", "fade_in": 0, "fade_out": 0}
    run(*mix_command(["ffmpeg"], voice, [(music, cue)], out, 20))
    measured = run("ffmpeg", "-hide_banner", "-i", str(out), "-filter_complex", "ebur128=peak=true", "-f", "null", "-").stderr
    loud = float(re.findall(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS", measured)[-1])
    peak = float(re.findall(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", measured)[-1])
    assert abs(loud + 14) <= 0.5
    assert peak <= -1


def test_bed_leveller_keeps_quiet_and_loud_passages_near_target(tmp_path):
    voice, music, out, decoded = [tmp_path / name for name in ("voice.wav", "music.wav", "mix.m4a", "decoded.wav")]
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000:duration=32", "-y", str(voice))
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=200:sample_rate=48000:duration=32",
        "-af", "volume='if(lt(t,16),0.05,1)':eval=frame", "-y", str(music))
    cue = {"start": 0, "end": 32, "offset": 0, "level": "normal", "role": "bed", "fade_in": 0, "fade_out": 0}
    run(*mix_command(["ffmpeg"], voice, [(music, cue)], out, 32))
    run("ffmpeg", "-v", "error", "-i", str(out), "-c:a", "pcm_s16le", "-y", str(decoded))
    for a, b in ((3, 13), (19, 29)):
        ratio = tone_level(decoded, a, b, 200) / tone_level(decoded, a, b, 1000)
        assert 0.70 < ratio / 0.1 < 1.41


def test_swell_retains_its_own_dynamics(tmp_path):
    voice, music, out, decoded = [tmp_path / name for name in ("voice.wav", "music.wav", "mix.m4a", "decoded.wav")]
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000:duration=32", "-y", str(voice))
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=200:sample_rate=48000:duration=32",
        "-af", "volume='if(lt(t,16),0.05,1)':eval=frame", "-y", str(music))
    cue = {"start": 0, "end": 32, "offset": 0, "level": "normal", "role": "swell", "fade_in": 0, "fade_out": 0}
    run(*mix_command(["ffmpeg"], voice, [(music, cue)], out, 32))
    run("ffmpeg", "-v", "error", "-i", str(out), "-c:a", "pcm_s16le", "-y", str(decoded))
    quiet, loud = tone_level(decoded, 3, 13, 200), tone_level(decoded, 19, 29, 200)
    assert loud / quiet > 15


def test_stereo_music_is_not_downmixed_away_by_mono_voice(tmp_path):
    voice, music, out, decoded = [tmp_path / name for name in ("voice.wav", "music.wav", "mix.m4a", "decoded.wav")]
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000:duration=6", "-y", str(voice))
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=200:sample_rate=48000:duration=6",
        "-af", "pan=stereo|c0=c0|c1=-1*c0", "-y", str(music))
    cue = {"start": 0, "end": 6, "offset": 0, "level": "normal", "role": "swell", "fade_in": 0, "fade_out": 0}
    run(*mix_command(["ffmpeg"], voice, [(music, cue)], out, 6))
    run("ffmpeg", "-v", "error", "-i", str(out), "-c:a", "pcm_s16le", "-y", str(decoded))
    with wave.open(str(decoded), 'rb') as audio:
        assert audio.getnchannels() == 2
    assert tone_level(decoded, 1, 5, 200) > 100
