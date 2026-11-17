from bti.voice.chunks import build_chunks, chunk_id, chunk_units, default_seed, next_seed, text_hash
from bti.voice.config import load_voice_config
from bti.voice.speak import speak_units

from conftest import make_narration

CFG = load_voice_config()


def texts(groups):
    return [" ".join(u.spoken for u in g) for g in groups]


def test_one_chunk_per_sentence_when_long_enough():
    a = "The painting is small and it hangs in the National Gallery."
    b = "Nobody knows who the two people really were, or why it was made."
    got = texts(chunk_units(speak_units(a + " " + b)))
    assert got == [a, b]


def test_short_sentence_joins_the_next():
    got = texts(chunk_units(speak_units("Look. The painting is small and it hangs in the National Gallery today.")))
    assert got == ["Look. The painting is small and it hangs in the National Gallery today."]


def test_short_last_sentence_joins_the_previous():
    a = "The painting is small and it hangs in the National Gallery today."
    got = texts(chunk_units(speak_units(a + " Yes.")))
    assert got == [a + " Yes."]


def test_long_sentence_cut_at_a_comma():
    part = "this is a clause that goes on and on"
    s = ", ".join([part] * 12) + "."
    got = texts(chunk_units(speak_units("The " + s)))
    assert len(got) > 1 and all(len(x) <= 280 for x in got)
    assert " ".join(got).replace(" ,", ",") == ("The " + s)


def test_abbreviation_does_not_split_a_sentence():
    got = texts(chunk_units(speak_units("Mr. Smith owned a small painting of a mirror that hung in his hall.")))
    assert len(got) == 1


def test_ids_and_seeds_are_stable_and_follow_the_text():
    sig = "fake|ref|0.35|0.5|0.7"
    n = make_narration()
    a = build_chunks(n, {}, CFG, sig)
    b = build_chunks(n, {}, CFG, sig)
    assert [c.id for c in a] == [c.id for c in b]
    assert all(c.seed == default_seed(c.th) for c in a)
    assert len({c.id for c in a}) == len(a)
    # another sentence before it does not change the id of a sentence that did not change
    n2 = make_narration({"c1": [("b0009", "A brand new opening sentence that is long enough to stand alone here.")] + [("b0001", "In 1434, Jan van Eyck painted a portrait. It is on show in London.")], "c2": []})
    ids2 = {c.id for c in build_chunks(n2, {}, CFG, sig)}
    assert any(c.id in ids2 for c in a)
    # another voice setting changes every id
    assert not ({c.id for c in build_chunks(n, {}, CFG, "other")} & {c.id for c in a})


def test_reseed_changes_only_that_sentence():
    sig = "s"
    n = make_narration()
    a = build_chunks(n, {}, CFG, sig)
    th = a[0].th
    b = build_chunks(n, {}, CFG, sig, {th: next_seed(a[0].seed)})
    assert b[0].id != a[0].id and b[0].seed != a[0].seed
    assert [c.id for c in b[1:]] == [c.id for c in a[1:]]
    assert next_seed(5) == next_seed(5)


def test_gaps():
    n = make_narration()
    cs = build_chunks(n, {}, CFG, "s")
    kinds = [c.gap_kind for c in cs]
    assert kinds[0] == "lead"
    assert "beat" in kinds and "card" in kinds
    card = next(c for c in cs if c.gap_kind == "card")
    assert card.gap == CFG["silence"]["card"] and card.chapter == "c2"
    sent = [c for c in cs if c.gap_kind == "sentence"]
    assert all(c.gap == CFG["silence"]["sentence"] for c in sent)


def test_chunks_never_cross_a_beat_and_keep_written_words():
    n = make_narration()
    cs = build_chunks(n, {}, CFG, "s")
    for ch in n.chapters:
        for b in ch.beats:
            mine = [w for c in cs if c.beat == b.id for w in c.written]
            assert mine == b.text.split()


def test_hashes():
    assert len(text_hash("x")) == 10 and len(chunk_id("x", "s", 1)) == 12
