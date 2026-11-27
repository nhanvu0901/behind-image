from __future__ import annotations

import numpy as np

from bti.scorecard.audio import compute_pause_vs_speech, is_media_file


def test_compute_pause_vs_speech_measures_db_difference():
    sr = 1000
    duration = 10.0
    t = np.arange(int(sr * duration), dtype=np.float32) / sr
    samples = np.full_like(t, 0.01)  # background music ~ -40 dBFS in pauses

    # Speech segments [1..4] and [6..9] have louder amplitude ~0.1 (-20 dBFS => ~20 dB above pause)
    speech_mask = ((t >= 1.0) & (t <= 4.0)) | ((t >= 6.0) & (t <= 9.0))
    samples[speech_mask] = 0.1

    words = [
        {"w": "a", "s": 1.0, "e": 2.5},
        {"w": "b", "s": 2.5, "e": 4.0},
        {"w": "c", "s": 6.0, "e": 7.5},
        {"w": "d", "s": 7.5, "e": 9.0},
    ]
    res = compute_pause_vs_speech(samples, sr, words, duration=duration)
    assert res is not None
    assert 18.0 <= res["diff_db"] <= 22.0
    assert res["pause_seconds"] >= 1.5
    assert res["pause_count"] == 1
    assert res["speech_db"] > res["pause_db"]


def test_compute_pause_vs_speech_returns_none_without_enough_pause():
    sr = 1000
    samples = np.full(2000, 0.05, dtype=np.float32)
    words = [{"w": "continuous", "s": 0.0, "e": 1.9}]
    assert compute_pause_vs_speech(samples, sr, words, duration=2.0) is None


def test_is_media_file_rejects_json_stub(tmp_path):
    stub = tmp_path / "video.mp4"
    stub.write_text('{"fake": true}\n', encoding="utf-8")
    assert is_media_file(stub) is False

    real = tmp_path / "real.mp4"
    real.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 300)
    assert is_media_file(real) is True


def test_find_exported_video_accepts_music_only_drift_but_rejects_storyboard_stale(tmp_path, monkeypatch):
    from bti.export import run as export_run
    from bti.scorecard.audio import find_exported_video

    pdir = tmp_path / "proj"
    (pdir / "export").mkdir(parents=True)
    mp4 = pdir / "export" / "proj.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 300)
    manifest = {"files": {"video": "proj.mp4"}, "loudness": {"lufs": -14.1}}
    monkeypatch.setattr(export_run, "read_manifest", lambda _: manifest)

    monkeypatch.setattr(export_run, "stale_reason", lambda _p, _m: "music")
    vp, man = find_exported_video(pdir)
    assert vp == mp4
    assert man == manifest

    monkeypatch.setattr(export_run, "stale_reason", lambda _p, _m: "storyboard")
    vp2, man2 = find_exported_video(pdir)
    assert vp2 is None
    assert man2 == manifest
