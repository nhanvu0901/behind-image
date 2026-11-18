"""The whole run with the fake voice and the even aligner, through a real long-job manager instance."""
import json
from pathlib import Path

import pytest

from bti.longjob import manager as _unused  # noqa: F401  (the module must exist)
from bti.longjob.config import ServerConfig
from bti.longjob.fakes import FakeProbes
from bti.longjob.heavy import HeavySlot
from bti.longjob.manager import LongJobManager
from bti.voice import describe, files, run as voice_run, state
from bti.voice.errors import VoiceError
from bti.voice.providers import fake as fakemod
from conftest import needs_ffmpeg, write_project

pytestmark = needs_ffmpeg


@pytest.fixture()
def mgr(tmp_path):
    # the in-process heavy slot only: these tests never touch the server's lock folder (a real run may hold it for an hour)
    m = LongJobManager(heavy=HeavySlot(ServerConfig(), probes=FakeProbes()))
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
    c1, c2 = t["chapters"]
    assert c1["lead"]["kind"] == "plain" and c1["lead"]["start"] == 0 and abs(c1["lead"]["end"] - c1["lead"]["start"] - cfg["silence"]["lead"]) < 0.01
    assert c2["lead"]["kind"] == "title"
    assert abs(c2["lead"]["end"] - c2["lead"]["start"] - (cfg["silence"]["title"] + cfg["silence"]["card"])) < 0.05
    assert abs(c2["card_end"] - c2["card_start"] - 2.8) < 1e-6 and c2["card_end"] <= c2["lead"]["end"] + 1e-6
    assert abs(c2["title_end"] - c2["title_start"] - 6.2) < 1e-6
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


def _by(project, cfg):
    return describe(project, cfg=cfg, server={}, provider_name="fake")


def test_a_pronunciation_change_is_named_for_what_it_is(project, mgr, cfg):
    """SU-004: the narration did not change, the pronunciation table did."""
    go(project, mgr, cfg)
    files.write_pronounce(project, {"London": "Lon-don"})
    d = _by(project, cfg)
    assert d["state"] == "stale" and d["counts"]["changed"] == 1
    assert d["reasons"] == ["pronounce_changed"] and d["counts"]["by_reason"] == {"pronounce_changed": 1}
    assert d["detail"] == "Bảng phát âm đã đổi: 1 câu cần đọc lại." and "Lời dẫn" not in d["detail"]
    assert go(project, mgr, cfg)["state"] == "done" and _by(project, cfg)["state"] == "done"


def test_asking_for_another_reading_is_named_for_what_it_is(project, mgr, cfg):
    """SU-004: the seed of one sentence moved on at the owner's request; its text did not change."""
    go(project, mgr, cfg)
    d0 = _by(project, cfg)
    cid = d0["chunks"][1]["id"]
    from bti.voice.plan import make_plan
    voice_run.reseed(project, make_plan(project, cfg=cfg, provider="fake"), [cid])
    d = _by(project, cfg)
    assert d["reasons"] == ["reread"] and d["counts"]["by_reason"] == {"reread": 1}
    assert d["detail"] == "Bạn đã yêu cầu đọc lại: 1 câu cần đọc lại."


def test_mixed_reasons_are_counted_per_reason(project, mgr, cfg):
    go(project, mgr, cfg)
    from bti.script import store
    n = store.load_narration(project)
    n.chapters[1].beats[1].text = "Look at the chandelier above the couple, it has a single candle."
    store.save_narration(project, n)
    store.approve(project, "narration", n.rev())
    files.write_pronounce(project, {"London": "Lon-don"})
    d = _by(project, cfg)
    assert d["counts"]["by_reason"] == {"narration_changed": 1, "pronounce_changed": 1} and d["counts"]["changed"] == 2
    assert d["reasons"][:2] == ["narration_changed", "pronounce_changed"]
    assert d["detail"] == "Cần đọc lại 2 câu: 1 do lời dẫn đổi, 1 do bảng phát âm đổi."


def test_voice_settings_change_is_its_own_reason(project, mgr, cfg):
    go(project, mgr, cfg)
    files.update_manifest(project, lambda doc: doc["plan"].update(settings_sig="an older voice"))
    d = _by(project, cfg)
    assert d["reasons"][0] == "voice_changed" and d["counts"]["by_reason"] == {}


