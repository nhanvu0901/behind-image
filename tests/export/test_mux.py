import sys

from bti.export import mux

FF = ["ffmpeg"]


def cmd(**kw):
    a = dict(video="v.mp4", audio="a.m4a", meta="m.txt", out="o.mp4", duration=12.5)
    a.update(kw)
    return mux.mux_command(FF, **a)


def test_no_video_filter_anywhere():
    for c in (cmd(), cmd(audio_copy=False), mux.join_command(FF, "l.txt", "o.mp4")):
        s = " ".join(c)
        for bad in ("-vf", "-filter_complex", "subtitles", "ass=", "-filter:v", "-lavfi"):
            assert bad not in s
    assert "copy" == cmd()[cmd().index("-c:v") + 1]


def test_mux_maps_copies_and_faststart():
    c = cmd()
    assert "-c:s" not in c and "mov_text" not in c
    assert c[c.index("-c:a") + 1] == "copy"
    assert "+faststart" in c
    assert c[c.index("-t") + 1] == "12.500"
    assert "-map_chapters" in c and "2" == c[c.index("-map_chapters") + 1]
    assert [c[i + 1] for i, a in enumerate(c) if a == "-map"] == ["0:v:0", "1:a:0"]
    assert c[-1] == "o.mp4"


def test_audio_is_encoded_when_not_aac():
    c = cmd(audio_copy=False)
    assert c[c.index("-c:a") + 1] == "aac" and "192k" in c


def test_language_tags():
    c = cmd(language="vie")
    assert "language=vie" in c


def test_concat_list_quotes():
    assert mux.concat_list(["/a/b.mp4", "/a/it's.mp4"]) == "file '/a/b.mp4'\nfile '/a/it'\\''s.mp4'\n"
    assert "C:/x/y.mp4" in mux.concat_list(["C:\\x\\y.mp4"])


def test_pretty_chapter():
    assert mux.pretty_chapter("COLD_OPEN") == "Cold Open"
    assert mux.pretty_chapter("The Mirror") == "The Mirror"
    assert mux.pretty_chapter("THE MERCHANT CITY") == "The Merchant City"


def test_chapter_marks_start_at_zero_and_cover_the_video():
    ch = [{"name": "A", "start": 2.0}, {"name": "B", "start": 80.0}, {"name": "C", "start": 500.0}, {"name": "Late", "start": 900.0}]
    m = mux.chapter_marks(ch, 600.0)
    assert [x["start"] for x in m] == [0.0, 80.0, 500.0]
    assert m[-1]["end"] == 600.0
    assert all(a["end"] == b["start"] for a, b in zip(m, m[1:]))
    assert mux.chapter_marks([], 10) == []


def test_ffmetadata():
    t = mux.ffmetadata([{"title": "A=b", "start": 0, "end": 1.5}], "T;1")
    assert t.startswith(";FFMETADATA1\n")
    assert r"title=T\;1" in t and "START=0\nEND=1500\n" + r"title=A\=b" in t


def test_merge_short_chapters():
    marks = [{"title": "A", "start": 0, "end": 5}, {"title": "B", "start": 5, "end": 100}, {"title": "C", "start": 100, "end": 104},
             {"title": "D", "start": 104, "end": 300}]
    out, n = mux.merge_short(marks)
    assert n == 2 and [(m["title"], m["start"], m["end"]) for m in out] == [("B", 0, 104), ("D", 104, 300)]
    assert mux.merge_short([{"title": "A", "start": 0, "end": 3}]) == ([{"title": "A", "start": 0, "end": 3}], 0)
    assert mux.merge_short([])[1] == 0
