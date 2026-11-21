"""The third trust level, `restored`: decided per WORK from the review of a restoration folder (bti/library/restored.py).

Everything here runs on a small temporary library (never the owner's data): a book `grovier_nws` with six works, each of two pages
(a body page and a plate page), a restoration folder with a review that covers every case, a normal book and a second book."""
import json

import pytest

from bti.library import __main__ as cli
from bti.library import catalogue, clean, config, dossiers, extract, projects, restored

NOTE_VI = ("Bản khôi phục từ bản dịch máy, đã rà soát: dùng được cho ý và mô tả; "
           "số liệu, năm và trích dẫn phải có nguồn khác xác nhận.")
NO_NORMAL_VI = "Chưa có nguồn tin cậy đầy đủ cho tác phẩm này."

MACHINE = "[page-type] body\n\n# {n} Machine title\n\n[meta] (machine date)\n\nMachine text of work {n} with Berkeley and mangled names.\n"
BODY = """[page-type] body

# {n} Artist, Work {n}

[meta] (1890)

Restored prose of work {n} says what the book says. A passage [[? garbled words here ?]] ends here.

[caption] Albrecht Schiller, Caption of work {n} (1500)

The last paragraph has exactly seven words.
"""
PLATE = "[page-type] plate\n\n[caption] Mark Queen plate caption {n}\n"
BODY_WORDS = 21         # 10 + 4 (the mark and its punctuation do not count) + 7


def _put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _putj(path, obj):
    _put(path, json.dumps(obj, ensure_ascii=False))


def _work(bid, n, pages, title=None):
    return {"id": f"{bid}/{n:03d}", "n": n, "title": title or f"Work {n}", "artist": "Artist", "year": "1890", "pdf_pages": pages}


def _books_json(lib, obj):
    _putj(lib / "overrides" / "books.json", obj)


def _edit(lib, name, obj):
    """Rewrite one file of the restoration folder (the review files are cached by size and time of change)."""
    _putj(lib / "restored" / "grovier_nws" / name, obj)
    restored.forget()


@pytest.fixture()
def lib(tmp_path, monkeypatch):
    root = tmp_path / "library"
    monkeypatch.setattr(config, "LIB_DIR", root)
    monkeypatch.setattr(extract, "images", lambda *a, **k: [])         # no PDF in a temporary library
    restored.forget()
    # grovier_nws: six works of two pages; the machine text is in clean_text, the restored pages in restored
    works = [_work("grovier_nws", n, [2 * n - 1, 2 * n]) for n in range(1, 7)]
    _putj(root / "books" / "grovier_nws" / "works.json", works)
    for n in range(1, 7):
        _put(root / "clean_text" / "grovier_nws" / f"page_{2 * n - 1:04d}.txt", MACHINE.format(n=n))
        _put(root / "clean_text" / "grovier_nws" / f"page_{2 * n:04d}.txt", PLATE.format(n=n))
        _put(root / "restored" / "grovier_nws" / f"page_{2 * n - 1:04d}.txt", BODY.format(n=n))
        _put(root / "restored" / "grovier_nws" / f"page_{2 * n:04d}.txt", PLATE.format(n=n))
    (root / "restored" / "grovier_nws" / "page_0012.txt").unlink()                  # work 6: a restored page is missing
    _putj(root / "restored" / "grovier_nws" / "review.json", {"work_verdicts": [
        {"work": 1, "verdict": "usable", "fix_ids": []},
        {"work": 2, "verdict": "usable_after_fixes", "fix_ids": ["F001"]},
        {"work": 3, "verdict": "usable_after_fixes", "fix_ids": ["F002"]},          # its fix is not recorded as applied
        {"work": 4, "verdict": "not_usable"},
        {"work": 6, "verdict": "usable", "fix_ids": []},
    ], "findings": []})
    _putj(root / "restored" / "grovier_nws" / "review_fixes.json", [{"id": "F001", "work": 2}, {"id": "F002", "work": 3}])
    _putj(root / "restored" / "grovier_nws" / "review_fixes.applied.json", {"applied": ["F001"], "at": "x"})
    _putj(root / "restored" / "grovier_nws" / "report.json", {"works": {
        str(n): {"n": n, "pages": [f"page_{2 * n - 1:04d}", f"page_{2 * n:04d}"], "ok": True} for n in range(1, 7)}})
    # a normal book and a second one, neither has a restoration folder
    for bid in ("payne_gae", "hodge_aid"):
        _putj(root / "books" / bid / "works.json", [_work(bid, 1, [1, 2], title="Work 1")])
        _put(root / "clean_text" / bid / "page_0001.txt", "[page-type] body\n\n# Work 1\n\nPlain text of the other book, five words.\n")
        _put(root / "clean_text" / bid / "page_0002.txt", "[page-type] body\n\nA second page.\n")
    return root


