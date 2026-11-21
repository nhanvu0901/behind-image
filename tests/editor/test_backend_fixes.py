"""Regression tests for the backend QA findings (docs/qa/BUGS_backend.md), in the everyday suite.
Real engine on a copy of technique_lab, mock model on a copy of arnolfini-from-books. No network."""
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

from bti.editor.app import create_app  # noqa: E402
from bti.editor.engine_adapter import ENGINE_LOCK  # noqa: E402
from bti.script import env as env_mod, models as models_mod  # noqa: E402

LAB, BOOKS = REPO / "projects" / "technique_lab", REPO / "projects" / "arnolfini-from-books"
pytestmark = pytest.mark.skipif(not LAB.is_dir() or not BOOKS.is_dir(), reason="reference projects are missing")
P = "/api/projects/lab"


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


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
    shutil.copytree(LAB, r / "lab", ignore=shutil.ignore_patterns("cache", "history"))
    shutil.copytree(BOOKS, r / "books", ignore=shutil.ignore_patterns("script", "cache", "history"))
    return r


@pytest.fixture()
def client(root):
    with TestClient(create_app(projects_root=root), raise_server_exceptions=False) as c:
        c.root = root
        yield c


@pytest.fixture()
def st(client):
    return client.get(P).json()


def put(client, sb, rev):
    return client.put(f"{P}/storyboard", json={"storyboard": sb, "base_rev": rev})


# ------------------------------------------------------------------ B-001 / B-003: nothing that cannot be re-opened is written
@pytest.mark.parametrize("field,value", [("style", "nope"), ("style", "../x"), ("style", 5), ("timing", "../../x.json"),
                                         ("timing", "nofile.json"), ("timing", "/etc/hosts"), ("audio", "../../etc/hosts")])
def test_save_refuses_references_that_cannot_be_loaded(client, st, root, field, value):
    before = (root / "lab" / "storyboard.json").read_text()
    sb = strip(st["storyboard"])
    sb[field] = value
    r = put(client, sb, st["rev"])
    assert r.status_code == 422 and any(i["path"] == field for i in r.json()["issues"])
    assert (root / "lab" / "storyboard.json").read_text() == before
    assert client.get(P).status_code == 200


@pytest.mark.parametrize("path", ["/etc/hosts", "media/../../books/project.json", "../x.png", "storyboard.json", "media/nope.jpg"])
def test_asset_file_must_be_an_image_inside_the_project(client, st, path):
    sb = strip(st["storyboard"])
    key = next(iter(sb["assets"]))
    sb["assets"][key]["file"] = path
    issues = client.post(f"{P}/validate", json={"storyboard": sb}).json()["issues"]
    assert any(i["level"] == "error" and i["path"] == f"assets.{key}.file" for i in issues)
    assert put(client, sb, st["rev"]).status_code == 422


def test_overlay_slot_assets_are_checked(client, st):
    sb = strip(st["storyboard"])
    o = next(o for s in sb["shots"] for o in s.get("overlays", []) if o["technique"] == "HI-03")
    o["slots"]["mask"] = {"asset": "NOPE"}
    issues = client.post(f"{P}/validate", json={"storyboard": sb}).json()["issues"]
    assert any(i["level"] == "error" and "not defined" in i["message"] for i in issues)


# ------------------------------------------------------------------ B-002: wrong types give issues, not 500
@pytest.mark.parametrize("mut", [lambda sb: sb["shots"][2].update(start={"t": "abc"}), lambda sb: sb.update(canvas="x"),
                                 lambda sb: sb["shots"][2].update(id=["a"]), lambda sb: sb["shots"][2].update(overlays="x"),
                                 lambda sb: sb["shots"][2].update(slots=[1]), lambda sb: sb.update(shots="x"),
                                 lambda sb: sb["shots"][2].update(technique=["CAM-01"])])
def test_validate_never_500(client, st, mut):
    sb = strip(st["storyboard"])
    mut(sb)
    r = client.post(f"{P}/validate", json={"storyboard": sb})
    assert r.status_code == 200 and any(i["level"] == "error" for i in r.json()["issues"])
    assert put(client, sb, st["rev"]).status_code == 422


# ------------------------------------------------------------------ rule 2: incomplete is not invalid
def _lab_with_bare_hi03(st):
    sb = strip(st["storyboard"])
    shot = next(s for s in sb["shots"] if s["id"] == "s0037")
    t0 = next(s for s in st["storyboard"]["shots"] if s["id"] == "s0037")["_t0"]
    shot["overlays"] = [{"id": "ox", "technique": "HI-03", "start": {"t": round(t0 + 0.3, 3)}, "dur": 2.0, "params": {},
                         "locked": False, "source": "human", "note": ""}]
    return sb, t0


