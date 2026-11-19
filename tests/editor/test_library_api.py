import json

import pytest

from bti.library import catalogue, config, dossiers

BUILT = (config.LIB_DIR / "books" / "hodge_aid" / "works.json").is_file()
pytestmark = pytest.mark.skipif(not BUILT, reason="run python -m bti.library build first")


def test_books(client):
    j = client.get("/api/library/books").json()
    assert {b["id"] for b in j} >= {"payne_gae", "hodge_aid"}
    assert all("n_with_project" in b and b["cover_url"] for b in j)


def test_works_filters_and_also_in(client):
    j = client.get("/api/library/books/hodge_aid/works").json()
    assert len(j) == 100 and all(w["thumb_url"] for w in j)
    arn = client.get("/api/library/books/hodge_aid/works", params={"q": "arnolfini"}).json()
    assert len(arn) == 1 and {o["book_id"] for o in arn[0]["also_in"]} == {"payne_gae", "brookehitching_mad"}
    multi = client.get("/api/library/books/hodge_aid/works", params={"multi": "true"}).json()
    assert 5 < len(multi) < 100 and all(w["also_in"] for w in multi)
    pd = client.get("/api/library/books/hodge_aid/works", params={"rights": "copyright_likely"}).json()
    assert pd and all(w["rights"]["status"] == "copyright_likely" for w in pd)
    c15 = client.get("/api/library/books/hodge_aid/works", params={"century": 15}).json()
    assert c15 and all(w["century"] == 15 for w in c15)


def test_detail_text_images_and_pages(client):
    d = client.get("/api/library/works/hodge_aid/3").json()
    assert d["ocr"] is True and "Arnolfini" in d["text"] and len(d["pages"]) == 4 and d["images"] == []
    p = client.get("/api/library/works/payne_gae/2").json()
    assert p["ocr"] is False and p["images"] and p["text_source"] in ("clean", "mixed", "layer")
    r = client.get(d["pages"][0]["url"].split("?")[0], params={"w": 200})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    im = client.get(p["images"][0]["url"])
    assert im.status_code == 200 and im.headers["content-type"] == "image/jpeg"


def test_artwork(client):
    a = client.get("/api/library/artworks/eyck-the-arnolfini-portrait").json()
    assert len(a["works"]) == 3 and len(a["works_detail"]) == 3


def test_path_and_id_validation(client):
    g = client.get
    assert g("/api/library/books/nope/works").status_code == 404
    assert g("/api/library/books/..%2f..%2fetc/works").status_code == 404
    assert g("/api/library/books/hodge_aid/cover.jpg", params={"w": 99999}).status_code == 422
    assert g("/api/library/works/hodge_aid/999").status_code == 404
    assert g("/api/library/works/hodge_aid/abc").status_code == 422
    assert g("/api/library/works/hodge_aid/3/page/999.jpg").status_code == 404   # outside the entry
    assert g("/api/library/works/hodge_aid/3/page/30.jpg").status_code == 404
    assert g("/api/library/works/hodge_aid/3/page/22.jpg", params={"w": 5}).status_code == 422
    assert g("/api/library/works/payne_gae/2/image/1.jpg").status_code == 404    # xref not in the entry
    assert g("/api/library/works/..%2f..%2fx/3").status_code in (404, 422)
    assert g("/api/library/artworks/..%2f..%2fx").status_code == 404
    assert g("/api/library/artworks/nope").status_code == 404


def test_create_project_endpoint(client):
    post = lambda body: client.post("/api/library/projects", json=body)
    r = post({"work_ids": ["payne_gae/002", "hodge_aid/003"], "slug": "arn-api"})
    assert r.status_code == 200 and r.json()["id"] == "arn-api"
    assert (client.root / "arn-api" / "project.json").is_file()
    assert post({"work_ids": ["payne_gae/002"], "slug": "arn-api"}).status_code == 409
    assert post({"work_ids": ["payne_gae/002"], "slug": "../evil"}).status_code == 422
    assert post({"work_ids": ["x/001"]}).status_code in (404, 422)
    assert post({"work_ids": []}).status_code == 422
    assert not (client.root.parent / "evil").exists()
    js = client.get("/api/projects").json()
    mine = next(p for p in js if p["id"] == "arn-api")
    assert mine["stage"] == "selected" and mine["has_storyboard"] is False
    works = client.get("/api/library/books/hodge_aid/works", params={"q": "arnolfini"}).json()
    assert works[0]["projects"][0]["id"] == "arn-api"


