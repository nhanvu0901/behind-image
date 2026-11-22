"""What each line of the narration does (`kinds` of the plan of the automatic choice of pictures) and the checks that follow from it: one test for every rule of
`bti.picks.auto.shapes.kind_problems`, the plan template's own examples, and what the wants carry through."""
import json
import re
from pathlib import Path

import pytest
from auto_helpers import PLAN, plan

from bti.picks import doc as pdoc
from bti.picks.auto import shapes

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "skills" / "picks_auto" / "PLAN.template.md"
IDS = ["b0001", "b0002", "b0003"]
BEATS = [{"id": b, "chapter": "c01", "words": 40} for b in IDS]
EXISTING = {n: [0.1, 0.1, 0.3, 0.3] for n in ("MIRROR", "HEAD", "SHELVES", "RING", "INSCRIPTION", "COUNTER_EDGE", "SCALES", "SHOP_FRONT", "SIGNATURE")}

CTX = {"type": "context", "search": "Philip the Good portrait Rogier van der Weyden", "alt": ["Philip the Good gold coin museum"], "kind": "portrait",
       "entity": "Philip the Good", "period": "then", "what": "Chân dung Philip the Good"}
WORK = dict(CTX, kind="work", search="Arnolfini Portrait Jan van Eyck", entity="Arnolfini Portrait", what="Chân dung Arnolfini")
MAP2 = {"type": "map", "places": ["Lübeck, Germany", "Bruges, Belgium"], "what": "Lübeck và Bruges"}
DETAIL = {"type": "detail", "region": "MIRROR"}
WHOLE = {"type": "whole"}
CLIP = {"type": "clip", "search": "harbour dawn", "what": "Bến cảng", "seconds": 6}


def check(lines, targets=None):
    """check_plan on one-chapter plans: `lines` is a list of (kinds | None, show, extra) for b0001...; the other targets are idle `idea` lines."""
    targets = targets or IDS
    ctx = shapes.PlanCtx(beats=BEATS, targets=list(targets), existing_regions=dict(EXISTING))
    rows = []
    for i, b in enumerate(targets):
        kinds, show, *extra = lines[i] if i < len(lines) else (["idea"], [], {})
        row = {"beat": b, "reason": "Lý do ngắn.", "show": show, **(extra[0] if extra else {})}
        if kinds is not None:
            row["kinds"] = kinds
        rows.append(row)
    return shapes.check_plan({"regions": [], "lines": rows}, ctx)


def errors_of(rep):
    return "\n".join(rep.errors)


def codes(rep):
    return sorted(set(re.findall(r"\[([a-z_]+)\]$", "\n".join(rep.errors), re.M)))


# ---------------------------------------------------------------------------------------------------------------- the words
def test_the_eleven_words_are_the_contract_and_the_table_has_one_row_for_each():
    assert set(shapes.KINDS) == {"detail", "whole", "outside", "compare", "journey", "dates", "figure", "inscription", "construction", "relations", "idea"}
    assert shapes.KINDS is pdoc.LINE_KINDS and shapes.MAX_KINDS == 2 and set(shapes.KIND_TABLE) == set(shapes.KINDS)
    assert shapes.CONTEXT_KINDS == ("work", "portrait", "document", "photo", "place", "object", "event", "other") and shapes.PERIODS == ("then", "now")
    text = TEMPLATE.read_text(encoding="utf-8")
    for kind, (does, asks) in shapes.KIND_TABLE.items():
        assert "| `%s` | %s | %s |" % (kind, does, asks) in text, kind                          # the template's table is the check's table, word for word


