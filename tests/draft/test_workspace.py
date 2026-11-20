import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bti.draft import workspace as W
from bti.draft.compile import compile_specs
from bti.draft.inputs import clone_inputs, load_inputs
from bti.draft.providers import auto
from helpers import GOOD

REPO = Path(__file__).resolve().parents[2]


def test_workspace_holds_copies_only(proj, tmp_path):
    inp = load_inputs(proj)
    ws = W.build(inp, root=tmp_path / "ws")
    r = ws.root
    for f in ("TASK.md", "inputs/beats.json", "inputs/words.tsv", "inputs/assets.json", "inputs/techniques.md", "inputs/style.json",
              "inputs/compile_input.json", "images/A.jpg", "images/B.jpg"):
        assert (r / f).is_file(), f
    assert (r / "out").is_dir() and (r / "look").is_dir()
    assert not (r / "INSTRUCTION.md").exists()
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in r.rglob("*") if p.is_file() and p.suffix in (".md", ".json", ".tsv", ".cmd", ""))
    assert str(proj) not in text.replace(str(REPO), "")
    assert not str(r).startswith(str(proj)) and not str(r).startswith(str(REPO))
    assert (r / "words.tsv").exists() is False
    assert len((r / "inputs" / "words.tsv").read_text().splitlines()) == 61


def test_images_are_downscaled_with_the_scale_recorded(tmp_path):
    import cv2
    from helpers import make_synth_project
    p = make_synth_project(tmp_path / "projects" / "big")
    big = cv2.imread(str(p / "media" / "a.jpg"))
    import numpy as np
    big = cv2.resize(big, (3200, 4800))
    cv2.imwrite(str(p / "media" / "a.jpg"), big)
    a = json.loads((p / "picks.json").read_text())
    a["assets"]["A"]["width"], a["assets"]["A"]["height"] = 3200, 4800
    (p / "picks.json").write_text(json.dumps(a))
    ws = W.build(load_inputs(p), root=tmp_path / "ws")
    im = cv2.imread(str(ws.root / "images" / "A.jpg"))
    assert max(im.shape[:2]) <= 1568
    rec = json.loads((ws.root / "inputs" / "assets.json").read_text())["assets"]["A"]
    assert rec["source_size"] == [3200, 4800] and rec["scale"] == pytest.approx(3200 / im.shape[1], rel=0.01)


def test_techniques_md_lists_every_available_technique(proj, tmp_path):
    ws = W.build(load_inputs(proj), root=tmp_path / "ws")
    md = (ws.root / "inputs" / "techniques.md").read_text(encoding="utf-8")
    from bti.engine import registry as R
    for t in R.load_bundle("gae").techniques:
        if t["engine"]["available"] and (t["offered"] or t["hidden_reason"]["code"] == "program"):         # catalogue pass: what is hidden from the models is not listed
            assert "### %s " % t["id"] in md
        elif t["engine"]["available"]:
            assert "### %s " % t["id"] not in md
    assert "SHORTS ONLY" not in md and "## Choosing by the kind of line" in md


def test_task_md_is_rendered_for_the_mode(proj, tmp_path):
    inp = load_inputs(proj)
    ws = W.build(inp, root=tmp_path / "ws")
    t = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "{{" not in t and "Mode: **draft**" in t and "Edit mode: changing" not in t and "- `c01` Intro" in t
    assert "check" in t and ("check.cmd" in t or "./check" in t)
    for rule in ("Work only inside this folder", "Never touch a locked shot", "Never put the narration's words on screen"):
        assert rule in t
    ws2 = W.build(clone_inputs(inp, edit_shots=set()) if False else inp, root=tmp_path / "ws2", instruction="zoom slower on the mirror", scope_words="chapter 1")
    t2 = (ws2.root / "TASK.md").read_text(encoding="utf-8")
    assert "Mode: **edit**" in t2 and "Edit mode: changing" in t2 and "{{" not in t2
    assert "zoom slower on the mirror" in (ws2.root / "INSTRUCTION.md").read_text(encoding="utf-8")


