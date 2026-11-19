"""The three trust levels of a source in the brief (normal, restored, low): what is included, what the model is told, the flag
for "no source is normal"."""
import json

import pytest

from bti.script.brief import OptionsError, build_brief, render_brief, restored_note, save_options

RESTORED_TEXT = """# 18 Hieronymus Bosch, The Garden of Earthly Delights

Bosch's triptych shows a garden of pleasures. Kelly's reading is that the fountain is a […] of the body.

[…]

The last paragraph ends here.
"""
PLAIN = "# Plain\n\nA plain paragraph of the normal book, with seven words here.\n"
LOW = "# Low\n\nThe lamp was lit for the wedding according to this unreliable edition.\n"


def project(root, sources, library=True):
    """A project whose dossier has one source per (book_id, level, text). Returns (project dir, library dir)."""
    d = root / "p"
    (d / "source").mkdir(parents=True)
    ds, srcs = [], []
    for i, (bid, level, text) in enumerate(sources, 1):
        name = f"{bid}_{i:03d}.txt"
        (d / "source" / name).write_text(text, encoding="utf-8")
        srcs.append({"work_id": f"{bid}/{i:03d}", "book_id": bid, "pdf_pages": [1, 2]})
        e = {"work_id": f"{bid}/{i:03d}", "book_id": bid, "file": name, "trust_note": "", "outline": {"meta": []}}
        if level is not None:
            e["trust"] = level
        ds.append(e)
    (d / "source" / "dossier.json").write_text(json.dumps({"artwork_key": "x", "identity": {"title": "T", "artist": "A", "year": "1500"},
                                                            "conflicts": [], "sources": ds}), encoding="utf-8")
    (d / "project.json").write_text(json.dumps({"id": "p", "title": "T", "dossier": "source/dossier.json", "sources": srcs}), encoding="utf-8")
    lib = root / "library"
    if library:
        for bid, title, author in (("grovier_nws", "A New Way of Seeing", "Kelly Grovier"), ("payne_gae", "Great Art Explained", "James Payne"),
                                   ("hodge_aid", "Art in Detail", "Susie Hodge")):
            (lib / "books" / bid).mkdir(parents=True)
            (lib / "books" / bid / "book.json").write_text(json.dumps({"title": title, "author": author}), encoding="utf-8")
    return d, lib


def by_book(b):
    return {s["book_id"]: s for s in b["sources"]}


NOTE_WORDS = ("restored and reviewed rendering of a machine-translated book", "unmarked prose says what the book says", "names corrected",
              "ideas and readings of the picture may be used as readings of the picture", "never as established fact", "never in the author's name",
              "one reading among others", "NO number, date or quotation", "unless another source of this dossier confirms it",
              "[…] marks a passage that could not be restored", "never guess what it said")


def test_each_level_is_marked_in_the_brief_and_the_page_fields(tmp_path):
    d, lib = project(tmp_path, [("payne_gae", "normal", PLAIN), ("grovier_nws", "restored", RESTORED_TEXT), ("hodge_aid", "low", LOW)])
    save_options(d, {"include_low": ["hodge_aid"]}, library_root=lib)
    b = build_brief(d, library_root=lib)
    s = by_book(b)
    assert (s["payne_gae"]["trust"], s["grovier_nws"]["trust"], s["hodge_aid"]["trust"]) == ("normal", "restored", "low")
    assert [s[x]["low_trust"] for x in ("payne_gae", "grovier_nws", "hodge_aid")] == [False, False, True]
    assert [s[x]["restored"] for x in ("payne_gae", "grovier_nws", "hodge_aid")] == [False, True, False]
    txt = render_brief(b)
    lines = {ln.split(" = ")[0]: ln for ln in txt.splitlines() if " = " in ln and ln[:3] in ("PAY", "GRO", "HOD")}
    assert "[RESTORED" not in lines["PAY"] and "[LOW TRUST" not in lines["PAY"]            # normal: no mark, as before
    assert "[LOW TRUST:" in lines["HOD"] and "[RESTORED" not in lines["HOD"]                # low: as before
    assert "[RESTORED: " in lines["GRO"] and "[LOW TRUST" not in lines["GRO"]
    for must in NOTE_WORDS:
        assert must in lines["GRO"], must
    assert "=== SOURCE GRO: A New Way of Seeing (grovier_nws/002) [RESTORED] ===" in txt
    assert "=== SOURCE HOD: Art in Detail (hodge_aid/003) [LOW TRUST] ===" in txt
    assert "=== SOURCE PAY: Great Art Explained (payne_gae/001) ===" in txt


def test_the_restricted_things_are_named_and_the_note_is_short(tmp_path):
    note = restored_note()
    for kind in ("number", "date", "quotation"):
        assert kind in note
    assert "argues" not in note and "Kelly" not in note and len(note) < 700                # the note does not ask the narration to name the author
    d, lib = project(tmp_path, [("grovier_nws", "restored", RESTORED_TEXT)], library=False)
    assert "never in the author's name" in render_brief(build_brief(d, library_root=lib))       # a book with no author on record: the same note


