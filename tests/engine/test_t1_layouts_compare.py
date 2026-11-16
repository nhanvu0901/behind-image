"""T1 family: LAY-02..08, CMP-01..05, X-CMP-01/02, TR-03, X-TR-02."""
import copy
import json
import os
import subprocess
import sys

import cv2
import numpy as np
import pytest

from bti.engine import base
from bti.engine import registry as R
from bti.engine.api import open_project
from bti.engine.techniques import transitions_extra as TX
from conftest import REPO, make_image

IDS = ["LAY-02", "LAY-03", "LAY-04", "LAY-05", "LAY-06", "LAY-07", "LAY-08", "CMP-01", "CMP-02", "CMP-03", "CMP-04", "CMP-05",
       "X-CMP-01", "X-CMP-02", "TR-03", "X-TR-02"]


def cam(cx, cy, z0, z1=None):
    return [{"at": {"rel": 0.0}, "cx": cx, "cy": cy, "zoom": z0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": cx, "cy": cy, "zoom": z1 or z0, "ease": "linear"}]


@pytest.fixture()
def lab(tiny, tiny_project):
    """tiny project + a mask, a video and a second image; one 6 s shot per base technique."""
    media = tiny / "media"
    m = np.zeros((1200, 800), np.uint8)
    cv2.circle(m, (400, 500), 250, 255, -1)
    cv2.imwrite(str(media / "m.png"), m)
    p = str(media / "v.mp4")
    pr = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "160x90", "-r", "10", "-i", "-", "-c:v", "libx264",
                           "-pix_fmt", "yuv420p", p], stdin=subprocess.PIPE)
    for i in range(20):
        pr.stdin.write(np.full((90, 160, 3), 10 + 11 * i, np.uint8).tobytes())
    pr.stdin.close(); pr.wait()
    sb = tiny_project.storyboard()
    sb["assets"]["M"] = {"file": "media/m.png", "kind": "mask", "aligned_to": "A", "width": 800, "height": 1200}
    sb["assets"]["VID"] = {"file": "media/v.mp4", "kind": "video"}
    A, B = {"asset": "A"}, {"asset": "B"}
    c = cam(400, 600, 0.5)
    spec = [
        ("LAY-02", {f"tile_{i}": A for i in range(1, 5)}, {f"camera_{i}": cam(400, 600, 0.6, 0.64) for i in range(1, 5)}),
        ("LAY-03", {f"tile_{i}": (A if i % 2 else B) for i in range(1, 6)}, {"treatment_3": "grey", "treatment_4": "warm", "treatment_5": "contrast"}),
        ("LAY-04", {"image": A, "inset": B}, {"camera": c, "inset_camera": cam(450, 350, 0.4)}),
        ("LAY-05", {"image": A, "mask": {"asset": "M"}, "background_1": B, "background_2": A}, {"camera": c, "seconds_per_background": 2.0}),
        ("LAY-06", {"image": A}, {"camera_base": c, "strip_start": [300, 300], "strip_step": [50, 80], "strip_zoom": 0.4}),
        ("LAY-07", {"tile_1": A, "tile_2": B, "tile_3": A, "object": A}, {"object_camera": cam(400, 400, 1.0)}),
        ("LAY-08", {"image": A}, {"camera": cam(400, 400, 0.5)}),
        ("CMP-01", {"colour": A}, {"camera": c}),
        ("CMP-02", {"finished": A}, {"finished_camera": cam(400, 500, 1.0), "stage_camera": cam(400, 500, 0.6)}),
        ("CMP-03", {"image": A}, {"camera": c}),
        ("CMP-04", {"image": A}, {"camera": c}),
        ("CMP-05", {"state_a": A, "state_b": A}, {"camera": c}),
        ("X-CMP-01", {"anchor": A, "swap_1": B, "swap_2": A}, {"seconds_per_swap": 3.0, "swap_transition": "slide", "swap_captions": ["ONE", "TWO"]}),
        ("X-CMP-02", {"state_a": A, "state_b": B}, {"camera": c, "state_b_treatment": "grey"}),
    ]
    sb["shots"] = []
    for i, (tid, slots, params) in enumerate(spec):
        sb["shots"].append({"id": "s%d" % i, "start": {"t": 6.0 * i}, "technique": tid, "intent": "compare", "slots": slots, "params": params,
                            "transition_in": None, "overlays": [], "locked": False, "source": "import", "note": ""})
    sb["end"] = {"t": 6.0 * len(spec), "fade_s": 0.0}
    tiny_project.use_draft(sb)
    tiny_project._spec_ids = [s[0] for s in spec]
    tiny_project._sb = sb
    return tiny_project