def test_current_storyboard_is_written_as_specs_with_marks(proj, tmp_path):
    inp = load_inputs(proj)
    cur = compile_specs(inp, {c: __import__("helpers").clean_spec(s, c) for c, s in GOOD.items()}, draw=False).storyboard
    cur["shots"][1]["locked"] = True
    (proj / "storyboard.json").write_text(json.dumps(cur), encoding="utf-8")
    inp2 = clone_inputs(load_inputs(proj), edit_shots={cur["shots"][0]["id"]})
    ws = W.build(inp2, root=tmp_path / "ws", instruction="x")
    d = json.loads((ws.root / "inputs" / "current" / "c01.json").read_text())
    assert d["shots"][0]["in_scope"] is True and d["shots"][1]["locked"] is True and d["shots"][1]["in_scope"] is False


def test_read_out_reads_only_out_and_reports_problems(proj, tmp_path):
    inp = load_inputs(proj)
    ws = W.build(inp, root=tmp_path / "ws")
    out = ws.root / "out"
    (out / "c01.json").write_text(json.dumps(GOOD["c01"]), encoding="utf-8")
    (out / "c02.json").write_text("{bad", encoding="utf-8")
    (out / "notes.md").write_text("Summary line\nmore", encoding="utf-8")
    (ws.root / "c03.json").write_text("{}", encoding="utf-8")                 # outside out/: ignored
    r = W.read_out(ws.root, ["c01", "c02"], inp.picks["assets"])
    assert list(r.specs) == ["c01"] and r.notes.startswith("Summary") and r.problems[0]["code"] == "spec_json"
    if os.name != "nt":
        (out / "c02.json").unlink()
        (out / "c02.json").symlink_to(proj / "timing.json")
        assert W.read_out(ws.root, ["c02"]).problems[0]["code"] == "spec_symlink"


def test_workspace_compile_matches_the_project_compile(proj, tmp_path):
    inp = load_inputs(proj)
    ws = W.build(inp, root=tmp_path / "ws")
    for cid, sp in auto.draft(inp).items():
        (ws.root / "out" / (cid + ".json")).write_text(json.dumps(sp), encoding="utf-8")
    res, _ = W.workspace_compile(ws.root, draw=True)
    assert not res.errors, res.errors
    ref = compile_specs(inp, {c: __import__("helpers").clean_spec(s, c) for c, s in auto.draft(inp).items()}, draw=False)
    strip = lambda d: [(s["id"], s["technique"], s["start"]) for s in d["shots"]]
    assert strip(res.storyboard) == strip(ref.storyboard)


def test_workspace_handles_video_assets_and_compiles_foot_01(proj, tmp_path):
    import cv2
    import numpy as np
    vpath = proj / "media" / "clip.mp4"
    wr = cv2.VideoWriter(str(vpath), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 180))
    for i in range(15):
        wr.write(np.full((180, 320, 3), 50 + i * 10, dtype=np.uint8))
    wr.release()
    pk = json.loads((proj / "picks.json").read_text(encoding="utf-8"))
    pk["assets"]["V"] = {
        "file": "media/clip.mp4", "kind": "video", "title": "Process clip", "artist": "", "year": "",
        "width": 320, "height": 180, "duration": 1.5,
        "credit": {"source": "upload", "source_url": "", "author": "Me", "licence": "CC0", "licence_url": "", "flag": None},
        "regions": {},
    }
    pk["beats"]["b0001"] = {"items": [{"asset": "V", "region": None, "role": "video", "note": "first sentence"}], "status": "picked", "note": ""}
    (proj / "picks.json").write_text(json.dumps(pk), encoding="utf-8")

    inp = load_inputs(proj)
    ws = W.build(inp, root=tmp_path / "ws_vid")
    assert (ws.root / "images" / "V.jpg").is_file() and (ws.root / "images" / "V.mp4").is_file()
    va = json.loads((ws.root / "inputs" / "assets.json").read_text(encoding="utf-8"))["assets"]["V"]
    assert va["kind"] == "video" and va["file"] == "images/V.jpg" and "FOOT-01" in va["note"]

    specs = auto.draft(inp)
    assert specs["c01"]["shots"][0]["technique"] == "FOOT-01"
    for cid, sp in specs.items():
        (ws.root / "out" / (cid + ".json")).write_text(json.dumps(sp), encoding="utf-8")
    res, _ = W.workspace_compile(ws.root, draw=True)
    assert not res.errors, res.errors
    assert res.storyboard["shots"][0]["technique"] == "FOOT-01"


