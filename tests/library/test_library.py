import json
import shutil

import pytest

from bti.library import catalogue, config, extract, parse, projects

HAVE = {b["id"]: config.book_pdf(b["id"]) is not None for b in config.BOOKS}
BUILT = (config.LIB_DIR / "books" / "payne_gae" / "works.json").is_file()


def need(bid):
    return pytest.mark.skipif(not HAVE[bid], reason=f"PDF of {bid} missing")


def parsed(bid):
    return parse.PARSERS[bid](extract.doc(bid))


# ---------------------------------------------------------------- counts and page ranges
@pytest.mark.parametrize("bid,count", [("payne_gae", 30), ("hodge_aid", 100), ("hagen_wgps", 80),
                                       ("grovier_nws", 57), ("dasal_artcurious", 12)])
def test_counts(bid, count):
    if not HAVE[bid]:
        pytest.skip("pdf missing")
    ws = parsed(bid)
    assert len(ws) == count
    assert [w["n"] for w in ws] == list(range(1, count + 1))


@need("brookehitching_mad")
def test_madman_about_60():
    assert 58 <= len(parsed("brookehitching_mad")) <= 63


@need("payne_gae")
def test_payne_ranges():
    ws = parsed("payne_gae")
    assert ws[1]["pdf_pages"] == [23, 35] and ws[1]["artist"] == "Jan Van Eyck"
    assert ws[1]["title"] == "The Arnolfini Portrait" and ws[1]["year"] == "1434"
    assert ws[-1]["pdf_pages"][1] == 374
    for a, b in zip(ws, ws[1:]):
        assert b["pdf_pages"][0] == a["pdf_pages"][1] + 1


@need("hodge_aid")
def test_hodge_arnolfini_and_death_years():
    ws = parsed("hodge_aid")
    w = next(x for x in ws if "Arnolfini" in x["title"])
    assert w["pdf_pages"] == [22, 25] and w["artist_death"] == 1441
    assert all(x["pdf_pages"][1] - x["pdf_pages"][0] == 3 for x in ws)
    starts = [x["pdf_pages"][0] for x in ws]
    assert starts == sorted(set(starts)) and starts[0] == 14  # book page 10 + 4


@need("hagen_wgps")
def test_hagen_layout():
    ws = parsed("hagen_wgps")
    assert ws[0]["pdf_pages"] == [12, 17] and ws[-1]["pdf_pages"] == [486, 491]
    assert ws[0]["title"] == "The Bayeux Tapestry" and ws[0]["headline"] == "Propaganda on cloth"
    assert ws[1]["headline"].startswith('"A garden inclosed')
    assert ws[2]["headline"] == "A deceptive idyll"  # the two headlines printed on one line are ordered


@need("dasal_artcurious")
def test_artcurious_titles():
    ws = parsed("dasal_artcurious")
    assert ws[1]["title"] == "Secrets and Lines: The CIA/AbEx Connection"
    assert ws[0]["headline"].startswith("Part I")


# ---------------------------------------------------------------- rights rules (pure)
@pytest.mark.parametrize("w,status", [
    ({"artist_death": 1441}, "pd_likely"),
    ({"artist_death": 1955}, "pd_likely"),          # 2026 - 1955 = 71
    ({"artist_death": 1956}, "copyright_likely"),
    ({"artist_death": 1900, "year_num": 1990}, "pd_likely"),
    ({"artist_alive": True, "year_num": 1500}, "copyright_likely"),
    ({"year_num": 1899}, "pd_likely"),
    ({"year_num": 1900}, "unknown"),
    ({"year_num": 1955}, "unknown"),
    ({"year_num": 1956}, "copyright_likely"),
    ({}, "unknown"),
])
def test_rights(w, status):
    r = catalogue.estimate_rights(w, 2026)
    assert r["status"] == status and r["basis"]


def test_year_parsing():
    assert parse.year_num("c. 1500-05") == 1500
    assert parse.year_num("38,000-33,000 bc") == -38000
    assert parse.year_num("eighteenth century") == 1750
    assert parse.year_num("x913") == 1913
    assert parse.parse_death("(1909-92)") == (1909, 1992, False)
    assert parse.parse_death("(b.1945)")[2] is True
    assert parse.parse_death("(c. 1431-1516)")[1] == 1516


# ---------------------------------------------------------------- matching rules (pure)
def W(title, artist, year=None):
    return {"title": title, "artist": artist, "year_num": year}


