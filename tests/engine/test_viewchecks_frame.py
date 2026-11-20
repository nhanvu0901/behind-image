"""Worker panelbox (2026-11-20): the check `frame_off_painting` of `bti/engine/viewchecks.py`: a camera key of a shot on the main painting shows more than 1% of its frame
outside the painted area of the picture (`content_box`, `bti/media/contentbox.py`), unless the frame holds the whole painting. Made-up storyboards (the real ones are in
`test_catalogue_real.py`)."""
from __future__ import annotations

import json

import pytest
from PIL import Image

from conftest import words as make_words

import bti.engine.api  # noqa: F401  (registers the techniques)
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import viewchecks as VC
from bti.engine.timing import Timing

BUNDLE = R.load_bundle("gae")
W, H = 3469, 4000
BOX = {"x0": 100, "y0": 106, "x1": 3363, "y1": 3900, "how": "found"}          # the painted area of the Met's goldsmith


def cam(*poses):
    n = len(poses)
    return [{"at": {"rel": round(i / (n - 1), 4)}, "cx": p[0], "cy": p[1], "zoom": p[2], "ease": "linear"} for i, p in enumerate(poses)]


def shot(i, t, camera, asset="A", tech="CAM-05", locked=False):
    return {"id": "s%d" % i, "start": {"t": t}, "technique": tech, "intent": "explore", "slots": {"image": {"asset": asset}},
            "params": {"camera": camera} if camera is not None else {}, "transition_in": None, "overlays": [], "locked": locked, "source": "agent", "note": ""}


def asset(w=W, h=H, box=BOX, file="media/a.jpg"):
    a = {"file": file, "kind": "image", "title": "A Goldsmith in His Shop", "artist": "Petrus Christus", "year": "1449", "width": w, "height": h, "regions": {}}
    if box is not None:
        a["content_box"] = dict(box)
    return a


