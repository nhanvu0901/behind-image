"""R3B-001: approval draws its samples one at a time; the process-wide ENGINE_LOCK is free between samples."""
from __future__ import annotations

import shutil
import statistics
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from bti.editor.app import create_app

REPO = Path(__file__).resolve().parents[2]


def _copy(root: Path, name: str) -> None:
    shutil.copytree(REPO / "projects" / name, root / name, ignore=shutil.ignore_patterns("cache", "history"))


def test_approve_does_not_hold_the_engine_lock_across_samples(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    _copy(root, "arnolfini")
    _copy(root, "technique_lab")
    app = create_app(projects_root=root)
    with TestClient(app, raise_server_exceptions=False) as c:
        st = c.get("/api/projects/arnolfini").json()
        other = c.get("/api/projects/technique_lab").json()
        t = other["storyboard"]["shots"][0]["_t0"] + 0.1
        box = {}
        th = threading.Thread(target=lambda: box.update(r=c.post("/api/projects/arnolfini/approve", json={"rev": st["rev"]})))
        th.start()
        time.sleep(0.5)
        gets, frames = [], []
        while th.is_alive() and len(gets) < 5:
            a = time.perf_counter()
            assert c.get("/api/projects/technique_lab").status_code == 200
            gets.append(time.perf_counter() - a)
            a = time.perf_counter()
            assert c.get(f"/api/projects/technique_lab/frame?t={t}&width=320").status_code == 200
            frames.append(time.perf_counter() - a)
        th.join()
        assert box["r"].status_code in (200, 422), box["r"].text
        assert gets, "the approval finished before any request could be measured"
        assert statistics.median(gets) < 0.5 and statistics.median(frames) < 0.5, (gets, frames)