def test_incomplete_overlay_warns_saves_renders_and_blocks_approval(client, st):
    sb, t0 = _lab_with_bare_hi03(st)
    issues = client.post(f"{P}/validate", json={"storyboard": sb}).json()["issues"]
    inc = [i for i in issues if i.get("code") == "incomplete"]
    assert inc and inc[0]["level"] == "warn" and "mask" in inc[0]["message"]
    assert not any(i["level"] == "error" for i in issues)
    r = client.post(f"{P}/frame", json={"t": t0 + 1, "width": 320, "storyboard": sb})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    saved = put(client, sb, st["rev"])
    assert saved.status_code == 200
    a = client.post(f"{P}/approve", json={"rev": saved.json()["rev"]})
    assert a.status_code == 422 and a.json()["incomplete"] is True and "mask" in a.json()["detail"]


def test_incomplete_shot_draws_a_placeholder(client, st):
    sb = strip(st["storyboard"])
    shot = next(s for s in sb["shots"] if s["technique"] == "LAY-04")
    shot["slots"]["inset"] = {}
    t0 = next(s for s in st["storyboard"]["shots"] if s["id"] == shot["id"])["_t0"]
    issues = client.post(f"{P}/validate", json={"storyboard": sb}).json()["issues"]
    assert any(i.get("code") == "incomplete" and "inset" in i["message"] for i in issues)
    assert client.post(f"{P}/frame", json={"t": t0 + 0.5, "width": 320, "storyboard": sb}).status_code == 200


def test_wrong_kind_in_a_slot_is_an_error(client, st):
    sb = strip(st["storyboard"])
    o = next(o for s in sb["shots"] for o in s.get("overlays", []) if o["technique"] == "HI-03")
    img = next(k for k, a in sb["assets"].items() if a["kind"] == "image")
    o["slots"]["mask"] = {"asset": img}
    issues = client.post(f"{P}/validate", json={"storyboard": sb}).json()["issues"]
    assert any(i["level"] == "error" and "mask" in i["message"] for i in issues)


def test_defaults_never_put_the_painting_into_video_or_mask_slots(client, st):
    sb = strip(st["storyboard"])
    shot = next(s for s in sb["shots"] if s["id"] == "s0037")
    ctx = {"shot_id": shot["id"], "slots": shot["slots"], "assets": {k: {"width": v.get("width"), "height": v.get("height")}
                                                                      for k, v in sb["assets"].items()}}
    for tech, empty in (("HI-03", {"mask"}), ("LAY-04", {"inset"}), ("AN-02", {"mask"})):
        r = client.post(f"{P}/defaults", json={"technique": tech, "context": ctx})
        assert r.status_code == 200
        slots = r.json()["slots"]
        assert not (set(slots) & empty), (tech, slots)
        assert "image" in slots


# ------------------------------------------------------------------ B-020 / B-021: corrupt file, history
@pytest.mark.parametrize("content", ["[1,2]", "null", "{trunc", ""])
def test_corrupt_storyboard_is_a_json_409_and_restorable(client, st, root, content):
    sb = strip(st["storyboard"])
    sb["title"] = "second version"
    assert put(client, sb, st["rev"]).status_code == 200                 # makes history/ hold a good copy
    f = root / "lab" / "storyboard.json"
    f.write_text(content)
    for url in (P, f"{P}/assets", f"{P}/audio"):
        r = client.get(url)
        assert r.status_code == 409 and r.json()["corrupt"] is True and r.json()["restore_from"], (url, r.text)
    assert client.put(f"{P}/storyboard", json={"storyboard": sb, "base_rev": "x"}).status_code == 409
    r = client.post(f"{P}/storyboard/restore", json={})
    assert r.status_code == 200 and r.json()["quarantined"]
    assert client.get(P).status_code == 200
    assert client.post(f"{P}/storyboard/restore", json={}).status_code == 409        # healthy now: nothing to restore


def test_history_keeps_the_newest_fifty(client, st, root):
    sb, rev = strip(st["storyboard"]), st["rev"]
    for i in range(55):
        sb["title"] = f"v{i}"
        r = put(client, sb, rev)
        assert r.status_code == 200
        rev = r.json()["rev"]
    assert len(list((root / "lab" / "history").glob("*.json"))) == 50


