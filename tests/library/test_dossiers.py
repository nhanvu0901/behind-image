import json
import shutil

import pytest

from bti.library import catalogue, clean, config, dossiers, extract, projects

BUILT = (config.LIB_DIR / "artworks.json").is_file() and (config.LIB_DIR / "dossiers").is_dir()


# ---------------------------------------------------------------- clean-text parser (pure)
PAGE1 = """[page-type] body

# The Kiss
[meta] Gustav Klimt
[meta] 1907

[caption] Klimt, The Kiss, 1907.

## FIRST SECTION

First paragraph of the body, which goes on and on and
[credit] Photo: somebody
[note] 1 A footnote.

[quote] An epigraph worth keeping.

The sentence that is broken at the end of the page and
[continues]
"""
PAGE2 = """[page-type] body

continues here and ends.

## SECOND

Another paragraph.
"""


def test_parse_page_tags():
    p = clean.parse_page(PAGE1)
    kinds = [b["kind"] for b in p["blocks"]]
    assert p["type"] == "body" and p["continues"] is True
    assert kinds == ["h1", "meta", "meta", "caption", "h2", "p", "credit", "note", "quote", "p"]
    assert p["blocks"][0]["text"] == "The Kiss" and p["blocks"][3]["text"].startswith("Klimt")


def _fake_entry(monkeypatch, pages, book="payne_gae"):
    def page_text(b, n):
        return pages[n - 1], "clean"
    monkeypatch.setattr(extract, "page_text", page_text)
    return {"id": f"{book}/001", "pdf_pages": [1, len(pages)]}


def test_entry_joins_continues_and_keeps_body_only(monkeypatch):
    w = _fake_entry(monkeypatch, [PAGE1, PAGE2])
    e = clean.entry(w)
    assert "and ends." in e["body"] and "broken at the end of the page and continues here and ends." in e["body"]
    for bad in ("Photo", "footnote", "Klimt, The Kiss", "Gustav Klimt"):
        assert bad not in e["body"]
    assert "An epigraph worth keeping." in e["body"]
    assert [h["text"] for h in e["outline"]["headings"]] == ["The Kiss", "FIRST SECTION", "SECOND"]
    assert e["outline"]["captions"] == [{"page": 1, "text": "Klimt, The Kiss, 1907."}]
    assert e["outline"]["meta"] == ["Gustav Klimt", "1907"]
    assert e["text_source"] == "clean" and e["words"] > 20
    assert "details" not in e["outline"]


def test_entry_skips_non_body_pages_and_hodge_details(monkeypatch):
    pages = ["[page-type] body\n\n# Mona Lisa\n\nText.\n\n## THE SMILE\n\nMore text.",
             "[page-type] notes\n\n[note] 1 Something.\n\nNot body.", "[page-type] plate\n\n[caption] A plate."]
    w = _fake_entry(monkeypatch, pages, "hodge_aid")
    e = clean.entry(w)
    assert "Not body" not in e["body"] and e["outline"]["details"] == ["THE SMILE"]
    assert e["outline"]["captions"][0]["text"] == "A plate."


def test_entry_mixed_and_layer_fallback(monkeypatch):
    src = {1: ("[page-type] body\n\nClean para.", "clean"), 2: ("Layer¬\nword text", "layer")}
    monkeypatch.setattr(extract, "page_text", lambda b, n: src[n])
    e = clean.entry({"id": "payne_gae/001", "pdf_pages": [1, 2]})
    assert e["text_source"] == "mixed" and "Layerword text" in e["body"]


# ---------------------------------------------------------------- identity and conflicts (pure)
def W(i, title, artist, year, yn):
    return {"id": i, "n": int(i[-3:]), "title": title, "artist": artist, "year": year, "year_num": yn}


def test_identity_conflicts():
    ws = [W("payne_gae/002", "The Arnolfini Portrait", "Jan Van Eyck", "1434", 1434),
          W("hodge_aid/003", "The Arnolfini Portrait", "Jan van Eyck", "1434", 1434)]
    assert dossiers._identity(ws)["conflicts"] == []
    ws.append(W("brookehitching_mad/011", "Arnolfini Wedding", "Jan van Eyck", "1470", 1470))
    ident = dossiers._identity(ws)
    assert {c["field"] for c in ident["conflicts"]} == {"title", "year"}
    assert ident["identity"]["title"] == "The Arnolfini Portrait"  # Payne is preferred
    assert ident["variants"]["year"][0]["value"] == "1434"
    ws[1]["artist"] = "Rogier van der Weyden"
    assert "artist" in {c["field"] for c in dossiers._identity(ws)["conflicts"]}


# ---------------------------------------------------------------- built dossiers
pytestmark_built = pytest.mark.skipif(not BUILT, reason="run python -m bti.library build and dossiers first")


@pytestmark_built
def test_dossier_merged_across_books():
    d = dossiers.load("eyck-the-arnolfini-portrait")
    assert d["totals"]["books"] == 3 and {s["book_id"] for s in d["sources"]} == {"payne_gae", "hodge_aid", "brookehitching_mad"}
    assert d["identity"]["title"] == "The Arnolfini Portrait" and d["images"]
    for s in d["sources"]:
        f = config.LIB_DIR / "dossiers" / "eyck-the-arnolfini-portrait" / s["file"]
        assert f.is_file() and len(f.read_text().split()) >= s["words"] * 0.9
        assert set(s) >= {"work_id", "book_id", "pdf_pages", "words", "text_source", "outline"}
    g = dossiers.load("bosch-the-garden-of-earthly-delights")
    assert g["totals"]["books"] == 4