def test_registry_entries_available_and_consistent(tiny_project):
    b = tiny_project.bundle
    assert R.check_registry(b) == []
    for tid in IDS:
        assert b.available(tid), tid
        spec = b.spec(tid)
        assert spec["engine"]["impl"].startswith("bti.engine.techniques.")
        mod, cls = spec["engine"]["impl"].rsplit(".", 1)
        assert R.RENDERERS[tid][0].__name__ == cls


def test_default_params_validate_with_and_without_context(tiny_project):
    for tid in IDS:
        spec = tiny_project.bundle.spec(tid)
        for ctx in ({}, {"asset": "A", "asset_right": "B", "region": "FACE"}):
            params = tiny_project.default_params(tid, ctx)
            errs = [i for i in R.validate_params(spec, params, tid) if i["level"] == "error"]
            assert errs == [], (tid, ctx, errs)


def test_every_base_technique_renders_and_moves(lab):
    for i, tid in enumerate(lab._spec_ids):
        t0 = 6.0 * i
        fa = lab.frame_at(t0 + 1.0, 480)
        fb = lab.frame_at(t0 + 3.5, 480)
        assert fa.shape == (270, 480, 3) and fa.dtype == np.uint8, tid
        assert fa.max() > 40, tid
        assert not np.array_equal(fa, fb), tid          # something animates


def test_deterministic_and_pure_function_of_time(lab):
    t = 6.0 * 5 + 2.2
    a = lab.frame_at(t, 480)
    base.LAYERS.clear(); base.IMAGES.clear(); base.MISC.clear()
    lab.frame_at(6.0 * 3 + 1.0, 480)                     # render another shot in between (out of order)
    assert np.array_equal(a, lab.frame_at(t, 480))


def test_validation_has_no_errors(lab):
    assert [i for i in lab.validate(lab._sb) if i["level"] == "error"] == []


def test_lay02_connectors_draw_progressively(lab):
    t0 = 0.0
    before = lab.frame_at(t0 + 1.7, 960).astype(float)
    mid = lab.frame_at(t0 + 2.4, 960).astype(float)
    late = lab.frame_at(t0 + 3.5, 960).astype(float)
    assert np.abs(mid - late).sum() > 0 and np.abs(before - late).sum() > np.abs(mid - late).sum() * 0.5
    sb = copy.deepcopy(lab._sb); sb["shots"][0]["params"]["connectors"] = False
    lab.use_draft(sb)
    nolines = lab.frame_at(t0 + 3.5, 960).astype(float)
    assert np.abs(nolines - late).sum() > 0


def test_lay03_columns_param_and_fit(lab):
    sb = copy.deepcopy(lab._sb)
    sb["shots"][1]["params"]["columns"] = 3
    sb["shots"][1]["params"]["fit"] = "contain"
    lab.use_draft(sb)
    assert lab.frame_at(6.0 + 2.5, 480).max() > 40


def test_lay04_accepts_video_inset(lab):
    sb = copy.deepcopy(lab._sb)
    sb["shots"][2]["slots"]["inset"] = {"asset": "VID"}
    sb["shots"][2]["params"]["inset_corner"] = "bottom_left"
    lab.use_draft(sb)
    f = lab.frame_at(12.0 + 3.0, 1920)
    x, y = 70 + 10, 1080 - 60 - 315 + 10
    assert f[y:y + 20, x:x + 20].std() < 6 and f[y:y + 20, x:x + 20].mean() > 5          # flat video colour in the corner window


