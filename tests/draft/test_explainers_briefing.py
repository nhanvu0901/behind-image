"""What the storyboard agents read about the explanatory devices (`MAP-01`, `TIME-01`, `TREE-01`, `STATE-01`, `KEY-01`, `NUM-01`, `DOC-01`):
the catalogue prints their fields and ONE filled example taken from the registry defaults, and the three briefings (draft, chapter and edit through
`TASK.template.md`; the fast edit through `FAST.template.md`) carry one short part that says which kind of sentence each serves and how to use them."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bti.draft import techniques_md
from bti.draft import workspace as W
from bti.draft.inputs import load_inputs
from bti.engine import registry as R

REPO = Path(__file__).resolve().parents[2]
TASK = (REPO / "skills" / "storyboard_draft" / "TASK.template.md").read_text(encoding="utf-8")
FAST = (REPO / "skills" / "storyboard_edit" / "FAST.template.md").read_text(encoding="utf-8")
SEVEN = ("MAP-01", "KEY-01", "TIME-01", "NUM-01", "TREE-01", "STATE-01", "DOC-01")


def section(md: str, tid: str) -> str:
    i = md.index("### %s " % tid)
    j = md.find("\n### ", i + 5)
    return md[i:j if j > 0 else len(md)]


def example_of(md: str, tid: str) -> dict:
    line = next(l for l in section(md, tid).splitlines() if l.startswith("- example"))
    assert "replace ALL" in line
    return json.loads(line.split(": ", 1)[1] if line.count(": ") == 1 else line[line.index("): ") + 3:])


@pytest.fixture(scope="module")
def md():
    return techniques_md.generate(R.load_bundle("gae"))


@pytest.mark.parametrize("tid", SEVEN)
def test_the_catalogue_prints_the_fields_and_one_filled_example_that_the_registry_accepts(md, tid):
    sec = section(md, tid)
    sp = R.load_bundle("gae").spec(tid)
    assert sec.count("- example") == 1
    ex = example_of(md, tid)
    assert ex, tid
    assert not R.validate_params(sp, ex, "p") or all(i["level"] != "error" for i in R.validate_params(sp, ex, "p")), R.validate_params(sp, ex, "p")
    for p in sp["params"]:
        if p["type"] == "items":
            assert p["name"] + ":items(" in sec, "the fields of every list are printed"
            for f in p["fields"]:
                assert f["name"] + ":" + f["type"] in sec, (tid, p["name"], f["name"])
            assert p["name"] in ex and len(ex[p["name"]]) == len(p["default"])
            for it in ex[p["name"]]:
                for f in p["fields"]:
                    if f.get("required"):
                        assert f["name"] in it, (tid, f["name"])
                assert all(k in {f["name"] for f in p["fields"]} for k in it)
    assert len(json.dumps(ex)) < 2600, "an example stays short: it is read on every call"
    assert "- when:" in sec and sp["usage_rule"][:40] in sec


def test_the_examples_are_the_registry_defaults_with_the_filled_in_fields_left_out(md):
    t = example_of(md, "TIME-01")
    assert [x["date"] for x in t["items"]] == [1425, 1426, 1431, 1432, 1433, 1434] and t["items"][-1]["accent"] is True and "side" not in t["items"][0]
    tr = example_of(md, "TREE-01")
    assert [n["id"] for n in tr["nodes"]] == ["duke", "jan", "fam", "gio", "cos", "pic"] and "row" not in tr["nodes"][0]
    assert any(e.get("kind") == "marriage" and e["label"] == "married 1426" for e in tr["edges"])
    st = example_of(md, "STATE-01")
    assert st == {"label_a": "Colour", "label_b": "Infrared", "holds": "1.5; 2.5; 1.5"}
    mp = example_of(md, "MAP-01")
    assert [p["id"] for p in mp["places"]] == ["bruges", "lucca"] and mp["region_iso"] == ["BE"] and mp["route"][0]["from"] == "bruges"
    ky = example_of(md, "KEY-01")
    assert [x["ref"] for x in ky["labels"]] == ["LIT", "INSCR", "MIRROR", "AMBER", "BRUSH"] and ky["labels"][1]["side"] == "n" and all("style" not in x for x in ky["labels"])
    nm = example_of(md, "NUM-01")
    assert [(r["value"], r["count"]) for r in nm["rows"]] == [("600", 12), ("2,000", 40)] and nm["caption"] == "each dot is fifty squirrel pelts"
    dc = example_of(md, "DOC-01")
    assert dc["lit"] == [{"ref": "INSCR"}] and dc["reading"] == "Jan van Eyck was here. 1434" and dc["original"].startswith("Johannes de eyck")


def test_no_other_technique_gets_an_example_line(md):
    assert md.count("- example (the defaults; replace ALL of its data):") == len([t for t in R.load_bundle("gae").techniques if t["id"].startswith(techniques_md.EXPLAINER_FAMILIES)])
    assert "- example" not in section(md, "CAM-01")


def test_the_intent_index_serves_the_new_techniques(md):
    idx = md.split("## The techniques")[0]
    assert "TIME-01" in next(l for l in idx.splitlines() if l.startswith("- **quantify**"))
    assert "TREE-01" in next(l for l in idx.splitlines() if l.startswith("- **context**")) and "TIME-01" in next(l for l in idx.splitlines() if l.startswith("- **context**"))
    assert "STATE-01" in next(l for l in idx.splitlines() if l.startswith("- **compare**")) and "STATE-01" in next(l for l in idx.splitlines() if l.startswith("- **reveal**"))
    line = lambda intent: next(l for l in idx.splitlines() if l.startswith("- **%s**" % intent))
    assert "KEY-01" in line("point_at") and "KEY-01" in line("context") and "DOC-01" in line("point_at") and "DOC-01" in line("isolate") and "DOC-01" in line("context")
    assert "NUM-01" in line("quantify") and "NUM-01" in line("context")


def part(text: str) -> str:
    i = text.index("Explanatory devices (")
    ends = [text.index(m, i + 10) for m in ("\n\n", "\n- **") if m in text[i + 10:]]
    return text[i:min(ends) if ends else len(text)]


@pytest.mark.parametrize("text,name", [(TASK, "task"), (FAST, "fast")])
def test_the_briefings_carry_the_part_on_explanatory_devices(text, name):
    p = part(text)
    for tid in SEVEN:
        assert "`%s`" % tid in p, (name, tid)
    for need in ("decoration", "ANY place", "STATIC-06", "AN-04", "X-ANN-05", "the word that names it", "never guess", "6 to 12"):
        assert need in p, (name, need)
    assert "`at`" in p and '"w"' in p, "each item is tied to the word that names it"
    assert "only from the narration and the project's sources" in p


def test_the_task_part_says_which_kind_of_sentence_each_device_serves_and_that_an_example_is_only_a_template():
    p = part(TASK)
    for kind in ("a place, a journey or a territory", "events with dates", "who is related to whom", "names for parts of the picture", "a figure", "the same picture in two states", "one line of a document"):
        assert kind in p, kind
    assert "replace all of its data" in p and "inputs/techniques.md" in p
    assert "never two in a row" in p and "general talk" in p


def test_the_fast_part_says_when_to_answer_cannot():
    p = part(FAST)
    assert "`cannot`" in p and "`escalate`" in p and "second picture" in p


def test_the_briefings_stay_short():
    """The part is read on every call: the templates may not grow by more than 1.6 KB (task) and 1.2 KB (fast) over their size before the part (22,250 and 10,498 bytes)."""
    assert len(part(TASK).encode("utf-8")) < 1900 and len(part(FAST).encode("utf-8")) < 1300
    assert len(TASK.encode("utf-8")) < 22250 + 1700 and len(FAST.encode("utf-8")) < 10498 + 1300


def test_the_rendered_task_of_a_draft_and_of_an_edit_holds_the_part(proj, tmp_path):
    inp = load_inputs(proj)
    ws = W.build(inp, root=tmp_path / "ws")
    t = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "{{" not in t and "Explanatory devices (" in t and "- example (the defaults; replace ALL of its data):" in (ws.root / "inputs" / "techniques.md").read_text(encoding="utf-8")
    ws2 = W.build(inp, root=tmp_path / "ws2", instruction="x", scope_words="chapter 1")
    t2 = (ws2.root / "TASK.md").read_text(encoding="utf-8")
    assert "Explanatory devices (" in t2 and "Mode: **edit**" in t2


def test_the_fast_edit_prompt_holds_the_part_and_the_catalogue_with_the_examples():
    from bti.draft import fastedit
    src = Path(fastedit.__file__).read_text(encoding="utf-8")
    assert "FAST.template.md" in src and "TECHNIQUES_MD" in src
    assert "- example (the defaults; replace ALL of its data):" in techniques_md.generate(R.load_bundle("gae"))
