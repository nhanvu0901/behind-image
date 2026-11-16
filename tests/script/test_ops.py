import pytest

from bti.script import ops
from bti.script.store import Narration
from script_helpers import make_narration


def beats(n, cid):
    return [b.id for b in n.chapter(cid).beats]


def test_split_at_a_word_makes_a_fresh_id_and_never_renumbers():
    n = make_narration()
    before = {b.id: b.text for c in n.chapters for b in c.beats}
    b = n.chapter("c02").beats[0]
    b.text = "One two three four five six."
    new = ops.split_beat(n, b.id, 3)
    assert new == "b0007" and beats(n, "c02") == ["b0003", "b0007", "b0004"]
    assert b.text == "One two three" and n.find_beat(new)[0].beats[1].text == "four five six."
    assert n.find_beat(new)[0].beats[1].facts == ["f01"]
    assert {i: t for i, t in before.items() if i not in ("b0003",)} == {i: t for c in n.chapters for x in c.beats for i, t in [(x.id, x.text)] if i in before and i != "b0003"}
    for bad in (0, 6, -1, 99):
        with pytest.raises(ops.OpError):
            ops.split_beat(n, "b0003", bad)
    with pytest.raises(ops.OpError):
        ops.split_beat(n, "b9999", 1)


def test_merge_with_previous_keeps_the_previous_id():
    n = make_narration()
    a, b = n.chapter("c02").beats
    a.show, b.show = ["x"], ["y"]
    a.facts, b.facts = ["f01"], ["f02", "f01"]
    keep = ops.merge_with_previous(n, b.id)
    assert keep == a.id and beats(n, "c02") == [a.id]
    assert a.facts == ["f01", "f02"] and a.show == ["x", "y"] and a.text.endswith("end.") and a.text.count("end.") == 2
    with pytest.raises(ops.OpError):
        ops.merge_with_previous(n, a.id)                          # first of its chapter
    assert n.new_beat_id() == "b0007"                             # b0004 is gone for good


def test_drop_leaves_a_gap_that_is_not_reused():
    n = make_narration()
    ops.drop_beat(n, "b0006")
    ops.drop_beat(n, "b0005")
    assert beats(n, "c03") == []
    assert n.new_beat_id() == "b0007"
    with pytest.raises(ops.OpError):
        ops.drop_beat(n, "b0006")


def test_insert_at_start_and_after():
    n = make_narration()
    i1 = ops.insert_beat(n, "c01", None, "new first")
    i2 = ops.insert_beat(n, "c01", "b0001", "after first", ["f01"], ["x"])
    assert beats(n, "c01") == [i1, "b0001", i2, "b0002"] and i1 == "b0007" and i2 == "b0008"
    assert n.find_beat(i2)[0].beats[2].facts == ["f01"]
    with pytest.raises(ops.OpError):
        ops.insert_beat(n, "c01", "b0005")                         # b0005 belongs to another chapter
    with pytest.raises(ops.OpError):
        ops.insert_beat(n, "c99")


def test_move_within_and_across_chapters():
    n = make_narration()
    ops.move_beat(n, "b0002", None, None)                         # to the start of its own chapter
    assert beats(n, "c01") == ["b0002", "b0001"]
    ops.move_beat(n, "b0001", "c03", "b0005")
    assert beats(n, "c01") == ["b0002"] and beats(n, "c03") == ["b0005", "b0001", "b0006"]
    with pytest.raises(ops.OpError):
        ops.move_beat(n, "b0001", "c03", "b0001")
    with pytest.raises(ops.OpError):
        ops.move_beat(n, "b0001", "c02", "b0006")                  # anchor is not in the destination
    assert beats(n, "c03") == ["b0005", "b0001", "b0006"]          # a refused move changes nothing
    with pytest.raises(ops.OpError):
        ops.move_beat(n, "b0001", "c77")


def test_locked_beats_refuse_text_changing_operations():
    n = make_narration()
    n.chapter("c02").beats[1].locked = True
    with pytest.raises(ops.OpError):
        ops.drop_beat(n, "b0004")
    with pytest.raises(ops.OpError):
        ops.split_beat(n, "b0004", 2)
    with pytest.raises(ops.OpError):
        ops.merge_with_previous(n, "b0004")
    n.chapter("c02").beats[1].locked = False
    ops.drop_beat(n, "b0004")


def test_apply_op_dispatch():
    n = make_narration()
    assert ops.apply_op(n, {"op": "split", "beat": "b0001", "at_word": 10})["id"] == "b0007"
    assert ops.apply_op(n, {"op": "insert", "chapter": "c03", "text": "t"})["id"] == "b0008"
    ops.apply_op(n, {"op": "merge", "beat": "b0007"})
    ops.apply_op(n, {"op": "drop", "beat": "b0008"})
    ops.apply_op(n, {"op": "move", "beat": "b0002", "to_chapter": "c03"})
    for bad in ({"op": "nope"}, {"op": "split"}, {"op": "split", "beat": "b0001", "at_word": "x"}):
        with pytest.raises(ops.OpError):
            ops.apply_op(n, bad)
