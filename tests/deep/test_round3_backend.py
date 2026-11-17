"""Round 3 backend tests. Each asserts the CORRECT behaviour and FAILS while its bug exists (see docs/qa/ROUND3_backend.md).
Mock model only, temp data roots, no real agy (BTI_AGY_BIN points at a fake or at nothing), no network."""
from __future__ import annotations

import copy
import itertools
import json
import os
import shutil
import threading
import time

import pytest

from conftest import state, strip, wait_job

ART = "bosch-the-garden-of-earthly-delights"
_n = itertools.count()


def P(pid):
    return f"/api/projects/{pid}"


@pytest.fixture()
def flow_pid(client, projects_root):
    pid = f"r3-flow-{next(_n)}"
    r = client.post("/api/library/projects", json={"artwork_key": ART, "slug": pid})
    assert r.status_code == 200, r.text
    yield pid
    shutil.rmtree(projects_root / pid, ignore_errors=True)


def _script_to_approved(client, pid):
    r = client.post(P(pid) + "/outline/generate", json={"model": "mock"})
    assert wait_job(client, r.json()["job_id"])["state"] == "done"
    o = client.get(P(pid) + "/outline").json()
    assert client.post(P(pid) + "/outline/approve", json={"rev": o["rev"]}).status_code == 200
    r = client.post(P(pid) + "/narration/generate", json={"model": "mock"})
    assert wait_job(client, r.json()["job_id"])["state"] == "done"
    n = client.get(P(pid) + "/narration").json()
    assert client.post(P(pid) + "/narration/approve", json={"rev": n["rev"]}).status_code == 200


# ------------------------------------------------------------------ R3B-001 approve holds the global engine lock
def test_R3B_001_approve_does_not_block_other_projects(client, arn, lab):
    st = state(client, arn)
    state(client, lab)                                   # warm: opened once
    out = {}

    def approve():
        out["r"] = client.post(P(arn) + "/approve", json={"rev": st["rev"]})
    th = threading.Thread(target=approve)
    th.start()
    time.sleep(0.7)
    t = time.time()
    r = client.get(P(lab))
    waited = time.time() - t
    th.join(120)
    assert r.status_code == 200 and "r" in out
    assert waited < 2.0, f"GET of another project waited {waited:.1f} s behind the approval's draw_check"


# ------------------------------------------------------------------ R3B-002 depth scan is quadratic
def test_R3B_002_depth_scan_is_linear_on_an_unterminated_escaped_string():
    from bti.editor.common import DepthLimitMiddleware
    body = b'"' + b'\\"' * 10000                        # 20 KB; 0.9 s today, 4x per doubling
    t = time.time()
    DepthLimitMiddleware(None).too_deep(body)
    assert time.time() - t < 0.2, "the scan is quadratic: a 2 MB body would freeze the event loop for hours"


# ------------------------------------------------------------------ R3B-003 wrong-shape fields on disk
def _write_sb(projects_root, pid, mut):
    f = projects_root / pid / "storyboard.json"
    sb = json.loads(f.read_text())
    mut(sb)
    f.write_text(json.dumps(sb))


@pytest.mark.parametrize("label,mut", [
    ("shots-string", lambda s: s.update(shots="no")),
    ("shots-list-of-strings", lambda s: s.update(shots=["a"])),
    ("overlays-string", lambda s: s["shots"][0].update(overlays="x")),
])
def test_R3B_003_storyboard_file_of_the_wrong_shape_is_not_a_500(client, projects_root, lab, label, mut):
    _write_sb(projects_root, lab, mut)
    for url in (P(lab), P(lab) + "/thumb/s0001", "/api/projects"):
        r = client.get(url)
        assert r.status_code < 500, f"{label}: GET {url} -> {r.status_code} {r.text[:100]}"


