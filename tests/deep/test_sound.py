"""Behaviour found sound during the deep test (regression guard). These pass today."""
from __future__ import annotations

import copy
import json
import random
import threading

import pytest
from fastapi.testclient import TestClient

from conftest import put_sb, script_to_narration, state, strip, wait_job


def P(pid):
    return f"/api/projects/{pid}"


def test_revision_rule(client, arn, projects_root):
    st = state(client, arn)
    sb, rev = strip(st["storyboard"]), st["rev"]
    r = put_sb(client, arn, sb, rev)
    assert r.status_code == 200 and r.json()["rev"] == rev                       # unchanged document: same rev
    assert put_sb(client, arn, sb, "deadbeef").status_code == 409
    assert client.put(P(arn) + "/storyboard", json={"storyboard": sb}).status_code == 422
    assert put_sb(client, arn, state(client, arn)["storyboard"], rev).status_code == 200      # derived `_` keys are stripped
    assert "_t0" not in (projects_root / arn / "storyboard.json").read_text()
    bad = copy.deepcopy(sb)
    bad["shots"][0]["technique"] = "NOPE"
    r = put_sb(client, arn, bad, rev)
    assert r.status_code == 422 and r.json()["issues"]


def test_approval_is_server_owned_and_tied_to_rev(client, arn):
    st = state(client, arn)
    sb, rev = strip(st["storyboard"]), st["rev"]
    assert client.post(P(arn) + "/approve", json={"rev": "x"}).status_code == 409
    r = client.post(P(arn) + "/approve", json={"rev": rev})
    assert r.status_code == 200 and state(client, arn)["rev"] == rev
    sb["approvals"] = {"storyboard": {"rev": "forged", "approved_at": "x"}}
    r = put_sb(client, arn, sb, rev)
    assert state(client, arn)["storyboard"]["approvals"]["storyboard"]["rev"] == rev


def test_concurrent_saves_exactly_one_wins(app, arn):
    st = state(TestClient(app), arn)
    sb, rev = strip(st["storyboard"]), st["rev"]
    codes = []

    def go(i):
        c = TestClient(app, raise_server_exceptions=False)
        d = copy.deepcopy(sb)
        d["title"] = f"T{i}"
        codes.append(c.put(P(arn) + "/storyboard", json={"storyboard": d, "base_rev": rev}).status_code)
    ths = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert sorted(codes) == [200] + [409] * 7


def test_failed_write_leaves_the_file_intact(client, arn, projects_root, monkeypatch):
    import os
    f = projects_root / arn / "storyboard.json"
    before = f.read_text()
    st = state(client, arn)
    sb = strip(st["storyboard"])
    sb["title"] = "will not be saved"
    real = os.replace

    def boom(src, dst, *a, **k):
        if str(dst).endswith("storyboard.json"):
            raise OSError("disk full")
        return real(src, dst, *a, **k)
    monkeypatch.setattr(os, "replace", boom)
    r = put_sb(client, arn, sb, st["rev"])
    monkeypatch.undo()
    assert r.status_code >= 400
    assert f.read_text() == before and not list(f.parent.glob("storyboard.json.*.tmp"))


@pytest.mark.parametrize("t", ["..", "%2e%2e", "..%2f..%2f..%2fetc%2fpasswd", "....//....//etc/passwd", "%00", "a%00b", "~", "/etc/passwd"])
def test_path_traversal_everywhere(client, arn, t):
    for tpl in ("/api/projects/{}", "/api/projects/{}/frame?t=1", "/api/projects/{}/pipeline", "/api/projects/{}/audio",
                "/api/projects/t_arn/files/{}", "/api/projects/t_arn/files/media/{}", "/api/projects/t_arn/thumb/{}",
                "/api/projects/t_arn/proposals/{}", "/style/gae/previews/{}", "/api/styles/{}", "/api/library/artworks/{}",
                "/api/jobs/{}", "/{}"):
        r = client.get(tpl.format(t))
        assert r.status_code in (200, 404, 405, 422), (tpl, t, r.status_code)
        assert "root:" not in r.text


