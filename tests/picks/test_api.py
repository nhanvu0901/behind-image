"""The picks routes end to end on a temp project: real media facade, fake sources (no network), no paid call."""
import copy
import json
import urllib.error

import pytest
from fastapi.testclient import TestClient
from picks_helpers import FakeNet, beat_ids, load_fix, make_project, mount, png_bytes

from bti.editor.app import create_app
from bti.editor import picks_api
from bti.media import api as media_api
from bti.media.sources.bookpage import BookPageSource
from bti.media.sources.commons import CommonsSource
from bti.media.sources.met import MetSource
from bti.media.sources.osm import OsmSource
from bti.script import env
from bti.script import store

PAGES = {p["pageid"]: p for p in load_fix("commons_search.json")["query"]["pages"]}
PD_ID = "File:Jan van Eyck - The Arnolfini Portrait - Google Art Project.jpg"


def commons_net():
    one = lambda n: {"query": {"pages": [copy.deepcopy(PAGES[n])]}}
    return FakeNet([("Google+Art+Project", one(2)), ("Arnolfini+nc.jpg", one(3)), ("Arnolfini+small.png", one(1)),
                    ("Arnolfini+nolicence", one(5)),
                    # CHANGED (mediafix3): the 4386 x 6000 Arnolfini is downloaded as the rendition its API answer names (thumb/a.jpg)
                    ("wikipedia/commons/a/a0", png_bytes(1300, 1250)), ("upload.wikimedia.org/thumb/a.jpg", png_bytes(1300, 1250)),
                    ("wikipedia/commons/s/s0", png_bytes(800, 600)),
                    ("x/nc.jpg", png_bytes(1300, 1250)), ("x/nl.jpg", png_bytes(1300, 1250)),
                    ("commons.wikimedia.org", load_fix("commons_search.json"))])


@pytest.fixture
def sources(monkeypatch):
    net = commons_net()
    monkeypatch.setitem(media_api._SOURCES, "commons", CommonsSource(opener=net, sleep=lambda s: None))
    met = FakeNet([("/search", {"total": 1, "objectIDs": [436535]}), ("/objects/436535", load_fix("met_object.json")),
                   ("images.metmuseum.org", png_bytes(1500, 1300))])
    monkeypatch.setitem(media_api._SOURCES, "met", MetSource(opener=met, sleep=lambda s: None))
    # the keyless map source is in the default list: a fake transport that finds no place (never a real request), and no keys for the others
    monkeypatch.setitem(media_api._SOURCES, "osm", OsmSource(opener=FakeNet([("nominatim", [])]), sleep=lambda s: None))
    monkeypatch.setattr(env, "has_key", lambda name: False)
    monkeypatch.setitem(media_api._SOURCES, "book", BookPageSource(renderer=lambda b, k, r, dest: dest.write_bytes(png_bytes(1358, 1600))))
    return net, met


@pytest.fixture
def client(root, proj, sources):
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    mount(app)
    with TestClient(app) as c:
        c.pid, c.pdir, c.root = proj.name, proj, root
        c.u = lambda tail="": f"/api/projects/{proj.name}/picks{tail}"
        yield c


def test_get_new_project(client):
    r = client.get(client.u()).json()
    assert r["exists"] is False and r["picks"]["main_asset"] is None and r["approved"] is False
    assert [i["code"] for i in r["issues"] if i["level"] == "error"] == ["no_main"]
    assert r["narration"]["approved"] is True and len(r["narration"]["beat_ids"]) == 6
    assert [d["id"] for d in r["details"]] == ["D1", "D2"] and r["default_main_query"] == "The Test Painting A. Painter"
    assert "video_tools" in r and "available" in r["video_tools"]
    assert not (client.pdir / "picks.json").exists()                      # reading writes nothing


def test_unknown_project_is_404(client):
    assert client.get("/api/projects/nope/picks").status_code == 404


def test_search_both_sources_and_flags(client):
    r = client.post(client.u("/search"), json={"query": "Arnolfini"}).json()
    by = {c["source_id"]: c for c in r["items"]}
    assert r["errors"] == [] and "436535" in by
    assert by["File:Arnolfini nc.jpg"]["flag"] == "rejected" and by["File:Arnolfini nolicence.jpg"]["flag"] == "unknown"
    assert by["File:Arnolfini small.png"]["flag"] == "small" and by[PD_ID]["flag"] is None
    assert all(c["imported"] is None for c in r["items"])