def level(n, bid="grovier_nws"):
    return catalogue.work_trust(catalogue.load_work(bid, n))["trust"]


# ---------------------------------------------------------------- the level of a work
def test_levels_follow_the_review_work_by_work(lib):
    assert level(1) == "restored"             # usable
    assert level(2) == "restored"             # usable_after_fixes, its fix is recorded as applied
    assert level(3) == "low"                  # usable_after_fixes, its fix is not recorded as applied
    assert level(4) == "low"                  # not_usable
    assert level(5) == "low"                  # no verdict at all
    assert level(6) == "low"                  # a restored page is missing
    assert level(1, "payne_gae") == "normal"  # a book without a restoration is what it was
    tr = catalogue.work_trust(catalogue.load_work("grovier_nws", 1))
    assert tr == {"trust": "restored", "trust_note": NOTE_VI}
    assert catalogue.work_trust(catalogue.load_work("grovier_nws", 4))["trust_note"] == config.TRUST_NOTE_LOW
    assert catalogue.book_trust("grovier_nws")["trust"] == "low"        # the BOOK stays what it was; only works are lifted


def test_usable_after_fixes_without_the_applied_record(lib):
    (lib / "restored" / "grovier_nws" / "review_fixes.applied.json").unlink()
    restored.forget()
    assert level(2) == "low"                  # nothing says its fixes were applied
    assert level(1) == "restored"             # a `usable` work needs no fix


def test_a_fix_that_only_review_fixes_json_lists_must_be_applied_too(lib):
    _edit(lib, "review_fixes.json", [{"id": "F001", "work": 2}, {"id": "F002", "work": 3}, {"id": "F099", "work": 1}])
    assert level(1) == "low"
    _edit(lib, "review_fixes.applied.json", {"applied": ["F001", "F099"]})
    assert level(1) == "restored" and level(2) == "restored" and level(3) == "low"
    _edit(lib, "review_fixes.applied.json", {"applied": ["F001", "F002", "F099"]})
    assert level(3) == "restored"


def test_usable_after_fixes_that_lists_no_fix_cannot_be_shown_as_applied(lib):
    _edit(lib, "review.json", {"work_verdicts": [{"work": 1, "verdict": "usable_after_fixes", "fix_ids": []}]})
    _edit(lib, "review_fixes.json", [])
    assert level(1) == "low"


def test_damaged_or_missing_review_files_mean_no(lib):
    _put(lib / "restored" / "grovier_nws" / "review_fixes.applied.json", "{not json")
    restored.forget()
    assert level(2) == "low" and level(1) == "restored"
    _put(lib / "restored" / "grovier_nws" / "review.json", "[]")
    restored.forget()
    assert level(1) == "low"
    (lib / "restored" / "grovier_nws" / "review.json").unlink()
    restored.forget()
    assert level(1) == "low" and restored.review("grovier_nws") is None


def test_report_json_must_agree_with_the_catalogue(lib):
    rep = json.loads((lib / "restored" / "grovier_nws" / "report.json").read_text(encoding="utf-8"))
    rep["works"]["1"]["pages"] = ["page_0001"]                       # the page range moved
    del rep["works"]["2"]                                            # not in the report
    rep["works"]["3"]["ok"] = False
    _edit(lib, "report.json", rep)
    assert level(1) == "low" and level(2) == "low"
    _edit(lib, "review_fixes.applied.json", {"applied": ["F001", "F002"]})
    assert level(3) == "low"                                         # the restoration of this work failed
    (lib / "restored" / "grovier_nws" / "report.json").unlink()      # no report: the review and the pages decide
    restored.forget()
    assert level(1) == "restored" and level(2) == "restored" and level(3) == "restored"


