"""Worker panelbox (2026-11-20): the painted area of a picture in the picks document (`content_box` of an asset, `bti/media/contentbox.py`).

It is found by the program when a picture is imported or uploaded and when the picks are saved with that picture as the main painting; it is kept through every read and
write (`normalize`), scaled with the picture when the declared size was wrong, never changed by the owner's page save, and said so (`content_box_unsure`) when the program
was not sure. A document of a picture with no ground band is read and written exactly as before. Made-up pictures (Pillow) and a fake media facade: no network."""
import copy
import json
import random

import pytest
from PIL import Image

from bti.media import contentbox as CB
from bti.picks import doc, service
from bti.picks.errors import PicksError

PANEL = (50, 60, 550, 740)


def picture(path, panel=PANEL, size=(600, 800), ring=True):
    rnd = random.Random(4)
    im = Image.new("RGB", size, (0, 0, 0) if ring else (90, 90, 90))
    x0, y0, x1, y1 = panel if ring else (0, 0, size[0], size[1])
    im.paste(Image.frombytes("RGB", (x1 - x0, y1 - y0), bytes(rnd.randint(70, 190) for _ in range((x1 - x0) * (y1 - y0) * 3))), (x0, y0))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


def asset(file="media/a.png", w=600, h=800, **kw):
    return {"file": file, "kind": "image", "title": "A", "artist": "", "year": "", "width": w, "height": h,
            "credit": {"source": "commons", "source_url": "u", "author": "x", "licence": "PD", "licence_url": "", "flag": None}, "regions": {}, **kw}


def write(pdir, assets, main="A"):
    raw = {"schema": doc.SCHEMA, "main_asset": main, "assets": assets, "beats": {}, "approval": {"approved": False, "sha1": None, "approved_at": None}}
    (pdir / "picks.json").write_text(json.dumps(raw), encoding="utf-8")
    return raw


# ----------------------------------------------------------------------------------------------------------------- the document
def test_normalize_keeps_a_usable_box_in_whole_pixels_and_drops_the_rest():
    d = doc.normalize({"main_asset": "A", "assets": {
        "A": asset(content_box={"x0": 50.4, "y0": 60, "x1": 550, "y1": 740.6, "how": "found"}),
        "B": asset(content_box={"x0": 10, "y0": 10, "x1": 5, "y1": 40, "how": "found"}),
        "C": asset(content_box={"x0": 1, "y0": 2, "x1": 30, "y1": 40}),
        "D": asset(content_box={"x0": 1, "y0": 2, "x1": 30, "y1": 40, "how": "unsure", "note": "one_side"}),
        "V": {**asset(file="media/v.mp4"), "kind": "video", "content_box": {"x0": 0, "y0": 0, "x1": 5, "y1": 5, "how": "found"}}}})
    assert d["assets"]["A"]["content_box"] == {"x0": 50, "y0": 60, "x1": 550, "y1": 741, "how": "found"}
    assert "content_box" not in d["assets"]["B"], "upside down"
    assert d["assets"]["C"]["content_box"]["how"] == "set", "a hand-written box with no `how` is a person's"
    assert d["assets"]["D"]["content_box"]["note"] == "one_side"
    assert "content_box" not in d["assets"]["V"], "a video has no painted area"


def test_a_document_without_a_box_keeps_its_revision():
    raw = {"main_asset": "A", "assets": {"A": asset()}, "beats": {}}
    assert "content_box" not in doc.normalize(raw)["assets"]["A"]
    with_box = copy.deepcopy(raw)
    with_box["assets"]["A"]["content_box"] = {"x0": 0, "y0": 0, "x1": 600, "y1": 700, "how": "set"}
    assert doc.revision(doc.normalize(with_box)) != doc.revision(doc.normalize(raw))