def test_lay05_subject_stays_while_background_changes(lab):
    t0 = 6.0 * 3
    a = lab.frame_at(t0 + 0.5, 960).astype(float)
    b = lab.frame_at(t0 + 3.5, 960).astype(float)
    c = (slice(270 - 20, 270 + 20), slice(480 - 20, 480 + 20))          # centre = inside the mask
    assert np.abs(a[c] - b[c]).mean() < 3
    assert np.abs(a[:20, :20] - b[:20, :20]).mean() > 3


def test_lay08_mirror_symmetry(lab):
    f = lab.frame_at(6.0 * 6 + 1.0, 1920).astype(int)
    assert np.abs(f[:, :480] - f[:, 480:960][:, ::-1]).max() <= 1
    assert np.abs(f[:540, :480] - f[540:, :480][::-1]).max() <= 1


def test_cmp04_blocks_are_flat(lab):
    f = lab.frame_at(6.0 * 10 + 0.5, 1920)                           # start: 8 columns -> 112 px blocks
    blk = f[90:90 + 112, 980:980 + 112]
    assert blk.reshape(-1, 3).std(0).max() < 1.5


def test_xcmp02_starts_and_ends_on_state_a(lab):
    t0 = 6.0 * 13
    a = lab.frame_at(t0 + 0.1, 480).astype(float)
    mid = lab.frame_at(t0 + 3.0, 480).astype(float)
    end = lab.frame_at(t0 + 5.95, 480).astype(float)
    assert np.abs(a - end).mean() < 1.0                              # back to the colour image
    assert np.abs(a - mid).mean() > 5                                # split state differs
    assert np.abs(mid[:, :200] - a[:, :200]).mean() < 1.0            # left half unchanged (b enters from the right)


def test_xcmp01_swaps_only_one_side(lab):
    t0 = 6.0 * 12
    a = lab.frame_at(t0 + 1.0, 960).astype(float)
    b = lab.frame_at(t0 + 4.5, 960).astype(float)
    assert np.abs(a[:, :400] - b[:, :400]).mean() < 6                # left (anchor) side stays (captions / push aside)
    assert np.abs(a[:, 520:] - b[:, 520:]).mean() > 8                # right side changed


def test_tr03_endpoints_and_motion(tiny_project):
    ctx = tiny_project._scene().ctx
    tr = TX.PanelOpening("TR-03", {"dur": 3.0, "params": {}}, ctx)
    out = np.random.RandomState(1).rand(1080, 1920, 3).astype(np.float32) * 255
    inn = np.random.RandomState(2).rand(1080, 1920, 3).astype(np.float32) * 255
    assert np.array_equal(tr.blend(out, inn, 0.0), out) and np.array_equal(tr.blend(out, inn, 1.0), inn)
    mid = tr.blend(out, inn, 0.5)
    assert mid.shape == out.shape and np.isfinite(mid).all()
    centre = mid[540, 930:990]                                        # the opening in the middle shows the (dimmed) inner image
    assert 0.3 < centre.mean() / inn[540, 930:990].mean() < 1.01
    # wings narrow: at 0.5 the left wing no longer reaches the middle of the box
    assert not np.array_equal(mid[200:900, 700:760], out[200:900, 700:760])


def test_xtr02_phases_and_endpoints(tiny_project):
    ctx = tiny_project._scene().ctx
    tr = TX.StripSplit("X-TR-02", {"dur": 3.6, "params": {}}, ctx)
    out = np.full((1080, 1920, 3), 30, np.float32)
    inn = np.full((1080, 1920, 3), 30, np.float32)
    inn[36:776, 970:1870] = 200                                       # the "second image" in the right panel
    assert np.array_equal(tr.blend(out, inn, 0.0), out) and np.array_equal(tr.blend(out, inn, 1.0), inn)
    early = tr.blend(out, inn, 0.1)                                   # strip entering from the bottom: bottom rows bright, top still bg
    assert early[1070, 960].mean() > 150 and early[10, 960].mean() < 40
    full = tr.blend(out, inn, (0.9 + 0.7 + 0.3) / 3.6)                # full frame phase
    assert full.mean() > 190
    late = tr.blend(out, inn, 0.97)
    assert np.abs(late - inn).mean() < 20
    for edge in ("top", "left", "right"):
        tr2 = TX.StripSplit("X-TR-02", {"dur": 3.6, "params": {"slide_from": edge}}, ctx)
        assert tr2.blend(out, inn, 0.08).shape == out.shape


