"""One folder per painting: a second project of the same artwork overwrites it and adds a run record; an older project never takes it over by itself."""
import json

from bti.output import publish
from output_helpers import KEY, PID, Project


def sync(p, **kw):
    kw.setdefault("sheets", False)
    kw.setdefault("moment", "test")
    return publish.sync(p.d, p.out, **kw)


def second(proj, tmp_path, created="2026-11-20T09:00:00-0800"):
    p2 = Project(tmp_path, pid="dutch-portrait-2", created=created)
    return p2


def test_a_second_project_of_the_same_painting_overwrites_the_folder_and_adds_a_run(proj, tmp_path, monkeypatch):
    proj.stage("export")
    sync(proj)
    assert "final.mp4" in proj.tree() and proj.state()["status"] == "done"
    p2 = second(proj, tmp_path)
    monkeypatch.setattr("bti.output.facts.voice_done", lambda pdir, pid: p2.voice_ok if pid == p2.pid else proj.voice_ok)
    p2.create().outline().approve_outline()
    res = sync(p2)
    assert res["takeover"] is True
    st = proj.state()
    assert st["project"] == p2.pid and st["status"] == "in_progress"
    assert [r["project"] for r in st["runs"]] == [PID, p2.pid], "the history of runs is kept, newest last"
    assert st["runs"][0]["reached"] == "export" and st["runs"][1]["reached"] == "artwork"
    t = proj.tree()
    assert "final.mp4" not in t and "3_voice/mix.m4a" not in t and "2_script/outline.md" in t, "what the first project made is replaced, not mixed with the new"
    assert p2.pid in proj.text("README.md") and PID in proj.text("README.md").split("## Các lần làm")[1]
    assert (proj.d / "export" / (PID + ".mp4")).exists(), "the first project's own folder is untouched: its video is still there"


def test_an_older_project_does_not_take_the_folder_back_by_itself(proj, tmp_path, monkeypatch):
    p2 = second(proj, tmp_path)
    p2.create().outline().approve_outline()
    sync(p2)
    proj.stage("export")
    res = sync(proj)
    assert res["skipped"] == "older_project" and proj.state()["project"] == p2.pid and "final.mp4" not in proj.tree()
    res = sync(proj, explicit=True)                      # the rebuild command takes it over when asked
    assert res["takeover"] is True and proj.state()["project"] == PID and "final.mp4" in proj.tree()
    assert [r["project"] for r in proj.state()["runs"]] == [p2.pid, PID]


def test_a_folder_whose_project_is_gone_can_be_taken_by_any_project(proj, tmp_path):
    p2 = second(proj, tmp_path)
    p2.create().outline().approve_outline()
    sync(p2)
    import shutil
    shutil.rmtree(p2.d)
    proj.stage("export")
    assert sync(proj)["skipped"] is None and proj.state()["project"] == PID


def test_a_project_without_a_library_artwork_is_named_by_its_id(proj):
    proj.create()
    meta = json.loads((proj.d / "project.json").read_text(encoding="utf-8"))
    meta.pop("artwork_key")
    (proj.d / "project.json").write_text(json.dumps(meta), encoding="utf-8")
    res = sync(proj)
    assert res["key"] == PID and (proj.out / PID / "state.json").exists()