def test_a_book_without_a_restoration_folder_is_unchanged(lib):
    import shutil
    shutil.rmtree(lib / "restored")
    restored.forget()
    assert all(level(n) == "low" for n in range(1, 7))
    assert level(1, "hodge_aid") == "normal"
    assert catalogue.book_trust("grovier_nws") == {"trust": "low", "trust_note": config.TRUST_NOTE_LOW}


# ---------------------------------------------------------------- the owner's override file
def test_an_entry_that_repeats_the_built_in_level_is_not_a_decision(lib):
    _books_json(lib, catalogue.DEFAULT_TRUST)                         # what catalogue.build() writes
    assert catalogue.book_forced("grovier_nws") is False
    assert level(1) == "restored" and level(4) == "low"
    _books_json(lib, {"grovier_nws": {"trust": "low", "trust_note": "my own words"}})
    assert level(1) == "restored"
    assert catalogue.book_trust("grovier_nws")["trust_note"] == "my own words"   # the book keeps the owner's note, a lifted work gets its own
    assert catalogue.work_trust(catalogue.load_work("grovier_nws", 4))["trust_note"] == "my own words"
    assert catalogue.work_trust(catalogue.load_work("grovier_nws", 1))["trust_note"] == NOTE_VI


def test_override_can_force_low_normal_or_restored(lib):
    _books_json(lib, {"grovier_nws": {"trust": "low", "force": True}})          # switch the restoration off
    assert catalogue.book_forced("grovier_nws") and all(level(n) == "low" for n in range(1, 7))
    _books_json(lib, {"grovier_nws": {"trust": "normal"}})                      # trusted by the owner: every work normal
    assert catalogue.book_forced("grovier_nws") and all(level(n) == "normal" for n in range(1, 7))
    assert catalogue.book_trust("grovier_nws")["trust"] == "normal"
    _books_json(lib, {"grovier_nws": {"trust": "restored"}})                    # restored by the owner: no review asked, pages needed
    assert [level(n) for n in range(1, 7)] == ["restored"] * 5 + ["low"]        # work 6 has a page missing
    bt = catalogue.book_trust("grovier_nws")
    assert bt == {"trust": "restored", "trust_note": NOTE_VI}
    _books_json(lib, {"payne_gae": {"trust": "low", "trust_note": "x"}})
    assert level(1, "payne_gae") == "low" and catalogue.book_trust("payne_gae") == {"trust": "low", "trust_note": "x"}
    _books_json(lib, {"payne_gae": {"force": True}, "grovier_nws": {"trust": "bogus"}})   # a force without a level, a level that is none
    assert level(1, "payne_gae") == "normal" and catalogue.book_forced("payne_gae") is False
    assert level(1) == "restored" and catalogue.book_trust("grovier_nws")["trust"] == "low"


def test_restored_text_does_not_lift_the_names_of_the_catalogue(lib):
    for lv in ("low", "restored"):
        assert catalogue.source_rank("grovier_nws", "clean", {"grovier_nws": lv}) == catalogue.SRC_RANK["low_trust"]
    assert catalogue.source_rank("payne_gae", "clean", {"payne_gae": "normal"}) < catalogue.SRC_RANK["low_trust"]


# ---------------------------------------------------------------- the text built for a restored work
def test_restored_text_marks_passages_drops_captions_and_counts_what_remains(lib):
    w = catalogue.load_work("grovier_nws", 1)
    e = clean.entry(w, restored=True)
    assert "[[?" not in e["body"] and "?]]" not in e["body"]
    assert "A passage […] ends here." in e["body"]                                  # the passage is the mark
    assert "garbled" not in e["body"] and "Machine text" not in e["body"]          # the unrestored text is not given
    for gone in ("Albrecht Schiller", "Mark Queen", "Caption of work", "plate caption"):
        assert gone not in e["body"]                                                # caption lines and plate-caption pages
    assert e["outline"]["captions"] == []
    assert e["body"].startswith("# 1 Artist, Work 1")                              # the heading is kept
    assert e["outline"]["meta"] == ["(1890)"] and [h["text"] for h in e["outline"]["headings"]] == ["1 Artist, Work 1"]
    assert e["words"] == BODY_WORDS and e["text_source"] == "restored" and e["ocr"] is False
    assert [p["type"] for p in e["pages"]] == ["body", "plate"] and {p["source"] for p in e["pages"]} == {"restored"}
    # the same work as plain text keeps what the restored text drops (nothing changes for a work that is not restored)
    plain = clean.entry(w)
    assert "Machine text of work 1" in plain["body"] and plain["text_source"] == "clean" and plain["words"] == 10