# ------------------------------------------------------------------ B-022 / B-023
def test_still_cache_follows_timing_and_media(client, st, root):
    t = st["storyboard"]["shots"][3]["_t0"] + 0.3
    a = client.get(f"{P}/frame", params={"t": t, "width": 320})
    f = root / "lab" / "timing.json"
    d = json.loads(f.read_text())
    for w in d["words"]:
        w["s"] += 6.0
        w["e"] += 6.0
    f.write_text(json.dumps(d))
    st2 = client.get(P).json()
    assert st2["render_key"] != st["render_key"] and st2["rev"] == st["rev"]
    b = client.get(f"{P}/frame", params={"t": t, "width": 320})
    assert b.headers["etag"] != a.headers["etag"]
    assert client.get(f"{P}/frame", params={"t": t, "width": 320}, headers={"If-None-Match": b.headers["etag"]}).status_code == 304


@pytest.mark.parametrize("how", ["missing", "corrupt"])
def test_bad_timing_file_is_a_json_409_for_every_reader(client, root, how):
    f = root / "lab" / "timing.json"
    f.unlink() if how == "missing" else f.write_text("{bad")
    r = client.get(P)
    assert r.status_code == 409 and r.json()["data_error"] == "timing" and "timing.json" in r.json()["detail"]
    shot = client.get(f"/api/projects").status_code
    assert shot == 200


def test_validate_reports_a_missing_timing_as_an_issue(client, st, root):
    sb = strip(st["storyboard"])
    (root / "lab" / "timing.json").unlink()
    r = client.post(f"{P}/validate", json={"storyboard": sb})
    assert r.status_code == 200 and any(i["path"] == "timing" for i in r.json()["issues"])


# ------------------------------------------------------------------ B-004 / B-005 / B-024 / B-026
def test_broken_drafts_are_422_with_issues(client, st):
    sb = strip(st["storyboard"])
    t = st["storyboard"]["shots"][3]["_t0"] + 0.3
    bad = copy.deepcopy(sb)
    bad["shots"][3]["slots"]["image"]["asset"] = "ZZZ"
    r = client.post(f"{P}/frame", json={"t": t, "width": 320, "storyboard": bad})
    assert r.status_code == 422 and r.json()["issues"]
    r = client.post(f"{P}/preview", json={"t0": t, "t1": t + 1, "storyboard": bad})
    assert r.status_code == 422 and r.json()["issues"]
    bad = copy.deepcopy(sb)
    bad["shots"] = []
    assert client.post(f"{P}/frame", json={"t": 1, "width": 320, "storyboard": bad}).status_code == 422


def test_text_with_line_breaks_draws_on_one_line(client, st):
    sb = strip(st["storyboard"])
    si = next(i for i, s in enumerate(sb["shots"]) if any(o["technique"] == "X-ANN-01" for o in s.get("overlays", [])))
    o = next(o for o in sb["shots"][si]["overlays"] if o["technique"] == "X-ANN-01")
    o["params"]["text"] = "a\nb\n\nc"
    ro = next(o for o in st["storyboard"]["shots"][si]["overlays"] if o["technique"] == "X-ANN-01")
    r = client.post(f"{P}/frame", json={"t": ro["_t0"] + 0.5, "width": 320, "storyboard": sb})
    assert r.status_code == 200


@pytest.mark.parametrize("w,h", [(-5, "x"), ("x", "y"), (0, 0)])
def test_defaults_with_bad_asset_sizes(client, w, h):
    r = client.post(f"{P}/defaults", json={"technique": "CAM-05", "context": {
        "slots": {"image": {"asset": "annot_A"}}, "assets": {"annot_A": {"width": w, "height": h}}}})
    assert r.status_code == 200


@pytest.mark.parametrize("body", [{"fps": 0}, {"fps": 31}, {"fps": "x"}, {"fps": True}, {"width": 0}, {"width": 100},
                                  {"t1": 100.0}, {"fps": 30, "t1": 50.0}])
def test_preview_parameters_are_checked(client, body):
    full = {"t0": 5.0, "t1": 6.0, **body}
    assert client.post(f"{P}/preview", json=full).status_code == 422


def test_label_defaults_carry_a_position(client):
    for tech in ("STATIC-08", "X-ANN-03"):
        p = client.post(f"{P}/defaults", json={"technique": tech, "context": {}}).json()["params"]
        assert p.get("at") is not None or p.get("screen") is not None


