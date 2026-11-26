"""What the model is given by the prompt box of step 5 (worker c2box): the operations rendered from the registry, only the scope's shots with
their two neighbours, the pictures and regions they can use, a catalogue reduced to what a small edit needs, the rules; and how big that is."""
from __future__ import annotations

import json

import pytest

from bti.draft import boxops, fastedit
from bti.draft.inputs import load_inputs
from bti.ops import registry

ASK = "làm vòng sáng ở cảnh này to hơn"


def briefing(box, payload, instruction=ASK, turns=None):
    be = boxops.Backend(box.pdir)
    inp = load_inputs(box.pdir, for_edit=True)
    doc, _ = be.read("storyboard")
    scope = fastedit.storyboard_scope(inp, doc, payload)
    return fastedit.build_briefing(inp, doc, be.adapter("storyboard").facts(doc), scope, instruction, turns), scope


def test_the_operations_are_rendered_from_the_registry_and_only_the_useful_ones(box):
    text, _ = briefing(box, {"shots": ["s0004"]})
    names = boxops.allowed_ops("storyboard")
    assert names == ["set_technique", "set_params", "set_slot", "add_overlay", "set_overlay", "remove_overlay", "split_shot", "merge_shots", "move_boundary"]
    table = registry.defs("storyboard")
    for name in names:
        assert "### %s: " % name in text
        assert json.dumps(table[name].example, ensure_ascii=False, separators=(",", ":")) in text           # the registry's own example, verbatim
        for field in table[name].schema["properties"]:
            if field != "op":
                assert "`%s`" % field in text, (name, field)                                              # every field of its schema
    for name in ("lock", "unlock", "replace_range"):
        assert "### %s: " % name not in text                                                              # not offered to the model
    assert "set_technique: " in text and "Change the technique of a shot" in table["set_technique"].summary and "Change the technique of a shot" in text


def test_a_change_of_the_registry_changes_the_briefing(box, monkeypatch):
    """Nothing about an operation is written by hand in the briefing: a summary changed in the registry is in the briefing."""
    d = registry.defs("storyboard")["remove_overlay"]
    monkeypatch.setitem(registry._OPS["storyboard"], "remove_overlay", type(d)(**{**d.__dict__, "summary": "Take an overlay off a shot, thoroughly."}))
    text, _ = briefing(box, {"shots": ["s0004"]})
    assert "Take an overlay off a shot, thoroughly." in text


def test_only_the_scopes_shots_and_their_two_neighbours_are_in_it(box):
    text, scope = briefing(box, {"shots": ["s0004"]})
    shots = text.split("### The shots in scope")[1].split("### The shot before")[0]
    assert '"id":"s0004"' in shots and '"STATIC-02"' in shots and "WINTER LANDSCAPE" in shots                  # its overlay, with its data
    for other in ("s0001", "s0002", "s0003", "s0005", "s0009", "s0010"):
        assert other not in shots
    near = text.split("### The shot before and the shot after the scope")[1].split("### The words")[0]
    assert '"id":"s0003"' in near and '"id":"s0005"' in near and "s0009" not in near
    assert "s0009" not in text and "s0010" not in text                                                       # nothing else of the storyboard
    assert scope.ids == ["s0004"] and scope.ops == {"shots": ["s0004"]}


def test_a_locked_shot_is_shown_as_locked_and_stays_in_the_selection_for_the_server_to_refuse(box):
    text, scope = briefing(box, {"shots": ["s0005", "s0006"]})
    assert '"id":"s0006"' in text and '"locked":true' in text
    assert scope.ids == ["s0005", "s0006"] and scope.editable == ["s0005"]


def test_the_pictures_with_their_regions_and_the_other_pictures_are_listed(box):
    # fixdraft: the others are only the pictures that a line of the narration has; in this fixture C (a detail) is put on a line, D (another work) is on none
    import json
    f = box.pdir / "picks.json"
    pk = json.loads(f.read_text(encoding="utf-8"))
    pk["beats"]["b0003"]["items"].append({"asset": "C", "region": None, "role": "detail", "note": ""})
    f.write_text(json.dumps(pk), encoding="utf-8")
    text, _ = briefing(box, {"shots": ["s0004"]})
    pics = text.split("### The pictures and their named regions")[1].split("## The techniques")[0]
    assert '"B":{"title":"Test landscape"' in pics and '"CENTRE":{"label":"Centre","x":800' in pics            # used by the scope: regions with their numbers
    assert "Other pictures of the project" in pics and "Test portrait" in pics                                 # the others, by title
    assert "Test detail" in pics.split("Other pictures of the project")[1] and "Test other work" not in pics     # D belongs to no line: not offered
    assert "the main picture A" in pics