def test_a_byte_order_mark_does_not_hide_the_page_type(lib):
    (lib / "restored" / "grovier_nws" / "page_0002.txt").write_bytes(b"\xef\xbb\xbf" + PLATE.format(n=1).encode("utf-8"))
    e = clean.entry(catalogue.load_work("grovier_nws", 1), restored=True)
    assert [p["type"] for p in e["pages"]] == ["body", "plate"] and "Mark Queen" not in e["body"]


def test_mark_unclear_handles_every_shape_of_marker():
    m = restored.mark_unclear
    assert m("a [[? x ?]] b [[? y z ?]].") == "a […] b […]."
    assert m("keep [[? a\nb ?]] going") == "keep […] going"                         # a passage over two lines
    assert m("fine\nbroken [[? never closed\nnext line") == "fine\n[…]\nnext line"   # an open marker: the whole line is one mark
    assert m("stray ?]] closer") == "[…]"
    assert m("no marker […] here") == "no marker […] here"
    assert restored.count_words("one […] two […]. three […], […]") == 3
    assert restored.count_words("[…]") == 0 and restored.count_words("") == 0


# ---------------------------------------------------------------- the dossier: numbers and flags
def build(works, key="x"):
    return dossiers.build_one(key, {"works": works}, out_dir=None)


def mix(lib, works, hodge_low=True):
    if hodge_low:
        _books_json(lib, {"hodge_aid": {"trust": "low"}})
    return build(works)


def test_dossier_numbers_and_flags_for_every_mix(lib):
    # normal + restored
    d = mix(lib, ["payne_gae/001", "grovier_nws/001"])
    t = d["totals"]
    assert [s["trust"] for s in d["sources"]] == ["normal", "restored"]
    assert t["words_restored"] == BODY_WORDS and t["words_low"] == 0 and t["words_normal"] > 0
    assert t["words"] == t["words_normal"] + t["words_restored"] + t["words_low"]
    assert d["only_low_trust"] is False and d["no_normal_source"] is False
    assert d["text_source"] == "mixed"
    # restored only
    d = mix(lib, ["grovier_nws/001"])
    assert d["totals"]["words_restored"] == BODY_WORDS == d["totals"]["words"]
    assert d["only_low_trust"] is False and d["no_normal_source"] is True and d["text_source"] == "restored"
    assert d["sources"][0]["trust_note"] == NOTE_VI
    # restored + low
    d = mix(lib, ["grovier_nws/001", "hodge_aid/001"])
    t = d["totals"]
    assert sorted(s["trust"] for s in d["sources"]) == ["low", "restored"]
    assert t["words_restored"] == BODY_WORDS and t["words_low"] > 0 and t["words_normal"] == 0
    assert d["only_low_trust"] is False and d["no_normal_source"] is True
    # low only (work 4 is not usable; the other source is low by the owner's override)
    d = mix(lib, ["grovier_nws/004", "hodge_aid/001"])
    assert {s["trust"] for s in d["sources"]} == {"low"}
    assert d["totals"]["words_restored"] == 0 and d["totals"]["words_low"] == d["totals"]["words"]
    assert d["only_low_trust"] is True and d["no_normal_source"] is True
    # normal + low: nothing about the new level
    d = mix(lib, ["payne_gae/001", "hodge_aid/001"])
    assert d["only_low_trust"] is False and d["no_normal_source"] is False and d["totals"]["words_restored"] == 0
    # no source at all
    assert build([])["only_low_trust"] is False and build([])["no_normal_source"] is False


def test_the_dossier_text_of_a_restored_work_is_the_restored_text(lib, tmp_path):
    d = build(["grovier_nws/001"], key="art")
    f = lib / "dossiers" / "art" / d["sources"][0]["file"]
    text = f.read_text(encoding="utf-8")
    assert "A passage […] ends here." in text and "Machine text" not in text and "Albrecht" not in text
    low = build(["grovier_nws/004"], key="art4")                    # a work that stays low keeps the plain text, as before
    assert "Machine text of work 4" in (lib / "dossiers" / "art4" / low["sources"][0]["file"]).read_text(encoding="utf-8")
    assert low["sources"][0]["trust"] == "low" and low["sources"][0]["text_source"] == "clean"


