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


# ---- followups item 5: `artist` is a key of every stored work (null when the book names none), and old files are read as that
def old_record_without_artist(bid, n=1):
    """A work as an older build stored it: the book names no artist, so `_public` left the key out (year stays, as null)."""
    return {"id": f"{bid}/{n:03d}", "n": n, "title": "The Bayeux Tapestry", "year": None, "pdf_pages": [n, n + 1], "field_src": {"title": "clean"}}


def test_a_stored_work_always_has_an_artist_key_null_when_the_book_names_none():
    w = old_record_without_artist("hagen_wgps")
    out = catalogue._public(w)
    assert "artist" in out and out["artist"] is None
    assert list(out)[:4] == ["id", "n", "title", "artist"]                              # the spec's order: the key sits after the title
    assert "artist" not in w                                                             # the work given is not changed
    assert catalogue._public({**w, "artist": "Jan van Eyck"})["artist"] == "Jan van Eyck"


def test_a_works_file_written_before_the_fix_is_read_with_artist_null(lib):
    (config.book_dir("hagen_wgps") / "works.json").write_text(json.dumps([old_record_without_artist("hagen_wgps"),
                                                                           {**old_record_without_artist("hagen_wgps", 2), "artist": "Someone"}]), encoding="utf-8")
    a, b = catalogue.load_works("hagen_wgps")
    assert a["artist"] is None and b["artist"] == "Someone"
    assert catalogue.load_work("hagen_wgps", 1)["artist"] is None


def test_regroup_rewrites_an_old_works_file_with_the_artist_key_and_no_rebuild_is_needed(lib):
    """The data on an already built library is brought to the documented shape by `python -m bti.library regroup` (no PDF access)."""
    f = config.book_dir("hagen_wgps") / "works.json"
    f.write_text(json.dumps([old_record_without_artist("hagen_wgps")]), encoding="utf-8")
    assert "artist" not in json.loads(f.read_text(encoding="utf-8"))[0]
    catalogue.regroup()
    stored = json.loads(f.read_text(encoding="utf-8"))
    assert all("artist" in w for w in stored) and stored[0]["artist"] is None


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
    assert p["pipeline"] == "visual"
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


# ---------------------------------------------------------------- D19: clean text, trust order, names, years, aliases
SEED_ARTISTS = {
    "Hieronymus Bosch": ["Hieronymous Bosch"], "Pieter Bruegel the Elder": ["Bruegel the Elder"],
    "Eugène Delacroix": ["Eugene Delacroix", "Eugéne Delacroix"],
    "Caravaggio": ["Michelangelo da Caravaggio"], "Diego Velázquez": ["Diego Velazquez"],
    "Salvador Dalí": ["Salvador Dali"], "Édouard Manet": ["Edouard Manet"],
    "Jean-François Millet": ["Jean-Francois Millet"], "Pierre-Auguste Renoir": ["Pierre Auguste Renoir"],
    "Georgia O’Keeffe": ["Georgia O Keeffe", "Georgia O’keeffe", "Georgia O'Keeffe"],
    "Cornelis van Dalem": ["Cornelis Van Dalem"], "Vincent van Gogh": ["Vincent Van Gogh"],
    "Rembrandt van Rijn": {"variants": ["Rembrandt"], "key_name": "rembrandt"},
    "Zhang Zeduan": {"variants": [], "key_name": "zhang"},
}


@pytest.fixture
def lib(tmp_path, monkeypatch):
    """An empty library in a temporary folder, with the seed artists file and every book folder present."""
    monkeypatch.setattr(config, "LIB_DIR", tmp_path / "library")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    (config.LIB_DIR / "overrides").mkdir(parents=True)
    (config.LIB_DIR / "overrides" / "artists.json").write_text(json.dumps(SEED_ARTISTS), encoding="utf-8")
    (config.LIB_DIR / "overrides" / "artworks.json").write_text('{"merge": [], "split": []}\n', encoding="utf-8")
    for b in config.BOOKS:
        config.book_dir(b["id"]).mkdir(parents=True)
        (config.book_dir(b["id"]) / "works.json").write_text("[]\n", encoding="utf-8")
    return config.LIB_DIR


