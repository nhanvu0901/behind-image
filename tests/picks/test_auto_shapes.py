"""The two files the agent writes (plan, choice): what is valid, what the program changes by rule, what it only warns about."""
import copy
import json

import pytest
from auto_helpers import CHOICE, PLAN, choice, plan

from bti.picks.auto import shapes, texts

BEATS = [{"id": "b0001", "chapter": "c01", "words": 50}, {"id": "b0002", "chapter": "c01", "words": 50},
         {"id": "b0003", "chapter": "c02", "words": 100}, {"id": "b0004", "chapter": "c02", "words": 100},
         {"id": "b0005", "chapter": "c03", "words": 50}, {"id": "b0006", "chapter": "c03", "words": 50}]
IDS = [b["id"] for b in BEATS]


def ctx(targets=IDS, existing=None):
    return shapes.PlanCtx(beats=BEATS, targets=list(targets), existing_regions=existing or {})


def line(beat, show, reason="Lý do ngắn."):
    return {"beat": beat, "reason": reason, "show": show}


def check(p, **kw):
    return shapes.check_plan(p, ctx(**kw))


def only_errors(rep):
    return "\n".join(rep.errors)


# ---------------------------------------------------------------------------------------------------------------- the plan
def test_the_example_plan_is_valid_and_normalised():
    rep = check(PLAN)
    assert rep.ok and rep.errors == [] and rep.value["schema"] == shapes.PLAN_SCHEMA
    assert [ln["beat"] for ln in rep.value["lines"]] == IDS
    assert set(rep.value["regions"]) == {"MIRROR", "HEAD"} and rep.value["regions"]["HEAD"]["box"] == [0.1, 0.05, 0.3, 0.25]
    wants = shapes.wants_of(rep.value)
    assert [w["id"] for w in wants] == ["b0003.1", "b0004.1", "b0004.2"] and [w["type"] for w in wants] == ["context", "map", "clip"]
    assert len(rep.warnings) == 1 and "b0005 to b0006" in rep.warnings[0]            # a last line with nothing new keeps the framing of the one before
    assert rep.text().endswith("0 error(s), 0 note(s), 1 warning(s)")


@pytest.mark.parametrize("bad,part", [
    ([], "must be one JSON object"),
    ({"lines": "x"}, "`lines` must be a list"),
    ({"schema": "other/9", "lines": []}, "schema must be"),
])
def test_a_plan_of_the_wrong_shape_is_an_error(bad, part):
    assert part in only_errors(check(bad))


def test_every_target_line_needs_an_entry_and_nothing_else_is_allowed():
    p = plan(lines=[x for x in PLAN["lines"] if x["beat"] not in ("b0003", "b0004")])
    assert "b0003, b0004" in only_errors(check(p))
    p = plan(lines=PLAN["lines"] + [line("b0099", [])])
    assert "b0099" in only_errors(check(p)) and "not one of the lines you must cover" in only_errors(check(p))
    p = plan(lines=PLAN["lines"] + [line("b0001", [])])
    assert "written twice" in only_errors(check(p))
    # lines that already have pictures are not targets: the plan must not cover them
    rep = check(plan(lines=[x for x in PLAN["lines"] if x["beat"] != "b0006"], regions=PLAN["regions"]), targets=IDS[:5])
    assert rep.ok, rep.text()


def test_a_line_needs_a_reason_and_at_most_three_pictures():
    p = plan(lines=[line("b0001", [{"type": "whole"}], reason=""), *PLAN["lines"][1:]])
    assert "`reason` must be one short sentence" in only_errors(check(p))
    four = [{"type": "whole"}, {"type": "detail", "region": "MIRROR"}, {"type": "detail", "region": "HEAD"}, {"type": "map", "place": "Oslo"}]
    p = plan(lines=[line("b0001", four), *PLAN["lines"][1:]])
    assert "at most 3" in only_errors(check(p))
    long = "Lý do " * 80
    rep = check(plan(lines=[line("b0001", [{"type": "whole"}], reason=long), *PLAN["lines"][1:]]))
    assert rep.ok and len(rep.value["lines"][0]["reason"]) <= shapes.REASON_MAX and any("reason is cut" in n for n in rep.notes)


