"""The painted area of a picture (worker panelbox, 2026-11-20): `bti.media.contentbox`.

A museum photograph of a panel is often taken on a black ground. The program finds the painted area (`content_box`) of a picture by peeling uniform dark or light lines
from the edges, says `unsure` and takes the whole picture when it is not sure, and the camera of the video is kept inside the box. Made-up pictures only (Pillow, no network)."""
import json
import random

import pytest
from PIL import Image

from bti.media import contentbox as CB


# ----------------------------------------------------------------------------------------------------------------- made-up pictures
def texture(w, h, seed=1, lo=70, hi=190):
    """A panel that is nowhere uniform: noise, so that every row and column of it is a line of painting."""
    rnd = random.Random(seed)
    return Image.frombytes("RGB", (w, h), bytes(rnd.randint(lo, hi) for _ in range(w * h * 3)))


def ringed(w, h, box, ground=(0, 0, 0), sides=("top", "bottom", "left", "right"), seed=1):
    """A w x h picture whose painted area is `box` (x0, y0, x1, y1) on a uniform ground. Only the listed sides have a band: the panel runs to the edge on the others."""
    x0, y0, x1, y1 = box
    x0 = x0 if "left" in sides else 0
    x1 = x1 if "right" in sides else w
    y0 = y0 if "top" in sides else 0
    y1 = y1 if "bottom" in sides else h
    im = Image.new("RGB", (w, h), ground)
    im.paste(texture(x1 - x0, y1 - y0, seed), (x0, y0))
    return im


def save(tmp_path, im, name="p.png"):
    p = tmp_path / name
    im.save(p)
    return p


def near(rec, box, tol=4):
    return all(abs(rec[k] - v) <= tol for k, v in zip(CB.FIELDS, box))


# ----------------------------------------------------------------------------------------------------------------- the finding
def test_a_black_ground_all_round_is_taken_away_and_the_box_is_the_painted_area(tmp_path):
    rec = CB.find(save(tmp_path, ringed(600, 800, (50, 60, 550, 740))))
    assert rec["how"] == "found" and "note" not in rec
    assert near(rec, (50, 60, 550, 740)), rec
    assert rec["x0"] >= 50 and rec["y0"] >= 60 and rec["x1"] <= 550 and rec["y1"] <= 740, "no pixel of the ground is inside the box"


def test_the_ground_may_be_thicker_on_one_side_than_the_other(tmp_path):
    rec = CB.find(save(tmp_path, ringed(600, 800, (30, 100, 570, 700))))
    assert rec["how"] == "found" and near(rec, (30, 100, 570, 700))


def test_a_light_ground_is_taken_away_too(tmp_path):
    rec = CB.find(save(tmp_path, ringed(600, 800, (60, 70, 540, 730), ground=(250, 250, 250))))
    assert rec["how"] == "found" and near(rec, (60, 70, 540, 730))


def test_a_ground_in_the_stripes_of_two_opposite_sides_only_is_a_letterbox_and_is_believed(tmp_path):
    rec = CB.find(save(tmp_path, ringed(800, 600, (0, 80, 800, 520), sides=("top", "bottom"))))
    assert rec["how"] == "found" and near(rec, (0, 80, 800, 520))


def test_no_band_the_box_is_the_whole_picture_and_nothing_is_written(tmp_path):
    p = save(tmp_path, texture(600, 800))
    rec = CB.find(p)
    assert rec == {"x0": 0, "y0": 0, "x1": 600, "y1": 800, "how": "whole"}
    asset = {"file": p.name, "kind": "image", "width": 600, "height": 800}
    assert CB.ensure(asset, tmp_path) is False and "content_box" not in asset, "a picture with no ground keeps its document as it was"
    assert CB.box_of(asset, tmp_path) == (0.0, 0.0, 600.0, 800.0)


def test_a_band_on_one_side_only_could_be_a_dark_part_of_the_painting_so_the_whole_picture_is_used_and_it_says_so(tmp_path):
    rec = CB.find(save(tmp_path, ringed(600, 800, (0, 0, 600, 700), sides=("bottom",))))
    assert rec["how"] == "unsure" and rec["note"] == "one_side"
    assert (rec["x0"], rec["y0"], rec["x1"], rec["y1"]) == (0, 0, 600, 800)
    assert CB.NOTES["one_side"]


def test_a_band_thinner_than_one_per_cent_is_not_a_band(tmp_path):
    rec = CB.find(save(tmp_path, ringed(800, 800, (4, 4, 796, 796))))
    assert rec["how"] == "whole"


def test_a_band_thicker_than_thirty_per_cent_of_its_side_is_not_believed(tmp_path):
    rec = CB.find(save(tmp_path, ringed(600, 800, (200, 100, 400, 700))))
    assert rec["how"] == "unsure" and rec["note"] == "too_thick"


