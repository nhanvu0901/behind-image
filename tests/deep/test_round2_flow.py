"""Round 2 backend tests: journey and stage machine. Each test asserts the CORRECT behaviour and FAILS while its bug exists.
Mock model only, temp data roots (see conftest)."""
from __future__ import annotations

import copy
import itertools
import shutil

import pytest

from conftest import state, strip, wait_job

ART = "bosch-the-garden-of-earthly-delights"
_n = itertools.count()


def P(pid):
    return f"/api/projects/{pid}"


@pytest.fixture()
def flow_pid(client, projects_root):
    """A fresh project made from a library artwork through the API."""
    pid = f"r2-flow-{next(_n)}"
    r = client.post("/api/library/projects", json={"artwork_key": ART, "slug": pid})
    assert r.status_code == 200, r.text
    yield pid
    shutil.rmtree(projects_root / pid, ignore_errors=True)


def to_approved_narration(client, pid):
    r = client.post(P(pid) + "/outline/generate", json={"model": "mock"})
    assert wait_job(client, r.json()["job_id"])["state"] == "done"
    o = client.get(P(pid) + "/outline").json()
    assert client.post(P(pid) + "/outline/approve", json={"rev": o["rev"]}).status_code == 200
    r = client.post(P(pid) + "/narration/generate", json={"model": "mock"})
    assert wait_job(client, r.json()["job_id"])["state"] == "done"
    n = client.get(P(pid) + "/narration").json()
    assert client.post(P(pid) + "/narration/approve", json={"rev": n["rev"]}).status_code == 200
    return client.get(P(pid) + "/narration").json()


def test_R2B_001_narration_approval_does_not_survive_a_changed_outline(client, flow_pid):
    """Outline loses a chapter and is approved again: the narration still has that chapter. Its old approval must not revive."""
    to_approved_narration(client, flow_pid)
    o = client.get(P(flow_pid) + "/outline").json()
    od = copy.deepcopy(o["outline"])
    od["chapters"].pop(2)
    assert client.put(P(flow_pid) + "/outline", json={"outline": od, "base_rev": o["rev"]}).status_code == 200
    o = client.get(P(flow_pid) + "/outline").json()
    assert client.post(P(flow_pid) + "/outline/approve", json={"rev": o["rev"]}).status_code == 200
    n = client.get(P(flow_pid) + "/narration").json()
    codes = [i["code"] for i in n["issues"]]
    assert "chapter_not_in_outline" in codes                      # precondition: the narration is out of line with the outline
    assert n["approved"] is False, "narration stays approved although it holds a chapter the outline no longer has"
    assert client.get(P(flow_pid) + "/pipeline").json()["stage"] != "script"


def test_R2B_002_stage_agrees_with_stale_storyboard_approval(client, make_project):
    """After a storyboard is edited, its approval is stale: the step says so, the stage must not say `approved`."""
    pid = make_project("arnolfini", "t_r2_stage")
    st = state(client, pid)
    assert client.post(P(pid) + "/approve", json={"rev": st["rev"]}).status_code == 200
    sb = strip(st["storyboard"])
    sb["title"] = "changed after approval"
    assert client.put(P(pid) + "/storyboard", json={"storyboard": sb, "base_rev": st["rev"]}).status_code == 200
    pl = client.get(P(pid) + "/pipeline").json()
    edit = next(s for s in pl["steps"] if s["id"] == "edit")
    assert "cũ" in edit["detail"] or edit["state"] != "done"          # the step knows the approval is stale
    assert pl["stage"] != "approved", f"stage={pl['stage']} but the approval is stale"
    row = next(p for p in client.get("/api/projects").json() if p["id"] == pid)
    assert row["stage"] != "approved"


def test_R2B_010_put_narration_refuses_duplicate_beat_ids(client, flow_pid):
    to_approved_narration(client, flow_pid)
    n = client.get(P(flow_pid) + "/narration").json()
    doc = copy.deepcopy(n["narration"])
    b0 = doc["chapters"][0]["beats"]
    b0[1]["id"] = b0[0]["id"]                                   # twice in one chapter
    doc["chapters"][1]["beats"][0]["id"] = b0[0]["id"]          # and in another chapter
    r = client.put(P(flow_pid) + "/narration", json={"narration": doc, "base_rev": n["rev"]})
    assert r.status_code == 422, f"duplicate beat ids saved: {r.status_code}"
    assert client.get(P(flow_pid) + "/narration").json()["rev"] == n["rev"]


def test_R2B_010_put_narration_does_not_coerce_role_or_card(client, flow_pid):
    to_approved_narration(client, flow_pid)
    n = client.get(P(flow_pid) + "/narration").json()
    doc = copy.deepcopy(n["narration"])
    doc["chapters"][2]["role"] = "bogus"
    r = client.put(P(flow_pid) + "/narration", json={"narration": doc, "base_rev": n["rev"]})
    assert r.status_code == 422, "an unknown role is silently turned into 'chapter'"
    doc = copy.deepcopy(n["narration"])
    doc["chapters"][2]["card"] = "yes"
    r = client.put(P(flow_pid) + "/narration", json={"narration": doc, "base_rev": n["rev"]})
    assert r.status_code == 422, "card: 'yes' is silently turned into true"


@pytest.mark.parametrize("cid", ["c 1", "C01", "é", "../../x", "c01\n## x"])
def test_R2B_013_outline_chapter_id_must_be_readable_by_the_narration_parser(client, flow_pid, cid):
    r = client.post(P(flow_pid) + "/outline/generate", json={"model": "mock"})
    assert wait_job(client, r.json()["job_id"])["state"] == "done"
    o = client.get(P(flow_pid) + "/outline").json()
    od = copy.deepcopy(o["outline"])
    od["chapters"][0]["id"] = cid
    r = client.put(P(flow_pid) + "/outline", json={"outline": od, "base_rev": o["rev"]})
    assert r.status_code == 422, f"chapter id {cid!r} accepted; the narration job will fail on it after the model calls"
