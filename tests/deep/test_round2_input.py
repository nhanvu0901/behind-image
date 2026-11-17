"""Round 2: broken input. Nothing may answer 500, write a half file or write outside the project."""
from __future__ import annotations

import itertools
import json

import pytest

from conftest import state, strip


_ids = itertools.count()


def P(pid):
    return f"/api/projects/{pid}"


def raw_post(client, method, url, obj):
    return client.request(method, url, content=json.dumps(obj), headers={"content-type": "application/json"})


def nested(n):
    d = cur = {}
    for _ in range(n):
        cur["a"] = {}
        cur = cur["a"]
    return d


def test_R2B_006_deeply_nested_storyboard_is_422_not_500(client, arn):
    st = state(client, arn)
    deep = nested(2000)
    for method, url, body in [
        ("POST", P(arn) + "/validate", {"storyboard": deep}),
        ("POST", P(arn) + "/frame", {"t": 1, "storyboard": deep}),
        ("POST", P(arn) + "/preview", {"t0": 0, "t1": 1, "storyboard": deep}),
        ("PUT", P(arn) + "/storyboard", {"storyboard": deep, "base_rev": st["rev"]}),
    ]:
        r = raw_post(client, method, url, body)
        assert r.status_code < 500, f"{method} {url.rsplit('/', 1)[-1]} -> {r.status_code} {r.text[:100]}"
    assert state(client, arn)["rev"] == st["rev"]


@pytest.mark.parametrize("body", [{"work_ids": [[]]}, {"work_ids": [{}]}, {"work_ids": [1]},
                                  {"artwork_key": "bosch-the-garden-of-earthly-delights", "exclude": [[]]},
                                  {"artwork_key": "bosch-the-garden-of-earthly-delights", "exclude": [{}]}])
def test_R2B_007_create_project_with_wrong_typed_lists_is_422(client, projects_root, body):
    before = sorted(p.name for p in projects_root.iterdir())
    r = client.post("/api/library/projects", json=body)
    assert r.status_code in (404, 422), f"{body} -> {r.status_code} {r.text[:100]}"
    assert sorted(p.name for p in projects_root.iterdir()) == before


def test_R2B_008_huge_integers_are_422_not_500(client, arn):
    big = 10 ** 400
    for method, url, body in [
        ("POST", P(arn) + "/frame", {"t": big, "storyboard": {}}),
        ("POST", P(arn) + "/preview", {"t0": 0, "t1": big}),
        ("POST", P(arn) + "/preview", {"t0": big, "t1": 1}),
    ]:
        r = raw_post(client, method, url, body)
        assert r.status_code == 422, f"{method} {url.rsplit('/', 1)[-1]} {str(body)[:30]} -> {r.status_code} {r.text[:80]}"
    r = client.get(P(arn) + "/frame", params={"t": "1" + "0" * 400})
    assert r.status_code == 422


def test_R2B_009_overlong_path_segment_is_404_not_500(client, arn):
    seg = "a" * 300
    for url in [P(arn) + f"/files/{seg}", f"/style/gae/previews/{seg}", f"/api/library/artworks/{seg}", f"/{seg}",
                f"/api/library/artworks/x/source/{seg}"]:
        r = client.get(url)
        assert r.status_code == 404, f"GET {url[:40]}... -> {r.status_code} {r.text[:80]}"


def test_R2B_011_upload_without_title_uses_the_file_name_not_the_temp_name(client, arn):
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(b, "PNG")
    r = client.post(P(arn) + "/assets/upload", files={"file": ("my_picture.png", b.getvalue(), "image/png")},
                    data={"title": "", "licence": "CC0", "source_url": "http://x", "author": "me"})
    assert r.status_code == 200, r.text
    assert "my_picture" in r.json()["asset"]["title"], r.json()["asset"]["title"]


def _corrupt(projects_root, pid, rel, data: bytes):
    f = projects_root / pid / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(data)


@pytest.mark.parametrize("data", [b"[1]", b"null", b"3"])
def test_R2B_014_one_project_json_of_the_wrong_shape_does_not_break_the_lists(client, make_project, projects_root, data):
    """A project.json that is valid JSON but not an object must not take down the home list or the library list."""
    pid = make_project("arnolfini-from-books", "t_r2_pj")
    _corrupt(projects_root, pid, "project.json", data)
    r = client.get("/api/projects")
    assert r.status_code == 200, f"GET /api/projects -> {r.status_code} {r.text[:80]}"
    r = client.get("/api/library/artworks")
    assert r.status_code == 200, f"GET /api/library/artworks -> {r.status_code} {r.text[:80]}"


@pytest.fixture()
def lib_pid(client, projects_root):
    import itertools, shutil
    pid = f"r2-lib-{next(_ids)}"
    r = client.post("/api/library/projects", json={"artwork_key": "bosch-the-garden-of-earthly-delights", "slug": pid})
    assert r.status_code == 200, r.text
    yield pid
    shutil.rmtree(projects_root / pid, ignore_errors=True)


@pytest.mark.parametrize("rel,data", [("script/brief_options.json", b"[1]"), ("script/brief_options.json", b"3"),
                                      ("source/payne_gae_004.txt", b"\xff\xfe\x00\x01 not utf-8")])
def test_R2B_014_damaged_script_inputs_are_409_not_500(client, lib_pid, projects_root, rel, data):
    _corrupt(projects_root, lib_pid, rel, data)
    for url in (P(lib_pid) + "/brief", P(lib_pid) + "/outline", P(lib_pid) + "/narration"):
        r = client.get(url)
        assert r.status_code < 500, f"GET {url.rsplit('/', 1)[-1]} -> {r.status_code} {r.text[:80]}"