def test_a_client_document_with_a_box_that_is_not_a_box_is_refused():
    d = {"main_asset": "A", "assets": {"A": asset(content_box={"x0": 9, "y0": 0, "x1": 1, "y1": 5})}, "beats": {}}
    assert "content_box" in doc.doc_problem(d)
    d["assets"]["A"]["content_box"] = {"x0": 0, "y0": 0, "x1": 5, "y1": 5}
    assert doc.doc_problem(d) is None
    d["assets"]["A"]["content_box"] = None
    assert doc.doc_problem(d) is None


def test_the_box_scales_with_its_picture_when_the_declared_size_was_wrong(proj):
    picture(proj / "media" / "a.png")
    write(proj, {"A": asset(w=300, h=400, content_box={"x0": 25, "y0": 30, "x1": 275, "y1": 370, "how": "found"}, regions={"R": {"x": 150, "y": 200, "rx": 20, "ry": 20, "label": "r"}})})
    a = doc.load(proj)["assets"]["A"]
    assert (a["width"], a["height"]) == (600, 800)
    assert a["content_box"] == {"x0": 50, "y0": 60, "x1": 550, "y1": 740, "how": "found"} and a["regions"]["R"]["x"] == 300


# ----------------------------------------------------------------------------------------------------------------- the main painting
def test_save_gives_the_main_painting_the_finding_of_its_file(proj):
    picture(proj / "media" / "a.png")
    write(proj, {"A": asset()})
    before = doc.load(proj)
    assert "content_box" not in before["assets"]["A"], "reading never writes or finds"
    with doc.Held(proj):
        doc.save(proj, before)
    a = json.loads((proj / "picks.json").read_text(encoding="utf-8"))["assets"]["A"]
    assert a["content_box"]["how"] == "found" and all(abs(a["content_box"][k] - v) <= 4 for k, v in zip(CB.FIELDS, PANEL)), a["content_box"]
    assert doc.load(proj)["assets"]["A"]["content_box"] == a["content_box"]


def test_a_main_painting_with_no_ground_is_saved_exactly_as_before(proj):
    picture(proj / "media" / "a.png", ring=False)
    write(proj, {"A": asset()})
    d = doc.load(proj)
    with doc.Held(proj):
        rev = doc.save(proj, d)
    assert rev == doc.revision(d) and "content_box" not in json.loads((proj / "picks.json").read_text(encoding="utf-8"))["assets"]["A"]


def test_only_the_main_painting_is_found_on_a_save_and_a_box_that_is_there_is_never_replaced(proj):
    picture(proj / "media" / "a.png")
    picture(proj / "media" / "b.png")
    mine = {"x0": 10, "y0": 10, "x1": 590, "y1": 790, "how": "set"}
    write(proj, {"A": asset(content_box=mine), "B": asset(file="media/b.png")})
    d = doc.load(proj)
    with doc.Held(proj):
        doc.save(proj, d)
    saved = json.loads((proj / "picks.json").read_text(encoding="utf-8"))["assets"]
    assert saved["A"]["content_box"] == mine and "content_box" not in saved["B"]
    d["main_asset"] = "B"
    with doc.Held(proj):
        doc.save(proj, d)
    saved = json.loads((proj / "picks.json").read_text(encoding="utf-8"))["assets"]
    assert saved["B"]["content_box"]["how"] == "found", "made the main painting: found"


def test_a_main_painting_whose_file_cannot_be_read_is_saved_without_a_box(proj):
    (proj / "media").mkdir(exist_ok=True)
    (proj / "media" / "a.png").write_bytes(b"not a picture")
    write(proj, {"A": asset()})
    d = doc.load(proj)
    with doc.Held(proj):
        doc.save(proj, d)
    assert "content_box" not in json.loads((proj / "picks.json").read_text(encoding="utf-8"))["assets"]["A"]


def test_the_owners_page_save_cannot_change_the_box(proj):
    picture(proj / "media" / "a.png")
    mine = {"x0": 10, "y0": 10, "x1": 590, "y1": 790, "how": "set"}
    write(proj, {"A": asset(content_box=mine)})
    d = doc.load(proj)
    sent = copy.deepcopy(d)
    sent["assets"]["A"]["content_box"] = {"x0": 0, "y0": 0, "x1": 5, "y1": 5, "how": "set"}
    sent["assets"]["A"]["title"] = "New title"
    service.put(proj, sent, doc.revision(d))
    saved = doc.load(proj)["assets"]["A"]
    assert saved["content_box"] == mine and saved["title"] == "New title"


