"""The rule: an asset's width and height are the pixels of the file that was STORED, whatever the source's metadata says.

Every source goes through `api.stored_image_size` (images) or the probe of the stored file (videos, clips). The source's own
claim is kept apart as `original_width` / `original_height`. Fakes only: no request leaves the test process."""
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from PIL import Image

from bti.media import api, assets, clips
from bti.media.imageinfo import drawn_size
from bti.media.sources.bookpage import BookPageSource
from bti.media.sources.commons import THUMB_STEPS, CommonsSource
from bti.media.sources.osm import OsmSource
from bti.media.sources.pexels import PexelsSource
from bti.media.sources.pixabay import PixabaySource

from conftest import FakeNet, png_bytes


def solid_png(w, h):
    buf = io.BytesIO()
    Image.new("L", (w, h), 128).save(buf, "PNG")          # one grey channel: a 3840 x 4767 file stays cheap
    return buf.getvalue()


def jpeg_bytes(w, h, orientation=None):
    buf = io.BytesIO()
    im = Image.new("RGB", (w, h), (120, 90, 60))
    if orientation is None:
        im.save(buf, "JPEG")
    else:
        exif = Image.Exif()
        exif[0x0112] = orientation
        im.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def widths_asked(urls):
    out = []
    for u in urls:
        out += [int(v) for v in parse_qs(urlparse(u).query).get("iiurlwidth", [])]
    return out


# ---------------------------------------------------------------- the incident: a large Commons painting
SCREAM = "File:Edvard Munch - The Scream - Google Art Project.jpg"
SCREAM_URL = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Scream.jpg"


def scream_page(w=6703, h=8322, size=30_000_000):
    return {"pageid": 7, "index": 1, "title": SCREAM, "imageinfo": [{
        "url": SCREAM_URL, "descriptionurl": "https://commons.wikimedia.org/wiki/" + SCREAM.replace(" ", "_"),
        "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Scream.jpg/330px-Scream.jpg",
        "width": w, "height": h, "size": size, "mime": "image/jpeg",
        "extmetadata": {"LicenseShortName": {"value": "Public domain"}, "Artist": {"value": "Edvard Munch"},
                        "ObjectName": {"value": "The Scream"}, "DateTimeOriginal": {"value": "1893"}}}]}


def test_large_commons_original_is_stored_as_a_standard_rendition_and_recorded_with_its_own_pixels(monkeypatch, tmp_path):
    rendition = {"query": {"pages": [{"title": SCREAM, "imageinfo": [{
        "url": SCREAM_URL, "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Scream.jpg/3840px-Scream.jpg",
        "thumbwidth": 3840, "thumbheight": 4767, "width": 6703, "height": 8322}]}]}}
    net = FakeNet([("iiurlwidth=3840", rendition),
                   ("iiurlwidth=330", {"query": {"pages": [scream_page()]}}),
                   ("3840px-Scream.jpg", solid_png(3840, 4767))])
    monkeypatch.setitem(api._SOURCES, "commons", CommonsSource(opener=net, sleep=lambda s: None))
    proj = tmp_path / "scream"

    res = api.import_candidate(proj, "commons", SCREAM)
    a = res["asset"]

    assert (a["width"], a["height"]) == (3840, 4767)                       # what is on disk, not what Commons says
    assert (a["original_width"], a["original_height"]) == (6703, 8322)     # what the source offers, kept apart
    assert Image.open(proj / a["file"]).size == (3840, 4767)
    assert net.urls[-1].endswith("3840px-Scream.jpg")                      # the rendition was downloaded, not the original
    assert SCREAM_URL not in net.urls
    asked = widths_asked(net.urls)
    assert asked and all(w in THUMB_STEPS for w in asked), asked           # never a width Wikimedia does not serve
    assert assets.reconcile_sizes({res["asset_key"]: dict(a)}, proj) == []    # the record agrees with the file: nothing to repair


