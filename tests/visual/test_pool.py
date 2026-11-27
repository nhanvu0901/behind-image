import pytest
from bti.picks import doc
from bti.ops.batch import apply_ops
from bti.ops.facts import PicksFacts
from bti.ops.errors import OpError


def pool():
    d = doc.empty()
    d["main_asset"] = "A"
    d["assets"] = {"A": {"file": "a.jpg", "regions": {}}, "B": {"file": "b.jpg", "regions": {}}}
    return d


def test_pool_fields_survive_normalization_and_shape_check():
    d = pool()
    d["assets"]["B"].update(shows=["river"], period="then")
    assert doc.doc_problem(d) is None
    a = doc.normalize(d)["assets"]["B"]
    assert a["shows"] == ["river"] and a["period"] == "then"
    d["assets"]["B"]["period"] = "tomorrow"
    assert "period" in doc.doc_problem(d)


def test_set_picture_pool_fields_is_atomic(tmp_path):
    d = pool()
    result = apply_ops("picks", d, [{"op": "set_picture_info", "asset": "B", "shows": ["river"], "period": "then"}], PicksFacts(tmp_path), actor="agent:test")
    assert result.doc["assets"]["B"]["shows"] == ["river"]
    assert result.doc["assets"]["B"]["period"] == "then"
    assert "shows" not in d["assets"]["B"]
    with pytest.raises(OpError):
        apply_ops("picks", d, [{"op": "set_picture_info", "asset": "B", "shows": ["river"], "period": "bad"}], PicksFacts(tmp_path), actor="agent:test")


def test_replanning_line_keeps_unused_picture(tmp_path):
    d = pool()
    d["beats"] = {"b0001": {"items": [{"asset": "B", "region": None, "role": "context", "note": ""}], "status": "picked", "note": ""}}
    result = apply_ops("picks", d, [{"op": "skip_beat", "beat": "b0001", "reason": "Changed plan"}], PicksFacts(tmp_path), actor="agent:test")
    assert "B" in result.doc["assets"]
