"""The three helper commands (`check`, `defaults`, `still`) refuse an output path or a workspace path that resolves outside the workspace
they were started in: exit status 2 and one plain sentence on standard error, nothing written. `..` and symbolic links are resolved first.
The normal calls (a path inside, `.`, a folder that does not exist yet below the workspace) are untouched: tests/draft/test_workspace.py
runs the real commands end to end."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti.draft.check import inside_workspace  # noqa: E402


def _run(module: str, cwd: Path, *args: str):
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE", "COMSPEC")}
    env["PYTHONPATH"] = str(REPO)
    env["PYTHONUTF8"] = "1"
    return subprocess.run([sys.executable, "-m", module, *args], cwd=str(cwd), env=env, capture_output=True, text=True, timeout=240)


@pytest.fixture()
def ws(tmp_path):
    w = tmp_path / "ws"
    (w / "look").mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    return w


def _link(target: Path, link: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("this machine does not allow symbolic links")


def _refused(r) -> None:
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    lines = [ln for ln in r.stderr.strip().splitlines() if ln.strip()]
    assert len(lines) == 1 and "outside the workspace" in lines[0], r.stderr               # one plain sentence
    assert r.stdout.strip() == ""


# ---------------------------------------------------------------- the rule itself
def test_a_path_inside_the_workspace_is_inside(ws, monkeypatch):
    monkeypatch.chdir(ws)
    for p in (".", "", "look/x.jpg", "look/../look/x.jpg", "not/yet/made/x.jpg", str(ws), str(ws / "look" / "a.jpg")):
        assert inside_workspace(p), p


def test_dotdot_and_absolute_paths_outside_are_outside(ws, monkeypatch):
    monkeypatch.chdir(ws)
    for p in ("..", "../x.jpg", "look/../../x.jpg", str(ws.parent), str(ws.parent / "outside" / "x.jpg"), os.path.abspath(os.sep)):
        assert not inside_workspace(p), p


def test_a_symbolic_link_out_of_the_workspace_is_followed(ws, monkeypatch):
    _link(ws.parent / "outside", ws / "lnk")
    monkeypatch.chdir(ws)
    assert not inside_workspace("lnk")
    assert not inside_workspace("lnk/x.jpg")                       # a file that does not exist yet below the link
    assert not inside_workspace(str(ws / "lnk" / "x.jpg"))
    (ws.parent / "outside" / "f.txt").write_text("x", encoding="utf-8")
    _link(ws.parent / "outside" / "f.txt", ws / "look" / "f.jpg")
    assert not inside_workspace("look/f.jpg")                      # the last part is a link to a file outside


def test_a_symbolic_link_inside_the_workspace_stays_inside(ws, monkeypatch):
    (ws / "real").mkdir()
    _link(ws / "real", ws / "alias")
    monkeypatch.chdir(ws)
    assert inside_workspace("alias/x.jpg")


def test_the_workspace_itself_may_be_reached_through_a_link(ws, tmp_path, monkeypatch):
    _link(ws, tmp_path / "ws_link")
    monkeypatch.chdir(tmp_path / "ws_link")                        # started in a folder reached through a link
    assert inside_workspace("look/x.jpg") and not inside_workspace("../outside/x.jpg")


@pytest.mark.skipif(os.name != "nt", reason="Windows file names: case does not matter, a drive is a different tree")
def test_windows_names_are_compared_the_way_windows_does(ws, monkeypatch):
    monkeypatch.chdir(ws)
    assert inside_workspace(str(ws).upper())
    assert inside_workspace(str(ws / "look").lower() + "\\x.jpg")
    other = "Z:\\" if not str(ws).upper().startswith("Z:") else "Y:\\"
    assert not inside_workspace(other + "x.jpg")


# ---------------------------------------------------------------- the three commands
@pytest.mark.parametrize("bad", ["..", "../outside"])
def test_check_refuses_a_workspace_outside(ws, bad):
    _refused(_run("bti.draft.check", ws, bad, "--no-draw"))


def test_check_refuses_an_absolute_workspace_outside_and_a_link(ws):
    _refused(_run("bti.draft.check", ws, str(ws.parent / "outside"), "--no-draw"))
    _link(ws.parent / "outside", ws / "lnk")
    _refused(_run("bti.draft.check", ws, "lnk", "--no-draw"))


def test_check_on_the_workspace_itself_is_not_refused(ws):
    r = _run("bti.draft.check", ws, ".", "--no-draw")               # not a draft workspace: it says so, but it is not the refusal
    assert r.returncode == 2 and "outside the workspace" not in r.stderr and "workspace_invalid" in r.stdout, (r.stdout, r.stderr)


@pytest.mark.parametrize("bad", ["..", "../outside"])
def test_defaults_refuses_a_workspace_outside(ws, bad):
    _refused(_run("bti.draft.defaults", ws, "CAM-05", "--workspace", bad))


def test_defaults_refuses_a_link_to_a_workspace_outside(ws):
    _link(ws.parent / "outside", ws / "lnk")
    _refused(_run("bti.draft.defaults", ws, "CAM-05", "--asset", "A", "--workspace", "lnk"))
    _refused(_run("bti.draft.defaults", ws, "CAM-05", "--workspace", str(ws.parent)))


def test_defaults_without_a_workspace_still_prints_the_technique(ws):
    r = _run("bti.draft.defaults", ws, "CAM-05")
    assert r.returncode == 0 and "CAM-05" in r.stdout and r.stderr.strip() == "", (r.stdout, r.stderr)
    r = _run("bti.draft.defaults", ws, "CAM-05", "--workspace", ".")
    assert r.returncode == 0 and "CAM-05" in r.stdout, (r.stdout, r.stderr)


@pytest.mark.parametrize("out", ["../x.jpg", "look/../../x.jpg", "../outside/x.jpg"])
def test_still_refuses_an_output_path_outside(ws, out):
    _refused(_run("bti.draft.still", ws, "--shot", "c01:1", "-o", out))
    assert not (ws.parent / "x.jpg").exists() and not (ws.parent / "outside" / "x.jpg").exists()


def test_still_refuses_an_absolute_output_path_outside(ws):
    dest = ws.parent / "outside" / "x.jpg"
    _refused(_run("bti.draft.still", ws, "--shot", "c01:1", "-o", str(dest)))
    assert not dest.exists()


def test_still_refuses_an_output_path_through_a_link(ws):
    _link(ws.parent / "outside", ws / "lnk")
    _refused(_run("bti.draft.still", ws, "--shot", "c01:1", "-o", "lnk/x.jpg"))
    assert not (ws.parent / "outside" / "x.jpg").exists()


def test_still_refuses_a_workspace_outside(ws):
    _refused(_run("bti.draft.still", ws, "..", "--shot", "c01:1", "-o", "look/x.jpg"))
    _refused(_run("bti.draft.still", ws, str(ws.parent / "outside"), "--shot", "c01:1"))


def test_the_default_output_is_refused_when_the_look_folder_is_a_link(ws, monkeypatch, capsys):
    (ws / "look").rmdir()
    _link(ws.parent / "outside", ws / "look")                      # no -o: the default look/c01_1.jpg would land outside
    monkeypatch.chdir(ws)
    from bti.draft.check import refuse_outside
    assert refuse_outside(ws / "look" / "c01_1.jpg", "the output path") == 2
    assert "outside the workspace" in capsys.readouterr().err


def test_still_with_a_path_inside_gets_past_the_refusal(ws):
    r = _run("bti.draft.still", ws, "--shot", "c01:1", "-o", "look/x.jpg")     # not a draft workspace: it says so, but it is not the refusal
    assert "outside the workspace" not in r.stderr and "workspace_invalid" in r.stdout, (r.stdout, r.stderr)
    r = _run("bti.draft.still", ws, "--shot", "c01:1", "-o", "new_folder/below/x.jpg")
    assert "outside the workspace" not in r.stderr and "workspace_invalid" in r.stdout, (r.stdout, r.stderr)