def test_the_same_picture_twice_in_a_line_is_dropped_with_a_note():
    rep = check(plan(lines=[line("b0001", [{"type": "whole"}, {"type": "whole"}]), *PLAN["lines"][1:]]))
    assert rep.ok and rep.value["lines"][0]["show"] == [{"type": "whole"}] and any("same picture twice" in n for n in rep.notes)


# ---- boxes
@pytest.mark.parametrize("box,part", [
    ([0.4, 0.3, 0.6], "four numbers"),
    ([0.4, 0.3, 0.6, "x"], "four numbers"),
    ([0.4, 0.3, 0.6, float("nan")], "four numbers"),
    ([0.4, 0.3, 1.5, 0.6], "outside the painting"),                    # a box outside the picture
    ([-0.2, 0.3, 0.5, 0.6], "outside the painting"),
    ([0.6, 0.3, 0.4, 0.5], "upside down"),
    ([0.4, 0.3, 0.41, 0.5], "too small"),
    ([0.0, 0.0, 1.0, 1.0], "almost the whole painting"),
])
def test_a_bad_box_is_an_error_that_says_what_to_change(box, part):
    p = plan(regions=[{"name": "MIRROR", "box": box, "what": "Gương"}, PLAN["regions"][1]])
    rep = check(p)
    assert not rep.ok and part in only_errors(rep) and "MIRROR" in only_errors(rep)


def test_a_box_a_hair_outside_is_clamped():
    rep = check(plan(regions=[{"name": "MIRROR", "box": [0.4, 0.3, 1.004, 0.55], "what": "Gương"}, PLAN["regions"][1]]))
    assert rep.ok and rep.value["regions"]["MIRROR"]["box"] == [0.4, 0.3, 1.0, 0.55]


def test_region_names_and_references():
    p = plan(regions=[{"name": "mirror!", "box": [0.4, 0.3, 0.6, 0.5], "what": "x y"}, PLAN["regions"][1]])
    assert "capital letters" in only_errors(check(p))
    p = plan(regions=[PLAN["regions"][0], PLAN["regions"][0], PLAN["regions"][1]])
    assert "used twice" in only_errors(check(p))
    p = plan(lines=[line("b0001", [{"type": "detail", "region": "NOPE"}]), *PLAN["lines"][1:]])
    assert "region 'NOPE' is not declared" in only_errors(check(p))
    # a region the painting already has is used by name, and may not be declared again
    mine = {"HAND": [0.2, 0.5, 0.3, 0.6]}
    p = plan(lines=[line("b0001", [{"type": "detail", "region": "HAND"}]), *PLAN["lines"][1:]])
    assert check(p, existing=mine).ok
    p = plan(regions=PLAN["regions"] + [{"name": "HAND", "box": [0.2, 0.5, 0.3, 0.6], "what": "Bàn tay"}])
    assert "already has a region with this name" in only_errors(check(p, existing=mine))


def test_a_region_no_line_uses_is_dropped_with_a_note():
    rep = check(plan(regions=PLAN["regions"] + [{"name": "SKY", "box": [0.0, 0.0, 0.9, 0.2], "what": "Bầu trời"}]))
    assert rep.ok and "SKY" not in rep.value["regions"] and any("SKY is not used" in n for n in rep.notes)


# ---- the pictures of a line
def test_context_map_and_clip_fields_are_checked():
    bad_ctx = [{"type": "context", "search": "x", "what": "y"}]
    assert "`search` must be 3 to 120" in only_errors(check(plan(lines=[line("b0001", bad_ctx), *PLAN["lines"][1:]])))
    assert "`what` must say" in only_errors(check(plan(lines=[line("b0001", [{"type": "context", "search": "van Eyck"}]), *PLAN["lines"][1:]])))
    assert "kind 'cat'" in only_errors(check(plan(lines=[line("b0001", [{"type": "context", "search": "van Eyck", "what": "xx", "kind": "cat"}]), *PLAN["lines"][1:]])))
    assert "`place` must be the name" in only_errors(check(plan(lines=[line("b0001", [{"type": "map"}]), *PLAN["lines"][1:]])))
    assert "type 'gif'" in only_errors(check(plan(lines=[line("b0001", [{"type": "gif"}]), *PLAN["lines"][1:]])))
    rep = check(plan(lines=[line("b0001", [{"type": "context", "search": "van Eyck", "what": "Họa sĩ", "alt": ["a b c", "d e f", "g h i"]}]), *PLAN["lines"][1:]]))
    assert rep.ok and rep.value["lines"][0]["show"][0]["alt"] == ["a b c", "d e f"] and any("alternatives" in n for n in rep.notes)


