import pytest

from bti.media import api
from bti.media.errors import NotFound
from bti.media.sources import bookpage
from bti.media.sources.bookpage import BookPageSource

from conftest import png_bytes


def test_ids():
    assert bookpage.make_id("payne_gae", "img", 850) == "payne_gae/img/850" and bookpage.make_id("payne_gae", "page", 3) == "payne_gae/page/3"
    assert bookpage.parse_id("payne_gae/page/23") == ("payne_gae", "page", 23)
    for bad in ("", "../x/img/1", "payne_gae/img/x", "payne_gae/other/1", "a/b"):
        with pytest.raises(NotFound):
            bookpage.parse_id(bad)


def test_unknown_book():
    with pytest.raises(NotFound):
        BookPageSource().fetch_meta("nobook/img/1")


def test_import_a_page_is_flagged_unknown_and_never_searched(monkeypatch, tmp_path):
    calls = []
    def render(book, kind, ref, dest):
        calls.append((book, kind, ref))
        dest.write_bytes(png_bytes(900, 1200))
    monkeypatch.setitem(api._SOURCES, "book", BookPageSource(renderer=render))
    assert api.search("anything", "book") == []
    res = api.import_candidate(tmp_path / "p", "book", "payne_gae/page/23")
    a = res["asset"]
    assert calls == [("payne_gae", "page", 23)] and (a["width"], a["height"]) == (900, 1200)
    assert a["credit"]["source"] == "book" and a["credit"]["flag"] == "unknown" and "p. 23" in a["credit"]["source_url"]
    assert "James Payne" in a["credit"]["author"]
    assert api.import_candidate(tmp_path / "p", "book", "payne_gae/page/23") == res and len(calls) == 1
    assert not list((tmp_path / "p" / "media").glob("*.part"))


def test_render_failure_leaves_nothing(monkeypatch, tmp_path):
    def render(book, kind, ref, dest):
        dest.write_bytes(b"junk")
        raise NotFound("no such page")
    monkeypatch.setitem(api._SOURCES, "book", BookPageSource(renderer=render))
    with pytest.raises(NotFound):
        api.import_candidate(tmp_path / "p", "book", "payne_gae/page/99")
    assert not list((tmp_path / "p" / "media").glob("*"))
