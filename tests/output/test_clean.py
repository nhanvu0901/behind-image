"""Cleaning the working folder after a successful export: exactly the listed caches go, nothing else, and only when the export stands, the switch is on and nothing else runs."""
import json
from pathlib import Path

from bti.output import clean, publish
from output_helpers import KEY, Project

REMOVED = ["export/chapters.ffmeta", "export/parts/part_01_x.mp4", "export/video_all.mp4", "frames", "thumbs", "previews", "uploads", "picks_auto/runs", "voice", "longjobs/work", "wave_abc_4000.json",
           "longjobs/1111111111111111.log", "longjobs/2222222222222222.log"]
KEPT = ["picks_auto/plan.json", "picks_auto/last.json", "picks_auto/thumbs/x.jpg", "draft/thread.json", "draft/turns/t1/out/c01.json", "picks/suggestions.json", "longjobs/1111111111111111.json", "longjobs/2222222222222222.json", "jobs/3333333333333333.json"]


def files_outside_cache(p: Project) -> dict:
    return {f.relative_to(p.d).as_posix(): f.read_bytes() for f in sorted(p.d.rglob("*")) if f.is_file() and "cache" not in f.relative_to(p.d).parts}


def sync(p, moment="export", **kw):
    kw.setdefault("sheets", False)
    return publish.sync(p.d, p.out, moment=moment, **kw)


def built(proj) -> Project:
    return proj.stage("export").caches().change()


def test_the_export_moment_removes_the_caches_and_keeps_everything_else(proj):
    built(proj)
    outside = files_outside_cache(proj)
    sizes = sum(f.stat().st_size for rel in REMOVED for f in ([proj.d / "cache" / rel] if (proj.d / "cache" / rel).is_file() else (proj.d / "cache" / rel).rglob("*")) if f.is_file())
    res = sync(proj)
    c = res["clean"]
    assert c["done"] is True and c["freed_bytes"] == sizes and c["files"] > 5
    cache = proj.d / "cache"
    for rel in REMOVED:
        assert not (cache / rel).exists(), rel
    for rel in KEPT:
        assert (cache / rel).is_file(), rel
    assert files_outside_cache(proj) == outside, "no document, history copy, change record, picture, audio or export file was touched"
    st = proj.state()
    assert st["clean"]["done"] and st["clean"]["freed_bytes"] == sizes
    assert "export" in st["clean"]["removed"][0] or any("cache/export" in x for x in st["clean"]["removed"])
    md = proj.text("README.md")
    assert "Dọn dẹp thư mục làm việc" in md and "giải phóng" in md
    from bti.output import words
    assert words.size(sizes) in md


def test_the_list_of_cache_paths_is_exactly_the_documented_one(proj):
    built(proj)
    (proj.d / "cache" / "zzz").mkdir()
    (proj.d / "cache" / "zzz" / "other.bin").write_bytes(b"x")
    got = {p.relative_to(proj.d / "cache").as_posix() for p in clean.targets(proj.d)}
    assert got == {"export/chapters.ffmeta", "export/parts/part_01_x.mp4", "export/video_all.mp4", "frames", "thumbs", "previews", "uploads", "picks_auto/runs", "voice", "longjobs/work", "wave_abc_4000.json",
                   "longjobs/1111111111111111.log", "longjobs/2222222222222222.log"}, got
    sync(proj)
    assert (proj.d / "cache" / "zzz" / "other.bin").exists(), "a path that is not on the list is never touched"


def test_the_switch_turns_the_cleaning_off(proj, set_clean):
    built(proj)
    set_clean(False)
    res = sync(proj)
    assert res["clean"] == {"done": False, "reason": "switched_off", "at": res["clean"]["at"]}
    assert (proj.d / "cache" / "export" / "video_all.mp4").exists()
    assert "bạn đã tắt việc tự dọn" in proj.text("README.md")
    set_clean(True)
    assert sync(proj)["clean"]["done"] is True