def test_a_clip_lasts_four_to_ten_seconds():
    for sec, want in ((1, 4.0), (30, 10.0), (6, 6.0)):
        clip = {"type": "clip", "search": "canal boat", "what": "Kênh", "seconds": sec}
        rep = check(plan(lines=[PLAN["lines"][0], PLAN["lines"][1], PLAN["lines"][2], line("b0004", [clip]), *PLAN["lines"][4:]]))
        assert rep.ok and shapes.wants_of(rep.value)[-1]["seconds"] == want
        assert (sec == 6) or any("a clip lasts 4 to 10 seconds" in n for n in rep.notes)


def test_two_clips_in_one_chapter_and_a_clip_on_a_painting_line_are_cut_to_the_rule():
    clip = lambda s: {"type": "clip", "search": "canal boat " + s, "what": "Cảnh " + s, "seconds": 6}      # noqa: E731
    lines = [line("b0001", [{"type": "whole"}, clip("a")]),                         # a clip on a painting line: dropped
             line("b0002", [{"type": "context", "search": "van Eyck", "what": "Họa sĩ"}, clip("b")]),      # c01: the first clip that is allowed
             line("b0003", [clip("c")]),                                            # c02: the first of its chapter
             line("b0004", [clip("d")]),                                            # c02: a second one: dropped
             line("b0005", [{"type": "detail", "region": "HEAD"}, clip("e")]),      # a painting line again
             line("b0006", [clip("f")])]                                            # c03: the first of its chapter (b0005's was dropped)
    rep = check(plan(lines=lines))
    assert rep.ok
    kept = [(ln["beat"], [i["type"] for i in ln["show"]]) for ln in rep.value["lines"]]
    assert kept == [("b0001", ["whole"]), ("b0002", ["context", "clip"]), ("b0003", ["clip"]), ("b0004", []), ("b0005", ["detail"]), ("b0006", ["clip"])]
    assert len([n for n in rep.notes if "the clip was dropped" in n]) == 3
    assert any("b0004" in n and "one clip per chapter" in n for n in rep.notes) and any("b0001" in n and "painting itself" in n for n in rep.notes)


def test_the_same_framing_for_more_than_half_a_minute_is_a_warning_not_an_error():
    same = [line(b["id"], [{"type": "whole"}]) for b in BEATS]
    rep = check(plan(regions=[], lines=same))
    assert rep.ok and len(rep.warnings) == 1 and "b0001 to b0006" in rep.warnings[0] and "keep the same framing" in rep.warnings[0]
    # a line with nothing new continues the framing before it
    empty = [line("b0001", [{"type": "whole"}])] + [line(b["id"], []) for b in BEATS[1:]]
    assert len(check(plan(regions=[], lines=empty)).warnings) == 1
    # framing that changes from line to line is fine
    varied = [line(b["id"], [{"type": "detail", "region": "HEAD"}] if i % 2 else [{"type": "whole"}]) for i, b in enumerate(BEATS)]
    assert check(plan(lines=varied, regions=PLAN["regions"][1:])).warnings == []


# ---------------------------------------------------------------------------------------------------------------- the choice
def cctx(**kw):
    d = {"wants": {"b0003.1": 3, "b0004.1": 1, "b0004.2": 2}, "books": 4, "regions": ["MIRROR", "HEAD"]}
    d.update(kw)
    return shapes.ChoiceCtx(**d)


