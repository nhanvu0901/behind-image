"""The real provider against a scripted child process (no model): the job file, the protocol lines, the moving of files."""
import json
import wave

from bti.voice import files
from bti.voice.chunks import build_chunks
from bti.voice.config import load_voice_config, voice_worker, aligner_config
from bti.voice.providers.chatterbox import ChatterboxProvider, wav_seconds
from bti.voice.providers.fake import write_wav, tone_samples
from conftest import FakeCtx, make_narration

W = {"python": "py", "worker": "w.py", "reference": "/x/ref.wav", "exaggeration": 0.35, "cfg_weight": 0.5, "temperature": 0.7, "device": "cpu"}


def chunks():
    return build_chunks(make_narration(), {}, load_voice_config(), "s")[:3]


def test_job_file_has_one_seed_per_chunk_and_the_settings(tmp_path):
    p = ChatterboxProvider(W)
    cs = chunks()
    job = p.job(cs, tmp_path / "out")
    assert [c["seed"] for c in job["chunks"]] == [c.seed for c in cs]
    assert [c["text"] for c in job["chunks"]] == [c.spoken for c in cs]
    assert job["audio_prompt"] == "/x/ref.wav" and job["temperature"] == 0.7 and job["chunks"][0]["exaggeration"] == 0.35
    assert p.command(tmp_path / "job.json") == ["py", "-B", "w.py", str(tmp_path / "job.json")]


def test_synth_moves_files_and_reports_failures(tmp_path):
    p = ChatterboxProvider(W)
    cs = chunks()
    ctx = FakeCtx(tmp_path / "w")

    def child(cmd, on_line):
        job = json.loads(open(cmd[-1], encoding="utf-8").read())
        out = tmp_path / "w" / "chatterbox" / "out"
        for i in (0, 2):                               # chunk 1 fails
            write_wav(out / f"chunk_{i:05d}.wav", tone_samples("hello there", 3))
            on_line(json.dumps({"i": i, "sec": 0.5, "sr": 24000}))
        on_line(json.dumps({"i": 1, "error": "boom"}))
        on_line("some log line")
        return 0
    ctx.on_process = child
    res = p.synth(cs, files.chunks_dir(tmp_path), ctx)
    assert res[cs[0].id]["ok"] and res[cs[2].id]["ok"]
    assert not res[cs[1].id]["ok"] and res[cs[1].id]["error"] == "boom"
    assert wav_seconds(files.chunk_path(tmp_path, cs[0].id)) > 0
    assert ctx.progress_log[-1][0] == 1.0


def test_worker_crash_with_nothing_written_raises(tmp_path):
    import pytest
    from bti.voice.errors import VoiceError
    ctx = FakeCtx(tmp_path / "w")
    ctx.on_process = lambda cmd, on_line: 3
    with pytest.raises(VoiceError) as e:
        ChatterboxProvider(W).synth(chunks(), files.chunks_dir(tmp_path), ctx)
    assert e.value.code == "voice_worker_failed"


def test_server_config_keys():
    srv = {"voice": {"python": "p", "worker": "w", "reference_voice": "r.wav", "temperature": 0.6},
           "aligner": {"python": "ap", "model": "small.en"}}
    w = voice_worker(srv)
    assert w["reference"] == "r.wav" and w["temperature"] == 0.6 and w["exaggeration"] == 0.35
    assert aligner_config(srv)["model"] == "small.en"
    assert voice_worker({"voice": None}) is None and aligner_config({"aligner": None}) is None