def test_search_default_query_from_beat_show(client):
    r = client.post(client.u("/search"), json={"beat": "b0001", "sources": ["commons"]})
    assert r.status_code == 200 and r.json()["query"] == "the mirror"
    assert client.post(client.u("/search"), json={"beat": "b9999"}).status_code == 404
    assert client.post(client.u("/search"), json={}).json()["detail"] and client.post(client.u("/search"), json={}).status_code == 422


def test_one_source_failing_does_not_sink_the_search(client, monkeypatch):
    bad = FakeNet([("/search", urllib.error.URLError("down"))])
    monkeypatch.setitem(media_api._SOURCES, "met", MetSource(opener=bad, sleep=lambda s: None))
    r = client.post(client.u("/search"), json={"query": "x"}).json()
    assert [e["source"] for e in r["errors"]] == ["met"] and r["errors"][0]["code"] == "source_unreachable" and r["items"]


def import_(client, sid, **kw):
    return client.post(client.u("/import"), json={"source": "commons", "source_id": sid, **kw})


def test_import_main_painting(client):
    r = import_(client, PD_ID, as_main=True)
    assert r.status_code == 200
    j = r.json()
    key = j["asset_key"]
    assert j["picks"]["main_asset"] == key and j["asset"]["credit"]["flag"] is None and j["asset"]["credit"]["licence"] == "PD"
    assert (client.pdir / j["asset"]["file"]).is_file()
    assert json.loads((client.pdir / "picks.json").read_text())["main_asset"] == key
    again = import_(client, PD_ID).json()
    assert again["asset_key"] == key


@pytest.mark.parametrize("sid,flag", [("File:Arnolfini nc.jpg", "rejected"), ("File:Arnolfini nolicence.jpg", "unknown"),
                                      ("File:Arnolfini small.png", "small")])
def test_import_is_never_refused_for_licence_or_size(client, sid, flag):
    r = import_(client, sid)
    assert r.status_code == 200, r.text
    assert r.json()["asset"]["credit"]["flag"] == flag
    assert any(i["code"] == "asset_flag" for i in r.json()["issues"])


def test_import_met_and_bad_source(client):
    r = client.post(client.u("/import"), json={"source": "met", "source_id": "436535"})
    assert r.status_code == 200 and r.json()["asset"]["credit"]["source"] == "met"
    assert client.post(client.u("/import"), json={"source": "flickr", "source_id": "1"}).json()["code"] == "unknown_source"
    assert client.post(client.u("/import"), json={"source": "commons"}).status_code == 422


def test_book_images_listing_and_import(client):
    li = client.get(client.u("/book-images")).json()
    assert [(x["book_id"], x["ref"]) for x in li["images"]] == [("payne_gae", 850)]        # the other work is not ours
    assert [p["ref"] for p in li["pages"]] == [23, 24, 25]
    assert li["images"][0]["thumb_url"].startswith("/api/library/works/payne_gae/2/image/850.jpg")
    r = client.post(client.u("/import-book-image"), json={"source_id": "payne_gae/img/850", "as_main": True})
    assert r.status_code == 200
    a = r.json()["asset"]
    assert r.json()["picks"]["main_asset"] == r.json()["asset_key"] and a["credit"]["source"] == "book" and a["credit"]["flag"] == "unknown"
    assert (a["width"], a["height"]) == (1358, 1600)
    assert client.post(client.u("/import-book-image"), json={"source_id": "payne_gae/page/99"}).status_code == 404
    assert client.post(client.u("/import-book-image"), json={"source_id": "../../x"}).status_code == 404


def test_upload_ok_and_broken(client):
    good = png_bytes(60, 40)
    r = client.post(client.u("/upload"), files={"file": ("my photo.png", good, "image/png")}, data={"title": "Mine"})
    assert r.status_code == 200 and r.json()["asset"]["credit"]["flag"] == "unknown" and r.json()["asset"]["title"] == "Mine"
    r = client.post(client.u("/upload"), files={"file": ("x.png", good[:-30], "image/png")})
    assert r.status_code == 422 and r.json()["code"] in ("image_truncated", "image_unreadable")
    e = client.post(client.u("/upload"), files={"file": ("x.png", b"", "image/png")})
    assert e.status_code == 422 and e.json()["code"].startswith("image_")
    assert client.post(client.u("/upload"), files={"file": ("x.gif", good, "image/gif")}).status_code == 422
    assert not list((client.pdir / "cache" / "uploads").glob("*"))                 # temp files are removed


