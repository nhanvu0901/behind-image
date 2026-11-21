import json

from bti.longjob.config import CONFIG_PATH, load, parse_block


def test_windows_block_of_the_shipped_file():
    c = load("windows")
    assert c.platform == "windows" and c.is_server
    assert c.lock_dir == "D:/bench/_heavy.lock" and c.memory_floor_kb == 12_000_000
    assert "_chatterbox_worker" in c.production_patterns and len(c.production_patterns) == 3
    assert c.voice.python.endswith(".venv-chatterbox/Scripts/python.exe") and c.voice.worker.endswith("_chatterbox_worker.py")
    assert c.voice.reference_voice.endswith("machiavelli_ref.wav")
    assert (c.voice.exaggeration, c.voice.cfg_weight, c.voice.temperature, c.voice.seed) == (0.35, 0.5, 0.7, 42)
    assert c.aligner.python == "D:/code/behind-the-image/.venv-align/Scripts/python.exe" and c.aligner.model == "small.en"
    assert c.render_threads == 4 and c.part_seconds == 240


def test_default_block_has_no_server_programs():
    c = load("default")
    assert not c.is_server and c.lock_dir is None and c.voice is None and c.aligner is None and c.production_patterns == ()


def test_unknown_platform_and_broken_files_fall_back(tmp_path):
    assert load("plan9").platform == "default"
    p = tmp_path / "s.json"
    assert load("windows", p).platform == "default"                  # missing file
    p.write_text("{not json", encoding="utf-8")
    assert load("windows", p).voice is None
    p.write_text(json.dumps({"windows": {"lock_dir": "Z:/l", "voice": {"python": "p"}, "memory_floor_kb": "x"}}), encoding="utf-8")
    c = load("windows", p)
    assert c.lock_dir == "Z:/l" and c.voice is None and c.memory_floor_kb == 0       # incomplete voice block = not available


def test_shipped_file_is_valid_json_with_both_blocks():
    doc = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert set(doc) >= {"windows", "default"}
    assert parse_block("windows", doc["windows"]).part_seconds == 240
