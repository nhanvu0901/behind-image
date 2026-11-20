"""Worker panelbox (2026-11-20): the regions the automatic choice of pictures draws on the main painting stay inside its painted area (`content_box`, `bti/media/contentbox.py`).

The boxes of the plan are fractions of the picture the agent was shown (the whole file, ground included); the pixels they come to are cut to the painted area before `set_region`,
and a box drawn on the ground alone makes no region (the lines that use it show the whole painting). A painting with no ground band is written exactly as before."""
import io
import random

from auto_fixtures import env, paid  # noqa: F401
from auto_helpers import CHOICE, choice
from PIL import Image

from bti.media import contentbox as CB
from bti.picks.auto import write as awrite

PANEL = (150, 100, 1150, 1150)             # on a 1300 x 1250 file


def photograph(env, panel=PANEL):
    rnd = random.Random(3)
    im = Image.new("RGB", (1300, 1250), (0, 0, 0))
    im.paste(Image.frombytes("RGB", (panel[2] - panel[0], panel[3] - panel[1]), bytes(rnd.randint(70, 190) for _ in range((panel[2] - panel[0]) * (panel[3] - panel[1]) * 3))), panel[:2])
    buf = io.BytesIO()
    im.save(buf, "PNG")
    (env.pdir / "media" / "main.png").write_bytes(buf.getvalue())


def inside(r, box, slack=1):
    return r["x"] - r["rx"] >= box[0] - slack and r["x"] + r["rx"] <= box[2] + slack and r["y"] - r["ry"] >= box[1] - slack and r["y"] + r["ry"] <= box[3] + slack


def test_a_box_that_overlaps_the_ground_is_cut_to_the_painted_area_and_one_that_is_inside_is_as_it_was(env):
    photograph(env)
    env.agent.choice = choice(regions=[CHOICE["regions"][0], {"name": "HEAD", "action": "adjust", "box": [0.08, 0.04, 0.32, 0.28], "reason": "Nới khung."}])
    job = env.run()
    assert job["state"] == "done", job.get("error")
    a = env.picks()["assets"]["A"]
    box = CB.box_of(a)
    assert a["content_box"]["how"] == "found" and box is not None
    assert set(a["regions"]) == {"MIRROR", "HEAD"}
    assert a["regions"]["MIRROR"]["x"] == 650 and a["regions"]["MIRROR"]["rx"] == 130, "inside the painting: exactly the box of the plan"
    assert all(inside(r, box) for r in a["regions"].values()), (box, a["regions"])
    head = a["regions"]["HEAD"]
    assert head["x"] - head["rx"] >= box[0] - 1 and head["rx"] < 156, "the adjusted box (104 to 416 across) is cut at the edge of the painting"


def test_a_box_drawn_on_the_ground_makes_no_region_and_the_line_shows_the_whole_painting(env):
    photograph(env)
    env.agent.choice = choice(regions=[CHOICE["regions"][0], {"name": "HEAD", "action": "adjust", "box": [0.0, 0.0, 0.08, 0.06], "reason": "Cạnh trên."}])
    job = env.run()
    assert job["state"] == "done", job.get("error")
    d = env.picks()
    assert set(d["assets"]["A"]["regions"]) == {"MIRROR"}
    assert [(i["asset"], i["region"], i["role"]) for i in d["beats"]["b0005"]["items"]] == [("A", None, "main")]


def test_a_painting_with_no_ground_band_gets_the_regions_of_the_plan_exactly(env):
    job = env.run()
    assert job["state"] == "done", job.get("error")
    a = env.picks()["assets"]["A"]
    assert "content_box" not in a and a["regions"]["HEAD"]["rx"] == 156 and a["regions"]["HEAD"]["ry"] == 150


def test_region_ops_cuts_and_reports_what_it_dropped():
    main = {"width": 1000, "height": 1000, "regions": {}, "content_box": {"x0": 100, "y0": 100, "x1": 900, "y1": 900, "how": "found"}}
    keep = {"IN": {"box": [0.4, 0.4, 0.6, 0.6], "what": "a"}, "EDGE": {"box": [0.8, 0.4, 1.0, 0.6], "what": "b"}, "GROUND": {"box": [0.95, 0.4, 1.0, 0.6], "what": "c"}}
    ops, names, made = awrite.region_ops("A", main, keep, 1000, 1000)
    by = {o["region"]: o for o in ops}
    assert names == {"IN": "IN", "EDGE": "EDGE", "GROUND": None} and made == 2 and set(by) == {"IN", "EDGE"}
    assert (by["IN"]["x"], by["IN"]["rx"]) == (500, 100)
    assert by["EDGE"]["x"] + by["EDGE"]["rx"] <= 900 and by["EDGE"]["rx"] < 100
    no_box = awrite.region_ops("A", {k: v for k, v in main.items() if k != "content_box"}, keep, 1000, 1000)
    assert no_box[1]["GROUND"] == "GROUND" and no_box[2] == 3
