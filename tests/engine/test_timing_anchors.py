import pytest

from bti.engine.timing import AnchorError, Timing, norm
from conftest import words


@pytest.fixture()
def tm():
    return Timing({"duration": 20.0, "words": words(), "beats": [], "chapters": []})


def test_absolute_anchor(tm):
    assert tm.resolve({"t": 3.25}) == 3.25


def test_word_anchor_with_offset(tm):
    # word 4 starts at 2.0 s
    assert tm.resolve({"w": 4, "off": -0.12, "text": "epsilon"}) == pytest.approx(1.88)
    assert tm.resolve({"w": 4}) == pytest.approx(2.0)


def test_rel_anchor_needs_parent_span(tm):
    assert tm.resolve({"rel": 0.25}, 10.0, 14.0) == pytest.approx(11.0)
    with pytest.raises(AnchorError):
        tm.resolve({"rel": 0.5})


def test_bad_anchors(tm):
    for bad in ({"w": 999}, {"w": -1}, {"w": "x"}, {}, "nope"):
        with pytest.raises(AnchorError):
            tm.resolve(bad)


def test_find_phrase_and_anchor_for(tm):
    i = tm.find("delta epsilon")
    assert i == 3
    a = tm.anchor_for("delta epsilon", wi=1, off=0.2)
    assert a == {"w": 4, "off": 0.2, "text": "epsilon"}
    assert tm.find("alpha", nth=1) == 10
    with pytest.raises(KeyError):
        tm.find("no such phrase")


def test_normalisation_ignores_punctuation_and_case(tm):
    assert norm("Eta,") == "eta"
    assert tm.find("ETA THETA") == 6          # word 6 is "eta," in the fixture


def test_stale_text_detection(tm):
    assert tm.stale({"w": 4, "text": "epsilon"}) is None
    assert tm.stale({"w": 6, "text": "eta"}) is None            # punctuation does not matter
    assert "does not match" in tm.stale({"w": 4, "text": "delta"})


def test_nearest_word_and_anchor_at(tm):
    assert tm.nearest_word(2.05) == 4
    assert tm.anchor_at(2.3) == {"w": 4, "off": 0.3, "text": "epsilon"}
    assert tm.anchor_at(2.3, snap=False) == {"t": 2.3}