def put_works(bid, rows):
    """rows: (n, title, artist, year, field_src or None)."""
    ws = [{"id": f"{bid}/{n:03d}", "n": n, "title": t, "artist": a, "year": y, "pdf_pages": [n, n + 1],
           "field_src": fs or {}} for n, t, a, y, fs in rows]
    (config.book_dir(bid) / "works.json").write_text(json.dumps(ws, ensure_ascii=False), encoding="utf-8")


def artwork_of(work_id):
    return next(a for a in catalogue.load_artworks().values() if work_id in a["works"])


# ---- 1. title casing
def test_title_casing_after_apostrophe():
    f = catalogue.title_case_words
    assert f("THE ARTIST’S STUDIO") == "The Artist’s Studio"
    assert f("THE ARTIST'S STUDIO") == "The Artist's Studio"
    assert f("STUDY AFTER VELÁZQUEZ’S PORTRAIT OF POPE INNOCENT X") == "Study after Velázquez’s Portrait of Pope Innocent X"
    assert f("the artist’s studio") == "The Artist’s Studio"


def test_title_casing_small_words_and_subtitles():
    f = catalogue.title_case_words
    assert f("THE LAST OF THE MOHICANS") == "The Last of the Mohicans"
    assert f("A BAR AT THE FOLIES BERGÈRE") == "A Bar at the Folies Bergère"
    assert f("WOMAN WITH A PARASOL AND A DOG IN LA PLAINE") == "Woman with a Parasol and a Dog in la Plaine"
    assert f("DU CÔTÉ DE CHEZ SWANN") == "Du Côté de Chez Swann"
    assert f("RAIN, STEAM AND SPEED – THE GREAT WESTERN RAILWAY") == "Rain, Steam and Speed – The Great Western Railway"
    assert f("MARRIAGE À-LA-MODE: 1, THE MARRIAGE SETTLEMENT") == "Marriage À-la-Mode: 1, The Marriage Settlement"
    assert f("“THE END”") == "“The End”"


@pytest.mark.parametrize("title", ["February miniature from the “Très Riches Heures du Duc de Berry”", "Merda d’Artista",
                                   "The Artist’s Studio", "Study after Velázquez’s Portrait of Pope Innocent X",
                                   "A Bar at the Folies Bergère", "I and the Village", "Marilyn Diptych"])
def test_title_in_mixed_case_stays_as_written(title):
    assert catalogue.title_case_words(title) == title


# ---- 2. canonical artists and the trust order
def test_canonical_artist_names(lib):
    expected = [("Hieronymous Bosch", "Hieronymus Bosch"), ("Bruegel the Elder", "Pieter Bruegel the Elder"),
                ("Eugene Delacroix", "Eugène Delacroix"), ("Eugéne Delacroix", "Eugène Delacroix"),
                ("EUGÈNE DELACROIX", "Eugène Delacroix"), ("Michelangelo da Caravaggio", "Caravaggio"),
                ("Diego Velazquez", "Diego Velázquez"), ("Salvador Dali", "Salvador Dalí"),
                ("Edouard Manet", "Édouard Manet"), ("Jean-Francois Millet", "Jean-François Millet"),
                ("Pierre Auguste Renoir", "Pierre-Auguste Renoir"), ("Georgia O Keeffe", "Georgia O’Keeffe"),
                ("Georgia O'Keeffe", "Georgia O’Keeffe"), ("Georgia O’keeffe", "Georgia O’Keeffe"),
                ("Cornelis Van Dalem", "Cornelis van Dalem"), ("Rembrandt", "Rembrandt van Rijn"),
                ("Vincent Van Gogh", "Vincent van Gogh"), ("VINCENT VAN GOGH", "Vincent van Gogh"),
                ("Pablo Picasso", "Pablo Picasso")]          # a name that is not in the file stays as written
    for raw, canonical in expected:
        assert catalogue.canonical_artist(raw) == (canonical, None), raw