def test_R3B_004_project_json_sources_not_a_list_is_not_a_500(client, projects_root, flow_pid):
    f = projects_root / flow_pid / "project.json"
    pj = json.loads(f.read_text())
    pj["sources"] = 5
    f.write_text(json.dumps(pj))
    r = client.get(P(flow_pid) + "/pipeline")
    assert r.status_code < 500, r.text[:120]


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a mode 000 file")
@pytest.mark.parametrize("rel,url", [
    ("source/*.txt", "/outline"), ("source/*.txt", "/brief"), ("source/*.txt", "/narration"),
    ("script/last_paste.txt", "/narration"),
])
def test_R3B_005_unreadable_file_is_409_not_500(client, projects_root, flow_pid, rel, url):
    d = projects_root / flow_pid
    if rel == "script/last_paste.txt":
        (d / "script").mkdir(exist_ok=True)
        (d / rel).write_text("pasted")
        targets = [d / rel]
    else:
        targets = sorted((d / "source").glob("*.txt"))
    assert targets
    try:
        for t in targets:
            os.chmod(t, 0)
        r = client.get(P(flow_pid) + url)
        assert r.status_code < 500, f"{rel} unreadable: GET {url} -> {r.status_code}"
    finally:
        for t in targets:
            os.chmod(t, 0o644)


def test_R3B_006_a_directory_in_place_of_a_script_file_is_not_a_500_on_save(client, projects_root, flow_pid):
    _script_to_approved(client, flow_pid)
    f = projects_root / flow_pid / "script" / "narration.json"
    n = client.get(P(flow_pid) + "/narration").json()
    doc = n["narration"]
    f.unlink()
    f.mkdir()
    g = client.get(P(flow_pid) + "/narration")
    r = client.put(P(flow_pid) + "/narration", json={"narration": doc, "base_rev": n["rev"]})
    assert g.status_code == 409 or r.status_code < 500, f"GET {g.status_code}, PUT {r.status_code} {r.text[:100]}"


# ------------------------------------------------------------------ R3B-007 narration order against the outline
def test_R3B_007_reordered_outline_chapters_do_not_leave_a_silently_approved_narration_in_the_old_order(client, flow_pid):
    _script_to_approved(client, flow_pid)
    o = client.get(P(flow_pid) + "/outline").json()
    od = copy.deepcopy(o["outline"])
    od["chapters"][1], od["chapters"][2] = od["chapters"][2], od["chapters"][1]
    assert client.put(P(flow_pid) + "/outline", json={"outline": od, "base_rev": o["rev"]}).status_code == 200
    o = client.get(P(flow_pid) + "/outline").json()
    assert client.post(P(flow_pid) + "/outline/approve", json={"rev": o["rev"]}).status_code == 200
    n = client.get(P(flow_pid) + "/narration").json()
    r = client.post(P(flow_pid) + "/narration/approve", json={"rev": n["rev"]})
    n = client.get(P(flow_pid) + "/narration").json()
    same = [c["id"] for c in n["narration"]["chapters"]] == [c["id"] for c in o["outline"]["chapters"]]
    says = any("order" in i["code"] for i in n["issues"])
    assert r.status_code != 200 or same or says, "narration approved with chapters in another order than the approved outline, no issue"


# ------------------------------------------------------------------ R3B-008 registry bounds that cannot be drawn
@pytest.mark.parametrize("tid,param,which", [
    ("LAY-01", "panel_w_px", "max"), ("LAY-01", "left_x_px", "max"), ("LAY-02", "tile_w_px", "max"),
    ("LAY-03", "columns", "max"), ("CMP-01", "panel_w_px", "max"), ("CMP-03", "pitch_px", "max"),
    ("CMP-02", "stage_size_px", "max"), ("X-ANN-01", "strip_y_top_pct", "max"), ("X-ANN-01", "strip_y_bottom_pct", "min"),
])
def test_R3B_008_a_value_at_the_registry_bound_is_refused_by_validate_or_drawn(client, tid, param, which):
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import sweep
    reg = client.get("/api/styles/gae").json()["techniques"]
    tech = next(t for t in reg if t["id"] == tid)
    spec = next(p for p in tech["params"] if p["name"] == param)
    st = state(client, "technique_lab")
    sb, rs = strip(st["storyboard"]), st["storyboard"]
    kind, i, j = sweep.locate(sb, tech)
    params = client.post(P("technique_lab") + "/defaults", json={"technique": tid, "context": sweep.context_for(sb, kind, i, j)}).json()["params"]
    params[param] = spec[which]
    draft = sweep.build_draft(sb, tech, params, kind, i, j)
    issues = client.post(P("technique_lab") + "/validate", json={"storyboard": draft}).json()["issues"]
    if any(x["level"] == "error" for x in issues):
        return
    t = sweep.sample_times(rs, kind, i, j)[1]
    r = client.post(P("technique_lab") + "/frame", json={"t": t, "width": 480, "storyboard": draft})
    assert r.status_code == 200, f"{tid}.{param}={spec[which]}: validate accepts, frame {r.status_code} {r.text[:120]}"