def test_commons_original_that_is_not_scaled_keeps_its_size(monkeypatch, tmp_path):
    page = scream_page(w=1300, h=1250, size=500_000)
    net = FakeNet([("iiurlwidth=330", {"query": {"pages": [page]}}), ("Scream.jpg", solid_png(1300, 1250))])
    monkeypatch.setitem(api._SOURCES, "commons", CommonsSource(opener=net, sleep=lambda s: None))
    a = api.import_candidate(tmp_path / "p", "commons", SCREAM)["asset"]
    assert (a["width"], a["height"]) == (1300, 1250) and (a["original_width"], a["original_height"]) == (1300, 1250)
    assert widths_asked(net.urls) == [330]


# ---------------------------------------------------------------- every other source
def test_pexels_photo_without_an_original_url_is_measured(monkeypatch, tmp_path):
    photo = {"id": 77, "width": 6000, "height": 4000, "url": "https://www.pexels.com/photo/77/", "photographer": "Jo",
             "alt": "Rocks", "src": {"large2x": "https://images.pexels.com/photos/77/large2x.jpeg"}}
    net = FakeNet([("images.pexels.com", png_bytes(940, 627)), ("/photos/77", photo)])      # the picture's own address also holds "/photos/77"
    monkeypatch.setitem(api._SOURCES, "pexels", PexelsSource(key="test-key", opener=net, sleep=lambda s: None))
    a = api.import_candidate(tmp_path / "p", "pexels", "77")["asset"]
    assert (a["width"], a["height"]) == (940, 627) and (a["original_width"], a["original_height"]) == (6000, 4000)


def test_pixabay_large_image_is_measured(monkeypatch, tmp_path):
    hit = {"id": 5, "tags": "mountain, lake", "user": "Ann", "imageWidth": 5472, "imageHeight": 3648, "imageSize": 9_000_000,
           "largeImageURL": "https://pixabay.com/get/large_5.jpg", "pageURL": "https://pixabay.com/photos/5/"}
    net = FakeNet([("pixabay.com/api/", {"hits": [hit]}), ("pixabay.com/get/", png_bytes(640, 427))])
    monkeypatch.setitem(api._SOURCES, "pixabay", PixabaySource(key="test-key", opener=net, sleep=lambda s: None))
    a = api.import_candidate(tmp_path / "p", "pixabay", "5")["asset"]
    assert (a["width"], a["height"]) == (640, 427) and (a["original_width"], a["original_height"]) == (5472, 3648)


def test_met_image_whose_api_size_is_unknown_is_measured(monkeypatch, tmp_path):
    from bti.media.sources.met import MetSource
    obj = {"objectID": 9, "title": "Wheat", "artistDisplayName": "V", "objectDate": "1889", "isPublicDomain": True,
           "primaryImage": "https://images.metmuseum.org/9.jpg", "objectURL": "https://www.metmuseum.org/art/9"}
    net = FakeNet([("/objects/9", obj), ("images.metmuseum.org", png_bytes(500, 400))])
    monkeypatch.setitem(api._SOURCES, "met", MetSource(opener=net, sleep=lambda s: None))
    a = api.import_candidate(tmp_path / "p", "met", "9")["asset"]
    assert (a["width"], a["height"]) == (500, 400) and "original_width" not in a     # the Met reports no pixels: nothing to keep


def test_osm_map_is_measured_not_trusted(monkeypatch, tmp_path):
    cache = tmp_path / "osmcache"
    cache.mkdir()
    (cache / "555_z12.jpg").write_bytes(jpeg_bytes(300, 169))                # what the cache holds is not 2400 x 1350
    monkeypatch.setitem(api._SOURCES, "osm", OsmSource(opener=FakeNet([]), sleep=lambda s: None, cache_dir=cache))
    a = api.import_candidate(tmp_path / "p", "osm", "555:12")["asset"]
    assert (a["width"], a["height"]) == (300, 169) and (a["original_width"], a["original_height"]) == (2400, 1350)