def test_an_unsure_finding_is_a_warning_on_the_main_painting_only(proj):
    unsure = {"x0": 0, "y0": 0, "x1": 600, "y1": 800, "how": "unsure", "note": "one_side"}
    d = doc.normalize({"main_asset": "A", "assets": {"A": asset(content_box=unsure), "B": asset(content_box=unsure)}, "beats": {}})
    rows = [i for i in doc.issues(d) if i["code"] == "content_box_unsure"]
    assert len(rows) == 1 and rows[0]["level"] == "warning" and rows[0]["asset"] == "A" and "one edge only" in rows[0]["message"]
    d["main_asset"] = "B"
    assert [i["asset"] for i in doc.issues(d) if i["code"] == "content_box_unsure"] == ["B"]
    d["assets"]["B"]["content_box"] = {**unsure, "how": "found", "note": None}
    assert not [i for i in doc.issues(d) if i["code"] == "content_box_unsure"]


def test_the_warning_does_not_stop_the_automatic_run():
    from bti.auto_run import checks
    row = {"level": "warning", "code": "content_box_unsure", "message": "x", "asset": "A"}
    assert checks.vet("picks", [row])[0] == "ok"


# ----------------------------------------------------------------------------------------------------------------- a picture comes in
class FakeMedia:
    """The media facade of a test: hands back the asset of a picture it has already put in the project's media folder."""

    def __init__(self, pdir, make):
        self.pdir, self.make, self.calls = pdir, make, 0

    def import_candidate(self, pdir, source, source_id, *, require_root=False):
        self.calls += 1
        return {"asset_key": "K", "asset": self.make()}

    def add_upload(self, pdir, file_path, meta, *, require_root=False):
        self.calls += 1
        return {"asset_key": "K", "asset": self.make()}


def test_a_picture_that_is_imported_gets_its_box_before_it_is_added_to_the_picks(proj, monkeypatch):
    picture(proj / "media" / "k.png")
    monkeypatch.setattr(service, "_media", FakeMedia(proj, lambda: asset(file="media/k.png")))
    res = service.import_asset(proj, "commons", "File:K.jpg")
    assert res["asset"]["content_box"]["how"] == "found"
    assert doc.load(proj)["assets"]["K"]["content_box"]["how"] == "found"
    assert service.fetch_asset(proj, "commons", "File:K.jpg")["asset"]["content_box"]["how"] == "found", "the operations fetch the same way"


def test_a_picture_with_no_ground_comes_in_with_no_box_and_a_video_or_a_broken_file_is_not_refused(proj, monkeypatch):
    picture(proj / "media" / "k.png", ring=False)
    monkeypatch.setattr(service, "_media", FakeMedia(proj, lambda: asset(file="media/k.png")))
    assert "content_box" not in service.import_asset(proj, "commons", "File:K.jpg")["asset"]
    (proj / "media" / "bad.png").write_bytes(b"x")
    monkeypatch.setattr(service, "_media", FakeMedia(proj, lambda: asset(file="media/bad.png")))
    assert "content_box" not in service.fetch_asset(proj, "commons", "File:Bad.jpg")["asset"]
    monkeypatch.setattr(service, "_media", FakeMedia(proj, lambda: {**asset(file="media/k.png"), "kind": "video"}))
    assert "content_box" not in service.fetch_asset(proj, "commons", "File:V.mp4")["asset"]


def test_an_upload_gets_its_box_too(proj, monkeypatch):
    picture(proj / "media" / "k.png")
    monkeypatch.setattr(service, "_media", FakeMedia(proj, lambda: asset(file="media/k.png")))
    res = service.upload(proj, proj / "media" / "k.png", {})
    assert res["asset"]["content_box"]["how"] == "found"
