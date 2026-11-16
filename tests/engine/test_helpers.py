import json
import subprocess

import cv2
import numpy as np
import pytest

from bti.engine import helpers as Hh
from bti.engine import registry as R
from bti.engine.base import Ctx
from conftest import make_image


@pytest.fixture()
def ctx(tiny, tiny_project):
    return tiny_project._scene().ctx


def test_tile_rects_grid():
    r = Hh.tile_rects(4, 2, (0, 0, 1000, 600), gutter=20, caption_h=40)
    assert len(r) == 4 and r[0][2] == 490 and r[1][0] == 510 and r[2][1] == r[0][1] + r[0][3] + 20 + 40
    assert all(x + w <= 1000 and y + h <= 600 for x, y, w, h in r)


def test_render_tiles_cover_view_and_caption(ctx):
    f = np.zeros((1080, 1920, 3), np.float32)
    f, rects = Hh.render_tiles(ctx, f, [{"asset": "A", "caption": "ONE", "sub": "sub"}, {"asset": "B", "view": (450, 350, 0.5), "matte": True}], cols=2)
    assert len(rects) == 2
    x, y, w, h = rects[0]
    assert f[y + 5:y + h - 5, x + 5:x + w - 5].mean() > 20                     # panel painted
    assert f[y + h + 5:y + h + 90, x:x + w].max() > 200                         # caption drawn under it
    assert f[:, :30].max() == 0                                                  # margin untouched


def test_mask_alpha_aligned_and_scaled(tiny, tiny_project):
    m = np.zeros((300, 200), np.uint8)                                          # quarter-size mask of image A (800x1200)
    cv2.circle(m, (100, 100), 40, 255, -1)
    cv2.imwrite(str(tiny / "media" / "m.png"), m)
    sb = tiny_project.storyboard()
    sb["assets"]["M"] = {"file": "media/m.png", "kind": "mask", "aligned_to": "A", "width": 200, "height": 300}
    tiny_project.use_draft(sb)
    ctx = tiny_project._scene().ctx
    a = Hh.mask_alpha(ctx, "M", 400, 400, 1.0)                                  # camera centred on the mask blob (100*4, 100*4)
    assert a.shape == (1080, 1920, 1) and a.dtype == np.float32
    assert a[540, 960, 0] > 0.99 and a[0, 0, 0] == 0
    assert 0.5 < a.sum() / (np.pi * 160 ** 2) < 1.2                              # blob radius 40 px of mask = 160 source px at zoom 1


def test_video_frame_reader_and_cache(tiny, tiny_project):
    p = str(tiny / "media" / "v.mp4")
    frames = [np.full((90, 160, 3), 20 * i, np.uint8) for i in range(10)]
    pr = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "160x90", "-r", "10", "-i", "-",
                           "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv444p", p], stdin=subprocess.PIPE)
    for fr in frames:
        pr.stdin.write(fr.tobytes())
    pr.stdin.close(); pr.wait()
    sb = tiny_project.storyboard()
    sb["assets"]["VID"] = {"file": "media/v.mp4", "kind": "video"}
    tiny_project.use_draft(sb)
    ctx = tiny_project._scene().ctx
    f0, f5, f9 = (Hh.video_frame(ctx, "VID", t) for t in (0.0, 0.5, 0.9))
    assert abs(int(f5.mean()) - 100) <= 4 and f0.mean() < 5 and abs(int(f9.mean()) - 180) <= 4
    assert abs(int(Hh.video_frame(ctx, "VID", 0.5).mean()) - 100) <= 4          # random access back
    assert abs(int(Hh.video_frame(ctx, "VID", 5.0).mean()) - 180) <= 4          # clamped past the end
    Hh.close_videos()


def test_vertical_panel_blur_computed_once(ctx):
    from bti.engine import base
    base.MISC.clear()
    content = np.full((1080, 608, 3), 120, np.float32)
    a = Hh.vertical_panel(ctx, content, "k1")
    n = base.MISC.stats()["entries"]
    b = Hh.vertical_panel(ctx, content * 0.5, "k1")
    assert base.MISC.stats()["entries"] == n                                    # the ambient fill was reused, not rebuilt
    x0 = (1920 - 608) // 2
    assert a.shape == (1080, 1920, 3) and np.allclose(a[:, x0:x0 + 608], 120) and np.allclose(b[:, x0:x0 + 608], 60)
    assert a[:, :x0 - 50].mean() < 120 * 0.5 and np.array_equal(a[:, :x0 - 50], b[:, :x0 - 50])