# ------------------------------------------------------------------ R3B-009 truncated JPEG passes everything
def test_R3B_009_a_truncated_image_is_not_silently_drawn(client, projects_root, lab):
    f = projects_root / lab / "media" / "arn__arnolfini_commons.jpg"
    data = f.read_bytes()
    f.write_bytes(data[: len(data) // 3])
    st = state(client, lab)
    sh = next(s for s in st["storyboard"]["shots"] if s["id"] == "s0001")
    t = (sh["_t0"] + sh["_t1"]) / 2
    r = client.get(P(lab) + f"/frame?t={t}&width=320")
    errs = [i for i in st["issues"] if i["level"] == "error"]
    assert r.status_code == 422 or errs, "a picture cut off at a third draws a 200 frame and validates without a word"


# ------------------------------------------------------------------ R3B-010 messages carry raw exceptions and server paths
def test_R3B_010_render_failed_message_does_not_leak_the_server_path_or_a_wrong_exception_name(client, projects_root, lab):
    f = projects_root / lab / "media" / "arn__arnolfini_commons.jpg"
    f.write_bytes(b"")                                   # exists, zero bytes
    st = state(client, lab)
    sh = next(s for s in st["storyboard"]["shots"] if s["id"] == "s0001")
    r = client.get(P(lab) + f"/frame?t={(sh['_t0'] + sh['_t1']) / 2}&width=320")
    assert r.status_code == 422
    d = r.json()["detail"]
    assert str(projects_root) not in d and "FileNotFoundError" not in d and "AssertionError" not in d, d


# ------------------------------------------------------------------ R3B-011 upload racing a delete
def test_R3B_011_upload_whose_folder_vanishes_while_it_is_checked_answers_404(client, projects_root, flow_pid, monkeypatch):
    import io
    from PIL import Image
    import bti.media.imageinfo as ii
    real = ii.readable_problem

    def racing(path):
        d = projects_root / flow_pid
        d.rename(projects_root / f".deleting-{flow_pid}-x")        # what DELETE does, in the middle of the upload
        try:
            return real(path)
        finally:
            shutil.rmtree(projects_root / f".deleting-{flow_pid}-x", ignore_errors=True)
    monkeypatch.setattr(ii, "readable_problem", racing)
    b = io.BytesIO()
    Image.new("RGB", (200, 150), (1, 2, 3)).save(b, "PNG")
    r = client.post(P(flow_pid) + "/assets/upload", files={"file": ("x.png", b.getvalue(), "image/png")},
                    data={"title": "t", "licence": "CC0", "source_url": "https://e.org/x", "author": "me"})
    assert r.status_code == 404, f"{r.status_code} {r.text[:120]}"


# ------------------------------------------------------------------ R3B-012, R3B-013 model list
def _fake_agy(tmp_path, monkeypatch, body):
    p = tmp_path / "agy"
    p.write_text("#!/bin/sh\n" + body + "\n")
    p.chmod(0o755)
    monkeypatch.setenv("BTI_AGY_BIN", str(p))
    from bti.script import models as M
    M.reset_cache()
    return M


def test_R3B_012_models_answers_200_when_the_cli_prints_bytes_that_are_not_utf8(client, tmp_path, monkeypatch):
    M = _fake_agy(tmp_path, monkeypatch, "printf 'ab\\366\\377\\tLabel\\n'; printf '\\366\\377' >&2; exit 0")
    try:
        r = client.get("/api/models")
        assert r.status_code == 200, f"{r.status_code} {r.text[:100]}"
        assert any(m["provider"] == "antigravity" for m in r.json())
    finally:
        M.reset_cache()


def test_R3B_013_starting_a_mock_job_does_not_wait_for_agy_models(client, tmp_path, monkeypatch, flow_pid):
    M = _fake_agy(tmp_path, monkeypatch, "sleep 4; printf 'g1\\tOne\\n'")
    try:
        t = time.time()
        r = client.post(P(flow_pid) + "/outline/generate", json={"model": "mock"})
        waited = time.time() - t
        assert r.status_code == 200
        wait_job(client, r.json()["job_id"])
        assert waited < 1.5, f"a job with the mock model waited {waited:.1f} s for `agy models`"
    finally:
        M.reset_cache()
