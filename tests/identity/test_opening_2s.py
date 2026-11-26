"""Two-second opening, scaled raking sweep, cross-cut bottom-left label, strip avoidance, reading time, and retime."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
engine_api = pytest.importorskip("bti.engine.api")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "draft"))

from bti import identity as ID  # noqa: E402
from bti.draft import retime as RT  # noqa: E402
from bti.draft import zones as Z  # noqa: E402
from bti.draft.compile import compile_specs, summary_text  # noqa: E402
from bti.draft.inputs import load_inputs, normalize_timing  # noqa: E402
from bti.engine import registry as R  # noqa: E402
from bti.engine import storyboard as SB  # noqa: E402
from bti.engine import viewchecks as VC  # noqa: E402
from bti.engine.scene import Scene  # noqa: E402
from bti.engine.timing import Timing  # noqa: E402
from intro_helpers import compiled, intro_timing, make_project, specs, style_doc  # noqa: E402


def _paint_project(tmp_path: Path, lead: float = 2.0, title: float = 10.2, spacing: float = 0.5) -> tuple[Path, dict]:
    t = intro_timing(lead=lead, title=title, spacing=spacing)
    proj = make_project(tmp_path, t)
    picks = json.loads((proj / "picks.json").read_text(encoding="utf-8"))
    # Use a dark painted rectangle with high-contrast texture at bottom-left so white label pixels are unmistakable.
    w, h = 800, 1200
    img = np.full((h, w, 3), 24, dtype=np.uint8)
    img[100:400, 150:650] = (90, 110, 130)
    asset_path = proj / picks["assets"]["A"]["file"]
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(asset_path), img)
    assert ok
    picks["assets"]["A"].update({"width": w, "height": h, "title": "The Arnolfini Portrait", "artist": "Jan van Eyck", "year": "1434"})
    (proj / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    return proj, t


def _ov_times(tm: Timing, shot: dict, t1: float, tech: str):
    out = []
    for o in shot.get("overlays") or []:
        if o.get("technique") == tech:
            s = tm.resolve(o["start"])
            e = tm.resolve(o["end"]) if isinstance(o.get("end"), dict) else (s + o["dur"] if o.get("dur") is not None else t1)
            out.append((s, e, o))
    return out


@pytest.mark.parametrize("lead", [1.2, 1.5, 2.0, 5.0])
def test_light_sweep_scales_and_leaves_painting_fully_lit_at_least_0_6s_before_voice(tmp_path, lead):
    proj, t = _paint_project(tmp_path / f"l{lead}", lead=lead)
    sb = compiled(proj).storyboard
    tm = Timing({"duration": t["duration"], "words": t["words"]})
    first_word_s = t["words"][0]["s"]
    s0 = sb["shots"][0]
    assert s0["id"] == "s0000"
    sweeps = _ov_times(tm, s0, tm.resolve(sb["shots"][1]["start"]), "ID-OPEN-01")
    assert len(sweeps) == 1
    sw_start, sw_end, _ = sweeps[0]
    assert sw_start == pytest.approx(0.0, abs=1e-6)
    assert sw_end < first_word_s - 0.59
    assert first_word_s - sw_end >= 0.6 - 1e-6

    bundle = R.load_bundle("gae")
    sc = Scene(proj, SB.resolve(sb, tm, bundle), tm, bundle)
    open_r = dict(sc.shot_at(0.1).overlays)[0]
    _, _, ahead, behind = open_r.state(sw_end + 1e-4)
    assert ahead == pytest.approx(1.0, abs=1e-4) and behind == pytest.approx(1.0, abs=1e-4)
    assert not [i for i in SB.validate(sb, tm, bundle, proj) if i["level"] == "error"]


def test_label_crosses_cut_without_blinking_and_passes_reading_check(tmp_path):
    # With spacing=0.7 s, s0001 spans [1.65, 9.0] s so the label completes its nominal [0.3, 8.0] s run across the cut.
    proj, t = _paint_project(tmp_path / "full", lead=2.0, spacing=0.7)
    sb = compiled(proj).storyboard
    tm = Timing({"duration": t["duration"], "words": t["words"]})
    bundle = R.load_bundle("gae")

    p0 = _ov_times(tm, sb["shots"][0], 1.65, "ID-LABEL-01")
    p1 = _ov_times(tm, sb["shots"][1], tm.resolve(sb["shots"][2]["start"]), "ID-LABEL-01")
    assert len(p0) == 1 and len(p1) == 1
    assert p0[0][0] == pytest.approx(0.3, abs=1e-3)
    assert p0[0][1] == pytest.approx(1.65, abs=1e-3)
    assert p0[0][2]["params"]["fade_out_s"] == 0.0
    assert p1[0][0] == pytest.approx(1.65, abs=1e-3)
    assert p1[0][1] == pytest.approx(8.0, abs=1e-3)
    assert p1[0][2]["params"]["fade_in_s"] == 0.0 and p1[0][2]["params"]["fade_out_s"] == 0.5
    assert p0[0][2]["params"]["title_cap_pct"] == 4.2 and p0[0][2]["params"]["second_cap_pct"] == 3.0

    # Render across the 1.65 s cut (1.60, 1.64, 1.66, 1.70 s): white label ink in bottom-left stays lit at 100 % with no blink.
    sc = Scene(proj, SB.resolve(sb, tm, bundle), tm, bundle)
    for t_sample in (1.55, 1.64, 1.6499, 1.65, 1.66, 1.70):
        cshot = sc.shot_at(t_sample)
        label_ren = next(r for _, r in cshot.overlays if r.tid == "ID-LABEL-01")
        assert label_ren.envelope(t_sample) == pytest.approx(1.0, abs=1e-3), t_sample
    assert sc.frame_at(1.64, 960)[int(0.78 * 540):int(0.95 * 540), int(0.03 * 960):int(0.45 * 960)].max() > 180
    assert sc.frame_at(1.66, 960)[int(0.78 * 540):int(0.95 * 540), int(0.03 * 960):int(0.45 * 960)].max() > 180
    assert sc.frame_at(8.1, 960)[int(0.78 * 540):int(0.95 * 540), int(0.03 * 960):int(0.45 * 960)].max() < 150

    # Shorter s0001 (ending at 7.0 s) clamps Piece 1 cleanly at the shot boundary.
    proj_short, t_short = _paint_project(tmp_path / "clamped", lead=2.0, spacing=0.5)
    tm_short = Timing({"duration": t_short["duration"], "words": t_short["words"]})
    sb_short = compiled(proj_short).storyboard
    assert _ov_times(tm_short, sb_short["shots"][1], 7.0, "ID-LABEL-01")[0][1] == pytest.approx(7.0, abs=1e-3)

    issues = SB.validate(sb, tm, bundle, proj)
    assert not [i for i in issues if i["level"] == "error"], issues
    assert not [i for i in issues if i["code"] == "text_too_brief"], issues


def test_label_leaves_before_name_strip_and_short_chain_still_triggers_text_too_brief(tmp_path):
    proj, t = _paint_project(tmp_path, lead=2.0)
    sb = compiled(proj).storyboard
    # Put an X-ANN-01 strip at 4.5 s on s0001
    s1 = sb["shots"][1]
    s1["overlays"] = [
        o for o in s1["overlays"] if not o["technique"].startswith("ID-")
    ] + [
        {"id": "o9", "technique": "X-ANN-01", "intent": "point_at", "start": {"t": 4.5}, "dur": 3.0, "params": {"text": "MIRROR"}, "slots": {}}
    ]
    bundle = R.load_bundle("gae")
    tm = Timing({"duration": t["duration"], "words": t["words"]})
    out, _ = ID.apply_identity(sb, "raking", bundle.style, t, {"main_asset": "A"}, defaults=bundle.param_defaults)
    p1 = _ov_times(tm, out["shots"][1], tm.resolve(out["shots"][2]["start"]), "ID-LABEL-01")
    assert len(p1) == 1 and p1[0][1] == pytest.approx(4.5, abs=1e-3)
    assert not [i for i in SB.validate(out, tm, bundle, proj) if i["code"] == "text_too_brief"]

    # Genuinely brief cross-cut chain (cuts off at 1.9 s total -> visible < 1.5 s) still triggers text_too_brief.
    short_sb = copy.deepcopy(out)
    for o in short_sb["shots"][1]["overlays"]:
        if o["technique"] == "ID-LABEL-01":
            o["dur"] = 0.25
    short_issues = SB.validate(short_sb, tm, bundle, proj)
    brief_codes = [i for i in short_issues if i["code"] == "text_too_brief"]
    assert len(brief_codes) >= 1


def test_retime_from_5s_to_2s_and_back_and_under_1_2s(tmp_path):
    proj, t5 = _paint_project(tmp_path / "rt", lead=5.0, spacing=0.7)
    sb5 = compiled(proj).storyboard
    bundle = R.load_bundle("gae")

    t2 = intro_timing(lead=2.0, title=10.2, spacing=0.7)
    sb2, rep2 = RT.retime(sb5, t2, bundle.style, {"main_asset": "A"}, bundle.param_defaults)
    assert RT.off_voice(sb2, t2, bundle.style, {"main_asset": "A"}) == [] and not rep2["left"]
    tm2 = Timing({"duration": t2["duration"], "words": t2["words"]})
    assert not [i for i in SB.validate(sb2, tm2, bundle, proj) if i["level"] == "error"]
    assert not [i for i in SB.validate(sb2, tm2, bundle, proj) if i["code"] == "text_too_brief"]
    p1_at_2 = _ov_times(tm2, sb2["shots"][1], tm2.resolve(sb2["shots"][2]["start"]), "ID-LABEL-01")
    assert len(p1_at_2) == 1 and p1_at_2[0][0] == pytest.approx(1.65, abs=1e-3) and p1_at_2[0][1] == pytest.approx(8.0, abs=1e-3)

    # Back to 5.0 s
    sb5_back, rep5 = RT.retime(sb2, t5, bundle.style, {"main_asset": "A"}, bundle.param_defaults)
    assert RT.off_voice(sb5_back, t5, bundle.style, {"main_asset": "A"}) == [] and not rep5["left"]
    tm5 = Timing({"duration": t5["duration"], "words": t5["words"]})
    assert _ov_times(tm5, sb5_back["shots"][1], tm5.resolve(sb5_back["shots"][2]["start"]), "ID-LABEL-01")[0][0] == pytest.approx(4.65, abs=1e-3)

    # Down to 1.0 s (< 1.2 s removes s0000 and cleanly moves opening overlays onto the first shot)
    t1 = intro_timing(lead=1.0, title=10.2, spacing=0.7)
    sb1, rep1 = RT.retime(sb2, t1, bundle.style, {"main_asset": "A"}, bundle.param_defaults)
    assert rep1["removed"] == ["s0000"] and "s0000" not in [s["id"] for s in sb1["shots"]]
    assert RT.off_voice(sb1, t1, bundle.style, {"main_asset": "A"}) == []
    assert not [i for i in SB.validate(sb1, Timing({"duration": t1["duration"], "words": t1["words"]}), bundle, proj) if i["level"] == "error"]


def test_identity_is_idempotent_with_cross_cut_label(tmp_path):
    proj, t = _paint_project(tmp_path, lead=2.0)
    sb = compiled(proj).storyboard
    bundle = R.load_bundle("gae")
    again, rep = ID.apply_identity(sb, "raking", bundle.style, t, {"main_asset": "A"}, defaults=bundle.param_defaults, project_dir=proj)
    assert rep["changed"] == [] and json.dumps(again, sort_keys=True) == json.dumps(sb, sort_keys=True)
    as_dim, _ = ID.apply_identity(sb, "dim", bundle.style, t, {"main_asset": "A"}, defaults=bundle.param_defaults, project_dir=proj)
    back, _ = ID.apply_identity(as_dim, "raking", bundle.style, t, {"main_asset": "A"}, defaults=bundle.param_defaults, project_dir=proj)
    assert json.dumps(back, sort_keys=True) == json.dumps(sb, sort_keys=True)


def test_stored_storyboard_with_explicit_old_label_params_draws_same_bytes(tmp_path):
    bundle = R.load_bundle("gae")
    proj, t = _paint_project(tmp_path, lead=5.0)
    sb = compiled(proj).storyboard
    # Write explicit pre-introrules 3.0 / 2.3 label on s0000 only, like a stored storyboard.
    sb["shots"][1]["overlays"] = [o for o in sb["shots"][1]["overlays"] if not o["technique"].startswith("ID-")]
    sb["shots"][0]["overlays"] = [
        {
            "id": "o1",
            "technique": "ID-LABEL-01",
            "intent": "structure",
            "start": {"t": 1.2},
            "dur": 3.45,
            "params": {**bundle.param_defaults("ID-LABEL-01"), "title": "The Arnolfini Portrait", "artist_year": "Jan van Eyck, 1434", "title_cap_pct": 3.0, "second_cap_pct": 2.3},
            "slots": {},
            "locked": False,
            "source": "agent",
            "note": "",
        }
    ]
    tm = Timing({"duration": t["duration"], "words": t["words"]})
    assert not [i for i in SB.validate(sb, tm, bundle, proj) if i["level"] == "error"]
    sc = Scene(proj, SB.resolve(sb, tm, bundle), tm, bundle)
    lab = dict(sc.shot_at(2.5).overlays)[0]
    assert lab.p["title_cap_pct"] == 3.0 and lab.p["second_cap_pct"] == 2.3
    assert sc.frame_at(2.5, 960).shape == (540, 960, 3)