# ------------------------------------------------------------------ B-025: a preview never holds the engine lock
def test_preview_does_not_need_the_engine_lock(client, st):
    t0 = st["storyboard"]["shots"][3]["_t0"]
    r = client.post(f"{P}/preview", json={"t0": t0, "t1": t0 + 1.0, "width": 320, "fps": 5})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    with ENGINE_LOCK:                       # everything that needs the engine for stills and validation is stuck now ...
        end = time.time() + 60
        while time.time() < end:
            j = client.get(f"/api/jobs/{jid}").json()
            if j["state"] in ("done", "error"):
                break
            time.sleep(0.05)
    assert j["state"] == "done", j          # ... and the preview still finished


def test_a_still_comes_back_while_a_preview_renders(client, st):
    t0 = st["storyboard"]["shots"][3]["_t0"]
    jid = client.post(f"{P}/preview", json={"t0": t0, "t1": t0 + 20, "width": 640, "fps": 30}).json()["job_id"]
    time.sleep(0.5)
    t = time.time()
    assert client.get(f"{P}/frame", params={"t": t0 + 1, "width": 320}).status_code == 200
    assert client.get(P).status_code == 200
    waited = time.time() - t
    j = client.get(f"/api/jobs/{jid}").json()
    assert waited < 8 and j["state"] in ("queued", "running", "done"), (waited, j)


def test_preview_length_is_limited(client):
    assert client.post(f"{P}/preview", json={"t0": 0, "t1": 61}).status_code == 422
    assert client.post(f"{P}/preview", json={"t0": 0, "t1": 31}).status_code == 422
    assert client.post(f"{P}/preview", json={"t0": 0, "t1": 30, "fps": 30, "width": 640}).status_code in (200, 422)


# ------------------------------------------------------------------ B-018 / B-019
def test_malformed_proposal_does_not_break_the_list(client, root):
    d = root / "lab" / "proposals"
    d.mkdir()
    (d / "bad4.json").write_text(json.dumps({"storyboard": {"shots": "x", "assets": [1], "end": 5}}))
    assert client.get(f"{P}/proposals").status_code == 200
    assert client.get(f"{P}/proposals/bad4").status_code == 422
    assert client.post(f"{P}/proposals/bad4/apply", json={"accept": "all"}).status_code == 422


@pytest.mark.parametrize("data", [b"not an image", b"", b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000])
def test_upload_must_be_a_readable_image(client, root, data):
    r = client.post(f"{P}/assets/upload", files={"file": ("a.png", data, "image/png")},
                    data={"title": "t", "licence": "CC0", "source_url": "http://x", "author": "me"})
    assert r.status_code == 422
    assert not list((root / "lab" / "media").glob("upload_*")) and not list((root / "lab" / "media").glob("t_*"))