def test_text_block_multiline_and_cached(ctx):
    L1 = Hh.text_block(ctx, ["FIRST LINE", "second line"], 960, 540, 50, tracking=4)
    L2 = Hh.text_block(ctx, ["FIRST LINE", "second line"], 960, 540, 50, tracking=4)
    assert L1 is L2
    one = Hh.text_block(ctx, ["FIRST LINE"], 960, 540, 50, tracking=4)
    assert L1.a.shape[0] > one.a.shape[0] * 1.5
    f = np.zeros((1080, 1920, 3), np.float32)
    L1.apply(f, Hh.fade_env(1.0, 0.0, 3.0, 0.1, 0.1))
    assert f.max() > 200 and f[:100].max() == 0


def test_registry_patches_merge_and_errors(tmp_path):
    reg = json.loads((R.STYLE_ROOT / "gae" / "techniques.json").read_text())["techniques"]
    pd = tmp_path / "patches"; pd.mkdir()
    (pd / "b.json").write_text(json.dumps({"CMP-01": {"engine": {"status": "done", "available": True, "impl": "bti.engine.x", "reason": None, "notes": "b"}}}))
    (pd / "a.json").write_text(json.dumps({"CMP-01": {"params": [], "engine": {"status": "done", "available": False, "impl": None, "reason": "from a", "notes": None}}}))
    out = {t["id"]: t for t in R.apply_patches(reg, pd)}
    assert out["CMP-01"]["params"] == [] and out["CMP-01"]["engine"]["notes"] == "b"      # sorted order: b wins; fields replaced wholesale
    assert [t["id"] for t in reg] == [t["id"] for t in R.apply_patches(reg, pd)]
    (pd / "c.json").write_text(json.dumps({"NOPE-99": {"params": []}}))
    with pytest.raises(R.PatchError):
        R.apply_patches(reg, pd)


def test_bundle_loads_patches_from_style_root(tmp_path, monkeypatch):
    import shutil
    root = tmp_path / "style"
    shutil.copytree(R.STYLE_ROOT / "gae", root / "gae", ignore=shutil.ignore_patterns("previews", "patches"))
    (root / "gae" / "patches").mkdir()
    (root / "gae" / "patches" / "x.json").write_text(json.dumps({"CMP-01": {"timing": {"default_s": 9.0, "min_s": 1, "max_s": 20, "anchor": "none"}}}))
    b = R.StyleBundle("gae", root)
    assert b.spec("CMP-01")["timing"]["default_s"] == 9.0


def test_techniques_are_auto_discovered(tmp_path):
    import importlib, pkgutil
    from bti.engine import techniques
    names = {m.name for m in pkgutil.iter_modules(techniques.__path__)}
    assert {"camera", "labels", "annotate"} <= names
    assert "bti.engine.techniques.diagrams" in __import__("sys").modules


def test_list_param_types():
    pts = {"name": "p", "type": "points", "default": [], "min": None, "max": None, "unit": None, "values": None, "measured": None}
    lns = dict(pts, name="l", type="lines")
    assert R.check_value(pts, ["MIRROR", [1, 2.5]]) is None and R.check_value(pts, []) is None
    assert "item 1" in R.check_value(pts, ["MIRROR", [1]]) and R.check_value(pts, "MIRROR") and R.check_value(pts, [[1, "a"]])
    assert R.check_value(lns, ["a", "b"]) is None and R.check_value(lns, ["a", 2]) and R.check_value(lns, "a")
    jsonschema = pytest.importorskip("jsonschema")
    sch = json.loads((R.STYLE_ROOT / "gae" / "techniques.schema.json").read_text())
    assert {"points", "lines"} <= set(sch["$defs"]["technique"]["properties"]["params"]["items"]["properties"]["type"]["enum"])


def test_final_quality_frame_exact_parts(tiny, tiny_project, tmp_path):
    def probe(p):
        o = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(p)], capture_output=True, text=True).stdout
        return json.loads(o)["streams"][0]
    a = tiny_project.render_range(1.0, 1.5, tmp_path / "a.mp4", 320, 10, quality="final", threads=2)
    b = tiny_project.render_range(1.5, 2.0, tmp_path / "b.mp4", 320, 10, quality="final", threads=2)
    whole = tiny_project.render_range(1.0, 2.0, tmp_path / "w.mp4", 320, 10, quality="final")
    assert int(probe(a)["nb_read_frames"]) + int(probe(b)["nb_read_frames"]) == int(probe(whole)["nb_read_frames"]) == 10
    with pytest.raises(ValueError):
        tiny_project.render_range(1, 2, tmp_path / "x.mp4", 320, 10, quality="best")


def test_cli_progress_on_stdout(tiny, tmp_path):
    r = subprocess.run([__import__("sys").executable, "-m", "bti.engine", "render", str(tiny), "--t0", "1", "--t1", "2", "--width", "320", "--fps", "10",
                        "--quality", "final", "--threads", "2", "-o", str(tmp_path / "c.mp4")], capture_output=True, text=True,
                       cwd=str(R.REPO_ROOT))
    assert r.returncode == 0 and "progress 100%" in r.stdout and (tmp_path / "c.mp4").exists()