def test_restored_is_included_by_default_and_low_is_not(tmp_path):
    d, lib = project(tmp_path, [("grovier_nws", "restored", RESTORED_TEXT), ("hodge_aid", "low", LOW)])
    b = build_brief(d, library_root=lib)
    s = by_book(b)
    assert s["grovier_nws"]["included"] is True and s["hodge_aid"]["included"] is False
    assert "unreliable edition" not in render_brief(b) and "Bosch's triptych" in render_brief(b)       # the low text is withheld, the restored is given
    with pytest.raises(OptionsError) as e:                      # the only included source is the restored one: it must stay
        save_options(d, {"exclude": ["grovier_nws"]}, library_root=lib)
    assert e.value.code == "at_least_one_source"
    save_options(d, {"include_low": ["hodge_aid"], "exclude": ["grovier_nws"]}, library_root=lib)     # ticking the low one lets the restored go
    assert by_book(build_brief(d, library_root=lib))["grovier_nws"]["included"] is False


def test_flag_no_normal_source_for_each_mix(tmp_path):
    def flag(sources, **opts):
        d, lib = project(tmp_path / f"m{len(list(tmp_path.iterdir()))}", sources)
        if opts:
            save_options(d, opts, library_root=lib)
        b = build_brief(d, library_root=lib)
        return b["no_normal_source"], render_brief(b)

    f, t = flag([("payne_gae", "normal", PLAIN), ("grovier_nws", "restored", RESTORED_TEXT)])         # normal + restored
    assert f is False and "NO FULLY TRUSTED SOURCE" not in t
    f, t = flag([("grovier_nws", "restored", RESTORED_TEXT)])                                         # restored only
    assert f is True and "NO FULLY TRUSTED SOURCE" in t
    f, t = flag([("grovier_nws", "restored", RESTORED_TEXT), ("hodge_aid", "low", LOW)])              # restored + low (low not ticked)
    assert f is True and "NO FULLY TRUSTED SOURCE" in t
    f, t = flag([("hodge_aid", "low", LOW)], include_low=["hodge_aid"])                               # low only, ticked
    assert f is True and "NO FULLY TRUSTED SOURCE" in t
    f, t = flag([("hodge_aid", "low", LOW)])                                                          # low only, not ticked: nothing is given
    assert f is False and "NO FULLY TRUSTED SOURCE" not in t
    f, t = flag([("payne_gae", "normal", PLAIN), ("hodge_aid", "low", LOW)])                          # normal + low (low not ticked)
    assert f is False and "NO FULLY TRUSTED SOURCE" not in t
    f, t = flag([("payne_gae", "normal", PLAIN), ("grovier_nws", "restored", RESTORED_TEXT)], exclude=["payne_gae"])   # the normal one left out
    assert f is True and "NO FULLY TRUSTED SOURCE" in t
    assert "every fact of this painting needs care" in t and '"established"' in t and '"likely"' in t
    assert "tells it as a reading, not as an established fact" in t and "whose claim" not in t


def test_words_of_a_restored_source_do_not_count_the_marks(tmp_path):
    d, lib = project(tmp_path, [("grovier_nws", "restored", RESTORED_TEXT), ("payne_gae", "normal", "# P\n\nOne […] two three.\n")])
    s = by_book(build_brief(d, library_root=lib))
    assert s["grovier_nws"]["words"] == 18 + 0 + 5          # 18 words, a paragraph that is only the mark, 5 words: the marks are not words
    assert s["payne_gae"]["words"] == 4                      # a normal source is counted as it always was: the "[…]" is a token


def test_an_unknown_or_missing_level_is_read_with_care(tmp_path):
    d, lib = project(tmp_path, [("payne_gae", "weird", PLAIN), ("hodge_aid", None, LOW)])
    (lib / "overrides").mkdir()
    (lib / "overrides" / "books.json").write_text(json.dumps({"hodge_aid": {"trust": "restored", "trust_note": "x"}}), encoding="utf-8")
    s = by_book(build_brief(d, library_root=lib))
    assert s["payne_gae"]["trust"] == "low" and s["payne_gae"]["included"] is False        # a word that is none of the three: low
    # the dossier says nothing: the book's entry decides, and `restored` cannot be believed from a table (it cannot say the text was restored)
    assert s["hodge_aid"]["trust"] == "low" and s["hodge_aid"]["restored"] is False
    (lib / "overrides" / "books.json").write_text(json.dumps({"hodge_aid": {"trust": "normal"}}), encoding="utf-8")
    assert by_book(build_brief(d, library_root=lib))["hodge_aid"]["trust"] == "normal"
    (lib / "overrides" / "books.json").write_text("{}", encoding="utf-8")
    assert by_book(build_brief(d, library_root=lib))["hodge_aid"]["trust"] == "normal"      # nothing at all: normal, as before