def test_match_rules():
    assert catalogue.works_match(W("The Arnolfini Portrait", "Jan Van Eyck", 1434), W("Arnolfini Portrait", "Jan van Eyck", 1434))
    assert not catalogue.works_match(W("The Kiss", "Auguste Rodin", 1882), W("The Kiss", "Gustav Klimt", 1907))
    assert not catalogue.works_match(W("The Kiss", "Auguste Rodin"), W("The Thinker", "Auguste Rodin"))
    assert not catalogue.works_match(W("Self-Portrait", "Jan Vermeer"), W("Self-Portrait", "Jan van Eyck"))
    assert not catalogue.works_match(W("Dance", None), W("Dance Class", "Edgar Degas"))
    assert catalogue.works_match(W("Rain, Steam and Speed", "J. M. W. Turner", 1844), W("Rain, Steam and Speed – The Great Western Railway", "J. M. W. Turner"))


# ---------------------------------------------------------------- the built catalogue
@pytest.mark.skipif(not BUILT, reason="run python -m bti.library build first")
def test_cross_book_checks():
    arts = catalogue.load_artworks()
    books_of = lambda a: {w.split("/")[0] for w in a["works"]}
    arn = next(a for a in arts.values() if "Arnolfini" in a["title"])
    assert books_of(arn) >= {"payne_gae", "hodge_aid", "brookehitching_mad"}
    gar = next(a for a in arts.values() if "Garden of Earthly" in a["title"])
    assert books_of(gar) >= {"payne_gae", "hodge_aid", "grovier_nws", "brookehitching_mad"}
    rodin = [a for a in arts.values() if a["artist"] and "Rodin" in a["artist"]]
    assert len(rodin) == 2 and all(len(a["works"]) == 1 for a in rodin)
    # no artwork holds two entries of the same book
    for a in arts.values():
        bs = [w.split("/")[0] for w in a["works"]]
        assert len(bs) == len(set(bs)) or a["works"][0].startswith("dasal")


@pytest.mark.skipif(not BUILT, reason="library not built")
def test_works_json_shape():
    for b in config.BOOKS:
        f = config.book_dir(b["id"]) / "works.json"
        if not f.is_file():
            continue
        bk = json.loads((config.book_dir(b["id"]) / "book.json").read_text())
        assert set(bk) >= {"id", "title", "author", "file", "pages", "pdf_type", "unit", "n_works", "notes"}
        for w in json.loads(f.read_text()):
            assert set(w) >= {"id", "n", "title", "artist", "year", "pdf_pages", "words", "n_images", "headings",
                              "artwork_key", "rights"}
            assert w["rights"]["status"] in ("pd_likely", "copyright_likely", "unknown") and w["rights"]["basis"]


