"""Tests of step 6 (export). Everything runs with fakes (a fake engine/ffmpeg/ffprobe script and a fake long-job runner) except
the few tests marked `server`, which render five seconds at final quality with the real programs. Those run only with
`--run-server`; each of them takes the heavy slot itself (`bti.longjob.heavy`, lock folder from config/server.json).
Nothing here writes to the real `projects/` folders."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import fakelongjob  # noqa: E402
from bti.editor.common import compute_rev  # noqa: E402
from bti.export import render  # noqa: E402
from bti.export.settings import Settings  # noqa: E402

FAKE = str(HERE / "fake_tools.py")


def pytest_addoption(parser):
    parser.addoption("--run-server", action="store_true", default=False, help="run the tests marked `server` (real programs; Windows server, heavy slot held)")


def pytest_configure(config):
    config.addinivalue_line("markers", "server: real engine and ffmpeg for five seconds; only on the Windows server, under the heavy slot")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-server"):
        return
    skip = pytest.mark.skip(reason="server test: needs --run-server (the test takes the heavy slot itself)")
    for it in items:
        if "server" in it.keywords:
            it.add_marker(skip)


@pytest.fixture()
def fake_tools(tmp_path):
    log = tmp_path / "fake.log"
    env = {"FAKE_LOG": str(log)}
    t = render.Tools(ffmpeg=[sys.executable, FAKE, "ffmpeg"], ffprobe=[sys.executable, FAKE, "ffprobe"],
                     engine=lambda project_dir, spec, out, settings: [sys.executable, FAKE, "engine", "render", str(project_dir), "--t0", "%.6f" % spec.t0,
                                                                      "--t1", "%.6f" % spec.t1, "--fps", str(spec.fps), "-o", str(out)],
                     cwd=tmp_path, env=env)
    t.log = log
    t.calls = lambda prog=None: [json.loads(x) for x in (log.read_text().splitlines() if log.exists() else []) if prog is None or json.loads(x)["prog"] == prog]
    return t


@pytest.fixture()
def settings():
    return Settings(render_threads=2, part_seconds=240.0, render_speed=2.0)


@pytest.fixture()
def manager():
    return fakelongjob.FakeManager()


@pytest.fixture()
def project(tmp_path):
    """A temp copy of the arnolfini project (storyboard, timing, project.json) with a FAKE audio file, approved."""
    src = REPO / "projects" / "arnolfini"
    d = tmp_path / "projects" / "arnolfini"
    d.mkdir(parents=True)
    for n in ("storyboard.json", "timing.json", "project.json"):
        shutil.copy(src / n, d / n)
    (d / "audio").mkdir()
    (d / "audio" / "mix.m4a").write_text(json.dumps({"kind": "audio", "codec": "aac", "duration": 820.8333}))
    approve(d)
    return d


def approve(d: Path) -> str:
    sb = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
    rev = compute_rev(sb)
    sb["approvals"] = {"storyboard": {"rev": rev, "at": "2026-11-16T12:00:00"}}
    (d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    return rev


def real_timeline(d: Path):
    """Shot starts and end of the arnolfini storyboard without the engine (the engine is exercised in test_timeline)."""
    sb = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
    starts = sorted(float(s["start"]["t"]) for s in sb["shots"] if isinstance(s.get("start"), dict) and "t" in s["start"])
    return starts, float(sb["end"]["t"])


@pytest.fixture()
def patch_run(monkeypatch, fake_tools, manager):
    """Makes `bti.export.run` use the fake tools, the fake runner and the Part class of the fake runner."""
    from bti.export import run
    monkeypatch.setattr(run, "get_manager", lambda: manager)
    monkeypatch.setattr(run, "_part_cls", lambda pc: fakelongjob.Part)
    monkeypatch.setattr(run.render.Tools, "from_settings", classmethod(lambda cls, s: fake_tools))
    monkeypatch.setattr(run, "engine_timeline", lambda d, rev: real_timeline(Path(d)))
    return run
