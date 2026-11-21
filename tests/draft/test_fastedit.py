"""The pure parts of the prompt box (worker c2box): the answer of the model (JSON, shape, the owner's language), the sentences of a refusal, the
rendering of an operation from its schema, the scope of the storyboard box. The turn itself (dry run, repair, batch) is tested through the
routes in `test_box_storyboard.py`; the briefing in `test_box_briefing.py`. Nothing here calls a model."""
from __future__ import annotations

import json

import pytest

from bti.draft import boxops as B
from bti.draft import fastedit
from bti.draft.inputs import DraftError, load_inputs


# ---------------------------------------------------------------------------------------------------------------- the answer
def test_extract_json_reads_a_fence_and_words_around_the_object():
    data, err = B.extract_json('Đây là kết quả:\n```json\n{"status": "cannot", "reason": "Không làm được."}\n```\nHết.')
    assert err is None and data["status"] == "cannot"
    assert B.extract_json("not json")[0] is None and "JSON parse error" in B.extract_json("not json")[1]
    assert B.extract_json("[1, 2]")[0] is None


@pytest.mark.parametrize("data,problem", [
    ({"status": "edit"}, "`status` must be one of"),
    ({"status": "cannot"}, "needs a non-empty `reason`"),
    ({"status": "escalate", "reason": "  "}, "needs a non-empty `reason`"),
    ({"status": "applied", "summary": "Đã sửa.", "ops": []}, "needs `ops`"),
    ({"status": "applied", "summary": "Đã sửa.", "ops": ["lock"]}, "must be an object"),
    ({"status": "applied", "summary": "", "ops": [{"op": "x"}]}, "needs `summary`"),
    ({"status": "applied", "summary": "Đã sửa.", "ops": [{"op": "x"}] * 41}, "send at most"),
])
def test_a_wrong_shape_is_named(data, problem):
    assert any(problem in p for p in B.check_shape(data)), B.check_shape(data)


def test_a_good_shape_has_no_problem():
    assert B.check_shape({"status": "applied", "summary": "Đã sửa.", "ops": [{"op": "set_params"}]}) == []
    assert B.check_shape({"status": "cannot", "reason": "Cần chọn thêm cảnh sau."}) == []


@pytest.mark.parametrize("text,lang", [("làm chậm cú zoom", "vi"), ("lam cham cu zoom o canh nay", "vi"), ("zoom", "vi"), ("", "vi"),
                                       ("make the ring around the mirror bigger", "en"), ("add a label to this shot please", "en"),
                                       ("them nhan cho canh nay va bo vong", "vi")])
def test_the_owners_language(text, lang):
    assert B.owner_language(text) == lang


def test_a_sentence_for_a_vietnamese_owner_must_be_plain_vietnamese():
    ok = "Máy quay ở cảnh này đi chậm hơn."
    assert B.sentence_problem(ok, "vi") is None
    for bad in ("The camera is slower.", "Làm chậm zoom vào s0004.", "Thêm AN-01 quanh gương.", "Đổi zoom từ 0.4075 sang 0.385.", "", None):
        assert B.sentence_problem(bad, "vi"), bad
    assert B.sentence_problem("The camera is slower.", "en") is None and B.sentence_problem("Slower at s0004.", "en")


def test_the_sentence_of_a_refusal_is_plain_and_names_the_shot_by_its_number():
    doc = {"shots": [{"id": "s0001"}, {"id": "s0007"}]}
    assert "Cảnh 2 đang khóa" in B.refusal_words("storyboard", "locked", {"shot": "s0007"}, doc)
    assert "chưa chọn" in B.refusal_words("storyboard", "out_of_scope") and "chưa chọn" in B.refusal_words("picks", "out_of_scope")
    assert "không có trong storyboard" in B.refusal_words("storyboard", "unknown_shot")
    assert "không có trong danh sách hình" in B.refusal_words("picks", "unknown_asset")
    assert B.refusal_words("storyboard", "something_else") == B.REFUSAL_OTHER
    for kind in ("storyboard", "picks"):
        for code in list(B.REFUSALS[kind]) + ["unknown_op", "invalid_field"]:
            w = B.refusal_words(kind, code, {"shot": "s0001"}, doc)
            assert w.endswith(".") and "!" not in w and not any(x in w for x in (code, "s0001", "scope")), (kind, code, w)


