"""API paths of the script stage, on a copy of projects/arnolfini-from-books, with the mock provider."""
import shutil
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti.editor.app import create_app  # noqa: E402
from bti.script import env as env_mod, models as models_mod, store  # noqa: E402
from bti.script.providers import mock as mock_mod, set_transport  # noqa: E402

REAL = REPO / "projects" / "arnolfini-from-books"
pytestmark = pytest.mark.skipif(not (REAL / "project.json").is_file(), reason="projects/arnolfini-from-books is missing")
P = "/api/projects/arn"


@pytest.fixture(autouse=True)
def _isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("BTI_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setenv("BTI_AGY_BIN", "")
    models_mod.reset_cache()
    for k in ("GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    env_mod._cache.clear()
    set_transport(None)
    mock_mod.CALLS.clear()
    yield
    set_transport(None)


@pytest.fixture()
def c(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    shutil.copytree(REAL, root / "arn", ignore=shutil.ignore_patterns("script", "cache", "history"))
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    with TestClient(app) as cl:
        cl.root = root
        yield cl


def job(c, jid, until=("done", "error", "cancelled"), seconds=20):
    end = time.time() + seconds
    while time.time() < end:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["state"] in until:
            return j
        time.sleep(0.03)
    raise AssertionError(j)


def outline_ready(c):
    jid = c.post(P + "/outline/generate", json={"model": "mock"}).json()["job_id"]
    assert job(c, jid)["state"] == "done"
    o = c.get(P + "/outline").json()
    assert c.post(P + "/outline/approve", json={"rev": o["rev"]}).status_code == 200
    return c.get(P + "/outline").json()


def narration_ready(c, notes=""):
    outline_ready(c)
    jid = c.post(P + "/narration/generate", json={"model": "mock", "notes": notes}).json()["job_id"]
    j = job(c, jid)
    assert j["state"] == "done", j
    return c.get(P + "/narration").json()


def test_models_and_missing_key(c, monkeypatch):
    ms = {m["id"]: m for m in c.get("/api/models").json()}
    assert ms["mock"]["enabled"] and ms["agy"]["enabled"] is False and "agy" in ms["agy"]["message"]     # agy absent in tests
    assert not ms["openrouter-claude"]["enabled"] and ms["openrouter-claude"]["missing_env"] == "OPENROUTER_API_KEY" and ms["openrouter-claude"]["paid"]
    assert "gemini-4-argon" not in ms
    r = c.post(P + "/outline/generate", json={"model": "openrouter-claude"})
    assert r.status_code == 409 and r.json()["missing_env"] == "OPENROUTER_API_KEY"
    assert c.post(P + "/outline/generate", json={"model": "nope"}).status_code == 404
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-SECRET1234567890")
    txt = c.get("/api/models").text
    assert "sk-or-SECRET" not in txt and {m["id"]: m for m in c.get("/api/models").json()}["openrouter-claude"]["enabled"]


def test_brief(c):
    b = c.get(P + "/brief").json()
    assert b["code_map"]["PAY"] == "payne_gae/002" and "PAY-01" in b["paragraph_ids"] and b["details"]
    assert c.get("/api/projects/nope/brief").status_code == 404
    assert c.get("/api/projects/..%2f..%2fx/brief").status_code in (404, 422)
    o = c.put(P + "/brief/options", json={"target_words": 1500, "include_low": ["grovier_nws"], "wps": 2.5}).json()
    assert o["target_words"] == 1500 and o["wps"] == 2.5 and o["include_low"] == ["grovier_nws"]


def test_prompt_endpoint(c):
    r = c.get(P + "/prompt", params={"phase": "outline"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain") and r.text.startswith("PHASE: outline")
    assert c.get(P + "/prompt", params={"phase": "script"}).status_code == 409           # needs an approved outline
    assert c.get(P + "/prompt", params={"phase": "bogus"}).status_code == 422
    outline_ready(c)
    s = c.get(P + "/prompt", params={"phase": "script", "chapters": "c02"}).text
    assert "Chapters to write now: c02" in s and "THE APPROVED OUTLINE" in s


def test_outline_flow_generate_edit_approve_and_staleness(c):
    assert c.get(P + "/outline").json()["outline"] is None
    jid = c.post(P + "/outline/generate", json={"model": "mock", "notes": "x"}).json()["job_id"]
    j = job(c, jid)
    assert j["state"] == "done" and j["chapters"][0]["state"] == "done"
    o = c.get(P + "/outline").json()
    assert o["outline"]["source"]["kind"] == "model" and not o["approved"] and o["rev"]
    doc = o["outline"]
    doc["thesis"] = "My own thesis."
    doc["chapters"][1]["word_budget"] = 300
    assert c.put(P + "/outline", json={"outline": doc, "base_rev": "0" * 40}).status_code == 409
    saved = c.put(P + "/outline", json={"outline": doc, "base_rev": o["rev"]}).json()
    assert saved["rev"] != o["rev"] and saved["outline"]["thesis"] == "My own thesis."
    assert c.put(P + "/outline", json={"outline": doc, "base_rev": o["rev"]}).status_code == 409   # old rev again
    assert c.post(P + "/outline/approve", json={"rev": o["rev"]}).status_code == 409                 # stale rev
    a = c.post(P + "/outline/approve", json={"rev": saved["rev"]}).json()
    assert a["approved"] and a["outline"]["approval"]["sha1"] == saved["rev"]
    doc["thesis"] = "Changed after approval."
    after = c.put(P + "/outline", json={"outline": doc, "base_rev": saved["rev"]}).json()
    assert after["approved"] is False and after["outline"]["approval"]["approved"] is False       # any edit drops it
    doc["chapters"] = []
    saved2 = c.put(P + "/outline", json={"outline": doc, "base_rev": after["rev"]}).json()
    r = c.post(P + "/outline/approve", json={"rev": saved2["rev"]})
    assert r.status_code == 422 and any(i["code"] == "no_chapters" for i in r.json()["issues"])      # errors block approval


def test_outline_import_good_and_bad_paste_is_kept(c):
    bad = "I could not do it.\n\nHere are ideas about the painting, not an outline."
    r = c.post(P + "/outline/import", json={"text": bad})
    assert r.status_code == 422 and r.json()["kept"] is True and "Found 2 paragraph(s)" in r.json()["detail"] and r.json()["paragraphs"]
    assert c.get(P + "/outline").json()["last_paste"] == bad                                      # restored on reload
    assert not (c.root / "arn" / "script" / "outline.json").exists()                              # nothing was written
    good = ("OUTLINE\nTHESIS: T\nHOOKS\nh1: a\nHOOK CHOICE: h1\nFACTS\nf01 | established | PAY-01 | A fact.\n"
            "CHAPTERS\n## c01 COLD OPEN\nBUDGET: 100\nFACTS: f01\n## c02 CLOSING\nBUDGET: 100\nTARGET WORDS: 200")
    r = c.post(P + "/outline/import", json={"text": good})
    assert r.status_code == 200 and r.json()["outline"]["source"]["kind"] == "paste" and len(r.json()["outline"]["chapters"]) == 2
    assert c.get(P + "/outline").json()["last_paste"] == ""


def test_narration_flow_generate_ops_rewrite_approve(c):
    n = narration_ready(c)
    assert n["stats"]["words"] > 1200 and len(n["narration"]["chapters"]) == 6 and not n["approved"]
    assert n["stats"]["minutes"] > 5 and all(ch["words"] > 0 for ch in n["stats"]["chapters"])
    rev = n["rev"]
    ch2 = n["narration"]["chapters"][1]
    b0 = ch2["beats"][0]
    # cut a beat with the operations endpoint
    r = c.post(P + "/narration/ops", json={"base_rev": rev, "ops": [{"op": "drop", "beat": ch2["beats"][1]["id"]}]})
    assert r.status_code == 200
    n2 = r.json()
    assert n2["rev"] != rev and len(n2["narration"]["chapters"][1]["beats"]) == len(ch2["beats"]) - 1
    assert c.post(P + "/narration/ops", json={"base_rev": rev, "ops": []}).status_code == 409        # stale base
    sp = c.post(P + "/narration/ops", json={"base_rev": n2["rev"], "ops": [{"op": "split", "beat": b0["id"], "at_word": 5}]}).json()
    new_id = sp["results"][0]["id"]
    assert new_id not in [b["id"] for b in ch2["beats"]]
    bad = c.post(P + "/narration/ops", json={"base_rev": sp["rev"], "ops": [{"op": "merge", "beat": b0["id"]}]})
    assert bad.status_code == 422                                                                    # first beat of the chapter
    # rewrite one chapter with a note
    jid = c.post(P + "/narration/generate", json={"model": "mock", "chapters": ["c03"], "notes": "shorter"}).json()["job_id"]
    assert job(c, jid)["state"] == "done"
    cur = c.get(P + "/narration").json()
    assert [b["id"] for b in cur["narration"]["chapters"][1]["beats"]][0] == b0["id"]               # other chapters untouched
    # approve
    r = c.post(P + "/narration/approve", json={"rev": cur["rev"]})
    assert r.status_code == 200 and r.json()["approved"] is True
    stage = {p["id"]: p["stage"] for p in c.get("/api/projects").json()}["arn"]
    assert stage == "script"
    d = r.json()["narration"]
    d["chapters"][0]["beats"][0]["text"] += " One more sentence."
    put = c.put(P + "/narration", json={"narration": d, "base_rev": cur["rev"]}).json()
    assert put["approved"] is False and put["stale"] is False and "stats" in put and "issues" in put   # an edit drops the approval
    assert {p["id"]: p["stage"] for p in c.get("/api/projects").json()}["arn"] == "outlined"


def test_approve_refuses_errors_and_a_stale_outline(c):
    n = narration_ready(c)
    doc = n["narration"]
    doc["chapters"][0]["beats"][0]["text"] = "[PAUSE] broken"
    put = c.put(P + "/narration", json={"narration": doc, "base_rev": n["rev"]}).json()
    assert any(i["code"] == "markup_in_text" for i in put["issues"])
    r = c.post(P + "/narration/approve", json={"rev": put["rev"]})
    assert r.status_code == 422 and any(i["code"] == "markup_in_text" for i in r.json()["issues"])
    doc["chapters"][0]["beats"][0]["text"] = "Fixed spoken words now."
    put = c.put(P + "/narration", json={"narration": doc, "base_rev": put["rev"]}).json()
    o = c.get(P + "/outline").json()
    od = o["outline"]
    od["thesis"] += " (late edit)"
    c.put(P + "/outline", json={"outline": od, "base_rev": o["rev"]})
    r = c.post(P + "/narration/approve", json={"rev": put["rev"]})
    assert r.status_code == 422 and any(i["code"].startswith("outline_") for i in r.json()["issues"])


def test_narration_import_good_and_bad_paste(c):
    assert c.post(P + "/narration/import", json={"text": "## c01 X\nHi."}).status_code == 409        # no outline yet
    o = outline_ready(c)["outline"]
    chs = o["chapters"]
    text = "Some chatter.\n\nFINAL SCRIPT\n\n" + "\n\n".join(
        f"## {ch['id']} {ch['title']}\nSpoken words for {ch['title'].lower()}, kept short and plain.\n>> facts: f01 | show: the whole painting" for ch in chs)
    r = c.post(P + "/narration/import", json={"text": text})
    assert r.status_code == 200 and len(r.json()["narration"]["chapters"]) == len(chs) and r.json()["narration"]["source"]["kind"] == "paste"
    assert any(i["code"] == "words_under" for i in r.json()["issues"])                               # short, so it cannot be approved
    before = c.get(P + "/narration").json()
    bad = "## c01 COLD OPEN\nOne.\n\n## c99 NOWHERE\nThis chapter is not in the outline at all.\n"
    r = c.post(P + "/narration/import", json={"text": bad})
    assert r.status_code == 422 and "c99 NOWHERE" in r.json()["detail"] and r.json()["paragraphs"] and r.json()["kept"]
    after = c.get(P + "/narration").json()
    assert after["rev"] == before["rev"] and after["last_paste"] == bad                              # nothing written, paste kept
    r = c.post(P + "/narration/import", json={"text": "## c01 COLD OPEN\nNew opening words only.", "merge": True})
    assert r.status_code == 200 and len(r.json()["narration"]["chapters"]) == len(chs)
    assert r.json()["narration"]["chapters"][0]["beats"][0]["text"] == "New opening words only."
    assert c.get(P + "/narration").json()["last_paste"] == ""


def test_generate_guards(c):
    assert c.post(P + "/narration/generate", json={"model": "mock"}).status_code == 409               # outline not approved
    narration_ready(c)
    assert c.post(P + "/narration/generate", json={"model": "mock", "chapters": ["c99"]}).status_code == 422
    cur = c.get(P + "/narration").json()
    doc = cur["narration"]
    doc["chapters"][2]["beats"][0]["locked"] = True
    saved = c.put(P + "/narration", json={"narration": doc, "base_rev": cur["rev"]}).json()
    r = c.post(P + "/narration/generate", json={"model": "mock", "chapters": ["c03"]})
    assert r.status_code == 409 and r.json()["locked"]
    ok = c.post(P + "/narration/generate", json={"model": "mock", "chapters": ["c03"], "force": True})
    assert ok.status_code == 200 and job(c, ok.json()["job_id"])["state"] == "done"


def test_job_cancel_timeout_and_listing(c):
    outline_ready(c)
    r = c.post(P + "/narration/generate", json={"model": "mock", "chapters": ["c01"], "notes": "[mock:slow]"})
    jid = r.json()["job_id"]
    busy = c.post(P + "/narration/generate", json={"model": "mock", "chapters": ["c02"]})
    assert busy.status_code == 409 and busy.json()["job_id"] == jid
    time.sleep(0.2)
    assert c.get(P + "/script/jobs").json()[0]["id"] == jid
    assert c.post(f"/api/jobs/{jid}/cancel").status_code == 200
    j = job(c, jid)
    assert j["state"] == "cancelled" and j["chapters"][0]["state"] == "cancelled"
    assert c.post("/api/jobs/zzz/cancel").status_code == 404 and c.get("/api/jobs/zzz").status_code == 404
    jid = c.post(P + "/narration/generate", json={"model": "mock", "chapters": ["c01"], "notes": "[mock:ratelimit]"}).json()["job_id"]
    j = job(c, jid)
    assert j["error_kind"] == "rate_limit" and j["alternatives"] == []                                # only the mock is enabled


def test_validation_retry_through_the_api(c):
    narration_ready(c, "[mock:bad c04]")
    retry = [x for x in mock_mod.CALLS if x["retry"]]
    assert len(retry) == 1 and "Validation failed" in retry[0]["user"]


def test_validation_failure_keeps_chapters_and_paste(c):
    outline_ready(c)
    jid = c.post(P + "/narration/generate", json={"model": "mock", "notes": "[mock:alwaysbad c02]"}).json()["job_id"]
    j = job(c, jid)
    assert j["state"] == "error" and j["error_kind"] == "validation"
    n = c.get(P + "/narration").json()
    assert [ch["id"] for ch in n["narration"]["chapters"]] == ["c01"] and "[PAUSE]" in n["last_paste"]


def test_editor_preview_jobs_still_answer_on_the_shared_path(c):
    assert c.get("/api/jobs/doesnotexist").status_code == 404
    assert c.get("/api/health").status_code == 200


def test_ids_and_paths_are_validated(c):
    for bad in ("nope", "..%2fx", "A B"):
        assert c.get(f"/api/projects/{bad}/outline").status_code in (404, 422)
    assert c.get("/api/projects/arn/narration").json()["narration"] is None


def test_no_key_value_is_ever_in_a_response(c, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "AIzaTOPSECRET0000000000")
    for url in ("/api/models", P + "/brief", P + "/outline", P + "/narration"):
        assert "AIzaTOPSECRET" not in c.get(url).text