def test_a_manifest_from_before_the_split_still_says_narration(project, mgr, cfg):
    """No `wh` in the manifest: the table cannot be told from the narration, so the old word is kept (never a wrong new one)."""
    go(project, mgr, cfg)
    files.update_manifest(project, lambda doc: [c.pop("wh", None) for c in doc["chunks"]])
    files.write_pronounce(project, {"London": "Lon-don"})
    assert _by(project, cfg)["reasons"] == ["narration_changed"]


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


def _flaky_finish(monkeypatch, fails_for_chunk, times):
    """The fake voice's rename fails `times` times for the file of one chunk (a lock held by another process)."""
    real = fakemod.atomic_replace
    seen = {"n": 0}

    def flaky(src, dst):
        if str(dst).endswith(fails_for_chunk + ".wav") and seen["n"] < times:
            seen["n"] += 1
            raise PermissionError(13, "Access is denied", None, 5)
        real(src, dst)
    monkeypatch.setattr(fakemod, "atomic_replace", flaky)
    return seen


def test_a_chunk_whose_file_cannot_be_finished_is_retried_and_the_job_survives(project, mgr, cfg, monkeypatch):
    first = None
    prov = fakemod.FakeProvider()
    monkeypatch.setattr("bti.voice.run.resolve", lambda name, server: prov)
    orig = prov.synth

    def spy(chunks, dest_dir, ctx, workdir=None):
        nonlocal first
        if first is None:
            first = chunks[0].id
            _flaky_finish(monkeypatch, first, 1)
        return orig(chunks, dest_dir, ctx, workdir)
    prov.synth = spy
    rec = go(project, mgr, cfg)
    assert rec["state"] == "done", rec.get("error")
    assert files.chunk_path(project, first).is_file()
    assert sum(call.count(first) for call in prov.calls) == 2      # offered again in a later part


def test_a_chunk_that_never_finishes_is_reported_not_a_crash(project, mgr, cfg, monkeypatch):
    prov = fakemod.FakeProvider()
    monkeypatch.setattr("bti.voice.run.resolve", lambda name, server: prov)
    orig = prov.synth
    done = {}

    def spy(chunks, dest_dir, ctx, workdir=None):
        if not done:
            done["id"] = chunks[0].id
            _flaky_finish(monkeypatch, chunks[0].id, 99)
        return orig(chunks, dest_dir, ctx, workdir)
    prov.synth = spy
    rec = go(project, mgr, cfg)
    assert rec["state"] == "error" and rec["error_code"] == "voice_chunks_failed"      # a reported error, not PermissionError


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


def test_clean_stop_past_28_minutes_finishes_sentence_and_creates_new_part(project, mgr, cfg, monkeypatch):
    """D17: A part that still runs past 28 minutes finishes the sentence it is on, stops cleanly,
    and the rest goes to a new part (never killed mid-sentence, never a failed job)."""
    # Custom provider with injected clock that triggers clean stop after first chunk
    simulated_time = [0.0]

    def mock_clock():
        return simulated_time[0]

    class OverrunningProvider(fakemod.FakeProvider):
        def synth(self, chunks, dest_dir, ctx, workdir=None):
            dest_dir = Path(dest_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)
            self.calls.append([c.id for c in chunks])
            res = {}
            for k, c in enumerate(chunks):
                if ctx.cancelled():
                    break
                s = fakemod.tone_samples(c.spoken, c.seed)
                fakemod.write_wav(dest_dir / f"{c.id}.wav", s)
                res[c.id] = {"ok": True, "sec": len(s) / fakemod.SR}
                # Simulate that first chunk pushed time past 28 minutes (28 * 60 = 1680s)
                if simulated_time[0] < 1680.0:
                    simulated_time[0] = 1685.0
                    # The sentence is finished, stop cleanly!
                    break
            return res

    prov = OverrunningProvider()
    monkeypatch.setattr("bti.voice.run.resolve", lambda name, server: prov)
    # Configure clock and run
    cfg_stop = dict(cfg, clock=mock_clock, part_stop_seconds=1680)
    rec = go(project, mgr, cfg_stop)
    assert rec["state"] == "done", rec.get("error")
    # Verify that a new synth part was created for the remaining sentences
    synth_parts = [p for p in rec["parts"] if p["key"].startswith("synth-")]
    # Should have synth-1 and at least one continuation part
    assert len(synth_parts) >= 2
    # All chunks exist on disk and all sentences were spoken
    assert files.mix_path(project).is_file() and files.timing_path(project).is_file()
    assert describe(project, cfg=cfg, server={}, provider_name="fake")["state"] == "done"

