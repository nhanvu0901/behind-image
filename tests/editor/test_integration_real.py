"""Integration tests: the editor backend against the REAL engine (bti.engine) on a small project (projects/demo_stub).

Skipped when the engine is not importable. Media stays the stub (no network); the real media facade is exercised by tests/media
and by the live run recorded in .scratch/integration.
"""
import copy
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

pytest.importorskip("cv2")
engine_api = pytest.importorskip("bti.engine.api")

from bti.editor.app import create_app  # noqa: E402
from editor_helpers import PID, editable  # noqa: E402

P = f"/api/projects/{PID}"


@pytest.fixture()
def rc(root):
    app = create_app(projects_root=root, engine_module=engine_api, media_module=None)
    with TestClient(app) as c:
        c.root = root
        yield c


@pytest.fixture()
def rstate(rc):
    return rc.get(P).json()


def test_health_reports_real_engine_without_fallback(rc, rstate):
    h = rc.get("/api/health").json()
    assert h["engine"] == "real" and "engine_fallbacks" not in h


def test_demo_project_is_valid_against_the_registry(rstate):
    assert [i for i in rstate["issues"] if i["level"] == "error"] == []


def test_frame_is_a_real_jpeg_and_draft_differs(rc, rstate):
    r = rc.get(f"{P}/frame", params={"t": 20, "width": 480})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    im = Image.open(io.BytesIO(r.content))
    assert im.size == (480, 270)
    draft = editable(rstate)
    shot = next(s for s in draft["shots"] if s["technique"] == "CAM-05")
    shot["params"]["camera"][0]["zoom"] *= 2.5
    t = shot["_t0"] + 0.1
    a = rc.get(f"{P}/frame", params={"t": t, "width": 320}).content
    b = rc.post(f"{P}/frame", json={"t": t, "width": 320, "storyboard": draft})
    assert b.status_code == 200 and b.content != a
    assert rc.get(f"{P}/frame", params={"t": t, "width": 320}).content == a   # the draft never leaks into the saved view


def test_defaults_with_the_pages_context(rc, rstate):
    sb = rstate["storyboard"]
    shot = next(s for s in sb["shots"] if s["technique"] == "CAM-05")
    asset = shot["slots"]["image"]["asset"]
    a = sb["assets"][asset]
    ctx = {"item": "shot", "shot_id": shot["id"], "duration": 5, "slots": {"image": {"asset": asset}},
           "assets": {asset: {"width": a["width"], "height": a["height"], "regions": a["regions"], "title": a["title"]}},
           "canvas": sb["canvas"], "camera": {"cx": 100, "cy": 100, "zoom": 0.5}}
    r = rc.post(f"{P}/defaults", json={"technique": "CAM-05", "context": ctx})
    assert r.status_code == 200
    cam = r.json()["params"]["camera"]
    assert len(cam) == 2 and cam[0]["zoom"] == pytest.approx(0.5)      # continues from the camera at the playhead
    # an asset that exists only in the unsaved draft (no key lookup possible)
    ctx2 = {"item": "shot", "slots": {"image": {"asset": "NEW"}}, "assets": {"NEW": {"width": 2000, "height": 3000}}}
    cam2 = rc.post(f"{P}/defaults", json={"technique": "CAM-01", "context": ctx2}).json()["params"]["camera"]
    assert cam2[0]["cx"] == pytest.approx(1000) or cam2[0]["cy"] == pytest.approx(1500)
    assert rc.post(f"{P}/defaults", json={"technique": "NOPE", "context": {}}).status_code == 422


def test_save_409_422_and_approve(rc, rstate):
    doc = editable(rstate)
    doc["shots"][0]["note"] = "edited"
    r = rc.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": rstate["rev"]})
    assert r.status_code == 200 and r.json()["rev"] != rstate["rev"]
    new_rev = r.json()["rev"]
    assert rc.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": rstate["rev"]}).status_code == 409
    bad = copy.deepcopy(doc)
    bad["shots"][1]["params"]["bogus"] = 1
    r = rc.put(f"{P}/storyboard", json={"storyboard": bad, "base_rev": new_rev})
    assert r.status_code == 422 and any(i["level"] == "error" for i in r.json()["issues"])
    ap = rc.post(f"{P}/approve", json={"rev": new_rev})
    assert ap.status_code == 200 and ap.json()["approvals"]["storyboard"]["rev"] == new_rev
    assert rc.get(P).json()["rev"] == new_rev       # approving does not change the revision


def test_preview_clip_has_video_and_audio(rc, rstate):
    import subprocess
    r = rc.post(f"{P}/preview", json={"t0": 1.0, "t1": 3.0, "width": 320, "fps": 10})
    jid = r.json()["job_id"]
    for _ in range(120):
        j = rc.get(f"/api/jobs/{jid}").json()
        if j["state"] in ("done", "error"):
            break
        time.sleep(0.25)
    assert j["state"] == "done", j
    f = rc.root / PID / j["result_url"].split(f"{PID}/files/")[1]
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(f)],
                         capture_output=True, text=True).stdout.split()
    assert "video" in out and "audio" in out


def test_styles_are_merged_registry_with_preview_fallback(rc):
    j = rc.get("/api/styles/gae").json()
    byid = {t["id"]: t for t in j["techniques"]}
    assert len(byid) >= 71
    for tid in ("X-CARD-01", "X-ANN-01", "X-LAY-01"):
        pv = byid[tid]["preview"]
        assert pv and pv["clip"].endswith(f"{tid}.mp4") and pv["thumb"].endswith(f"{tid}.jpg")
        assert rc.get(f"/style/gae/previews/{tid}.mp4").status_code == 200


def test_import_then_slot_renders(rc, rstate):
    sb = editable(rstate)
    imp = rc.post(f"{P}/assets/import", json={"source": "commons", "source_id": "File:Stub_Portrait_1.jpg"}).json()
    key = imp["asset_key"]
    sb["assets"][key] = {k: v for k, v in imp["asset"].items() if k != "thumb_url"}
    shot = next(s for s in sb["shots"] if s["technique"] == "STATIC-01")
    shot["slots"]["image"] = {"asset": key}
    r = rc.post(f"{P}/frame", json={"t": shot["_t0"] + 0.5, "width": 320, "storyboard": sb})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert rc.post(f"{P}/validate", json={"storyboard": sb}).json()["issues"] is not None


def test_locked_proposal_change_is_blocked_with_the_real_engine(rc):
    r = rc.post(f"{P}/proposals/p_demo_001/apply", json={"accept": ["shot.s0006"]}).json()
    assert r["applied"] == [] and r["skipped_locked"] == ["shot.s0006"]
    r = rc.post(f"{P}/proposals/p_demo_001/apply", json={"accept": ["shot.s0002"]})
    assert r.status_code == 200 and r.json()["applied"] == ["shot.s0002"]


def test_overlay_ids_repeat_across_shots_in_the_real_project():
    """The exporter writes o1, o2 ... in every shot, so overlay ids are only unique per shot (the page scopes its lookups)."""
    import json
    from editor_helpers import REPO
    sb = json.loads((REPO / "projects" / "arnolfini" / "storyboard.json").read_text())
    ids = [o["id"] for s in sb["shots"] for o in s.get("overlays", [])]
    assert len(ids) > len(set(ids))
