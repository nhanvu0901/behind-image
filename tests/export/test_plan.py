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


def test_default_part_length_is_60_seconds_and_splits_arnolfini_into_many_parts():
    parts = plan_parts([i * 7.0 for i in range(100)], 689.0)
    assert 9 <= len(parts) <= 15
    for p in parts[:-1]:
        assert 30 <= p.seconds <= 90
    assert parts[-1].seconds <= 90
    assert sum(p.frames for p in parts) == round(689.0 * 30)

    starts, end = real_timeline(REPO / "projects" / "arnolfini")
    aparts = plan_parts(starts, end)
    assert len(aparts) >= 10
    assert sum(p.frames for p in aparts) == 24625 == plan.total_frames(end)
    cut = {round(t * 30) for t in starts}
    assert all(p.f0 in cut or prev.frames == 60 * 30 for prev, p in zip(aparts, aparts[1:]))


def test_part_key_depends_on_everything():
    a = PartSpec(0, 0, 100, 30)
    k = plan.part_key("rev1", a)
    assert k == plan.part_key("rev1", a)
    assert k != plan.part_key("rev2", a)
    assert k != plan.part_key("rev1", PartSpec(0, 0, 101, 30))
    assert k != plan.part_key("rev1", a, width=1280)
    assert plan.part_filename(a, k) == "part_01_%s.mp4" % k