def test_the_catalogue_is_reduced_to_what_a_small_edit_needs(box):
    text, _ = briefing(box, {"shots": ["s0004"]})
    cat = text.split("## The techniques you may choose from")[1].split("## How the usual requests")[0]
    assert "### CAM-01" in cat and "### STATIC-02" in cat and "### HI-01" in cat and "### AN-01" in cat      # on the scope's shot, and the usual overlays
    assert "- CAM-03 " in cat                                                                                  # a core treatment, in one line
    for gone in ("ID-OPEN-01", "ID-BRAND-01", "ID-BRAND-03", "ID-BRAND-04", "SHORT-01", "MAP-01", "TIME-01", "KEY-01", "NUM-01", "DOC-01", "STATE-01", "TREE-01"):
        assert "### %s " % gone not in cat and "- %s " % gone not in cat, gone                               # identity, shorts-only, devices nobody asked for (a use text may name them: "use KEY-01 instead")
    assert "- use when:" in cat and "- never when:" in cat                                                     # catalogue pass: the full entries say when to use a technique and when never
    for hidden in ("### X-HI-01", "### CAM-06", "- CAM-06 ", "### STATIC-04"):
        assert hidden not in cat, hidden                                                                       # hidden from the models: not listed unless a shot of the scope has it


@pytest.mark.parametrize("ask,device", [("thêm bản đồ cho nơi nói đến ở cảnh này", "MAP-01"), ("hiện mốc năm 1434 trên dòng thời gian", "TIME-01"),
                                        ("làm sáng dòng chữ ký ở góc tranh", "DOC-01"), ("so sánh con số 600 và 2000", "NUM-01")])
def test_an_explanatory_device_is_described_only_when_the_request_is_about_its_kind_of_point(box, ask, device):
    text, _ = briefing(box, {"shots": ["s0004"]}, ask)
    cat = text.split("## The techniques you may choose from")[1].split("## How the usual requests")[0]
    assert "### %s" % device in cat and "Explanatory devices the request is about" in cat
    other, _ = briefing(box, {"shots": ["s0004"]}, ASK)
    assert "### %s" % device not in other


def test_the_rules_are_in_the_briefing(box):
    text, _ = briefing(box, {"shots": ["s0004"]})
    for rule in ("the only ones you may change; never a `locked` one", "**only when the owner's sentence asks for that kind of point**",
                 "**Never guess a fact.**", "everything you do not touch stays as it is", "ONE JSON object", '"status": "applied" | "cannot" | "escalate"'):
        assert rule in text, rule
    assert "plain words, in Vietnamese" in text and "plain words, in English" not in text


def test_an_english_request_gets_an_english_briefing_header(box):
    text, _ = briefing(box, {"shots": ["s0004"]}, "make the label bigger please")
    assert "plain words, in English" in text and "plain words, in Vietnamese" not in text and "say it in English" in text


def test_the_last_turns_of_the_thread_are_in_it(box):
    turns = [{"instruction": "lần một", "summary": "Đã đổi lần một.", "status": "applied", "doc": "storyboard"},
             {"instruction": "chọn hình", "summary": "x", "status": "applied", "doc": "picks"}]
    text, _ = briefing(box, {"shots": ["s0004"]}, "làm tương tự", turns)
    assert "lần một" in text and "Đã đổi lần một." in text and "chọn hình" not in text.split("## The last turns")[1].split("## The answer")[0]


@pytest.mark.parametrize("payload,limit", [({"shots": ["s0004"]}, 27_500), ({"shots": ["s0002", "s0004"]}, 29_500), ({"chapter": "c02"}, 33_500),
                                           ({"all": True}, 38_000)])           # catalogue pass: +1,500 for `use when` and `never when` of the techniques of the scope
def test_the_briefing_stays_under_its_size(box, payload, limit):
    """Measured on the fixture project (tests/draft/measure_briefing.py prints the parts): about 22 000 characters for one shot."""
    text, scope = briefing(box, payload)
    assert len(text) < limit, (len(text), len(scope.ids))


def test_the_briefing_size_on_the_real_arnolfini_copy(arnolfini):
    from box_helpers import REPO  # noqa: F401
    be = boxops.Backend(arnolfini)
    inp = load_inputs(arnolfini, for_edit=True)
    doc, _ = be.read("storyboard")
    ids = [s["id"] for s in doc["shots"]]
    scope = fastedit.storyboard_scope(inp, doc, {"shots": ids[10:22]})
    text = fastedit.build_briefing(inp, doc, be.adapter("storyboard").facts(doc), scope, "làm chậm cú zoom ở các cảnh này", [])
    assert len(text) < 42_000, (len(text), len(scope.ids))
    one = fastedit.build_briefing(inp, doc, be.adapter("storyboard").facts(doc), fastedit.storyboard_scope(inp, doc, {"shots": ids[10:11]}), "làm chậm", [])
    assert len(one) < 28_000, len(one)
