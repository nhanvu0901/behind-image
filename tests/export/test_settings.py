import json

from bti.export.settings import load_settings


def test_defaults_without_a_file(tmp_path):
    s = load_settings(tmp_path / "none.json")
    assert (s.render_threads, s.part_seconds, s.render_speed) == (4, 60.0, 2.0)


def test_platform_block_and_fallback(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"windows": {"render_threads": 8, "part_seconds": 300}, "default": {"render_threads": 2}}))
    assert load_settings(p, "windows").render_threads == 8 and load_settings(p, "windows").part_seconds == 300.0
    assert load_settings(p, "default").render_threads == 2
    assert load_settings(p, "linux").render_threads == 2


def test_bad_values_are_ignored(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"default": {"render_threads": "many", "part_seconds": -5, "ffmpeg": ""}}))
    s = load_settings(p, "default")
    assert (s.render_threads, s.part_seconds, s.ffmpeg) == (4, 60.0, "ffmpeg")
    p.write_text("not json")
    assert load_settings(p, "default").render_threads == 4


def test_the_real_server_file_is_readable():
    s = load_settings(platform="windows")
    assert s.render_threads >= 1 and s.part_seconds >= 30 and s.part_seconds == 60.0