def test_part_key_is_purely_content_based_and_scoped_per_part(tmp_path):
    from copy import deepcopy
    from bti.export import partkey

    (tmp_path / "media").mkdir()
    img_a = tmp_path / "media" / "a.jpg"
    img_b = tmp_path / "media" / "b.jpg"
    img_unused = tmp_path / "media" / "u.jpg"
    img_a.write_bytes(b"IMG-A-v1")
    img_b.write_bytes(b"IMG-B-v1")
    img_unused.write_bytes(b"UNUSED-v1")

    timing = {
        "duration": 30.0,
        "words": [
            {"s": 0.0, "e": 0.5, "w": "zero"},
            {"s": 10.0, "e": 10.5, "w": "one"},
            {"s": 20.0, "e": 20.5, "w": "two"},
            {"s": 28.0, "e": 28.5, "w": "unused"},
        ],
    }
    base_sb = {
        "schema": "bti.storyboard/1",
        "project": "p",
        "title": "Initial Title",
        "style": "gae",
        "canvas": {"w": 1920, "h": 1080, "fps": 30},
        "identity": {"title": "Arnolfini", "artist": "Van Eyck", "year": "1434"},
        "assets": {
            "A": {
                "file": "media/a.jpg", "kind": "image", "width": 1000, "height": 1000,
                "credit": {"author": "Anon"},
                "regions": {
                    "MIRROR": {"x": 500, "y": 400, "rx": 60, "ry": 80, "label": "Mirror"},
                    "UNUSED_REG": {"x": 100, "y": 100, "rx": 30, "ry": 30, "label": "Shoe"},
                },
            },
            "B": {
                "file": "media/b.jpg", "kind": "image", "width": 800, "height": 600,
                "credit": {"author": "Other"}, "regions": {},
            },
            "U": {"file": "media/u.jpg", "kind": "image", "width": 200, "height": 200, "credit": {}, "regions": {}},
        },
        "shots": [
            {"id": "s0001", "start": {"w": 0}, "technique": "CAM-01", "slots": {"image": {"asset": "A", "region": "MIRROR"}},
             "params": {}, "overlays": [], "note": "first", "locked": False, "beat": "b0001", "intent": "explore"},
            {"id": "s0002", "start": {"w": 2}, "technique": "CAM-03", "slots": {"image": {"asset": "B"}},
             "params": {}, "overlays": [{"id": "o1", "technique": "X-ANN-01", "start": {"t": 22.0}, "dur": 2.0, "params": {"text": "First"}}],
             "note": "second", "locked": False, "beat": "b0002", "intent": "explain"},
        ],
        "end": {"t": 30.0, "fade_s": 1.6},
        "approvals": {"storyboard": {"rev": "abc"}},
    }
    p0 = PartSpec(0, 0, 600, 30)       # 0..20s -> only s0001 + MIRROR + A
    p1 = PartSpec(1, 600, 900, 30)     # 20..30s -> only s0002 + B

    k0, k1 = partkey.part_keys(tmp_path, base_sb, timing, [p0, p1])

    # 1. Pure metadata, unused assets/regions/words, and region label changes change neither part key.
    meta = deepcopy(base_sb)
    meta["title"] = "Completely Different"
    meta["approvals"] = None
    meta["shots"][0]["note"] = "changed note"
    meta["shots"][0]["locked"] = True
    meta["shots"][0]["beat"] = "b9999"
    meta["shots"][0]["intent"] = "compare"
    meta["shots"][0]["id"] = "s0999"
    meta["assets"]["A"]["credit"] = {"author": "Someone Else"}
    meta["assets"]["A"]["regions"]["MIRROR"]["label"] = "Renamed Label"
    meta["assets"]["A"]["regions"]["UNUSED_REG"]["x"] = 250
    meta["identity"]["artist"] = "Changed Artist"      # no ID-* shot uses identity yet
    img_unused.write_bytes(b"UNUSED-v2")
    tm_unused = deepcopy(timing)
    tm_unused["words"][3]["s"] = 29.0
    assert partkey.part_keys(tmp_path, meta, tm_unused, [p0, p1]) == [k0, k1]

    # 2. Editing shot 2 overlay/technique/params changes ONLY part 1.
    ov = deepcopy(base_sb)
    ov["shots"][1]["overlays"][0]["params"]["text"] = "Updated"
    n0, n1 = partkey.part_keys(tmp_path, ov, timing, [p0, p1])
    assert n0 == k0 and n1 != k1

    # 3. Editing shot 1 camera DOES NOT affect part 1 on a hard cut, DOES affect part 1 when shot 2 has transition_in > 0.
    cam = deepcopy(base_sb)
    cam["shots"][0]["params"] = {"zoom": 1.8}
    c0, c1 = partkey.part_keys(tmp_path, cam, timing, [p0, p1])
    assert c0 != k0 and c1 == k1

    sb_tr = deepcopy(base_sb)
    sb_tr["shots"][1]["transition_in"] = {"technique": "TR-01", "dur": 1.0}
    tk0, tk1 = partkey.part_keys(tmp_path, sb_tr, timing, [p0, p1])
    sb_tr_cam = deepcopy(sb_tr)
    sb_tr_cam["shots"][0]["params"] = {"zoom": 1.8}
    tck0, tck1 = partkey.part_keys(tmp_path, sb_tr_cam, timing, [p0, p1])
    assert tck0 != tk0 and tck1 != tk1

    # 4. Asset file bytes (B used only in part 1) -> only part 1 changes.
    img_b.write_bytes(b"IMG-B-v2-changed")
    b0, b1 = partkey.part_keys(tmp_path, base_sb, timing, [p0, p1])
    assert b0 == k0 and b1 != k1
    img_b.write_bytes(b"IMG-B-v1")

    # 5. Referenced region geometry & content_box on A (used only in part 0) -> only part 0 changes.
    reg = deepcopy(base_sb)
    reg["assets"]["A"]["regions"]["MIRROR"]["x"] = 515
    assert partkey.part_keys(tmp_path, reg, timing, [p0, p1])[0] != k0
    assert partkey.part_keys(tmp_path, reg, timing, [p0, p1])[1] == k1
    cbox = deepcopy(base_sb)
    cbox["assets"]["A"]["content_box"] = [0.1, 0.1, 0.9, 0.9]
    assert partkey.part_keys(tmp_path, cbox, timing, [p0, p1])[0] != k0
    assert partkey.part_keys(tmp_path, cbox, timing, [p0, p1])[1] == k1

    # 6. Referenced word timing for boundary word 2 (sets t1 of shot 1 and t0 of shot 2) vs end.fade_s (only part 1).
    tm_w2 = deepcopy(timing)
    tm_w2["words"][2]["s"] = 20.4
    w0, w1 = partkey.part_keys(tmp_path, base_sb, tm_w2, [p0, p1])
    assert w0 != k0 and w1 != k1

    fade = deepcopy(base_sb)
    fade["end"]["fade_s"] = 2.4
    f0, f1 = partkey.part_keys(tmp_path, fade, timing, [p0, p1])
    assert f0 == k0 and f1 != k1

    # 7. ID-* shot makes identity count only for that part.
    id_sb = deepcopy(base_sb)
    id_sb["shots"][1]["overlays"].append({"id": "o2", "technique": "ID-01", "start": {"t": 21.0}, "dur": 2.0, "params": {}})
    ik0, ik1 = partkey.part_keys(tmp_path, id_sb, timing, [p0, p1])
    id_sb2 = deepcopy(id_sb)
    id_sb2["identity"]["title"] = "Arnolfini Alternate"
    ik0b, ik1b = partkey.part_keys(tmp_path, id_sb2, timing, [p0, p1])
    assert ik0 == k0 and ik0b == ik0 and ik1b != ik1

    # 8. Global settings (width, fps, quality, style_sig, style id, engine_version) invalidate every part.
    assert partkey.part_keys(tmp_path, base_sb, timing, [p0, p1], width=1280) != [k0, k1]
    assert all(a != b for a, b in zip([k0, k1], partkey.part_keys(tmp_path, base_sb, timing, [p0, p1], quality="preview")))
    assert all(a != b for a, b in zip([k0, k1], partkey.part_keys(tmp_path, base_sb, timing, [p0, p1], engine_version=99)))
    custom_style = [partkey.part_key(base_sb, sp, project_dir=tmp_path, timing=timing, style_sig="customsig") for sp in (p0, p1)]
    assert all(a != b for a, b in zip([k0, k1], custom_style))
    other_style = deepcopy(base_sb)
    other_style["style"] = "other"
    assert all(a != b for a, b in zip([k0, k1], partkey.part_keys(tmp_path, other_style, timing, [p0, p1])))


