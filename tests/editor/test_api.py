import io
import json
import time

import pytest
from PIL import Image

from editor_helpers import PID, editable

P = f"/api/projects/{PID}"


def jpeg_size(data: bytes):
    im = Image.open(io.BytesIO(data))
    assert im.format == "JPEG"
    return im.size


# ---------------------------------------------------------------- health, style, static
def test_health(client):
    j = client.get("/api/health").json()
    assert j == {"ok": True, "engine": "stub", "media": "stub"}


def test_style(client):
    j = client.get("/api/styles/gae").json()
    assert set(j) == {"style", "techniques", "intents"}
    assert len(j["techniques"]) >= 60 and "point_at" in j["intents"]
    assert client.get("/api/styles/nope").status_code == 404
    assert client.get("/api/styles/..%2Fx").status_code == 404


def test_style_previews_static(client):
    r = client.get("/style/gae/previews/CAM-05.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert client.get("/style/gae/previews/nope.jpg").status_code == 404
    assert client.get("/style/gae/previews/%2e%2e/techniques.json").status_code == 404
    assert client.get("/style/gae/previews/..%2ftechniques.json").status_code == 404


def test_root_placeholder_or_index(client):
    r = client.get("/")
    assert r.status_code == 200 and "html" in r.headers["content-type"]


def test_static_dir_and_no_escape(root, tmp_path):
    from fastapi.testclient import TestClient
    from bti.editor.app import create_app
    st = tmp_path / "static"
    st.mkdir()
    (st / "index.html").write_text("<p>hi</p>")
    (tmp_path / "secret.txt").write_text("s")
    c = TestClient(create_app(root, engine_module=None, media_module=None, static_dir=st))
    assert c.get("/").text == "<p>hi</p>"
    assert c.get("/..%2fsecret.txt").status_code == 404
    assert c.get("/%2e%2e/secret.txt").status_code == 404


# ---------------------------------------------------------------- projects
def test_list_projects(client):
    j = client.get("/api/projects").json()
    assert j[0]["id"] == PID and j[0]["duration"] == 90.0 and j[0]["updated_at"]


def test_get_project(state):
    assert len(state["rev"]) == 64
    sb = state["storyboard"]
    assert sb["shots"][0]["_t0"] == pytest.approx(state["timing"]["words"][0]["s"])
    assert sb["shots"][-1]["_t1"] == 90.0
    for a, b in zip(sb["shots"], sb["shots"][1:]):
        assert a["_t1"] == b["_t0"]
    ov = sb["shots"][1]["overlays"][0]
    assert ov["start"]["_t"] == ov["_t0"] and ov["_t1"] == pytest.approx(ov["_t0"] + 5.0, abs=1e-3)
    assert [i for i in state["issues"] if i["level"] == "error"] == []
    assert len(sb["shots"]) == 10 and len(state["timing"]["words"]) == 250


def test_unknown_and_bad_pid(client):
    assert client.get("/api/projects/nope").status_code == 404
    for bad in ("..", "Demo", "demo stub", "%2e%2e", "demo_stub%0a", "a" * 70, "-x"):
        assert client.get(f"/api/projects/{bad}").status_code == 404, bad


# ---------------------------------------------------------------- save semantics
def test_put_ok_strips_derived_and_changes_rev(client, state):
    doc = editable(state)
    doc["shots"][0]["note"] = "edited"
    r = client.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": state["rev"]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["rev"] != state["rev"] and j["storyboard"]["shots"][0]["_t0"] is not None
    on_disk = json.loads((client.root / PID / "storyboard.json").read_text())

    def no_underscore(o):
        if isinstance(o, dict):
            assert not any(k.startswith("_") for k in o)
            [no_underscore(v) for v in o.values()]
        elif isinstance(o, list):
            [no_underscore(v) for v in o]
    no_underscore(on_disk)
    assert on_disk["shots"][0]["note"] == "edited"
    assert client.get(P).json()["rev"] == j["rev"]
    assert list((client.root / PID / "history").glob("storyboard_*.json"))


def test_put_409_on_stale_rev(client, state):
    doc = editable(state)
    r = client.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": "0" * 64})
    assert r.status_code == 409 and r.json()["rev"] == state["rev"]
    doc["shots"][0]["note"] = "a"
    assert client.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": state["rev"]}).status_code == 200
    doc["shots"][0]["note"] = "b"
    assert client.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": state["rev"]}).status_code == 409


def test_put_422_on_errors_and_not_saved(client, state):
    doc = editable(state)
    doc["shots"][2]["technique"] = "NOPE-99"
    doc["shots"][1]["params"]["bogus"] = 1
    r = client.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": state["rev"]})
    assert r.status_code == 422
    paths = {i["path"] for i in r.json()["issues"] if i["level"] == "error"}
    assert "shots[2].technique" in paths and "shots[1].params.bogus" in paths
    assert client.get(P).json()["rev"] == state["rev"]


def test_put_warnings_do_not_block(client, state):
    doc = editable(state)
    doc["shots"][3]["start"]["text"] = "wrong-word"  # stale anchor text: warning only
    r = client.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": state["rev"]})
    assert r.status_code == 200
    assert any(i["level"] == "warn" for i in r.json()["issues"])


def test_put_requires_body_fields(client, state):
    assert client.put(f"{P}/storyboard", json={"storyboard": editable(state)}).status_code == 422
    assert client.put(f"{P}/storyboard", json={"base_rev": state["rev"]}).status_code == 422


def test_validate_endpoint(client, state):
    doc = editable(state)
    assert [i for i in client.post(f"{P}/validate", json={"storyboard": doc}).json()["issues"]
            if i["level"] == "error"] == []
    doc["shots"][3]["overlays"][0]["dur"] = 500
    doc["shots"][8]["start"] = {"w": 9999}
    doc["shots"][5]["slots"]["image"] = {"asset": "ZZ"}
    issues = client.post(f"{P}/validate", json={"storyboard": doc}).json()["issues"]
    msgs = {i["path"] for i in issues if i["level"] == "error"}
    assert {"shots[3].overlays[0]", "shots[8].start", "shots[5].slots.image.asset"} <= msgs


def test_validate_shot_order_and_stale_anchor(client, state):
    doc = editable(state)
    doc["shots"][3]["start"]["text"] = "wrong-word"
    doc["shots"][6]["start"] = {"t": doc["shots"][5]["_t0"] + 0.05}
    issues = client.post(f"{P}/validate", json={"storyboard": doc}).json()["issues"]
    assert any(i["level"] == "warn" and "stale" in i["message"] for i in issues)
    assert any(i["level"] == "error" and "minimum" in i["message"] for i in issues)


def test_defaults(client):
    j = client.post(f"{P}/defaults", json={"technique": "CAM-05", "context": {}}).json()
    assert set(j["params"]) <= {"camera", "shadow"}  # camera techniques store only camera and shadow
    assert client.post(f"{P}/defaults", json={"technique": "NOPE", "context": {}}).status_code == 422
    assert client.post(f"{P}/defaults", json={}).status_code == 422


# ---------------------------------------------------------------- approve
def test_approve(client, state):
    assert client.post(f"{P}/approve", json={"rev": "bad"}).status_code == 409
    r = client.post(f"{P}/approve", json={"rev": state["rev"]})
    assert r.status_code == 200
    ap = r.json()["approvals"]["storyboard"]
    assert ap["rev"] == state["rev"] and ap["approved_at"]
    st2 = client.get(P).json()
    assert st2["rev"] == state["rev"]  # approving does not change the revision
    assert st2["storyboard"]["approvals"]["storyboard"]["rev"] == state["rev"]
    # PUT cannot forge approvals
    doc = editable(st2)
    doc["approvals"] = {"storyboard": None}
    doc["shots"][0]["note"] = "x"
    j = client.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": st2["rev"]}).json()
    assert j["storyboard"]["approvals"]["storyboard"]["rev"] == state["rev"] != j["rev"]


def test_approve_refused_with_errors(client, root, state):
    p = root / PID / "storyboard.json"
    sb = json.loads(p.read_text())
    sb["shots"][0]["technique"] = "NOPE-1"
    p.write_text(json.dumps(sb))
    st = client.get(P).json()
    r = client.post(f"{P}/approve", json={"rev": st["rev"]})
    assert r.status_code == 422 and r.json()["issues"]


# ---------------------------------------------------------------- frames
def test_frame_get_and_disk_cache(client, root):
    r = client.get(f"{P}/frame", params={"t": 12.5, "width": 480})
    assert r.status_code == 200 and jpeg_size(r.content) == (480, 270)
    files = list((root / PID / "cache" / "frames").glob("f_*.jpg"))
    assert len(files) == 1
    mt = files[0].stat().st_mtime_ns
    r2 = client.get(f"{P}/frame", params={"t": 12.5, "width": 480})
    assert r2.content == r.content and files[0].stat().st_mtime_ns == mt
    client.get(f"{P}/frame", params={"t": 12.5, "width": 320})
    assert len(list((root / PID / "cache" / "frames").glob("f_*.jpg"))) == 2


def test_frame_cache_control_and_rev(client, state):
    r = client.get(f"{P}/frame", params={"t": 1, "rev": state["render_key"]})
    assert "immutable" in r.headers["cache-control"]
    assert "immutable" not in client.get(f"{P}/frame", params={"t": 1, "rev": "old"}).headers["cache-control"]


def test_frame_validation(client):
    assert client.get(f"{P}/frame").status_code == 422
    assert client.get(f"{P}/frame", params={"t": -1}).status_code == 422
    assert client.get(f"{P}/frame", params={"t": "nan"}).status_code == 422
    assert client.get(f"{P}/frame", params={"t": 1, "width": 99999}).status_code == 422
    assert client.get(f"{P}/frame", params={"t": 1, "width": 10}).status_code == 422


def test_frame_draft_not_cached_and_differs(client, state, root):
    doc = editable(state)
    saved = client.get(f"{P}/frame", params={"t": 5, "width": 480}).content
    n = len(list((root / PID / "cache" / "frames").glob("*.jpg")))
    doc["shots"][0]["id"] = "s_DRAFT"
    r = client.post(f"{P}/frame", json={"t": 5, "width": 480, "storyboard": doc})
    assert r.status_code == 200 and jpeg_size(r.content) == (480, 270)
    assert r.content != saved
    assert r.headers["cache-control"] == "no-store"
    assert len(list((root / PID / "cache" / "frames").glob("*.jpg"))) == n
    # draft is reverted: the saved render is unchanged
    assert client.get(f"{P}/frame", params={"t": 5, "width": 480}).content == saved
    assert client.get(P).json()["storyboard"]["shots"][0]["id"] == "s0001"
    assert (root / PID / "storyboard.json").read_text().count("s_DRAFT") == 0


def test_frame_post_validation(client, state):
    assert client.post(f"{P}/frame", json={"t": 1}).status_code == 422
    assert client.post(f"{P}/frame", json={"width": 480, "storyboard": editable(state)}).status_code == 422


def test_thumb(client, state):
    r = client.get(f"{P}/thumb/s0003")
    assert r.status_code == 200 and jpeg_size(r.content)[0] == 320
    assert client.get(f"{P}/thumb/nope").status_code == 404
    assert client.get(f"{P}/thumb/..%2f..").status_code == 404


# ---------------------------------------------------------------- audio, waveform
def test_waveform(client, root):
    j = client.get(f"{P}/waveform", params={"bins": 500}).json()
    assert len(j["peaks"]) == 500 and j["duration"] == pytest.approx(90.0, abs=0.1)
    assert all(0 <= v <= 1 for v in j["peaks"]) and max(j["peaks"]) > 0.5
    assert len(list((root / PID / "cache").glob("wave_*_500.json"))) == 1
    assert client.get(f"{P}/waveform", params={"bins": 5}).status_code == 422
    assert client.get(f"{P}/waveform").json()["peaks"].__len__() == 4000


def test_audio_range(client):
    full = client.get(f"{P}/audio")
    assert full.status_code == 200 and "audio" in full.headers["content-type"]
    n = len(full.content)
    r = client.get(f"{P}/audio", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100
    assert r.headers["content-range"] == f"bytes 0-99/{n}" and r.content == full.content[:100]
    r = client.get(f"{P}/audio", headers={"Range": "bytes=100-"})
    assert r.status_code == 206 and r.content == full.content[100:]
    r = client.get(f"{P}/audio", headers={"Range": "bytes=-50"})
    assert r.status_code == 206 and r.content == full.content[-50:]
    assert client.get(f"{P}/audio", headers={"Range": f"bytes={n + 10}-"}).status_code == 416


# ---------------------------------------------------------------- jobs / preview
def wait_job(client, jid, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["state"] in ("done", "error"):
            return j
        time.sleep(0.1)
    raise AssertionError("job timeout")


def test_preview_job_lifecycle(client, root):
    r = client.post(f"{P}/preview", json={"t0": 2, "t1": 5, "width": 320, "fps": 10})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    j0 = client.get(f"/api/jobs/{jid}").json()
    assert j0["state"] in ("queued", "running", "done")
    j = wait_job(client, jid)
    assert j["state"] == "done" and j["progress"] == 1.0 and j["error"] is None
    assert j["result_url"].startswith(f"{P}/files/cache/previews/pv_")
    clip = client.get(j["result_url"])
    assert clip.status_code == 200 and clip.content[4:8] == b"ftyp"
    out = root / PID / "cache" / "previews" / j["result_url"].rsplit("/", 1)[1]
    import subprocess
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True).stdout.split()
    assert "video" in probe and "audio" in probe
    # unique names
    j2 = wait_job(client, client.post(f"{P}/preview", json={"t0": 2, "t1": 5, "width": 320, "fps": 10}).json()["job_id"])
    assert j2["result_url"] != j["result_url"]
    # range requests on the clip
    assert client.get(j["result_url"], headers={"Range": "bytes=0-9"}).status_code == 206


def test_preview_with_draft_and_errors(client, state):
    doc = editable(state)
    j = wait_job(client, client.post(f"{P}/preview", json={"t0": 1, "t1": 2, "width": 160, "fps": 5,
                                                          "storyboard": doc}).json()["job_id"])
    assert j["state"] == "done"
    assert client.get("/api/jobs/doesnotexist").status_code == 404
    for body in ({"t0": 5, "t1": 5}, {"t0": 0, "t1": 999}, {"t0": "x", "t1": 3}, {"t0": 0, "t1": 3, "width": 5},
                 {"t0": 0, "t1": 3, "fps": 100}, {"t0": 0, "t1": 3, "storyboard": 5}):
        assert client.post(f"{P}/preview", json=body).status_code == 422, body


def test_job_error_state(client, monkeypatch):
    from bti.editor import engine_stub

    def boom(self, *a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(engine_stub.StubProject, "render_range", boom)
    j = wait_job(client, client.post(f"{P}/preview", json={"t0": 1, "t1": 2}).json()["job_id"])
    assert j["state"] == "error" and "boom" in j["error"] and j["result_url"] is None


def test_preview_cleanup_keeps_last_20(client, root):
    d = root / PID / "cache" / "previews"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(30):
        f = d / f"pv_{i}_x.mp4"
        f.write_bytes(b"x")
        import os
        os.utime(f, (1000 + i, 1000 + i))
    wait_job(client, client.post(f"{P}/preview", json={"t0": 1, "t1": 2, "width": 160, "fps": 5}).json()["job_id"])
    assert len(list(d.glob("pv_*.mp4"))) == 20
    assert not (d / "pv_0_x.mp4").exists()


# ---------------------------------------------------------------- files, path traversal
def test_files_ok_and_thumbnail(client):
    r = client.get(f"{P}/files/media/a_portrait.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    r = client.get(f"{P}/files/media/a_portrait.jpg", params={"w": 100})
    assert r.status_code == 200 and jpeg_size(r.content)[0] == 100
    assert client.get(f"{P}/files/media/nope.jpg").status_code == 404
    assert client.get(f"{P}/files/media").status_code == 404  # a directory


@pytest.mark.parametrize("path", [
    "../storyboard.json", "..%2fstoryboard.json", "%2e%2e/%2e%2e/%2e%2e/etc/passwd", "media/../../x",
    "media/%2e%2e/%2e%2e/demo_stub/storyboard.json", "/etc/passwd", "%2fetc%2fpasswd", "media//a_portrait.jpg",
    "..%5cstoryboard.json", "media%00.jpg", "....//storyboard.json"])
def test_files_traversal(client, path):
    r = client.get(f"{P}/files/{path}")
    assert r.status_code in (400, 404), (path, r.status_code)
    assert b"schema" not in r.content


def test_files_symlink_escape(client, root, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "secret.txt"
    outside.write_text("secret")
    (root / PID / "media" / "link.txt").symlink_to(outside)
    assert client.get(f"{P}/files/media/link.txt").status_code == 404


def test_pid_traversal_everywhere(client):
    for url in ("/api/projects/..%2f..%2fetc/files/passwd", "/api/projects/%2e%2e/storyboard",
                "/api/projects/..%2fdemo_stub/frame?t=1", "/api/projects/demo_stub%2f..%2fdemo_stub/audio"):
        assert client.get(url).status_code in (404, 400), url


def test_proposal_id_traversal(client):
    assert client.get(f"{P}/proposals/..%2fstoryboard").status_code == 404
    assert client.post(f"{P}/proposals/..%2fstoryboard/apply", json={"accept": "all"}).status_code in (404, 405)


# ---------------------------------------------------------------- assets, media
def test_assets_and_regions(client, state):
    a = client.get(f"{P}/assets").json()
    assert set(a) == {"A", "B", "C", "D"} and a["A"]["thumb_url"].endswith("a_portrait.jpg?w=320")
    assert client.get(a["A"]["thumb_url"]).status_code == 200
    reg = {"MIRROR": {"x": 10, "y": 20, "rx": 5, "ry": 5, "label": "Mirror"}}
    r = client.put(f"{P}/assets/A/regions", json={"regions": reg})
    assert r.status_code == 200 and r.json()["rev"] != state["rev"]
    assert client.get(f"{P}/assets").json()["A"]["regions"] == reg
    assert client.put(f"{P}/assets/ZZ/regions", json={"regions": reg}).status_code == 404
    assert client.put(f"{P}/assets/A/regions", json={"regions": {"X": {"x": "a"}}}).status_code == 422
    assert client.put(f"{P}/assets/A/regions", json={}).status_code == 422


def test_media_search_and_import(client):
    c = client.get("/api/media/search", params={"q": "mirror", "limit": 5}).json()
    assert 0 < len(c) <= 5
    for k in ("source", "source_id", "title", "thumb_url", "page_url", "width", "height", "mime", "author",
              "licence", "licence_ok", "licence_reason"):
        assert k in c[0]
    assert client.get(c[0]["thumb_url"]).headers["content-type"] == "image/jpeg"
    ok = next(x for x in client.get("/api/media/search", params={"limit": 50}).json() if x["licence_ok"])
    r = client.post(f"{P}/assets/import", json={"source": ok["source"], "source_id": ok["source_id"]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["asset_key"] not in "ABCD" and j["asset"]["credit"]["licence"] and j["asset"]["thumb_url"]
    assert client.get(j["asset"]["thumb_url"]).status_code == 200


def test_media_import_licence_is_advisory(client):
    """The licence gate only flags (design 2026-11-16, section 6): a restricted or unknown licence is imported with `credit.flag`."""
    cands = client.get("/api/media/search", params={"limit": 50}).json()
    bad = next(x for x in cands if not x["licence_ok"])
    assert bad["flag"] in ("rejected", "unknown")
    r = client.post(f"{P}/assets/import", json={"source": bad["source"], "source_id": bad["source_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["asset"]["credit"]["flag"] == bad["flag"]
    assert client.post(f"{P}/assets/import", json={"source": "x"}).status_code == 422
    assert client.post(f"{P}/assets/import", json={"source": "commons", "source_id": "nope"}).status_code == 404


def _png():
    b = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 10, 10)).save(b, "PNG")
    return b.getvalue()


def test_upload(client, root):
    form = {"title": "T", "artist": "A", "year": "1900", "licence": "CC0", "source_url": "https://x.invalid/a",
            "author": "me"}
    r = client.post(f"{P}/assets/upload", data=form, files={"file": ("my pic.png", _png(), "image/png")})
    assert r.status_code == 200, r.text
    a = r.json()["asset"]
    assert (root / PID / a["file"]).is_file() and a["width"] == 40 and a["credit"]["licence"] == "CC0"
    nc = client.post(f"{P}/assets/upload", data={**form, "licence": "CC BY-NC 4.0"},
                     files={"file": ("p.png", _png(), "image/png")})
    assert nc.status_code == 200 and nc.json()["asset"]["credit"]["flag"] == "rejected"      # flagged, never refused
    bare = client.post(f"{P}/assets/upload", data={}, files={"file": ("q.png", _png(), "image/png")})
    assert bare.status_code == 200, bare.text                                                 # no licence, source or author needed
    assert bare.json()["asset"]["credit"]["flag"] in ("unknown", "small") and bare.json()["asset"]["credit"]["source_url"] == ""
    assert client.post(f"{P}/assets/upload", data=form,
                       files={"file": ("p.exe", b"MZ", "application/octet-stream")}).status_code == 422
    assert client.post(f"{P}/assets/upload", data=form,
                       files={"file": ("p.png", b"not an image", "image/png")}).status_code == 422
    assert not list((root / PID / "cache" / "uploads").glob("*"))


# ---------------------------------------------------------------- facades
def test_broken_facade_falls_back(root):
    import types
    from fastapi.testclient import TestClient
    from bti.editor.app import create_app
    mod = types.SimpleNamespace(open_project=lambda d: (_ for _ in ()).throw(RuntimeError("broken")),
                                load_style=lambda s: (_ for _ in ()).throw(RuntimeError("broken")))
    c = TestClient(create_app(root, engine_module=mod, media_module=None))
    assert c.get("/api/health").json()["engine"] == "real"
    assert c.get(P).status_code == 200  # stub took over for this project
    assert "engine_fallbacks" in c.get("/api/health").json()
    assert len(c.get("/api/styles/gae").json()["techniques"]) > 50


def test_real_facade_is_used(root):
    """A fake real engine: frames come from it, calls are made under the engine lock."""
    import numpy as np
    import types
    from fastapi.testclient import TestClient
    from bti.editor.app import create_app
    from bti.editor.engine_adapter import ENGINE_LOCK
    from bti.editor.engine_stub import StubProject, load_style_stub
    from editor_helpers import REPO
    seen = []

    class P(StubProject):
        def frame_at(self, t, width=960):
            seen.append(ENGINE_LOCK._is_owned())
            return np.full((int(width * 9 / 16), width, 3), 77, np.uint8)
    mod = types.SimpleNamespace(open_project=lambda d: P(d, REPO / "style"),
                                load_style=lambda s: load_style_stub(REPO / "style", s))
    c = TestClient(create_app(root, engine_module=mod, media_module=None))
    assert c.get("/api/health").json()["engine"] == "real"
    r = c.get(f"/api/projects/{PID}/frame", params={"t": 3, "width": 320})
    assert r.status_code == 200 and seen == [True]
    assert Image.open(io.BytesIO(r.content)).getpixel((5, 5))[0] in range(70, 85)


def test_real_media_exceptions_are_translated(root):
    import types
    from fastapi.testclient import TestClient
    from bti.editor.app import create_app

    class LicenceRejected(Exception):
        pass

    def imp(d, s, i, **kw):
        raise LicenceRejected("CC BY-NC not allowed")

    def up(d, f, m, **kw):
        raise ValueError("upload metadata is missing: source_url")

    def se(q, source="commons", kind="image", limit=24):
        raise ValueError("unknown source 'x'")
    mod = types.SimpleNamespace(search=se, import_candidate=imp, add_upload=up)
    c = TestClient(create_app(root, engine_module=None, media_module=mod))
    assert c.get("/api/health").json()["media"] == "real"
    r = c.post(f"{P}/assets/import", json={"source": "commons", "source_id": "x"})
    assert r.status_code == 422 and "NC" in r.json()["reason"]
    assert c.get("/api/media/search", params={"source": "x"}).status_code == 422
    r = c.post(f"{P}/assets/upload", data={"licence": "CC0"}, files={"file": ("p.png", _png(), "image/png")})
    assert r.status_code == 422 and "missing" in r.json()["detail"]