def test_after_is_an_attribution_not_part_of_the_name(lib):
    for raw in ("After Cornelis Van Dalem", "after Cornelis van Dalem", "AFTER CORNELIS VAN DALEM"):
        assert catalogue.canonical_artist(raw) == ("Cornelis van Dalem", "after"), raw
    assert catalogue.canonical_artist(None) == (None, None) and catalogue.canonical_artist("  ") == (None, None)


def test_attributed_is_an_attribution_too(lib):
    assert catalogue.canonical_artist("Zhang Zeduan (Attrib.)") == ("Zhang Zeduan", "attributed")
    assert catalogue.canonical_artist("Zhang Zeduan (attributed)") == ("Zhang Zeduan", "attributed")


def test_key_name_decides_the_first_word_of_the_key(lib):
    assert catalogue.artist_key_word("Rembrandt van Rijn") == "rembrandt"
    assert catalogue.artist_key_word("Zhang Zeduan") == "zhang"
    assert catalogue.artist_key_word("Vincent van Gogh") == "gogh"           # no key_name: the last word, particles left out
    assert catalogue.artist_key_word("Pablo Picasso") == "picasso" and catalogue.artist_key_word(None) == "unknown"
    put_works("payne_gae", [(1, "The Night Watch", "Rembrandt van Rijn", "1642", None),
                            (2, "Along the River", "Zhang Zeduan (Attrib.)", "1085–1145", None)])
    ws = json.loads((config.book_dir("payne_gae") / "works.json").read_text())
    ws[1]["artist"], ws[1]["attribution"] = "Zhang Zeduan", "attributed"
    (config.book_dir("payne_gae") / "works.json").write_text(json.dumps(ws), encoding="utf-8")
    put_works("hodge_aid", [(1, "The Night Watch", "Rembrandt", "1642", None)])
    catalogue.regroup()
    arts = catalogue.load_artworks()
    assert set(arts) == {"rembrandt-the-night-watch", "zhang-along-the-river"}
    assert arts["rembrandt-the-night-watch"]["artist"] == "Rembrandt van Rijn"
    assert arts["zhang-along-the-river"]["attribution"] == "attributed"


def test_artist_in_capitals_without_a_better_spelling(lib):
    assert catalogue.canonical_artist("LEONARDO DA VINCI") == ("Leonardo da Vinci", None)
    assert catalogue.canonical_artist("JAMES ABBOTT MCNEILL WHISTLER") == ("James Abbott McNeill Whistler", None)
    assert catalogue.canonical_artist("GEORGES DE LA TOUR") == ("Georges de la Tour", None)


def test_no_artists_file_means_no_canonical_names(lib):
    (lib / "overrides" / "artists.json").unlink()
    assert catalogue.canonical_artist("Hieronymous Bosch") == ("Hieronymous Bosch", None)


def test_source_rank_order(lib):
    r = catalogue.source_rank
    t = {"payne_gae": "normal", "hodge_aid": "normal", "grovier_nws": "low", "brookehitching_mad": "normal"}
    order = [r("hodge_aid", "override", t), r("payne_gae", "clean", t), r("hodge_aid", "clean", t),
             r("payne_gae", "outline", t), r("hodge_aid", "outline", t), r("grovier_nws", "clean", t)]
    assert order == sorted(order) and len(set(order[:3])) == 3
    assert r("grovier_nws", "override", t) < r("payne_gae", "clean", t)       # an override wins even in a low-trust book
    assert r("grovier_nws", "outline", t) == r("grovier_nws", "clean", t) > r("hodge_aid", "outline", t)
    assert r("payne_gae", "outline", t) == r("hodge_aid", "outline", t)


