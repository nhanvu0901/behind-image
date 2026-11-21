"""The title in the output folder (`README.md`, `state.json`, `2_script/title.md`) and in the export's description (its first line). Old projects without a title read exactly as before."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "output"))

from output_helpers import Project  # noqa: E402
from title_helpers import good_choice  # noqa: E402

from bti.export import describe  # noqa: E402
from bti.output import clean, facts as F, publish, words  # noqa: E402
from bti.script import store as sstore  # noqa: E402
from bti.title import store as T  # noqa: E402

TITLE = "The Saint Who Was Also an Advertisement"


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    p = Project(tmp_path)
    monkeypatch.setattr(F, "voice_done", lambda pdir, pid: p.voice_ok)
    return p


def sync(p, moment="test"):
    return publish.sync(p.d, p.out, moment=moment, sheets=False)


def write_title(p, by="agent:claude:claude-opus-5-5@high"):
    cands = good_choice(["b0001", "b0002", "b0003", "b0004", "b0005", "b0006"] + ["b0006"])["candidates"]
    return T.write_generated(p.d, cands, by=by, narration_rev_=T.narration_rev(p.d), written={"model": "claude:claude-opus-5-5@high", "agent": {"id": "opus", "label": "Opus 5.5 High"},
                                                                                                "note": "keep it short", "at": "2026-11-20T10:00:00+0700"}, at="2026-11-20T10:00:00+0700")


def test_a_project_without_a_title_reads_exactly_as_before(proj):
    proj.stage("approve_narration")
    sync(proj, "narration approved")
    assert "2_script/title.md" not in proj.tree()
    st = proj.state()
    assert "title" not in st and "title" not in st["revisions"] and "title" not in st["parts"]
    assert "Tựa video" not in proj.text("README.md") and "title.md" not in proj.text("README.md")


def test_the_title_is_in_the_readme_the_state_and_its_own_page(proj):
    proj.stage("approve_narration")
    write_title(proj)
    sync(proj, "title written")
    assert "2_script/title.md" in proj.tree()
    st = proj.state()
    assert st["title"] == {"text": TITLE, "by": "agent:claude:claude-opus-5-5@high", "at": "2026-11-20T10:00:00+0700", "source": "agent", "state": "done", "candidates": 6}
    assert st["revisions"]["title"] == st["parts"]["title"]["rev"] and st["parts"]["title"]["files"] == ["2_script/title.md"] and st["parts"]["title"]["counts"] == {"candidates": 6}
    readme = proj.text("README.md")
    assert 'Tựa video: **%s**' % TITLE in readme and "Agent claude:claude-opus-5-5@high" in readme
    assert "`2_script/title.md`: tựa video và 5 tựa khác agent đề xuất, mỗi tựa có lý do." in readme
    md = proj.text("2_script/title.md")
    assert md.startswith("# Tựa video — The Dutch Portrait\n\n**%s**\n" % TITLE)
    assert "- Tình trạng: đang dùng\n" in md and "- Ai chọn: Agent claude:claude-opus-5-5@high · 20/11/2026 10:00" in md
    assert "Do Opus 5.5 High viết theo lời nhắn của bạn: \"keep it short\"." in md
    assert "| 1 | %s **(đang dùng)** | contradiction | 5 / 5 / 5 / 4 | b0001, b0002, b0006 | Một vị thánh và một tấm biển quảng cáo" % TITLE in md
    assert "| 2 | Why Is a Saint Weighing a Ring? | question | 4 / 5 / 5 / 5 | b0001 | Câu hỏi mà người lạ chưa thể trả lời. |" in md
    assert "Các tựa đã dùng trước đó" not in md
    assert "title.md" in [p.name for p in (proj.out / proj.key / "2_script").iterdir()]


def test_a_title_a_person_sets_replaces_it_in_the_folder_and_the_old_one_is_listed(proj):
    proj.stage("approve_narration")
    doc = write_title(proj)
    sync(proj)
    rev1 = proj.state()["parts"]["title"]["rev"]
    T.set_title(proj.d, base_rev=T.revision(doc), actor="human", option=2)
    sync(proj, "title set")
    st = proj.state()
    assert st["title"]["text"] == "Why Is a Saint Weighing a Ring?" and st["title"]["source"] == "person" and st["title"]["by"] == "human" and st["parts"]["title"]["rev"] != rev1
    md = proj.text("2_script/title.md")
    assert md.startswith("# Tựa video — The Dutch Portrait\n\n**Why Is a Saint Weighing a Ring?**\n") and "- Ai chọn: Bạn (trên trang)" in md
    assert "| 2 | Why Is a Saint Weighing a Ring? **(đang dùng)** |" in md and "| 1 | %s |" % TITLE in md
    assert "## Các tựa đã dùng trước đó\n\n- %s — Agent claude:claude-opus-5-5@high" % TITLE in md
    assert 'Tựa video: **Why Is a Saint Weighing a Ring?** (Bạn (trên trang))' in proj.text("README.md")


def test_a_stale_title_says_so(proj):
    proj.stage("approve_narration")
    write_title(proj)
    proj.edit_narration()
    sync(proj, "narration edited")
    st = proj.state()
    assert st["title"]["state"] == "stale"
    assert "đang dùng, nhưng lời dẫn đã đổi sau khi tựa này được viết: nên nhờ agent viết lại" in proj.text("2_script/title.md")
    assert "lời dẫn đã đổi sau khi tựa này được viết" in proj.text("README.md")


def test_writing_the_folder_again_changes_nothing_and_the_title_may_come_before_the_approval(proj):
    proj.stage("narration")                                              # narration written, not approved: a title may exist already
    write_title(proj)
    sync(proj)
    before = {k: v for k, v in proj.tree().items()}
    assert "2_script/title.md" in before
    sync(proj)
    assert proj.tree() == before


def test_a_second_write_changes_nothing_with_and_without_a_title(proj):
    proj.stage("export")
    assert sync(proj, "export done")["skipped"] is None and sync(proj, "again")["skipped"] == "unchanged"        # no title: the part has nothing to write and the shortcut still holds
    write_title(proj)
    assert sync(proj, "title written")["skipped"] is None and "2_script/title.md" in proj.tree()
    mtimes = {p: p.stat().st_mtime_ns for p in (proj.out / proj.key).rglob("*") if p.is_file()}
    res = sync(proj, "again")
    assert res["skipped"] == "unchanged" and res["written"] == []
    assert mtimes == {p: p.stat().st_mtime_ns for p in (proj.out / proj.key).rglob("*") if p.is_file()}


def test_a_damaged_title_file_is_a_warning_of_the_facts_and_never_breaks_the_folder(proj):
    proj.stage("approve_narration")
    (proj.d / "title.json").write_text("{ nope", encoding="utf-8")
    f = F.collect(proj.d)
    assert f.title_doc is None and any("title.json cannot be read" in p for p in f.problems)
    sync(proj)
    assert "2_script/title.md" not in proj.tree() and "2_script/narration.md" in proj.tree()


def test_a_title_job_is_a_row_of_the_jobs_page_with_its_label_and_its_title(proj):
    proj.stage("approve_narration")
    proj.job("aaaaaaaaaaaaaaaa", "title", agent={"id": "opus", "label": "Opus 5.5 High", "model": "m"}, model="claude:m")
    rec = json.loads((proj.d / "cache" / "longjobs" / "aaaaaaaaaaaaaaaa.json").read_text(encoding="utf-8"))
    rec["result"] = {"title": TITLE}
    (proj.d / "cache" / "longjobs" / "aaaaaaaaaaaaaaaa.json").write_text(json.dumps(rec), encoding="utf-8")
    sync(proj)
    jobs = proj.text("log/jobs.md")
    assert words.KIND_LABEL["title"] == "Viết tựa video" and "Viết tựa video" in jobs and TITLE in jobs and "Opus 5.5 High" in jobs


def test_the_cleaning_removes_the_title_writers_transcripts_and_never_the_title(proj):
    proj.stage("approve_narration")
    write_title(proj)
    run = proj.d / "cache" / "title" / "runs" / "20261120-100000"
    run.mkdir(parents=True)
    (run / "title-events.jsonl").write_text("x" * 100, encoding="utf-8")
    assert run.parent in clean.targets(proj.d)
    res = clean.clean_project(proj.d)
    assert res["done"] and "cache/title/runs" in res["removed"] and not run.exists() and (proj.d / "title.json").is_file()


# ---------------------------------------------------------------------------------------------------------------- the description
def sb(**kw):
    return {"title": "The Arnolfini Portrait", "assets": {}, "shots": [], **kw}


META = {"title": "The Arnolfini Portrait", "artist": "Jan van Eyck", "year": "1434"}


def test_the_first_line_of_the_description_is_the_videos_title_then_the_painting_as_before():
    d = describe.build_description(sb(), {"chapters": []}, META, duration=10, video_title=TITLE)["description"]
    assert d.splitlines()[0] == TITLE and d.splitlines()[1] == "" and d.splitlines()[2] == "Jan van Eyck, The Arnolfini Portrait (1434)"


def test_without_a_document_the_description_takes_the_title_the_beat_shows_else_the_paintings():
    shown = describe.build_description(sb(identity={"style": "raking", "video_title": "  The Mirror\nThat Remembers "}), {"chapters": []}, META, duration=10)["description"]
    assert shown.splitlines()[0] == "The Mirror That Remembers"
    plain = describe.build_description(sb(), {"chapters": []}, META, duration=10)["description"]
    assert plain.splitlines()[0] == "The Arnolfini Portrait" and plain == describe.build_description(sb(), {"chapters": []}, META, duration=10, video_title=None)["description"]
    both = describe.build_description(sb(identity={"video_title": "From The Storyboard"}), {"chapters": []}, META, duration=10, video_title="From The Document")["description"]
    assert both.splitlines()[0] == "From The Document"
    blank = describe.build_description(sb(identity={"video_title": "   "}), {"chapters": []}, META, duration=10, video_title="  ")["description"]
    assert blank.splitlines()[0] == "The Arnolfini Portrait"


def test_the_export_job_writes_the_title_on_the_first_line_of_the_description_and_the_folder_keeps_it(proj, monkeypatch):
    from bti.output import hooks
    from output_helpers import export_world
    proj.stage("approve_storyboard")
    write_title(proj)
    run, settings, _ = export_world(proj, monkeypatch)
    try:
        job = run.start(proj.d, settings=settings)
        assert job["state"] == "done", job.get("error")
        names = json.loads((proj.d / "export" / "export.json").read_text(encoding="utf-8"))["files"]
        first = (proj.d / "export" / names["description"]).read_text(encoding="utf-8").splitlines()
        assert first[0] == TITLE and first[1] == "" and first[2].startswith("Jan Vermeer, The Dutch Portrait")
        assert proj.text("6_export/description.txt").splitlines()[0] == TITLE and "2_script/title.md" in proj.tree()
    finally:
        hooks.register(proj.root, None)
        hooks.flush(30)


def test_without_a_title_the_export_description_starts_with_the_paintings_title_as_before(proj, monkeypatch):
    from bti.output import hooks
    from output_helpers import export_world
    proj.stage("approve_storyboard")
    run, settings, _ = export_world(proj, monkeypatch)
    try:
        job = run.start(proj.d, settings=settings)
        assert job["state"] == "done", job.get("error")
        names = json.loads((proj.d / "export" / "export.json").read_text(encoding="utf-8"))["files"]
        assert (proj.d / "export" / names["description"]).read_text(encoding="utf-8").splitlines()[0] == "The Dutch Portrait"
        assert "2_script/title.md" not in proj.tree()
    finally:
        hooks.register(proj.root, None)
        hooks.flush(30)