@pytest.mark.parametrize("kinds,show,extra", [
    (["detail"], [DETAIL], {}),
    (["whole"], [WHOLE], {}),
    (["outside"], [CTX], {"fallback": WHOLE}),
    (["outside"], [CLIP], {"fallback": DETAIL}),
    (["compare"], [DETAIL, WORK], {}),
    (["compare"], [WORK, WHOLE], {}),
    (["journey"], [MAP2], {}),
    (["dates"], [DETAIL], {}),
    (["dates"], [WHOLE], {}),
    (["figure"], [CTX], {}),
    (["figure"], [DETAIL], {}),
    (["inscription"], [DETAIL], {}),
    (["construction"], [DETAIL], {}),
    (["construction"], [WHOLE], {}),
    (["relations"], [CTX], {}),
    (["relations"], [DETAIL], {}),
    (["idea"], [WHOLE], {}),
    (["idea"], [DETAIL], {}),
    (["outside", "journey"], [CTX, MAP2], {"fallback": {"type": "detail", "region": "SCALES"}}),
    (["outside", "figure"], [CTX], {"fallback": WHOLE}),
    (["detail", "inscription"], [DETAIL, {"type": "detail", "region": "SIGNATURE"}], {}),
])
def test_every_kind_is_accepted_with_the_pictures_its_row_of_the_table_asks_for(kinds, show, extra):
    rep = check([(kinds, show, extra)])
    assert rep.ok, rep.text()
    assert rep.value["lines"][0]["kinds"] == kinds


@pytest.mark.parametrize("kinds", [["detail"], ["whole"], ["dates"], ["inscription"], ["construction"], ["relations"], ["idea"], ["detail", "idea"]])
def test_a_line_about_the_painting_may_leave_show_empty_because_the_picture_before_stays(kinds):
    assert check([(kinds, [], {})]).ok


@pytest.mark.parametrize("kinds", [["outside"], ["compare"], ["journey"], ["figure"]])
def test_a_line_that_needs_a_picture_may_not_leave_show_empty(kinds):
    assert not check([(kinds, [], {"fallback": WHOLE})]).ok


# ---------------------------------------------------------------------------------------------------------------- kinds itself
def test_a_plan_made_before_kinds_existed_fails_on_one_sentence_that_lists_the_lines():
    rep = check([(None, [WHOLE]), (None, [CTX]), (None, [])])
    assert not rep.ok and len(rep.errors) == 1
    e = rep.errors[0]
    assert "3 line(s) have no `kinds`: b0001, b0002, b0003" in e and "[kinds_missing]" in e
    assert all(k in e for k in shapes.KINDS)                                  # it says every word the model may write


def test_the_missing_kinds_sentence_stops_at_twenty_lines_and_says_how_many_more():
    ids = ["b%04d" % i for i in range(1, 31)]
    ctx = shapes.PlanCtx(beats=[{"id": b, "chapter": "c01", "words": 40} for b in ids], targets=ids)
    rep = shapes.check_plan({"regions": [], "lines": [{"beat": b, "reason": "Lý do ngắn.", "show": []} for b in ids]}, ctx)
    assert len(rep.errors) == 1 and "30 line(s) have no `kinds`" in rep.errors[0] and "b0020" in rep.errors[0] and "b0021" not in rep.errors[0] and "and 10 more" in rep.errors[0]


@pytest.mark.parametrize("kinds,part,code", [
    ("detail", "must be a list of one or two words", "kinds_shape"),
    ([], "must be a list of one or two words", "kinds_shape"),
    ([{"a": 1}], "is not one of", "kinds_unknown"),
    (["detail", "whole", "idea"], "has 3 words; a line has one or two", "kinds_too_many"),
    (["picture"], "kind 'picture' is not one of: detail, whole, outside", "kinds_unknown"),
    (["detail", "detail"], "names 'detail' twice", "kinds_repeated"),
])
def test_a_bad_kinds_is_refused_with_the_words_it_may_have(kinds, part, code):
    rep = check([(kinds, [DETAIL])])
    assert not rep.ok and part in errors_of(rep) and codes(rep) == [code], rep.text()
    assert "lines[0] (b0001)" in errors_of(rep)


# ---------------------------------------------------------------------------------------------------------------- outside, fallback
def test_an_outside_line_that_shows_only_the_painting_is_refused_with_what_to_add():
    rep = check([(["outside"], [DETAIL], {"fallback": WHOLE})])
    e = errors_of(rep)
    assert codes(rep) == ["outside_only_painting"] and "shows only the painting" in e and '"type": "context"' in e and '"entity"' in e and '"period": "then"' in e
    assert 'change kinds to "detail" or "whole"' in e
    rep = check([(["outside"], [], {"fallback": WHOLE})])
    assert codes(rep) == ["outside_only_painting"] and "shows nothing new" in errors_of(rep)


