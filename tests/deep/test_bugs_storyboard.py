"""Known bugs in the storyboard / render side. Each test FAILS today and passes when the bug is fixed."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import time

import numpy as np
import pytest
from PIL import Image

from conftest import put_sb, state, strip, wait_job


def _sb(client, pid):
    st = state(client, pid)
    return strip(st["storyboard"]), st


def _file(projects_root, pid):
    return projects_root / pid / "storyboard.json"


def test_B001_unknown_style_is_refused_and_not_saved(client, arn, projects_root):
    sb, st = _sb(client, arn)
    before = _file(projects_root, arn).read_text()
    sb["style"] = "nope"
    r = put_sb(client, arn, sb, st["rev"])
    assert r.status_code == 422, r.status_code
    assert _file(projects_root, arn).read_text() == before
    assert client.get(f"/api/projects/{arn}").status_code == 200


@pytest.mark.parametrize("mut", ["t_str", "off_str", "canvas_str"])
def test_B002_validate_does_not_crash_on_wrong_types(client, arn, mut):
    sb, st = _sb(client, arn)
    if mut == "t_str":
        sb["shots"][5]["start"] = {"t": "abc"}
    elif mut == "off_str":
        w = st["timing"]["words"][st["storyboard"]["shots"][3]["start"]["w"]]["w"]
        sb["shots"][3]["overlays"][0]["start"] = {"w": st["storyboard"]["shots"][3]["start"]["w"], "off": "a", "text": w}
    else:
        sb["canvas"] = "x"
    r = client.post(f"/api/projects/{arn}/validate", json={"storyboard": sb})
    assert r.status_code == 200, r.status_code
    assert any(i["level"] == "error" for i in r.json()["issues"])


@pytest.mark.parametrize("field,value", [("timing", "../../x.json"), ("timing", "missing_timing.json"),
                                          ("audio", "../../../etc/hosts")])
def test_B003_paths_must_exist_inside_project(client, arn, projects_root, field, value):
    sb, st = _sb(client, arn)
    before = _file(projects_root, arn).read_text()
    sb[field] = value
    r = put_sb(client, arn, sb, st["rev"])
    assert r.status_code == 422, (r.status_code, r.text[:100])
    assert _file(projects_root, arn).read_text() == before


@pytest.mark.parametrize("path", ["/etc/hosts", "media/../../t_arn/storyboard.json"])
def test_B003_asset_file_path_must_stay_inside_media(client, arn, path):
    sb, st = _sb(client, arn)
    sb["assets"]["A"]["file"] = path
    issues = client.post(f"/api/projects/{arn}/validate", json={"storyboard": sb}).json()["issues"]
    assert any(i["level"] == "error" and i["path"].startswith("assets.A") for i in issues)


def test_B004_frame_of_a_broken_draft_is_not_a_500(client, arn):
    sb, st = _sb(client, arn)
    t = st["storyboard"]["shots"][3]["_t0"] + 0.3
    bad = copy.deepcopy(sb)
    bad["shots"][3]["slots"]["image"]["asset"] = "ZZZ"
    assert client.post(f"/api/projects/{arn}/frame", json={"t": t, "width": 320, "storyboard": bad}).status_code < 500
    bad = copy.deepcopy(sb)
    bad["assets"]["A"]["file"] = "media/nope.jpg"
    assert client.post(f"/api/projects/{arn}/frame", json={"t": t, "width": 320, "storyboard": bad}).status_code < 500
    bad = copy.deepcopy(sb)
    bad["shots"] = []
    assert client.post(f"/api/projects/{arn}/frame", json={"t": 1, "width": 320, "storyboard": bad}).status_code < 500


def test_B004_preview_of_a_broken_draft_is_refused_up_front(client, arn):
    sb, st = _sb(client, arn)
    bad = copy.deepcopy(sb)
    bad["shots"][3]["slots"]["image"]["asset"] = "ZZZ"
    t0 = st["storyboard"]["shots"][3]["_t0"]
    r = client.post(f"/api/projects/{arn}/preview", json={"t0": t0, "t1": t0 + 1, "storyboard": bad})
    assert r.status_code == 422, "an invalid draft should be refused with its issues, not queued"


def test_B005_text_param_with_newline_renders(client, lab):
    sb, st = _sb(client, lab)
    si = next(i for i, s in enumerate(sb["shots"]) if any(o["technique"] == "X-ANN-01" for o in s.get("overlays", [])))
    o = next(o for o in sb["shots"][si]["overlays"] if o["technique"] == "X-ANN-01")
    o["params"]["text"] = "a\nb\n\nc"
    ro = next(o for o in st["storyboard"]["shots"][si]["overlays"] if o["technique"] == "X-ANN-01")
    r = client.post(f"/api/projects/{lab}/frame", json={"t": ro["_t0"] + 0.5, "width": 320, "storyboard": sb})
    assert r.status_code == 200, r.text[:150]


def _overlay_on_plain_shot(client, pid, tech, params, slots=None):
    sb, st = _sb(client, pid)
    si = next(i for i, s in enumerate(sb["shots"]) if s["id"] == "s0037")
    a = st["storyboard"]["shots"][si]["_t0"]
    o = {"id": "ox", "technique": tech, "start": {"t": round(a + 0.3, 3)}, "dur": 2.0, "params": params,
         "locked": False, "source": "human", "note": ""}
    if slots:
        o["slots"] = slots
    d = copy.deepcopy(sb)
    d["shots"][si]["overlays"] = [o]
    return d, si, a


def test_B006_overlay_required_slot_is_enforced(client, lab):
    d, si, a = _overlay_on_plain_shot(client, lab, "HI-03",
                                      client.post(f"/api/projects/{lab}/defaults", json={"technique": "HI-03", "context": {}}).json()["params"])
    issues = client.post(f"/api/projects/{lab}/validate", json={"storyboard": d}).json()["issues"]
    # ADJUSTED by the backend fixer to the coordinator's rule 2 ("incomplete is not invalid"): a missing required slot is a
    # `warn` with code `incomplete` naming the slot, not an `error`; it saves, and approval is refused while it exists.
    assert any(i["level"] == "warn" and i.get("code") == "incomplete" and "mask" in i["message"] for i in issues)
    assert not any(i["level"] == "error" for i in issues)


@pytest.mark.parametrize("tech", ["STATIC-08", "X-ANN-03"])
def test_B007_label_defaults_have_a_position(client, lab, tech):
    sb, st = _sb(client, lab)
    shot = next(s for s in sb["shots"] if s["id"] == "s0037")
    ctx = {"item": "overlay", "shot_id": shot["id"], "slots": shot["slots"], "canvas": sb["canvas"],
           "assets": {k: {"width": v.get("width"), "height": v.get("height"), "regions": v.get("regions") or {}}
                      for k, v in sb["assets"].items()}}
    p = client.post(f"/api/projects/{lab}/defaults", json={"technique": tech, "context": ctx}).json()["params"]
    assert p.get("at") is not None or p.get("screen") is not None


def test_B020_corrupt_storyboard_gives_a_json_error(client, arn, projects_root):
    for content in ("[1,2]", "null", "{trunc"):
        (projects_root / arn / "storyboard.json").write_text(content)
        r = client.get(f"/api/projects/{arn}")
        assert r.headers["content-type"].startswith("application/json"), (content, r.text[:60])


def test_B021_history_is_pruned(client, lab, projects_root):
    sb, st = _sb(client, lab)
    rev = st["rev"]
    for i in range(70):
        d = copy.deepcopy(sb)
        d["title"] = f"v{i}"
        r = put_sb(client, lab, d, rev)
        assert r.status_code == 200
        rev = r.json()["rev"]
    n = len(list((projects_root / lab / "history").glob("*.json")))
    assert n <= 50, f"{n} history files after 70 saves"


def test_B022_frame_cache_follows_timing_changes(client, arn, projects_root):
    st = state(client, arn)
    t = st["storyboard"]["shots"][3]["_t0"] + 0.3
    a = client.get(f"/api/projects/{arn}/frame", params={"t": t, "width": 320}).content
    f = projects_root / arn / "timing.json"
    d = json.loads(f.read_text())
    for w in d["words"]:
        w["s"] += 6.0
        w["e"] += 6.0
    for b in d.get("beats", []):
        b["start"] += 6
        b["end"] += 6
    f.write_text(json.dumps(d))
    b = client.get(f"/api/projects/{arn}/frame", params={"t": t, "width": 320}).content
    assert hashlib.md5(a).digest() != hashlib.md5(b).digest(), "the still did not change after timing.json moved"


def test_B023_missing_timing_gives_a_json_error(client, arn, projects_root):
    (projects_root / arn / "timing.json").unlink()
    r = client.get(f"/api/projects/{arn}")
    assert r.headers["content-type"].startswith("application/json"), r.text[:60]


@pytest.mark.parametrize("w,h", [(-5, "x"), ("x", "y")])
def test_B024_defaults_with_bad_asset_size(client, lab, w, h):
    r = client.post(f"/api/projects/{lab}/defaults", json={"technique": "CAM-05", "context": {
        "slots": {"image": {"asset": "A"}}, "assets": {"A": {"width": w, "height": h}}}})
    assert r.status_code < 500, r.status_code


def test_B025_long_preview_does_not_freeze_stills(client, arn):
    """A 20 s 1280x720 30 fps preview (600 frames) must not hold the engine for the whole render."""
    st = state(client, arn)
    sb = strip(st["storyboard"])
    client.get(f"/api/projects/{arn}/frame", params={"t": 40, "width": 320})
    r = client.post(f"/api/projects/{arn}/preview", json={"t0": 100, "t1": 120, "width": 1280, "fps": 30})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    time.sleep(1.0)
    t = time.time()
    client.post(f"/api/projects/{arn}/frame", json={"t": 41.0, "width": 320, "storyboard": sb})
    waited = time.time() - t
    wait_job(client, jid, timeout=300)
    assert waited < 3.0, f"a still waited {waited:.1f}s behind the preview"


def test_B026_preview_rejects_fps_zero(client, arn):
    r = client.post(f"/api/projects/{arn}/preview", json={"t0": 5, "t1": 6, "fps": 0})
    assert r.status_code == 422


def _preview_seconds(client, pid, body):
    t = time.time()
    r = client.post(f"/api/projects/{pid}/preview", json=body)
    assert r.status_code == 200, r.text
    j = wait_job(client, r.json()["job_id"], timeout=120)
    assert j["state"] == "done", j
    return time.time() - t


def _ref_preview_body(client, pid, tid):
    from sweep import build_draft, locate, sample_times
    reg = {t["id"]: t for t in client.get("/api/styles/gae").json()["techniques"]}
    st = state(client, pid)
    sb, rs = strip(st["storyboard"]), st["storyboard"]
    kind, i, j = locate(sb, reg[tid])
    t = sample_times(rs, kind, i, j)[0]
    t0 = max(0.0, t - 0.5) if kind not in ("base", "card") else rs["shots"][i]["_t0"]
    return {"t0": t0, "t1": t0 + 3.0, "width": 640, "fps": 15, "storyboard": sb}


def test_B028_tr03_preview_is_not_an_outlier(client, lab):
    ref = ["LAY-01", "CAM-03", "HI-01", "X-TR-01", "X-CARD-02"]
    base = sorted(_preview_seconds(client, lab, _ref_preview_body(client, lab, t)) for t in ref)[len(ref) // 2]
    tr = min(_preview_seconds(client, lab, _ref_preview_body(client, lab, "TR-03")) for _ in range(2))
    assert tr < 2.2 * base, f"TR-03 {tr:.1f}s vs median {base:.1f}s of five other techniques"


def test_B029_x_lay_01_preview_frame_count(client, lab, tmp_path):
    import subprocess
    body = _ref_preview_body(client, lab, "X-LAY-01")
    r = client.post(f"/api/projects/{lab}/preview", json=body)
    j = wait_job(client, r.json()["job_id"], timeout=120)
    clip = client.get(j["result_url"]).content
    f = tmp_path / "c.mp4"
    f.write_bytes(clip)
    out = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                          "stream=nb_read_frames", "-of", "json", str(f)], capture_output=True)
    assert int(json.loads(out.stdout)["streams"][0]["nb_read_frames"]) == 45
