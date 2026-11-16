from bti.script import stats
from script_helpers import make_narration, make_outline, words


def test_count_words_ignores_lone_punctuation():
    assert stats.count_words("One — two  three,\nfour.") == 4 and stats.count_words("") == 0


def test_minutes_at_configurable_rate():
    assert stats.WPS_DEFAULT == 2.41
    assert stats.minutes(241 * 60) == 100.0
    assert stats.minutes(120, 2.0) == 1.0 and stats.minutes(120, 0) == 0.0


def test_sentences_keep_abbreviations_and_years():
    s = stats.sentences("Dr. Smith saw it in c. 1390. He left! Was it 1434? Yes.")
    assert s == ["Dr. Smith saw it in c. 1390.", "He left!", "Was it 1434?", "Yes."]


def test_narration_stats_per_chapter_budget():
    n, o = make_narration((100, 200, 100)), make_outline()
    st = stats.narration_stats(n, o)
    assert st["words"] == 400 and st["beats"] == 6 and st["target_words"] == 400 and st["target_ratio"] == 1.0
    assert [c["words"] for c in st["chapters"]] == [100, 200, 100]
    assert st["chapters"][1]["budget"] == 200 and st["chapters"][1]["ratio"] == 1.0
    assert st["minutes"] == round(400 / 2.41 / 60, 2)
    assert stats.narration_stats(n, o, 4.0)["minutes"] == round(400 / 4 / 60, 2)


def test_sentence_profile_against_targets():
    S = lambda k: " ".join(["Word"] * k) + "."
    prof = stats.sentence_profile([f"{S(9)} {S(16)} {S(22)}"] * 4)
    assert prof["sentences"] == 12 and prof["median"] == 16 and prof["share_over_25"] == 0 and prof["notes"] == []
    flat = stats.sentence_profile([S(40)] * 10)
    assert flat["share_over_25"] == 1.0 and flat["notes"]
    frag = stats.sentence_profile(["No. Yes. Ok. " + S(15)] * 5)
    assert frag["share_under_4"] > 0.05 and any("shorter than 4" in x for x in frag["notes"])
    assert stats.sentence_profile([])["sentences"] == 0
