"""Engine side of the backend QA fixes: nothing that cannot be re-opened passes validation; wrong types give issues; an
incomplete item is a warning and renders as a placeholder or is skipped; one-line text; history is capped."""
import json
import shutil

import numpy as np
import pytest

from bti.engine import storyboard as SB
from bti.engine.errors import DataError
from bti.engine.timing import Timing
from conftest import base_storyboard
from test_validation import errors, find


@pytest.mark.parametrize("style", ["nope", "../x", "", 5, ["gae"]])
def test_unknown_style_is_an_error_not_an_exception(tiny_project, style):
    sb = base_storyboard()
    sb["style"] = style
    assert find(tiny_project.validate(sb), "style")


@pytest.mark.parametrize("value", ["../../x.json", "/etc/hosts", "missing.json", 5, "a\\b.json"])
def test_timing_path_must_be_a_readable_file_inside_the_project(tiny_project, value):
    sb = base_storyboard()
    sb["timing"] = value
    assert [i for i in errors(tiny_project.validate(sb)) if i["path"] == "timing"]


@pytest.mark.parametrize("value", ["../../../etc/hosts", "/etc/hosts", 5, ""])
def test_audio_path_must_stay_inside_the_project(tiny_project, value):
    sb = base_storyboard()
    sb["audio"] = value
    assert [i for i in errors(tiny_project.validate(sb)) if i["path"] == "audio"]


@pytest.mark.parametrize("file", ["/etc/hosts", "media/../../x.jpg", "../x.jpg", "media/nope.jpg"])
def test_asset_file_must_exist_inside_the_project(tiny_project, file):
    sb = base_storyboard()
    sb["assets"]["A"]["file"] = file
    assert find(errors(tiny_project.validate(sb)), "assets.A.file")


def test_junk_asset_file_is_an_error(tiny_project, tiny):
    (tiny / "media" / "junk.jpg").write_bytes(b"not an image")
    sb = base_storyboard()
    sb["assets"]["A"]["file"] = "media/junk.jpg"
    assert find(errors(tiny_project.validate(sb)), "assets.A.file", "readable image")


@pytest.mark.parametrize("mut", [lambda sb: sb["shots"][1].update(start={"t": "abc"}), lambda sb: sb.update(canvas="x"),
                                 lambda sb: sb["shots"][0].update(slots=[1]), lambda sb: sb["shots"][0].update(id=["x"]),
                                 lambda sb: sb["shots"][0].update(overlays=[7]), lambda sb: sb["shots"][0].update(technique={"a": 1}),
                                 lambda sb: sb.update(end={"t": 8, "fade_s": "x"}), lambda sb: sb["assets"]["A"].update(width=-4),
                                 lambda sb: sb["assets"]["A"].update(regions=[1])])
def test_wrong_types_are_issues(tiny_project, mut):
    sb = base_storyboard()
    mut(sb)
    assert errors(tiny_project.validate(sb))


def test_anchor_numbers_are_checked():
    tm = Timing({"duration": 5, "words": [{"w": "a", "s": 1.0}]})
    for a in ({"t": "abc"}, {"w": 0, "off": "a"}, {"t": float("nan")}, {"t": True}):
        with pytest.raises(SB.AnchorError):
            tm.resolve(a)


@pytest.mark.parametrize("content", ["", "{bad", "[1]", '{"words": "x"}', '{"words": [{"w": 1}]}'])
def test_timing_load_raises_a_data_error(tmp_path, content):
    f = tmp_path / "t.json"
    f.write_text(content)
    with pytest.raises(DataError):
        Timing.load(f)
    with pytest.raises(DataError):
        Timing.load(tmp_path / "missing.json")


def test_required_slot_missing_is_incomplete_not_an_error(tiny_project):
    sb = base_storyboard()
    sb["shots"][0]["slots"] = {}
    iss = tiny_project.validate(sb)
    inc = [i for i in iss if i.get("code") == "incomplete"]
    assert inc and all(i["level"] == "warn" for i in inc) and not errors(iss)
    tiny_project.use_draft(sb)
    frame = tiny_project.frame_at(1.0, 320)                       # a placeholder, never an exception
    assert frame.shape[1] == 320 and frame.std() > 0


def test_incomplete_overlay_is_skipped(tiny_project):
    sb = base_storyboard()
    ov = {"id": "o9", "technique": "HI-03", "start": {"t": 1.0}, "dur": 1.0, "params": {}, "locked": False, "source": "human", "note": ""}
    sb["shots"][0]["overlays"] = [ov]
    assert [i for i in tiny_project.validate(sb) if i.get("code") == "incomplete" and "mask" in i["message"]]
    tiny_project.use_draft(sb)
    with_ov = tiny_project.frame_at(1.5, 320)
    sb["shots"][0]["overlays"] = []
    tiny_project.use_draft(sb)
    assert np.array_equal(with_ov, tiny_project.frame_at(1.5, 320))
    tiny_project.use_draft(None)


def test_text_params_are_collapsed_to_one_line(tiny_project):
    sb = base_storyboard()
    ov = {"id": "o9", "technique": "X-ANN-01", "start": {"t": 1.0}, "dur": 2.0, "params": {"text": "a\nb\n\nc"}, "locked": False,
          "source": "human", "note": ""}
    sb["shots"][0]["overlays"] = [ov]
    tiny_project.use_draft(sb)
    assert tiny_project.frame_at(1.8, 320).shape[1] == 320
    tiny_project.use_draft(None)


def test_save_cannot_write_a_nan_or_a_surrogate(tiny_project):
    sb = base_storyboard()
    sb["title"] = "bad \ud800"
    with pytest.raises(UnicodeEncodeError):
        tiny_project.save(sb)
    sb = base_storyboard()
    sb["shots"][0]["params"]["camera"][0]["zoom"] = float("nan")
    with pytest.raises((SB.ValidationError, ValueError)):
        tiny_project.save(sb)
    assert tiny_project.storyboard()["title"] == "Tiny"


def test_history_is_capped(tiny_project, tiny):
    for i in range(SB.KEEP_HISTORY + 8):
        sb = base_storyboard()
        sb["title"] = f"v{i}"
        tiny_project.save(sb)
    assert len(list((tiny / "history").glob("*.json"))) == SB.KEEP_HISTORY


def test_preview_frame_count_is_the_length_times_fps(tiny_project, tmp_path):
    import subprocess
    for t0 in (0.0, 0.1, 1.0 / 3):
        out = tmp_path / "p.mp4"
        tiny_project.render_range(t0, t0 + 3.0, out, width=160, fps=15)
        n = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of", "json", str(out)], capture_output=True)
        assert int(json.loads(n.stdout)["streams"][0]["nb_read_frames"]) == 45