def test_project_delete_rules(client, make_project, projects_root):
    pid = make_project("arnolfini-from-books", "t_del2")
    assert client.delete(P(pid)).status_code == 422
    assert client.delete(P(pid), params={"confirm": "nope"}).status_code == 422
    assert client.delete("/api/projects/arnolfini", params={"confirm": "arnolfini"}).status_code == 403
    assert client.delete("/api/projects/technique_lab", params={"confirm": "technique_lab"}).status_code == 403
    link = projects_root / "t_link"
    link.symlink_to(projects_root / pid)
    try:
        assert client.delete(P("t_link"), params={"confirm": "t_link"}).status_code == 409
        assert (projects_root / pid).exists()
    finally:
        link.unlink()
    assert client.delete(P(pid), params={"confirm": pid}).status_code == 200 and not (projects_root / pid).exists()


def test_slugs_and_sources(client, projects_root):
    arts = client.get("/api/library/artworks").json()
    multi = next(a for a in arts if a["n_sources"] >= 3 and not a["only_low_trust"])["artwork_key"]
    for slug in ["../evil", "a/b", "..", "UPPER", "lab_x", "demo_x", "-lead", "a" * 65, "x\x00y", "é", "a b", "x\n"]:
        assert client.post("/api/library/projects", json={"artwork_key": multi, "slug": slug}).status_code == 422, slug
    r = client.post("/api/library/projects", json={"artwork_key": multi, "slug": "t-multi"})
    assert r.status_code == 200
    try:
        assert client.post("/api/library/projects", json={"artwork_key": multi, "slug": "t-multi"}).status_code == 409
        assert client.post("/api/library/projects", json={"work_ids": ["payne_gae/002", "payne_gae/003"]}).status_code == 422
        assert not any(s["book_id"] == "grovier_nws" for s in r.json()["sources"])      # low trust left out by default
    finally:
        import shutil
        shutil.rmtree(projects_root / "t-multi", ignore_errors=True)


def test_every_book_and_artwork_loads(client):
    books = client.get("/api/library/books").json()
    assert len(books) == 6
    n = 0
    for b in books:
        for w in client.get(f"/api/library/books/{b['id']}/works").json():
            assert client.get(f"/api/library/works/{b['id']}/{w['n']}").status_code == 200
            n += 1
    assert n == 340
    for a in client.get("/api/library/artworks", params={"kind": ""}).json():
        assert client.get("/api/library/artworks/" + a["artwork_key"]).status_code == 200


def test_page_images_sample(client):
    random.seed(7)
    works = [(b["id"], w) for b in client.get("/api/library/books").json()
             for w in client.get(f"/api/library/books/{b['id']}/works").json()]
    for bid, w in random.sample(works, 12):
        a, b = w["pdf_pages"]
        for pg in {a, b}:
            r = client.get(f"/api/library/works/{bid}/{w['n']}/page/{pg}.jpg", params={"w": 300})
            assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
        assert client.get(f"/api/library/works/{bid}/{w['n']}/page/{b + 50}.jpg").status_code == 404


def test_beat_operations_at_the_boundaries(client, script_pid):
    n = script_to_narration(client, script_pid)
    ch = n["narration"]["chapters"]
    b0 = ch[0]["beats"][0]
    words = len(b0["text"].split())

    def ops(*o):
        return client.post(P(script_pid) + "/narration/ops",
                           json={"ops": list(o), "base_rev": client.get(P(script_pid) + "/narration").json()["rev"]})
    assert ops({"op": "split", "beat": b0["id"], "at_word": 0}).status_code == 422
    assert ops({"op": "split", "beat": b0["id"], "at_word": words}).status_code == 422
    assert ops({"op": "merge", "beat": b0["id"]}).status_code == 422
    r = ops({"op": "split", "beat": b0["id"], "at_word": 1})
    assert r.status_code == 200
    new = r.json()["results"][0]["id"]
    ids = [b["id"] for c in client.get(P(script_pid) + "/narration").json()["narration"]["chapters"] for b in c["beats"]]
    assert len(ids) == len(set(ids)) and new in ids
    last = client.get(P(script_pid) + "/narration").json()["narration"]["chapters"][-1]
    assert ops(*[{"op": "drop", "beat": b["id"]} for b in last["beats"]]).status_code == 200
    r = ops({"op": "insert", "chapter": last["id"], "text": "Hello there friend."})
    assert r.status_code == 200
    assert ops({"op": "split", "beat": "nope", "at_word": 1}, {"op": "drop", "beat": "zzz"}).status_code == 422