def test_book_image_is_measured(monkeypatch, tmp_path):
    monkeypatch.setitem(api._SOURCES, "book", BookPageSource(renderer=lambda b, k, r, dest: dest.write_bytes(png_bytes(400, 300))))
    a = api.import_candidate(tmp_path / "p", "book", "payne_gae/img/850")["asset"]
    assert (a["width"], a["height"]) == (400, 300) and "original_width" not in a


def test_upload_is_measured(tmp_path):
    f = tmp_path / "scan.png"
    f.write_bytes(png_bytes(64, 32))
    a = api.add_upload(tmp_path / "p", f, {"title": "Scan"})["asset"]
    assert (a["width"], a["height"]) == (64, 32) and "original_width" not in a


def test_upload_of_a_photo_turned_by_its_exif_tag_is_recorded_as_drawn(tmp_path):
    """OpenCV (the engine) and the browser (the page) both turn a JPEG with EXIF orientation 6 a quarter turn: 60 x 40 is drawn 40 x 60."""
    f = tmp_path / "phone.jpg"
    f.write_bytes(jpeg_bytes(60, 40, orientation=6))
    a = api.add_upload(tmp_path / "p", f, {"title": "Phone"})["asset"]
    assert (a["width"], a["height"]) == (40, 60)


def test_drawn_size_of_the_files_the_engine_reads(tmp_path):
    cases = {"a.png": (png_bytes(64, 32), (64, 32)), "b.jpg": (jpeg_bytes(60, 40), (60, 40)),
             "c.jpg": (jpeg_bytes(60, 40, 1), (60, 40)), "d.jpg": (jpeg_bytes(60, 40, 8), (40, 60)),
             "e.jpg": (jpeg_bytes(60, 40, 3), (60, 40)), "f.jpg": (jpeg_bytes(60, 40, 5), (40, 60))}
    for name, (data, want) in cases.items():
        (tmp_path / name).write_bytes(data)
        assert drawn_size(tmp_path / name) == want, name
    (tmp_path / "bad.jpg").write_bytes(b"not an image")
    assert drawn_size(tmp_path / "bad.jpg") == (0, 0) and drawn_size(tmp_path / "missing.png") == (0, 0)


def test_drawn_size_is_what_the_engine_really_draws(tmp_path):
    cv2 = pytest.importorskip("cv2")
    for orientation in (1, 6, 8):
        f = tmp_path / f"o{orientation}.jpg"
        f.write_bytes(jpeg_bytes(60, 40, orientation))
        h, w = cv2.imread(str(f), cv2.IMREAD_COLOR).shape[:2]            # exactly what bti.engine.vfx.Img does
        assert drawn_size(f) == (w, h), orientation


def test_an_unreadable_stored_image_is_refused_not_recorded_with_a_guess(tmp_path, monkeypatch):
    from bti.media.imageinfo import ImageDamaged
    f = tmp_path / "x.png"
    f.write_bytes(b"junk")
    with pytest.raises(ImageDamaged):
        api.stored_image_size(f)


def test_video_import_records_the_stored_files_size_and_keeps_the_claim(monkeypatch, tmp_path):
    class Src:
        name = "vsrc"

        def fetch_meta(self, sid):
            return {"source": "vsrc", "source_id": sid, "title": "Clip", "kind": "video", "mime": "video/mp4",
                    "url": "https://example.com/v.mp4", "width": 3840, "height": 2160, "licence": "CC0"}

        def download(self, meta, dest, **kw):
            Path(dest).write_bytes(b"raw")
            return dest

        def credit(self, meta):
            return {"source": "vsrc", "source_url": "", "author": "", "licence": "CC0", "licence_url": ""}

    probed = []
    monkeypatch.setitem(api._SOURCES, "vsrc", Src())
    monkeypatch.setattr("bti.media.clips.normalize", lambda src, dest, **kw: Path(dest).write_bytes(b"norm"))
    monkeypatch.setattr("bti.media.api._probe_upload_video", lambda p: probed.append(Path(p).name) or {"width": 1920, "height": 1080, "duration": 5.0})
    a = api.import_candidate(tmp_path / "p", "vsrc", "v1")["asset"]
    assert (a["width"], a["height"]) == (1920, 1080) and (a["original_width"], a["original_height"]) == (3840, 2160)
    assert probed == [Path(a["file"]).name]                                 # the probe read the STORED file


