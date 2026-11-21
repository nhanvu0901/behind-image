"""Round 2: the engine command line (`python -m bti.engine`) on a temp copy. Exit codes and messages must be honest."""
from __future__ import annotations

import subprocess
import sys

import pytest

from conftest import REPO


def cli(*args, timeout=120):
    return subprocess.run([sys.executable, "-m", "bti.engine", *map(str, args)], cwd=REPO, capture_output=True, text=True,
                          timeout=timeout)


@pytest.fixture()
def cdir(make_project, projects_root):
    return projects_root / make_project("technique_lab", "t_r2_cli")


def test_R2B_003_render_backwards_range_is_refused(cdir, tmp_path):
    out = tmp_path / "back.mp4"
    r = cli("render", cdir, "--t0", 5, "--t1", 2, "-o", out, "--width", 160, "--fps", 5)
    assert r.returncode != 0, "t1 < t0 is accepted and a one-frame video is written"
    assert not out.exists()


def test_R2B_003_still_with_nan_or_negative_time_is_refused(cdir, tmp_path):
    for t in ("nan", "-3", "inf"):
        out = tmp_path / f"s{t}.png"
        r = cli("still", cdir, t, "-o", out, "--width", 160)
        assert r.returncode != 0, f"still at t={t} wrote a picture and exited 0"


def test_R2B_003_render_with_zero_fps_or_width_is_refused(cdir, tmp_path):
    for flag in ("--fps", "--width"):
        out = tmp_path / f"z{flag[2:]}.mp4"
        r = cli("render", cdir, "--t0", 0, "--t1", 1, "-o", out, flag, 0)
        assert r.returncode != 0, f"{flag} 0 is silently replaced by the default and a video is written"


def test_R2B_004_cli_errors_are_messages_not_tracebacks(cdir, tmp_path):
    cases = [
        ("validate", tmp_path / "no_such_project"),
        ("still", cdir, 1, "-o", tmp_path / "w.png", "--width", 0),
        ("still", cdir, 1, "-o", tmp_path / "w.txt", "--width", 160),
        ("render", cdir, "--t0", 0, "--t1", 1, "-o", tmp_path / "t.mp4", "--width", 160, "--fps", 5, "--threads", -2),
    ]
    for args in cases:
        r = cli(*args)
        assert r.returncode != 0
        assert "Traceback" not in r.stderr, f"{args[0]} {args[1:]}: a Python traceback instead of a message:\n{r.stderr[-300:]}"