def test_an_outside_line_needs_a_fallback_and_the_fallback_must_be_the_painting():
    rep = check([(["outside"], [CTX])])
    assert codes(rep) == ["outside_no_fallback"] and '"fallback": {"type": "whole"}' in errors_of(rep)
    for bad in ({"type": "context", "search": "abc", "what": "xyz"}, {"type": "map"}, "whole", 3, {}):
        rep = check([(["outside"], [CTX], {"fallback": bad})])
        assert codes(rep) == ["fallback_bad"], bad
    rep = check([(["outside"], [CTX], {"fallback": {"type": "detail", "region": "NOPE"}})])
    assert "region 'NOPE' is not declared" in errors_of(rep) and ".fallback" in errors_of(rep)
    rep = check([(["outside"], [CTX], {"fallback": [WHOLE]})])                   # a list of one item is read as the item
    assert rep.ok and rep.value["lines"][0]["fallback"] == WHOLE


def test_a_fallback_may_ask_for_a_region_and_the_region_is_made_even_when_only_the_fallback_uses_it():
    ctx = shapes.PlanCtx(beats=BEATS, targets=IDS)
    rows = [{"beat": "b0001", "reason": "Lý do ngắn.", "kinds": ["outside"], "show": [CTX], "fallback": {"type": "detail", "region": "COUNTER"}},
            {"beat": "b0002", "reason": "Lý do ngắn.", "kinds": ["whole"], "show": [WHOLE]}, {"beat": "b0003", "reason": "Lý do ngắn.", "kinds": ["idea"], "show": []}]
    rep = shapes.check_plan({"regions": [{"name": "COUNTER", "box": [0.1, 0.5, 0.5, 0.7], "what": "Quầy", "thing": "wooden shop counter"}], "lines": rows}, ctx)
    assert rep.ok and set(rep.value["regions"]) == {"COUNTER"} and not any("not used" in n for n in rep.notes)
    assert rep.value["lines"][0]["fallback"] == {"type": "detail", "region": "COUNTER"}


def test_an_outside_line_whose_only_clip_is_cut_by_the_clip_rule_is_refused_after_the_cut():
    ctx = shapes.PlanCtx(beats=BEATS, targets=IDS)
    clip = lambda w: {"type": "clip", "search": "harbour dawn " + w, "what": "Bến cảng " + w, "seconds": 6}      # noqa: E731
    rows = [{"beat": "b0001", "reason": "Lý do ngắn.", "kinds": ["outside"], "show": [clip("a")], "fallback": WHOLE},
            {"beat": "b0002", "reason": "Lý do ngắn.", "kinds": ["outside"], "show": [clip("b")], "fallback": WHOLE},       # the second clip of the chapter is dropped
            {"beat": "b0003", "reason": "Lý do ngắn.", "kinds": ["idea"], "show": []}]
    rep = shapes.check_plan({"regions": [], "lines": rows}, ctx)
    assert not rep.ok and "lines[1] (b0002) after the clip rule" in errors_of(rep) and codes(rep) == ["outside_only_painting"]
    assert any("one clip per chapter" in n for n in rep.notes)


# ---------------------------------------------------------------------------------------------------------------- maps
def test_a_map_on_a_line_that_is_not_a_journey_is_refused_and_the_sentence_says_what_to_ask_for_instead():
    for kinds in (["outside"], ["detail"], ["whole"]):
        rep = check([(kinds, [CTX, {"type": "map", "places": ["Limoges, France", "Noyon, France"], "what": "Hai nơi"}], {"fallback": WHOLE})])
        e = errors_of(rep)
        assert "map_without_journey" in codes(rep) and "lines[0] (b0001).show[1]" in e and "born at Limoges" in e and '"kind": "<place>"' in e and '"journey"' in e