def test_dossier_of_an_unrestored_book_has_the_same_numbers_as_before(lib):
    d = build(["payne_gae/001", "hodge_aid/001"])
    assert d["totals"]["words_restored"] == 0 and d["totals"]["words"] == d["totals"]["words_normal"]
    assert d["text_source"] == "clean"


# ---------------------------------------------------------------- rebuilding one book
def _artworks(lib):
    _putj(lib / "artworks.json", {
        "art-a": {"title": "Work 1", "artist": "Artist", "year": "1890", "works": ["payne_gae/001", "grovier_nws/001"]},
        "art-b": {"title": "Work 4", "artist": "Artist", "year": "1890", "works": ["grovier_nws/004"]},
        "art-c": {"title": "Work 1", "artist": "Artist", "year": "1890", "works": ["hodge_aid/001"]}})


def test_rebuild_only_the_dossiers_of_one_book(lib, capsys):
    _artworks(lib)
    assert dossiers.keys_of_book("grovier_nws") == ["art-a", "art-b"]
    done = dossiers.build_book("grovier_nws")
    assert set(done) == {"art-a", "art-b"}
    assert (lib / "dossiers" / "art-a" / "dossier.json").is_file() and (lib / "dossiers" / "art-b" / "dossier.json").is_file()
    assert not (lib / "dossiers" / "art-c").exists()                  # the other book's dossier was not touched
    with pytest.raises(KeyError):
        dossiers.build_book("no_such_book")
    # the same through the command line
    import shutil
    shutil.rmtree(lib / "dossiers")
    assert cli.main(["dossiers", "--book", "grovier_nws"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["artworks"] == 2 and out["sources_by_trust"] == {"normal": 1, "restored": 1, "low": 1}
    assert not (lib / "dossiers" / "art-c").exists()
    assert cli.main(["dossiers", "--book", "nope"]) == 2 and cli.main(["dossiers", "--book"]) == 2
    capsys.readouterr()
    assert cli.main(["trust", "grovier_nws"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("grovier_nws/001  restored") and "grovier_nws/004  low" in lines[3]
    assert json.loads(lines[-1]) == {"works_by_trust": {"restored": 2, "low": 4}}


# ---------------------------------------------------------------- what a dossier says now, and a project's default sources
def test_live_trust_never_promises_more_than_the_dossier_text_is(lib):
    _artworks(lib)
    _books_json(lib, {"grovier_nws": {"trust": "low", "force": True}})
    d = dossiers.build_one("art-a", {"works": ["payne_gae/001", "grovier_nws/001"]})          # built while the restoration was off
    src = next(s for s in d["sources"] if s["book_id"] == "grovier_nws")
    assert src["trust"] == "low" and src["text_source"] == "clean"
    _books_json(lib, catalogue.DEFAULT_TRUST)                                                  # the library now says restored ...
    assert level(1) == "restored"
    assert dossiers.live_trust(src)["trust"] == "low"                                          # ... the text of this dossier is not
    d = build(["grovier_nws/001"], key="art-a2")
    assert dossiers.live_trust(d["sources"][0])["trust"] == "restored"
    _books_json(lib, {"grovier_nws": {"trust": "normal"}})                                     # the owner's override shows at once
    assert dossiers.live_trust(d["sources"][0])["trust"] == "normal"
    _books_json(lib, {"grovier_nws": {"trust": "low", "force": True}})                         # and so does a switch off
    assert dossiers.live_trust(d["sources"][0])["trust"] == "low"


def test_project_default_leaves_out_low_sources_only(lib, tmp_path):
    root = tmp_path / "projects"
    _putj(lib / "artworks.json", {
        "a-nr": {"title": "Work 1", "artist": "Artist", "year": "1890", "works": ["payne_gae/001", "grovier_nws/001"]},
        "a-rl": {"title": "Work 1", "artist": "Artist", "year": "1890", "works": ["hodge_aid/001", "grovier_nws/001"]},
        "a-l": {"title": "Work 4", "artist": "Artist", "year": "1890", "works": ["grovier_nws/004"]}})
    _books_json(lib, {"hodge_aid": {"trust": "low"}})
    p = projects.create_project(None, "p-nr", root, artwork_key="a-nr")
    assert [s["work_id"] for s in p["sources"]] == ["payne_gae/001", "grovier_nws/001"]         # normal + restored: both in
    p = projects.create_project(None, "p-rl", root, artwork_key="a-rl")
    assert [s["work_id"] for s in p["sources"]] == ["grovier_nws/001"]                           # restored in, low out
    doc = json.loads((root / "p-rl" / "source" / "dossier.json").read_text(encoding="utf-8"))
    assert doc["sources"][0]["trust"] == "restored" and doc["no_normal_source"] is True
    assert "A passage […]" in (root / "p-rl" / "source" / "grovier_nws_001.txt").read_text(encoding="utf-8")
    p = projects.create_project(None, "p-l", root, artwork_key="a-l")
    assert [s["work_id"] for s in p["sources"]] == ["grovier_nws/004"]                           # only a low source: kept, not empty


# ---------------------------------------------------------------- the editor's API
def _client(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from bti.editor import library_api
    app = FastAPI()
    (tmp_path / "projects").mkdir(exist_ok=True)
    app.include_router(library_api.make_router(tmp_path / "projects"))
    return TestClient(app)


def test_api_rows_and_dossier_carry_the_three_levels(lib, tmp_path):
    _putj(lib / "artworks.json", {
        "a-nr": {"title": "Work 1", "artist": "Artist", "year": "1890", "works": ["payne_gae/001", "grovier_nws/001"]},
        "a-rl": {"title": "Work 2", "artist": "Artist", "year": "1890", "works": ["hodge_aid/001", "grovier_nws/002"]},
        "a-l": {"title": "Work 4", "artist": "Artist", "year": "1890", "works": ["grovier_nws/004"]},
        "a-n": {"title": "Work 5", "artist": "Artist", "year": "1890", "works": ["payne_gae/001"]}})
    _books_json(lib, {"hodge_aid": {"trust": "low"}})
    dossiers.build_all()
    c = _client(tmp_path)
    rows = {r["artwork_key"]: r for r in c.get("/api/library/artworks").json()}
    nr, rl, lo, no = rows["a-nr"], rows["a-rl"], rows["a-l"], rows["a-n"]
    assert nr["restored_books"] == ["grovier_nws"] and nr["low_trust_books"] == [] and nr["no_normal_source"] is False
    assert nr["words_restored"] == BODY_WORDS and nr["words_normal"] > 0 and nr["only_low_trust"] is False
    assert rl["restored_books"] == ["grovier_nws"] and rl["low_trust_books"] == ["hodge_aid"]
    assert rl["no_normal_source"] is True and rl["only_low_trust"] is False
    assert lo["low_trust_books"] == ["grovier_nws"] and lo["restored_books"] == [] and lo["only_low_trust"] is True and lo["no_normal_source"] is True
    assert no["restored_books"] == [] and no["low_trust_books"] == [] and no["no_normal_source"] is False and no["words_restored"] == 0
    d = c.get("/api/library/artworks/a-nr").json()["dossier"]
    assert {s["book_id"]: s["trust"] for s in d["sources"]} == {"payne_gae": "normal", "grovier_nws": "restored"}
    assert next(s for s in d["sources"] if s["book_id"] == "grovier_nws")["trust_note"] == NOTE_VI
    # the library says low now (an override), the page shows it at once; and a dossier that was not rebuilt is never shown as restored
    _books_json(lib, {"grovier_nws": {"trust": "low", "force": True}})
    assert c.get("/api/library/artworks/a-nr").json()["dossier"]["sources"][1]["trust"] == "low"
    rows = {r["artwork_key"]: r for r in c.get("/api/library/artworks").json()}
    assert rows["a-nr"]["restored_books"] == [] and rows["a-nr"]["low_trust_books"] == ["grovier_nws"] and rows["a-nr"]["no_normal_source"] is False
    dossiers.build_all()                                            # rebuilt while forced low: the text is the plain text
    _books_json(lib, catalogue.DEFAULT_TRUST)
    d = c.get("/api/library/artworks/a-nr").json()["dossier"]
    assert next(s for s in d["sources"] if s["book_id"] == "grovier_nws")["trust"] == "low"