def test_each_field_comes_from_the_most_trusted_source(lib):
    # one painting in four books; every book writes the artist differently and gives a different year
    put_works("payne_gae", [(1, "The Haywain", "Hieronymous Bosch", "1485", {"title": "outline", "artist": "outline", "year": "outline"})])
    put_works("hodge_aid", [(1, "The Haywain", "Hieronymus Bosch", "c. 1490", {"title": "clean", "artist": "clean", "year": "clean"})])
    put_works("hagen_wgps", [(1, "The Haywain", "Bosch", "1500", {"title": "clean", "artist": "clean", "year": "clean"})])
    put_works("grovier_nws", [(1, "The Hay Wain", "Hieronymus Bosch", "1510", {"title": "clean", "artist": "clean", "year": "clean"})])
    catalogue.regroup()
    a = artwork_of("payne_gae/001")
    assert sorted(a["works"]) == ["grovier_nws/001", "hagen_wgps/001", "hodge_aid/001", "payne_gae/001"]
    assert a["artist"] == "Hieronymus Bosch" and a["title"] == "The Haywain"
    # payne has only an outline value, hodge and hagen a clean scan value: the scan wins, hodge before hagen (book order)
    assert a["year"] == "c. 1490"
    ws = {w["id"]: w for w in catalogue.load_works("payne_gae") + catalogue.load_works("hodge_aid")}
    assert ws["payne_gae/001"]["artist"] == "Hieronymous Bosch"      # works.json keeps what each book says


def test_digital_clean_beats_scan_clean_beats_outline_beats_low_trust(lib):
    def year_of(rows):
        for bid, y, how in rows:
            put_works(bid, [(1, "The Kiss", "Gustav Klimt", y, {"year": how})])
        catalogue.regroup()
        out = artwork_of(rows[0][0] + "/001")["year"]
        for bid, *_ in rows:
            put_works(bid, [])
        return out
    assert year_of([("payne_gae", "1907", "outline"), ("hodge_aid", "1908", "clean"), ("grovier_nws", "1909", "clean")]) == "1908"
    assert year_of([("payne_gae", "1907", "clean"), ("hodge_aid", "1908", "clean"), ("grovier_nws", "1909", "clean")]) == "1907"
    assert year_of([("payne_gae", "1907", "outline"), ("hodge_aid", "1908", "outline"), ("grovier_nws", "1909", "clean")]) == "1907"
    assert year_of([("payne_gae", "1907", "outline"), ("grovier_nws", "1909", "clean")]) == "1907"
    assert year_of([("hodge_aid", "1908", "clean"), ("grovier_nws", "1909", "outline")]) == "1908"
    assert year_of([("payne_gae", "1907", "clean"), ("hodge_aid", "1908", "override")]) == "1908"      # a person's value wins


def test_override_beats_every_source_and_is_normalised(lib):
    put_works("payne_gae", [(1, "The Kiss", "Gustav Klimt", "1907", {"year": "clean", "artist": "clean"})])
    (lib / "overrides" / "payne_gae.json").write_text(json.dumps(
        {"payne_gae/001": {"year": "c.1907-8", "artist": "GUSTAV KLIMT"}}), encoding="utf-8")
    w = catalogue.load_works("payne_gae")[0]
    assert w["artist"] == "Gustav Klimt" and w["year"] == "c. 1907–1908" and w["field_src"]["year"] == "override" and w["year_num"] == 1907
    (lib / "overrides" / "payne_gae.json").write_text(json.dumps(
        {"payne_gae/001": {"year": "about 800 years"}}), encoding="utf-8")
    w = catalogue.load_works("payne_gae")[0]
    assert w["year"] is None and w["year_raw"] == "about 800 years"


