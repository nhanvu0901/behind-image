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
    assert args[-2] == "--"
    assert args[-1] == "https://www.youtube.com/watch?v=aaaaaaaaaaa"
    with pytest.raises(ValueError):
        clips.ytdlp_section_args("u", tmp_path, start=5, end=5)
    with pytest.raises(ValueError):
        clips.ytdlp_section_args("--batch-file=C:/x", tmp_path, start=5, end=10)
    assert clips.video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert clips.video_id("https://example.org/x") is None


def test_safe_youtube_url_hostile_strings():
    hostile = [
        "--batch-file=C:/x youtube.com/watch?v=aaaaaaaaaaa",
        "-o /tmp/pwn https://www.youtube.com/watch?v=aaaaaaaaaaa",
        "--help",
        "-v",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa https://www.youtube.com/watch?v=bbbbbbbbbbb",
        "https://www.youtube.com/watch?v=aaaa aaaaaaa",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa\nhttps://www.youtube.com/watch?v=bbbbbbbbbbb",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa&redirect=https://evil.com",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa;https://evil.com",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa; rm -rf /",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa && touch /tmp/pwn",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa|cat",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa$(whoami)",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa`whoami`",
        "https://evil.com/watch?v=aaaaaaaaaaa",
        "https://youtube.com.attacker.com/watch?v=aaaaaaaaaaa",
        "https://vimeo.com/123456789",
        "https://notyoutube.com/watch?v=aaaaaaaaaaa",
        "https://attacker.org/?https://www.youtube.com/watch?v=aaaaaaaaaaa",
        "",
        "   ",
        "https://youtube.com/watch?v=short",
        "https://youtube.com/watch?v=toolong123456789",
        "ftp://youtube.com/watch?v=aaaaaaaaaaa",
        "javascript:alert(1)",
    ]
    for bad in hostile:
        assert clips.video_id(bad) is None, f"expected None for hostile: {bad!r}"
        with pytest.raises(ValueError):
            clips.safe_youtube_url(bad)

    valid = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ&feature=shared", "dQw4w9WgXcQ"),
        ("http://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ]
    for raw, expected_id in valid:
        assert clips.video_id(raw) == expected_id
        assert clips.safe_youtube_url(raw) == f"https://www.youtube.com/watch?v={expected_id}"


def test_clips_tool_status(monkeypatch):
    monkeypatch.setattr(clips, "_ytdlp_cmd", lambda: ["yt-dlp"])
    monkeypatch.setattr(clips, "_ffmpeg", lambda: "ffmpeg")
    assert clips.has_ytdlp() is True
    assert clips.tool_status() == {"available": True, "code": None}

    def fake_missing():
        raise clips.ToolMissing("yt-dlp missing")

    monkeypatch.setattr(clips, "_ytdlp_cmd", fake_missing)
    assert clips.has_ytdlp() is False
    assert clips.tool_status() == {"available": False, "code": "tool_missing"}



def test_sheet_times():
    times, _ = clips.sheet_times(10, every=2)
    assert times == [0, 2, 4, 6, 8]
    t2, s2 = clips.sheet_times(1000, every=1, max_frames=100)
    assert len(t2) <= 101 and s2 == 10


def test_moment_discovery_and_search():
    qs = clips.moment_queries("oil glazing technique")
    assert qs[0] == "oil glazing technique" and len(qs) >= 2
    parsed = clips.parse_search_results({"results": {"web": [
        {"title": "Glazing", "url": "https://www.youtube.com/watch?v=abc12345678", "snippets": ["Demo"]},
        {"title": "Dup", "url": "https://youtu.be/abc12345678", "snippets": ["Same id"]},
        {"title": "Wiki", "url": "https://en.wikipedia.org/wiki/Glaze", "snippets": ["Article"]},
    ]}})
    assert [r["url"] for r in parsed] == ["https://www.youtube.com/watch?v=abc12345678", "https://en.wikipedia.org/wiki/Glaze"]
    assert [r["is_video"] for r in parsed] == [True, False]

    vtt = "WEBVTT\n\n00:00:12.000 --> 00:00:16.500\n<c>Now apply transparent oil glazing</c>\n"
    cues = clips.parse_vtt(vtt)
    assert cues == [(12.0, 16.5, "Now apply transparent oil glazing")]

    fake_info = {
        "id": "abc12345678", "title": "Old Masters Documentary", "channel": "Museum",
        "duration": 180.0, "height": 1080, "width": 1920, "license": "Standard YouTube License",
        "chapters": [{"title": "Transparent glazing layer", "start_time": 40, "end_time": 65}],
        "heatmap": [{"start_time": 80, "end_time": 90, "value": 0.9}, {"start_time": 90, "end_time": 100, "value": 0.2}],
    }
    rows = clips.moment_search(
        "transparent oil glazing",
        search=lambda q: [{"url": "https://www.youtube.com/watch?v=abc12345678", "title": "Old Masters", "snippet": "", "is_video": True}],
        metadata=lambda u, td: (fake_info, cues),
    )
    assert len(rows) == 1 and rows[0]["flag"] == "unknown" and len(rows[0]["moments"]) >= 2

    one = clips.inspect_video_url("https://youtu.be/abc12345678", "glazing", metadata=lambda u, td: (fake_info, cues))
    assert one["id"] == "abc12345678" and one["licence_ok"] is False


def test_fetch_section_advisory_licence(tmp_path, monkeypatch):
    def fake_dl(cmd, *, timeout=None):
        p = tmp_path / "cache" / "clips" / "src" / "aaaaaaaaaaa_sec_1.0_5.0.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"raw")
        from subprocess import CompletedProcess
        return CompletedProcess(cmd, 0, str(p) + "\n", "")

    monkeypatch.setattr(clips, "_ytdlp_cmd", lambda: ["yt-dlp"])
    monkeypatch.setattr(clips, "normalize", lambda raw, out: out.write_bytes(b"mp4") or out)
    res = clips.fetch_section(
        tmp_path, "https://www.youtube.com/watch?v=aaaaaaaaaaa", 1, 5,
        info={"id": "aaaaaaaaaaa", "license": "Standard YouTube License", "channel": "Demo"},
        sheet=False, strict_licence=False, runner=fake_dl,
    )
    assert res["credit"]["flag"] == "unknown" and res["file"].endswith(".mp4")

    res2 = clips.fetch_section(
        tmp_path, "https://www.youtube.com/watch?v=aaaaaaaaaaa", 2, 6,
        info={"id": "aaaaaaaaaaa", "license": "All rights reserved", "channel": "Demo"},
        sheet=False, strict_licence=False, runner=fake_dl,
    )
    assert res2["credit"]["flag"] == "rejected"


def test_import_clip_one_copy_and_prune_cache(tmp_path, monkeypatch):
    def fake_dl(cmd, *, timeout=None):
        p = tmp_path / "cache" / "clips" / "src" / "aaaaaaaaaaa_sec_1.0_5.0.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"raw_content")
        from subprocess import CompletedProcess
        return CompletedProcess(cmd, 0, str(p) + "\n", "")

    monkeypatch.setattr(clips, "_ytdlp_cmd", lambda: ["yt-dlp"])
    monkeypatch.setattr(clips, "normalize", lambda raw, out: out.write_bytes(b"normalized_clip") or out)
    monkeypatch.setattr(clips, "probe_video", lambda p: {"width": 1280, "height": 720, "duration": 4.0})
    monkeypatch.setattr(clips, "contact_sheet", lambda v, out, **kw: out.write_bytes(b"sheet") or out)

    res = clips.import_clip(
        tmp_path, "https://www.youtube.com/watch?v=aaaaaaaaaaa", 1, 5,
        info={"id": "aaaaaaaaaaa", "title": "Clip Title", "license": "Creative Commons Attribution", "channel": "Demo"},
        strict_licence=False, runner=fake_dl,
    )
    media_file = tmp_path / res["asset"]["file"]
    assert media_file.is_file() and media_file.read_bytes() == b"normalized_clip"
    working_file = tmp_path / "cache" / "clips" / "aaaaaaaaaaa_1.0_5.0.mp4"
    assert not working_file.exists()

    cache_dir = tmp_path / "cache" / "clips"
    cache_dir.mkdir(parents=True, exist_ok=True)
    f1 = cache_dir / "old.mp4"
    f2 = cache_dir / "new.mp4"
    f1.write_bytes(b"x" * 600)
    f2.write_bytes(b"y" * 600)
    import os
    os.utime(f1, (100, 100))
    os.utime(f2, (200, 200))
    freed = clips.prune_clips_cache(tmp_path, max_bytes=800)
    assert freed == 600
    assert not f1.exists()
    assert f2.exists()