def test_the_example_choice_is_valid_and_normalised():
    rep = shapes.check_choice(CHOICE, cctx())
    assert rep.ok and rep.value["wants"]["b0003.1"]["pick"] == ("c", 1) and rep.value["regions"]["HEAD"]["box"] == [0.08, 0.04, 0.32, 0.28]
    assert rep.value["regions"]["MIRROR"]["action"] == "keep"


def test_a_pick_is_a_candidate_number_a_book_picture_or_null():
    wants = lambda pick: choice(wants=[{"id": "b0003.1", "pick": pick, "reason": "Lý do."}, *CHOICE["wants"][1:]])      # noqa: E731
    for pick, want in ((3, ("c", 3)), ("2", ("c", 2)), ("B4", ("b", 4)), ("b1", ("b", 1)), (None, None)):
        rep = shapes.check_choice(wants(pick), cctx())
        assert rep.ok and rep.value["wants"]["b0003.1"]["pick"] == want, pick
    for pick, part in ((0, "not one of its candidates (1 to 3)"), (4, "not one of its candidates"), ("B5", "not one of the book pictures (B1 to B4)"),
                       (True, "must be a number"), ("x", "must be a number"), (2.5, "must be a number")):
        assert part in only_errors(shapes.check_choice(wants(pick), cctx())), pick


def test_the_choice_must_decide_every_wanted_picture_and_every_box():
    rep = shapes.check_choice(choice(wants=CHOICE["wants"][:1]), cctx())
    assert "b0004.1, b0004.2" in only_errors(rep) and "pick null when none" in only_errors(rep)
    rep = shapes.check_choice(choice(regions=CHOICE["regions"][:1]), cctx())
    assert "HEAD" in only_errors(rep) and "keep, adjust or drop" in only_errors(rep)
    rep = shapes.check_choice(choice(wants=[{"id": "b9999.1", "pick": 1, "reason": "Lý do."}] + CHOICE["wants"]), cctx())
    assert "no such wanted picture" in only_errors(rep)
    rep = shapes.check_choice(choice(wants=[{"id": "b0003.1", "pick": 1}, *CHOICE["wants"][1:]]), cctx())
    assert "`reason` must say" in only_errors(rep)


def test_an_adjusted_box_needs_a_valid_box_and_a_reason_and_a_dropped_one_a_reason():
    bad = lambda r: choice(regions=[CHOICE["regions"][0], r])                                       # noqa: E731
    assert "box must be four numbers" in only_errors(shapes.check_choice(bad({"name": "HEAD", "action": "adjust", "reason": "x y z"}), cctx()))
    assert "outside the painting" in only_errors(shapes.check_choice(bad({"name": "HEAD", "action": "adjust", "box": [0, 0, 2, 1], "reason": "x y z"}), cctx()))
    assert "`reason` must say" in only_errors(shapes.check_choice(bad({"name": "HEAD", "action": "drop"}), cctx()))
    assert "action must be one of" in only_errors(shapes.check_choice(bad({"name": "HEAD", "action": "move", "reason": "x y z"}), cctx()))
    rep = shapes.check_choice(bad({"name": "HEAD", "action": "drop", "reason": "Khung lệch."}), cctx())
    assert rep.ok and rep.value["regions"]["HEAD"]["action"] == "drop"


# ---------------------------------------------------------------------------------------------------------------- the pieces
def test_boxes_and_regions_convert_both_ways():
    box = [0.125, 0.25, 0.5, 0.75]
    r = shapes.box_to_region(box, 2000, 1000)
    assert r == {"x": 625, "y": 500, "rx": 375, "ry": 250}
    assert shapes.region_to_box({**r, "label": "x"}, 2000, 1000) == box
    assert shapes.region_to_box({"x": 5, "y": 5}, 100, 100) is None                      # a point has no box
    assert shapes.crop_pixels(box, 2000, 1000) == (250, 250, 1000, 750)
    x0, y0, x1, y1 = shapes.crop_pixels([0.9999, 0.9999, 1.0, 1.0], 100, 100)
    assert x1 > x0 and y1 > y0                                                            # never an empty crop