def test_bands_of_different_colours_are_not_a_ground(tmp_path):
    im = texture(600, 800)
    im.paste(Image.new("RGB", (600, 60), (0, 0, 0)), (0, 0))
    im.paste(Image.new("RGB", (600, 60), (250, 250, 250)), (0, 740))
    rec = CB.find(save(tmp_path, im))
    assert rec["how"] == "unsure" and rec["note"] == "colours_differ"


def test_a_painted_area_under_sixty_per_cent_of_the_picture_is_not_believed(tmp_path):
    rec = CB.find(save(tmp_path, ringed(600, 800, (150, 150, 450, 650))))
    assert rec["how"] == "unsure" and rec["note"] == "too_small"


def test_a_middle_grey_ground_needs_three_sides(tmp_path):
    grey = (128, 128, 128)
    assert CB.find(save(tmp_path, ringed(600, 800, (50, 60, 550, 740), ground=grey)))["how"] == "found"
    two = CB.find(save(tmp_path, ringed(600, 800, (50, 60, 550, 740), ground=grey, sides=("left", "right")), "two.png"))
    assert two["how"] == "unsure" and two["note"] == "mid_tone"


def test_a_picture_of_one_colour_has_nothing_to_find(tmp_path):
    for colour in ((0, 0, 0), (128, 128, 128), (250, 250, 250)):
        assert CB.find(save(tmp_path, Image.new("RGB", (400, 300), colour), "c%d.png" % colour[0]))["how"] == "whole"


def test_a_dark_painted_edge_that_is_not_uniform_is_painting_not_ground(tmp_path):
    """A dark brown noise band is brushwork, not a photograph's cloth: it is never taken away."""
    im = texture(600, 800)
    im.paste(texture(600, 70, seed=9, lo=10, hi=40), (0, 0))
    im.paste(texture(600, 70, seed=8, lo=10, hi=40), (0, 730))
    assert CB.find(save(tmp_path, im))["how"] == "whole"


def test_the_finding_is_the_same_every_time_and_is_remembered_until_the_file_changes(tmp_path):
    p = save(tmp_path, ringed(600, 800, (50, 60, 550, 740)))
    a, b = CB.find(p), CB.find(p)
    assert a == b and a is not b
    ringed(600, 800, (40, 50, 560, 750)).save(p)
    c = CB.find(p)
    assert c != a and near(c, (40, 50, 560, 750))


def test_the_box_is_in_the_pixels_of_the_picture_as_it_is_drawn_exif_turn_included(tmp_path):
    """A JPEG stored 400 x 600 with the orientation `6` is drawn 600 x 400 (the page and the engine turn it): the box is in that space."""
    im = ringed(400, 600, (20, 90, 380, 500), seed=3)
    exif = Image.Exif()
    exif[0x0112] = 6
    p = tmp_path / "turned.jpg"
    im.save(p, "JPEG", quality=95, exif=exif)
    rec = CB.find(p)
    # turning 90 degrees clockwise sends the stored point (x, y) to (600 - y, x)
    assert rec["how"] == "found" and near(rec, (600 - 500, 20, 600 - 90, 380), tol=8), rec


def test_a_file_that_is_not_a_picture_or_is_missing_has_no_finding(tmp_path):
    bad = tmp_path / "x.jpg"
    bad.write_bytes(b"not an image")
    assert CB.find(bad) is None and CB.find(tmp_path / "nothing.png") is None


def test_a_record_for_a_picture_of_another_size_is_stale(tmp_path):
    p = save(tmp_path, ringed(600, 800, (50, 60, 550, 740)))
    assert CB.find(p, 600, 800)["how"] == "found"
    assert CB.find(p, 300, 400) is None


def test_ensure_writes_a_box_only_when_something_was_found_and_never_replaces_one_that_is_there(tmp_path):
    p = save(tmp_path, ringed(600, 800, (50, 60, 550, 740)))
    asset = {"file": p.name, "kind": "image", "width": 600, "height": 800}
    assert CB.ensure(asset, tmp_path) is True and asset["content_box"]["how"] == "found"
    mine = {"x0": 10, "y0": 10, "x1": 590, "y1": 790, "how": "set"}
    asset["content_box"] = dict(mine)
    assert CB.ensure(asset, tmp_path) is False and asset["content_box"] == mine
    video = {"file": "v.mp4", "kind": "video", "width": 10, "height": 10}
    assert CB.ensure(video, tmp_path) is False and "content_box" not in video


