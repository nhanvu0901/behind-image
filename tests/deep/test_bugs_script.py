"""Known bugs in the script stage, library, proposals, projects. Each test FAILS today. Mock model only."""
from __future__ import annotations

import copy
import io
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from conftest import script_to_narration, state, strip, wait_job


def P(pid):
    return f"/api/projects/{pid}"


def test_B008_put_without_document_does_not_wipe(client, script_pid):
    n = script_to_narration(client, script_pid)
    assert len(n["narration"]["chapters"]) > 0
    r = client.put(P(script_pid) + "/narration", json={"base_rev": n["rev"]})
    assert r.status_code == 422, r.status_code
    o = client.get(P(script_pid) + "/outline").json()
    r = client.put(P(script_pid) + "/outline", json={"base_rev": o["rev"]})
    assert r.status_code == 422, r.status_code
    assert len(client.get(P(script_pid) + "/narration").json()["narration"]["chapters"]) > 0
    assert len(client.get(P(script_pid) + "/outline").json()["outline"]["chapters"]) > 0


def test_B009_only_one_job_can_start(app, script_pid):
    codes = []
    barrier = threading.Barrier(6)

    def go():
        c = TestClient(app, raise_server_exceptions=False)      # no `with`: do not run (and end) the shared app's lifespan
        barrier.wait()
        codes.append(c.post(P(script_pid) + "/outline/generate", json={"model": "mock"}).status_code)
    ths = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    time.sleep(1.5)
    assert codes.count(200) == 1, sorted(codes)


@pytest.mark.parametrize("op", [1, None, "x"])
def test_B010_non_object_op_is_422(client, script_pid, op):
    n = script_to_narration(client, script_pid)
    r = client.post(P(script_pid) + "/narration/ops", json={"ops": [op], "base_rev": n["rev"]})
    assert r.status_code == 422, r.status_code


def test_B010_insert_does_not_coerce_types(client, script_pid):
    n = script_to_narration(client, script_pid)
    cid = n["narration"]["chapters"][0]["id"]
    r = client.post(P(script_pid) + "/narration/ops",
                    json={"ops": [{"op": "insert", "chapter": cid, "text": ["a"]}], "base_rev": n["rev"]})
    assert r.status_code == 422
    n = client.get(P(script_pid) + "/narration").json()
    r = client.post(P(script_pid) + "/narration/ops",
                    json={"ops": [{"op": "insert", "chapter": cid, "facts": "f01"}], "base_rev": n["rev"]})
    assert r.status_code == 422


@pytest.mark.parametrize("body", [{"target_words": 5}, {"target_words": 99999999}, {"target_words": "x"}, {"wps": 0},
                                   {"include_low": 5}, {"include_low": "abc"}])
def test_B011_brief_options_are_validated(client, script_pid, body):
    r = client.put(P(script_pid) + "/brief/options", json=body)
    assert r.status_code == 422, (r.status_code, r.text[:80])


def test_B012_failed_job_leaves_no_running_chapter(client, script_pid):
    script_to_narration(client, script_pid)
    r = client.post(P(script_pid) + "/narration/generate", json={"model": "mock", "force": True, "notes": "[mock:ratelimit]"})
    j = wait_job(client, r.json()["job_id"])
    assert j["state"] == "error"
    assert not [c for c in j["chapters"] if c["state"] in ("running", "pending")], j["chapters"]


def test_B013_import_keeps_or_refuses_locked_beats(client, script_pid):
    n = script_to_narration(client, script_pid)
    nn = n["narration"]
    nn["chapters"][0]["beats"][0]["locked"] = True
    lock_id = nn["chapters"][0]["beats"][0]["id"]
    assert client.put(P(script_pid) + "/narration", json={"narration": nn, "base_rev": n["rev"]}).status_code == 200
    text = "FINAL SCRIPT\n\n" + "\n\n".join(f"## {c['id']} {c['title']}\n" + "\n\n".join("Replaced text here." for _ in c["beats"])
                                          for c in nn["chapters"])
    r = client.post(P(script_pid) + "/narration/import", json={"text": text})
    now = client.get(P(script_pid) + "/narration").json()["narration"]
    kept = any(b["id"] == lock_id and b["locked"] for c in now["chapters"] for b in c["beats"])
    assert r.status_code == 409 or kept, "the locked beat was replaced by a paste"


def test_B014_lone_surrogate_in_paste(client, script_pid):
    script_to_narration(client, script_pid)
    r = client.post(P(script_pid) + "/narration/import", content=b'{"text":"## c01 COLD OPEN\\n\\ud800 broken"}',
                    headers={"content-type": "application/json"})
    assert r.status_code < 500, r.status_code


