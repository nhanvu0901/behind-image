from bti.visual.helpers import moment_words, sentence_for_word, cast_member, show_matches, pool_shows


def test_moment_words_and_speech_times():
    timing = {"words": [{"w": "The", "s": 0.1, "e": 0.3}, {"w": "river.", "s": 0.4, "e": 1.0}, {"w": "Next", "s": 1.2, "e": 1.5}]}
    assert moment_words({"w0": 0, "w1": 2}, timing) == (["The", "river."], 0.1, 1.0)
    assert sentence_for_word(timing, 1) == (0, 2)
    assert sentence_for_word(timing, 2) == (2, 3)


def test_cast_show_and_pool():
    cast = [{"id": "river", "shown_by": [{"region": "RIVER"}, {"picture": "P"}]}]
    assert cast_member(cast, "river") == cast[0]
    assert cast_member(cast, "missing") is None
    assert show_matches({"region": "RIVER"}, cast[0])
    assert not show_matches({"region": "SKY"}, cast[0])
    assert pool_shows({"assets": {"A": {}, "P": {"shows": ["river"]}}, "main_asset": "A"}) == {"P": ["river"]}


def test_word_helpers_reject_empty_or_out_of_range():
    import pytest
    timing = {"words": [{"w": "one.", "s": 0, "e": 2}]}
    with pytest.raises(ValueError):
        moment_words({"w0": 0, "w1": 0}, timing)
    with pytest.raises(IndexError):
        sentence_for_word(timing, 1)


def test_none_wanted_resolves_to_its_explicit_fallback():
    from bti.visual.helpers import resolve_show
    show = {"want": "w1", "else": {"region": "RIVER"}}
    assert resolve_show(show, [{"id": "w1", "status": "none"}]) == {"region": "RIVER"}
    assert resolve_show(show, [{"id": "w1", "status": "found", "picture": "P"}]) == {"picture": "P"}
    assert show == {"want": "w1", "else": {"region": "RIVER"}}