def test_a_box_that_is_outside_the_picture_or_upside_down_is_not_a_box():
    assert CB.clean({"x0": 0, "y0": 0, "x1": 100, "y1": 100}, 100, 100) == (0.0, 0.0, 100.0, 100.0)
    assert CB.clean({"x0": 0, "y0": 0, "x1": 100, "y1": 100}, 50, 50) is None
    assert CB.clean({"x0": 60, "y0": 0, "x1": 40, "y1": 100}) is None
    assert CB.clean({"x0": "1", "y0": 0, "x1": 4, "y1": 4}) is None and CB.clean(None) is None and CB.clean({"x0": float("nan"), "y0": 0, "x1": 4, "y1": 4}) is None
    assert CB.clean({"x0": -1, "y0": -1, "x1": 100, "y1": 100}, 100, 100) == (0.0, 0.0, 100.0, 100.0), "a hair outside is cut to the picture"


def test_box_problem_says_why_a_person_s_box_is_refused():
    assert CB.box_problem((10, 10, 90, 90), 100, 100) is None
    assert "inside the picture" in CB.box_problem((-1, 0, 90, 90), 100, 100)
    assert "x0 must be less" in CB.box_problem((50, 0, 50, 90), 100, 100)
    assert "too small" in CB.box_problem((10, 10, 20, 90), 1000, 100)
    assert "not known" in CB.box_problem((0, 0, 1, 1), 0, 0)


def test_the_box_scales_with_its_picture():
    a = {"content_box": {"x0": 100, "y0": 50, "x1": 900, "y1": 450, "how": "found"}}
    CB.scale_asset_box(a, 0.5, 2.0)
    assert a["content_box"] == {"x0": 50, "y0": 100, "x1": 450, "y1": 900, "how": "found"}
    CB.scale_asset_box({}, 2, 2)


# ----------------------------------------------------------------------------------------------------------------- the camera inside the box
BOX = (100.0, 106.0, 3363.0, 3900.0)            # the painted area of the Met's goldsmith (3469 x 4000), found by the program


def test_a_frame_inside_the_box_shows_nothing_outside():
    assert CB.outside_share(BOX, 1700, 2000, 1.0) == 0.0


def test_a_close_up_past_the_right_edge_shows_a_band_of_the_ground():
    """The mirror of the first test video: centre 3000 at zoom 2.1 is a frame 914 pixels wide, 94 of them past the edge: 10% of the frame."""
    share = CB.outside_share(BOX, 3000, 2700, 2.1)
    assert share == pytest.approx((3000 + 1920 / 2.1 / 2 - 3363) / (1920 / 2.1), abs=1e-6) and 0.10 < share < 0.11


def test_a_frame_that_holds_the_whole_painting_is_a_pull_back_and_may_show_the_ground():
    cx, cy, z, _ = CB.whole_frame(BOX, 95.5)
    assert CB.holds_whole(BOX, cx, cy, z) and CB.outside_share(BOX, cx, cy, z) == 0.0
    assert CB.outside_share(BOX, cx, cy, z * 1.03) == 0.0, "the push of 3 % of the opening keeps the whole painting"


def test_a_frame_that_nearly_fills_the_width_but_not_quite_shows_a_band_at_each_side():
    """The framing `zoom = 1920 / W` of the file: 3469 px of the picture across, the box is 3263 wide: 3% of the frame black at each side."""
    share = CB.outside_share(BOX, 1734.5, 2000, 1920 / 3469)
    assert share == pytest.approx(1 - 3263 / 3469, abs=1e-4) and share > CB.OFF_LIMIT


def test_a_painting_narrower_than_the_frame_stands_in_the_matte_by_design():
    """Along an axis where the frame is a quarter wider than the painting or more, the bars at both sides are the look, not a fault (a push in on the whole painting)."""
    portrait = (0.0, 0.0, 3840.0, 5253.0)
    assert CB.outside_share(portrait, 1950, 2450, 0.24) == 0.0
    assert CB.outside_share(portrait, 1920, 2626, 0.5) == 0.0                         # full width, inside
    assert CB.outside_share(portrait, 1920, 100, 0.5) > CB.OFF_LIMIT, "above the painting is a fault"


def test_a_frame_wide_enough_for_the_matte_that_is_far_off_the_painting_is_not_a_pull_back():
    """4800 px across (zoom 0.4) is wider than the painting by a quarter or more, but this frame starts at 600: it cuts the painting at the left and shows 2000 px of black
    at the right. The matte is only the matte when the frame holds the painting."""
    assert not CB.holds_whole(BOX, 3000, 2000, 0.4)
    share = CB.outside_share(BOX, 3000, 2000, 0.4)
    assert share == pytest.approx((3000 + 2400 - 3363) / 4800, abs=1e-4)
    cx, cy, z = CB.fit_frame(BOX, 3000, 2000, 0.4)
    assert z == pytest.approx(1920 / 3263, abs=2e-5) and CB.outside_share(BOX, cx, cy, z) == 0.0


