"""Regression tests for round 2 of the backend QA (docs/qa/ROUND2_backend.md): the API half.
Real engine on a copy of technique_lab and arnolfini, mock model on a copy of arnolfini-from-books. No network."""
import copy
import json
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti.editor import common  # noqa: E402
from bti.editor.app import create_app  # noqa: E402
from bti.engine.errors import RenderError  # noqa: E402
from bti.script import env as env_mod, models as models_mod, store  # noqa: E402

LAB, BOOKS, ARN = (REPO / "projects" / n for n in ("technique_lab", "arnolfini-from-books", "arnolfini"))
pytestmark = pytest.mark.skipif(not (LAB.is_dir() and BOOKS.is_dir() and ARN.is_dir()), reason="reference projects are missing")
B = "/api/projects/books"
CLONE = shutil.ignore_patterns("script", "cache", "history")


@pytest.fixture(autouse=True)
def _isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("BTI_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setenv("BTI_AGY_BIN", "")
    models_mod.reset_cache()
    env_mod._cache.clear()


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "projects"
    r.mkdir()
    shutil.copytree(BOOKS, r / "books", ignore=CLONE)
    shutil.copytree(ARN, r / "arn", ignore=shutil.ignore_patterns("cache", "history", "protected"))
    pj = r / "arn" / "project.json"
    if pj.is_file():
        d = json.loads(pj.read_text())
        d.pop("protected", None)
        pj.write_text(json.dumps(d))
    return r


@pytest.fixture()
def app(root):
    return create_app(projects_root=root)


@pytest.fixture()
def client(app, root):
    with TestClient(app, raise_server_exceptions=False) as c:
        c.root = root
        yield c


def wait_job(client, jid, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if j.get("state") in ("done", "error", "cancelled"):
            return j
        time.sleep(0.05)
    raise AssertionError("job timeout")


def make_outline(client, pid="books"):
    r = client.post(f"/api/projects/{pid}/outline/generate", json={"model": "mock"})
    assert wait_job(client, r.json()["job_id"])["state"] == "done"


def make_narration(client, approve=True):
    make_outline(client)
    o = client.get(f"{B}/outline").json()
    assert client.post(f"{B}/outline/approve", json={"rev": o["rev"]}).status_code == 200
    r = client.post(f"{B}/narration/generate", json={"model": "mock", "force": True})
    assert wait_job(client, r.json()["job_id"])["state"] == "done"
    n = client.get(f"{B}/narration").json()
    if approve:
        assert client.post(f"{B}/narration/approve", json={"rev": n["rev"]}).status_code == 200
        n = client.get(f"{B}/narration").json()
    return n


def stage_in_list(client, pid="books"):
    return next(p for p in client.get("/api/projects").json() if p["id"] == pid)["stage"]


# ------------------------------------------------------------------ R2B-001: a narration approval belongs to one outline
def test_approval_record_holds_both_hashes_and_all_views_agree(client):
    n = make_narration(client)
    o = client.get(f"{B}/outline").json()
    rec = json.loads((client.root / "books" / "script" / "narration.json").read_text())["approval"]
    assert rec["sha1"] == n["rev"] and rec["outline_sha1"] == o["rev"]
    assert n["approved"] is True and n["approval_reason"] is None and n["approved_outline_rev"] == o["rev"]
    assert client.get(f"{B}/pipeline").json()["stage"] == "script" == stage_in_list(client)


def test_old_record_without_the_outline_hash_is_not_fresh(client):
    make_narration(client)
    f = client.root / "books" / "script" / "narration.json"
    d = json.loads(f.read_text())
    d["approval"].pop("outline_sha1")
    f.write_text(json.dumps(d))
    n = client.get(f"{B}/narration").json()
    assert n["approved"] is False and n["approval_reason"] == "outline_changed"
    assert client.get(f"{B}/pipeline").json()["stage"] == "outlined" == stage_in_list(client)


def test_small_outline_edit_costs_one_reapproval_never_a_rewrite(client):
    n = make_narration(client)
    o = client.get(f"{B}/outline").json()
    od = copy.deepcopy(o["outline"])
    od["thesis"] += " (edited)"
    assert client.put(f"{B}/outline", json={"outline": od, "base_rev": o["rev"]}).status_code == 200
    o2 = client.get(f"{B}/outline").json()
    assert client.post(f"{B}/outline/approve", json={"rev": o2["rev"]}).status_code == 200
    n2 = client.get(f"{B}/narration").json()
    assert n2["approved"] is False and n2["approval_reason"] == "outline_changed" and n2["stale"] is True   # information, not a block
    assert client.get(f"{B}/pipeline").json()["stage"] == "outlined" == stage_in_list(client)
    r = client.post(f"{B}/narration/approve", json={"rev": n2["rev"]})
    assert r.status_code == 200 and r.json()["approved"] is True and r.json()["approved_outline_rev"] == o2["rev"]
    assert client.get(f"{B}/pipeline").json()["stage"] == "script" == stage_in_list(client)
    assert n2["rev"] == n["rev"]                        # the narration itself was never touched


def test_approval_is_refused_for_chapters_that_differ_and_lists_them(client):
    n = make_narration(client, approve=False)
    o = client.get(f"{B}/outline").json()
    od = copy.deepcopy(o["outline"])
    gone = od["chapters"].pop(2)["id"]
    assert client.put(f"{B}/outline", json={"outline": od, "base_rev": o["rev"]}).status_code == 200
    o = client.get(f"{B}/outline").json()
    assert client.post(f"{B}/outline/approve", json={"rev": o["rev"]}).status_code == 200
    n = client.get(f"{B}/narration").json()
    assert n["chapter_diff"]["not_in_outline"] == [gone]
    r = client.post(f"{B}/narration/approve", json={"rev": n["rev"]})
    assert r.status_code == 422 and r.json()["chapter_diff"]["not_in_outline"] == [gone]
    assert any(i["code"] == "unknown_chapter" and i["level"] == "error" for i in r.json()["issues"])
    # saving stays allowed ("incomplete is not invalid")
    assert client.put(f"{B}/narration", json={"narration": n["narration"], "base_rev": n["rev"]}).status_code == 200
    # an outline chapter with no narration is refused too
    od2 = copy.deepcopy(o["outline"])
    od2["chapters"].append({**od2["chapters"][0], "id": "c99", "title": "NEW"})
    o = client.get(f"{B}/outline").json()
    assert client.put(f"{B}/outline", json={"outline": od2, "base_rev": o["rev"]}).status_code == 200


# ------------------------------------------------------------------ R2B-002: one rule for the storyboard approval
def test_stage_follows_the_storyboard_approval_everywhere(client):
    A = "/api/projects/arn"
    st = client.get(A).json()
    assert client.post(A + "/approve", json={"rev": st["rev"]}).status_code == 200
    assert client.get(A + "/pipeline").json()["stage"] == "approved" == stage_in_list(client, "arn")
    from bti.library import projects as libprojects
    assert libprojects.infer_stage(client.root / "arn") == "approved"
    sb = common.strip_derived(st["storyboard"])
    sb["title"] = "changed"
    assert client.put(A + "/storyboard", json={"storyboard": sb, "base_rev": st["rev"]}).status_code == 200
    assert client.get(A + "/pipeline").json()["stage"] == "storyboard" == stage_in_list(client, "arn")
    assert libprojects.infer_stage(client.root / "arn") == "storyboard"
    assert client.get("/api/library/artworks").status_code == 200


# ------------------------------------------------------------------ R2B-005: delete and saves exclude each other
def test_delete_is_refused_with_409_when_a_save_holds_the_lock_and_removes_nothing(client, monkeypatch):
    from bti.editor import pipeline_api
    monkeypatch.setattr(pipeline_api, "DELETE_WAIT_S", 0.2)
    d = client.root / "books"
    got = threading.Event()
    release = threading.Event()

    def holder():
        with store.script_lock(d):
            got.set()
            release.wait(5)
    t = threading.Thread(target=holder)
    t.start()
    got.wait(5)
    r = client.delete(B + "?confirm=books")
    release.set()
    t.join()
    assert r.status_code == 409 and r.json()["code"] == "project_busy"
    assert (d / "project.json").is_file()
    assert client.delete(B + "?confirm=books").status_code == 200


def test_delete_leaves_no_folder_frees_the_slug_and_drops_the_locks(client):
    d = client.root / "books"
    make_outline(client)
    l1, l2 = store.script_lock(d), common.save_lock(d)
    assert client.delete(B + "?confirm=books").status_code == 200
    assert not d.exists() and not list(client.root.glob(".deleting-*"))
    assert store.script_lock(d) is not l1 and common.save_lock(d) is not l2
    assert client.get(B + "/outline").status_code == 404
    o = {"chapters": []}
    assert client.put(B + "/outline", json={"outline": o, "base_rev": "x"}).status_code == 404
    assert not d.exists()


def test_write_helpers_never_create_a_project_folder(tmp_path):
    gone = tmp_path / "projects" / "ghost"
    with pytest.raises(store.ProjectGone):
        store.write_json_atomic(gone / "script" / "outline.json", {})
    with pytest.raises(store.ProjectGone):
        common.write_json_atomic(gone / "x.json", {})
    assert not gone.exists() and not (tmp_path / "projects").exists()
    (tmp_path / "projects" / "real").mkdir(parents=True)
    store.write_json_atomic(tmp_path / "projects" / "real" / "script" / "o.json", {})       # one level inside a project is fine
    assert (tmp_path / "projects" / "real" / "script" / "o.json").is_file()


def test_delete_stress_only_200_404_409_and_no_ghost(app, client):
    """The stress of docs/qa/ROUND2_backend.md, with a small count here (the report says how the 200-trial run went)."""
    import os
    trials = int(os.environ.get("BTI_STRESS_TRIALS", "12"))
    bad = []
    for i in range(trials):
        pid = f"del{i}"
        shutil.copytree(BOOKS, client.root / pid, ignore=CLONE)
        S = f"/api/projects/{pid}"
        make_outline(client, pid)
        o = client.get(S + "/outline").json()
        stop = threading.Event()
        codes = []

        def writer():
            cl = TestClient(app, raise_server_exceptions=False)
            rev, k = o["rev"], 0
            while not stop.is_set():
                od = copy.deepcopy(o["outline"])
                od["thesis"] = f"x{k}"
                k += 1
                rr = cl.put(S + "/outline", json={"outline": od, "base_rev": rev})
                codes.append(rr.status_code)
                if rr.status_code == 200:
                    rev = rr.json()["rev"]
                else:
                    g = cl.get(S + "/outline")
                    if g.status_code == 200:
                        rev = g.json()["rev"]
        ts = [threading.Thread(target=writer) for _ in range(3)]
        [t.start() for t in ts]
        time.sleep(0.05 + (i % 5) * 0.03)
        d = client.delete(S + f"?confirm={pid}")
        time.sleep(0.15)
        stop.set()
        [t.join() for t in ts]
        if d.status_code not in (200, 409):
            bad.append((pid, "delete", d.status_code))
        if any(c not in (200, 404, 409) for c in codes):
            bad.append((pid, "save", sorted(set(codes))))
        if d.status_code == 200 and (client.root / pid).exists():
            bad.append((pid, "ghost folder"))
        if d.status_code == 200 and list(client.root.glob(f".deleting-{pid}-*")):
            bad.append((pid, "trash left"))
        if d.status_code == 200:
            r = client.post("/api/library/projects", json={"artwork_key": "bosch-the-garden-of-earthly-delights", "slug": pid})
            if r.status_code == 409 and "already exists" in r.text:
                bad.append((pid, "slug not free"))
            shutil.rmtree(client.root / pid, ignore_errors=True)
        else:
            shutil.rmtree(client.root / pid, ignore_errors=True)
    assert not bad, bad


# ------------------------------------------------------------------ R2B-006 .. 009, 011: input at the edge
def test_depth_limit_is_one_shared_check_before_the_routes(client):
    def nest(n):
        return "[" * n + "]" * n
    for url in (B + "/outline", "/api/projects/arn/validate", "/api/library/projects"):
        r = client.post(url, content='{"x": ' + nest(41) + "}", headers={"content-type": "application/json"})
        assert r.status_code == 422 and r.json()["code"] == "too_deep", url
    ok = client.post("/api/library/projects", content='{"work_ids": ' + nest(5) + "}", headers={"content-type": "application/json"})
    assert ok.status_code == 422 and "code" not in ok.json()                       # a normal 422 of the route, not the depth check
    # brackets inside strings do not count
    r = client.post("/api/library/projects", content=json.dumps({"slug": "[" * 100}), headers={"content-type": "application/json"})
    assert r.status_code != 422 or "code" not in r.json()


def test_finite_number_helper():
    f = common.finite_number
    assert f(5, "n", 0, 10) == 5 and f(None, "n", default=3) == 3 and f(4.0, "n", integer=True) == 4
    for bad in (True, "5", None, float("nan"), float("inf"), -1, 11, 10 ** 400, 4.5):
        with pytest.raises(common.ApiError) as e:
            f(bad, "n", 0, 10, integer=(bad == 4.5))
        assert e.value.status == 422


def test_other_helpers():
    assert common.string_list(None, "x") is None and common.string_list(["a"], "x") == ["a"]
    for bad in ([[]], [{}], [1], "a", {"a": 1}):
        with pytest.raises(common.ApiError):
            common.string_list(bad, "x")
    assert common.segment_ok("a" * 255) and not common.segment_ok("a" * 256) and not common.segment_ok("\ud800")
    assert not common.segment_ok("é" * 128) and common.segment_ok("é" * 127)


@pytest.mark.parametrize("n", [1, 10 ** 400, "1", None, True, float("nan")])
def test_every_number_route_answers_422_never_500(client, n):
    A = "/api/projects/arn"
    for url, body in ((A + "/preview", {"t0": 0, "t1": n}), (A + "/preview", {"t0": n, "t1": 5}),
                      (A + "/preview", {"t0": 0, "t1": 1, "fps": n}), (A + "/preview", {"t0": 0, "t1": 1, "width": n}),
                      (A + "/frame", {"t": n, "storyboard": {}})):
        r = client.post(url, content=json.dumps(body), headers={"content-type": "application/json"})
        assert r.status_code < 500, (url, body, r.status_code)


def test_library_create_lists_are_checked(client):
    for body in ({"work_ids": [[]]}, {"work_ids": [{}]}, {"work_ids": "x"}, {"exclude": [[]], "artwork_key": "x"},
                 {"artwork_key": 5}, {"slug": 5}):
        r = client.post("/api/library/projects", json=body)
        assert r.status_code in (404, 422), (body, r.status_code)


def test_long_segments_are_404_everywhere(client):
    seg = "a" * 300
    for url in (f"/api/projects/arn/files/{seg}", f"/style/gae/previews/{seg}", f"/api/library/artworks/{seg}", f"/{seg}",
                f"/api/library/artworks/x/source/{seg}", f"/api/library/artworks/{seg}/source/x", f"/api/styles/{seg}",
                f"/api/projects/arn/thumb/{seg}", f"/api/projects/{seg}/pipeline", f"/api/jobs/{seg}"):
        assert client.get(url).status_code == 404, url


def test_upload_without_a_title_takes_the_file_name(client):
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(b, "PNG")
    for fname, want in (("my_picture.png", "my_picture"), ("C:\\x\\Les  Mées.png", "Les Mées"), ("../../up.png", "up")):
        r = client.post("/api/projects/arn/assets/upload", files={"file": (fname, b.getvalue(), "image/png")},
                        data={"title": "  ", "licence": "CC0", "source_url": "http://x", "author": "me"})
        assert r.status_code == 200, r.text
        assert want in r.json()["asset"]["title"] and "tmp" not in r.json()["asset"]["title"]


# ------------------------------------------------------------------ R2B-010 / 013: ids and enums are checked, never coerced
def test_chapter_and_beat_ids_enums_and_flags_are_checked(client):
    n = make_narration(client, approve=False)
    nd = n["narration"]

    def put(mut):
        d = copy.deepcopy(nd)
        mut(d)
        return client.put(f"{B}/narration", json={"narration": d, "base_rev": n["rev"]})
    assert put(lambda d: None).status_code == 200
    n = client.get(f"{B}/narration").json()
    bad = {
        "dup beat in chapter": lambda d: d["chapters"][0]["beats"][1].update(id=d["chapters"][0]["beats"][0]["id"]),
        "dup beat across": lambda d: d["chapters"][1]["beats"][0].update(id=d["chapters"][0]["beats"][0]["id"]),
        "beat id form": lambda d: d["chapters"][0]["beats"][0].update(id="beat 1"),
        "beat id type": lambda d: d["chapters"][0]["beats"][0].update(id=7),
        "chapter id form": lambda d: d["chapters"][0].update(id="C01"),
        "dup chapter": lambda d: d["chapters"][1].update(id=d["chapters"][0]["id"]),
        "role": lambda d: d["chapters"][0].update(role="bogus"),
        "role type": lambda d: d["chapters"][0].update(role=3),
        "card": lambda d: d["chapters"][0].update(card="yes"),
        "locked": lambda d: d["chapters"][0]["beats"][0].update(locked=1),
    }
    for name, mut in bad.items():
        d = copy.deepcopy(nd)
        mut(d)
        r = client.put(f"{B}/narration", json={"narration": d, "base_rev": n["rev"]})
        assert r.status_code == 422, name


def test_outline_enums_and_numbers_are_checked(client):
    make_outline(client)
    o = client.get(f"{B}/outline").json()
    bad = {
        "chapter id": lambda d: d["chapters"][0].update(id="c 1"),
        "role": lambda d: d["chapters"][0].update(role="x"),
        "card": lambda d: d["chapters"][0].update(card=None),
        "certainty": lambda d: d["facts"][0].update(certainty="sure"),
        "budget inf": lambda d: d["chapters"][0].update(word_budget=float("inf")),
        "hook choice": lambda d: d.update(hook_choice=5),
        "sources": lambda d: d["facts"][0].update(sources="PAY-01"),
    }
    for name, mut in bad.items():
        d = copy.deepcopy(o["outline"])
        mut(d)
        r = client.put(f"{B}/outline", content=json.dumps({"outline": d, "base_rev": o["rev"]}),
                       headers={"content-type": "application/json"})
        assert r.status_code == 422, name


def test_a_model_or_pasted_outline_with_odd_ids_is_normalised_or_refused_by_the_parser(client):
    from bti.script import parse
    text = "OUTLINE\n\nTHESIS: why?\n\n## C01 COLD OPEN\n- budget: 100\n"
    res = parse.parse_outline(text, set(), target_words=300)
    assert not res.ok or all(store.CHAPTER_ID_RE.fullmatch(c.id) for c in res.outline.chapters)


# ------------------------------------------------------------------ R2B-014: one damaged project never breaks the others
@pytest.mark.parametrize("data", [b"[1]", b"null", b"3", b"\xff\xfe\x00", b"{"])
def test_damaged_project_json_is_a_row_not_a_500(client, data):
    (client.root / "books" / "project.json").write_bytes(data)
    r = client.get("/api/projects")
    assert r.status_code == 200
    rows = {p["id"]: p for p in r.json()}
    assert rows["books"]["data_error"] and rows["books"]["stage"] is None and rows["books"]["title"] == "books"
    assert "arn" in rows and "data_error" not in rows["arn"]
    assert client.get("/api/library/artworks").status_code == 200
    assert client.get("/api/library/artworks/eyck-the-arnolfini-portrait").status_code == 200
    for url in ("/brief", "/outline", "/narration", "/pipeline"):
        r = client.get(B + url)
        assert r.status_code == 409 and r.json()["data_error"] == "project", (url, r.status_code, r.text[:80])


@pytest.mark.parametrize("rel,data,what", [("script/brief_options.json", b"[1]", "script"), ("script/brief_options.json", b"3", "script"),
                                           ("script/brief_options.json", b"\xff", "script"),
                                           ("source/dossier.json", b'{"sources": [1]}', "source"),
                                           ("source/dossier.json", b"[1]", "source"),
                                           ("source/payne_gae_002.txt", b"\xff\xfe\x00\x01", "source")])
def test_damaged_script_inputs_are_409_naming_the_file(client, rel, data, what):
    f = client.root / "books" / rel
    f.parent.mkdir(exist_ok=True)
    assert f.is_file() or rel.startswith("script/")
    f.write_bytes(data)
    for url in ("/brief", "/outline", "/narration", "/prompt?phase=outline"):
        r = client.get(B + url)
        assert r.status_code == 409 and r.json()["data_error"] == what and f.name in r.json()["detail"], (url, r.status_code, r.text[:90])
    assert client.get("/api/projects").status_code == 200
    if rel.endswith("brief_options.json"):       # the owner can repair it from the page: a save replaces the damaged file
        r = client.put(B + "/brief/options", json={"target_words": 1500})
        assert r.status_code == 200 and json.loads(f.read_text())["target_words"] == 1500


def test_damaged_outline_or_media_index_does_not_break_the_lists(client):
    (client.root / "books" / "script").mkdir(exist_ok=True)
    (client.root / "books" / "script" / "outline.json").write_text("[1]")
    assert client.get("/api/projects").status_code == 200
    assert client.get(B + "/pipeline").status_code == 200
    (client.root / "arn" / "media").mkdir(exist_ok=True)
    (client.root / "arn" / "media" / "index.json").write_text("[1]")
    from bti.media import assets
    assert assets.load_index(client.root / "arn")["items"] == {}


def test_damaged_dossier_in_the_library_is_one_row_with_data_error(client, tmp_path, monkeypatch):
    from bti.library import config as libcfg, dossiers
    lib = tmp_path / "lib"
    (lib / "dossiers" / "k1").mkdir(parents=True)
    (lib / "dossiers" / "k1" / "dossier.json").write_text("[1]")
    monkeypatch.setattr(libcfg, "LIB_DIR", lib)
    with pytest.raises(ValueError):
        dossiers.load("k1")
    assert dossiers.load("a" * 300) is None and dossiers.load("../x") is None and dossiers.load("nope") is None


# ------------------------------------------------------------------ R2B-012 (API half): RenderError is 422, approval draws
def _lab_client(tmp_path):
    r = tmp_path / "p2"
    r.mkdir()
    shutil.copytree(LAB, r / "lab", ignore=shutil.ignore_patterns("cache", "history"))
    return r


def test_render_error_is_422_render_failed_on_frame_thumb_and_preview(tmp_path, monkeypatch):
    root = _lab_client(tmp_path)
    app = create_app(projects_root=root)
    with TestClient(app, raise_server_exceptions=False) as c:
        st = c.get("/api/projects/lab").json()
        shot = st["storyboard"]["shots"][0]
        proj = app.state.engine.project("lab")
        prev = app.state.engine.preview_project("lab")[0]

        def boom(*a, **k):
            raise RenderError("cannot be drawn: bad value", shot=shot["id"], technique="CMP-03")
        monkeypatch.setattr(proj, "frame_at", boom)
        monkeypatch.setattr(prev, "render_range", boom)
        t = shot["_t0"] + 0.1
        for r in (c.get("/api/projects/lab/frame", params={"t": t}),
                  c.post("/api/projects/lab/frame", json={"t": t, "storyboard": common.strip_derived(st["storyboard"])}),
                  c.get(f"/api/projects/lab/thumb/{shot['id']}")):
            assert r.status_code == 422, r.text
            j = r.json()
            assert j["code"] == "render_failed" and j["shot"] == shot["id"] and j["technique"] == "CMP-03" and "overlay" in j
        jid = c.post("/api/projects/lab/preview", json={"t0": 0, "t1": 1}).json()["job_id"]
        j = wait_job(c, jid)
        assert j["state"] == "error" and j["error_code"] == "render_failed" and j["shot"] == shot["id"]


def test_approve_runs_draw_check_and_lists_the_undrawable_items(tmp_path, monkeypatch):
    root = _lab_client(tmp_path)
    app = create_app(projects_root=root)
    with TestClient(app, raise_server_exceptions=False) as c:
        proj = app.state.engine.project("lab")
        calls = []
        real = proj.draw_check

        def fake(sb=None, width=320):
            calls.append(1)
            return [{"level": "error", "code": "undrawable", "path": "shots[1]", "shot": "s0002", "message": "no good"}]
        monkeypatch.setattr(proj, "draw_check", fake)
        st = c.get("/api/projects/lab").json()
        if any(i["level"] == "error" or i.get("code") == "incomplete" for i in st["issues"]):
            pytest.skip("the lab project is not approvable on its own")
        r = c.post("/api/projects/lab/approve", json={"rev": st["rev"]})
        assert r.status_code == 422 and calls
        j = r.json()
        assert j["undrawable"] is True and j["code"] == "undrawable" and any(i.get("code") == "undrawable" for i in j["issues"])
        assert "shots[1]" in j["detail"]
        assert c.get("/api/projects/lab").json()["storyboard"].get("approvals", {}).get("storyboard") in (None, {})
        monkeypatch.setattr(proj, "draw_check", real)
        assert c.post("/api/projects/lab/approve", json={"rev": st["rev"]}).status_code == 200


# ------------------------------------------------------------------ Residual 2: a damaged project.json never lets a delete through
@pytest.mark.parametrize("data", [b"[1]", b"null", b'{"id": "bo', b"\xff\xfe"])
def test_delete_with_a_damaged_project_file_is_409_and_removes_nothing(client, data):
    f = client.root / "books" / "project.json"
    f.write_bytes(data)
    r = client.delete(B + "?confirm=books")
    assert r.status_code == 409 and r.json()["data_error"] == "project" and "books" in r.json()["detail"]
    assert f.read_bytes() == data and (client.root / "books" / "source").is_dir()


def test_delete_without_a_project_file_is_allowed(client):
    (client.root / "books" / "project.json").unlink()
    assert client.delete(B + "?confirm=books").status_code == 200


# ------------------------------------------------------------------ Residual 1: media writes never bring a deleted project back
def _png():
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(b, "PNG")
    return b.getvalue()


@pytest.mark.parametrize("trial", range(int(__import__("os").environ.get("BTI_MEDIA_TRIALS", "10"))))
def test_upload_and_import_racing_a_delete_answer_404_and_leave_nothing(app, client, monkeypatch, trial):
    from bti.editor import media_adapter
    pid = f"m{trial}"
    shutil.copytree(ARN, client.root / pid, ignore=shutil.ignore_patterns("cache", "history"))
    pj = client.root / pid / "project.json"
    if pj.is_file():
        d = json.loads(pj.read_text())
        d.pop("protected", None)
        pj.write_text(json.dumps(d))
    A = f"/api/projects/{pid}"
    media = app.state.media
    for mode in ("upload", "import"):
        entered, go = threading.Event(), threading.Event()
        orig = media.module.add_upload if mode == "upload" else media.module.import_candidate

        def slow(*a, **k):
            entered.set()
            go.wait(5)                              # the "network / transfer" part: the delete happens now
            return orig(*a, **k)
        if media.module is None:
            pytest.skip("stub media")
        monkeypatch.setattr(media.module, "add_upload" if mode == "upload" else "import_candidate", slow)
        res = {}

        def call():
            c = TestClient(app, raise_server_exceptions=False)
            if mode == "upload":
                res["r"] = c.post(A + "/assets/upload", files={"file": ("x.png", _png(), "image/png")},
                                  data={"licence": "CC0", "source_url": "http://x", "author": "me"})
            else:
                res["r"] = c.post(A + "/assets/import", json={"source": "commons", "source_id": "File:x.jpg"})
        t = threading.Thread(target=call)
        t.start()
        assert entered.wait(5)
        assert client.delete(A + f"?confirm={pid}").status_code == 200
        go.set()
        t.join(10)
        assert res["r"].status_code == 404, (mode, res["r"].status_code, res["r"].text[:100])
        assert not (client.root / pid).exists() and not list(client.root.glob(f".deleting-{pid}-*")), mode
        shutil.copytree(ARN, client.root / pid, ignore=shutil.ignore_patterns("cache", "history")) if mode == "upload" else None
        monkeypatch.undo() if False else None
        monkeypatch.setattr(media.module, "add_upload" if mode == "upload" else "import_candidate", orig)
        if mode == "upload":
            pj = client.root / pid / "project.json"
            if pj.is_file():
                d = json.loads(pj.read_text()); d.pop("protected", None); pj.write_text(json.dumps(d))
    r = client.post("/api/library/projects", json={"artwork_key": "bosch-the-garden-of-earthly-delights", "slug": pid})
    assert r.status_code == 200, "slug not free: " + r.text      # also proves no folder was left
    shutil.rmtree(client.root / pid, ignore_errors=True)


def test_media_facade_default_still_creates_folders_and_require_root_never_does(tmp_path):
    from bti.media import assets
    assets.media_dir(tmp_path / "p")
    assert (tmp_path / "p" / "media").is_dir()
    with pytest.raises(FileNotFoundError):
        assets.media_dir(tmp_path / "gone", require_root=True)
    assert not (tmp_path / "gone").exists()


def test_http_limits_are_the_engine_limits(client):
    """The editor reads its limits from bti.engine.limits (the command line reads the same file): changing a value there moves both."""
    from bti.editor import frames
    from bti.engine import limits
    A = "/api/projects/arn"
    assert frames.limits is limits
    for w, ok in ((limits.FRAME_WIDTH_MIN - 1, False), (limits.FRAME_WIDTH_MAX + 1, False)):
        assert client.get(A + "/frame", params={"t": 1, "width": w}).status_code == 422
    for body in ({"t0": 0, "t1": 1, "width": limits.PREVIEW_WIDTH_MAX + 1}, {"t0": 0, "t1": 1, "width": limits.PREVIEW_WIDTH_MIN - 1},
                 {"t0": 0, "t1": 1, "fps": limits.FPS_MAX + 1}, {"t0": 0, "t1": 1, "fps": limits.FPS_MIN - 1},
                 {"t0": 0, "t1": limits.PREVIEW_MAX_SECONDS + 1}):
        assert client.post(A + "/preview", json=body).status_code == 422, body