def test_B014_bad_utf8_last_paste_does_not_break_get(client, script_pid, projects_root):
    script_to_narration(client, script_pid)
    (projects_root / script_pid / "script" / "last_paste.txt").write_bytes(b"\xff\xfe\x00bad")
    assert client.get(P(script_pid) + "/narration").status_code == 200


def test_B015_outline_edit_makes_narration_approval_stale(client, script_pid):
    n = script_to_narration(client, script_pid)
    text = "FINAL SCRIPT\n\n" + "\n\n".join(
        f"## {c['id']} {c['title']}\n" + " ".join(["Sentence of words here."] * 60) for c in n["narration"]["chapters"])
    assert client.post(P(script_pid) + "/narration/import", json={"text": text}).status_code == 200
    n = client.get(P(script_pid) + "/narration").json()
    assert client.post(P(script_pid) + "/narration/approve", json={"rev": n["rev"]}).status_code == 200
    assert client.get(P(script_pid) + "/narration").json()["approved"] is True
    o = client.get(P(script_pid) + "/outline").json()
    ol = o["outline"]
    ol["thesis"] += " edited"
    assert client.put(P(script_pid) + "/outline", json={"outline": ol, "base_rev": o["rev"]}).status_code == 200
    n = client.get(P(script_pid) + "/narration").json()
    steps = {s["id"]: s["state"] for s in client.get(P(script_pid) + "/pipeline").json()["steps"]}
    assert n["approved"] is False and steps["script"] != "done"


def test_B016_delete_refused_while_a_job_runs(client, make_project, projects_root):
    # CORRECTED by the backend fixer with the coordinator's authority: the old second check (folder gone after a refused
    # delete) contradicted the first. Fixed behaviour: 409 while the job runs, folder intact after it ends, then delete works.
    pid = make_project("arnolfini-from-books", "t_del")
    r = client.post(P(pid) + "/outline/generate", json={"model": "mock", "notes": "[mock:slow]"})
    assert r.status_code == 200
    time.sleep(0.5)
    d = client.delete(P(pid), params={"confirm": pid})
    assert d.status_code == 409
    wait_job(client, r.json()["job_id"], timeout=60)
    time.sleep(1)
    assert json.loads((projects_root / pid / "project.json").read_text())
    assert client.delete(P(pid), params={"confirm": pid}).status_code == 200
    time.sleep(1)
    assert not (projects_root / pid).exists()


def test_B017_lab_projects_are_protected(client, make_project, projects_root):
    # ADJUSTED by the backend fixer to the owner's decision: protection is the `"protected": true` flag in project.json
    # (set for arnolfini and technique_lab); lab_* and demo_* projects are ordinary and deletable.
    pid = make_project("technique_lab", "t_flagged")                       # carries the flag in its project.json
    assert client.delete(P(pid), params={"confirm": pid}).status_code == 403
    assert (projects_root / pid).is_dir()
    pid = make_project("lab_text", "lab_tmp")
    assert not json.loads((projects_root / pid / "project.json").read_text()).get("protected") \
        if (projects_root / pid / "project.json").is_file() else True
    r = client.delete(P(pid), params={"confirm": pid})
    assert r.status_code == 200, r.status_code


def test_B018_malformed_proposal_does_not_break_the_list(client, lab, projects_root):
    d = projects_root / lab / "proposals"
    d.mkdir(exist_ok=True)
    (d / "bad4.json").write_text(json.dumps({"storyboard": {"shots": "x", "assets": [1], "end": 5}}))
    try:
        assert client.get(P(lab) + "/proposals").status_code == 200
        assert client.get(P(lab) + "/proposals/bad4").status_code < 500
        assert client.post(P(lab) + "/proposals/bad4/apply", json={"accept": "all"}).status_code < 500
    finally:
        (d / "bad4.json").unlink(missing_ok=True)


@pytest.mark.parametrize("name,data", [("a.png", b"not an image"), ("a.png", b""), ("a.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000)])
def test_B019_upload_must_be_an_image(client, lab, name, data):
    r = client.post(P(lab) + "/assets/upload", files={"file": (name, data, "image/png")},
                    data={"title": "t", "licence": "CC0", "source_url": "http://x", "author": "me"})
    assert r.status_code == 422, r.status_code


def test_B027_jobs_survive_a_restart(projects_root, script_pid):
    from bti.editor.app import create_app
    a1 = create_app(projects_root=projects_root)
    with TestClient(a1) as c1:
        r = c1.post(P(script_pid) + "/outline/generate", json={"model": "mock"})
        jid = r.json()["job_id"]
        wait_job(c1, jid)
    a2 = create_app(projects_root=projects_root)
    with TestClient(a2) as c2:
        assert c2.get(f"/api/jobs/{jid}").status_code == 200