def test_the_summary_made_by_code_is_the_batch_first_sentence():
    assert B.code_summary([]) == "Đã sửa theo yêu cầu."
    assert B.code_summary([{"what": "Cảnh 2: đổi thiết lập rx"}]) == "Cảnh 2: đổi thiết lập rx"
    assert B.code_summary([{"what": "Cảnh 2: a."}, {"what": "Cảnh 3: b"}, {"what": "Cảnh 4: c"}]) == "Cảnh 2: a. Và 2 thay đổi khác."


# ---------------------------------------------------------------------------------------------------------------- operations as text
def test_schema_types_are_rendered_compactly():
    from bti.ops import registry
    t = registry.defs("storyboard")["add_overlay"].schema["properties"]
    assert B.schema_type(t["shot"]) == "text" and B.schema_type(t["dur"]) == "number" and B.schema_type(t["params"]) == "object"
    assert B.schema_type(t["intent"]).startswith("one of establish|explore")
    assert B.schema_type(t["start"]).startswith("{")                                  # an anchor: its fields
    assert B.schema_type(registry.defs("picks")["set_picks"].schema["properties"]["items"]).startswith("list of {asset")


def test_a_description_given_once_is_not_repeated():
    text = B.render_ops("storyboard", B.allowed_ops("storyboard"))
    assert text.count("A shot id of the storyboard (such as s0012)") == 1
    assert text.count("### ") == 9


def test_the_picks_box_offers_the_whole_video_operations_only_to_the_whole_video():
    scoped = B.allowed_ops("picks")
    whole = B.allowed_ops("picks", whole_video=True)
    assert "import" not in scoped and "import" not in whole
    assert not set(B.WHOLE_VIDEO_PICKS) & set(scoped) and set(B.WHOLE_VIDEO_PICKS) <= set(whole)
    assert {"set_picks", "add_pick", "remove_pick", "skip_beat"} <= set(scoped)


# ---------------------------------------------------------------------------------------------------------------- the scope of the storyboard box
def test_the_scope_of_shots_chapter_and_all(box):
    be = B.Backend(box.pdir)
    doc, _ = be.read("storyboard")
    inp = load_inputs(box.pdir, for_edit=True)
    one = fastedit.storyboard_scope(inp, doc, {"shots": ["s0004"]})
    assert (one.kind, one.ids, one.editable, one.ops, one.words) == ("shots", ["s0004"], ["s0004"], {"shots": ["s0004"]}, "1 cảnh đang chọn")
    two = fastedit.storyboard_scope(inp, doc, {"shots": ["s0005", "s0006"]})
    assert two.ids == ["s0005", "s0006"] and two.editable == ["s0005"]                 # the locked shot is in the selection, not editable
    chap = fastedit.storyboard_scope(inp, doc, {"chapter": "c02"})
    assert chap.kind == "chapter" and chap.ids == ["s0005", "s0006", "s0007", "s0008"] and chap.words.startswith("Chương: ")
    whole = fastedit.storyboard_scope(inp, doc, {"all": True})
    assert whole.kind == "all" and whole.words == "Cả video" and "s0001" in whole.ids and "s0010" in whole.ids


def test_a_scope_that_cannot_be_used_is_a_draft_error(box):
    be = B.Backend(box.pdir)
    doc, _ = be.read("storyboard")
    inp = load_inputs(box.pdir, for_edit=True)
    for payload in ({}, {"shots": []}, {"shots": ["s9999"]}, {"shots": ["s0006"]}, {"chapter": "nope"}, {"shots": ["s0001"], "all": True}):
        with pytest.raises(DraftError) as e:
            fastedit.storyboard_scope(inp, doc, payload)
        assert e.value.code in ("edit_bad_scope", "unknown_chapter"), payload


def test_the_scope_snapshot_tells_a_change_inside_the_scope_from_one_outside(box):
    be = B.Backend(box.pdir)
    doc, _ = be.read("storyboard")
    inp = load_inputs(box.pdir, for_edit=True)
    scope = fastedit.storyboard_scope(inp, doc, {"shots": ["s0004"]})
    snap = B.scope_snapshot("storyboard", doc, scope)
    elsewhere = json.loads(json.dumps(doc))
    elsewhere["shots"][8]["note"] = "x"
    inside = json.loads(json.dumps(doc))
    inside["shots"][3]["note"] = "x"
    assert B.scope_snapshot("storyboard", elsewhere, scope) == snap and B.scope_snapshot("storyboard", inside, scope) != snap
