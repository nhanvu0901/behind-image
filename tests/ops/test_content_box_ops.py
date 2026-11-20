"""Worker panelbox (2026-11-20): the operations `set_content_box` and `clear_content_box` of the picks document (the painted area of a picture, `bti/media/contentbox.py`),
and what the log and the undo make of a box that the program found by itself when a picture was made the main painting."""
import random

import pytest
from ops_helpers import FILES, PID, SIZES, paths, pk, pk_rev, picks, snapshot
from PIL import Image

from bti.media import contentbox as CB

B = "/api/projects/%s" % PID


def untouched(client, resp, before):
    assert resp.status_code >= 400
    assert snapshot(client.pdir) == before


def undo(client, batch):
    return client.post(B + "/changes/%s/undo" % batch, json={"base_rev": pk_rev(client), "actor": "human"})


def ring_picture_for(client, key, panel):
    """Picture `key` of the fixture project becomes a photograph on a black ground whose painted area is `panel` (noise inside, so that no line of it is uniform)."""
    w, h = SIZES[key]
    rnd = random.Random(7)
    im = Image.new("RGB", (w, h), (0, 0, 0))
    im.paste(Image.frombytes("RGB", (panel[2] - panel[0], panel[3] - panel[1]), bytes(rnd.randint(70, 190) for _ in range((panel[2] - panel[0]) * (panel[3] - panel[1]) * 3))), panel[:2])
    im.save(client.pdir / FILES[key])


# ---------------------------------------------------------------- set_content_box
def test_set_content_box_sets_the_box_as_a_persons_and_says_so_in_vietnamese(client):
    r = pk(client, [{"op": "set_content_box", "asset": "A", "x0": 40, "y0": 50, "x1": 1160, "y1": 1550}])
    assert r.status_code == 200, r.text
    assert picks(client)["assets"]["A"]["content_box"] == {"x0": 40, "y0": 50, "x1": 1160, "y1": 1550, "how": "set"}
    assert r.json()["changes"] == [{"target": {"asset": "A"}, "time": None, "what": "Vùng tranh của hình “Test portrait”: đã đặt"}]


def test_a_box_that_is_set_replaces_the_one_that_is_there_and_is_never_replaced_by_the_program(client):
    ring_picture_for(client, "A", (100, 120, 1100, 1500))
    assert pk(client, [{"op": "set_content_box", "asset": "A", "x0": 0, "y0": 0, "x1": 1200, "y1": 1600}]).status_code == 200
    assert pk(client, [{"op": "set_region", "asset": "A", "region": "EYE", "x": 600, "y": 500}]).status_code == 200      # a later save: the main painting is A
    assert picks(client)["assets"]["A"]["content_box"] == {"x0": 0, "y0": 0, "x1": 1200, "y1": 1600, "how": "set"}


@pytest.mark.parametrize("op,where", [
    ({"op": "set_content_box", "asset": "A", "x0": -5, "y0": 0, "x1": 100, "y1": 100}, ["ops[0].x0"]),
    ({"op": "set_content_box", "asset": "A", "x0": 0, "y0": 0, "x1": 1300, "y1": 100}, ["ops[0].x0"]),
    ({"op": "set_content_box", "asset": "A", "x0": 600, "y0": 0, "x1": 600, "y1": 100}, ["ops[0].x0"]),
    ({"op": "set_content_box", "asset": "A", "x0": 0, "y0": 0, "x1": 10, "y1": 1000}, ["ops[0].x0"]),
    ({"op": "set_content_box", "asset": "A", "x0": 0, "y0": 0, "x1": 1000}, ["ops[0].y1"]),
    ({"op": "set_content_box", "asset": "A", "x0": "0", "y0": 0, "x1": 1000, "y1": 1000}, ["ops[0].x0"]),
    ({"op": "set_content_box", "asset": "Z9", "x0": 0, "y0": 0, "x1": 1000, "y1": 1000}, ["ops[0].asset"]),
])
def test_set_content_box_wrong_fields(client, op, where):
    before = snapshot(client.pdir)
    r = pk(client, [op])
    assert r.status_code == 422 and paths(r) == where and r.json()["fix"] and r.json()["retry"] == "after_fix", r.text
    untouched(client, r, before)


def test_a_dry_run_checks_the_box_and_writes_nothing(client):
    before = snapshot(client.pdir)
    r = pk(client, [{"op": "set_content_box", "asset": "A", "x0": 40, "y0": 50, "x1": 1160, "y1": 1550}], dry_run=True)
    assert r.status_code == 200 and r.json()["dry_run"] is True and r.json()["changes"], r.text
    assert snapshot(client.pdir) == before