def test_projects_stage_and_has_storyboard(client):
    js = client.get("/api/projects").json()
    from editor_helpers import PID
    p = next(x for x in js if x["id"] == PID)
    assert p["has_storyboard"] is True and p["stage"] in ("storyboard", "approved", "rendered")


# ---------------------------------------------------------------- artwork-centred endpoints
DOS = (config.LIB_DIR / "dossiers" / "eyck-the-arnolfini-portrait" / "dossier.json").is_file()


@pytest.mark.skipif(not DOS, reason="run python -m bti.library dossiers first")
def test_artwork_by_old_key_answers_with_the_current_key(client, monkeypatch):
    monkeypatch.setattr(catalogue, "load_aliases", lambda: {"arnolfini-old-key": "eyck-the-arnolfini-portrait"})
    g = client.get
    new = g("/api/library/artworks/eyck-the-arnolfini-portrait").json()
    old = g("/api/library/artworks/arnolfini-old-key")
    assert old.status_code == 200
    j = old.json()
    assert j["artwork_key"] == "eyck-the-arnolfini-portrait" and j["title"] == new["title"] and j["works"] == new["works"]
    assert all("arnolfini-old-key" not in s["text_url"] for s in (j["dossier"] or {}).get("sources", []))
    stem = (new["dossier"]["sources"][0]["text_url"]).rsplit("/", 1)[1]
    assert g("/api/library/artworks/arnolfini-old-key/source/" + stem).status_code == 200
    assert g("/api/library/artworks/not-an-old-key").status_code == 404


def test_artworks_list_filters_sort(client):
    g = client.get
    rows = g("/api/library/artworks").json()
    assert len(rows) > 250 and all(r["kind"] == "artwork" for r in rows)
    assert rows[0]["n_sources"] >= rows[-1]["n_sources"]
    assert rows[0]["n_sources"] == 4  # Garden of Earthly Delights first
    multi = g("/api/library/artworks", params={"min_sources": 2}).json()
    assert 30 <= len(multi) < 60 and all(r["n_sources"] >= 2 for r in multi)
    q = g("/api/library/artworks", params={"q": "arnolfini"}).json()
    assert len(q) == 1 and set(q[0]["books"]) == {"payne_gae", "hodge_aid", "brookehitching_mad"}
    assert q[0]["rights"]["status"] in ("pd_likely", "copyright_likely", "unknown")
    assert all(r["century"] == 15 for r in g("/api/library/artworks", params={"century": 15}).json())
    assert g("/api/library/artworks", params={"has_project": "true"}).json() == []
    assert g("/api/library/artworks", params={"sort": "nope"}).status_code == 422
    themes = g("/api/library/artworks", params={"kind": "theme"}).json()
    assert len(themes) == 12


@pytest.mark.skipif(not DOS, reason="dossiers not built")
def test_artwork_detail_dossier_and_source_text(client):
    d = client.get("/api/library/artworks/eyck-the-arnolfini-portrait").json()
    dos = d["dossier"]
    assert dos["totals"]["books"] == 3 and len(d["works_detail"]) == 3
    s = dos["sources"][0]
    assert s["pages"] and s["text_url"]
    t = client.get(s["text_url"]).json()
    assert t["work_id"] == s["work_id"] and "Arnolfini" in t["text"]
    assert "Photo" not in t["text"]
    assert client.get("/api/library/artworks/eyck-the-arnolfini-portrait/source/..%2fx").status_code == 404
    assert client.get("/api/library/artworks/eyck-the-arnolfini-portrait/source/nope_001").status_code == 404
    assert client.get("/api/library/artworks/nope/source/payne_gae_002").status_code == 404


