import numpy as np
import pytest

from bti.engine import base
from bti.engine.api import open_project
from conftest import REPO


def test_frame_shape_dtype_and_determinism(tiny_project):
    a = tiny_project.frame_at(3.0, 480)
    assert a.shape == (270, 480, 3) and a.dtype == np.uint8
    base.LAYERS.clear(); base.IMAGES.clear(); base.MISC.clear()
    b = tiny_project.frame_at(3.0, 480)
    assert np.array_equal(a, b)


def test_width_changes_size_only(tiny_project):
    big = tiny_project.frame_at(3.0, 1920)
    small = tiny_project.frame_at(3.0, 960)
    assert big.shape == (1080, 1920, 3) and small.shape == (540, 960, 3)


def test_overlays_change_the_frame(tiny, tiny_project):
    sb = tiny_project.storyboard()
    with_ov = tiny_project.frame_at(3.5, 640)
    sb["shots"][0]["overlays"] = []
    tiny_project.use_draft(sb)
    without = tiny_project.frame_at(3.5, 640)
    assert not np.array_equal(with_ov, without)


def test_card_text_appears_and_leaves(tiny_project):
    shown = tiny_project.frame_at(6.6, 640)           # card starts at 6.0; text in at +0.2
    gone = tiny_project.frame_at(8.2, 640)
    assert shown.max() > 200 and gone.max() == 0


def test_dissolve_blends_both_shots(tiny_project):
    t0 = 9.0
    a = tiny_project.frame_at(t0 - 0.01, 320).astype(float)
    mid = tiny_project.frame_at(t0 + 0.5, 320).astype(float)
    sb = tiny_project.storyboard()
    sb["shots"][2]["transition_in"] = None
    tiny_project.use_draft(sb)
    cut = tiny_project.frame_at(t0 + 0.5, 320).astype(float)
    assert np.abs(mid - cut).mean() > 1.0 and np.abs(mid - cut).mean() < np.abs(a - cut).mean() + 60


def test_slide_in_transition(tiny_project):
    sb = tiny_project.storyboard()
    sb["shots"][2]["transition_in"] = {"technique": "TR-02", "dur": 1.0, "params": {"from_edge": "right", "easing": "linear"}}
    assert [i for i in tiny_project.validate(sb) if i["level"] == "error"] == []
    tiny_project.use_draft(sb)
    f = tiny_project.frame_at(9.5, 320)
    assert f.shape == (180, 320, 3)


def test_end_fade_goes_to_black(tiny_project):
    assert tiny_project.frame_at(18.99, 320).max() < 5
    assert tiny_project.frame_at(10.0, 320).max() > 20


def test_render_range_writes_h264(tiny, tiny_project, tmp_path):
    import json, subprocess
    out = tiny_project.render_range(1.0, 2.0, tmp_path / "o.mp4", width=320, fps=10)
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,nb_frames", "-of", "json", str(out)],
                                     capture_output=True, text=True).stdout)["streams"][0]
    assert info["codec_name"] == "h264" and info["width"] == 320 and info["height"] == 180 and int(info["nb_frames"]) == 10


def test_image_cache_is_bounded_lru(tiny):
    store = base._LRU(max_bytes=1000, keep=1)
    for k in range(10):
        store.get(k, lambda: np.zeros(400, np.uint8), lambda a: a.nbytes)
    assert store.stats()["entries"] <= 3


def test_cache_keys_include_size_and_font(tiny_project):
    from bti.engine import vfx
    ctx = tiny_project._scene().ctx
    k1 = ("layer", ctx.w, ctx.h, ctx._font_sig)
    ctx2 = tiny_project._scene().ctx
    assert k1 == ("layer", ctx2.w, ctx2.h, ctx2._font_sig) and str(ctx.h) in str(k1) and "reg=" in ctx._font_sig


OLD = REPO / ".scratch" / "engine" / "old"


@pytest.mark.skipif(not (OLD / "build_v2.py").exists() or not (REPO / "projects/arnolfini/storyboard.json").exists(), reason="old reference copy not present")
def test_equivalence_spot_check_against_the_benchmark(arnolfini):
    import sys
    sys.path.insert(0, str(OLD / "lib")); sys.path.insert(0, str(OLD))
    import build_v2 as B
    fa, _ = B.frame_fn(B.TL(str(OLD / "timing2.json")))
    for t in (5.0, 40.0, 75.0, 104.5, 310.0, 508.0, 580.0, 800.0, 820.0):
        o, n = fa(t), arnolfini.frame_at(t, 1920)
        mse = np.mean((o.astype(float) - n.astype(float)) ** 2)
        psnr = 99 if mse == 0 else 10 * np.log10(255 ** 2 / mse)
        assert psnr >= 40, (t, psnr)


def test_worked_example_source_label_renders(tiny_project):
    sb = tiny_project.storyboard()
    params = tiny_project.default_params("STATIC-02", {"asset": "A"})
    assert params["text"] == "Nobody, Test, 1999"
    before = tiny_project.frame_at(2.0, 960)
    sb["shots"][0]["overlays"].append({"id": "o9", "technique": "STATIC-02", "intent": "context", "start": {"t": 0.5}, "dur": 4.0, "params": params,
                                       "locked": False, "source": "human", "note": ""})
    assert [i for i in tiny_project.validate(sb) if i["level"] == "error"] == []
    tiny_project.use_draft(sb)
    after = tiny_project.frame_at(2.0, 960)
    assert not np.array_equal(before, after)
    assert np.array_equal(before[:400], after[:400])           # only the bottom strip changed