def test_attribution_is_kept_in_its_own_field(lib):
    put_works("brookehitching_mad", [(1, "The Legend of the Baker of Eeklo", "Cornelis van Dalem", "c.1550-1650",
                                      {"artist": "outline", "year": "outline"})])
    ws = json.loads((config.book_dir("brookehitching_mad") / "works.json").read_text())
    ws[0]["attribution"] = "after"
    (config.book_dir("brookehitching_mad") / "works.json").write_text(json.dumps(ws), encoding="utf-8")
    catalogue.regroup()
    a = artwork_of("brookehitching_mad/001")
    assert a["artist"] == "Cornelis van Dalem" and a["attribution"] == "after" and not a["title"].lower().startswith("after")


# ---- the clean text and pick_fields
def clean_page(bid, page, text):
    d = config.LIB_DIR / "clean_text" / bid
    d.mkdir(parents=True, exist_ok=True)
    (d / f"page_{page:04d}.txt").write_text(text, encoding="utf-8")


def test_extract_clean_meta_gives_the_text_as_written(lib):
    clean_page("payne_gae", 1, "[page-type] body\n\n# RAIN, STEAM AND SPEED – THE GREAT WESTERN RAILWAY\n"
                               "[meta] CHAPTER 1\n[meta] J. M. W. TURNER\n[meta] 1844\n\nBody.\n")
    assert catalogue.extract_clean_meta("payne_gae", {"pdf_pages": [1, 2], "n": 1}) == {
        "title": "RAIN, STEAM AND SPEED – THE GREAT WESTERN RAILWAY", "artist": "J. M. W. TURNER", "year": "1844"}
    clean_page("hagen_wgps", 5, "[page-type] body\n\n# Propaganda on cloth\n[meta] Eugéne Delacroix: The Death of Sardanapalus, c. 1827\n")
    assert catalogue.extract_clean_meta("hagen_wgps", {"pdf_pages": [5, 10], "n": 1}) == {
        "artist": "Eugéne Delacroix", "title": "The Death of Sardanapalus", "year": "c. 1827", "headline": "Propaganda on cloth"}
    assert catalogue.extract_clean_meta("payne_gae", {"pdf_pages": [7, 9], "n": 2}) == {}        # no clean page


def test_pick_fields_prefers_clean_text_and_normalises(lib):
    out = {"title": "Rail, Steam and Speed", "artist": "J. M. W. Turner", "year": "1840"}
    clean = {"title": "RAIN, STEAM AND SPEED – THE GREAT WESTERN RAILWAY", "artist": "J. M. W. TURNER", "year": "1844"}
    f, src = catalogue.pick_fields("payne_gae", out, clean)
    assert f == {"title": "Rain, Steam and Speed – The Great Western Railway", "artist": "J. M. W. Turner", "year": "1844"}
    assert src == {"title": "clean", "artist": "clean", "year": "clean"}
    f, src = catalogue.pick_fields("payne_gae", out, {})
    assert f["title"] == "Rail, Steam and Speed" and src == {"title": "outline", "artist": "outline", "year": "outline"}


def test_pick_fields_keeps_the_better_case_of_the_outline(lib):
    f, src = catalogue.pick_fields("brookehitching_mad", {"title": "Judith Slaying Holofernes", "artist": "Artemisia Gentileschi",
                                                          "year": "1612-13"},
                                   {"title": "JUDITH SLAYING HOLOFERNES", "artist": "ARTEMISIA GENTILESCHI", "year": "1612-13"})
    assert f["title"] == "Judith Slaying Holofernes" and f["artist"] == "Artemisia Gentileschi" and f["year"] == "1612–1613"
    assert src["title"] == "clean"
    f, _ = catalogue.pick_fields("brookehitching_mad", {"title": "Fairy Feller’s Master-Stroke", "artist": None, "year": None},
                                 {"title": "The Fairy Feller’s Master- Stroke"})
    assert f["title"] == "The Fairy Feller’s Master-Stroke"            # the clean text is a hyphen broken at a line end