def test_nothing_is_cleaned_after_a_failed_export(proj):
    proj.stage("approve_storyboard").caches()            # the export never finished: no manifest, only the render parts in cache/export
    res = sync(proj)
    assert res["clean"] == {"done": False, "reason": "export_failed", "at": res["clean"]["at"]}
    assert (proj.d / "cache" / "export" / "parts" / "part_01_x.mp4").exists()
    assert "final.mp4" not in proj.tree()


def test_nothing_is_cleaned_when_the_export_reports_an_error(proj):
    proj.stage("approve_storyboard").export(status="error").caches()
    res = sync(proj)
    assert res["clean"]["reason"] == "export_failed" and (proj.d / "cache" / "export" / "video_all.mp4").exists()


def test_nothing_is_cleaned_while_another_job_runs(proj):
    built(proj)
    res = sync(proj, busy=lambda: {"id": "abcdabcdabcdabcd", "kind": "voice"})
    assert res["clean"]["reason"] == "job_running" and (proj.d / "cache" / "export" / "video_all.mp4").exists()


def test_the_calling_jobs_own_log_stays(proj):
    built(proj)
    proj.job("4444444444444444", "export")
    res = sync(proj, job={"id": "4444444444444444", "kind": "export"})
    assert res["clean"]["done"] and (proj.d / "cache" / "longjobs" / "4444444444444444.log").exists() and (proj.d / "cache" / "longjobs" / "4444444444444444.json").exists()
    assert not (proj.d / "cache" / "longjobs" / "1111111111111111.log").exists()
    jobs = json.loads(proj.text("log/jobs.json"))["jobs"]
    exp = next(j for j in jobs if j["id"] == "4444444444444444")
    assert exp["state"] == "done" and exp["kind"] == "export", "the job that is calling is written as done, not as running"


def test_a_rebuild_cleans_only_when_asked(proj):
    built(proj)
    sync(proj, "rebuild", explicit=True)
    assert (proj.d / "cache" / "export" / "video_all.mp4").exists()
    res = sync(proj, "rebuild", explicit=True, clean=True)
    assert res["clean"]["done"] and not (proj.d / "cache" / "export").exists()


def test_dry_run_changes_nothing(proj):
    built(proj)
    r = clean.clean_project(proj.d, dry_run=True)
    assert r["freed_bytes"] > 0 and (proj.d / "cache" / "export" / "video_all.mp4").exists()


def test_a_second_cleaning_has_nothing_to_do_and_does_not_fail(proj):
    built(proj)
    sync(proj)
    r = clean.clean_project(proj.d)
    assert r["done"] is True and r["freed_bytes"] <= 100            # only the log files made since


def test_current_export_parts_are_kept_while_stale_parts_and_video_all_go(proj):
    built(proj)
    cur = proj.d / "cache" / "export" / "parts" / "part_01_cur.mp4"
    cur.write_bytes(b"CUR" * 400)
    m = json.loads((proj.d / "export" / "export.json").read_text(encoding="utf-8"))
    m["parts"] = [{"index": 1, "key": "cur", "file": "part_01_cur.mp4", "did_render": True}]
    m["parts_total"], m["parts_rendered"], m["parts_reused"] = 1, 1, 0
    (proj.d / "export" / "export.json").write_text(json.dumps(m), encoding="utf-8")

    res = sync(proj)
    c = res["clean"]
    assert c["done"] is True
    assert c["kept_parts"] == 1 and c["kept_parts_bytes"] == cur.stat().st_size
    assert cur.is_file()
    assert not (proj.d / "cache" / "export" / "parts" / "part_01_x.mp4").exists()
    assert not (proj.d / "cache" / "export" / "video_all.mp4").exists()
    md = proj.text("README.md")
    assert "Các đoạn dựng" in md and "Đã giữ lại **1 đoạn dựng** của lần xuất này" in md