def test_region_names_never_take_a_name_that_is_taken():
    assert shapes.region_name("Mirror 1!", set()) == "MIRROR_1"
    assert shapes.region_name("MIRROR", {"MIRROR"}) == "MIRROR_2"
    assert shapes.region_name("MIRROR", {"MIRROR", "MIRROR_2"}) == "MIRROR_3"
    assert shapes.region_name("", set()) == "VUNG" and shapes.region_name("ế", set()) == "VUNG"


def test_the_result_sentence_of_the_brief():
    assert texts.result_sentence(25, 28, 3) == "Agent đã chọn hình cho 25/28 đoạn. 3 đoạn chưa có hình phù hợp."
    assert texts.result_sentence(28, 28, 0) == "Agent đã chọn hình cho 28/28 đoạn."
    assert texts.progress_session("Agent đang lập danh sách hình", 12, 80, 190, 20) == "Agent đang lập danh sách hình: bước 12/80, 3/20 phút."


def test_files_of_the_agent_are_read_with_care(tmp_path):
    f = tmp_path / "out.json"
    assert "missing" in shapes.read_json_file(f, "out/plan.json")[1]
    f.write_text("{not json", encoding="utf-8")
    assert "not valid JSON" in shapes.read_json_file(f, "out/plan.json")[1]
    f.write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert shapes.read_json_file(f, "x") == ({"a": 1}, None)
    f.write_text("x" * (shapes.MAX_FILE_BYTES + 1), encoding="utf-8")
    assert "bigger than" in shapes.read_json_file(f, "x")[1]
    link = tmp_path / "link.json"
    try:
        link.symlink_to(f)
    except OSError:
        return                                            # no symbolic links here (Windows without the right)
    assert "is a link" in shapes.read_json_file(link, "x")[1]


def test_a_plan_may_not_ask_for_more_pictures_from_elsewhere_than_the_choosing_session_can_look_at():
    n = shapes.MAX_WANTS + 1
    beats = [{"id": "b%04d" % i, "chapter": "c%02d" % (i // 10), "words": 20} for i in range(1, n + 1)]
    ctx_ = shapes.PlanCtx(beats=beats, targets=[b["id"] for b in beats])
    lines = [{"beat": b["id"], "reason": "Lý do.", "show": [{"type": "map", "place": "Oslo, Norway"}]} for b in beats]
    rep = shapes.check_plan({"regions": [], "lines": lines}, ctx_)
    assert not rep.ok and "asks for %d pictures from elsewhere" % n in only_errors(rep) and "at most %d" % shapes.MAX_WANTS in only_errors(rep)
    ok = shapes.check_plan({"regions": [], "lines": lines[:-1] + [{"beat": beats[-1]["id"], "reason": "Lý do.", "show": []}]}, ctx_)
    assert ok.ok and len(shapes.wants_of(ok.value)) == shapes.MAX_WANTS


def test_a_reason_the_owner_reads_must_be_vietnamese():
    english = plan(lines=[line("b0001", [{"type": "whole"}], reason="Opens with the whole painting."), *PLAN["lines"][1:]])
    assert "must be written in Vietnamese" in only_errors(check(english)) and "Opens with the whole painting." in only_errors(check(english))
    assert check(plan(lines=[line("b0001", [{"type": "whole"}], reason="Mở bằng cả bức tranh."), *PLAN["lines"][1:]])).ok
    bad_want = choice(wants=[{"id": "b0003.1", "pick": 1, "reason": "Clear photograph of the painter."}, *CHOICE["wants"][1:]])
    assert "must be written in Vietnamese" in only_errors(shapes.check_choice(bad_want, cctx()))
    bad_box = choice(regions=[CHOICE["regions"][0], {"name": "HEAD", "action": "drop", "reason": "The box misses the face."}])
    assert "must be written in Vietnamese" in only_errors(shapes.check_choice(bad_box, cctx()))
    assert shapes.check_choice(choice(regions=[{"name": "MIRROR", "action": "keep", "reason": ""}, CHOICE["regions"][1]]), cctx()).ok      # a keep needs no reason