def test_pick_fields_year_that_is_not_a_year(lib):
    f, src = catalogue.pick_fields("grovier_nws", {"title": "The Book of Kells", "artist": None, "year": None},
                                   {"year": "approximately 800 years", "title": "THE BOOK OF KELLS"})
    assert f["year"] is None and f["year_raw"] == "approximately 800 years" and f["title"] == "The Book of Kells"
    assert src["year"] == "clean" and "title" in src and src["title"] == "outline"      # a low-trust book gives only its year
    # the clean text has no usable year but the outline has: the year is taken from the outline
    f, src = catalogue.pick_fields("payne_gae", {"title": "T", "artist": "A", "year": "1500"}, {"year": "after 1500"})
    assert f["year"] == "1500" and "year_raw" not in f and src["year"] == "outline"
    f, _ = catalogue.pick_fields("brookehitching_mad", {"title": "T", "artist": None, "year": "seventeenth century"}, {})
    assert f["year"] is None and f["year_raw"] == "seventeenth century"


def test_after_in_the_artist_of_a_source(lib):
    f, _ = catalogue.pick_fields("brookehitching_mad", {"title": "T", "artist": "After Cornelis Van Dalem", "year": None}, {})
    assert f["artist"] == "Cornelis van Dalem" and f["attribution"] == "after"
    f, _ = catalogue.pick_fields("brookehitching_mad", {"title": "T", "artist": "Cornelis van Dalem", "year": None, "attribution": "after"}, {})
    assert f["attribution"] == "after"


# ---- 3. years: one parse function, one print function
YEARS = [  # every form that occurs in the catalogue -> printed form
    ("1434", "1434"), ("1085–1145", "1085–1145"), ("1459-61", "1459–1461"), ("1482/83", "1482–1483"),
    ("1599/1600", "1599–1600"), ("1907–8", "1907–1908"), ("1830–32", "1830–1832"), ("1490-1500", "1490–1500"),
    ("1562-1566", "1562–1566"), ("1914–26", "1914–1926"), ("1909-26", "1909–1926"), ("1932-67", "1932–1967"),
    ("between 1485 and 1490", "1485–1490"), ("c. 1303-05", "c. 1303–1305"), ("c.1460", "c. 1460"), ("c. 1460", "c. 1460"),
    ("c.1473-5", "c. 1473–1475"), ("c.1580-90", "c. 1580–1590"), ("c.1550-1650", "c. 1550–1650"), ("c. 1819–23", "c. 1819–1823"),
    ("c. 1727-45", "c. 1727–1745"), ("1563-c.1590", "c. 1563–1590"), ("c.1950-64", "c. 1950–1964"),
    ("c.900 bc", "c. 900 BC"), ("c. 900 BC", "c. 900 BC"), ("c.1600 bc", "c. 1600 BC"), ("c.480 bc", "c. 480 BC"),
    ("444 B.C.", "444 BC"), ("(approximately 210 B.C.)", "c. 210 BC"), ("645 B.C. - 635 B.C.", "645–635 BC"),
    ("38,000-33,000 bc", "38,000–33,000 BC"), ("27-68 B.C.", "27 BC–AD 68"), ("27 BC–AD 68", "27 BC–AD 68"),
    ("113", "AD 113"), ("x913", "1913"),
]
NOT_YEARS = ["About 60 B.C. - 50 years ago", "approximately 800 years", "approximately 1,000 years", "approximately 1077 or later",
             "approximately 1503-1506 years", "after 1066", "after 1475", "before 1500", "late second century",
             "early thirteenth century", "seventeenth century", "fifteenth-seventeenth centuries", "twentieth century",
             "", "  ", None, "60", "1500-1400", "unknown"]


