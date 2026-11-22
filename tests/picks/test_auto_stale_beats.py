from auto_helpers import make_auto_project
from bti.picks import doc
from bti.picks.auto import inputs, write


def run_writer(tmp_path, limited):
    pdir = make_auto_project(tmp_path)
    picks = doc.load_or_new(pdir)
    item = {"asset": "A", "region": None, "role": "main", "note": ""}
    for bid in ("b0001", "b0002", "b0098", "b0099"):
        picks["beats"][bid] = {"items": [item.copy()], "status": "picked", "note": ""}
    picks["names"] = [{"name": "Old", "also": [], "line": "b0098", "where": {"asset": "A"}, "sure": True, "words": ""}]
    with doc.Held(pdir):
        doc.save(pdir, picks)
    inp = inputs.load(pdir, ["b0003"] if limited else None)
    plan = {"lines": [{"beat": "b0003", "reason": "Whole painting", "show": [{"type": "whole"}]}], "regions": {}}
    result = write.run(pdir, inp, plan, {}, {}, {}, actor="agent:test", cancelled=lambda: False,
                       progress=lambda *_: None, save_run=lambda _: None)
    return doc.load_or_new(pdir), result


def test_full_run_removes_old_lines_and_their_names(tmp_path):
    picks, result = run_writer(tmp_path, False)
    assert set(picks["beats"]) == {"b0001", "b0002", "b0003"}
    assert picks["names"] == []
    assert result["lines_removed"] == 2
    assert result["batches"]


def test_limited_run_keeps_old_lines_and_names(tmp_path):
    picks, result = run_writer(tmp_path, True)
    assert set(picks["beats"]) == {"b0001", "b0002", "b0003", "b0098", "b0099"}
    assert picks["names"][0]["line"] == "b0098"
    assert result["lines_removed"] == 0
