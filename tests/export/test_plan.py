import json

from bti.export import plan
from bti.export.plan import PartSpec, plan_parts

from conftest import REPO, real_timeline


def test_short_video_is_one_part():
    parts = plan_parts([0, 5, 9], 12.0, 30, 240)
    assert [(p.f0, p.f1) for p in parts] == [(0, 360)]


def test_frames_add_up_and_cuts_are_shot_starts():
    starts = [i * 7.0 for i in range(100)]
    parts = plan_parts(starts, 693.0, 30, 240)
    assert parts[0].f0 == 0 and parts[-1].f1 == round(693 * 30)
    assert all(a.f1 == b.f0 for a, b in zip(parts, parts[1:]))
    cut_frames = {round(t * 30) for t in starts}
    assert all(p.f0 in cut_frames for p in parts[1:])
    assert sum(p.frames for p in parts) == 20790


def test_part_lengths_stay_between_half_and_one_and_a_half_targets():
    parts = plan_parts([i * 3.3 for i in range(400)], 1200.0, 30, 240)
    for p in parts[:-1]:
        assert 120 <= p.seconds <= 360
    assert parts[-1].seconds <= 360


def test_one_very_long_shot_is_cut_at_the_wanted_frame():
    parts = plan_parts([0.0], 600.0, 30, 240)
    assert len(parts) == 2 and parts[1].seconds == 360
    assert parts[0].f1 == 240 * 30


def test_real_arnolfini_timeline():
    starts, end = real_timeline(REPO / "projects" / "arnolfini")
    parts = plan_parts(starts, end, 30, 240)
    assert 3 <= len(parts) <= 4
    assert sum(p.frames for p in parts) == 24625 == plan.total_frames(end)
    cut = {round(t * 30) for t in starts}
    assert all(p.f0 in cut for p in parts[1:])


def test_nothing_to_render_is_an_error():
    import pytest
    with pytest.raises(ValueError):
        plan_parts([], 0.0)


def test_times_roundtrip_through_the_engine_rounding():
    for p in plan_parts([i * 7.0 for i in range(100)], 693.0):
        assert round(float("%.6f" % p.t0) * p.fps) == p.f0
        assert round(float("%.6f" % p.t1) * p.fps) == p.f1


def test_part_key_depends_on_everything():
    a = PartSpec(0, 0, 100, 30)
    k = plan.part_key("rev1", a)
    assert k == plan.part_key("rev1", a)
    assert k != plan.part_key("rev2", a)
    assert k != plan.part_key("rev1", PartSpec(0, 0, 101, 30))
    assert k != plan.part_key("rev1", a, width=1280)
    assert plan.part_filename(a, k) == "part_01_%s.mp4" % k


def test_estimate():
    assert plan.estimate_seconds(60, 2.0) == 120
    assert plan.estimate_seconds(-5) == 0