@pytest.mark.parametrize("raw,printed", YEARS)
def test_year_forms(raw, printed):
    p = parse.parse_year(raw)
    assert p is not None, raw
    assert parse.print_year(p) == printed
    assert parse.parse_year(printed) == p            # printing and parsing agree: the printed form is stable


@pytest.mark.parametrize("raw", NOT_YEARS)
def test_text_that_is_not_a_year(raw):
    assert parse.parse_year(raw) is None
    year, year_raw = parse.normalise_year(raw)
    assert year is None and year_raw == (raw.strip() if raw and raw.strip() else None)


def test_parsed_year_shape():
    assert parse.parse_year("1434") == {"from": 1434, "to": None, "circa": False, "era": "AD"}
    assert parse.parse_year("c. 1562-66") == {"from": 1562, "to": 1566, "circa": True, "era": "AD"}
    assert parse.parse_year("c. 900 BC") == {"from": 900, "to": None, "circa": True, "era": "BC"}
    assert parse.parse_year("27 BC-AD 68") == {"from": 27, "to": 68, "circa": False, "era": "BC-AD"}
    assert parse.print_year(None) is None


def test_year_num_follows_the_parse():
    assert parse.year_num("c. 1562–1566") == 1562 and parse.year_num("c. 900 BC") == -900 and parse.year_num("27 BC–AD 68") == -27
    assert parse.year_num("seventeenth century") == 1650 and parse.year_num("after 1475") == 1475      # as a sort key only
    assert parse.year_num("approximately 1,000 years") is None and parse.year_num(None) is None


# ---- 4. aliases and the keys that must not change
def test_changed_key_is_kept_as_an_alias_and_old_links_open(lib):
    put_works("payne_gae", [(1, "Rail, Steam and Speed", "J. M. W. Turner", "1844", None)])
    catalogue.regroup()
    assert "turner-rail-steam-and-speed" in catalogue.load_artworks()
    put_works("payne_gae", [(1, "Rain, Steam and Speed – The Great Western Railway", "J. M. W. Turner", "1844", None)])
    catalogue.regroup()
    arts = catalogue.load_artworks()
    new = "turner-rain-steam-and-speed-the"
    assert list(arts) == [new] and arts[new]["aliases"] == ["turner-rail-steam-and-speed"]
    old = "turner-rail-steam-and-speed"
    assert arts[old]["title"].startswith("Rain, Steam") and arts.get(old) is arts[new] and arts.resolve(old) == new
    assert old not in arts and old not in list(arts) and len(arts) == 1        # an alias is not a second artwork
    assert catalogue.get_artwork(old)["works"] == ["payne_gae/001"] and catalogue.resolve_key(old) == new
    assert catalogue.get_artwork("no-such-key") is None and arts.get("no-such-key", 5) == 5
    with pytest.raises(KeyError):
        arts["no-such-key"]
    assert json.loads((lib / "overrides" / "aliases.json").read_text()) == {old: new}


def test_alias_follows_the_artwork_when_its_key_changes_again(lib):
    put_works("payne_gae", [(1, "Rail", "J. M. W. Turner", "1844", None)])
    catalogue.regroup()
    put_works("payne_gae", [(1, "Rain", "J. M. W. Turner", "1844", None)])
    catalogue.regroup()
    put_works("payne_gae", [(1, "Rain Steam", "J. M. W. Turner", "1844", None)])
    catalogue.regroup()
    assert json.loads((lib / "overrides" / "aliases.json").read_text()) == {
        "turner-rail": "turner-rain-steam", "turner-rain": "turner-rain-steam"}
    assert catalogue.get_artwork("turner-rail")["title"] == "Rain Steam"
    catalogue.regroup()                              # nothing changed: nothing is recorded or lost
    assert len(json.loads((lib / "overrides" / "aliases.json").read_text())) == 2


