"""docs/AGENT_API.md: the generated parts are the code's, the hand-written example has the keys the real answer has."""
import json
import re

from bti.editor import hints, state_api
from state_helpers import action, build, make_book_project


def doc_text():
    return hints.DOC_PATH.read_text(encoding="utf-8")


def test_the_generated_parts_are_not_stale():
    text = doc_text()
    assert hints.render_doc(text) == text, "docs/AGENT_API.md is stale: run `python -m bti.editor.hints`"
    assert hints.main(["--check"]) == 0


def test_every_action_id_every_need_and_every_code_is_in_the_document():
    text = doc_text()
    for spec in state_api.SPECS:
        assert "| `%s` |" % spec.id in text, spec.id
    for need in state_api.NEEDS:
        assert "| `%s` |" % need in text, need
    for code in hints.HINTS:
        assert "| `%s` |" % code in text, code


def test_every_action_has_a_condition_in_words_and_a_vietnamese_label():
    ids = [s.id for s in state_api.SPECS]
    assert len(ids) == len(set(ids))
    for s in state_api.SPECS:
        assert re.fullmatch(r"[a-z_]+\.[a-z_]+", s.id) and s.when.endswith(".") and s.label, s.id
        assert re.search(r"[À-ỹ]", s.label) or s.label in ("Sửa chọn hình",), s.label


def test_the_example_in_the_document_has_the_keys_of_the_real_answer(client, root, monkeypatch):
    block = re.search(r"```json\n(\{\n  \"project\".*?)\n```", doc_text(), re.S).group(1)
    example = json.loads(block)
    make_book_project(root)
    build("picks_approved", client, monkeypatch)
    real = client.get("/api/projects/arn/state").json()
    assert set(example) == set(real)
    assert set(example["steps"][0]) == set(real["steps"][0])
    ex = {a["id"]: a for a in example["next_actions"]}
    for aid, a in ex.items():
        got = action(real, aid)
        assert set(a) == set(got), (aid, set(a) ^ set(got))
        assert a["method"] == got["method"] and a["path"] == got["path"]
    assert example["steps"][4]["state"] == real["steps"][4]["state"] and example["current"] == real["current"]
