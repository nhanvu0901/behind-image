import wave

import numpy as np
import pytest

from bti.voice import assemble, files
from bti.voice.chunks import build_chunks
from bti.voice.config import load_voice_config
from bti.voice.plan import make_plan
from bti.voice.providers.fake import FakeProvider
from conftest import FakeCtx, make_narration, needs_ffmpeg


def test_layout_adds_up_exactly():
    lay = assemble.layout([1.0, 2.0, 0.5], [0.35, 0.2, 3.0], 2.5)
    s = lay["spans"]
    assert s[0] == (0.35, 1.35)
    assert abs(s[1][0] - 1.55) < 1e-9 and abs(s[1][1] - 3.55) < 1e-9
    assert abs(s[2][0] - 6.55) < 1e-9
    assert abs(lay["duration"] - (7.05 + 2.5)) < 1e-9
    assert all(a < b for a, b in zip([x[0] for x in s], [x[0] for x in s][1:]))


def test_layout_in_whole_samples():
    lay = assemble.layout([0.123456], [0.2], 1.0)
    a, b = lay["sample_spans"][0]
    assert a == 9600 and b - a == round(0.123456 * 48000)


def test_parse_loudnorm():
    err = 'junk\n{\n "input_i" : "-20.1",\n "input_tp" : "-3.0"\n}\n'
    assert assemble.parse_loudnorm(err)["input_i"] == "-20.1"
    assert assemble.parse_loudnorm("no json here") is None


def test_pad_is_quiet_and_stereo():
    pad = assemble.make_pad(48000 * 3, 3.0)
    assert pad.shape == (2, 48000 * 3)
    assert 0.01 < float(np.sqrt((pad ** 2).mean())) < 0.2


def test_mix_with_pad_is_under_the_voice():
    t = np.arange(48000 * 4) / 48000
    voice = (0.3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    mix = assemble.mix_with_pad(voice, -24, 0.37, 4.0)
    assert mix.shape == (2, len(voice))
    diff = mix[0] - voice
    assert np.sqrt((diff ** 2).mean()) < 0.3 * np.sqrt((voice ** 2).mean())
    assert float(np.abs(mix).max()) <= 1.0


@needs_ffmpeg
@pytest.mark.parametrize("tempo,pad", [(1.0, False), (1.1, True)])
def test_assemble_end_to_end(project, cfg, tmp_path, tempo, pad):
    files.write_settings(project, {"tempo": tempo, "pad": pad})
    plan = make_plan(project, cfg=cfg, provider="fake")
    ctx = FakeCtx(tmp_path / "w")
    FakeProvider().synth(plan.chunks, files.chunks_dir(project), ctx)
    res = assemble.assemble(project, plan.chunks, plan.settings, cfg, tmp_path / "w", ctx)
    assert files.mix_path(project).is_file() and files.dry_path(project).is_file()
    spans = res["spans"]
    assert len(spans) == len(plan.chunks)
    assert all(a["end"] <= b["start"] for a, b in zip(spans, spans[1:]))
    # the silence before the first chapter after the cold open holds the title card and the chapter card and the first sentence starts after the lead
    first_card = next(i for i, c in enumerate(plan.chunks) if c.gap_kind == "title")
    gap = spans[first_card]["start"] - spans[first_card - 1]["end"]
    assert abs(gap - (cfg["silence"]["title"] + cfg["silence"]["card"])) < 0.01
    assert abs(spans[0]["start"] - cfg["silence"]["lead"]) < 0.01
    with wave.open(str(files.dry_path(project))) as wf:
        assert wf.getframerate() == 48000 and wf.getnchannels() == 1
        assert abs(wf.getnframes() / 48000 - res["duration"]) < 0.01
    # tempo shortens a span by the tempo
    c0 = plan.chunks[0]
    raw = 1.0 * len(c0.spoken) * 0.05
    assert abs((spans[0]["end"] - spans[0]["start"]) - max(raw, 0.1) / tempo) < 0.03
    assert res["loudness"]["i"] is not None and abs(res["loudness"]["i"] - cfg["loudness"]["i"]) < 3.0
    assert res["loudness"]["tp"] is not None and res["loudness"]["tp"] <= -1.5 + 1e-4


@needs_ffmpeg
def test_true_peak_held_at_or_under_minus_one_point_five(project, cfg, tmp_path):
    plan = make_plan(project, cfg=cfg, provider="fake")
    ctx = FakeCtx(tmp_path / "w")
    FakeProvider().synth(plan.chunks, files.chunks_dir(project), ctx)
    res = assemble.assemble(project, plan.chunks, plan.settings, cfg, tmp_path / "w", ctx)
    tp = res["loudness"]["tp"]
    assert tp is not None
    # Contract: true-peak limiter holds the mix at or under -1.5 dBTP
    assert tp <= -1.5 + 1e-4, f"True peak {tp} dBTP exceeds -1.5 dBTP"


def test_mix_over_target_true_peak_raises_assemble_error(project, cfg, tmp_path, monkeypatch):
    from bti.voice.errors import VoiceError
    plan = make_plan(project, cfg=cfg, provider="fake")
    ctx = FakeCtx(tmp_path / "w")
    FakeProvider().synth(plan.chunks, files.chunks_dir(project), ctx)
    # Monkeypatch normalise to return tp over -1.5 (e.g. -1.06 like the real run)
    monkeypatch.setattr(assemble, "normalise", lambda src, dst, loud, bitrate: {"i": -15.0, "tp": -1.06, "lra": 3.0})
    with pytest.raises(VoiceError) as exc_info:
        assemble.assemble(project, plan.chunks, plan.settings, cfg, tmp_path / "w", ctx)
    assert exc_info.value.code == "voice_assemble_failed"
    assert "true peak" in str(exc_info.value).lower()


def test_missing_chunk_is_reported_by_sentence(project, cfg, tmp_path):
    from bti.voice.errors import VoiceError
    plan = make_plan(project, cfg=cfg, provider="fake")
    with pytest.raises(VoiceError) as e:
        assemble.assemble(project, plan.chunks, plan.settings, cfg, tmp_path / "w", None, decode=lambda p, t: np.zeros(10, np.float32))
    assert e.value.code == "voice_chunks_missing" and e.value.extra["sentences"]