def test_changing_cross_cut_opening_label_only_changes_opening_part(tmp_path):
    from copy import deepcopy
    from bti.export import partkey

    (tmp_path / "media").mkdir(exist_ok=True)
    (tmp_path / "media" / "p.jpg").write_bytes(b"PAINTING")
    timing = {"duration": 120.0, "words": [{"s": 2.0, "e": 2.5, "w": "Look"}, {"s": 65.0, "e": 65.5, "w": "Later"}]}
    sb = {
        "schema": "bti.storyboard/1",
        "style": "gae",
        "identity": {"style": "raking"},
        "canvas": {"w": 1920, "h": 1080, "fps": 30},
        "assets": {"A": {"kind": "image", "file": "media/p.jpg", "width": 1000, "height": 1200, "regions": {}}},
        "shots": [
            {
                "id": "s0000", "start": {"t": 0.0}, "technique": "CAM-01", "slots": {"image": {"asset": "A"}}, "params": {},
                "overlays": [{"id": "o2", "technique": "ID-LABEL-01", "start": {"t": 0.3}, "dur": 1.35,
                              "params": {"title": "Old Title", "artist_year": "Painter, 1434", "fade_in_s": 0.5, "fade_out_s": 0.0}}],
            },
            {
                "id": "s0001", "start": {"w": 0, "off": -0.35}, "technique": "CAM-01", "slots": {"image": {"asset": "A"}}, "params": {},
                "overlays": [{"id": "o1", "technique": "ID-LABEL-01", "start": {"w": 0, "off": -0.35}, "dur": 6.35,
                              "params": {"title": "Old Title", "artist_year": "Painter, 1434", "fade_in_s": 0.0, "fade_out_s": 0.5}}],
            },
            {
                "id": "s0002", "start": {"t": 65.0}, "technique": "CAM-01", "slots": {"image": {"asset": "A"}}, "params": {},
                "overlays": [],
            },
        ],
        "end": {"t": 120.0, "fade_s": 1.0},
    }
    p0 = PartSpec(0, 0, 1950, 30)      # [0, 65 s)
    p1 = PartSpec(1, 1950, 3600, 30)   # [65, 120 s)
    k0, k1 = partkey.part_keys(tmp_path, sb, timing, [p0, p1])

    changed = deepcopy(sb)
    for sh in changed["shots"][:2]:
        sh["overlays"][0]["params"]["title"] = "Updated Title"
    ck0, ck1 = partkey.part_keys(tmp_path, changed, timing, [p0, p1])
    assert ck0 != k0 and ck1 == k1


def test_estimate():
    assert plan.estimate_seconds(60, 2.0) == 120
    assert plan.estimate_seconds(-5) == 0
