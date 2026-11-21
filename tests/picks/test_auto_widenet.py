"""Tests for widenet: the 3-step wider search for outside lines before falling back to the painting."""
import copy
import json
import types
from pathlib import Path

import pytest
from auto_helpers import CHOICE, PLAN, FakeSource, make_auto_project, plan

from bti.picks import doc as pdoc
from bti.picks.auto import search as asearch, shapes, webround, workspace, write as awrite

BEATS = [{"id": b, "chapter": "c01", "words": 40} for b in ("b0001", "b0002", "b0003")]
EXISTING = {"MIRROR": [0.4, 0.3, 0.6, 0.55]}


def test_shapes_wider_validation_and_check():
    ctx = shapes.PlanCtx(beats=BEATS, targets=["b0001", "b0002", "b0003"], existing_regions=EXISTING,
                         painting_title="The Arnolfini Portrait")

    # 1. Valid wider with step 2 and step 3
    valid_plan = plan(regions=[], lines=[
        {"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "kinds": ["whole"], "show": [{"type": "whole"}]},
        {"beat": "b0002", "reason": "Chi tiết tấm gương.", "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
        {"beat": "b0003", "reason": "Điều lệ phường thợ vàng.", "kinds": ["outside"],
         "show": [{"type": "context", "search": "medieval goldsmith guild statutes", "kind": "document", "period": "then",
                   "what": "Điều lệ phường thợ vàng",
                   "wider": [{"step": 2, "search": "medieval guild charter manuscript", "kind": "document", "what": "Văn bản đặc quyền"},
                             {"step": 3, "search": "medieval guild seal chest museum", "kind": "object", "what": "Hiện vật con dấu"}]}],
         "fallback": {"type": "whole"}},
    ])
    rep = shapes.check_plan(valid_plan, ctx)
    assert rep.ok, rep.text()
    assert rep.value["lines"][2]["show"][0]["wider"] == [
        {"step": 2, "search": "medieval guild charter manuscript", "kind": "document", "what": "Văn bản đặc quyền"},
        {"step": 3, "search": "medieval guild seal chest museum", "kind": "object", "what": "Hiện vật con dấu"}
    ]

    # 2. wider_missing rule: document with period then needs wider
    plan_missing_wider = plan(regions=[], lines=[
        {"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "kinds": ["whole"], "show": [{"type": "whole"}]},
        {"beat": "b0002", "reason": "Chi tiết tấm gương.", "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
        {"beat": "b0003", "reason": "Điều lệ phường thợ vàng.", "kinds": ["outside"],
         "show": [{"type": "context", "search": "medieval goldsmith guild statutes", "kind": "document", "period": "then",
                   "what": "Điều lệ phường thợ vàng"}],
         "fallback": {"type": "whole"}},
    ])
    rep = shapes.check_plan(plan_missing_wider, ctx)
    assert not rep.ok
    assert any("wider_missing" in e for e in rep.errors)

    # 3. wider is optional for portrait with entity or period now
    plan_portrait = plan(regions=[], lines=[
        {"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "kinds": ["whole"], "show": [{"type": "whole"}]},
        {"beat": "b0002", "reason": "Chi tiết tấm gương.", "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
        {"beat": "b0003", "reason": "Chân dung họa sĩ.", "kinds": ["outside"],
         "show": [{"type": "context", "search": "Jan van Eyck portrait", "kind": "portrait", "entity": "Jan van Eyck", "period": "then",
                   "what": "Chân dung Jan van Eyck"}],
         "fallback": {"type": "whole"}},
    ])
    rep = shapes.check_plan(plan_portrait, ctx)
    assert rep.ok, rep.text()

    # 4. Bad wider steps: step 1 instead of step 2, step 3 kind not object, painting title in search
    bad_step = copy.deepcopy(valid_plan)
    bad_step["lines"][2]["show"][0]["wider"][0]["step"] = 1
    assert "wider_step" in shapes.check_plan(bad_step, ctx).text()

    bad_kind = copy.deepcopy(valid_plan)
    bad_kind["lines"][2]["show"][0]["wider"][1]["kind"] = "document"
    assert "wider_kind" in shapes.check_plan(bad_kind, ctx).text()

    bad_title = copy.deepcopy(valid_plan)
    bad_title["lines"][2]["show"][0]["wider"][0]["search"] = "The Arnolfini Portrait copy"
    assert "wider_painting_title" in shapes.check_plan(bad_title, ctx).text()


def test_wants_of_and_search_state_carry_wider():
    valid_plan = plan(lines=[
        {"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "kinds": ["whole"], "show": [{"type": "whole"}]},
        {"beat": "b0002", "reason": "Chi tiết tấm gương.", "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
        {"beat": "b0003", "reason": "Điều lệ phường thợ vàng.", "kinds": ["outside"],
         "show": [{"type": "context", "search": "medieval goldsmith guild statutes", "kind": "document", "period": "then",
                   "what": "Điều lệ phường thợ vàng",
                   "wider": [{"step": 2, "search": "medieval guild charter manuscript", "kind": "document", "what": "Văn bản đặc quyền"},
                             {"step": 3, "search": "medieval guild seal chest museum", "kind": "object", "what": "Hiện vật con dấu"}]}],
         "fallback": {"type": "whole"}},
    ])
    wants = shapes.wants_of(valid_plan)
    w3 = next(w for w in wants if w["id"] == "b0003.1")
    assert "wider" in w3
    assert len(w3["wider"]) == 2
    assert w3["wider"][0]["step"] == 2
    assert w3["wider"][1]["step"] == 3

    st = asearch.new_state()
    st["wants"][w3["id"]] = asearch._new_want(w3)
    assert st["wants"][w3["id"]]["wider"] == w3["wider"]


def test_round_two_searches_both_step2_and_step3_with_at_most_4_each(tmp_path):
    pdir = make_auto_project(tmp_path, "w1")
    want = {
        "id": "b0003.1", "beat": "b0003", "n": 1, "type": "context", "kind": "document", "period": "then",
        "search": "goldsmith statutes", "what": "Điều lệ",
        "wider": [
            {"step": 2, "search": "guild charter miniature", "kind": "document", "what": "Tiểu họa"},
            {"step": 3, "search": "guild seal museum", "kind": "object", "what": "Con dấu"}
        ]
    }
    st = asearch.new_state()
    st["wants"][want["id"]] = asearch._new_want(want)

    # Fake search where both step 2 and step 3 return 6 items each
    def fake_search_both(pdir, q, offset, sources, limit, kind="image"):
        if q == "guild charter miniature":
            return {"items": [{"source": "commons", "source_id": f"M_step2_{i}", "title": f"Charter {i}",
                               "thumb_url": f"thumb2_{i}.jpg", "mime": "image/jpeg", "width": 800, "height": 600}
                              for i in range(1, 7)],
                    "errors": []}
        if q == "guild seal museum":
            return {"items": [{"source": "met", "source_id": f"M_step3_{i}", "title": f"Seal {i}",
                               "thumb_url": f"thumb3_{i}.jpg", "mime": "image/jpeg", "width": 800, "height": 600}
                              for i in range(1, 7)],
                    "errors": []}
        return {"items": [], "errors": []}

    def fake_thumb(pdir, c, limited, clock):
        return "thumb.jpg"

    web = asearch.Web(on=False, max=0)
    choice = {"wants": {"b0003.1": {"pick": None, "reason": "null"}}, "regions": {}}

    res_st = webround.search_round_two(
        pdir, [want], st, choice, main_key="A", web=web, fetch_thumb=fake_thumb,
        clock=lambda: 1000.0, cancelled=lambda: False, progress=lambda p, s: None,
        save=lambda s: None, search=fake_search_both, wiki_search=fake_search_both
    )
    cands = res_st["wants"]["b0003.1"]["candidates"]
    # At most 4 from step 2 and at most 4 from step 3 -> 8 in all
    assert len(cands) == 8
    assert [c["step"] for c in cands] == [2, 2, 2, 2, 3, 3, 3, 3]
    assert [c["source_id"] for c in cands[:4]] == [f"M_step2_{i}" for i in range(1, 5)]
    assert [c["source_id"] for c in cands[4:]] == [f"M_step3_{i}" for i in range(1, 5)]

    # Now test when step 2 finds nothing, step 3 finds result
    st2 = asearch.new_state()
    st2["wants"][want["id"]] = asearch._new_want(want)

    def fake_search_step3_only(pdir, q, offset, sources, limit, kind="image"):
        if q == "guild seal museum":
            return {"items": [{"source": "commons", "source_id": "M2", "title": "Seal object",
                               "thumb_url": "thumb2.jpg", "mime": "image/jpeg", "width": 800, "height": 600}],
                    "errors": []}
        return {"items": [], "errors": []}

    res_st2 = webround.search_round_two(
        pdir, [want], st2, choice, main_key="A", web=web, fetch_thumb=fake_thumb,
        clock=lambda: 1000.0, cancelled=lambda: False, progress=lambda p, s: None,
        save=lambda s: None, search=fake_search_step3_only, wiki_search=fake_search_step3_only
    )
    cands2 = res_st2["wants"]["b0003.1"]["candidates"]
    assert len(cands2) == 1
    assert cands2[0]["source_id"] == "M2"
    assert cands2[0]["step"] == 3


def test_round_two_web_budget(tmp_path):
    pdir = make_auto_project(tmp_path, "w_budget")
    want = {
        "id": "b0003.1", "beat": "b0003", "n": 1, "type": "context", "kind": "document", "period": "then",
        "search": "goldsmith statutes", "what": "Điều lệ",
        "wider": [
            {"step": 2, "search": "guild charter miniature", "kind": "document", "what": "Tiểu họa"},
            {"step": 3, "search": "guild seal museum", "kind": "object", "what": "Con dấu"}
        ]
    }
    st = asearch.new_state()
    st["wants"][want["id"]] = asearch._new_want(want)

    # Empty free search, web has 0 budget left
    def empty_search(pdir, q, offset, sources, limit, kind="image"):
        return {"items": [], "errors": []}

    web = asearch.Web(on=True, max=5, spent=5)  # left == 0
    choice = {"wants": {"b0003.1": {"pick": None, "reason": "null"}}, "regions": {}}

    res_st = webround.search_round_two(
        pdir, [want], st, choice, main_key="A", web=web, fetch_thumb=lambda p, c, l, cl: None,
        clock=lambda: 1000.0, cancelled=lambda: False, progress=lambda p, s: None,
        save=lambda s: None, search=empty_search, wiki_search=empty_search
    )
    assert res_st["wants"]["b0003.1"]["code"] == "web_budget"


def test_build_choose_second_session_sees_steps(tmp_path):
    pdir = make_auto_project(tmp_path, "w_choose")
    from bti.picks.auto import inputs as ainputs
    inp = ainputs.load(pdir, redo=True, need_targets=False)

    plan_doc = plan(lines=[
        {"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "kinds": ["whole"], "show": [{"type": "whole"}]},
        {"beat": "b0002", "reason": "Chi tiết tấm gương.", "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
        {"beat": "b0003", "reason": "Điều lệ phường thợ vàng.", "kinds": ["outside"],
         "show": [{"type": "context", "search": "medieval goldsmith guild statutes", "kind": "document", "period": "then",
                   "what": "Điều lệ phường thợ vàng",
                   "wider": [{"step": 2, "search": "medieval guild charter manuscript", "kind": "document", "what": "Văn bản đặc quyền"},
                             {"step": 3, "search": "medieval guild seal chest museum", "kind": "object", "what": "Hiện vật con dấu"}]}],
         "fallback": {"type": "whole"}},
    ])
    search_doc = {
        "wants": {
            "b0003.1": {
                "id": "b0003.1", "beat": "b0003", "n": 1, "type": "context", "kind": "document", "what": "Điều lệ",
                "queries": ["guild charter miniature"],
                "candidates": [
                    {"n": 1, "source": "commons", "source_id": "M1", "title": "Charter miniature",
                     "author": "Painter", "licence": "PD", "flag": None, "width": 800, "height": 600,
                     "page_url": "https://example.org", "thumb": None, "step": 2, "round": 2}
                ]
            }
        }
    }
    limits = types.SimpleNamespace(minutes=20, steps=80)
    ws, cctx = workspace.build_choose(inp, plan_doc, search_doc, limits, books=[], second=True)
    wants_json = json.loads((ws.root / "inputs" / "wants.json").read_text(encoding="utf-8"))
    cands = wants_json["wants"][0]["candidates"]
    assert cands[0]["step"] == 2


def test_write_records_step_and_empties_missing(tmp_path):
    pdir = make_auto_project(tmp_path, "w_write")
    from bti.picks.auto import inputs as ainputs
    inp = ainputs.load(pdir, redo=True, need_targets=False)

    plan_doc = plan(lines=[
        {"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "kinds": ["whole"], "show": [{"type": "whole"}]},
        {"beat": "b0002", "reason": "Chi tiết tấm gương.", "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
        {"beat": "b0003", "reason": "Điều lệ phường thợ vàng.", "kinds": ["outside"],
         "show": [{"type": "context", "search": "medieval goldsmith guild statutes", "kind": "document", "period": "then",
                   "what": "Điều lệ phường thợ vàng",
                   "wider": [{"step": 2, "search": "medieval guild charter manuscript", "kind": "document", "what": "Văn bản đặc quyền"},
                             {"step": 3, "search": "medieval guild seal chest museum", "kind": "object", "what": "Hiện vật con dấu"}]}],
         "fallback": {"type": "whole"}},
    ])
    search_doc = {
        "wants": {
            "b0003.1": {
                "id": "b0003.1", "beat": "b0003", "n": 1, "type": "context", "kind": "document", "what": "Điều lệ",
                "candidates": [
                    {"n": 1, "source": "commons", "source_id": "M1", "title": "Charter miniature",
                     "author": "Painter", "licence": "PD", "flag": None, "width": 800, "height": 600,
                     "page_url": "https://example.org", "thumb": None, "step": 2, "media": "image"}
                ]
            }
        }
    }
    choice_doc = {
        "wants": {"b0003.1": {"pick": ("c", 1), "reason": "Tiểu họa cùng thời."}},
        "regions": {}
    }
    picks = awrite.resolve_picks(plan_doc, search_doc, choice_doc, books=[])
    assert picks["b0003.1"]["step"] == 2

    # When asset is imported successfully
    got = {("commons", "M1"): "media/m1.png"}
    lines = awrite.build_lines(inp, plan_doc, picks, got, failed={}, names={}, dropped=[], lost=set())
    line3 = next(ln for ln in lines if ln["beat"] == "b0003")
    assert len(line3["items"]) == 1
    assert line3["items"][0]["step"] == 2
    assert line3["missing"] == []

    # Operations contain step
    ops = awrite._ops_for(lines, main_key="A")
    set_pick_op = next(o for o in ops if o.get("op") == "set_picks" and o.get("beat") == "b0003")
    assert set_pick_op["items"][0]["step"] == 2
    assert set_pick_op["missing"] == []


def test_write_fallback_when_all_three_fail(tmp_path):
    pdir = make_auto_project(tmp_path, "w_fallback")
    from bti.picks.auto import inputs as ainputs
    inp = ainputs.load(pdir, redo=True, need_targets=False)

    plan_doc = plan(lines=[
        {"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "kinds": ["whole"], "show": [{"type": "whole"}]},
        {"beat": "b0002", "reason": "Chi tiết tấm gương.", "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
        {"beat": "b0003", "reason": "Điều lệ phường thợ vàng.", "kinds": ["outside"],
         "show": [{"type": "context", "search": "medieval goldsmith guild statutes", "kind": "document", "period": "then",
                   "what": "Điều lệ phường thợ vàng",
                   "wider": [{"step": 2, "search": "medieval guild charter manuscript", "kind": "document", "what": "Văn bản đặc quyền"},
                             {"step": 3, "search": "medieval guild seal chest museum", "kind": "object", "what": "Hiện vật con dấu"}]}],
         "fallback": {"type": "whole"}},
    ])
    search_doc = {"wants": {"b0003.1": {"candidates": [], "code": "no_candidates"}}}
    choice_doc = {"wants": {}, "regions": {}}
    picks = awrite.resolve_picks(plan_doc, search_doc, choice_doc, books=[])

    lines = awrite.build_lines(inp, plan_doc, picks, got={}, failed={}, names={}, dropped=[], lost=set())
    line3 = next(ln for ln in lines if ln["beat"] == "b0003")
    # Falls back to whole painting
    assert len(line3["items"]) == 1
    assert line3["items"][0]["asset"] == "main"
    assert line3["items"][0]["role"] == "main"
    # missing is recorded
    assert len(line3["missing"]) == 1
    assert line3["missing"][0]["want"] == "b0003.1"


def test_old_plan_without_wider_behaves_as_before(tmp_path):
    # Old plan without wider field on context item
    ctx = shapes.PlanCtx(beats=BEATS, targets=["b0001", "b0002", "b0003"], existing_regions=EXISTING)
    old_plan = plan(regions=[], lines=[
        {"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "kinds": ["whole"], "show": [{"type": "whole"}]},
        {"beat": "b0002", "reason": "Chi tiết tấm gương.", "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
        {"beat": "b0003", "reason": "Chân dung họa sĩ.", "kinds": ["outside"],
         "show": [{"type": "context", "search": "Jan van Eyck portrait", "alt": ["van Eyck self portrait"],
                   "kind": "portrait", "entity": "Jan van Eyck", "period": "then", "what": "Chân dung họa sĩ"}],
         "fallback": {"type": "whole"}},
    ])
    rep = shapes.check_plan(old_plan, ctx)
    assert rep.ok, rep.text()

    wants = shapes.wants_of(old_plan)
    assert "wider" not in wants[0]

    pdir = make_auto_project(tmp_path, "w_old")
    from bti.picks.auto import inputs as ainputs
    inp = ainputs.load(pdir, redo=True, need_targets=False)

    search_doc = {
        "wants": {
            "b0003.1": {
                "id": "b0003.1", "beat": "b0003", "n": 1, "type": "context", "kind": "portrait", "what": "Chân dung",
                "candidates": [
                    {"n": 1, "source": "commons", "source_id": "P1", "title": "Portrait",
                     "author": "Painter", "licence": "PD", "flag": None, "width": 800, "height": 600,
                     "page_url": "https://example.org", "thumb": None, "media": "image"}
                ]
            }
        }
    }
    choice_doc = {"wants": {"b0003.1": {"pick": ("c", 1), "reason": "Chân dung đúng người."}}, "regions": {}}
    picks = awrite.resolve_picks(old_plan, search_doc, choice_doc, books=[])
    assert "step" not in picks["b0003.1"]

    lines = awrite.build_lines(inp, old_plan, picks, got={("commons", "P1"): "media/p1.png"}, failed={}, names={}, dropped=[], lost=set())
    line3 = next(ln for ln in lines if ln["beat"] == "b0003")
    assert "step" not in line3["items"][0]


def test_draft_inputs_beat_picks_carries_step():
    from bti.draft.inputs import beat_picks
    picks = {
        "assets": {"A": {"file": "media/a.png"}, "C1": {"file": "media/c1.png"}},
        "beats": {
            "b0001": {
                "items": [
                    {"asset": "C1", "role": "context", "note": "Miniature", "step": 2}
                ]
            },
            "b0002": {
                "items": [
                    {"asset": "A", "role": "main", "note": "Main painting"}
                ]
            }
        }
    }
    items1 = beat_picks(picks, "b0001")
    assert len(items1) == 1
    assert items1[0]["step"] == 2

    items2 = beat_picks(picks, "b0002")
    assert len(items2) == 1
    assert "step" not in items2[0]


def test_round_two_web_search_of_thing_itself_runs_first_with_wider(tmp_path):
    pdir = make_auto_project(tmp_path, "w_web_first")
    want = {
        "id": "b0003.1", "beat": "b0003", "n": 1, "type": "context", "kind": "portrait", "period": "then",
        "search": "Jan van Eyck portrait", "alt": ["van Eyck painter"], "what": "Chân dung Jan van Eyck",
        "wider": [
            {"step": 2, "search": "15th-century painter portrait miniature", "kind": "portrait", "what": "Tiểu họa"},
            {"step": 3, "search": "painter badge guild museum", "kind": "object", "what": "Huy hiệu"}
        ]
    }
    st = asearch.new_state()
    st["wants"][want["id"]] = asearch._new_want(want)

    def fake_search(pdir, q, offset, sources, limit, kind="image"):
        if "miniature" in q:
            return {"items": [{"source": "commons", "source_id": f"step2_{i}", "title": f"Miniature {i}",
                               "thumb_url": f"t2_{i}.jpg", "mime": "image/jpeg", "width": 800, "height": 600}
                              for i in range(1, 5)], "errors": []}
        if "museum" in q:
            return {"items": [{"source": "met", "source_id": f"step3_{i}", "title": f"Museum {i}",
                               "thumb_url": f"t3_{i}.jpg", "mime": "image/jpeg", "width": 800, "height": 600}
                              for i in range(1, 5)], "errors": []}
        return {"items": [], "errors": []}

    web = asearch.Web(on=True, max=10, spent=0)
    web_queries = []

    def fake_web_search(pdir, query, limit):
        web_queries.append(query)
        if query == "van Eyck painter":
            return {
                "items": [
                    {"source": "web", "source_id": f"web_{i}", "title": f"Van Eyck {i}",
                     "thumb_url": f"tw_{i}.jpg", "mime": "image/jpeg", "width": 800, "height": 600,
                     "page_url": f"https://example.com/item{i}"}
                    for i in range(1, 7)
                ],
                "errors": []
            }
        return {"items": [], "errors": []}

    web.search = fake_web_search

    def fake_thumb(pdir, c, limited, clock):
        return "thumb.jpg"

    choice = {"wants": {"b0003.1": {"pick": None, "reason": "null"}}, "regions": {}}

    res_st = webround.search_round_two(
        pdir, [want], st, choice, main_key="A", web=web, fetch_thumb=fake_thumb,
        clock=lambda: 1000.0, cancelled=lambda: False, progress=lambda p, s: None,
        save=lambda s: None, search=fake_search, wiki_search=fake_search
    )
    assert "van Eyck painter" in web_queries
    assert "15th-century painter portrait miniature" in web_queries
    cands = res_st["wants"]["b0003.1"]["candidates"]

    # Total candidates capped at 8
    assert len(cands) == 8
    # The thing itself got up to 4 candidates, and they COME FIRST
    assert [c["source_id"] for c in cands[:4]] == ["web_1", "web_2", "web_3", "web_4"]
    for c in cands[:4]:
        assert "step" not in c or c.get("step") == 1

    # Remaining 4 slots shared by step 2 and step 3 (step 2 gets min(4, 4) = 4)
    assert [c["source_id"] for c in cands[4:]] == ["step2_1", "step2_2", "step2_3", "step2_4"]
    for c in cands[4:]:
        assert c["step"] == 2


