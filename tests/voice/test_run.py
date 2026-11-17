"""The whole run with the fake voice and the even aligner, through a real long-job manager instance."""
import json

import pytest

from bti.longjob import manager as _unused  # noqa: F401  (the module must exist)
from bti.longjob.manager import LongJobManager
from bti.voice import describe, files, run as voice_run, state
from bti.voice.errors import VoiceError
from bti.voice.providers import fake as fakemod
from conftest import needs_ffmpeg, write_project

pytestmark = needs_ffmpeg


@pytest.fixture()
def mgr(tmp_path):
    m = LongJobManager()
    m.configure(projects_root=tmp_path)
    return m


def go(project, mgr, cfg, **kw):
    job = voice_run.start(project, project.name, cfg=cfg, server={}, provider_name="fake", manager=mgr, **kw)
    return mgr.wait(job, 120)


def test_full_run_produces_the_files_and_a_fresh_state(project, mgr, cfg):
    assert describe(project, cfg=cfg, server={}, provider_name="fake")["state"] == "none"
    rec = go(project, mgr, cfg)
    assert rec["state"] == "done", rec
    keys = [p["key"] for p in rec["parts"]]
    assert keys[-2:] == ["assemble", "align"] and keys[0] == "synth-1" and "synth-retry" in keys
    assert files.mix_path(project).is_file() and files.timing_path(project).is_file() and files.dry_path(project).is_file()
    m = files.read_manifest(project)
    assert m["timing_quality"] == "even" and m["timing"]["match_rate"] is None
    t = json.loads(files.timing_path(project).read_text(encoding="utf-8"))
    from bti.script import store
    n = store.load_narration(project)
    expect = [w for ch in n.chapters for b in ch.beats for w in b.text.split()]
    assert [w["w"] for w in t["words"]] == expect
    assert [b["id"] for b in t["beats"]] == ["b0001", "b0002", "b0003", "b0004"]
    for b in t["beats"]:
        assert b["w0"] < b["w1"] and b["start"] == t["words"][b["w0"]]["s"] and b["end"] == t["words"][b["w1"] - 1]["e"]
    assert [c["id"] for c in t["chapters"]] == ["c1", "c2"] and t["chapters"][1]["card"] is True
    assert t["chapters"][0]["start"] == 0 and t["chapters"][-1]["end"] == t["duration"]
    assert t["chapters"][1]["card_end"] - t["chapters"][1]["card_start"] > 2.0
    assert describe(project, cfg=cfg, server={}, provider_name="fake")["state"] == "done"


def test_second_run_does_nothing_and_a_change_redoes_only_that_sentence(project, mgr, cfg, tmp_path):
    go(project, mgr, cfg)
    ids_before = set(p.stem for p in files.chunks_dir(project).glob("*.wav"))
    rec = go(project, mgr, cfg)
    assert rec["state"] == "done"
    assert all(p["state"] == "done" for p in rec["parts"])
    # change one beat: unapprove-and-reapprove through the store, as the script page would
    from bti.script import store
    n = store.load_narration(project)
    n.chapters[1].beats[1].text = "Look at the chandelier above the couple, it has a single candle."
    store.save_narration(project, n)
    store.approve(project, "narration", n.rev())
    d = describe(project, cfg=cfg, server={}, provider_name="fake")
    assert d["state"] == "stale" and d["counts"]["changed"] == 1 and d["counts"]["missing"] == 1
    assert "narration_changed" in d["reasons"]
    rec = go(project, mgr, cfg)
    assert rec["state"] == "done"
    ids_after = set(p.stem for p in files.chunks_dir(project).glob("*.wav"))
    assert len(ids_after - ids_before) == 1 and ids_before <= ids_after
    assert describe(project, cfg=cfg, server={}, provider_name="fake")["state"] == "done"