def test_merged_artworks_keep_both_old_keys(lib):
    put_works("payne_gae", [(1, "The Kiss", "Gustav Klimt", "1907", None)])
    put_works("hodge_aid", [(1, "Kiss, The Lovers", "Gustav Klimt", "1907", None)])
    catalogue.regroup()
    assert len(catalogue.load_artworks()) == 2
    (lib / "overrides" / "artworks.json").write_text(json.dumps({"merge": [["payne_gae/001", "hodge_aid/001"]], "split": []}))
    catalogue.regroup()
    arts = catalogue.load_artworks()
    assert len(arts) == 1
    (key,) = arts
    assert {catalogue.resolve_key(k) for k in ("klimt-the-kiss", "klimt-kiss-the-lovers")} == {key}


def test_a_live_key_is_never_shadowed_by_an_alias(lib):
    (lib / "overrides" / "aliases.json").write_text(json.dumps({"turner-rain": "turner-rail", "turner-rail": "turner-rain"}))
    put_works("payne_gae", [(1, "Rail", "J. M. W. Turner", "1844", None), (2, "Rain", "J. M. W. Turner", "1844", None)])
    catalogue.regroup()
    arts = catalogue.load_artworks()
    assert arts["turner-rail"]["title"] == "Rail" and arts["turner-rain"]["title"] == "Rain"
    assert not any("aliases" in a for a in arts.values())


def test_dossier_of_an_old_key_opens(lib):
    from bti.library import dossiers
    put_works("payne_gae", [(1, "Rain", "J. M. W. Turner", "1844", None)])
    catalogue.regroup()
    (lib / "overrides" / "aliases.json").write_text(json.dumps({"turner-rail": "turner-rain"}))
    catalogue.write_json(dossiers.dossier_path("turner-rain"), {"artwork_key": "turner-rain", "sources": []})
    assert dossiers.load("turner-rail")["artwork_key"] == "turner-rain"
    assert dossiers.load("turner-rain")["artwork_key"] == "turner-rain" and dossiers.load("nothing-here") is None


def test_protected_keys_do_not_change(lib):
    put_works("payne_gae", [(1, "The Scream", "Edvard Munch", "1893", {"title": "outline", "artist": "outline"}),
                            (2, "The Arnolfini Portrait", "Jan Van Eyck", "1434", {"title": "outline", "artist": "outline"})])
    put_works("hodge_aid", [(1, "The Scream", "Edvard Munch", "1893", {"title": "clean", "artist": "clean"}),
                            (2, "The Arnolfini Portrait", "Jan van Eyck", "1434", {"title": "clean", "artist": "clean"})])
    catalogue.regroup()
    arts = catalogue.load_artworks()
    assert set(catalogue.PINNED_KEYS) == {"eyck-the-arnolfini-portrait", "munch-the-scream"}
    for k in catalogue.PINNED_KEYS:
        assert k in arts and not arts.aliases.get(k)


@pytest.mark.skipif(not BUILT, reason="library not built")
def test_protected_keys_in_the_built_library():
    arts = catalogue.load_artworks()
    assert arts["eyck-the-arnolfini-portrait"]["title"] == "The Arnolfini Portrait"
    assert arts["munch-the-scream"]["title"] == "The Scream"
    for k in catalogue.PINNED_KEYS:
        assert dict.__contains__(arts, k) and arts.resolve(k) == k


def test_project_key_is_kept_when_the_title_changes(lib):
    put_works("payne_gae", [(1, "Rain, Steam and Speed – The Great Western Railway", "J. M. W. Turner", "1844", None)])
    proj = config.PROJECTS_DIR / "turner"
    proj.mkdir(parents=True)
    (proj / "project.json").write_text(json.dumps({"id": "turner", "artwork_key": "turner-rail-steam-and-speed",
                                                   "sources": [{"work_id": "payne_gae/001"}]}), encoding="utf-8")
    catalogue.regroup()
    arts = catalogue.load_artworks()
    assert list(arts) == ["turner-rail-steam-and-speed"]
    assert not (lib / "overrides" / "aliases.json").exists()
