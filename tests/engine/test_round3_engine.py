"""Round 3, engine half: R3B-003 (wrong types inside a storyboard), R3B-009 (damaged media), R3B-010 (messages without raw text)."""
from __future__ import annotations

import copy
import json
import logging

import cv2
import numpy as np
import pytest

from bti.engine import storyboard as SB
from bti.engine.api import open_project
from bti.engine.errors import DataError, RenderError


# ----------------------------------------------------------------------------- R3B-003
MUTATIONS = [
    ("shots-string", lambda s: s.update(shots="no")),
    ("shots-number", lambda s: s.update(shots=5)),
    ("shots-dict", lambda s: s.update(shots={"a": 1})),
    ("shots-list-of-strings", lambda s: s.update(shots=["a"])),
    ("shot-null", lambda s: s["shots"].__setitem__(1, None)),
    ("shot-list", lambda s: s["shots"].__setitem__(1, [1])),
    ("overlays-string", lambda s: s["shots"][0].update(overlays="x")),
    ("overlays-number", lambda s: s["shots"][0].update(overlays=7)),
    ("overlay-string", lambda s: s["shots"][0].update(overlays=["x"])),
    ("params-string", lambda s: s["shots"][0].update(params="p")),
    ("params-list", lambda s: s["shots"][0].update(params=[1])),
    ("slots-string", lambda s: s["shots"][0].update(slots="x")),
    ("slot-value-string", lambda s: s["shots"][0]["slots"].update(image="A")),
    ("start-string", lambda s: s["shots"][0].update(start="0")),
    ("start-number", lambda s: s["shots"][1].update(start=3)),
    ("overlay-start-list", lambda s: s["shots"][0]["overlays"][0].update(start=[1])),
    ("overlay-params-string", lambda s: s["shots"][0]["overlays"][0].update(params="q")),
    ("transition-string", lambda s: s["shots"][2].update(transition_in="TR-01")),
    ("transition-params-string", lambda s: s["shots"][2]["transition_in"].update(params="x")),
    ("camera-key-at-string", lambda s: s["shots"][0]["params"]["camera"][0].update(at="0")),
    ("end-string", lambda s: s.update(end="19")),
    ("assets-string", lambda s: s.update(assets="x")),
    ("asset-string", lambda s: s["assets"].update(A="x")),
    ("regions-string", lambda s: s["assets"]["A"].update(regions="x")),
    ("canvas-string", lambda s: s.update(canvas="x")),
]


@pytest.mark.parametrize("label,mut", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_wrong_types_inside_are_a_data_error_never_an_attribute_error(tiny, label, mut):
    f = tiny / "storyboard.json"
    sb = json.loads(f.read_text())
    mut(sb)
    f.write_text(json.dumps(sb))
    with pytest.raises(DataError):                                  # the loader
        SB.load(tiny)
    with pytest.raises(DataError):                                  # `open_project` goes through the loader
        open_project(tiny)
    # every function that walks a document that is already in memory
    SB.canonical(sb)                                                # generic walkers never fail on a type
    SB.strip_derived(sb)
    from bti.engine.timing import Timing
    from bti.engine import registry as R
    tm, bundle = Timing({"duration": 20.0, "words": []}), R.load_bundle("gae")
    with pytest.raises(DataError):
        SB.resolve(sb, tm, bundle)
    issues = SB.validate(sb, tm, bundle, tiny)                      # validate never raises: it reports
    assert isinstance(issues, list)


def test_a_good_document_still_loads_and_resolves(tiny_project):
    assert tiny_project.resolve()["shots"][0]["_t0"] == 0.0


def test_draw_check_of_a_wrong_shaped_draft_is_an_issue_not_an_exception(tiny_project):
    sb = copy.deepcopy(tiny_project.storyboard())
    sb["shots"][0]["overlays"] = "x"
    out = tiny_project.draw_check(sb)
    assert out and out[0]["code"] == "undrawable"
    assert tiny_project.draw_check() == []                          # the saved document is untouched


# ----------------------------------------------------------------------------- R3B-009
def _codes(project, sb=None):
    return [(i["code"], i["args"].get("asset")) for i in project.validate(sb) if i["level"] == "error"]


def _jpeg_bytes(n=1):
    from PIL import Image
    import io
    rng = np.random.RandomState(3)
    im = Image.fromarray(rng.randint(0, 255, (600, 800, 3), dtype=np.uint8))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=90)
    return b.getvalue()


def test_intact_files_have_no_media_issue(tiny_project):
    assert _codes(tiny_project) == []


