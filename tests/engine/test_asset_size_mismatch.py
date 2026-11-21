"""Worker sizefollow: an image asset recorded with a size that is not the size of its stored file gets the warning
`asset_size_mismatch` from `bti.engine.storyboard.validate`. Nothing is rewritten, nothing is an error, and a file that did not
change is not measured again. Fakes only: tiny images written into a temp folder."""
from __future__ import annotations

import copy

import cv2
import numpy as np

from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine.timing import Timing
from bti.media import assets as media_assets
from conftest import make_image

CODE = "asset_size_mismatch"


def mism(issues):
    return [i for i in issues if i.get("code") == CODE]


def wrong(project, key="A", w=1600, h=2400):
    sb = copy.deepcopy(project.storyboard())
    sb["assets"][key]["width"], sb["assets"][key]["height"] = w, h
    return sb


def test_the_code_is_documented_and_is_a_warning_with_its_args(tiny_project):
    assert CODE in SB.ISSUE_CODES
    got = mism(tiny_project.validate(wrong(tiny_project)))
    assert len(got) == 1
    i = got[0]
    assert i["level"] == "warn" and i["path"] == "assets.A"
    assert i["args"] == {"asset": "A", "width": 1600, "height": 2400, "stored_width": 800, "stored_height": 1200}
    assert "A" in i["message"] and "1600x2400" in i["message"] and "800x1200" in i["message"]
    assert i["code"] in SB.ISSUE_CODES and all(x["level"] != "error" for x in tiny_project.validate(wrong(tiny_project)))


def test_a_size_that_agrees_gives_no_warning(tiny_project):
    assert mism(tiny_project.validate()) == []                      # A is 800 x 1200 and so is its file, B is 900 x 700 and so is its file


def test_either_side_wrong_is_enough(tiny_project):
    assert len(mism(tiny_project.validate(wrong(tiny_project, w=800, h=1500)))) == 1
    assert len(mism(tiny_project.validate(wrong(tiny_project, w=801, h=1200)))) == 1


def test_only_the_asset_that_disagrees_is_named(tiny_project):
    sb = wrong(tiny_project, "B", 1800, 1400)
    got = mism(tiny_project.validate(sb))
    assert [i["args"]["asset"] for i in got] == ["B"] and got[0]["args"]["stored_width"] == 900


def test_a_missing_file_is_the_missing_file_error_and_nothing_else(tiny_project, tiny):
    sb = wrong(tiny_project)
    sb["assets"]["A"]["file"] = "media/none.jpg"
    got = tiny_project.validate(sb)
    assert "asset_file_missing" in [i["code"] for i in got if i["level"] == "error"]
    assert mism(got) == []


def test_an_unreadable_file_is_the_unreadable_error_and_nothing_else(tiny_project, tiny):
    (tiny / "media" / "a.jpg").write_bytes(b"not an image")
    got = tiny_project.validate(wrong(tiny_project))
    assert "asset_file_unreadable" in [i["code"] for i in got] and mism(got) == []


def test_without_a_project_folder_no_file_is_looked_at(tiny_project):
    sb = wrong(tiny_project)
    tm, bundle = Timing({"duration": 20.0, "words": []}), R.load_bundle("gae")
    assert mism(SB.validate(sb, tm, bundle)) == []
    assert mism(SB.validate(sb, tm, bundle, None)) == []
    assert len(mism(SB.validate(sb, tm, bundle, tiny_project.dir))) == 1      # the same document with a folder does warn


def test_an_asset_that_declares_no_size_is_not_a_mismatch(tiny_project):
    sb = copy.deepcopy(tiny_project.storyboard())
    del sb["assets"]["A"]["width"], sb["assets"]["A"]["height"]
    assert mism(tiny_project.validate(sb)) == []
    sb["assets"]["A"]["width"] = 0                                    # not a positive number: the existing `asset_size` error, not this
    got = tiny_project.validate(sb)
    assert mism(got) == [] and "asset_size" in [i["code"] for i in got]


def test_a_video_asset_is_never_compared(tiny_project, tiny):
    f = tiny / "media" / "v.avi"
    vw = cv2.VideoWriter(str(f), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (64, 48))
    for k in range(10):
        vw.write(np.full((48, 64, 3), k * 20, np.uint8))
    vw.release()
    sb = copy.deepcopy(tiny_project.storyboard())
    sb["assets"]["V"] = {"file": "media/v.avi", "kind": "video", "title": "Clip", "artist": "", "year": "", "width": 1920, "height": 1080,
                         "credit": {"source": "test", "source_url": "", "author": "x", "licence": "PD", "licence_url": ""}}
    got = tiny_project.validate(sb)
    assert mism(got) == []
    if f.is_file() and f.stat().st_size:                              # the writer of this machine made a clip: it must have read fine
        assert "asset_video_unreadable" not in [i["code"] for i in got]


def test_a_mask_is_compared_like_an_image(tiny_project, tiny):
    make_image(tiny / "media" / "m.png", 320, 200, 3)
    sb = copy.deepcopy(tiny_project.storyboard())
    sb["assets"]["M"] = {"file": "media/m.png", "kind": "mask", "title": "Mask", "artist": "", "year": "", "width": 640, "height": 400,
                         "credit": {"source": "test", "source_url": "", "author": "x", "licence": "PD", "licence_url": ""}}
    got = mism(tiny_project.validate(sb))
    assert [(i["args"]["asset"], i["args"]["stored_width"], i["args"]["stored_height"]) for i in got] == [("M", 320, 200)]
    sb["assets"]["M"].update(width=320, height=200)
    assert mism(tiny_project.validate(sb)) == []


def test_the_answer_follows_the_file_when_it_is_replaced(tiny_project, tiny):
    sb = wrong(tiny_project)
    assert len(mism(tiny_project.validate(sb))) == 1
    make_image(tiny / "media" / "a.jpg", 1600, 2400, 1)               # the picture is now the size the document says
    assert mism(tiny_project.validate(sb)) == []


def test_an_unchanged_file_is_not_measured_again(tiny_project, monkeypatch):
    sb = wrong(tiny_project)
    calls = []
    real = media_assets.drawn_size

    def counting(path):
        calls.append(str(path))
        return real(path)

    monkeypatch.setattr(media_assets, "drawn_size", counting)
    for _ in range(5):                                                # validation runs on every edit of the page
        assert len(mism(tiny_project.validate(sb))) == 1
    assert sorted(set(calls)) == sorted(calls) and len(calls) <= 2     # each of the two pictures is measured once, however often the page validates


def test_nothing_is_rewritten(tiny_project, tiny):
    sb = wrong(tiny_project)
    before = (tiny / "storyboard.json").read_bytes()
    tiny_project.validate(sb)
    assert (tiny / "storyboard.json").read_bytes() == before and sb["assets"]["A"]["width"] == 1600
