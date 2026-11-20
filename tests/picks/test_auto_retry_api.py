"""fixes4, point 2: the route `POST /api/projects/{pid}/picks/retry-missing`, the action `picks.retry_missing` in the state answer and the command's view of it, through the real app."""
import pytest
from test_auto_api import api, err, wait  # noqa: F401
from auto_fixtures import paid  # noqa: F401

from bti.picks import doc, service
from bti.picks.errors import PicksError

REAL_FETCH = service.fetch_asset
PROJECT = "/api/projects/%s"


def state(api):
    return api.get(PROJECT % api.pid + "/state").json()


def act(st, aid):
    return next((a for a in st["next_actions"] if a["id"] == aid), None)


def limited_run(api, monkeypatch):
    """A run of the pictures agent in which Commons refuses every download (the two Commons pictures are listed `import_limited`), then the download works again."""
    def refuse(pdir, source, source_id):
        if source == "commons":
            raise PicksError(503, "limits", "source_rate_limited", retryable=True, retry_after=None)
        return REAL_FETCH(pdir, source, source_id)
    monkeypatch.setattr(service, "fetch_asset", refuse)
    job = wait(api, api.post("/api/projects/%s/picks/auto" % api.pid, json={}).json()["job_id"])
    assert job["state"] == "done", job.get("error")
    monkeypatch.setattr(service, "fetch_asset", REAL_FETCH)


def test_the_action_is_listed_only_while_a_line_says_import_limited_and_is_ready_with_the_saved_files(api, monkeypatch):
    assert act(state(api), "picks.retry_missing") is None                       # no line says it: nothing is listed
    limited_run(api, monkeypatch)
    a = act(state(api), "picks.retry_missing")
    assert a["ready"] is True and a["needs"] == [] and a["advances"] is True and a["long_job"] is True and a["uses_model"] is False
    assert a["method"] == "POST" and a["path"] == "/api/projects/%s/picks/retry-missing" % api.pid and a["follow"] == "GET /api/longjobs/{job_id}"
    assert a["cost"] is None and a["gate"] is False and a["step"] == "picks" and a["body"]["beats"] is None and a["body"]["actor"].startswith("cli:")
    ids = [x["id"] for x in state(api)["next_actions"]]
    assert ids.index("picks.retry_missing") < ids.index("picks.approve")         # before the gate, in the order of the steps


def test_without_the_saved_files_it_is_listed_but_not_ready_and_says_why(api, monkeypatch):
    limited_run(api, monkeypatch)
    import shutil
    from bti.picks.auto import store
    (store.cache_dir(api.pdir) / "choice.json").unlink()
    a = act(state(api), "picks.retry_missing")
    assert a["ready"] is False and a["needs"] == ["picks_saved_files"] and a["advances"] is False
    err(api.post("/api/projects/%s/picks/retry-missing" % api.pid, json={}), 409, "retry_no_files")


def test_the_route_runs_the_job_and_the_state_stops_offering_it_to_the_run(api, monkeypatch):
    limited_run(api, monkeypatch)
    r = api.post("/api/projects/%s/picks/retry-missing" % api.pid, json={"actor": "cli:test"})
    assert r.status_code == 200 and r.json()["lines"] == 2 and len(r.json()["job_id"]) == 16
    job = wait(api, r.json()["job_id"])
    assert job["state"] == "done", job.get("error")
    assert job["kind"] == "picks" and job["meta"]["action"] == "retry" and job["result"]["lines_fixed"] == ["b0003", "b0004"]
    assert job["result"]["sentence"] == "Đã tải lại hình cho 2/2 đoạn."
    page = api.get("/api/projects/%s/picks" % api.pid).json()
    assert page["approved"] is False and all("missing" not in b for b in page["picks"]["beats"].values())
    assert act(state(api), "picks.retry_missing") is None                       # nothing says import_limited any more
    log = api.get("/api/projects/%s/changes" % api.pid).json()["changes"]
    assert [c["actor"] for c in log[:2]] == ["cli:test", "cli:test"]


def test_a_line_that_is_still_refused_stays_listed_but_is_not_offered_to_the_run_a_second_time(api, monkeypatch):
    limited_run(api, monkeypatch)
    def refuse(pdir, source, source_id):
        raise PicksError(503, "limits", "source_rate_limited", retryable=True, retry_after=45)
    monkeypatch.setattr(service, "fetch_asset", refuse)
    job = wait(api, api.post("/api/projects/%s/picks/retry-missing" % api.pid, json={}).json()["job_id"])
    assert job["state"] == "done" and job["result"]["lines_fixed"] == [] and len(job["result"]["lines_still_limited"]) == 2
    a = act(state(api), "picks.retry_missing")
    assert a["ready"] is True and a["advances"] is False                         # listed, ready for a hand-started call, but the run has had its one try
    monkeypatch.setattr(service, "fetch_asset", REAL_FETCH)
    job = wait(api, api.post("/api/projects/%s/picks/retry-missing" % api.pid, json={}).json()["job_id"])
    assert job["result"]["lines_fixed"] == ["b0003", "b0004"]                    # by hand it can be called again, and now the source gives the pictures


def test_the_body_is_checked_and_the_refusals_say_what_to_change(api, monkeypatch):
    url = "/api/projects/%s/picks/retry-missing" % api.pid
    err(api.post(url, json={}), 409, "retry_nothing_to_do")                      # nothing says import_limited
    limited_run(api, monkeypatch)
    for body, field in (({"beats": "b0003"}, "beats"), ({"beats": [1]}, "beats"), ({"beats": []}, "beats")):
        b = err(api.post(url, json=body), 422, "invalid_field")
        assert b["fields"][0]["path"] == field if "fields" in b else b["field"] == field
    err(api.post(url, json=[1]), 422, "invalid_request")
    err(api.post(url, json={"actor": "robot"}), 422, "invalid_field")
    err(api.post(url, json={"beats": ["b0001"]}), 409, "retry_nothing_to_do")    # a line that does not say it
    assert api.post("/api/projects/nope/picks/retry-missing", json={}).status_code == 404


def test_the_picks_agent_refuses_to_start_while_the_retry_runs_and_the_action_waits(api, monkeypatch):
    import threading
    limited_run(api, monkeypatch)
    started, release = threading.Event(), threading.Event()

    def slow(pdir, source, source_id):
        started.set()
        release.wait(20)
        return REAL_FETCH(pdir, source, source_id)
    monkeypatch.setattr(service, "fetch_asset", slow)
    job_id = api.post("/api/projects/%s/picks/retry-missing" % api.pid, json={}).json()["job_id"]
    try:
        assert started.wait(20)
        a = act(state(api), "picks.retry_missing")
        assert a["ready"] is False and a["needs"] == ["no_running_job"]
        assert act(state(api), "picks.auto")["ready"] is False and "no_running_job" in act(state(api), "picks.auto")["needs"]
        err(api.post("/api/projects/%s/picks/auto" % api.pid, json={"redo": True}), 409, "busy")
    finally:
        release.set()
        wait(api, job_id)


def test_the_docs_know_the_action():
    from bti.editor import state_api
    spec = state_api.SPEC["picks.retry_missing"]
    assert spec.long_job and spec.cost is None and spec.role is None and spec.path.endswith("/picks/retry-missing")
    assert "picks_saved_files" in state_api.NEEDS
    from bti.auto_run import reasons
    assert set(state_api.NEEDS) <= set(reasons.NEED_VI)
