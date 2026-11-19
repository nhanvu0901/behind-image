"""The output folder of a fixture project, after each step and as a whole: what is there, what is not yet, what never is, and that writing it again changes nothing."""
import hashlib
import json
import re

import pytest

from bti.output import publish
from output_helpers import KEY, PID, Project

RAW_ID = re.compile(r"\b[A-Z]{1,6}-[A-Z0-9]{1,3}(?:-\d+)?\b")


def sync(p, moment="test", **kw):
    kw.setdefault("sheets", False)
    return publish.sync(p.d, p.out, moment=moment, **kw)


def names(p):
    return set(p.tree())


def test_the_folder_fills_as_the_project_moves(proj):
    base = {"README.md", "state.json", "log/changes.md", "log/jobs.md", "log/jobs.json"}
    proj.create()
    sync(proj, "project created")
    assert names(proj) == base | {"1_sources/dossier.json", "1_sources/payne_gae_002.txt", "1_sources/hodge_aid_003.txt", "1_sources/sources.md"}

    proj.outline()
    sync(proj)
    assert not any(n.startswith("2_script") for n in names(proj)), "an outline that is not approved is not published"
    proj.approve_outline()
    sync(proj, "outline approved")
    assert {"2_script/outline.md", "2_script/outline.json"} <= names(proj) and "2_script/narration.md" not in names(proj)

    proj.narration().approve_narration()
    sync(proj, "narration approved")
    assert {"2_script/narration.md", "2_script/narration.json"} <= names(proj) and not any(n.startswith("3_voice") for n in names(proj))

    proj.voice()
    sync(proj, "voice done")
    assert {"3_voice/narration.wav", "3_voice/mix.m4a", "3_voice/timing.json"} <= names(proj) and not any(n.startswith("4_pictures") for n in names(proj))

    proj.picks()
    sync(proj)
    assert not any(n.startswith("4_pictures") for n in names(proj)), "picks that are not approved are not published"
    proj.approve_picks()
    sync(proj, "picks approved")
    pics = {n for n in names(proj) if n.startswith("4_pictures/")}
    assert pics == {"4_pictures/main.jpg", "4_pictures/B.jpg", "4_pictures/D.jpg", "4_pictures/picks.json", "4_pictures/regions.jpg", "4_pictures/credits.txt"}, \
        "before the storyboard: the main painting and the pictures given to lines, never the one nobody picked (C.jpg)"
    assert not any(n.startswith("5_storyboard") for n in names(proj))

    proj.storyboard()
    sync(proj)
    assert not any(n.startswith("5_storyboard") for n in names(proj)), "a storyboard that is not approved is not published"
    proj.approve_storyboard()
    sync(proj, "storyboard approved")
    assert {"5_storyboard/shots.md", "5_storyboard/storyboard.json"} <= names(proj)
    pics = {n for n in names(proj) if n.startswith("4_pictures/") and n.endswith(".jpg")}
    assert "4_pictures/D.jpg" not in pics and {"4_pictures/main.jpg", "4_pictures/B.jpg"} <= pics, "with the approved storyboard only the pictures its shots show stay"
    assert "final.mp4" not in names(proj) and not any(n.startswith("6_export") for n in names(proj))

    proj.export()
    sync(proj, "export done")
    assert {"final.mp4", "6_export/description.txt", "6_export/chapters.txt", "6_export/report.json"} <= names(proj)
    st = proj.state()
    assert st["status"] == "done" and st["project"] == PID and st["artwork"]["key"] == KEY
    assert [s["state"] for s in st["steps"]] == ["done"] * 6 and all(s["reached"] for s in st["steps"])


def test_never_in_the_folder(proj):
    proj.stage("export").caches().change()
    proj.edit_picks()
    proj.approve_picks()
    sync(proj, "export done")
    (proj.d / ".env").write_text("SECRET=1", encoding="utf-8")
    sync(proj, force=True)
    for n in names(proj):
        assert not re.search(r"(^|/)(cache|history|proposals|changes|media|auto_runs)(/|$)", n), n
        assert not re.search(r"\.(before|after|prev)\.json$|\.env|\.log$|\.part$", n), n
    assert not any(n.lower().endswith("c.jpg") for n in names(proj)), "the picture nobody uses is never copied"
    blob = "".join((proj.out / KEY / n).read_bytes().decode("utf-8", "ignore") for n in names(proj) if n.endswith((".md", ".json", ".txt")))
    assert "SECRET=1" not in blob


def test_the_video_and_the_big_files_are_the_same_bytes_and_never_half_written(proj, monkeypatch):
    proj.stage("export")
    sync(proj)
    src = proj.d / "export" / (PID + ".mp4")
    assert (proj.out / KEY / "final.mp4").read_bytes() == src.read_bytes()
    # a failing copy leaves neither a final.mp4 nor a .part file behind
    (proj.out / KEY / "final.mp4").unlink()
    import shutil
    monkeypatch.setattr(shutil, "copy2", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    import os
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError("no links here")))
    res = sync(proj, force=True)
    assert not (proj.out / KEY / "final.mp4").exists() and not list((proj.out / KEY).rglob("*.part"))
    assert any(w["part"] == "export" for w in res["warnings"]) and "export" not in proj.state()["parts"]