def make(tmp_path, shots, *, a=None, picks=None, picture=None, end=60.0):
    d = tmp_path / "proj"
    (d / "media").mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 96), (120, 120, 120)).save(d / "media" / "a.jpg")
    Image.new("RGB", (64, 96), (120, 120, 120)).save(d / "media" / "b.jpg")
    if picture is not None:
        picture.save(d / "media" / "a.jpg")
    if picks is not None:
        (d / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    doc = {"schema": "bti.storyboard/1", "project": "proj", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
           "assets": {"A": a or asset(), "B": {**asset(900, 700, None), "file": "media/b.jpg"}}, "shots": shots, "end": {"t": end}, "approvals": {"storyboard": None}}
    return doc, Timing({"duration": end, "words": make_words(120, step=end / 120)}), d


def flagged(doc, tm, d):
    return [i for i in SB.validate(doc, tm, BUNDLE, d) if i["code"] == "frame_off_painting"]


INSIDE = cam((1700, 2000, 1.0), (1700, 2200, 1.3))
MIRROR = cam((2930, 2716, 1.8), (3000, 2716, 2.1))                 # the close-up of the mirror, past the right edge of the painted area
WHOLE = cam((1731.5, 2003, 0.2688), (1731.5, 2003, 0.2768))       # the opening shot: the whole painting at 95.5% of the height, pushed in by 3%
FULL_WIDTH_OF_THE_FILE = cam((1734.5, 1500, 1920 / 3469), (1734.5, 2500, 1920 / 3469))


def test_a_camera_inside_the_painted_area_and_a_pull_back_are_not_flagged(tmp_path):
    doc, tm, d = make(tmp_path, [shot(1, 0.0, INSIDE), shot(2, 10.0, WHOLE)])
    assert flagged(doc, tm, d) == []


def test_the_close_up_past_the_edge_is_flagged_with_the_key_the_share_and_what_to_do(tmp_path):
    doc, tm, d = make(tmp_path, [shot(1, 0.0, INSIDE), shot(2, 10.0, MIRROR)])
    (i,) = flagged(doc, tm, d)
    assert i["level"] == "warn" and i["path"] == "shots[1].params.camera[1]"
    a = i["args"]
    assert a["shot"] == "s2" and a["asset"] == "A" and a["key"] == 1 and a["limit"] == 0.01 and a["box"] == [100, 106, 3363, 3900]
    assert 0.10 < a["share"] < 0.11 and a["zoom"] == 2.1
    assert "main painting" in i["message"] and "x 100 to 3363" in i["message"] and i["hint"] in i["message"] and i["hint"] == VC.HINTS["frame_off_painting"]


def test_the_framing_at_the_full_width_of_the_file_shows_the_ground_at_both_sides_and_is_flagged(tmp_path):
    doc, tm, d = make(tmp_path, [shot(1, 0.0, FULL_WIDTH_OF_THE_FILE)])
    (i,) = flagged(doc, tm, d)
    assert i["args"]["share"] == pytest.approx(0.059, abs=0.001)


def test_the_worst_key_of_a_shot_is_the_one_reported_and_a_shot_is_reported_once(tmp_path):
    doc, tm, d = make(tmp_path, [shot(1, 0.0, cam((3000, 2716, 2.1), (1700, 2000, 1.0), (3100, 2716, 2.5)))])
    (i,) = flagged(doc, tm, d)
    assert i["args"]["key"] == 2 and i["path"].endswith("camera[2]")


def test_only_a_shot_on_the_main_painting_is_judged(tmp_path):
    other = {"A": asset(), "B": {**asset(900, 700, {"x0": 100, "y0": 100, "x1": 800, "y1": 600, "how": "found"}), "file": "media/b.jpg"}}
    doc, tm, d = make(tmp_path, [shot(1, 0.0, INSIDE), shot(2, 10.0, cam((850, 350, 3.0), (860, 350, 3.0)), asset="B")], picks={"main_asset": "A", "assets": {}, "beats": {}})
    doc["assets"] = other
    assert flagged(doc, tm, d) == [], "a picture that is not the main painting has no frame to keep"


def test_the_main_painting_is_the_one_of_the_picks_else_the_picture_on_screen_the_longest(tmp_path):
    doc, tm, d = make(tmp_path, [shot(1, 0.0, MIRROR)], picks={"main_asset": "B", "assets": {}, "beats": {}})
    assert flagged(doc, tm, d) == [], "the picks say the main painting is B: A is just a picture"
    doc, tm, d = make(tmp_path / "x", [shot(1, 0.0, MIRROR)])
    assert [i["args"]["shot"] for i in flagged(doc, tm, d)] == ["s1"], "no picks: A is on screen the longest"


def test_a_locked_shot_is_judged_like_any_other_and_a_shot_with_no_camera_or_a_broken_one_is_ignored(tmp_path):
    broken = [{"at": {"rel": 0.0}, "cx": "x", "cy": 1, "zoom": 1.0}, {"at": {"rel": 1.0}, "cx": 2000, "cy": 2000, "zoom": -3}]
    doc, tm, d = make(tmp_path, [shot(1, 0.0, MIRROR, locked=True), shot(2, 10.0, None, tech="STATIC-01"), shot(3, 20.0, broken)])
    assert [i["args"]["shot"] for i in flagged(doc, tm, d)] == ["s1"]


def test_with_no_box_anywhere_nothing_is_said_a_picture_without_one_is_the_whole_picture(tmp_path):
    doc, tm, d = make(tmp_path, [shot(1, 0.0, MIRROR)], a=asset(box=None))
    assert flagged(doc, tm, d) == [], "the stub file is not of the declared size: no finding, so no box"
    doc, tm, d = make(tmp_path / "y", [shot(1, 0.0, cam((1734.5, 2000, 2.0), (1734.5, 2000, 2.2)))], a=asset(box={"x0": 0, "y0": 0, "x1": W, "y1": H, "how": "set"}))
    assert flagged(doc, tm, d) == [], "a frame inside the whole picture"


def ringed_picture(w=600, h=800, box=(50, 60, 550, 740)):
    import random
    rnd = random.Random(2)
    im = Image.new("RGB", (w, h), (0, 0, 0))
    im.paste(Image.frombytes("RGB", (box[2] - box[0], box[3] - box[1]), bytes(rnd.randint(70, 190) for _ in range((box[2] - box[0]) * (box[3] - box[1]) * 3))), (box[0], box[1]))
    return im


def test_a_picture_with_no_stored_box_gets_the_finding_of_its_file_when_the_project_folder_is_known(tmp_path):
    """A storyboard made before the box existed (the finished videos): the check reads the picture, as the program did when it made the box."""
    a = asset(600, 800, box=None)
    shots = [shot(1, 0.0, cam((300, 400, 4.0), (540, 400, 4.0)))]                        # at the end the frame ends at 540 + 240 = 780, far past 550
    doc, tm, d = make(tmp_path, shots, a=a, picture=ringed_picture())
    (i,) = flagged(doc, tm, d)
    assert 40 <= i["args"]["box"][0] <= 60 and 540 <= i["args"]["box"][2] <= 560, i["args"]          # a JPEG: the edge is a few pixels either way
    assert [x for x in SB.validate(doc, tm, BUNDLE, None) if x["code"] == "frame_off_painting"] == [], "no project folder: no file to read, no box"


def test_a_box_that_a_person_set_wins_over_the_finding(tmp_path):
    """The frame is 480 px wide at zoom 4 and ends at x = 590: inside a box set to the whole picture, 40 px past the 550 the program found."""
    frame = [shot(1, 0.0, cam((350, 400, 4.0), (350, 400, 4.0)))]
    set_box = asset(600, 800, box={"x0": 0, "y0": 0, "x1": 600, "y1": 800, "how": "set"})
    doc, tm, d = make(tmp_path, frame, a=set_box, picture=ringed_picture())
    assert flagged(doc, tm, d) == []
    doc, tm, d = make(tmp_path / "found", frame, a=asset(600, 800, box=None), picture=ringed_picture())
    (i,) = flagged(doc, tm, d)
    assert i["args"]["share"] == pytest.approx(40 / 480, abs=0.01)


def test_the_check_never_changes_the_other_issues_of_a_storyboard(tmp_path):
    doc, tm, d = make(tmp_path, [shot(1, 0.0, INSIDE), shot(2, 10.0, MIRROR)])
    mixed = SB.validate(doc, tm, BUNDLE, d)
    others = [i for i in mixed if i["code"] != "frame_off_painting"]
    doc2 = json.loads(json.dumps(doc))
    doc2["shots"][1]["params"]["camera"] = INSIDE
    assert [i for i in SB.validate(doc2, tm, BUNDLE, d)] == others


def test_the_code_is_in_the_engine_s_table_and_stops_the_automatic_gate():
    from bti.auto_run import checks as ARC
    assert "frame_off_painting" in VC.CODES and "frame_off_painting" in SB.ISSUE_CODES and "frame_off_painting" in VC.HINTS
    assert "(warning)" in VC.CODES["frame_off_painting"] and "args:" in VC.CODES["frame_off_painting"]
    assert "frame_off_painting" in ARC.STOPS["storyboard"] and "frame_off_painting" not in ARC.TOLERATED["storyboard"]
    stops = ARC.judge("storyboard", [{"level": "warn", "code": "frame_off_painting", "message": "x", "path": "shots[1]"}])["stopping"]
    assert len(stops) == 1 and stops[0]["why"] and stops[0]["why_vi"]
