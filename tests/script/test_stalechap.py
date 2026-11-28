"""Tests for stale chapter removal during narration generation/import and chapter_not_in_outline validation."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from bti.auto_run import checks
from bti.editor.app import create_app
from bti.script import generate, store, validate
from bti.script.runner import ScriptJobs
from bti.script.store import Beat, Fact, NChapter, Narration, OChapter, Outline

MOCK = {"id": "mock", "provider": "mock", "model": "mock", "key_env": None}


def _wait(job, seconds: float = 20.0):
    end = time.time() + seconds
    while time.time() < end:
        if job.state in ("done", "error", "cancelled"):
            return job
        time.sleep(0.02)
    raise AssertionError(f"job still {job.state}")


def _run(jobs: ScriptJobs, pdir, chapters=None):
    return _wait(jobs.start("narration", pdir.name, "mock", lambda job: generate.run_narration(job, pdir, MOCK, chapters)))


def _make_outline(n_chapters: int = 8) -> Outline:
    chapters = []
    for i in range(1, n_chapters + 1):
        cid = f"c{i:02d}"
        role = "cold_open" if i == 1 else "closing" if i == n_chapters else "chapter"
        title = "COLD OPEN" if i == 1 else "CLOSING" if i == n_chapters else f"CHAPTER {i}"
        chapters.append(OChapter(cid, role, title, i > 1, "Explain the detail.", 20, ["f01"], ["the mirror"]))
    return Outline(
        thesis="What does the mirror show?",
        hook_options=[],
        hook_choice=None,
        chapters=chapters,
        facts=[Fact("f01", "The picture shows a mirror on the back wall.", ["PAY-01"], "established")],
        target_words=n_chapters * 20,
    )


def _seed_project(tproj, n_outline: int = 8, n_narr: int = 9) -> tuple[Outline, Narration]:
    o = _make_outline(n_outline)
    store.save_outline(tproj, o, backup=False)
    o = store.load_outline(tproj)
    store.approve(tproj, "outline", o.rev())

    n = Narration(project=tproj.name, title="The Test Painting", language="en")
    for i in range(1, n_narr + 1):
        cid = f"c{i:02d}"
        role = "cold_open" if i == 1 else "closing" if i == n_narr else "chapter"
        title = "COLD OPEN" if i == 1 else "CLOSING" if i == n_narr else f"CHAPTER {i}"
        if i == 1:
            beats = [
                Beat(n.new_beat_id(), "In The Test Painting, A. Painter places the mirror on the back wall.", ["f01"], ["the mirror"]),
                Beat(n.new_beat_id(), "But one detail refuses to fit. What does it mean?", ["f01"], ["the mirror"]),
            ]
        else:
            beats = [
                Beat(
                    n.new_beat_id(),
                    f"Old sentence for chapter {cid} describing the mirror and the painted room in plain detail.",
                    ["f01"],
                    ["the mirror"],
                ),
            ]
        n.chapters.append(NChapter(cid, role, title, i > 1, beats))
    store.save_narration(tproj, n, backup=False)
    return store.load_outline(tproj), store.load_narration(tproj)


def test_generating_all_chapters_removes_stale_chapter_and_records_removed(tproj, monkeypatch):
    monkeypatch.setattr(generate, "repetition_repairs", lambda *args: {})
    o, _ = _seed_project(tproj, n_outline=8, n_narr=9)
    jobs = ScriptJobs()

    job = _run(jobs, tproj)
    assert job.state == "done", job.error
    assert job.result["removed"] == ["c09"]

    after = store.load_narration(tproj)
    assert [c.id for c in after.chapters] == [c.id for c in o.chapters] == [f"c{i:02d}" for i in range(1, 9)]
    iss = validate.validate_narration(after, o)
    assert not any(i["code"] == "chapter_not_in_outline" for i in iss)


def test_generating_one_chapter_also_removes_stale_chapter(tproj, monkeypatch):
    monkeypatch.setattr(generate, "repetition_repairs", lambda *args: {})
    o, before = _seed_project(tproj, n_outline=8, n_narr=9)
    kept_before = {c.id: [b.id for b in c.beats] for c in before.chapters if c.id not in ("c02", "c09")}
    c02_before = [b.id for b in before.chapter("c02").beats]
    jobs = ScriptJobs()

    job = _run(jobs, tproj, chapters=["c02"])
    assert job.state == "done", job.error
    assert job.result["written"] == ["c02"]
    assert job.result["removed"] == ["c09"]

    after = store.load_narration(tproj)
    assert [c.id for c in after.chapters] == [f"c{i:02d}" for i in range(1, 9)]
    for cid, ids in kept_before.items():
        assert [b.id for b in after.chapter(cid).beats] == ids
    assert [b.id for b in after.chapter("c02").beats] != c02_before


def test_multiple_stale_chapters_removed_and_clean_run_omits_removed(tproj, monkeypatch):
    monkeypatch.setattr(generate, "repetition_repairs", lambda *args: {})
    _seed_project(tproj, n_outline=8, n_narr=10)
    jobs = ScriptJobs()

    job1 = _run(jobs, tproj, chapters=["c02"])
    assert job1.state == "done", job1.error
    assert job1.result["removed"] == ["c09", "c10"]

    job2 = _run(jobs, tproj, chapters=["c03"])
    assert job2.state == "done", job2.error
    assert "removed" not in job2.result


def test_validate_flags_stale_chapter_and_blocks_gate(tproj):
    o, n = _seed_project(tproj, n_outline=8, n_narr=9)
    iss = validate.validate_narration(n, o)
    stale = [i for i in iss if i["code"] == "chapter_not_in_outline"]
    assert len(stale) == 1
    assert stale[0]["level"] == "error"
    assert stale[0]["chapter"] == "c09"
    assert stale[0]["args"] == {"chapter": "c09"}
    assert [i["code"] for i in validate.blocking(iss)] == ["chapter_not_in_outline"]

    verdict, stopping, _ = checks.vet("narration", iss)
    assert verdict == "error"
    assert any(i["code"] == "chapter_not_in_outline" for i in stopping)

    app = create_app(projects_root=tproj.parent, engine_module=None, media_module=None, output_root=False)
    client = TestClient(app)
    r = client.post(f"/api/projects/{tproj.name}/narration/approve", json={"rev": n.rev()})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "narration_has_errors"
    assert body["chapter_diff"]["not_in_outline"] == ["c09"]
    assert any(i["code"] == "chapter_not_in_outline" and i["level"] == "error" for i in body["issues"])


def test_narration_import_merge_also_drops_stale_chapters(tproj):
    o, _ = _seed_project(tproj, n_outline=8, n_narr=9)
    app = create_app(projects_root=tproj.parent, engine_module=None, media_module=None, output_root=False)
    client = TestClient(app)
    r = client.post(
        f"/api/projects/{tproj.name}/narration/import",
        json={"text": "## c02 CHAPTER 2\nFresh words for chapter two.\n>> facts: f01 | show: the mirror", "merge": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [c["id"] for c in body["narration"]["chapters"]] == [c.id for c in o.chapters]
    assert body["chapter_diff"]["not_in_outline"] == []
    assert not any(i["code"] == "chapter_not_in_outline" for i in body["issues"])