def test_clip_import_measures_the_stored_copy(monkeypatch, tmp_path):
    def fake_dl(cmd, *, timeout=None):
        p = tmp_path / "cache" / "clips" / "src" / "aaaaaaaaaaa_sec_1.0_5.0.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"raw_content")
        from subprocess import CompletedProcess
        return CompletedProcess(cmd, 0, str(p) + "\n", "")

    probed = []
    monkeypatch.setattr(clips, "_ytdlp_cmd", lambda: ["yt-dlp"])
    monkeypatch.setattr(clips, "normalize", lambda raw, out: out.write_bytes(b"normalized_clip") or out)
    monkeypatch.setattr(clips, "probe_video", lambda p: probed.append(Path(p)) or {"width": 1280, "height": 720, "duration": 4.0})
    monkeypatch.setattr(clips, "contact_sheet", lambda v, out, **kw: out.write_bytes(b"sheet") or out)
    res = clips.import_clip(tmp_path, "https://www.youtube.com/watch?v=aaaaaaaaaaa", 1, 5,
                            info={"id": "aaaaaaaaaaa", "title": "Clip Title", "license": "Creative Commons Attribution", "channel": "Demo"},
                            strict_licence=False, runner=fake_dl)
    stored = tmp_path / res["asset"]["file"]
    assert stored.is_file() and probed == [stored]
    assert (res["asset"]["width"], res["asset"]["height"]) == (1280, 720)


# ---------------------------------------------------------------- an item imported before the rule
def test_import_again_of_an_item_with_a_wrong_recorded_size_repairs_the_record_without_a_request(monkeypatch, tmp_path):
    proj = tmp_path / "p"
    (proj / "media").mkdir(parents=True)
    (proj / "media" / "scream.jpg").write_bytes(solid_png(384, 477))
    old = {"file": "media/scream.jpg", "kind": "image", "title": "The Scream", "artist": "", "year": "1893",
           "width": 6703, "height": 8322, "credit": {"source": "commons", "flag": None}}
    (proj / "media" / "sources.json").write_text(json.dumps({"items": {f"commons:{SCREAM}": {"key": "scream", "asset": old}}}))
    net = FakeNet([])                                                   # any request would fail the test
    monkeypatch.setitem(api._SOURCES, "commons", CommonsSource(opener=net, sleep=lambda s: None))

    res = api.import_candidate(proj, "commons", SCREAM)

    assert net.urls == []
    assert (res["asset"]["width"], res["asset"]["height"]) == (384, 477)
    assert (res["asset"]["original_width"], res["asset"]["original_height"]) == (6703, 8322)
    saved = json.loads((proj / "media" / "sources.json").read_text())["items"][f"commons:{SCREAM}"]["asset"]
    assert (saved["width"], saved["height"]) == (384, 477)              # the index is right now too
    assert api.import_candidate(proj, "commons", SCREAM) == res          # and a second call changes nothing


# ---------------------------------------------------------------- the repair function itself
def _png(path, w, h):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(solid_png(w, h))


def _asset(w, h, regions=None, file="media/a.png", kind="image", **extra):
    return {"file": file, "kind": kind, "width": w, "height": h, "regions": regions if regions is not None else {}, **extra}


