from bti.voice.align import build_words, even_times, merge_words, written_times
from bti.voice.chunks import build_chunks
from bti.voice.config import load_voice_config
from bti.voice.speak import speak_units

from conftest import make_narration


def test_even_times_cover_the_span():
    t = even_times(["a", "bbb", "cc"], 1.0, 4.0)
    assert t[0][0] == 1.0 and abs(t[-1][1] - 4.0) < 1e-9
    assert all(a[1] <= b[0] + 1e-9 for a, b in zip(t, t[1:]))


def test_merge_matches_and_interpolates():
    spoken = "the mirror hangs behind them".split()
    heard = [{"w": "The", "s": 1.0, "e": 1.2}, {"w": "mirror", "s": 1.3, "e": 1.8}, {"w": "behind", "s": 2.4, "e": 2.8}, {"w": "them", "s": 2.8, "e": 3.0}]
    times, matched = merge_words(spoken, heard, (0.9, 3.2))
    assert matched == 4
    assert times[0] == (1.0, 1.2) and times[3] == (2.4, 2.8)
    assert 1.8 <= times[2][0] and times[2][1] <= 2.4                 # "hangs" sits in the gap
    assert all(a[0] <= b[0] for a, b in zip(times, times[1:]))


def test_merge_without_heard_is_even_and_inside_the_span():
    times, matched = merge_words("one two three".split(), None, (2.0, 3.0))
    assert matched == 0 and times[0][0] == 2.0 and abs(times[-1][1] - 3.0) < 1e-9


def test_merge_clamps_to_the_span():
    times, _ = merge_words(["a"], [{"w": "a", "s": 0.0, "e": 9.0}], (1.0, 2.0))
    assert times == [(1.0, 2.0)]


def test_written_words_of_a_number_share_its_spoken_span():
    units = speak_units("In 1434, he left.")
    spoken = " ".join(u.spoken for u in units).split()
    assert len(spoken) == 5                                   # in fourteen thirty-four, he left.
    times = [(i * 1.0, i * 1.0 + 1.0) for i in range(5)]
    w = written_times(units, times, 0.0, 5.0)
    assert [x["w"] for x in w] == ["In", "1434,", "he", "left."]
    assert w[1]["s"] == 1.0 and w[1]["e"] == 3.0 and w[2]["s"] == 3.0


def test_build_words_covers_every_written_word_in_order():
    cfg = load_voice_config()
    n = make_narration()
    cs = build_chunks(n, {}, cfg, "s")
    spans, t = [], 0.5
    for c in cs:
        d = len(c.spoken) * 0.05
        spans.append({"index": c.index, "start": t, "end": t + d})
        t += d + 0.3
    words, st = build_words(cs, spans, {})
    expect = [w for ch in n.chapters for b in ch.beats for w in b.text.split()]
    assert [w["w"] for w in words] == expect
    assert all(a["s"] <= b["s"] for a, b in zip(words, words[1:]))
    assert all(s["start"] <= words[r[0]]["s"] and words[r[1] - 1]["e"] <= s["end"] + 1e-6 for s, r in zip(spans, st["ranges"]))
