from copy import deepcopy

from bti.compose.schedule import schedule as _schedule


def schedule(moments, end, **kwargs):
    return _schedule(moments, end, floor=kwargs.pop("floor", 2.5),
                     borrowed_floor=kwargs.pop("borrowed_floor", 3.0), **kwargs)


def moment(ident, start, show, line="line", sentence_start=0):
    return {"id": ident, "start": start, "show": show, "line": line,
            "sentence_start": sentence_start}


def test_identical_neighbours_join_without_mutating_input():
    source = [moment("a", 0, {"whole": True}), moment("b", 3, {"region": "R"}),
              moment("c", 4, {"region": "R"})]
    original = deepcopy(source)
    shots, notes = schedule(source, 8)
    assert source == original
    assert [(s["id"], s["start"]) for s in shots] == [("a", 0), ("b", 3)]
    assert notes == [{"moment": "c", "rule": "C1", "what": "joined into b"}]


def test_borrowed_picture_takes_slack_back_then_forward():
    source = [moment("a", 0, {"whole": True}), moment("b", 4, {"picture": "B"}, sentence_start=3),
              moment("c", 5, {"region": "R"})]
    shots, notes = schedule(source, 9)
    assert [s["start"] for s in shots] == [0, 3, 6]
    assert [n["what"] for n in notes if n["moment"] == "b"] == ["extended backward toward sentence start", "extended forward"]


def test_two_short_pictures_become_pair():
    source = [moment("a", 0, {"picture": "A"}), moment("b", 1.5, {"picture": "B"})]
    shots, notes = schedule(source, 4)
    assert shots[0]["show"] == {"pair": [{"picture": "A"}, {"picture": "B"}]}
    assert notes[0]["rule"] == "C2"


def test_single_short_moment_is_retained_and_noted():
    shots, notes = schedule([moment("a", 0, {"whole": True})], 1.5)
    assert len(shots) == 1
    assert notes[0]["rule"] == "C1"


def test_generated_schedules_terminate_and_cover_the_timeline():
    import random
    rng = random.Random(103)
    for _ in range(300):
        count = rng.randint(1, 25)
        starts = [0.0]
        for _ in range(count - 1):
            starts.append(starts[-1] + rng.uniform(0.2, 5.0))
        end = starts[-1] + rng.uniform(0.2, 5.0)
        entries = [moment(str(i), start, {"region": str(rng.randrange(4))}, line=str(i))
                   for i, start in enumerate(starts)]
        result, notes = schedule(entries, end)
        assert result[0]["start"] == 0.0
        assert all(a["start"] < b["start"] for a, b in zip(result, result[1:]))
        if end >= 2.5:
            boundaries = [s["start"] for s in result] + [end]
            assert all(b - a >= 2.5 - 1e-9 for a, b in zip(boundaries, boundaries[1:]))
        assert len(result) <= count
        assert len(notes) <= count


def test_intro_keeps_spoken_word_and_expands_forward():
    source = [moment("a", 0, {"region": "R"}), moment("b", 3, {"region": "S"})]
    source[0]["intro_end"] = 4.0
    shots, notes = schedule(source, 8)
    assert shots[1]["start"] == 4.0
    assert any("introduction" in n["what"] for n in notes)


def test_long_borrowed_view_still_begins_at_sentence_start_if_room():
    source = [moment("a", 0, {"whole": True}), moment("b", 6, {"picture": "B"}, sentence_start=4)]
    shots, notes = schedule(source, 11)
    assert shots[1]["start"] == 4
    assert any(n["moment"] == "a" for n in notes)


def test_borrowed_picture_is_kept_by_joining_previous_view():
    source = [moment("a", 0, {"whole": True}), moment("b", 2.5, {"picture": "B"})]
    shots, notes = schedule(source, 5)
    assert len(shots) == 1 and shots[0]["show"] == {"picture": "B"}
    assert shots[0]["start"] == 0
    assert any(n["rule"] == "C1" and n["moment"] == "a" for n in notes)


def test_pair_covers_the_whole_sentence_even_when_neighbours_must_join():
    source = [moment('a', 0, {'whole': True}),
              moment('b', 4, {'picture': 'B'}, sentence_start=2),
              moment('c', 5, {'picture': 'C'}, sentence_start=2),
              moment('d', 6.5, {'region': 'R'}, sentence_start=2)]
    for item in source:
        item['sentence_end'] = 8
    shots, notes = schedule(source, 10)
    index = next(i for i, shot in enumerate(shots) if 'pair' in shot['show'])
    end = shots[index + 1]['start'] if index + 1 < len(shots) else 10
    assert shots[index]['start'] <= 2 and end >= 8
    assert any(note['rule'] == 'C2' for note in notes)