def test_a_journey_needs_a_map_with_two_or_more_places():
    rep = check([(["journey"], [WHOLE])])
    assert codes(rep) == ["journey_no_map"] and '"places"' in errors_of(rep)
    rep = check([(["journey"], [{"type": "map", "place": "Bruges, Belgium"}])])        # the single `place` of an old plan is one place
    assert codes(rep) == ["journey_one_place"] and "has 1 (Bruges, Belgium)" in errors_of(rep) and "one place is not a journey" in errors_of(rep)
    rep = check([(["journey"], [{"type": "map", "places": ["Bruges, Belgium"], "what": "Một nơi"}])])
    assert codes(rep) == ["journey_one_place"]
    rep = check([(["journey"], [{"type": "map", "places": ["Bruges, Belgium", "Bruges, Belgium"]}])])           # the same name twice is one place
    assert codes(rep) == ["journey_one_place"]


def test_the_places_of_a_map_are_read_from_places_or_from_the_old_place_and_keep_both_names():
    rep = check([(["journey"], [MAP2])])
    m = rep.value["lines"][0]["show"][0]
    assert rep.ok and m["places"] == ["Lübeck, Germany", "Bruges, Belgium"] and m["place"] == "Lübeck, Germany"          # `place` stays for the map search
    old = check([(["outside"], [{"type": "map", "place": "Oslo, Norway"}], {"fallback": WHOLE})])
    assert "map_without_journey" in codes(old)
    assert shapes._item({"type": "map", "place": "Oslo, Norway"}, "x", {}, [], [])["places"] == ["Oslo, Norway"]
    bad = check([(["journey"], [{"type": "map", "places": "Oslo"}])])
    assert "`places` must be a list of 1 to 6 place names" in errors_of(bad)
    bad = check([(["journey"], [{"type": "map", "places": ["Oslo, Norway", 7]}])])
    assert "every entry of `places`" in errors_of(bad)
    assert not check([(["journey"], [{"type": "map", "places": ["a%d, X" % i for i in range(7)]}])]).ok


# ---------------------------------------------------------------------------------------------------------------- compare, figure and the others
def test_a_compare_needs_the_other_work_and_a_part_of_this_painting():
    rep = check([(["compare"], [DETAIL, CTX])])                                      # a portrait is not a work
    assert codes(rep) == ["compare_no_work"] and '"kind": "work"' in errors_of(rep)
    rep = check([(["compare"], [WORK])])
    assert codes(rep) == ["compare_no_painting"] and "beside the other work" in errors_of(rep)
    rep = check([(["compare"], [DETAIL])])
    assert codes(rep) == ["compare_no_work"]


@pytest.mark.parametrize("kinds,show,part", [
    (["detail"], [WHOLE], "kinds says \"detail\""),
    (["whole"], [DETAIL], "kinds says \"whole\""),
    (["dates"], [CTX], "kinds says \"dates\""),
    (["inscription"], [WHOLE], "kinds says \"inscription\""),
    (["construction"], [CTX], "kinds says \"construction\""),
    (["idea"], [CTX], "kinds says \"idea\""),
    (["relations"], [MAP2], "kinds says \"relations\""),
])
def test_a_kind_about_the_painting_must_show_the_part_of_the_painting_it_names(kinds, show, part):
    rep = check([(kinds, show, {"fallback": WHOLE})])
    assert "kind_needs_painting" in codes(rep) and part in errors_of(rep)


def test_a_figure_shows_the_thing_counted():
    rep = check([(["figure"], [WHOLE])])
    assert codes(rep) == ["figure_no_picture"] and "the thing that is counted" in errors_of(rep)
    assert check([(["figure"], [CLIP])]).ok


def test_a_picture_from_elsewhere_needs_a_kind_that_says_so():
    for kinds in (["detail"], ["idea"], ["dates"], ["whole", "construction"]):
        rep = check([(kinds, [DETAIL, WHOLE, CTX])] if kinds[0] != "whole" else [(kinds, [WHOLE, DETAIL, CTX])])
        assert "context_without_kind" in codes(rep), kinds
    rep = check([(["detail"], [DETAIL, CLIP])])
    assert "context_without_kind" in codes(rep) and "a clip" in errors_of(rep)
    for kinds in (["outside"], ["figure"], ["relations"], ["compare"]):
        rep = check([(kinds, [WHOLE, WORK], {"fallback": WHOLE})])
        assert "context_without_kind" not in codes(rep)


