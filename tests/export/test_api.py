import json
import os

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from bti.editor import export_api
from bti.editor.common import ApiError
from bti.export import run
from conftest import approve


@pytest.fixture()
def client(project, patch_run):
    app = FastAPI()
    app.state.projects_root = project.parent

    @app.exception_handler(ApiError)
    async def _e(_, e):
        return JSONResponse({"detail": e.detail, **e.extra}, status_code=e.status)

    app.include_router(export_api.router)
    with TestClient(app) as c:
        yield c


def test_get_before_export(client):
    j = client.get("/api/projects/arnolfini/export").json()
    assert j["state"] == "none" and j["blocked"] is None and j["plan"]["parts"] >= 3 and j["files"] == [] and j["manifest"] is None


def test_blocked_when_not_approved(client, project):
    sb = json.loads((project / "storyboard.json").read_text())
    sb["approvals"] = {"storyboard": None}
    (project / "storyboard.json").write_text(json.dumps(sb))
    j = client.get("/api/projects/arnolfini/export").json()
    assert j["blocked"]["code"] == "not_approved" and j["plan"] is None
    r = client.post("/api/projects/arnolfini/export/start")
    assert r.status_code == 409 and r.json()["code"] == "not_approved"


def test_start_then_everything_is_served(client):
    r = client.post("/api/projects/arnolfini/export/start")
    assert r.status_code == 200 and r.json()["job_id"]
    j = client.get("/api/projects/arnolfini/export").json()
    assert j["state"] == "done"
    assert [f["key"] for f in j["files"]] == ["video", "subtitles", "description", "chapters"]
    assert "Chapters:" in j["description"] and j["manifest"]["report_status"] == "ok"
    url = next(f["url"] for f in j["files"] if f["key"] == "video")
    full = client.get(url)
    assert full.status_code == 200 and full.headers["accept-ranges"] == "bytes" and full.headers["content-type"].startswith("video/mp4")
    body = full.content
    r = client.get(url, headers={"Range": "bytes=0-9"})
    assert r.status_code == 206 and r.content == body[:10] and r.headers["content-range"] == "bytes 0-9/%d" % len(body)
    r = client.get(url, headers={"Range": "bytes=-5"})
    assert r.status_code == 206 and r.content == body[-5:]
    r = client.get(url, headers={"Range": "bytes=%d-" % (len(body) - 3)})
    assert r.content == body[-3:]
    assert client.get(url, headers={"Range": "bytes=%d-" % (len(body) + 5)}).status_code == 416
    h = client.head(url)
    assert h.status_code == 200 and int(h.headers["content-length"]) == len(body) and h.content == b""
    assert "attachment" in client.get(url + "?download=1").headers["content-disposition"]
    srt = client.get(url.replace("arnolfini.mp4", "arnolfini.srt"))
    assert srt.headers["content-type"].startswith("application/x-subrip") and "-->" in srt.text


def test_second_start_while_the_manager_says_busy(client, manager):
    manager.running.add(("arnolfini", "export"))
    r = client.post("/api/projects/arnolfini/export/start")
    assert r.status_code == 409 and r.json()["code"] == "busy"


@pytest.mark.parametrize("name", ["a/b", "%2e%2e", "..%2fproject.json", "nope.mp4", ".hidden", "x" * 300, "export.json%00"])
def test_file_names_that_leave_or_do_not_exist_are_404(client, name):
    client.post("/api/projects/arnolfini/export/start")
    assert client.get("/api/projects/arnolfini/export/files/" + name).status_code == 404


def test_symlink_in_the_export_folder_is_not_followed(client, project):
    client.post("/api/projects/arnolfini/export/start")
    link = project / "export" / "evil.txt"
    try:
        os.symlink(project / "project.json", link)
    except (OSError, NotImplementedError):
        pytest.skip("no symlinks here")
    assert client.get("/api/projects/arnolfini/export/files/evil.txt").status_code == 404


def test_unknown_or_bad_project(client):
    assert client.get("/api/projects/nope/export").status_code == 404
    assert client.get("/api/projects/..%2f/export").status_code in (404, 422)
    assert client.get("/api/projects/nope/export/files/x.mp4").status_code == 404


@pytest.mark.parametrize("hdr,size,want", [(None, 10, None), ("bytes=0-4", 10, (0, 4)), ("bytes=5-", 10, (5, 9)), ("bytes=-3", 10, (7, 9)), ("bytes=0-99", 10, (0, 9)),
                                           ("bytes=0-1,4-5", 10, None), ("items=1-2", 10, None), ("bytes=-", 10, None), ("bytes=-99", 10, (0, 9))])
def test_parse_range(hdr, size, want):
    assert export_api.parse_range(hdr, size) == want


@pytest.mark.parametrize("hdr,size", [("bytes=10-", 10), ("bytes=5-2", 10), ("bytes=-0", 10), ("bytes=0-0", 0)])
def test_parse_range_unsatisfiable(hdr, size):
    with pytest.raises(export_api.RangeNotSatisfiable):
        export_api.parse_range(hdr, size)