@pytest.mark.parametrize("damage,code", [
    ("truncated", "asset_file_truncated"),
    ("zero", "asset_file_unreadable"),
    ("garbage", "asset_file_unreadable"),
])
def test_a_damaged_image_is_an_error_with_its_asset(tiny, damage, code):
    f = tiny / "media" / "a.jpg"
    data = _jpeg_bytes()
    f.write_bytes({"truncated": data[: len(data) // 3], "zero": b"", "garbage": b"not an image at all" * 50}[damage])
    p = open_project(tiny)
    assert (code, "A") in _codes(p)


def test_a_damaged_mask_is_an_error(tiny):
    sb = json.loads((tiny / "storyboard.json").read_text())
    sb["assets"]["M"] = {"file": "media/m.png", "kind": "mask", "aligned_to": "A"}
    cv2.imwrite(str(tiny / "media" / "m.png"), np.full((100, 100), 255, np.uint8))
    (tiny / "storyboard.json").write_text(json.dumps(sb))
    p = open_project(tiny)
    assert _codes(p) == []
    data = (tiny / "media" / "m.png").read_bytes()
    (tiny / "media" / "m.png").write_bytes(data[: len(data) // 2])
    assert _codes(p) and _codes(p)[0][1] == "M" and _codes(p)[0][0] in ("asset_file_truncated", "asset_file_unreadable")   # a cut PNG has no end marker
    (tiny / "media" / "m.png").write_bytes(b"")
    assert ("asset_file_unreadable", "M") in _codes(p)


def test_a_video_that_cannot_be_opened_or_has_no_frame_is_an_error(tiny):
    sb = json.loads((tiny / "storyboard.json").read_text())
    sb["assets"]["V"] = {"file": "media/v.mp4", "kind": "video"}
    (tiny / "storyboard.json").write_text(json.dumps(sb))
    (tiny / "media" / "v.mp4").write_bytes(b"")
    p = open_project(tiny)
    assert ("asset_video_unreadable", "V") in _codes(p)
    (tiny / "media" / "v.mp4").write_bytes(b"garbage" * 100)
    assert ("asset_video_unreadable", "V") in _codes(p)
    w = cv2.VideoWriter(str(tiny / "media" / "v.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 5, (64, 48))
    if not w.isOpened():
        pytest.skip("no mp4 writer in this OpenCV build")
    for _ in range(5):
        w.write(np.zeros((48, 64, 3), np.uint8))
    w.release()
    assert _codes(p) == []


def test_the_media_check_is_cached_by_path_size_and_mtime(tiny, monkeypatch):
    p = open_project(tiny)
    calls = []
    real = SB._check_media
    monkeypatch.setattr(SB, "_check_media", lambda path, kind: calls.append(path) or real(path, kind))
    SB._MEDIA_OK.clear()
    p.validate()
    n = len(calls)
    assert n == 2                                   # one decode per image asset
    for _ in range(5):
        p.validate()
    assert len(calls) == n                          # nothing changed: nothing decoded again
    f = tiny / "media" / "a.jpg"
    f.write_bytes(f.read_bytes()[:-5000])
    assert ("asset_file_truncated", "A") in _codes(p)
    assert len(calls) == n + 1                      # only the changed file was looked at again


def test_every_new_code_is_documented():
    for c in ("asset_file_truncated", "asset_video_unreadable", "asset_file_unreadable"):
        assert c in SB.ISSUE_CODES


# ----------------------------------------------------------------------------- R3B-010
def _fail(project, t=1.5):
    with pytest.raises(RenderError) as e:
        project.frame_at(t, 160)
    return e.value


def test_message_of_a_zero_byte_image_is_one_sentence_without_the_server_path(tiny, caplog):
    (tiny / "media" / "a.jpg").write_bytes(b"")
    p = open_project(tiny)
    with caplog.at_level(logging.WARNING, logger="bti.engine"):
        e = _fail(p)
    assert str(tiny) not in e.message and "Error" not in e.message and "Exception" not in e.message
    assert "media/a.jpg" in e.message and "image" in e.message and "missing" not in e.message
    assert e.shot == "s1" and e.asset == "A" and e.__cause__ is not None
    assert any("render failed" in r.getMessage() and r.exc_info for r in caplog.records)       # the raw exception is in the log


def test_message_of_a_missing_file_says_missing(tiny):
    (tiny / "media" / "a.jpg").unlink()
    e = _fail(open_project(tiny))
    assert "missing" in e.message and str(tiny) not in e.message and "media/a.jpg" in e.message


def test_message_of_a_damaged_mask_and_video_names_the_right_kind_and_not_a_missing_file(tiny):
    for kind, fname in (("mask", "m.png"), ("video", "v.mp4")):
        sb = json.loads((tiny / "storyboard.json").read_text())
        sb["assets"]["X"] = {"file": "media/" + fname, "kind": kind, "aligned_to": "A"}
        (tiny / "media" / fname).write_bytes(b"junk")
        p = open_project(tiny)
        from bti.engine import helpers as H
        from bti.engine.base import Ctx
        from bti.engine import registry as R
        from bti.engine.timing import Timing
        ctx = Ctx(tiny, sb, Timing({"duration": 1.0, "words": []}), R.load_bundle("gae"))
        try:
            if kind == "mask":
                H._mask_img(ctx, "X")
            else:
                H.video_frame(ctx, "X", 0.0)
        except Exception as exc:        # noqa: BLE001
            from bti.engine.scene import render_error
            e = render_error(exc, {"id": "s1"}, "CAM-01", 0)
        else:
            pytest.fail("no error for a damaged %s" % kind)
        assert kind in e.message and fname in e.message and "missing" not in e.message
        assert str(tiny) not in e.message and "FileNotFoundError" not in e.message and "Assertion" not in e.message


def test_a_technique_failure_with_a_raw_exception_shows_no_exception_text(tiny_project, monkeypatch):
    from bti.engine import registry as R
    cls = R.RENDERERS["X-ANN-01"][0]

    def boom(self, *a, **k):
        raise ValueError("operands could not be broadcast together with shapes (520,0,3) /private/secret/x.jpg")
    monkeypatch.setattr(cls, "apply", boom)
    e = _fail(tiny_project)
    assert "broadcast" not in e.message and "/private" not in e.message and "ValueError" not in e.message
    assert e.technique == "X-ANN-01" and e.overlay == "o3" and isinstance(e.__cause__, ValueError)