def test_fit_frame_changes_nothing_that_is_right():
    for key in ((1700, 2000, 1.0), (1700, 2000, 0.2678), (3000, 2000, 5.0)):
        assert CB.fit_frame(BOX, *key) == key


def test_fit_frame_moves_a_close_up_inside_and_keeps_its_zoom():
    cx, cy, z = CB.fit_frame(BOX, 3000, 2700, 2.1)
    assert z == 2.1 and cy == 2700 and cx < 3000
    assert cx + 1920 / z / 2 <= 3363 + 1e-9 and CB.outside_share(BOX, cx, cy, z) == 0.0
    assert cx == pytest.approx(3363 - 1920 / 2.1 / 2, abs=0.01)


def test_fit_frame_tightens_a_frame_that_is_wider_than_the_painting_by_no_more_than_it_must():
    cx, cy, z = CB.fit_frame(BOX, 1734.5, 2000, 1920 / 3469)
    assert z == pytest.approx(1920 / 3263, abs=2e-5) and z > 1920 / 3469
    assert 100 <= cx - 1920 / z / 2 and cx + 1920 / z / 2 <= 3363 + 1e-6 and CB.outside_share(BOX, cx, cy, z) == 0.0


def test_fit_frame_is_idempotent_and_never_zooms_out_over_many_made_up_frames():
    rnd = random.Random(5)
    for _ in range(400):
        key = (rnd.uniform(-500, 4000), rnd.uniform(-500, 4500), rnd.choice([0.15, 0.3, 0.5, 0.55, 0.6, 0.9, 1.3, 2.0, 3.5, 8.0]))
        got = CB.fit_frame(BOX, *key)
        assert got[2] >= key[2] - 1e-9, key
        assert CB.outside_share(BOX, *got) <= CB.OFF_LIMIT + 1e-9, (key, got)
        assert CB.fit_frame(BOX, *got) == got, (key, got)


def test_fit_frame_keeps_the_axis_that_is_a_pull_back():
    portrait = (0.0, 0.0, 3840.0, 5253.0)
    cx, cy, z = CB.fit_frame(portrait, 1950, -300, 0.24)          # above the painting: the vertical axis is the window
    assert (cx, z) == (1950, 0.24) and cy >= 4500 / 2 - 1e-6 and CB.outside_share(portrait, cx, cy, z) == 0.0


def test_whole_frame_fits_and_centres_the_box_not_the_file():
    cx, cy, z, edge = CB.whole_frame(BOX, 95.5)
    assert (cx, cy) == ((100 + 3363) / 2, (106 + 3900) / 2)
    assert z == pytest.approx(0.955 * 1080 / (3900 - 106)) and edge == pytest.approx(1080 / (3900 - 106))
    wide = (0, 0, 4000.0, 1000.0)
    assert CB.whole_frame(wide, 95.5)[2] == pytest.approx(0.955 * 1920 / 4000), "the smaller of the two fits"


def test_clamp_region_cuts_a_region_to_the_box_and_drops_one_drawn_on_the_ground():
    box = (100.0, 106.0, 3363.0, 3900.0)
    assert CB.clamp_region({"x": 1700, "y": 2000, "rx": 200, "ry": 150, "label": "a"}, box) == {"x": 1700, "y": 2000, "rx": 200, "ry": 150, "label": "a"}
    cut = CB.clamp_region({"x": 3300, "y": 2000, "rx": 200, "ry": 150}, box)          # 137 of its 400 px of width are on the ground
    assert cut["x"] + cut["rx"] <= 3363 and cut["rx"] < 200 and cut["y"] == 2000 and isinstance(cut["x"], int)
    assert CB.clamp_region({"x": 3500, "y": 2000, "rx": 100, "ry": 100}, box) is None, "drawn on the ground"
    assert CB.clamp_region({"x": 3380, "y": 2000, "rx": 150, "ry": 150}, box) is None, "under half inside"
    assert CB.clamp_region({"x": 3000, "y": 2000}, box) == {"x": 3000, "y": 2000} and CB.clamp_region({"x": 3500, "y": 2000}, box) is None


def test_the_record_is_whole_pixels_with_how_and_note():
    assert CB.record((1.4, 2.6, 99.5, 200.2), "found") == {"x0": 1, "y0": 3, "x1": 100, "y1": 200, "how": "found"}
    assert CB.record((0, 0, 5, 5), "unsure", "one_side")["note"] == "one_side" and CB.record((0, 0, 5, 5), "bogus")["how"] == "set"
    json.dumps(CB.record((0, 0, 5, 5), "found"))