def test_every_error_of_a_line_is_given_in_one_round_so_that_one_repair_is_enough():
    rep = check([(["outside"], [WHOLE]), (["journey"], [WHOLE]), (["compare"], [WORK])])
    assert len(rep.errors) == 4 and {"outside_only_painting", "outside_no_fallback", "journey_no_map", "compare_no_painting"} == set(codes(rep))
    assert all("lines[%d] (b000%d)" % (n, n + 1) in e for e, n in ((rep.errors[0], 0), (rep.errors[2], 1), (rep.errors[3], 2)))


def test_the_codes_of_the_kind_rules_are_all_in_the_list_and_nothing_else_is_named():
    said = set()
    for kinds, show, extra in [(["outside"], [DETAIL], {}), (["journey"], [WHOLE], {}), (["compare"], [CTX], {}), (["figure"], [WHOLE], {}), (["detail"], [WHOLE, CTX], {}),
                               (["detail"], [MAP2], {}), (["journey"], [{"type": "map", "places": ["Oslo, Norway"]}], {}), (["outside"], [CTX], {"fallback": 3}),
                               (["outside"], [{"type": "context", "search": "medieval guild charter", "kind": "document", "period": "then", "what": "Điều lệ"}], {"fallback": WHOLE}),
                               ("x", [WHOLE], {}), ([], [WHOLE], {}), (["a"], [WHOLE], {}), (["detail", "whole", "idea"], [WHOLE], {}), (["detail", "detail"], [DETAIL], {}),
                               (None, [WHOLE], {})]:
        said |= set(codes(check([(kinds, show, extra)])))
    assert said == set(shapes.CODES_OF_KINDS)


# ---------------------------------------------------------------------------------------------------------------- context items
def test_a_context_item_carries_entity_and_period_and_the_new_kinds_are_valid():
    rep = check([(["outside"], [dict(CTX, kind="object", period="now")], {"fallback": WHOLE})])
    it = rep.value["lines"][0]["show"][0]
    assert rep.ok and (it["entity"], it["period"], it["kind"]) == ("Philip the Good", "now", "object")
    assert check([(["outside"], [dict(CTX, kind="event")], {"fallback": WHOLE})]).ok
    bare = {k: v for k, v in CTX.items() if k not in ("entity", "period")}
    it = check([(["outside"], [bare], {"fallback": WHOLE})]).value["lines"][0]["show"][0]
    assert it["period"] == "then" and "entity" not in it                          # `then` is the default, a thing with no encyclopedia name has no entity


def test_a_bad_entity_or_period_is_refused():
    rep = check([(["outside"], [dict(CTX, period="yesterday")], {"fallback": WHOLE})])
    assert '`period` must be "then"' in errors_of(rep) and "'yesterday'" in errors_of(rep)
    for bad in ("x", "", 5, "y" * 121):
        rep = check([(["outside"], [dict(CTX, entity=bad)], {"fallback": WHOLE})])
        assert "`entity` must be the name under which an encyclopedia knows the thing" in errors_of(rep), bad


def test_the_wants_carry_kinds_entity_period_and_places_through():
    rep = check([(["outside", "journey"], [CTX, MAP2, CLIP], {"fallback": WHOLE}), (["compare"], [DETAIL, WORK])])
    wants = shapes.wants_of(rep.value)
    assert [w["id"] for w in wants] == ["b0001.1", "b0001.2", "b0001.3", "b0002.2"]
    ctx_want, map_want, clip_want, work_want = wants
    assert ctx_want["kinds"] == ["outside", "journey"] and ctx_want["entity"] == "Philip the Good" and ctx_want["period"] == "then"
    assert map_want["places"] == ["Lübeck, Germany", "Bruges, Belgium"] and map_want["place"] == "Lübeck, Germany" and map_want["kinds"] == ["outside", "journey"]
    assert clip_want["kinds"] == ["outside", "journey"] and "period" not in clip_want
    assert work_want["kinds"] == ["compare"] and work_want["kind"] == "work" and work_want["entity"] == "Arnolfini Portrait"