# ---------------------------------------------------------------------------------------------------- equivalence with the reel
def _reel_available():
    return (REPO / ".scratch" / "r1" / "build_reel.py").exists() and (REPO / "projects" / "lab_layouts" / "storyboard.json").exists()


@pytest.mark.skipif(not _reel_available(), reason="needs .scratch/r1 and projects/lab_layouts")
def test_psnr_against_the_reel_segments():
    """PSNR >= 40 dB against the benchmark's own frame for the 12 reel-derived base techniques (lab_layouts content)."""
    code = r"""
import sys, json, os
sys.dont_write_bytecode = True
REPO = %r
sys.path.insert(0, REPO); sys.path.insert(0, REPO + '/.scratch/r1'); sys.path.insert(0, REPO + '/.scratch/r1/lib')
import numpy as np
from bti.engine.api import open_project
os.chdir(REPO + '/.scratch/r1')
import build_reel as BR
os.chdir(REPO)
BR.S()
sc = open_project(REPO + '/projects/lab_layouts')._scene()
idx = json.load(open(REPO + '/projects/lab_layouts/index.json'))
out = {}
for tid, (T0, d) in idx.items():
    if tid.startswith('X') or tid == 'TR-03':
        continue
    e = next(x for x in BR.SEG if x['id'] == tid)
    worst = 99.0
    for frac in (.3, .75):
        t = d * frac
        ref = BR.to_u8(np.asarray(e['fn'](t, e['dur']), np.float32)).astype(np.float64)
        mine = BR.to_u8(sc.frame_float(T0 + t)).astype(np.float64)
        m = ((ref - mine) ** 2).mean()
        worst = min(worst, 99.0 if m == 0 else 10 * np.log10(255 ** 2 / m))
    out[tid] = worst
print('RESULT' + json.dumps(out))
""" % str(REPO)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO), timeout=600)
    line = [l for l in r.stdout.splitlines() if l.startswith("RESULT")]
    assert line, r.stderr[-2000:]
    res = json.loads(line[0][6:])
    assert len(res) == 12
    for tid, v in res.items():
        assert v >= 40.0, (tid, v)


@pytest.mark.skipif(not _reel_available(), reason="needs .scratch/r1")
def test_tr03_psnr_against_the_reel_formula():
    code = r"""
import sys, os
sys.dont_write_bytecode = True
REPO = %r
sys.path.insert(0, REPO); sys.path.insert(0, REPO + '/.scratch/r1'); sys.path.insert(0, REPO + '/.scratch/r1/lib')
import numpy as np
from bti.engine.api import open_project
from bti.engine.techniques.transitions_extra import PanelOpening
from bti.engine.vfx import backdrop
os.chdir(REPO + '/.scratch/r1')
import build_reel as BR
os.chdir(REPO)
s = BR.S()
ctx = open_project(REPO + '/projects/lab_layouts')._scene().ctx
tr = PanelOpening('TR-03', {'dur': 3.2, 'params': {}}, ctx)
f_out = np.asarray(BR.tr03(1.0, 6.0), np.float32)
f_in = backdrop(1920, 1080).copy(); f_in[90:990, 360:1560] = BR.view(s['V'], 2085, 1624, 0.30, 1200, 900)
w = 99.0
for p in (.2, .5, .8):
    ref = BR.to_u8(np.asarray(BR.tr03(1.0 + 3.2 * p, 6.0), np.float32)).astype(float); mine = BR.to_u8(tr.blend(f_out, f_in, p)).astype(float)
    w = min(w, 10 * np.log10(255 ** 2 / ((ref - mine) ** 2).mean()))
print('RESULT%%.2f' %% w)
""" % str(REPO)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO), timeout=600)
    line = [l for l in r.stdout.splitlines() if l.startswith("RESULT")]
    assert line, r.stderr[-2000:]
    assert float(line[0][6:]) >= 40.0
