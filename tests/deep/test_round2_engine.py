"""Round 2: validate versus draw. A draft that `validate` accepts without an error must be drawable (200); otherwise validate
must say why (error). Mock-free, real engine, temp copy of technique_lab."""
from __future__ import annotations

import pytest

import sweep
from conftest import state

# (technique, param, value): validate says "no error" today, the frame answers 500 "render failed"
HOLES = [("LAY-06", "strip_start", "x"), ("LAY-06", "strip_step", "x"), ("LAY-08", "tiles", "x"),
         ("STATIC-06", "from_point", "x"), ("STATIC-06", "to_point", "x"), ("STATIC-06", "control_point", "x"),
         ("DIA-01", "focus", "x"), ("DIA-01", "axes_origin", "x"), ("DIA-01", "axes_end", "x"), ("DIA-01", "ray_origin", "x"),
         ("DIA-02", "focus", "x"), ("DIA-02", "to_quad", []), ("DIA-04", "figure_focus", "x"), ("DIA-05", "focus", "x"),
         ("DIA-06", "room_center", "x"), ("DIA-06", "room_label_pos", "x"), ("DIA-06", "uv_label_pos", "x"),
         ("CMP-02", "stage_blur", "x"), ("CMP-02", "stage_grey", "x"), ("CMP-02", "stage_gain", "x"), ("CMP-03", "versions", "x")]


@pytest.fixture(scope="module")
def lab_ctx(client, projects_root):
    import shutil
    from conftest import _clone
    _clone(projects_root / "technique_lab", projects_root / "r2_eng_lab")
    st = state(client, "r2_eng_lab")
    reg = {t["id"]: t for t in client.get("/api/styles/gae").json()["techniques"]}
    yield "r2_eng_lab", sweep.strip(st["storyboard"]), st["storyboard"], reg
    shutil.rmtree(projects_root / "r2_eng_lab", ignore_errors=True)


@pytest.mark.parametrize("tid,param,value", HOLES, ids=[f"{t}-{p}" for t, p, _ in HOLES])
def test_R2B_012_validate_accepts_only_what_can_be_drawn(client, lab_ctx, tid, param, value):
    pid, sb, rs, reg = lab_ctx
    tech = reg[tid]
    kind, i, j = sweep.locate(sb, tech)
    ctx = sweep.context_for(sb, kind, i, j)
    params = client.post(f"/api/projects/{pid}/defaults", json={"technique": tid, "context": ctx}).json()["params"]
    params[param] = value
    draft = sweep.build_draft(sb, tech, params, kind, i, j)
    v = client.post(f"/api/projects/{pid}/validate", json={"storyboard": draft})
    assert v.status_code == 200
    errors = [x for x in v.json()["issues"] if x["level"] == "error"]
    t = sweep.sample_times(rs, kind, i, j)[1]
    f = client.post(f"/api/projects/{pid}/frame", json={"t": t, "width": 160, "storyboard": draft})
    if not errors:
        assert f.status_code == 200, f"validate: no error, frame: {f.status_code} {f.text[:120]}"
    else:
        assert f.status_code == 422, f"validate error but frame answered {f.status_code}"


@pytest.mark.timing
def test_TR03_preview_is_faster_than_it_plays_and_not_an_outlier(client, make_project):
    """R2B-015 / B-028 in one test, everything measured warm: one warm-up, then the best of three, for TR-03 and for each of
    five reference techniques.  TR-03 draws two shots at once, so about twice the cost of one shot is inherent; what matters is
    that its 3 s preview comes back in under 3 s, and in under 3.0 times the warm median of the references.

    It is a wall-clock test, so a loaded machine can fail an attempt: up to three attempts, it passes at the first one that meets
    both conditions and fails (listing every attempt with the load average) only when all three fail.
    Skip it with `-m "not timing"`."""
    import os
    from test_bugs_storyboard import _preview_seconds, _ref_preview_body
    lab = make_project("technique_lab", "t_r2_tr03")
    ref = ["LAY-01", "CAM-03", "HI-01", "X-TR-01", "X-CARD-02"]
    bodies = {t: _ref_preview_body(client, lab, t) for t in ref + ["TR-03"]}
    attempts = []
    for n in range(3):
        for b in bodies.values():                                   # warm-up
            _preview_seconds(client, lab, b)
        best = {t: min(_preview_seconds(client, lab, b) for _ in range(3)) for t, b in bodies.items()}
        base = sorted(best[t] for t in ref)[len(ref) // 2]
        load = os.getloadavg()[0]
        ok = best["TR-03"] < 3.0 and best["TR-03"] < 3.0 * base
        attempts.append("attempt %d: TR-03 %.2fs, warm median %.2fs, ratio %.2f, load %.1f, all %s" % (
            n + 1, best["TR-03"], base, best["TR-03"] / base, load, {k: round(v, 2) for k, v in best.items()}))
        print(attempts[-1])
        if ok:
            return
    pytest.fail("TR-03 failed all 3 attempts (limits: under 3.0 s and under 3.0x the median):\n" + "\n".join(attempts))


def test_R2B_016_validate_checks_basic_fields_of_the_document(client, arn):
    """canvas.fps 0, a non-boolean `locked` and a shot starting before 0 are all accepted without even a warning."""
    st = state(client, arn)
    base = sweep.strip(st["storyboard"])
    bad = {}
    d = __import__("copy").deepcopy(base); d["canvas"]["fps"] = 0; bad["canvas.fps = 0"] = d
    d = __import__("copy").deepcopy(base); d["shots"][1]["locked"] = "yes"; bad["locked = 'yes'"] = d
    d = __import__("copy").deepcopy(base); d["shots"][0]["start"] = {"t": -3.0}; bad["shots[0].start = -3 s"] = d
    missed = []
    for name, doc in bad.items():
        issues = client.post(f"/api/projects/{arn}/validate", json={"storyboard": doc}).json()["issues"]
        fresh = [i for i in issues if i["level"] in ("error", "warn") and not i["message"].startswith("project ")]
        if not fresh:
            missed.append(name)
    assert not missed, f"no error or warning for: {missed}"
