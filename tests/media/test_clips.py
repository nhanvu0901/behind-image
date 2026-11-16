import pytest

from bti.media import clips
from bti.media.errors import LicenceRejected


def test_clear_error_without_ytdlp(monkeypatch):
    monkeypatch.setattr(clips.shutil, "which", lambda n: None)
    monkeypatch.setattr("importlib.util.find_spec", lambda n: None)
    with pytest.raises(clips.ToolMissing, match="yt-dlp is not installed"):
        clips.video_metadata("https://www.youtube.com/watch?v=aaaaaaaaaaa")


def test_clip_licence_gate():
    assert clips.clip_licence({"license": "Creative Commons Attribution license (reuse allowed)"})[0]
    assert not clips.clip_licence({"license": "Standard YouTube License"})[0]
    assert not clips.clip_licence({"license": None})[0]
    assert not clips.clip_licence({})[0]
    assert not clips.clip_licence({"license": "CC BY-NC"})[0]


def test_fetch_section_rejects_before_any_download(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no process may be started")
    monkeypatch.setattr(clips, "_run_capture", boom)
    with pytest.raises(LicenceRejected):
        clips.fetch_section(tmp_path, "https://www.youtube.com/watch?v=aaaaaaaaaaa", 1, 5,
                            info={"id": "aaaaaaaaaaa", "license": "Standard YouTube License"})
    assert not (tmp_path / "cache").exists()


def test_section_args_and_video_id(monkeypatch, tmp_path):
    monkeypatch.setattr(clips, "_ytdlp_cmd", lambda: ["yt-dlp"])
    args = clips.ytdlp_section_args("https://youtu.be/aaaaaaaaaaa", tmp_path, start=10, end=20)
    assert "*10.00-20.00" in args and "--download-sections" in args
    with pytest.raises(ValueError):
        clips.ytdlp_section_args("u", tmp_path, start=5, end=5)
    assert clips.video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert clips.video_id("https://example.org/x") is None


def test_sheet_times():
    times, _ = clips.sheet_times(10, every=2)
    assert times == [0, 2, 4, 6, 8]
    t2, s2 = clips.sheet_times(1000, every=1, max_frames=100)
    assert len(t2) <= 101 and s2 == 10