def _run(module, ws, *args):
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE")}
    env["PYTHONPATH"] = str(REPO)
    return subprocess.run([sys.executable, "-m", module, *args], cwd=str(ws), env=env, capture_output=True, text=True, timeout=240)


def test_helper_commands_run_from_the_workspace(proj, tmp_path):
    inp = load_inputs(proj)
    ws = W.build(inp, root=tmp_path / "ws")
    for cid, sp in auto.draft(inp).items():
        (ws.root / "out" / (cid + ".json")).write_text(json.dumps(sp), encoding="utf-8")
    (ws.root / "out" / "notes.md").write_text("Test draft", encoding="utf-8")
    r = _run("bti.draft.check", ws.root, "--no-draw")
    assert r.returncode == 0 and "0 error(s)" in r.stdout, r.stdout + r.stderr
    r = _run("bti.draft.defaults", ws.root, "CAM-05", "--asset", "A", "--region", "MIRROR", "--workspace", ".")
    assert r.returncode == 0 and '"camera"' in r.stdout, r.stdout + r.stderr
    r = _run("bti.draft.still", ws.root, "--shot", "c01:2", "-o", "look/x.jpg", "--width", "320")
    assert r.returncode == 0 and (ws.root / "look" / "x.jpg").is_file(), r.stdout + r.stderr
    r = _run("bti.draft.check", ws.root, "--chapter", "c01")
    assert "draw check: done" in r.stdout


def test_check_reports_a_problem_and_exits_nonzero(proj, tmp_path):
    inp = load_inputs(proj)
    ws = W.build(inp, root=tmp_path / "ws")
    bad = json.loads(json.dumps(GOOD["c01"]))
    bad["shots"][1]["technique"] = "NOPE-9"
    (ws.root / "out" / "c01.json").write_text(json.dumps(bad), encoding="utf-8")
    r = _run("bti.draft.check", ws.root, "--no-draw")
    assert r.returncode == 1 and "chapter c01, shot 2" in r.stdout and "c02" in r.stdout      # c02 is missing


def test_wrapper_scripts_work_from_the_workspace_without_pythonpath(proj, tmp_path):
    inp = load_inputs(proj)
    ws = W.build(inp, root=tmp_path / "ws")
    for cid, sp in auto.draft(inp).items():
        (ws.root / "out" / (cid + ".json")).write_text(json.dumps(sp), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE", "COMSPEC")}
    cmd = [str(ws.root / "check.cmd")] if os.name == "nt" else [str(ws.root / "check")]
    r = subprocess.run(cmd + ["--no-draw"], cwd=str(ws.root), env=env, capture_output=True, text=True, timeout=240)
    assert r.returncode == 0 and "0 error(s)" in r.stdout, r.stdout + r.stderr
    r = subprocess.run([str(ws.root / ("still.cmd" if os.name == "nt" else "still")), "--shot", "c02:1", "--width", "200"], cwd=str(ws.root), env=env,
                       capture_output=True, text=True, timeout=240)
    assert r.returncode == 0 and (ws.root / "look" / "c02_1.jpg").is_file(), r.stdout + r.stderr