# ---------------------------------------------------------------- overrides
def test_overrides_merge_by_id_and_field(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LIB_DIR", tmp_path)
    bd = config.book_dir("payne_gae")
    bd.mkdir(parents=True)
    works = [{"id": "payne_gae/001", "n": 1, "title": "A", "artist": "X", "year": "1500", "pdf_pages": [1, 2],
              "rights": {"status": "unknown", "basis": "b"}},
             {"id": "payne_gae/002", "n": 2, "title": "B", "artist": "Y", "year": None, "pdf_pages": [3, 4],
              "rights": {"status": "unknown", "basis": "b"}}]
    (bd / "works.json").write_text(json.dumps(works))
    (tmp_path / "overrides").mkdir()
    (tmp_path / "overrides" / "payne_gae.json").write_text(json.dumps({
        "payne_gae/002": {"title": "B fixed", "year": "1901", "rights": {"status": "pd_likely"}, "bogus": 1}}))
    out = catalogue.load_works("payne_gae")
    assert out[0]["title"] == "A"
    assert out[1]["title"] == "B fixed" and out[1]["artist"] == "Y" and out[1]["year_num"] == 1901
    assert out[1]["rights"] == {"status": "pd_likely", "basis": "b"} and "bogus" not in out[1]


def test_override_files_exist_and_are_not_overwritten():
    for b in config.BOOKS:
        assert (config.LIB_DIR / "overrides" / f"{b['id']}.json").is_file()


# ---------------------------------------------------------------- project creation
@pytest.mark.skipif(not (BUILT and HAVE["payne_gae"] and HAVE["hodge_aid"]), reason="needs library and PDFs")
def test_create_project_several_works_and_refuse_overwrite(tmp_path):
    p = projects.create_project(["payne_gae/002", "hodge_aid/003"], "arn-test", tmp_path)
    assert p["id"] == "arn-test" and p["stage"] == "selected" and p["artwork_key"]
    assert [s["work_id"] for s in p["sources"]] == ["payne_gae/002", "hodge_aid/003"]
    d = tmp_path / "arn-test"
    assert json.loads((d / "project.json").read_text())["title"] == "The Arnolfini Portrait"
    assert (d / "source" / "payne_gae_002.txt").read_text().strip()
    doc = json.loads((d / "source" / "dossier.json").read_text())
    assert doc["totals"]["books"] == 2 and doc["sources"][1]["ocr"] is True
    assert p["dossier"] == "source/dossier.json" and p["library_dossier"].startswith("library/dossiers/")
    assert not (d / "storyboard.json").exists()
    assert projects.infer_stage(d) == "selected"
    before = (d / "project.json").read_text()
    with pytest.raises(projects.ProjectError) as e:
        projects.create_project(["payne_gae/002"], "arn-test", tmp_path)
    assert e.value.status == 409 and (d / "project.json").read_text() == before


def test_create_project_validation(tmp_path):
    for bad in ([], ["nope"], ["payne_gae/2"], ["../x/001"], ["payne_gae/002", "payne_gae/002"]):
        with pytest.raises(projects.ProjectError):
            projects.create_project(bad, None, tmp_path)
    if BUILT:
        for slug in ("../x", "A b", "lab_x", "demo_x", ""):
            if slug == "":
                continue
            with pytest.raises(projects.ProjectError):
                projects.create_project(["payne_gae/002"], slug, tmp_path)
    assert list(tmp_path.iterdir()) == []


@need("hagen_wgps")
def test_soft_hyphen_repair():
    assert extract.repair("Hast¬\nings and re¬ \nproduc¬\ntion") == "Hastings and reproduction"
    assert "¬" not in extract.work_text({"id": "hagen_wgps/001", "pdf_pages": [12, 13]})["text"]


# ---------------------------------------------------------------- D19 clean text catalogue & project key alias
def test_d19_clean_text_metadata_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LIB_DIR", tmp_path)
    clean_dir = tmp_path / "clean_text" / "payne_gae"
    clean_dir.mkdir(parents=True)
    # page 1 has clean text with corrected title, artist and year
    (clean_dir / "page_0001.txt").write_text(
        "[page-type] body\n\n# RAIN, STEAM AND SPEED – THE GREAT WESTERN RAILWAY\n"
        "[meta] CHAPTER 1\n[meta] J. M. W. TURNER\n[meta] 1844\n\nSome body text.\n",
        encoding="utf-8"
    )
    raw_work = {"id": "payne_gae/001", "n": 1, "title": "Rail, Steam and Speed", "artist": "J. M. W. Turner",
                "year": "1840", "pdf_pages": [1, 2]}
    meta = catalogue.extract_clean_meta("payne_gae", raw_work)
    assert meta["title"] == "Rain, Steam and Speed – the Great Western Railway"
    assert meta["artist"] == "J. M. W. Turner"
    assert meta["year"] == "1844"


def test_d19_artwork_key_preserved_with_alias(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LIB_DIR", tmp_path)
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    (tmp_path / "overrides").mkdir()
    (tmp_path / "overrides" / "artworks.json").write_text('{"merge": [], "split": []}\n', encoding="utf-8")
    
    # Fake books and works
    bd = config.book_dir("payne_gae")
    bd.mkdir(parents=True)
    works = [{"id": "payne_gae/001", "n": 1, "title": "Rain, Steam and Speed – The Great Western Railway",
              "artist": "J. M. W. Turner", "year": "1844", "pdf_pages": [1, 2]}]
    (bd / "works.json").write_text(json.dumps(works), encoding="utf-8")
    for b in config.BOOKS:
        if b["id"] != "payne_gae":
            (config.book_dir(b["id"])).mkdir(parents=True, exist_ok=True)
            (config.book_dir(b["id"]) / "works.json").write_text("[]\n", encoding="utf-8")

    # An existing project points to the old key
    proj_dir = tmp_path / "projects" / "test-turner"
    proj_dir.mkdir(parents=True)
    (proj_dir / "project.json").write_text(json.dumps({
        "id": "test-turner",
        "title": "Rail, Steam and Speed",
        "artwork_key": "turner-rail-steam-and-speed",
        "sources": [{"work_id": "payne_gae/001"}]
    }), encoding="utf-8")

    catalogue.regroup()
    artworks = catalogue.load_artworks()
    
    # Old key must be kept for the artwork that has a project
    assert "turner-rail-steam-and-speed" in artworks
    art = artworks["turner-rail-steam-and-speed"]
    assert art["alias"].startswith("turner-rain-steam-and-speed")

