"""The registry: every operation is declared once, its schema is a real JSON Schema, its example passes it and applies on a
fixture project, the schema route serves it, and docs/OPS.md is what the registry says."""
import jsonschema
import pytest
from ops_helpers import PID, pk, sb

from bti.ops import doc as opsdoc
from bti.ops import registry, schemacheck
from bti.ops.errors import ERRORS

PICKS = ["set_subjects", "set_about", "set_main", "set_region", "remove_region", "set_picks", "add_pick", "remove_stale_beats", "remove_pick", "skip_beat", "import", "set_content_box", "clear_content_box"]
STORYBOARD = ["set_technique", "set_params", "set_slot", "add_overlay", "set_overlay", "remove_overlay", "split_shot", "merge_shots",
              "move_boundary", "replace_range", "lock", "unlock"]
ALL = [("picks", n) for n in PICKS] + [("storyboard", n) for n in STORYBOARD]


def test_every_operation_of_the_brief_is_registered():
    assert registry.names("picks") == PICKS
    assert registry.names("storyboard") == STORYBOARD


@pytest.mark.parametrize("doc,name", ALL)
def test_each_entry_is_complete(doc, name):
    d = registry.defs(doc)[name]
    assert d.name == name and d.doc == doc
    assert d.summary.endswith(".") and len(d.summary) > 20
    assert d.example["op"] == name
    assert d.sentences and all(isinstance(t, str) and "!" not in t for t in d.sentences.values())
    assert callable(d.fn)
    assert d.schema["properties"]["op"] == {"const": name, "description": "The operation name."}


@pytest.mark.parametrize("doc,name", ALL)
def test_schema_is_valid_json_schema(doc, name):
    jsonschema.Draft202012Validator.check_schema(registry.defs(doc)[name].schema)


@pytest.mark.parametrize("doc,name", ALL)
def test_example_passes_its_own_schema_in_both_checkers(doc, name):
    d = registry.defs(doc)[name]
    assert list(jsonschema.Draft202012Validator(d.schema).iter_errors(d.example)) == []
    assert schemacheck.validate(d.schema, d.example, "ops[0]") == []


@pytest.mark.parametrize("doc,name", ALL)
def test_example_applies_on_a_fixture_project(client, doc, name):
    d = registry.defs(doc)[name]
    r = (pk if doc == "picks" else sb)(client, [d.example])
    assert r.status_code == 200, r.text
    j = r.json()
    if name == "remove_stale_beats":            # the fixture's picks hold no line outside the narration: nothing to remove
        assert j["applied"] == 1
        return
    assert j["applied"] == 1 and j["batch"] and j["changes"] and j["changes"][0]["what"]
    assert all("!" not in c["what"] for c in j["changes"])


def test_the_checkers_agree_on_a_wrong_operation():
    """The schema means one thing to both checkers: a wrong operation fails in the same places."""
    d = registry.defs("storyboard")["split_shot"]
    for bad in ({"op": "split_shot", "shot": "s0004"}, {"op": "split_shot", "shot": 4, "at": 1}, {"op": "split_shot", "shot": "s0004", "at": -1},
                {"op": "split_shot", "shot": "s0004", "at": 1, "extra": 1}):
        assert list(jsonschema.Draft202012Validator(d.schema).iter_errors(bad)), bad
        assert schemacheck.validate(d.schema, bad, "ops[0]"), bad


def test_schema_route_has_every_operation(client):
    r = client.get("/api/ops/schema")
    assert r.status_code == 200
    j = r.json()
    assert list(j) == ["picks", "storyboard"]
    assert list(j["picks"]) == PICKS and list(j["storyboard"]) == STORYBOARD
    for doc in j.values():
        for name, entry in doc.items():
            assert set(entry) == {"summary", "schema", "example"}
            jsonschema.Draft202012Validator.check_schema(entry["schema"])
            assert entry["example"]["op"] == name


def test_docs_ops_md_is_current():
    assert opsdoc.OPS_MD.is_file(), "docs/OPS.md is missing: run python -m bti.ops.doc"
    assert opsdoc.OPS_MD.read_text(encoding="utf-8") == opsdoc.render(), "docs/OPS.md is out of date: run python -m bti.ops.doc"


def test_docs_mention_every_operation_and_every_error_code():
    text = opsdoc.render()
    for _, name in ALL:
        assert "### `%s`" % name in text
    for code in ERRORS:
        assert "| `%s` |" % code in text
    assert "/api/projects/{pid}/picks/ops" in text and "/api/projects/{pid}/changes/{batch}/undo" in text


def test_every_error_code_has_status_retry_and_an_imperative_fix():
    for code, (status, retry, fix, meaning) in ERRORS.items():
        assert 400 <= status < 600 and retry in ("no", "after_fix", "later")
        assert fix[0].isupper() and fix.endswith(".") and meaning.endswith("."), code


def test_the_project_helper_is_what_the_examples_assume(client):
    assert PID == "ops1"
