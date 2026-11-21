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


def test_the_sentence_limit_is_one_number():
    assert stats.MAX_SENTENCE_WORDS == 25
    assert stats.STYLE_TARGETS["max"] == stats.MAX_SENTENCE_WORDS
    assert "p90_max" not in stats.STYLE_TARGETS and "share_over_25_max" not in stats.STYLE_TARGETS      # the old, vaguer limits (32 and a quarter over 25) are gone
    S = lambda k: " ".join(["Word"] * k) + "."
    prof = stats.sentence_profile([S(stats.MAX_SENTENCE_WORDS + 1)] * 10)
    assert f"share_over_{stats.MAX_SENTENCE_WORDS}" in prof          # the key names the limit: change the number and this test says the key must be renamed
    assert prof[f"share_over_{stats.MAX_SENTENCE_WORDS}"] == 1.0


def test_sentence_profile_against_targets():
    S = lambda k: " ".join(["Word"] * k) + "."
    prof = stats.sentence_profile([f"{S(9)} {S(16)} {S(22)}"] * 4)
    assert prof["sentences"] == 12 and prof["median"] == 16 and prof["share_over_25"] == 0 and prof["notes"] == []
    one = stats.sentence_profile([f"{S(9)} {S(16)} {S(22)} {S(26)}"] * 4)           # one sentence of 26 in four is no longer inside a "quarter that may be long"
    assert one["share_over_25"] == 0.25 and any("longer than 25 words" in x for x in one["notes"])
    flat = stats.sentence_profile([S(40)] * 10)
    assert flat["share_over_25"] == 1.0 and flat["notes"]
    frag = stats.sentence_profile(["No. Yes. Ok. " + S(15)] * 5)
    assert frag["share_under_4"] > 0.05 and any("shorter than 4" in x for x in frag["notes"])
    assert stats.sentence_profile([])["sentences"] == 0
