"""The two pictures made for people: the contact sheets cut from a short real video, and the sheet of the regions on the main painting."""
import json
from pathlib import Path

import pytest
from PIL import Image

from bti.output import publish, sheets
from output_helpers import KEY, PID, have_ffmpeg, make_video, png

needs_ffmpeg = pytest.mark.skipif(not have_ffmpeg(), reason="ffmpeg is not on this machine")


def size_of(path):
    with Image.open(path) as im:            # closed at once: on Windows a file that is open cannot be replaced
        return im.size


def items(n, seconds):
    step = seconds / n
    return [{"n": i + 1, "t": i * step + 0.2, "label": sheets.label_for(i + 1, i * step, "Zoom kèm dịch tới “Tấm gương trên tường” · vòng sáng · nhãn chi tiết")} for i in range(n)]


@needs_ffmpeg
def test_contact_sheets_are_cut_from_a_short_video(tmp_path):
    v = tmp_path / "final.mp4"
    make_video(v, 8)
    out = tmp_path / "sheets"
    out.mkdir()
    (out / "shots.md").write_text("keep me", encoding="utf-8")
    names = sheets.contact_sheets(v, items(45, 7.5), out, ["ffmpeg"], title="The Dutch Portrait", tmp_root=tmp_path)
    assert names == ["contact_sheet_01.jpg", "contact_sheet_02.jpg", "contact_sheet_03.jpg"]
    first = size_of(out / names[0])
    assert first[0] == 1920 and first[1] > 900
    assert size_of(out / names[2])[1] < first[1], "the last sheet is only as tall as its rows"
    assert not list(tmp_path.glob(".frames-*")), "the scratch folder of the cut frames is gone"
    names = sheets.contact_sheets(v, items(5, 7.5), out, ["ffmpeg"], title="The Dutch Portrait", tmp_root=tmp_path)
    assert names == ["contact_sheet_01.jpg"] and sorted(p.name for p in out.iterdir()) == ["contact_sheet_01.jpg", "shots.md"], "sheets that are no longer needed go; other files stay"


@needs_ffmpeg
def test_a_frame_that_cannot_be_cut_is_a_grey_tile_and_no_frame_at_all_is_an_error(tmp_path):
    v = tmp_path / "final.mp4"
    make_video(v, 3)
    shots = items(4, 3.0) + [{"n": 5, "t": 500.0, "label": ("5 · 8:20", "far past the end")}]
    names = sheets.contact_sheets(v, shots, tmp_path / "a", ["ffmpeg"], tmp_root=tmp_path)
    assert names == ["contact_sheet_01.jpg"]
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(sheets.SheetError):
        sheets.contact_sheets(bad, items(3, 3.0), tmp_path / "b", ["ffmpeg"], tmp_root=tmp_path)
    assert not (tmp_path / "b").exists() or not list((tmp_path / "b").glob("*.jpg"))


@needs_ffmpeg
def test_the_folder_gets_the_contact_sheets_of_its_video(proj):
    proj.stage("approve_storyboard")
    v = proj.d.parent / "real.mp4"
    make_video(v, 14)                                   # longer than the fixture's storyboard
    proj.export(video=v)
    res = publish.sync(proj.d, proj.out, moment="export done")
    assert res["warnings"] == []
    t = proj.tree()
    assert "5_storyboard/contact_sheet_01.jpg" in t and "final.mp4" in t
    st = proj.state()
    assert st["parts"]["export"]["sheets"] == ["5_storyboard/contact_sheet_01.jpg"]
    assert "tờ ảnh tổng hợp" in proj.text("README.md") and "contact_sheet_01.jpg" in proj.text("README.md")
    assert size_of(proj.out / KEY / "5_storyboard" / "contact_sheet_01.jpg")[0] == 1920
    n = (proj.out / KEY / "5_storyboard" / "contact_sheet_01.jpg").stat().st_mtime_ns
    publish.sync(proj.d, proj.out, moment="again")
    assert (proj.out / KEY / "5_storyboard" / "contact_sheet_01.jpg").stat().st_mtime_ns == n, "the sheets are not cut again when nothing changed"


def test_a_video_that_cannot_be_cut_is_a_warning_and_the_video_is_still_published(proj):
    proj.stage("export")                                 # the fixture's video is 10 KB of bytes, not a video
    res = publish.sync(proj.d, proj.out, moment="export done")
    assert [w["code"] for w in res["warnings"]] == ["output_sheets_failed"] and "Video vẫn được lưu" in res["warnings"][0]["sentence"]
    assert "final.mp4" in proj.tree() and not any("contact_sheet" in n for n in proj.tree())


def test_the_regions_sheet_draws_every_region_with_its_name(tmp_path):
    img = tmp_path / "a.jpg"
    png(img, (400, 500))
    regions = {"MIRROR": {"x": 200, "y": 120, "rx": 80, "ry": 60, "label": "Tấm gương trên tường"}, "PEARL": {"x": 250, "y": 300, "rx": 30, "label": ""}, "POINT": {"x": 20, "y": 20, "label": "Một điểm"}}
    out = tmp_path / "regions.jpg"
    assert sheets.regions_sheet(img, regions, out, "The Dutch Portrait") == 3
    with Image.open(out) as im:
        assert im.size[0] > 400 and im.size[1] >= 500 and im.format == "JPEG"
    assert sheets.regions_sheet(img, {}, tmp_path / "none.jpg") == 0


def test_the_font_has_the_vietnamese_letters():
    assert sheets._has_vietnamese(sheets.font(24))