def test_upload_with_licence_and_as_main(client):
    r = client.post(client.u("/upload"), files={"file": ("a.png", png_bytes(1300, 1250), "image/png")},
                    data={"licence": "CC BY 4.0", "author": "Me", "source_url": "https://x", "as_main": "1"}).json()
    assert r["asset"]["credit"]["flag"] is None and r["picks"]["main_asset"] == r["asset_key"]


def test_put_edits_and_rules(client):
    j = import_(client, PD_ID, as_main=True).json()
    key, rev = j["asset_key"], j["rev"]
    d = j["picks"]
    d["beats"]["b0001"] = {"items": [{"asset": key, "region": None, "role": "main", "note": "n"}], "status": "picked", "note": ""}
    r = client.put(client.u(), json={"picks": d, "base_rev": rev})
    assert r.status_code == 200 and r.json()["picks"]["beats"]["b0001"]["items"][0]["note"] == "n"
    # stale
    r2 = client.put(client.u(), json={"picks": d, "base_rev": rev})
    assert r2.status_code == 409 and r2.json()["code"] == "stale" and r2.json()["rev"] == r.json()["rev"]
    # cannot invent an asset or change the file or credit
    d2 = r.json()["picks"]
    d2["assets"]["NEW"] = copy.deepcopy(d2["assets"][key])
    assert client.put(client.u(), json={"picks": d2, "base_rev": r.json()["rev"]}).json()["code"] == "unknown_asset"
    d3 = r.json()["picks"]
    d3["assets"][key]["file"] = "../../etc/passwd"
    d3["assets"][key]["credit"]["licence"] = "forged"
    d3["assets"][key]["title"] = "New title"
    r3 = client.put(client.u(), json={"picks": d3, "base_rev": r.json()["rev"]}).json()
    assert r3["picks"]["assets"][key]["file"] == j["asset"]["file"] and r3["picks"]["assets"][key]["credit"]["licence"] == "PD"
    assert r3["picks"]["assets"][key]["title"] == "New title"
    bad = r3["picks"]
    bad["beats"]["b0001"]["items"][0]["role"] = "dance"
    assert client.put(client.u(), json={"picks": bad, "base_rev": r3["rev"]}).status_code == 422


def test_regions(client):
    j = import_(client, PD_ID, as_main=True).json()
    key = j["asset_key"]
    url = client.u(f"/assets/{key}/regions")
    # CHANGED (the stored size rule): regions are in the pixels of the stored file (the fake download is 1300 x 1250), not of the
    # original that Commons describes (4386 x 6000): (2210, 1730) used to be accepted only because of that wrong declared size
    ok = {"MIRROR": {"x": 650, "y": 620, "rx": 160, "ry": 160, "label": "Gương"}}
    r = client.put(url, json={"regions": ok, "base_rev": j["rev"]})
    assert r.status_code == 200 and r.json()["picks"]["assets"][key]["regions"]["MIRROR"]["rx"] == 160
    assert client.put(url, json={"regions": ok, "base_rev": j["rev"]}).json()["code"] == "stale"
    assert client.put(url, json={"regions": {"A": {"x": 99999, "y": 1}}}).json()["code"] == "region_outside"
    assert client.put(url, json={"regions": {"A": {"x": 2210, "y": 1730}}}).json()["code"] == "region_outside"      # inside the original, outside the file
    assert client.put(url, json={"regions": {"bad/name": {"x": 1, "y": 1}}}).json()["code"] == "region_name"
    assert client.put(url, json={"regions": {"A": {"x": "1", "y": 1}}}).json()["code"] == "region_shape"
    assert client.put(url, json={"regions": []}).status_code == 422
    assert client.put(client.u("/assets/nope/regions"), json={"regions": {}}).status_code == 404
    assert client.get(client.u()).json()["picks"]["assets"][key]["regions"].keys() == {"MIRROR"}


