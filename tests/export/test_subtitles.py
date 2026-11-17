import json

from bti.export import subtitles as S

from conftest import REPO


def words(text, start=0.0, per=0.3, gap=0.0):
    out, t = [], start
    for w in text.split():
        out.append({"w": w, "s": round(t, 3), "e": round(t + per, 3)})
        t += per + gap
    return out


def test_short_sentence_is_one_cue():
    c = S.build_cues(words("It is a lovely story."))
    assert len(c) == 1 and c[0].lines == ("It is a lovely story.",)


def test_two_lines_of_at_most_42():
    c = S.build_cues(words("It is a lovely story, and guidebooks have repeated it for generations."))
    assert len(c) == 1
    assert len(c[0].lines) == 2 and all(len(x) <= 42 for x in c[0].lines)


def test_sentence_end_breaks_cues():
    c = S.build_cues(words("One two three four. Five six seven eight."))
    assert [x.text for x in c] == ["One two three four.", "Five six seven eight."]


def test_abbreviation_does_not_end_a_sentence():
    c = S.build_cues(words("Mr. Arnolfini was a merchant."))
    assert len(c) == 1


def test_pause_breaks_cues():
    w = words("so we begin", 0.0) + words("and then we go", 3.0)
    c = S.build_cues(w)
    assert len(c) == 2


def test_long_sentence_breaks_after_comma_when_it_can():
    t = "The painting was made in Bruges in 1434 by a painter of the court, and it shows a couple standing in a small room full of objects."
    c = S.build_cues(words(t, per=0.25))
    assert len(c) >= 2
    assert c[0].text.rstrip().endswith(",")


def test_no_cue_over_six_seconds_or_over_limits():
    t = " ".join(["word%d" % i for i in range(120)])
    c = S.build_cues(words(t, per=0.5))
    assert S.check_cues(c) == []
    assert all(x.ms <= S.MAX_MS for x in c)


def test_short_cue_is_lengthened_into_the_silence():
    w = words("Yes.", 0.0, per=0.3) + words("Then a long second sentence follows here.", 5.0)
    c = S.build_cues(w)
    assert c[0].ms >= S.MIN_MS
    assert c[0].end < c[1].start


def test_short_cue_squeezed_between_neighbours_is_merged():
    w = words("Look at this.", 0.0, per=0.3) + words("No.", 1.0, per=0.2) + words("Really now.", 1.3, per=0.3)
    c = S.build_cues(w)
    assert S.check_cues(c) == []


def test_never_overlap_even_with_overlapping_words():
    w = [{"w": "a.", "s": 0.0, "e": 2.0}, {"w": "b.", "s": 1.0, "e": 3.0}, {"w": "c.", "s": 2.5, "e": 4.0}]
    c = S.build_cues(w)
    assert all(b.start >= a.end for a, b in zip(c, c[1:]))


def test_beat_starts_force_a_break():
    w = words("one two three four five six")
    c = S.cues_from_timing({"words": w, "beats": [{"w0": 0, "w1": 3}, {"w0": 3, "w1": 6}]})
    assert [x.text for x in c] == ["one two three", "four five six"]


def test_empty_and_bad_words_are_ignored():
    assert S.build_cues([]) == []
    c = S.build_cues([{"w": "", "s": 0, "e": 1}, {"w": "hi.", "s": 0.1, "e": 0.5}, {"w": "x", "s": "?", "e": 1}, None])
    assert len(c) == 1 and c[0].text == "hi."


def test_srt_text_and_roundtrip():
    c = S.build_cues(words("One two three four. Five six seven eight."))
    txt = S.to_srt(c)
    assert txt.startswith("1\n00:00:00,000 --> ")
    assert txt.count("-->") == 2 and "\n\n2\n" in txt
    assert S.parse_srt(txt) == c


def test_srt_time():
    assert S.srt_time(3723004) == "01:02:03,004"


def test_check_cues_finds_each_rule():
    bad = S.check_cues([S.Cue(0, 500, ("a",)), S.Cue(400, 9000, ("x" * 50, "b", "c"))])
    codes = {b["code"] for b in bad}
    assert {"too_short", "overlap", "too_long", "line_length", "lines"} <= codes


def test_real_arnolfini_timing():
    t = json.loads((REPO / "projects" / "arnolfini" / "timing.json").read_text(encoding="utf-8"))
    c = S.cues_from_timing(t)
    assert 150 <= len(c) <= 260
    assert S.check_cues(c) == []
    # every word of the narration is in the cues once, in order
    said = " ".join(x.text.replace("\n", " ") for x in c).split()
    assert said == [w["w"] for w in t["words"]]
    # no cue crosses a chapter start (one chapter of this timing starts inside a sentence: 417.3 s, mid "The room")
    crossing = sum(1 for ch in t["chapters"][1:] for x in c if x.start < int(round(ch["start"] * 1000)) - 100 and x.end > int(round(ch["start"] * 1000)) + 100)
    assert crossing <= 1
    assert max(len(l) for x in c for l in x.lines) <= 42


def test_real_timing_is_never_drawn_into_the_picture_by_this_module():
    import inspect
    src = inspect.getsource(S)
    assert "subtitles=" not in src and "-vf" not in src
