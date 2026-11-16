import json

import pytest

from bti.library import catalogue, config

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