@pytestmark_built
def test_every_artwork_has_a_dossier():
    arts = catalogue.load_artworks()
    assert len(list((config.LIB_DIR / "dossiers").glob("*/dossier.json"))) == len(arts)


# ---------------------------------------------------------------- merge / split overrides (on a temporary copy)
@pytest.fixture()
def tmplib(tmp_path, monkeypatch):
    dst = tmp_path / "library"
    shutil.copytree(config.LIB_DIR, dst, ignore=shutil.ignore_patterns("cache", "dossiers", "text_audit"))
    monkeypatch.setattr(config, "LIB_DIR", dst)
    return dst


@pytest.mark.skipif(not BUILT, reason="library not built")
def test_merge_then_split(tmplib):
    arts = catalogue.load_artworks()
    a, b = "weyden-descent-from-the-cross", "eyck-the-arnolfini-portrait"
    assert a in arts and b in arts
    ids = arts[a]["works"] + arts[b]["works"]
    key = dossiers.merge_artworks(a, b)
    after = catalogue.load_artworks()
    assert set(after[key]["works"]) == set(ids) and a not in after or b not in after
    ovr = json.loads((tmplib / "overrides" / "artworks.json").read_text())
    assert sorted(ovr["merge"][0]) == sorted(ids)
    assert dossiers.load(key)["totals"]["sources"] == len(ids)
    # the merge survives a regroup
    catalogue.regroup()
    assert any(set(ids) <= set(x["works"]) for x in catalogue.load_artworks().values())
    victim = "brookehitching_mad/011"
    key2 = dossiers.split_work(victim)
    after = catalogue.load_artworks()
    assert after[key2]["works"] == [victim]
    assert victim not in after[key]["works"] if key in after else True
    catalogue.regroup()  # a split stays split
    assert next(x for x in catalogue.load_artworks().values() if victim in x["works"])["works"] == [victim]
    assert json.loads((tmplib / "overrides" / "artworks.json").read_text())["split"] == [victim]
    with pytest.raises(ValueError):
        dossiers.split_work(victim)
    with pytest.raises(ValueError):
        dossiers.merge_artworks(key2, key2)


@pytest.mark.skipif(not BUILT, reason="library not built")
def test_project_from_artwork_with_exclusion(tmp_path):
    p = projects.create_project(None, "arn-art", tmp_path, artwork_key="eyck-the-arnolfini-portrait",
                                exclude=["hodge_aid/003"])
    assert p["artwork_key"] == "eyck-the-arnolfini-portrait"
    assert [s["work_id"] for s in p["sources"]] == ["payne_gae/002", "brookehitching_mad/011"]
    d = tmp_path / "arn-art" / "source"
    doc = json.loads((d / "dossier.json").read_text())
    assert doc["totals"]["sources"] == 2 and (d / "payne_gae_002.txt").is_file() and not (d / "hodge_aid_003.txt").exists()
    assert not (tmp_path / "arn-art" / ".dossier_tmp").exists()
    with pytest.raises(projects.ProjectError):
        projects.create_project(None, "x1", tmp_path, artwork_key="nope-nope")
    with pytest.raises(projects.ProjectError):
        projects.create_project(None, "x2", tmp_path, artwork_key="eyck-the-arnolfini-portrait", exclude=["payne_gae/002", "hodge_aid/003", "brookehitching_mad/011"])


def test_book_trust_defaults_and_override(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LIB_DIR", tmp_path)
    assert catalogue.book_trust("grovier_nws")["trust"] == "low" and catalogue.book_trust("grovier_nws")["trust_note"]
    assert catalogue.book_trust("payne_gae")["trust"] == "normal"
    (tmp_path / "overrides").mkdir()
    (tmp_path / "overrides" / "books.json").write_text(json.dumps({"grovier_nws": {"trust": "normal"}, "payne_gae": {"trust": "low", "trust_note": "x"}}))
    assert catalogue.book_trust("grovier_nws")["trust"] == "normal"
    assert catalogue.book_trust("payne_gae") == {"trust": "low", "trust_note": "x"}


@pytest.mark.skipif(not BUILT, reason="library not built")
def test_overrides_books_file_exists_and_dossier_trust():
    f = config.LIB_DIR / "overrides" / "books.json"
    assert json.loads(f.read_text())["grovier_nws"]["trust"] == "low"
    d = dossiers.load("bosch-the-garden-of-earthly-delights")
    # Grovier's work is `low`, or `restored` once library/restored/grovier_nws is there and the dossiers were rebuilt
    assert {s["book_id"]: s["trust"] for s in d["sources"]}["grovier_nws"] in ("low", "restored")
    t = d["totals"]
    assert t["words"] == t["words_normal"] + t.get("words_restored", 0) + t["words_low"] and t["words_low"] + t.get("words_restored", 0) > 0
    assert d["only_low_trust"] is False
