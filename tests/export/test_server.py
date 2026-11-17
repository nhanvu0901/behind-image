"""Real programs, five seconds of video. Only on the Windows server, with the heavy slot held by the caller:
    tools/deploy/remote_test.sh tests/export/test_server.py --run-server -s
Each test takes the heavy slot itself (checks first, lock folder, release even on failure). Never a full export."""
import time
import json
import shutil
import subprocess
import sys

import pytest

from bti.export import check, plan, render, run
from bti.export.settings import REPO_ROOT, load_settings
from conftest import REPO, approve, fakelongjob

pytestmark = pytest.mark.server

SECONDS = 5


@pytest.fixture(autouse=True)
def heavy_slot():
    """The test cannot run outside the heavy slot: free-memory and production-process checks, `D:\\bench\\_heavy.lock`, released at the end."""
    from bti.longjob import HeavySlot, load_config
    slot = HeavySlot(load_config(), own_markers=(str(REPO_ROOT),))
    with slot.hold("export server test (5 s of video)", expected_seconds=300):
        yield


@pytest.fixture()
def real_project(tmp_path):
    src = REPO / "projects" / "arnolfini"
    d = tmp_path / "projects" / "arnolfini"
    shutil.copytree(src, d, ignore=shutil.ignore_patterns("cache", "history", "audio"))
    (d / "audio").mkdir()
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-nostdin", "-i", str(src / "audio" / "mix.m4a"), "-t", str(SECONDS), "-c", "copy", str(d / "audio" / "mix.m4a")], capture_output=True)
    assert r.returncode == 0, r.stderr[-300:]
    approve(d)
    return d


def test_one_part_at_final_quality(real_project, tmp_path):
    s = load_settings()
    spec = plan.PartSpec(0, 0, SECONDS * 30, 30)
    out = tmp_path / "p.mp4"
    t = time.time()
    r = subprocess.run(render.engine_command(real_project, spec, out, s), cwd=str(REPO_ROOT), capture_output=True, timeout=900)
    print("\nSERVER-METRIC render: %.1f s of compute for %d s of video (%.2f per second)" % (time.time() - t, SECONDS, (time.time() - t) / SECONDS))
    assert r.returncode == 0, r.stderr[-400:]
    info = check.probe(["ffprobe"], out)
    assert info["video"]["frames"] == 150 and info["video"]["width"] == 1920 and info["video"]["codec"] == "h264"


def test_five_second_export_through_the_job(real_project, monkeypatch):
    s = load_settings()
    mgr = fakelongjob.FakeManager()
    monkeypatch.setattr(run, "get_manager", lambda: mgr)
    monkeypatch.setattr(run, "_part_cls", lambda pc: fakelongjob.Part)
    t = time.time()
    job = run.start(real_project, settings=s, timeline=lambda d, rev: ([0.0], float(SECONDS)))
    print("\nSERVER-METRIC job: %.1f s for %d s of video" % (time.time() - t, SECONDS))
    assert job["state"] == "done", job.get("error")
    m = run.read_manifest(real_project)
    assert m["frames"] == 150
    st = {i["key"]: i for i in m["report"]}
    assert st["frames"]["status"] == "ok" and st["subtitles"]["status"] == "ok" and st["audio"]["status"] == "ok"
    info = check.probe(["ffprobe"], real_project / "export" / "arnolfini.mp4")
    assert info["subtitle"]["codec"] == "mov_text" and info["audio"]["codec"] == "aac" and info["video"]["frames"] == 150
    assert abs(info["video"]["duration"] - SECONDS) < 0.1 and info["duration"] < SECONDS + 1.0   # the 5 s cut still holds cues that end later and len(info["chapters"]) >= 1
    print("SERVER-METRIC frames=%s loudness=%s subtitle=%s audio=%s chapters=%s" % (m["frames"], m["loudness"], info["subtitle"]["codec"], info["audio"]["codec"], len(info["chapters"])))
    assert m["loudness"] is None or isinstance(m["loudness"]["lufs"], float)