def test_a_rebuild_gives_the_same_tree(proj, tmp_path):
    proj.stage("export").caches().change().job("4444444444444444", "export")
    sync(proj, "export done")
    first, st1 = proj.tree(), proj.state()

    def digest(p):
        return {n: hashlib.sha1((proj.out / KEY / n).read_bytes()).hexdigest() for n in p if n not in ("README.md", "state.json")}
    sync(proj, "rebuild", explicit=True, force=True)
    drop = lambda t: {n: v for n, v in t.items() if n != "state.json"}          # noqa: E731 (state.json names the moment of the last write: "export done" or "rebuild")
    assert drop(proj.tree()) == drop(first), "a second write changes no name and no size"
    assert digest(first) == digest(proj.tree())
    # a rebuild into an empty folder from the same project gives the same set of files
    other = Project(tmp_path / "second")
    other.root = proj.root
    other.out = tmp_path / "second" / "output"
    other.d = proj.d
    publish.sync(proj.d, other.out, moment="rebuild", explicit=True, sheets=False)
    assert other.tree().keys() == first.keys() and {n: other.tree()[n] for n in first if n not in ("README.md", "state.json", "log/jobs.json")} == {n: first[n] for n in first if n not in ("README.md", "state.json", "log/jobs.json")}
    st2 = proj.state()
    assert st2["parts"] == st1["parts"] or {k: v["rev"] for k, v in st2["parts"].items()} == {k: v["rev"] for k, v in st1["parts"].items()}
    assert st2["runs"][0]["writes"] > st1["runs"][0]["writes"] and len(st2["runs"]) == 1


def test_nothing_is_written_when_nothing_changed(proj):
    proj.stage("export")
    sync(proj, "export done")
    mtimes = {p: p.stat().st_mtime_ns for p in (proj.out / KEY).rglob("*") if p.is_file()}
    res = sync(proj, "again")
    assert res["skipped"] == "unchanged" and res["written"] == []
    assert mtimes == {p: p.stat().st_mtime_ns for p in (proj.out / KEY).rglob("*") if p.is_file()}


def test_a_part_goes_out_of_date_and_comes_back(proj):
    proj.stage("export")
    sync(proj, "export done")
    assert not any(v["out_of_date"] for v in proj.state()["parts"].values())
    old_text = proj.text("2_script/narration.md")

    proj.edit_narration()                       # saving drops the narration's approval (and so the picks', which were approved against it)
    sync(proj, "narration saved")
    parts = proj.state()["parts"]
    assert parts["narration"]["out_of_date"] and parts["narration"]["reason"] == "changed"
    assert parts["pictures"]["out_of_date"] and parts["pictures"]["reason"] == "approval_withdrawn"
    assert proj.text("2_script/narration.md") == old_text, "the files are kept as they were, marked, not silently replaced"
    readme = proj.text("README.md")
    assert "Phần đã cũ" in readme and "Lời dẫn" in readme and "Hình ảnh" in readme
    from bti.output import index
    assert set(index.rows(proj.out)[0]["out_of_date"]) >= {"narration", "pictures"}

    proj.approve_narration().approve_picks()
    sync(proj, "narration approved")
    parts = proj.state()["parts"]
    assert not any(v["out_of_date"] for k, v in parts.items() if k not in ("voice",)) or not parts["narration"]["out_of_date"]
    assert not parts["narration"]["out_of_date"] and not parts["pictures"]["out_of_date"]
    assert "(a new sentence)" in proj.text("2_script/narration.md")
    assert "Phần đã cũ" not in proj.text("README.md") or "Lời dẫn" not in proj.text("README.md").split("Phần đã cũ")[-1].split("##")[0]


def test_an_export_that_went_stale_is_marked_and_comes_back_with_a_new_export(proj):
    proj.stage("export")
    sync(proj, "export done")
    proj.edit_storyboard()
    sync(proj, "storyboard saved")
    p = proj.state()["parts"]
    assert p["storyboard"]["out_of_date"] and p["export"]["out_of_date"]
    assert (proj.out / KEY / "final.mp4").exists(), "the old video stays: it is the last one that was made"
    assert "đã cũ" in proj.text("README.md")
    proj.approve_storyboard().export()
    sync(proj, "export done")
    assert not any(v["out_of_date"] for v in proj.state()["parts"].values())


def test_a_part_that_fails_is_a_warning_and_the_others_are_written(proj, monkeypatch):
    proj.stage("export")
    from bti.output import parts as P

    def boom(f, folder):
        raise RuntimeError("the narration cannot be copied")
    monkeypatch.setattr(P, "write_narration", boom)
    res = sync(proj, "narration approved")
    assert [w["part"] for w in res["warnings"]] == ["narration"]
    w = res["warnings"][0]
    assert w["code"] == "output_part_failed" and re.search(r"[À-ỹ]", w["sentence"]) and "Lời dẫn" in w["sentence"]
    assert "narration" not in proj.state()["parts"] and {"final.mp4", "5_storyboard/shots.md", "3_voice/mix.m4a"} <= names(proj)
    assert proj.state()["warnings"][0]["sentence"] in proj.text("README.md")
    monkeypatch.undo()
    monkeypatch.setattr("bti.output.facts.voice_done", lambda pdir, pid: True)
    res = sync(proj, "again")
    assert res["warnings"] == [] and "narration" in proj.state()["parts"] and "2_script/narration.md" in names(proj)


def test_unused_pictures_are_left_out(proj):
    proj.stage("export")
    sync(proj)
    pics = {n.split("/")[-1] for n in names(proj) if n.startswith("4_pictures/")}
    assert {"main.jpg", "B.jpg"} <= pics and "C.jpg" not in pics and "D.jpg" not in pics
    credits = proj.text("4_pictures/credits.txt")
    assert "A map of the provinces" in credits and "A picture nobody uses" not in credits and "Picked, never on screen" not in credits
    p = proj.state()["parts"]["pictures"]
    assert p["basis"] == "storyboard" and p["count"] == 2 and p["unused_left_out"] == 2