def test_approval_flow(client):
    j = import_(client, PD_ID, as_main=True).json()
    key = j["asset_key"]
    d = j["picks"]
    d["beats"]["b0001"] = {"items": [{"asset": key, "region": "GONE", "role": "detail", "note": ""}], "status": "picked", "note": ""}
    r = client.put(client.u(), json={"picks": d, "base_rev": j["rev"]}).json()
    bad = client.post(client.u("/approve"), json={"rev": r["rev"]})
    assert bad.status_code == 422 and bad.json()["code"] == "picks_have_errors"
    d = r["picks"]
    d["beats"]["b0001"]["items"][0]["region"] = None
    r = client.put(client.u(), json={"picks": d, "base_rev": r["rev"]}).json()
    assert client.post(client.u("/approve"), json={"rev": "old"}).json()["code"] == "stale"
    ok = client.post(client.u("/approve"), json={"rev": r["rev"]})
    assert ok.status_code == 200 and ok.json()["approved"] is True
    assert any(i["code"] == "beat_no_pick" for i in ok.json()["issues"])          # a warning, not an error
    from bti.picks import state
    assert state(client.pdir)["state"] == "done"
    # a change drops the approval; the narration changing makes a recorded approval stale
    ok2 = client.put(client.u(), json={"picks": ok.json()["picks"], "base_rev": ok.json()["rev"]}).json()
    assert ok2["approved"] is True
    n = store.load_narration(client.pdir)
    n.chapters[0].beats[0].text += " More words."
    store.save_narration(client.pdir, n)
    s = state(client.pdir)
    assert s["state"] == "stale" and s["reason"] == "narration_changed"
    after = client.get(client.u()).json()
    assert after["approved"] is False


def test_approve_needs_approved_narration(root, sources):
    d = make_project(root, "pk2", approved=False)
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    mount(app)
    with TestClient(app) as c:
        u = "/api/projects/pk2/picks"
        j = c.post(u + "/import", json={"source": "commons", "source_id": PD_ID, "as_main": True}).json()
        r = c.post(u + "/approve", json={"rev": j["rev"]})
        assert r.status_code == 409 and r.json()["code"] == "narration_not_approved"
        assert c.get(u).json()["narration"]["approved"] is False


def test_corrupt_picks_is_a_data_error(client):
    (client.pdir / "picks.json").write_text("{broken")
    r = client.get(client.u())
    assert r.status_code == 409 and r.json()["data_error"] == "picks"


def test_deleted_project_is_not_recreated(client, sources):
    import shutil
    shutil.rmtree(client.pdir)
    r = client.post(client.u("/import"), json={"source": "commons", "source_id": PD_ID})
    assert r.status_code == 404 and not client.pdir.exists()


def _mp4_bytes(w: int = 320, h: int = 180, frames: int = 12) -> bytes:
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "clip.mp4"
        ff = shutil.which("ffmpeg")
        if ff:
            subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=blue:s={w}x{h}:d=1:r=12",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], check=True)
        else:
            import cv2
            import numpy as np
            wr = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), 12, (w, h))
            for _ in range(frames):
                wr.write(np.full((h, w, 3), 120, dtype=np.uint8))
            wr.release()
        return out.read_bytes()


