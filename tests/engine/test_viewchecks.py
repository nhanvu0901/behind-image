"""Worker fixdraft: the checks of what a VIEWER would see (`bti/engine/viewchecks.py`), run by `storyboard.validate`.

Two kinds of tests. (1) The real run: the storyboards of the first video made end to end with a real model (`arnolfini-opus`), kept in
`fixtures/viewer/` (the first draft as the model wrote it, the draft after the owner's first round of requests, the state before the third
round with its seventeen highlight layers, and the final storyboard), with the narration's timing, the project's picks and a small copy of the
painting: the first draft must raise the checks, the final storyboard none, and the brightness estimate of a highlight must agree with the luma
measured in the exported file. (2) Small made-up storyboards for every check: raised, not raised, and the thresholds."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from conftest import words as make_words

import bti.engine.api  # noqa: F401  (registers the techniques)
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import viewchecks as VC
from bti.engine.timing import Timing

FIX = Path(__file__).parent / "fixtures" / "viewer"
BUNDLE = R.load_bundle("gae")
VIEWER = set(VC.CODES) - {"small_detail_not_lit", "highlight_nothing_to_dim", "text_too_brief"}


# ----------------------------------------------------------------------------------------------------------------- the real run
@pytest.fixture(scope="module")
def real(tmp_path_factory):
    """A project folder of the real run: the picks, a small copy of the painting, a tiny file for every other picture."""
    d = tmp_path_factory.mktemp("arnolfini-opus")
    (d / "media").mkdir()
    (d / "picks.json").write_bytes((FIX / "picks.json").read_bytes())
    doc = json.loads((FIX / "final.json").read_text(encoding="utf-8"))
    from PIL import Image
    for key in doc["assets"]:
        f = d / "media" / ("%s.jpg" % key)
        if key == "van_eyck_arnolfini":
            f.write_bytes((FIX / "painting.jpg").read_bytes())
        else:
            Image.new("RGB", (8, 8), (90, 90, 90)).save(f)
    return d


@pytest.fixture(scope="module")
def timing():
    return Timing.load(FIX / "timing.json")


def run(real, timing, name):
    doc = json.loads((FIX / ("%s.json" % name)).read_text(encoding="utf-8"))
    issues = SB.validate(doc, timing, BUNDLE, real)
    return doc, issues, [i for i in issues if i["code"] in VIEWER]


def by_code(issues):
    out: dict = {}
    for i in issues:
        out.setdefault(i["code"], []).append(i)
    return out


def test_the_first_draft_of_the_real_run_raises_the_checks_a_draft_can_show(real, timing):
    doc, issues, viewer = run(real, timing, "first_draft")
    assert not [i for i in issues if i["level"] == "error"], "the first draft validated with no error"
    got = by_code(viewer)
    assert set(got) == {"upright_whole_share", "highlight_off_frame", "highlight_too_dark", "text_not_in_narration", "asset_not_in_lines", "explainer_early"}
    up = got["upright_whole_share"][0]["args"]
    assert up["count"] == 41                                    # the 41 shots of 109 that showed the painting small between the bars
    assert 0.24 <= up["share"] <= 0.30 and 190 <= up["seconds"] <= 215
    assert {w["shot"] for w in up["worst"]} <= {s["id"] for s in doc["shots"]} and up["worst"][0]["seconds"] >= 9
    assert {i["args"]["shot"] for i in got["highlight_off_frame"]} == {"s0076", "s0077"}       # the camera had moved away from the lit spot
    assert len(got["highlight_too_dark"]) >= 6
    assert {i["args"]["asset"] for i in got["asset_not_in_lines"]} == {"squirrel_perched_snowy", "european_pine_marten", "mulling_dry_pigment"}
    assert [i["args"]["shot"] for i in got["explainer_early"]] == ["s0003"]                     # the time axis on black at second 15
    assert [i["args"]["param"] for i in got["text_not_in_narration"]] == ["reading"]            # "Van Eyck was present", the narration says "was here"


def test_the_draft_after_the_first_round_of_requests_also_raises_the_short_shot_the_captions_and_the_map(real, timing):
    doc, issues, viewer = run(real, timing, "after_round1")
    got = by_code(viewer)
    assert [i["args"]["shot"] for i in got["shot_short"]] == ["s0073"] and got["shot_short"][0]["args"]["got"] == pytest.approx(1.1, abs=0.06)
    caps = {(i["args"]["shot"], i["args"]["kind"]): i for i in got["caption_placeholder"]}
    assert set(caps) == {("s0112", "placeholder"), ("s0036", "placeholder"), ("s0089", "metadata")}
    assert caps[("s0112", "placeholder")]["args"]["text"] == "UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950"
    assert "narration" in caps[("s0036", "placeholder")]["args"]["text"]
    texts = {(i["args"]["shot"], i["args"]["param"]) for i in got["text_not_in_narration"]}
    assert ("s0013", "region_label") in texts and ("s0013", "sea_names") in texts            # "Belgium" and a sea name nobody spoke
    assert ("s0036", "source") in texts
    assert "asset_not_in_lines" not in got, "the three photographs were gone from the draft by then"
    assert "caption_repeats" not in got                          # the repeated words were caught as a placeholder first


def test_the_final_storyboard_of_the_real_run_raises_none_of_them(real, timing):
    doc, issues, viewer = run(real, timing, "final")
    assert viewer == [], [(i["code"], i["path"]) for i in viewer]
    assert not [i for i in issues if i["level"] == "error"]


def test_the_state_before_the_third_round_raises_the_highlights_that_made_the_screen_black(real, timing):
    doc, issues, viewer = run(real, timing, "before_round3")
    got = by_code(viewer)
    assert {i["args"]["shot"] for i in got["highlight_off_frame"]} == {"s0126", "s0076", "s0158"}
    dark = {(i["args"]["shot"], i["args"]["overlay"]) for i in got["highlight_too_dark"]}
    assert {("s0145", "o37"), ("s0097", "o1"), ("s0159", "o52")} <= dark             # the three black stretches of the exported file (5:56, 11:09 and the oranges)
    assert set(got) == {"highlight_off_frame", "highlight_too_dark"}, "the cameras were already corrected, nothing else is left"
    assert all(i["args"]["luma"] < VC.HI_MIN_LUMA for i in got["highlight_too_dark"])


def test_the_brightness_estimate_agrees_with_the_luma_measured_in_the_exported_file(real, timing):
    """The seventeen highlight layers of the run: the luma of the exported frame at the middle of each window (ffmpeg signalstats, 16..235) against the
    estimate from the geometry and a 96-pixel grey copy of the painting."""
    doc = json.loads((FIX / "before_round3.json").read_text(encoding="utf-8"))
    rows = json.loads((FIX / "hi_luma.json").read_text(encoding="utf-8"))["rows"]
    assert len(rows) == 17
    starts = [timing.resolve(s["start"]) for s in doc["shots"]]
    end_t = timing.resolve(doc["end"])
    c = VC._Ctx(doc, timing, BUNDLE, real, starts, end_t, SB.safe_rel)
    errors = []
    for r in rows:
        i = next(k for k, s in enumerate(doc["shots"]) if s["id"] == r["shot"])
        o = next(o for o in doc["shots"][i]["overlays"] if o["id"] == r["overlay"])
        sp = c.spans[i]
        p = {**BUNDLE.param_defaults(o["technique"]), **o["params"]}
        keys = c.keys_of(i, sp)
        xy = VC._region_xy(doc["assets"][c.primary(i)], p["at"])
        t = (timing.resolve(o["start"]) + timing.resolve(o["start"]) + o["dur"]) / 2
        now, plain, need = VC.estimate_highlight(c, c.primary(i), keys, t, xy[:2], p["rx"], p["ry"], p.get("feather", 0.55), p.get("shape") == "rect",
                                                 p[VC.HIGHLIGHTS[o["technique"]]])
        errors.append(abs(now - r["measured_before"]))
        assert abs(now - r["measured_before"]) <= 2.0, (r["shot"], r["overlay"], round(now, 1), r["measured_before"])
    assert sum(errors) / len(errors) <= 1.0, errors
    assert max(errors) <= 2.0


def test_validating_the_real_storyboard_stays_fast(real, timing):
    import time
    doc = json.loads((FIX / "first_draft.json").read_text(encoding="utf-8"))
    SB.validate(doc, timing, BUNDLE, real)                       # the grey copy of the painting is read once
    t0 = time.time()
    SB.validate(doc, timing, BUNDLE, real)
    assert time.time() - t0 < 1.0


# ----------------------------------------------------------------------------------------------------------------- made-up storyboards
def asset(w, h, **kw):
    return {"file": "media/a.jpg", "kind": "image", "title": kw.pop("title", "Test"), "artist": kw.pop("artist", "Nobody"), "year": kw.pop("year", "1999"),
            "width": w, "height": h, "regions": kw.pop("regions", {"FACE": {"x": w / 2, "y": h / 3, "rx": w / 10, "ry": w / 10, "label": "Face"}})}


def cam(*poses):
    n = len(poses)
    return [{"at": {"rel": round(i / (n - 1), 4)}, "cx": p[0], "cy": p[1], "zoom": p[2], "ease": "linear"} for i, p in enumerate(poses)]


def shot(i, t, tech="CAM-05", asset_key="A", camera=None, overlays=None, params=None, slots=None):
    p = dict(params or {})
    if camera is not None:
        p["camera"] = camera
    return {"id": "s%d" % i, "start": {"t": t}, "technique": tech, "intent": "explore", "slots": slots if slots is not None else {"image": {"asset": asset_key}},
            "params": p, "transition_in": None, "overlays": overlays or [], "locked": False, "source": "agent", "note": ""}


def overlay(oid, tech, t, dur, **params):
    return {"id": oid, "technique": tech, "intent": "isolate", "start": {"t": t}, "dur": dur, "params": params, "locked": False, "source": "agent", "note": ""}


def make(tmp_path, shots, *, assets=None, end=120.0, n_words=300, picks=None, grey=120, size=(1000, 1500), narration=None):
    """(doc, timing, project folder) of a made-up storyboard: asset A is `size`, flat grey `grey`."""
    d = tmp_path / "proj"
    (d / "media").mkdir(parents=True, exist_ok=True)
    from PIL import Image
    Image.new("RGB", (64, 96), (grey, grey, grey)).save(d / "media" / "a.jpg")
    Image.new("RGB", (64, 96), (grey, grey, grey)).save(d / "media" / "b.jpg")
    doc = {"schema": "bti.storyboard/1", "project": "proj", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
           "assets": assets or {"A": asset(*size), "B": {**asset(900, 700), "file": "media/b.jpg"}}, "shots": shots, "end": {"t": end}, "approvals": {"storyboard": None}}
    ws = narration if narration is not None else make_words(n_words, step=end / max(1, n_words))
    tm = Timing({"duration": end, "words": ws})
    if picks is not None:
        (d / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    elif (d / "picks.json").exists():
        (d / "picks.json").unlink()
    return doc, tm, d


def viewer_of(doc, tm, d):
    return [i for i in SB.validate(doc, tm, BUNDLE, d) if i["code"] in VIEWER]


def codes(doc, tm, d):
    return sorted(i["code"] for i in viewer_of(doc, tm, d))


FILL = (500, 750, 0.55)         # 1000 px wide: 1920 / 1000 = 1.92 fills the width; 0.55 is "small"? no: see SMALL below
WIDE = cam((500, 750, 1.92), (500, 800, 1.92))      # the painting at full width
SMALL = cam((500, 750, 0.5), (500, 750, 0.55))      # 1000 x 1500 px at zoom 0.5: 26% of the screen's width


def test_a_shot_under_one_and_a_half_seconds_raises_and_one_of_exactly_that_does_not(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 10.0, camera=WIDE), shot(3, 11.4, camera=WIDE), shot(4, 20.0, camera=WIDE), shot(5, 21.5, camera=WIDE)]
    doc, tm, d = make(tmp_path, shots, end=30.0, n_words=60)
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "shot_short"]
    assert [(i["args"]["shot"], i["args"]["got"]) for i in got] == [("s2", 1.4)]
    assert got[0]["level"] == "warn" and got[0]["hint"] and got[0]["message"].endswith(got[0]["hint"])


def test_a_shot_under_the_engines_own_floor_is_an_error_and_not_also_a_flicker_warning(tmp_path):
    doc, tm, d = make(tmp_path, [shot(1, 0, camera=WIDE), shot(2, 5.0, camera=WIDE), shot(3, 5.1, camera=WIDE)], end=20.0, n_words=40)
    issues = SB.validate(doc, tm, BUNDLE, d)
    assert [i["code"] for i in issues if i["code"] == "shot_too_short"]
    assert "shot_short" not in [i["code"] for i in issues]


def test_the_painting_small_between_the_bars_raises_above_six_percent_of_the_running_time_and_not_at_or_below(tmp_path):
    def video(small_s):
        shots = [shot(1, 0, camera=WIDE), shot(2, 40.0, camera=SMALL), shot(3, 40.0 + small_s, camera=WIDE)]
        return make(tmp_path, shots, end=120.0, n_words=300)
    doc, tm, d = video(7.0)                                       # 5.8% of 120 s
    assert "upright_whole_share" not in codes(doc, tm, d)
    doc, tm, d = video(8.0)                                       # 6.7%
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "upright_whole_share"]
    assert len(got) == 1 and got[0]["args"]["count"] == 1 and got[0]["args"]["worst"] == [{"shot": "s2", "seconds": 8.0}]
    assert got[0]["path"] == "shots[1]" and "8 s in 1 shots" in got[0]["message"] and 0.066 <= got[0]["args"]["share"] <= 0.067


def test_a_wide_band_of_the_painting_is_not_small_and_a_landscape_painting_is_not_small_at_its_normal_framing(tmp_path):
    band = lambda z: [shot(1, 0, camera=cam((500, 750, z), (500, 750, z))), shot(2, 60.0, camera=cam((500, 750, z), (500, 750, z)))]
    doc, tm, d = make(tmp_path, band(1.2), end=120.0)                           # 1000 px wide at zoom 1.2: 62% of the screen, over the 60% line
    assert "upright_whole_share" not in codes(doc, tm, d)
    doc, tm, d = make(tmp_path, band(1.1), end=120.0)                           # 57%: under it
    assert "upright_whole_share" in codes(doc, tm, d)
    doc, tm, d = make(tmp_path, band(0.5), end=120.0)
    assert "upright_whole_share" in codes(doc, tm, d)
    doc, tm, d = make(tmp_path, [shot(1, 0, camera=cam((1500, 750, 0.64), (1500, 750, 0.64)))], end=120.0, size=(3000, 1500))   # a 2:1 painting at full width: 89%
    assert "upright_whole_share" not in codes(doc, tm, d)


def test_a_clip_under_a_minute_never_raises_the_share(tmp_path):
    doc, tm, d = make(tmp_path, [shot(1, 0, camera=SMALL)], end=50.0, n_words=100)
    assert "upright_whole_share" not in codes(doc, tm, d)


def test_only_the_main_painting_counts(tmp_path):
    small_b = cam((450, 350, 0.3), (450, 350, 0.3))                             # the 900 x 700 picture B at zoom 0.3: 14% of the screen
    doc, tm, d = make(tmp_path, [shot(1, 0, camera=WIDE), shot(2, 80.0, asset_key="B", camera=small_b)], end=120.0)
    assert "upright_whole_share" not in codes(doc, tm, d), "A is on screen 80 s, B 40 s: B is not the main painting"
    doc, tm, d = make(tmp_path, [shot(1, 0, camera=WIDE), shot(2, 30.0, asset_key="B", camera=small_b)], end=120.0)
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "upright_whole_share"]
    assert [i["args"]["asset"] for i in got] == ["B"], "B is on screen 90 s: it is the main painting and it is small"


def hi(oid, t, dur, region="FACE", floor=0.2, rx=100, ry=100, tech="HI-01", **kw):
    key = "floor" if tech == "HI-01" else "surround_floor"
    return overlay(oid, tech, t, dur, at=region, rx=rx, ry=ry, **{key: floor}, **kw)


def test_a_highlight_whose_region_leaves_the_frame_raises_at_the_edge_and_not_well_inside(tmp_path):
    # asset A is 1000 x 1500, FACE at (500, 500). Zoom 2: the frame shows 960 x 540 source px.
    inside = shot(1, 0, camera=cam((500, 500, 2.0), (500, 500, 2.0)), overlays=[hi("o1", 1.0, 4.0, floor=0.9)])
    doc, tm, d = make(tmp_path, [inside], end=20.0, n_words=40)
    assert "highlight_off_frame" not in codes(doc, tm, d)
    # the camera travels down: the face (y 500) is at 50% of the frame, then at the top edge and out of the frame
    drift = shot(1, 0, camera=cam((500, 500, 2.0), (500, 1400, 2.0)), overlays=[hi("o1", 1.0, 8.0, floor=0.9)])
    doc, tm, d = make(tmp_path, [drift], end=20.0, n_words=40)
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "highlight_off_frame"]
    assert len(got) == 1 and got[0]["args"]["shot"] == "s1" and got[0]["args"]["overlay"] == "o1" and got[0]["path"] == "shots[0].overlays[0]"
    assert got[0]["args"]["y_pct"] < 6 or got[0]["args"]["y_pct"] > 94 or got[0]["args"]["x_pct"] < 5


def test_a_highlight_five_percent_in_from_the_edge_is_the_line(tmp_path):
    # zoom 1.0 and the camera centre 540 source px above the face: the face is at 1080 * 0.5 + 540 = 1080 px: out. Put it at 4% and 6% of the height.
    for y_pct, expect in ((4, True), (6, False)):
        cy = 500 - (y_pct / 100.0 * 1080 - 540) / 1.0           # the face's screen y is y_pct % of 1080
        s = shot(1, 0, camera=cam((500, cy, 1.0), (500, cy, 1.0)), overlays=[hi("o1", 1.0, 4.0, floor=0.9)])
        doc, tm, d = make(tmp_path, [s], end=20.0, n_words=40)
        assert ("highlight_off_frame" in codes(doc, tm, d)) is expect, y_pct


def test_a_highlight_that_leaves_the_frame_almost_black_raises_with_the_floor_that_would_do_and_a_milder_one_does_not(tmp_path):
    # flat grey 120 -> luma 16 + 219/255*120 = 119; a small spot with floor 0.1 leaves about 25: raised; floor 0.6 leaves about 75
    def with_floor(f):
        s = shot(1, 0, camera=cam((500, 500, 1.92), (500, 500, 1.92)), overlays=[hi("o1", 1.0, 4.0, floor=f, rx=80, ry=80)])
        return make(tmp_path, [s], end=20.0, n_words=40, grey=60)
    doc, tm, d = with_floor(0.1)
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "highlight_too_dark"]
    assert len(got) == 1 and got[0]["args"]["luma"] < 32 and got[0]["args"]["luma_without"] > 60 and got[0]["args"]["min"] == 32.0
    assert got[0]["args"]["floor_needed"] is not None and 0.2 <= got[0]["args"]["floor_needed"] <= 1.0
    assert "floor of" in got[0]["message"]
    doc, tm, d = with_floor(0.6)
    assert "highlight_too_dark" not in codes(doc, tm, d)
    # the floor the check names is enough
    need = [i for i in viewer_of(*with_floor(0.1)) if i["code"] == "highlight_too_dark"][0]["args"]["floor_needed"]
    doc, tm, d = with_floor(need)
    assert "highlight_too_dark" not in codes(doc, tm, d)


def test_a_frame_that_was_already_dark_without_the_highlight_is_not_blamed_on_it(tmp_path):
    s = shot(1, 0, camera=cam((500, 500, 1.92), (500, 500, 1.92)), overlays=[hi("o1", 1.0, 4.0, floor=0.8, rx=80, ry=80)])
    doc, tm, d = make(tmp_path, [s], end=20.0, n_words=40, grey=10)          # a nearly black picture: 25 with or without
    assert "highlight_too_dark" not in codes(doc, tm, d)


def test_the_brightness_estimate_is_skipped_when_the_picture_cannot_be_read_but_the_frame_check_still_runs(tmp_path):
    s = shot(1, 0, camera=cam((500, 500, 1.92), (500, 500, 1.92)), overlays=[hi("o1", 1.0, 4.0, floor=0.0, rx=60, ry=60)])
    doc, tm, d = make(tmp_path, [s], end=20.0, n_words=40, grey=60)
    (d / "media" / "a.jpg").unlink()
    assert "highlight_too_dark" not in codes(doc, tm, d)
    s2 = shot(1, 0, camera=cam((500, 500, 2.0), (500, 1400, 2.0)), overlays=[hi("o1", 1.0, 8.0, floor=0.9)])
    doc, tm, d = make(tmp_path, [s2], end=20.0, n_words=40)
    (d / "media" / "a.jpg").unlink()
    assert "highlight_off_frame" in codes(doc, tm, d)
    assert "highlight_too_dark" not in codes(doc, tm, d)


def test_x_hi_01_is_judged_with_its_own_floor_and_shape(tmp_path):
    s = shot(1, 0, camera=cam((500, 500, 1.92), (500, 500, 1.92)), overlays=[hi("o1", 1.0, 4.0, floor=0.1, rx=80, ry=80, tech="X-HI-01")])
    doc, tm, d = make(tmp_path, [s], end=20.0, n_words=40, grey=60)
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "highlight_too_dark"]
    assert got and got[0]["args"]["technique"] == "X-HI-01" and got[0]["args"]["floor"] == 0.1


# --- captions
def lay(text_left="", sub_left="", text_right="", sub_right="", a="A", b="B"):
    return shot(1, 0, tech="LAY-01", slots={"left": {"asset": a}, "right": {"asset": b}},
                params={"caption_left": text_left, "caption_left_sub": sub_left, "caption_right": text_right, "caption_right_sub": sub_right})


def test_a_caption_that_is_a_placeholder_or_a_note_to_the_reader_raises(tmp_path):
    for text in ("UNKNOWN AUTHOR, 1950", "Unknown author", "unknown", "Source: an estimate cited in the narration", "the narrator says so", "Lorem ipsum", "N/A"):
        doc, tm, d = make(tmp_path, [lay(sub_left=text)], end=20.0, n_words=40)
        got = [i for i in viewer_of(doc, tm, d) if i["code"] == "caption_placeholder"]
        assert len(got) == 1 and got[0]["args"]["param"] == "caption_left_sub" and got[0]["args"]["shot"] == "s1", text
    for text in ("Jan van Eyck", "The Arnolfini Portrait, 1434", "Man in a Red Turban", "Unknown Man in a Red Turban"):
        doc, tm, d = make(tmp_path, [lay(text_left=text, sub_left="Oil on oak")], end=20.0, n_words=40)
        assert "caption_placeholder" not in codes(doc, tm, d), text


def test_a_caption_that_says_the_same_words_twice_in_a_row_raises(tmp_path):
    for text, rep in (("Jan van Eyck Jan van Eyck", "jan van eyck"), ("Wedding Wedding", "wedding"), ("Arnolfini 1434 1434 portrait", None)):
        doc, tm, d = make(tmp_path, [lay(text_left=text)], end=20.0, n_words=40)
        got = [i for i in viewer_of(doc, tm, d) if i["code"] == "caption_repeats"]
        assert (len(got) == 1 and got[0]["args"]["repeated"] == rep) if rep else not got, text
    doc, tm, d = make(tmp_path, [lay(text_left="Jan van Eyck and Jan van Eyck")], end=20.0, n_words=40)
    assert "caption_repeats" not in codes(doc, tm, d), "the same words apart are not a repeat"


def test_a_sub_caption_that_is_only_the_artist_and_year_of_the_file_raises_under_a_caption_of_its_own(tmp_path):
    assets = {"A": asset(1000, 1500, artist="Jan van Eyck", year="1434", title="The Arnolfini Portrait"), "B": {**asset(900, 700), "file": "media/b.jpg"}}
    doc, tm, d = make(tmp_path, [lay(text_left="Wedding", sub_left="JAN VAN EYCK, 1434")], assets=assets, end=20.0, n_words=40)
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "caption_placeholder"]
    assert len(got) == 1 and got[0]["args"]["kind"] == "metadata"
    for main in ("Jan van Eyck", "The Arnolfini Portrait"):
        doc, tm, d = make(tmp_path, [lay(text_left=main, sub_left="JAN VAN EYCK, 1434")], assets=assets, end=20.0, n_words=40)
        assert "caption_placeholder" not in codes(doc, tm, d), main


# --- text the narration does not carry
NARRATION = "In 1426 Giovanni married Costanza in Lucca and moved to Bruges. About twenty three paintings survive and a hundred pine martens died for one gown".split()


def words_of(text):
    return [{"w": w, "s": round(i * 0.5, 2), "e": round(i * 0.5 + 0.4, 2)} for i, w in enumerate(text)]


def map_shot(**p):
    base = {"places": [{"id": "lucca", "name": "Lucca", "lonlat": [10.5, 43.8], "at": 1.0}, {"id": "bruges", "name": "Bruges", "lonlat": [3.2, 51.2], "at": 2.0}],
            "route": [{"from": "lucca", "to": "bruges", "via": "7.6, 46.0; 5.5, 48.8", "shape": "curve", "at": 3.0}],
            "region_iso": [], "region_label": "", "sea_names": False}
    base.update(p)
    return shot(1, 40.0, tech="MAP-01", slots={}, params=base)


def test_a_map_label_the_narration_never_says_raises_and_the_places_it_says_do_not(tmp_path):
    ws = words_of(NARRATION)
    doc, tm, d = make(tmp_path, [shot(0, 0, camera=WIDE), map_shot()], end=60.0, narration=ws)
    assert [i for i in viewer_of(doc, tm, d) if i["code"] == "text_not_in_narration"] == []
    doc, tm, d = make(tmp_path, [shot(0, 0, camera=WIDE), map_shot(region_label="Belgium")], end=60.0, narration=ws)
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "text_not_in_narration"]
    assert [(i["args"]["param"], i["args"]["missing"]) for i in got] == [("region_label", ["belgium"])]
    doc, tm, d = make(tmp_path, [shot(0, 0, camera=WIDE), map_shot(region_label="Bruges")], end=60.0, narration=ws)
    assert "text_not_in_narration" not in codes(doc, tm, d)
    bad_place = map_shot()
    bad_place["params"]["places"][1]["name"] = "Antwerp"
    doc, tm, d = make(tmp_path, [shot(0, 0, camera=WIDE), bad_place], end=60.0, narration=ws)
    assert [i["args"]["param"] for i in viewer_of(doc, tm, d) if i["code"] == "text_not_in_narration"] == ["places[1].name"]


def test_sea_names_are_raised_unless_the_narration_names_a_sea(tmp_path):
    doc, tm, d = make(tmp_path, [shot(0, 0, camera=WIDE), map_shot(sea_names=True)], end=60.0, narration=words_of(NARRATION))
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "text_not_in_narration"]
    assert [i["args"]["param"] for i in got] == ["sea_names"] and "sea" in got[0]["message"]
    doc, tm, d = make(tmp_path, [shot(0, 0, camera=WIDE), map_shot(sea_names=True)], end=60.0, narration=words_of(NARRATION + ["across", "the", "North", "Sea"]))
    assert "text_not_in_narration" not in codes(doc, tm, d)


def num_shot(value, t=40.0):
    return shot(1, t, camera=WIDE, overlays=[overlay("o1", "NUM-01", t + 1, 6.0, rows=[{"label": "Paintings", "value": value, "units": "works", "count": 0, "at": 0.5}],
                                                         caption="", source="")])


def test_a_figure_on_the_screen_must_be_a_number_the_narration_says_in_digits_or_in_words(tmp_path):
    ws = words_of(NARRATION)
    for value, bad in (("about 23", False), ("23", False), ("1426", False), ("100", False), ("about 100", False), ("24", True), ("1433", True), ("600", True)):
        doc, tm, d = make(tmp_path, [shot(0, 0, camera=WIDE), num_shot(value)], end=60.0, narration=ws)
        got = [i for i in viewer_of(doc, tm, d) if i["code"] == "text_not_in_narration"]
        assert bool(got) is bad, (value, [i["message"] for i in got])
        if bad:
            assert got[0]["args"]["missing"] == [value.split()[-1]] and got[0]["args"]["param"] == "rows[0].value"


def test_a_year_of_the_picture_itself_may_be_on_the_screen_even_when_the_narration_does_not_say_it(tmp_path):
    ws = words_of(NARRATION)
    s = shot(1, 40.0, camera=WIDE, overlays=[overlay("o1", "STATIC-09", 41.0, 3.0, year="1999", sub="")])        # asset A is dated 1999
    doc, tm, d = make(tmp_path, [shot(0, 0, camera=WIDE), s], end=60.0, narration=ws)
    assert "text_not_in_narration" not in codes(doc, tm, d)
    s["overlays"][0]["params"]["year"] = "1434"
    doc, tm, d = make(tmp_path, [shot(0, 0, camera=WIDE), s], end=60.0, narration=ws)
    assert "text_not_in_narration" in codes(doc, tm, d)


def test_a_reading_may_have_a_quarter_of_its_words_of_its_own_but_a_name_may_not(tmp_path):
    ws = words_of("Jan van Eyck was here in 1434 said the inscription above the mirror".split())
    def doc_line(reading):
        s = shot(1, 40.0, camera=WIDE, overlays=[overlay("o1", "DOC-01", 41.0, 6.0, lit=[{"ref": "FACE", "box": "", "at": 1.0, "hold_s": 0}], reading=reading, original="")])
        return make(tmp_path, [shot(0, 0, camera=WIDE), s], end=60.0, narration=ws)
    assert "text_not_in_narration" not in codes(*doc_line("Jan van Eyck was here, 1434"))
    assert "text_not_in_narration" in codes(*doc_line("Jan van Eyck was present, 1434 said so, as sure as day"))


def test_nothing_is_said_about_text_when_there_is_no_timing(tmp_path):
    doc, tm, d = make(tmp_path, [shot(0, 0, camera=WIDE), map_shot(region_label="Belgium")], end=60.0, narration=[])
    assert "text_not_in_narration" not in codes(doc, tm, d)


# --- pictures no line uses
def picks_doc(items_by_beat, main="A", skip=()):
    return {"main_asset": main, "assets": {"A": {}, "B": {}}, "beats": {b: {"status": "skip" if b in skip else "picked", "items": [{"asset": a} for a in items]}
                                                                         for b, items in items_by_beat.items()}}


def test_a_picture_that_no_line_has_raises_once_per_picture_with_the_shots_that_use_it(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 10.0, asset_key="B", camera=cam((450, 350, 2.1), (450, 350, 2.1))), shot(3, 20.0, asset_key="B", camera=cam((450, 350, 2.1), (450, 350, 2.1)))]
    doc, tm, d = make(tmp_path, shots, end=30.0, n_words=60, picks=picks_doc({"b1": ["A"], "b2": []}))
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "asset_not_in_lines"]
    assert len(got) == 1 and got[0]["args"] == {"asset": "B", "title": "Test", "count": 2, "shots": ["s2", "s3"]} and got[0]["path"] == "shots[1]"
    doc, tm, d = make(tmp_path, shots, end=30.0, n_words=60, picks=picks_doc({"b1": ["A"], "b2": ["B"]}))
    assert "asset_not_in_lines" not in codes(doc, tm, d)
    doc, tm, d = make(tmp_path, shots, end=30.0, n_words=60, picks=picks_doc({"b1": ["A"], "b2": ["B"]}, skip=("b2",)))
    assert "asset_not_in_lines" in codes(doc, tm, d), "a skipped line has no pictures"
    doc, tm, d = make(tmp_path, shots, end=30.0, n_words=60)
    assert "asset_not_in_lines" not in codes(doc, tm, d), "no picks.json: nothing to compare with"


def test_the_main_painting_is_never_unused_and_an_overlay_picture_counts_as_used(tmp_path):
    ov = overlay("o1", "LAY-04", 1.0, 3.0)
    s = shot(1, 0, camera=WIDE)
    s["overlays"] = [{**ov, "technique": "X-ANN-02", "slots": {"image": {"asset": "B"}}, "params": {}}]
    doc, tm, d = make(tmp_path, [s], end=30.0, n_words=60, picks=picks_doc({"b1": []}))
    got = [i for i in viewer_of(doc, tm, d) if i["code"] == "asset_not_in_lines"]
    assert [i["args"]["asset"] for i in got] == ["B"]


# --- an explainer on black in the first half minute
def test_a_base_explanatory_component_before_second_thirty_raises_and_at_thirty_or_as_an_overlay_does_not(tmp_path):
    time_axis = lambda t: shot(2, t, tech="TIME-01", slots={}, params={"items": [{"date": 1426, "label": "Marries", "side": "auto", "at": 0.5}, {"date": 1433, "label": "Dies", "side": "auto", "at": 3.0}]})
    for t, expect in ((15.0, True), (29.9, True), (30.0, False), (60.0, False)):
        doc, tm, d = make(tmp_path, [shot(1, 0, camera=WIDE), time_axis(t), shot(3, t + 9.0, camera=WIDE)], end=90.0, n_words=180)
        got = [i for i in viewer_of(doc, tm, d) if i["code"] == "explainer_early"]
        assert bool(got) is expect, t
        if expect:
            assert got[0]["args"]["shot"] == "s2" and got[0]["args"]["technique"] == "TIME-01" and got[0]["args"]["start"] == t
    over = shot(1, 0, camera=WIDE, overlays=[overlay("o1", "NUM-01", 5.0, 6.0, rows=[{"label": "x", "value": "1426", "units": "", "count": 0, "at": 0.5}], caption="", source="")])
    doc, tm, d = make(tmp_path, [over], end=90.0, narration=words_of(NARRATION * 3))
    assert "explainer_early" not in codes(doc, tm, d), "an overlay keeps the painting on screen"


# ----------------------------------------------------------------------------------------------------------------- the module itself
def test_every_code_has_a_description_a_hint_and_is_a_warning():
    assert set(VC.CODES) == set(VC.HINTS)
    for code, text in VC.CODES.items():
        assert code in SB.ISSUE_CODES and "(warning)" in text and "args:" in text, code
        assert VC.HINTS[code].endswith(".") and len(VC.HINTS[code]) > 40, code
    i = VC._issue("shot_short", "shots[0]", "Shot s1 lasts only 1.00 seconds.", shot="s1")
    assert i["level"] == "warn" and i["code"] == "shot_short" and i["hint"] == VC.HINTS["shot_short"] and i["message"] == "Shot s1 lasts only 1.00 seconds. " + i["hint"]


def test_the_numbers_a_narration_says():
    t = VC.tokens
    assert VC.numbers_in(t("Giovanni married in 1426 and she died in 1433")) == {1426, 1433}
    assert VC.numbers_in(t("twenty-three paintings, a hundred pine martens and six hundred pelts")) == {23, 100, 600}
    assert VC.numbers_in(t("two thousand and the 1430s")) == {2000, 1430}
    assert VC.numbers_in(t("nothing at all")) == set()
    assert VC.numbers_in(t("one two")) == {1, 2}
    assert VC.numbers_in(t("one hundred and five and twenty one")) == {105, 21}
    assert VC.numbers_in(t("fifteen")) == {15} and VC.numbers_in(t("six hundred")) == {600}


def test_repeated_words():
    assert VC._repeated(VC.tokens("UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950")) == "unknown author"
    assert VC._repeated(VC.tokens("Wedding Wedding")) == "wedding"
    assert VC._repeated(VC.tokens("1434 1434")) is None
    assert VC._repeated(VC.tokens("Jan van Eyck and Jan van Eyck")) is None


def test_the_camera_follows_the_engines_own_interpolation():
    from bti.engine.vfx import Cam
    keys = [(0.0, 100.0, 200.0, 0.25, "inout_cubic"), (10.0, 900.0, 800.0, 1.0, "linear")]
    cam_ = Cam(keys)
    for t in (0.0, 1.0, 5.0, 7.5, 10.0, 12.0):
        a, b = VC.camera_at(keys, t), cam_.at(t)
        assert all(abs(x - y) < 1e-9 for x, y in zip(a, b)), t


def test_the_coverage_of_the_screen():
    assert VC.coverage(1920, 2626, 0.2056, 3840, 5253) == pytest.approx(0.41, abs=0.02)
    assert VC.coverage(1920, 2626, 0.5, 3840, 5253) == pytest.approx(1.0)
    assert VC.coverage(1920, 100, 0.5, 3840, 5253) < 1.0            # the frame reaches above the picture
    assert VC.coverage(100000, 100000, 1.0, 3840, 5253) == 0.0


def test_a_broken_storyboard_never_makes_the_viewer_checks_raise(tmp_path):
    doc, tm, d = make(tmp_path, [shot(1, 0, camera=WIDE)], end=20.0, n_words=40)
    bad = copy.deepcopy(doc)
    bad["shots"][0]["params"]["camera"] = [{"at": "x"}]
    bad["shots"][0]["overlays"] = [{"technique": "HI-01", "params": {"at": [1], "rx": "a"}, "start": {"t": 1}}, 5]
    bad["assets"]["A"]["width"] = "wide"
    out = SB.validate(bad, tm, BUNDLE, d)
    assert out and all(i["code"] in SB.ISSUE_CODES for i in out)
    assert VC.check({"shots": 5}, tm, BUNDLE, d, [0.0], 10.0, SB.safe_rel) == []


def test_a_huge_png_is_not_decoded_for_the_estimate_and_a_jpeg_of_any_size_is_read_small(tmp_path):
    from PIL import Image
    huge = tmp_path / "huge.png"
    Image.new("L", (7000, 6000), 90).save(huge)                    # 42 MP, a few KB on disk
    assert VC.luma_map(huge) is None
    big_jpeg = tmp_path / "big.jpg"
    Image.new("L", (6200, 6000), 90).save(big_jpeg)                # 37 MP JPEG: read at one eighth by the decoder
    got = VC.luma_map(big_jpeg)
    assert got is not None and got[0] == VC.LUMA_W and abs(got[2][3][5] - 90) <= 1
    assert VC.luma_map(tmp_path / "missing.png") is None
    (tmp_path / "text.jpg").write_text("not an image")
    assert VC.luma_map(tmp_path / "text.jpg") is None