@pytest.mark.skipif(not DOS, reason="dossiers not built")
def test_create_project_from_artwork(client):
    post = lambda b: client.post("/api/library/projects", json=b)
    r = post({"artwork_key": "eyck-the-arnolfini-portrait", "exclude": ["hodge_aid/003"], "slug": "arn-art-api"})
    assert r.status_code == 200 and len(r.json()["sources"]) == 2 and r.json()["dossier"]
    assert (client.root / "arn-art-api" / "source" / "dossier.json").is_file()
    assert post({"artwork_key": "eyck-the-arnolfini-portrait", "slug": "arn-art-api"}).status_code == 409
    assert post({"artwork_key": "nope"}).status_code == 404
    assert post({"artwork_key": "eyck-the-arnolfini-portrait", "work_ids": ["payne_gae/002"]}).status_code == 422
    assert post({"artwork_key": "eyck-the-arnolfini-portrait", "exclude": "x"}).status_code == 422
    row = client.get("/api/library/artworks", params={"q": "arnolfini"}).json()[0]
    assert row["projects"][0]["id"] == "arn-art-api"


@pytest.fixture()
def tmplib(tmp_path, monkeypatch):
    import shutil
    dst = tmp_path / "library"
    shutil.copytree(config.LIB_DIR, dst, ignore=shutil.ignore_patterns("cache", "text_audit"))
    monkeypatch.setattr(config, "LIB_DIR", dst)
    return dst


def test_merge_split_endpoint_validation(client, tmplib):
    p = client.post
    assert p("/api/library/artworks/merge", json={}).status_code == 422
    assert p("/api/library/artworks/merge", json={"key": "a", "with": "b"}).status_code == 404
    assert p("/api/library/artworks/split", json={"work_id": "../x"}).status_code == 422
    assert p("/api/library/artworks/split", json={"work_id": "payne_gae/999"}).status_code == 404
    assert p("/api/library/artworks/split", json={"work_id": "hodge_aid/001"}).status_code == 422  # alone already
    r = p("/api/library/artworks/split", json={"work_id": "brookehitching_mad/011"})
    assert r.status_code == 200
    key = r.json()["artwork_key"]
    assert client.get(f"/api/library/artworks/{key}").json()["works"] == ["brookehitching_mad/011"]
    m = p("/api/library/artworks/merge", json={"key": key, "with": "eyck-the-arnolfini-portrait"})
    assert m.status_code == 200
    assert len(client.get(f"/api/library/artworks/{m.json()['artwork_key']}").json()["works"]) == 3
    assert json.loads((tmplib / "overrides" / "artworks.json").read_text())["merge"]


LEVELS = {"normal", "restored", "low"}
GARDEN = "bosch-the-garden-of-earthly-delights"


