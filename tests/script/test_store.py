import json

import pytest

from bti.script import store
from script_helpers import make_narration, make_outline


def test_revision_ignores_approval_only():
    o = make_outline()
    r0 = o.rev()
    o.approval = {"approved": True, "sha1": "x", "approved_at": "y"}
    assert o.rev() == r0
    o.thesis += "!"
    assert o.rev() != r0


def test_save_load_roundtrip_and_atomic_file(tmp_path):
    n = make_narration()
    rev = store.save_narration(tmp_path, n)
    assert rev == n.rev() and (tmp_path / "script" / "narration.json").is_file()
    assert not list((tmp_path / "script").glob("*.tmp"))
    n2 = store.load_narration(tmp_path)
    assert n2.rev() == rev and n2.to_dict() == n.to_dict()
    d = json.loads((tmp_path / "script" / "narration.json").read_text())
    assert d["schema"] == "bti.narration/1" and d["chapters"][0]["beats"][0]["id"] == "b0001"
    o = make_outline()
    store.save_outline(tmp_path, o)
    assert json.loads((tmp_path / "script" / "outline.json").read_text())["schema"] == "bti.outline/1"
    assert store.load_outline(tmp_path).rev() == o.rev()


def test_approval_is_tied_to_the_hash_and_dropped_by_any_edit(tmp_path):
    n = make_narration()
    rev = store.save_narration(tmp_path, n)
    ap = store.approve(tmp_path, "narration", rev)
    assert ap["approved"] and ap["sha1"] == rev
    loaded = store.load_narration(tmp_path)
    assert loaded.approved_fresh()
    loaded.chapters[0].beats[0].text += " more"                       # any edit
    new_rev = store.save_narration(tmp_path, loaded, rev)
    again = store.load_narration(tmp_path)
    assert new_rev != rev and not again.approval["approved"] and again.approval["sha1"] is None
    assert not again.approved_fresh()


def test_stale_approval_is_detected_when_the_file_changed_behind_our_back(tmp_path):
    n = make_narration()
    rev = store.save_narration(tmp_path, n)
    store.approve(tmp_path, "narration", rev)
    p = tmp_path / "script" / "narration.json"
    d = json.loads(p.read_text())
    d["chapters"][0]["beats"][0]["text"] = "edited by hand"
    p.write_text(json.dumps(d))
    assert store.load_narration(tmp_path).approval["approved"] is True
    assert store.load_narration(tmp_path).approved_fresh() is False        # stale: hash differs
    with pytest.raises(store.StaleRevision):
        store.approve(tmp_path, "narration", rev)                          # the old rev cannot be approved


def test_save_with_wrong_base_rev_is_refused(tmp_path):
    n = make_narration()
    rev = store.save_narration(tmp_path, n)
    n.chapters[0].beats[0].text = "x"
    with pytest.raises(store.StaleRevision):
        store.save_narration(tmp_path, n, "0" * 40)
    store.save_narration(tmp_path, n, rev)


def test_ids_are_never_reused(tmp_path):
    n = make_narration()
    assert [b.id for c in n.chapters for b in c.beats] == [f"b{i:04d}" for i in range(1, 7)]
    n.chapters[2].beats.pop()                                              # delete the highest id
    assert n.new_beat_id() == "b0007"
    store.save_narration(tmp_path, n)
    assert store.load_narration(tmp_path).new_beat_id() == "b0008"          # the counter survives a reload
    o = make_outline()
    assert o.to_dict()["counters"] == {"chapter": 3, "fact": 2}


def test_tolerant_loading_of_odd_documents():
    n = store.Narration.from_dict({"chapters": [{"id": "c01", "beats": [{"text": "a"}, {"id": "b0009", "text": "b", "facts": "f01"}]}]})
    ids = [b.id for b in n.chapters[0].beats]
    assert ids == ["b0010", "b0009"] or ids[1] == "b0009" and ids[0] != "b0009"
    assert n.chapters[0].beats[1].facts == ["f01"]
    o = store.Outline.from_dict({"chapters": [{"id": "c1", "role": "weird", "word_budget": "120"}], "facts": [{"id": "f1", "certainty": "??"}]})
    assert o.chapters[0].role == "chapter" and o.chapters[0].word_budget == 120 and o.facts[0].certainty == "likely"


def test_paste_files(tmp_path):
    assert store.read_paste(tmp_path, "narration") == ""
    store.keep_paste(tmp_path, "narration", "bad text")
    assert (tmp_path / "script" / "last_paste.txt").read_text() == "bad text"
    assert store.read_paste(tmp_path, "narration") == "bad text"
    store.clear_paste(tmp_path, "narration")
    assert store.read_paste(tmp_path, "narration") == ""
    store.clear_paste(tmp_path, "narration")                               # idempotent


def test_backup_of_the_previous_file(tmp_path):
    n = make_narration()
    store.save_narration(tmp_path, n)
    n.title = "changed"
    store.save_narration(tmp_path, n)
    assert json.loads((tmp_path / "script" / "narration.prev.json").read_text())["title"] == "The Test Painting"