def test_tempo_change_regenerates_only_the_mix(project, mgr, cfg):
    go(project, mgr, cfg)
    before = {p.name: p.stat().st_mtime_ns for p in files.chunks_dir(project).glob("*.wav")}
    files.write_settings(project, {"tempo": 1.1})
    d = describe(project, cfg=cfg, server={}, provider_name="fake")
    assert d["state"] == "stale" and d["counts"]["missing"] == 0 and "mix_settings_changed" in d["reasons"]
    rec = go(project, mgr, cfg)
    assert rec["state"] == "done"
    assert before == {p.name: p.stat().st_mtime_ns for p in files.chunks_dir(project).glob("*.wav")}
    m = files.read_manifest(project)
    assert m["plan"]["settings"]["tempo"] == 1.1


def test_reseed_changes_one_sentence(project, mgr, cfg):
    go(project, mgr, cfg)
    d = describe(project, cfg=cfg, server={}, provider_name="fake")
    target = d["chunks"][1]
    rec = go(project, mgr, cfg, scope=[target["id"]], reseed_ids=[target["id"]])
    assert rec["state"] == "done"
    d2 = describe(project, cfg=cfg, server={}, provider_name="fake")
    assert d2["chunks"][1]["id"] != target["id"] and d2["chunks"][1]["seed"] != target["seed"]
    assert [c["id"] for c in d2["chunks"][2:]] == [c["id"] for c in d["chunks"][2:]]
    assert d2["state"] == "done"


def test_failed_sentence_is_retried_then_reported(project, mgr, cfg, monkeypatch):
    prov = fakemod.FakeProvider(fail={"Look at the chandelier."})
    monkeypatch.setattr("bti.voice.run.resolve", lambda name, server: prov)
    rec = go(project, mgr, cfg)
    assert rec["state"] == "error" and rec["error_code"] == "voice_chunks_failed"
    assert "Look at the chandelier." in rec["error"]
    # retried: the failing chunk was offered in at least two synthesis calls
    flat = [i for call in prov.calls for i in call]
    assert any(flat.count(i) == 2 for i in set(flat))
    # nothing was assembled
    assert not files.mix_path(project).exists()


def test_not_approved_and_not_configured(tmp_path, mgr, cfg):
    d = write_project(tmp_path, "unap", approve=False)
    with pytest.raises(VoiceError) as e:
        voice_run.start(d, "unap", cfg=cfg, server={}, provider_name="fake", manager=mgr)
    assert e.value.code == "narration_not_approved"
    d2 = write_project(tmp_path, "ok2")
    with pytest.raises(VoiceError) as e:
        voice_run.start(d2, "ok2", cfg=cfg, server={}, provider_name="chatterbox", manager=mgr)
    assert e.value.code == "voice_not_configured"


def test_cancel_stops_the_job(project, mgr, cfg, monkeypatch):
    class Slow(fakemod.FakeProvider):
        def synth(self, chunks, dest_dir, ctx, workdir=None):
            import time
            for _ in range(200):
                if ctx.cancelled():
                    return {}
                time.sleep(0.01)
            return super().synth(chunks, dest_dir, ctx, workdir)
    monkeypatch.setattr("bti.voice.run.resolve", lambda name, server: Slow())
    job = voice_run.start(project, project.name, cfg=cfg, server={}, provider_name="fake", manager=mgr)
    import time
    time.sleep(0.2)
    assert mgr.cancel(job)
    rec = mgr.wait(job, 30)
    assert rec["state"] == "cancelled"
    assert not files.mix_path(project).exists()


def test_busy_when_a_job_runs(project, mgr, cfg, monkeypatch):
    from bti.longjob import Busy
    class Slow(fakemod.FakeProvider):
        def synth(self, chunks, dest_dir, ctx, workdir=None):
            import time
            for _ in range(300):
                if ctx.cancelled():
                    return {}
                time.sleep(0.01)
            return {}
    monkeypatch.setattr("bti.voice.run.resolve", lambda name, server: Slow())
    job = voice_run.start(project, project.name, cfg=cfg, server={}, provider_name="fake", manager=mgr)
    with pytest.raises(Busy):
        voice_run.start(project, project.name, cfg=cfg, server={}, provider_name="fake", manager=mgr)
    assert state_running(project, mgr, cfg)
    mgr.cancel(job)
    mgr.wait(job, 30)


def state_running(project, mgr, cfg):
    return describe(project, cfg=cfg, server={}, provider_name="fake", manager=mgr)["state"] == "running"
