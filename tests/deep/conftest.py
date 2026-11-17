"""Deep backend tests: run on temporary COPIES of projects/ and library/, with the mock model only and no network.

Run on its own (not part of the normal suites):
    .venv/bin/python -m pytest tests/deep -p no:cacheprovider -q
Every bug of docs/qa/BUGS_backend.md has a test `test_B0NN_*` that FAILS while the bug exists.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bti.editor.app import create_app  # noqa: E402
from bti.library import config as libcfg  # noqa: E402

BASE_PROJECTS = ("technique_lab", "arnolfini", "arnolfini-from-books", "lab_text")


def _clone(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    r = None
    if sys.platform == "darwin":                                                 # APFS clone: cheap (no `cp` on Windows)
        r = subprocess.run(["cp", "-Rc", str(src), str(dst)], capture_output=True)
    if r is None or r.returncode != 0:
        shutil.copytree(src, dst, symlinks=True)
    for sub in ("cache", "history"):
        shutil.rmtree(dst / sub, ignore_errors=True)


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


@pytest.fixture(scope="session")
def data_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("deep")
    proj = root / "projects"
    proj.mkdir()
    for p in BASE_PROJECTS:
        _clone(REPO / "projects" / p, proj / p)
    _clone(REPO / "library", root / "library")
    return root


@pytest.fixture(scope="session", autouse=True)
def _patch_library(data_root):
    """The library module reads module-level paths; point them at the copy (never the real library)."""
    old = (libcfg.LIB_DIR, libcfg.PROJECTS_DIR)
    libcfg.LIB_DIR, libcfg.PROJECTS_DIR = data_root / "library", data_root / "projects"
    yield
    libcfg.LIB_DIR, libcfg.PROJECTS_DIR = old


@pytest.fixture(scope="session")
def projects_root(data_root) -> Path:
    return data_root / "projects"


@pytest.fixture(scope="session")
def app(projects_root):
    return create_app(projects_root=projects_root)


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def make_project(projects_root):
    """make_project(src, name) -> name: a private clone of a base project."""
    made: list[Path] = []

    def mk(src: str, name: str) -> str:
        _clone(projects_root / src, projects_root / name)
        made.append(projects_root / name)
        return name
    yield mk
    for d in made:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def lab(make_project):
    return make_project("technique_lab", "t_lab")


@pytest.fixture()
def arn(make_project):
    return make_project("arnolfini", "t_arn")


@pytest.fixture()
def script_pid(make_project):
    return make_project("arnolfini-from-books", "t_script")


def state(client, pid):
    r = client.get(f"/api/projects/{pid}")
    assert r.status_code == 200, r.text
    return r.json()


def put_sb(client, pid, sb, rev):
    return client.put(f"/api/projects/{pid}/storyboard", json={"storyboard": sb, "base_rev": rev})


def wait_job(client, jid, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if j.get("state") in ("done", "error", "cancelled"):
            return j
        time.sleep(0.1)
    raise AssertionError("job timeout")


def script_to_narration(client, pid):
    """Mock outline, approve, mock narration. Returns the narration payload."""
    P = f"/api/projects/{pid}"
    r = client.post(f"{P}/outline/generate", json={"model": "mock"})
    assert r.status_code == 200, r.text
    assert wait_job(client, r.json()["job_id"])["state"] == "done"
    o = client.get(f"{P}/outline").json()
    assert client.post(f"{P}/outline/approve", json={"rev": o["rev"]}).status_code == 200
    r = client.post(f"{P}/narration/generate", json={"model": "mock", "force": True})
    assert r.status_code == 200, r.text
    assert wait_job(client, r.json()["job_id"])["state"] == "done"
    return client.get(f"{P}/narration").json()


def pytest_configure(config):
    config.addinivalue_line("markers", "timing: wall-clock test, can fail on a loaded machine; skip with -m 'not timing'")