def test_a_box_cannot_be_set_in_a_scoped_batch_it_belongs_to_the_whole_document(client):
    r = pk(client, [{"op": "set_content_box", "asset": "A", "x0": 40, "y0": 50, "x1": 1160, "y1": 1550}], scope={"beats": ["b0001"]})
    assert r.status_code == 422 and r.json()["code"] == "out_of_scope"


def test_a_video_has_no_painted_area(client):
    from bti.picks import doc as pdoc
    d = pdoc.load(client.pdir)
    (client.pdir / "media" / "v_clip.mp4").write_bytes(b"not a real video")
    d["assets"]["V"] = {"file": "media/v_clip.mp4", "kind": "video", "title": "Clip", "artist": "", "year": "", "width": 640, "height": 360, "credit": {"flag": None}, "regions": {}, "duration": 5.0}
    pdoc.save(client.pdir, d)
    r = pk(client, [{"op": "set_content_box", "asset": "V", "x0": 0, "y0": 0, "x1": 640, "y1": 360}])
    assert r.status_code == 422 and paths(r) == ["ops[0].asset"]


# ---------------------------------------------------------------- clear_content_box
def test_clear_content_box_takes_the_box_away_and_the_program_finds_it_again_on_the_next_save_of_the_main_painting(client):
    ring_picture_for(client, "A", (100, 120, 1100, 1500))
    assert pk(client, [{"op": "set_content_box", "asset": "A", "x0": 0, "y0": 0, "x1": 1200, "y1": 1600}]).status_code == 200
    r = pk(client, [{"op": "clear_content_box", "asset": "A"}])
    assert r.status_code == 200, r.text
    assert r.json()["changes"][0]["what"] == "Vùng tranh của hình “Test portrait”: để chương trình tự tìm lại"
    cb = picks(client)["assets"]["A"]["content_box"]
    assert cb["how"] == "found" and all(abs(cb[k] - v) <= 12 for k, v in zip(CB.FIELDS, (100, 120, 1100, 1500))), cb


def test_clear_content_box_of_a_picture_that_is_not_the_main_one_leaves_none(client):
    assert pk(client, [{"op": "set_content_box", "asset": "B", "x0": 0, "y0": 0, "x1": 1600, "y1": 900}]).status_code == 200
    assert pk(client, [{"op": "clear_content_box", "asset": "B"}]).status_code == 200
    assert "content_box" not in picks(client)["assets"]["B"]


def test_clearing_what_is_not_there_changes_nothing_and_says_nothing(client):
    r = pk(client, [{"op": "clear_content_box", "asset": "B"}])
    assert r.status_code == 200 and r.json()["changes"] == [] and r.json()["batch"] is None


# ---------------------------------------------------------------- the log and the undo
def test_the_undo_of_a_set_gives_back_the_box_the_program_had_found(client):
    ring_picture_for(client, "A", (100, 120, 1100, 1500))
    assert pk(client, [{"op": "set_region", "asset": "A", "region": "EYE", "x": 600, "y": 500}]).status_code == 200            # A is the main painting: the save found its box
    found = picks(client)["assets"]["A"]["content_box"]
    assert found["how"] == "found"
    r = pk(client, [{"op": "set_content_box", "asset": "A", "x0": 0, "y0": 0, "x1": 1200, "y1": 1600}])
    batch = r.json()["batch"]
    assert picks(client)["assets"]["A"]["content_box"]["how"] == "set"
    u = undo(client, batch)
    assert u.status_code == 200, u.text
    assert picks(client)["assets"]["A"]["content_box"] == found


def test_making_a_picture_the_main_painting_finds_its_box_and_the_undo_of_that_gives_the_painting_back(client):
    ring_picture_for(client, "B", (80, 60, 1520, 940))
    assert "content_box" not in picks(client)["assets"]["B"]
    r = pk(client, [{"op": "set_main", "asset": "B"}])
    assert r.status_code == 200, r.text
    cb = picks(client)["assets"]["B"]["content_box"]
    assert cb["how"] == "found" and all(abs(cb[k] - v) <= 12 for k, v in zip(CB.FIELDS, (80, 60, 1520, 940))), cb
    u = undo(client, r.json()["batch"])
    assert u.status_code == 200, u.text
    d = picks(client)
    assert d["main_asset"] == "A" and "content_box" not in d["assets"]["B"]