# ------------------------------------------------------------------ errors are answers
def test_a_surrogate_anywhere_in_a_text_is_a_422(client, st):
    sb = strip(st["storyboard"])
    sb["title"] = "bad \ud800 text"
    body = json.dumps({"storyboard": sb, "base_rev": st["rev"]}, ensure_ascii=True).encode()
    r = client.put(f"{P}/storyboard", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_nan_is_not_storable(client, st):
    sb = strip(st["storyboard"])
    shot = next(s for s in sb["shots"] if s["technique"] == "CAM-01")
    key = next(iter(shot["params"]["camera"]))
    shot["params"]["camera"][0]["zoom"] = float("nan")
    r = client.put(f"{P}/storyboard", content=json.dumps({"storyboard": sb, "base_rev": st["rev"]}).encode(),
                   headers={"content-type": "application/json"})
    assert r.status_code == 422


# ------------------------------------------------------------------ script stage
B = "/api/projects/books"


def wait_job(client, jid, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if j.get("state") in ("done", "error", "cancelled"):
            return j
        time.sleep(0.05)
    raise AssertionError("job timeout")


def make_outline(client):
    r = client.post(f"{B}/outline/generate", json={"model": "mock"})
    assert r.status_code == 200, r.text
    assert wait_job(client, r.json()["job_id"])["state"] == "done"


def make_narration(client):
    make_outline(client)
    o = client.get(f"{B}/outline").json()
    assert client.post(f"{B}/outline/approve", json={"rev": o["rev"]}).status_code == 200
    r = client.post(f"{B}/narration/generate", json={"model": "mock", "force": True})
    assert wait_job(client, r.json()["job_id"])["state"] == "done"
    return client.get(f"{B}/narration").json()


@pytest.mark.parametrize("path", ["outline", "narration"])
def test_every_job_endpoint_refuses_a_model_that_is_not_a_model_id(client, path):
    """A model that is named must be a non-empty text. A request that leaves it out is no longer refused: the project's agent decides
    (tests/editor/test_agent_routes.py); what a request that names nothing runs is `bti.agents.model_for_project`, never a silent default."""
    for bad in ("", "  ", 5, ["mock"]):
        r = client.post(f"{B}/{path}/generate", json={"model": bad})
        assert r.status_code == 400 and "model" in r.json()["detail"], bad
    assert client.get(f"{B}/script/jobs").json() == []


def test_put_without_a_document_never_wipes(client):
    n = make_narration(client)
    for path, key, rev in (("narration", "narration", n["rev"]), ("outline", "outline", client.get(f"{B}/outline").json()["rev"])):
        for bad in ({}, {"chapters": "x"}, {"chapters": [1]}, {"chapters": [{"title": "no id"}]}, "x", []):
            body = {"base_rev": rev} if bad == {} and False else {key: bad, "base_rev": rev}
            assert client.put(f"{B}/{path}", json=body).status_code == 422, (path, bad)
        assert client.put(f"{B}/{path}", json={"base_rev": rev}).status_code == 422
    assert client.get(f"{B}/narration").json()["narration"]["chapters"]
    assert client.get(f"{B}/outline").json()["outline"]["chapters"]


def test_only_one_job_starts_at_once(client):
    codes = []
    barrier = threading.Barrier(6)

    def go():
        c = TestClient(client.app, raise_server_exceptions=False)
        barrier.wait()
        codes.append(c.post(f"{B}/outline/generate", json={"model": "mock"}).status_code)
    ths = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert codes.count(200) == 1, sorted(codes)


@pytest.mark.parametrize("op", [1, None, "x", [], {"op": "insert"}, {"op": "insert", "chapter": "c01", "text": ["a"]},
                                {"op": "insert", "chapter": "c01", "facts": "f01"}, {"op": "split", "beat": "b0001", "at_word": "3"},
                                {"op": "split", "beat": 1, "at_word": 3}])
def test_ops_are_type_checked(client, op):
    n = make_narration(client)
    r = client.post(f"{B}/narration/ops", json={"ops": [op], "base_rev": n["rev"]})
    assert r.status_code == 422
    assert client.post(f"{B}/narration/ops", json={"ops": "x", "base_rev": n["rev"]}).status_code == 422


@pytest.mark.parametrize("body", [{"target_words": 5}, {"target_words": 99999999}, {"target_words": "x"}, {"wps": 0}, {"wps": -1},
                                  {"include_low": 5}, {"include_low": "abc"}, {"notes": 5}, {"target_words": True}])
def test_brief_options_are_validated(client, body):
    before = client.get(f"{B}/brief").json()["options"]
    assert client.put(f"{B}/brief/options", json=body).status_code == 422
    assert client.get(f"{B}/brief").json()["options"] == before
    assert client.put(f"{B}/brief/options", json={"target_words": 3000, "wps": 2.5}).json()["target_words"] == 3000


def test_failed_job_leaves_no_running_chapter(client):
    make_narration(client)
    r = client.post(f"{B}/narration/generate", json={"model": "mock", "force": True, "notes": "[mock:ratelimit]"})
    j = wait_job(client, r.json()["job_id"])
    assert j["state"] == "error" and not [c for c in j["chapters"] if c["state"] in ("running", "pending", "retrying")]


def test_import_refuses_to_replace_locked_beats(client):
    n = make_narration(client)
    nn = n["narration"]
    nn["chapters"][0]["beats"][0]["locked"] = True
    lock_id = nn["chapters"][0]["beats"][0]["id"]
    assert client.put(f"{B}/narration", json={"narration": nn, "base_rev": n["rev"]}).status_code == 200
    text = "FINAL SCRIPT\n\n" + "\n\n".join(f"## {c['id']} {c['title']}\n" + "\n\n".join("Replaced text here." for _ in c["beats"])
                                          for c in nn["chapters"])
    r = client.post(f"{B}/narration/import", json={"text": text})
    assert r.status_code == 409 and any(lock_id in x for x in r.json()["locked"]) and r.json()["kept"] is True
    now = client.get(f"{B}/narration").json()
    assert any(b["id"] == lock_id and b["locked"] for c in now["narration"]["chapters"] for b in c["beats"])
    assert client.post(f"{B}/narration/import", json={"text": text, "force": True}).status_code == 200


def test_surrogate_paste_and_bad_utf8_paste(client, root):
    make_narration(client)
    r = client.post(f"{B}/narration/import", content=b'{"text":"## c01 COLD OPEN\\n\\ud800 broken"}',
                    headers={"content-type": "application/json"})
    assert r.status_code == 422
    (root / "books" / "script" / "last_paste.txt").write_bytes(b"\xff\xfe\x00bad")
    assert client.get(f"{B}/narration").status_code == 200


def test_outline_edit_makes_the_narration_approval_stale(client):
    n = make_narration(client)
    text = "FINAL SCRIPT\n\n" + "\n\n".join(f"## {c['id']} {c['title']}\n" + " ".join(["Sentence of words here."] * 60)
                                          for c in n["narration"]["chapters"])
    assert client.post(f"{B}/narration/import", json={"text": text}).status_code == 200
    n = client.get(f"{B}/narration").json()
    assert client.post(f"{B}/narration/approve", json={"rev": n["rev"]}).status_code == 200
    assert client.get(f"{B}/narration").json()["approved"] is True
    assert {s["id"]: s["state"] for s in client.get(f"{B}/pipeline").json()["steps"]}["script"] == "done"
    o = client.get(f"{B}/outline").json()
    ol = o["outline"]
    ol["thesis"] += " edited"
    assert client.put(f"{B}/outline", json={"outline": ol, "base_rev": o["rev"]}).status_code == 200
    n = client.get(f"{B}/narration").json()
    assert n["approved"] is False and n["stale"] is True
    assert {s["id"]: s["state"] for s in client.get(f"{B}/pipeline").json()["steps"]}["script"] != "done"


def test_delete_is_refused_while_a_job_runs(client, root):
    r = client.post(f"{B}/outline/generate", json={"model": "mock", "notes": "[mock:slow]"})
    assert r.status_code == 200
    time.sleep(0.3)
    d = client.delete(B, params={"confirm": "books"})
    assert d.status_code == 409 and d.json()["job_id"] == r.json()["job_id"]
    assert (root / "books" / "project.json").is_file()
    client.post(f"/api/jobs/{r.json()['job_id']}/cancel")
    wait_job(client, r.json()["job_id"], 30)
    assert client.delete(B, params={"confirm": "books"}).status_code == 200
    assert not (root / "books").exists()


def test_jobs_survive_a_restart(root):
    with TestClient(create_app(projects_root=root)) as c1:
        jid = c1.post(f"{B}/outline/generate", json={"model": "mock"}).json()["job_id"]
        wait_job(c1, jid)
        slow = c1.post(f"{B}/narration/generate", json={"model": "mock"})           # refused (no approved outline): no job
        assert slow.status_code == 409
    with TestClient(create_app(projects_root=root)) as c2:
        j = c2.get(f"/api/jobs/{jid}").json()
        assert j["state"] == "done" and j["id"] == jid
        assert c2.get("/api/jobs/0123456789abcdef").status_code == 404
        assert c2.get("/api/jobs/..%2f..%2fx").status_code in (404, 422)


def test_a_job_in_flight_is_reported_failed_after_a_restart(root):
    from bti.script.runner import write_record, job_file
    rec = {"id": "aaaaaaaaaaaaaaaa", "kind": "outline", "pid": "books", "model": "mock", "state": "running", "progress": 0.0,
           "chapters": [{"id": "outline", "state": "running"}], "message": "", "error": None, "error_kind": None,
           "alternatives": [], "result": {}, "created": time.time(), "finished": None}
    write_record(job_file(root, "books", rec["id"]), rec)
    with TestClient(create_app(projects_root=root)) as c:
        j = c.get(f"/api/jobs/{rec['id']}").json()
        assert j["state"] == "error" and j["error_kind"] == "interrupted" and "restarted" in j["error"]
        assert j["chapters"][0]["state"] == "failed"


# ------------------------------------------------------------------ a job finishes against the CURRENT document
@pytest.fixture()
def slow_mock(monkeypatch):
    from bti.script.providers import mock as mock_mod
    monkeypatch.setattr(mock_mod, "DELAY", 0.4)


def _poll(client, jid, until, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if until(j):
            return j
        time.sleep(0.05)
    raise AssertionError("timeout")


def _save_retrying(client, mutate):
    """PUT /narration with `mutate(doc)`, re-reading the revision when the job saved in between (409)."""
    for _ in range(20):
        n = client.get(f"{B}/narration").json()
        doc = n["narration"]
        mutate(doc)
        r = client.put(f"{B}/narration", json={"narration": doc, "base_rev": n["rev"]})
        if r.status_code == 200:
            return r.json()
        assert r.status_code == 409, r.text
    raise AssertionError("could not save")


def test_a_save_to_another_chapter_survives_the_job(client, slow_mock):
    n = make_narration(client)
    ids = [c["id"] for c in n["narration"]["chapters"]]
    assert len(ids) >= 3
    jid = client.post(f"{B}/narration/generate", json={"model": "mock", "force": True, "chapters": ids[:2]}).json()["job_id"]
    _poll(client, jid, lambda j: bool(j["chapters"]) and j["chapters"][0]["state"] == "done")           # chapter 1 is written, chapter 2 is being written

    def edit(doc):
        doc["chapters"][2]["beats"][0]["text"] = "Owner edit made while the model was working."
    _save_retrying(client, edit)
    j = _poll(client, jid, lambda j: j["state"] in ("done", "error", "cancelled"))
    assert j["state"] == "done" and j["result"]["written"] == ids[:2] and j["result"]["skipped"] == []
    now = client.get(f"{B}/narration").json()
    assert now["narration"]["chapters"][2]["beats"][0]["text"] == "Owner edit made while the model was working."
    assert j["result"]["rev"] == now["rev"]                                      # the page can follow the new revision
    assert [c["id"] for c in now["narration"]["chapters"]] == ids                # order kept


def test_a_beat_locked_during_the_job_is_not_overwritten(client, slow_mock):
    n = make_narration(client)
    ids = [c["id"] for c in n["narration"]["chapters"]]
    before = {b["id"]: b["text"] for b in n["narration"]["chapters"][1]["beats"]}
    jid = client.post(f"{B}/narration/generate", json={"model": "mock", "force": True, "chapters": ids[:2]}).json()["job_id"]
    _poll(client, jid, lambda j: bool(j["chapters"]) and j["chapters"][0]["state"] == "done")
    locked = n["narration"]["chapters"][1]["beats"][0]["id"]

    def lock(doc):
        doc["chapters"][1]["beats"][0]["locked"] = True
    _save_retrying(client, lock)
    j = _poll(client, jid, lambda j: j["state"] in ("done", "error", "cancelled"))
    assert j["state"] == "done"
    assert j["result"]["written"] == [ids[0]] and j["result"]["skipped"] == [
        {"chapter": ids[1], "beats": [locked], "reason": "locked while the job ran"}]
    ch = client.get(f"{B}/narration").json()["narration"]["chapters"][1]
    assert {b["id"]: b["text"] for b in ch["beats"]} == before and ch["beats"][0]["locked"] is True


def test_cancel_keeps_the_owners_save_and_the_finished_chapters(client, slow_mock):
    n = make_narration(client)
    ids = [c["id"] for c in n["narration"]["chapters"]]
    old_texts = {c["id"]: [b["text"] for b in c["beats"]] for c in n["narration"]["chapters"]}
    jid = client.post(f"{B}/narration/generate", json={"model": "mock", "force": True, "chapters": ids[:3]}).json()["job_id"]
    _poll(client, jid, lambda j: bool(j["chapters"]) and j["chapters"][0]["state"] == "done")

    def edit(doc):
        doc["chapters"][-1]["beats"][0]["text"] = "Edited after the job began."
    _save_retrying(client, edit)
    client.post(f"/api/jobs/{jid}/cancel")
    j = _poll(client, jid, lambda j: j["state"] in ("done", "error", "cancelled"))
    assert j["state"] == "cancelled"
    now = client.get(f"{B}/narration").json()["narration"]["chapters"]
    assert now[-1]["beats"][0]["text"] == "Edited after the job began."
    unfinished = [c for c in now if c["id"] in ids[1:3]]
    assert all([b["text"] for b in c["beats"]] == old_texts[c["id"]] for c in unfinished if c["id"] != ids[-1])


def test_a_new_beat_id_never_collides_with_one_made_during_the_job(client, slow_mock):
    n = make_narration(client)
    ids = [c["id"] for c in n["narration"]["chapters"]]
    jid = client.post(f"{B}/narration/generate", json={"model": "mock", "force": True, "chapters": ids[:2]}).json()["job_id"]
    _poll(client, jid, lambda j: bool(j["chapters"]) and j["chapters"][0]["state"] == "done")
    cur = client.get(f"{B}/narration").json()
    r = client.post(f"{B}/narration/ops", json={"ops": [{"op": "insert", "chapter": ids[-1], "text": "new"}], "base_rev": cur["rev"]})
    if r.status_code == 409:
        cur = client.get(f"{B}/narration").json()
        r = client.post(f"{B}/narration/ops", json={"ops": [{"op": "insert", "chapter": ids[-1], "text": "new"}], "base_rev": cur["rev"]})
    assert r.status_code == 200
    _poll(client, jid, lambda j: j["state"] in ("done", "error", "cancelled"))
    all_ids = [b["id"] for c in client.get(f"{B}/narration").json()["narration"]["chapters"] for b in c["beats"]]
    assert len(all_ids) == len(set(all_ids))


def test_an_outline_saved_during_the_outline_job_is_not_overwritten(client, slow_mock):
    make_outline(client)
    o = client.get(f"{B}/outline").json()
    jid = client.post(f"{B}/outline/generate", json={"model": "mock"}).json()["job_id"]
    ol = o["outline"]
    ol["thesis"] = "Owner thesis saved while the model ran."
    assert client.put(f"{B}/outline", json={"outline": ol, "base_rev": o["rev"]}).status_code == 200
    j = _poll(client, jid, lambda j: j["state"] in ("done", "error", "cancelled"))
    assert j["state"] == "error" and j["error_kind"] == "conflict"
    now = client.get(f"{B}/outline").json()
    assert now["outline"]["thesis"] == "Owner thesis saved while the model ran." and now["last_paste"]


# ------------------------------------------------------------------ proposals: skipped files are named
def test_proposal_list_names_the_files_it_skipped(client, root):
    d = root / "lab" / "proposals"
    d.mkdir()
    (d / "bad4.json").write_text(json.dumps({"storyboard": {"shots": "x"}}))
    (d / "bad5.json").write_text("{not json")
    (d / "bad6.json").write_text("[]")
    j = client.get(f"{P}/proposals").json()
    assert j["items"] == []
    got = {s["file"]: s["reason"] for s in j["skipped"]}
    assert set(got) == {"bad4.json", "bad5.json", "bad6.json"} and all(got.values())
    assert "malformed" in got["bad4.json"]
    j = client.get(f"{P}/proposals").json()              # the corrupt file was moved aside: not listed again
    assert {s["file"] for s in j["skipped"]} == {"bad4.json", "bad6.json"}


# ------------------------------------------------------------------ R3B-014: the base of a job is fixed by the request, not by the thread
@pytest.fixture()
def held_job(monkeypatch):
    """The job thread is held at its very first step until the test releases it: no timing involved."""
    import threading
    from bti.script import generate
    release = threading.Event()
    real = generate.build_brief
    release.armed = False

    def held(*a, **k):
        if release.armed:
            assert release.wait(30)
        return real(*a, **k)
    monkeypatch.setattr(generate, "build_brief", held)
    yield release              # a test sets `release.armed = True` once its own set-up jobs are done
    release.set()


@pytest.mark.parametrize("n", range(30))
def test_an_outline_saved_between_the_post_and_the_job_thread_is_a_conflict(client, held_job, n):
    make_outline(client)
    o = client.get(f"{B}/outline").json()
    held_job.armed = True
    jid = client.post(f"{B}/outline/generate", json={"model": "mock"}).json()["job_id"]      # the thread has not read anything yet
    ol = o["outline"]
    ol["thesis"] = "Owner thesis saved before the job thread started."
    assert client.put(f"{B}/outline", json={"outline": ol, "base_rev": o["rev"]}).status_code == 200
    held_job.set()
    j = _poll(client, jid, lambda j: j["state"] in ("done", "error", "cancelled"))
    assert j["state"] == "error" and j["error_kind"] == "conflict"
    now = client.get(f"{B}/outline").json()
    assert now["outline"]["thesis"] == "Owner thesis saved before the job thread started." and now["last_paste"]


def test_a_beat_locked_between_the_post_and_the_job_thread_is_not_overwritten(client, held_job):
    nar = make_narration(client)
    ids = [c["id"] for c in nar["narration"]["chapters"]]
    before = {b["id"]: b["text"] for b in nar["narration"]["chapters"][1]["beats"]}
    held_job.armed = True
    jid = client.post(f"{B}/narration/generate", json={"model": "mock", "force": True, "chapters": ids[:2]}).json()["job_id"]
    locked = nar["narration"]["chapters"][1]["beats"][0]["id"]

    def lock(doc):
        doc["chapters"][1]["beats"][0]["locked"] = True
    _save_retrying(client, lock)
    held_job.set()
    j = _poll(client, jid, lambda j: j["state"] in ("done", "error", "cancelled"))
    assert j["state"] == "done" and j["result"]["written"] == [ids[0]]
    assert j["result"]["skipped"] == [{"chapter": ids[1], "beats": [locked], "reason": "locked while the job ran"}]
    ch = client.get(f"{B}/narration").json()["narration"]["chapters"][1]
    assert {b["id"]: b["text"] for b in ch["beats"]} == before


@pytest.mark.parametrize("n", range(30))
def test_the_old_outline_conflict_test_is_stable(client, slow_mock, n):
    test_an_outline_saved_during_the_outline_job_is_not_overwritten(client, slow_mock)