def test_job_cancel_and_edits_drop_approval(client, script_pid):
    n = script_to_narration(client, script_pid)
    assert client.post(P(script_pid) + "/narration/approve", json={"rev": n["rev"]}).status_code == 200
    assert client.get(P(script_pid) + "/narration").json()["approved"]
    cur = client.get(P(script_pid) + "/narration").json()
    nn = cur["narration"]
    nn["chapters"][0]["beats"][0]["note"] = "n"
    client.put(P(script_pid) + "/narration", json={"narration": nn, "base_rev": cur["rev"]})
    assert client.get(P(script_pid) + "/narration").json()["approved"] is False
    r = client.post(P(script_pid) + "/outline/generate", json={"model": "mock", "notes": "[mock:slow]"})
    jid = r.json()["job_id"]
    assert client.post(f"/api/jobs/{jid}/cancel").status_code == 200
    assert wait_job(client, jid, 30)["state"] == "cancelled"


def test_failed_paste_is_kept_and_restored(client, script_pid):
    script_to_narration(client, script_pid)
    r = client.post(P(script_pid) + "/narration/import", json={"text": "no chapter lines here"})
    assert r.status_code == 422
    assert client.get(P(script_pid) + "/narration").json()["last_paste"] == "no chapter lines here"


def test_proposals_respect_locks(client, lab, projects_root):
    st = state(client, lab)
    sb, rev = strip(st["storyboard"]), st["rev"]
    ci = next(i for i, s in enumerate(sb["shots"]) if s["id"] == "s0022")
    d = copy.deepcopy(sb)
    d["shots"][ci]["overlays"][0]["locked"] = True
    d["shots"][ci + 1]["locked"] = True
    r = put_sb(client, lab, d, rev)
    assert r.status_code == 200
    base = strip(state(client, lab)["storyboard"])
    prop = copy.deepcopy(base)
    prop["shots"][ci]["overlays"][0]["params"]["radius"] = 999
    prop["shots"][ci + 1]["note"] = "locked change"
    prop["shots"][ci + 2]["note"] = "free change"
    pdir = projects_root / lab / "proposals"
    pdir.mkdir(exist_ok=True)
    (pdir / "p1.json").write_text(json.dumps({"created_at": "x", "author": "a", "summary": "s", "base_rev": "old", "storyboard": prop}))
    ch = client.get(P(lab) + "/proposals/p1").json()
    assert {c["id"]: c["blocked_by_lock"] for c in ch["changes"]} == {"overlay.s0022.o1": True, "shot.s0023": True, "shot.s0024": False}
    assert ch["proposal"]["stale"] is True
    r = client.post(P(lab) + "/proposals/p1/apply", json={"accept": "all"}).json()
    assert r["applied"] == ["shot.s0024"] and sorted(r["skipped_locked"]) == ["overlay.s0022.o1", "shot.s0023"]
    assert client.post(P(lab) + "/proposals/p1/apply", json={"accept": ["zzz"]}).status_code == 422


def test_pipeline_states(client, script_pid, arn):
    imp = client.get(P(arn) + "/pipeline").json()
    assert imp["imported"] and imp["current"] == "edit" and imp["steps"][0]["state"] == "no_data"
    sel = client.get(P(script_pid) + "/pipeline").json()
    assert sel["current"] == "script" and [s["state"] for s in sel["steps"]][:1] == ["done"]


def test_licence_gate():
    from bti.media.api import check_licence
    ok = ["PD", "Public domain", "CC0", "CC BY 4.0", "CC BY-SA 4.0", "CC-BY-SA-3.0", "pd-art", "CC0 1.0 Universal"]
    no = ["CC BY-NC 4.0", "CC BY-ND 2.0", "CC BY-NC-SA", "fair use", "", "unknown", "GFDL", "Attribution", "CC BY-SA 4.0 non-commercial"]
    assert all(check_licence({"licence": x, "source": "commons"})[0] for x in ok)
    assert not any(check_licence({"licence": x, "source": "commons"})[0] for x in no)