def test_wants_of_reads_a_plan_saved_before_kinds_entity_and_period_existed():
    old = {"lines": [{"beat": "b0003", "reason": "x", "show": [{"type": "context", "search": "van Eyck portrait", "alt": [], "kind": "portrait", "what": "Họa sĩ"},
                                                          {"type": "map", "place": "Bruges, Belgium", "what": "Bản đồ"}]}]}
    a, b = shapes.wants_of(old)
    assert a["kinds"] == [] and a["period"] == "then" and "entity" not in a
    assert b["kinds"] == [] and b["places"] == ["Bruges, Belgium"] and b["place"] == "Bruges, Belgium"


# ---------------------------------------------------------------------------------------------------------------- the template
def example_lines():
    """The worked examples of section 5 of the template, exactly as the template writes them: `{beat: line}` from the backticked pieces of each bullet."""
    text = TEMPLATE.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^   - (b\d{4}): .*$", text, re.M):
        pieces = [p for p in re.findall(r"`([^`]+)`", m.group(0)) if p.startswith(('"kinds":', '"show":', '"fallback":'))]
        out[m.group(1)] = json.loads("{" + ", ".join(pieces) + "}")
    return out


def test_the_template_has_the_worked_examples_of_the_brief_and_each_one_passes_the_check():
    ex = example_lines()
    assert {b: ex[b]["kinds"] for b in ex} == {"b0006": ["detail"], "b0007": ["outside"], "b0008": ["journey"], "b0022": ["idea"]}
    ids = sorted(ex)
    regions = {**EXISTING, "VILLAGE": [0.1, 0.2, 0.3, 0.4]}
    context = shapes.PlanCtx(beats=[{"id": b, "chapter": "c01", "words": 40} for b in ids], targets=ids, existing_regions=regions)
    rows = [{"beat": b, "reason": "Lý do ngắn.", **ex[b]} for b in ids]
    result = shapes.check_plan({"regions": [], "lines": rows}, context)
    assert result.ok, result.text()
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "The village sits beside the river." in text
    assert "The painter travelled to Rome." in text
    assert "The saint embodies hope." in text
    assert "Arnolfini" not in text


def test_the_json_example_of_the_template_is_a_valid_plan():
    text = TEMPLATE.read_text(encoding="utf-8")
    raw = re.search(r"```json\n(.*?)\n```", text, re.S).group(1)
    obj = json.loads(raw)
    ids = [ln["beat"] for ln in obj["lines"]]
    ctx = shapes.PlanCtx(beats=[{"id": b, "chapter": "c01", "words": 20} for b in ids], targets=ids)
    rep = shapes.check_plan(obj, ctx)
    assert rep.ok, rep.text()
    assert [ln["kinds"] for ln in rep.value["lines"]] == [["detail"]]
    assert rep.value["subjects"][0]["id"] == "village"
    assert rep.value["lines"][0]["about"][0]["words"] == "the village"


def test_the_template_says_the_rules_the_brief_asks_for():
    t = TEMPLATE.read_text(encoding="utf-8")
    assert t.index("1. **Say what each line does.**") < t.index("2. **A line about something outside the painting wants a picture of the subject")
    for must in ("born at Limoges", "Bruges was the commercial capital", "at most 60 pictures from elsewhere", "Philip the Good portrait Rogier van der Weyden",
                 "different in kind", "Never put the main painting's own title in a search", "a picture made in that period comes first", "`period: \"then\"`",
                 "reuses its subject’s picture when possible", "one picture per line is the usual number", "A map only when the line is about *where*",
                 "the short name under which the thing is known", "moneylender and his wife", "royal gold cup", "codex behem"):
        assert must.lower() in t.lower(), must
    assert "keep the ones that matter" not in t and "at most 30 pictures" not in t
    choose_t = (REPO / "skills" / "picks_auto" / "CHOOSE.template.md").read_text(encoding="utf-8")
    for must_choose in ("a candidate is right only when it shows that same subject",
                        "a modern image may be chosen only after no usable period image exists"):
        assert must_choose.lower() in choose_t.lower(), must_choose