@pytest.mark.skipif(not DOS, reason="dossiers not built")
def test_low_trust_fields_and_default_exclusion(client):
    """True before and after library/restored/grovier_nws is installed and the dossiers are rebuilt: Grovier's work is `low` in the
    first state and `restored` in the second, so this reads the trust values the dossier itself holds and checks that the API
    rows, the dossier view and the project defaults agree with them. A low source in by default, or a trust field that is gone, fails here."""
    row = client.get("/api/library/artworks", params={"q": "garden of earthly"}).json()[0]
    own = dossiers.load(GARDEN)                                       # the dossier as it was built
    own_trust = {s["book_id"]: s["trust"] for s in own["sources"]}
    g = own_trust["grovier_nws"]
    assert g in ("low", "restored") and set(own_trust.values()) <= LEVELS
    assert all(v == "normal" for b, v in own_trust.items() if b != "grovier_nws")
    shown = client.get(f"/api/library/artworks/{GARDEN}").json()["dossier"]
    assert {s["book_id"]: s["trust"] for s in shown["sources"]}["grovier_nws"] == g      # the page never labels the text above what it is
    # the row: every field is there and says what the dossier says
    for k in ("low_trust_books", "restored_books", "words_normal", "words_restored", "words_low", "only_low_trust", "no_normal_source"):
        assert k in row, k
    t = own["totals"]
    assert t["words"] == t["words_normal"] + t.get("words_restored", 0) + t["words_low"]
    assert (row["words_normal"], row["words_restored"], row["words_low"]) == (t["words_normal"], t.get("words_restored", 0), t["words_low"])
    assert row["words_normal"] > 0 and (row["words_low"] > 0) == (g == "low") and (row["words_restored"] > 0) == (g == "restored")
    assert row["low_trust_books"] == (["grovier_nws"] if g == "low" else []) and row["restored_books"] == (["grovier_nws"] if g == "restored" else [])
    assert row["only_low_trust"] is False and row["no_normal_source"] is False         # the other three books are normal sources
    # artworks that only Grovier covers: `low` before, `restored` after (works 2 and 54 stay low); none of them has a normal source
    rows = client.get("/api/library/artworks").json()
    solo = [r for r in rows if r["books"] == ["grovier_nws"]]
    assert len(solo) > 10
    for r in solo:
        lv = dossiers.load(r["artwork_key"])["sources"][0]["trust"]
        assert lv in ("low", "restored") and r["only_low_trust"] is (lv == "low") and r["no_normal_source"] is True
    assert all(r["books"] == ["grovier_nws"] for r in rows if r["only_low_trust"])
    # default sources: a low source is left out when others remain, a normal or restored one stays; judged by the project's own copy
    a = client.post("/api/library/projects", json={"artwork_key": GARDEN, "slug": "g1"}).json()
    got = {s["work_id"] for s in a["sources"]}
    mine = {s["work_id"]: s["trust"] for s in json.loads((client.root / "g1" / "source" / "dossier.json").read_text(encoding="utf-8"))["sources"]}
    assert set(mine) == got and set(mine.values()) <= LEVELS and "low" not in mine.values()
    assert ("grovier_nws/018" in got) == (mine.get("grovier_nws/018") == "restored") and len(got) == 3 + ("grovier_nws/018" in got)
    # an explicit empty exclude keeps everything
    b = client.post("/api/library/projects", json={"artwork_key": GARDEN, "slug": "g2", "exclude": []}).json()
    assert len(b["sources"]) == 4
    both = {s["work_id"]: s["trust"] for s in json.loads((client.root / "g2" / "source" / "dossier.json").read_text(encoding="utf-8"))["sources"]}
    assert both["grovier_nws/018"] in ("low", "restored") and len(both) == 4
    # an artwork with only one source keeps it, whatever its level
    c = client.post("/api/library/projects", json={"artwork_key": solo[0]["artwork_key"], "slug": "g3"})
    assert c.status_code == 200 and len(c.json()["sources"]) == 1


@pytest.mark.skipif(not DOS, reason="dossiers not built")
def test_a_low_source_is_left_out_by_default_in_any_state_of_the_library(client, tmplib):
    """The exclusion rule itself, on the real artwork, whatever the state of the restoration: the owner forces Grovier to `low`."""
    (tmplib / "overrides" / "books.json").write_text(json.dumps({"grovier_nws": {"trust": "low", "force": True}}), encoding="utf-8")
    post = lambda b: client.post("/api/library/projects", json=b)
    a = post({"artwork_key": GARDEN, "slug": "gl1"}).json()
    assert "grovier_nws/018" not in [s["work_id"] for s in a["sources"]] and len(a["sources"]) == 3
    mine = json.loads((client.root / "gl1" / "source" / "dossier.json").read_text(encoding="utf-8"))
    assert {s["trust"] for s in mine["sources"]} == {"normal"}
    b = post({"artwork_key": GARDEN, "slug": "gl2", "exclude": []}).json()
    assert len(b["sources"]) == 4
    both = json.loads((client.root / "gl2" / "source" / "dossier.json").read_text(encoding="utf-8"))
    g = next(s for s in both["sources"] if s["work_id"] == "grovier_nws/018")
    assert g["trust"] == "low" and g["text_source"] == "clean"                  # forced low: the plain text, not the restored one
    solo = next(r for r in client.get("/api/library/artworks").json() if r["books"] == ["grovier_nws"])
    assert solo["low_trust_books"] == ["grovier_nws"] and solo["restored_books"] == []
    c = post({"artwork_key": solo["artwork_key"], "slug": "gl3"})
    assert c.status_code == 200 and len(c.json()["sources"]) == 1               # only a low source: kept, not empty


def test_search_with_d_bar_is_not_an_empty_search(client):
    """U1-001: q=đ used to fold to nothing and match every artwork."""
    all_ = client.get("/api/library/artworks", params={"kind": "artwork"}).json()
    q = client.get("/api/library/artworks", params={"kind": "artwork", "q": "đ"}).json()
    plain = client.get("/api/library/artworks", params={"kind": "artwork", "q": "d"}).json()
    assert 0 < len(q) < len(all_) and q == plain
