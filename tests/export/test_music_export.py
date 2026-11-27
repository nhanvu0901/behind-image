import json

from bti.export import run
from bti.music import library


def test_music_remixes_without_rendering_and_adds_credit(patch_run, project, settings, manager, fake_tools, tmp_path, monkeypatch):
    from bti.music import mix
    monkeypatch.setattr(mix, "mix_command", lambda ffmpeg, voice, cues, out, duration:
                        [*ffmpeg, "-filter_complex", "fake", "-t", str(duration), str(out)])
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    (music_dir / "one.opus").write_text("fake audio")
    rows = [{"id": "one", "file": "one.opus", "duration": 100, "title": "A piece", "composer": "A composer",
             "performer": "A performer", "credit": "A piece — A performer", "license": "CC0", "source": "https://commons.wikimedia.org/wiki/File:One.ogg"}]
    (music_dir / "library.json").write_text(json.dumps(rows))
    monkeypatch.setattr(library, "directory", lambda: music_dir)
    before_plan = run.plan_for(project, settings)
    first = run.start(project, settings=settings)
    assert first["state"] == "done"
    calls = len(fake_tools.calls("engine"))
    doc = {"schema": "bti.music/1", "cues": [{"recording": "one", "start": {"t": 0}, "end": {"t": 5},
            "offset": 0, "level": "normal", "fade_in": 1, "fade_out": 1, "role": "bed", "why": "Quiet."}]}
    (project / "music.json").write_text(json.dumps(doc))
    assert run.state(project, manager)["state"] == "stale"
    after_plan = run.plan_for(project, settings)
    assert after_plan["part_seconds"] == before_plan["part_seconds"]
    assert after_plan["parts_to_render"] == 0
    second = run.start(project, settings=settings)
    assert second["state"] == "done", second.get("error")
    assert len(fake_tools.calls("engine")) == calls
    text = (project / "export" / "description.txt").read_text(encoding="utf-8")
    assert "Music" in text and "A piece — A composer; performed by A performer" in text and "CC0" in text
    assert run.state(project, manager)["state"] == "done"


def test_music_document_does_not_change_the_serialized_picture_plan(project, settings):
    before = json.dumps(run.plan_for(project, settings), sort_keys=True, separators=(",", ":"))
    (project / "music.json").write_text(json.dumps({"schema": "bti.music/1", "cues": []}))
    after = json.dumps(run.plan_for(project, settings), sort_keys=True, separators=(",", ":"))
    assert after.encode("utf-8") == before.encode("utf-8")