def test_video_search_paid_gate_and_url_inspect(client):
    assert client.post(client.u("/video-search"), json={"query": "van eyck"}).json()["code"] == "confirm_required"

    fake_info = {
        "id": "dQw4w9WgXcQ", "title": "Van Eyck Oil Technique", "channel": "Museum",
        "duration": 90.0, "height": 1080, "width": 1920, "license": "Standard YouTube License",
        "chapters": [{"title": "glazing oil technique", "start_time": 12, "end_time": 24}],
    }
    client.app.state.video_search_fn = lambda q: [{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": "VE", "snippet": "", "is_video": True}]
    client.app.state.video_metadata_fn = lambda u, td: (fake_info, [])

    r = client.post(client.u("/video-search"), json={"query": "oil technique", "confirm_paid": True})
    assert r.status_code == 200 and r.json()["paid"] is True and len(r.json()["items"]) == 1
    assert r.json()["items"][0]["moments"][0]["start"] == 12.0

    free = client.post(client.u("/video-search"), json={"url": "https://youtu.be/dQw4w9WgXcQ", "query": "oil"})
    assert free.status_code == 200 and free.json()["paid"] is False and free.json()["items"][0]["id"] == "dQw4w9WgXcQ"
    assert free.json()["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert client.post(client.u("/video-search"), json={"url": "https://example.org/not-yt"}).json()["code"] == "video_bad_url"
    assert client.post(client.u("/video-search"), json={"url": "--batch-file=C:/x youtube.com/watch?v=aaaaaaaaaaa"}).json()["code"] == "video_bad_url"
    assert client.post(client.u("/video-search"), json={"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa; rm -rf /"}).json()["code"] == "video_bad_url"

    def fail_missing(*a, **k):
        from bti.media.clips import ToolMissing
        raise ToolMissing("missing yt-dlp")
    client.app.state.video_metadata_fn = fail_missing
    miss = client.post(client.u("/video-search"), json={"url": "https://youtu.be/dQw4w9WgXcQ"})
    assert miss.status_code == 503 and miss.json()["code"] == "tool_missing"



def test_import_clip_and_upload_video(client):
    import_(client, PD_ID, as_main=True)
    mp4 = _mp4_bytes()

    def fake_imp(pdir, url, s, e, *, strict_licence=False, require_root=True):
        assert url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        m = pdir / "media"
        m.mkdir(exist_ok=True)
        (m / "ve_clip.mp4").write_bytes(mp4)
        return {"asset_key": "ve_clip", "asset": {
            "file": "media/ve_clip.mp4", "kind": "video", "title": "Glaze Clip",
            "artist": "Museum", "year": "", "width": 320, "height": 180, "duration": e - s,
            "credit": {"source": "youtube", "source_url": url, "author": "Museum", "licence": "Standard", "licence_url": "", "flag": "rejected"},
        }}

    client.app.state.clip_importer = fake_imp
    assert client.post(client.u("/import-clip"), json={"url": "https://youtu.be/dQw4w9WgXcQ", "start": 5, "end": 5.1}).json()["code"] == "video_bad_range"
    assert client.post(client.u("/import-clip"), json={"url": "--batch-file=C:/x youtube.com/watch?v=aaaaaaaaaaa", "start": 1, "end": 5}).json()["code"] == "video_bad_url"
    assert client.post(client.u("/import-clip"), json={"url": "https://evil.com/x", "start": 1, "end": 5}).json()["code"] == "video_bad_url"
    import bti.longjob as lj

    # Async job test
    r_async = client.post(client.u("/import-clip"), json={"url": "https://youtu.be/dQw4w9WgXcQ", "start": 10, "end": 18, "beat_id": "b0001", "note": "when talking about glaze"})
    assert r_async.status_code == 200 and "job_id" in r_async.json()
    jid = r_async.json()["job_id"]
    rec = lj.manager.wait(jid, timeout=10)
    assert rec["state"] == "done"
    part_res = rec.get("result") or {}
    assert part_res.get("asset", {}).get("duration") == 8.0

    # Wait=True test
    r = client.post(client.u("/import-clip"), json={"url": "https://youtu.be/dQw4w9WgXcQ", "start": 10, "end": 18, "beat_id": "b0001", "note": "when talking about glaze", "wait": True})
    assert r.status_code == 200 and r.json()["asset"]["kind"] == "video" and r.json()["asset"]["duration"] == 8.0
    items = r.json()["picks"]["beats"]["b0001"]["items"]
    assert items[0]["asset"] == "ve_clip" and items[0]["role"] == "video" and items[0]["note"] == "when talking about glaze"

    # Cancel test
    import threading
    started_evt = threading.Event()
    def slow_imp(pdir, url, s, e, **kw):
        started_evt.set()
        import time
        for _ in range(50):
            time.sleep(0.05)
        return fake_imp(pdir, url, s, e, **kw)
    client.app.state.clip_importer = slow_imp
    r_c = client.post(client.u("/import-clip"), json={"url": "https://youtu.be/dQw4w9WgXcQ", "start": 10, "end": 18})
    jid_c = r_c.json()["job_id"]
    started_evt.wait(timeout=2.0)
    cancel_res = client.post(f"/api/longjobs/{jid_c}/cancel")
    assert cancel_res.status_code == 200
    rec_c = lj.manager.wait(jid_c, timeout=10)
    assert rec_c["state"] == "cancelled"

    bad_main = client.post(client.u("/upload"), files={"file": ("clip.mp4", mp4, "video/mp4")}, data={"as_main": "1"})
    assert bad_main.status_code == 422 and bad_main.json()["code"] == "video_not_main"

    up = client.post(client.u("/upload"), files={"file": ("brushwork.mp4", mp4, "video/mp4")}, data={"title": "Brush"})
    assert up.status_code == 200 and up.json()["asset"]["kind"] == "video" and up.json()["asset"]["width"] == 320
    th = client.get(f"/api/projects/{client.pid}/files/{up.json()['asset']['file']}?w=160")
    assert th.status_code == 200 and th.headers["content-type"] == "image/jpeg"