def test_reconcile_scales_the_regions_with_the_size(tmp_path):
    _png(tmp_path / "media" / "a.png", 400, 200)
    a = _asset(4000, 2000, {"EYE": {"x": 2000, "y": 1000, "rx": 400, "ry": 200, "label": "Eye"}, "EDGE": {"x": 4000, "y": 0}})
    assert assets.reconcile_sizes({"A": a}, tmp_path) == ["A"]
    assert (a["width"], a["height"]) == (400, 200) and (a["original_width"], a["original_height"]) == (4000, 2000)
    assert a["regions"]["EYE"] == {"x": 200, "y": 100, "rx": 40, "ry": 20, "label": "Eye"}
    assert a["regions"]["EDGE"] == {"x": 400, "y": 0}


def test_reconcile_scales_each_axis_with_its_own_factor(tmp_path):
    _png(tmp_path / "media" / "a.png", 500, 250)
    a = _asset(1000, 1000, {"R": {"x": 800, "y": 800, "rx": 100, "ry": 100}})
    assets.reconcile_sizes({"A": a}, tmp_path)
    assert a["regions"]["R"] == {"x": 400, "y": 200, "rx": 50, "ry": 25}


def test_reconcile_is_idempotent(tmp_path):
    _png(tmp_path / "media" / "a.png", 400, 200)
    a = _asset(4000, 2000, {"R": {"x": 2001, "y": 999, "rx": 7, "label": ""}})
    assets.reconcile_sizes({"A": a}, tmp_path)
    once = json.dumps(a, sort_keys=True)
    assert assets.reconcile_sizes({"A": a}, tmp_path) == [] and json.dumps(a, sort_keys=True) == once


def test_reconcile_leaves_alone_what_it_cannot_judge(tmp_path):
    _png(tmp_path / "media" / "ok.png", 100, 50)
    (tmp_path / "media" / "bad.png").write_bytes(b"junk")
    outside = tmp_path.parent / "outside.png"
    _png(outside, 10, 10)
    d = {"ok": _asset(100, 50, {"R": {"x": 5, "y": 5}}, file="media/ok.png"),
         "bad": _asset(999, 999, {"R": {"x": 5, "y": 5}}, file="media/bad.png"),
         "gone": _asset(999, 999, file="media/gone.png"),
         "video": _asset(1920, 1080, file="media/ok.png", kind="video"),
         "up": _asset(999, 999, file="../outside.png"),
         "abs": _asset(999, 999, file=str(outside)),
         "junk": "not a dict", "nofile": {"kind": "image", "width": 5, "height": 5}}
    before = json.dumps(d, sort_keys=True)
    assert assets.reconcile_sizes(d, tmp_path) == [] and json.dumps(d, sort_keys=True) == before


def test_reconcile_fills_a_missing_size_and_does_not_guess_the_region_space(tmp_path):
    _png(tmp_path / "media" / "a.png", 300, 200)
    a = _asset(0, 0, {"R": {"x": 50, "y": 60}})
    assert assets.reconcile_sizes({"A": a}, tmp_path) == ["A"]
    assert (a["width"], a["height"]) == (300, 200) and a["regions"]["R"] == {"x": 50, "y": 60} and "original_width" not in a


def test_reconcile_keeps_an_original_size_that_is_already_recorded(tmp_path):
    _png(tmp_path / "media" / "a.png", 400, 200)
    a = _asset(4000, 2000, original_width=6703, original_height=8322)
    assets.reconcile_sizes({"A": a}, tmp_path)
    assert (a["original_width"], a["original_height"]) == (6703, 8322)


def test_reconcile_keeps_a_fractional_region_fractional(tmp_path):
    _png(tmp_path / "media" / "a.png", 400, 200)
    a = _asset(4000, 2000, {"R": {"x": 2000.5, "y": 1000.5}})
    assets.reconcile_sizes({"A": a}, tmp_path)
    assert a["regions"]["R"] == {"x": 200.05, "y": 100.05}


def test_the_size_of_a_file_is_read_again_when_the_file_changes(tmp_path):
    f = tmp_path / "media" / "a.png"
    _png(f, 40, 20)
    assert assets.stored_size(f) == (40, 20)
    _png(f, 80, 60)                                                     # same name, new pixels (and a new size on disk)
    assert assets.stored_size(f) == (80, 60)
