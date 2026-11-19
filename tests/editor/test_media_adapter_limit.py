"""Worker sizefollow: the older import path of the storyboard's picture tab (`bti.editor.media_adapter`) says "the source limits
downloads" with the wait the source asked for, instead of one fixed sentence with `retry_after=10`. Same code and body shape as
`bti.picks.service`, so the page shows the same sentence with the minutes (errmsg.js `sourceLimitText`).
Fakes only: the media module is a namespace whose functions raise `MediaHTTPError`; no request leaves the process."""
from __future__ import annotations

import types

import pytest
from fastapi.testclient import TestClient

from bti.editor.app import create_app
from bti.editor.common import ApiError
from bti.editor.media_adapter import _translate
from bti.media.http import MediaHTTPError
from editor_helpers import PID

P = f"/api/projects/{PID}"


def limited(status, retry_after):
    return MediaHTTPError("HTTP %s for https://example.invalid/x" % status, status, retry_after=retry_after)


# ------------------------------------------------------------------------------------------------- the translation
@pytest.mark.parametrize("status,wait", [(429, 600), (429, 3), (429, 3600), (503, 120)])
def test_a_rate_limit_with_a_wait_is_answered_503_with_its_own_code_and_the_real_wait(status, wait):
    e = _translate(limited(status, wait))
    assert isinstance(e, ApiError) and e.status == 503
    assert e.extra == {"code": "source_rate_limited", "retryable": True, "retry_after": wait}


def test_a_rate_limit_that_gave_no_time_says_so_with_a_null_wait_not_ten_seconds():
    e = _translate(limited(429, None))
    assert e.status == 503 and e.extra["code"] == "source_rate_limited" and e.extra["retry_after"] is None and e.extra["retryable"] is True


def test_the_wait_is_whole_seconds_as_the_media_layer_rounds_it():
    assert _translate(limited(429, 90.2)).extra["retry_after"] == 91            # MediaHTTPError rounds up; the adapter passes it on


@pytest.mark.parametrize("status", [503, 502, 504, None])
def test_the_other_unavailable_answers_keep_today_s_sentence_and_ten_seconds(status):
    e = _translate(MediaHTTPError("HTTP %s" % status, status))
    assert not e.extra.get("code")                                              # a 503 with no time is not called a rate limit
    assert e.status == 503 and e.extra == {"retryable": True, "retry_after": 10}
    assert "Nguồn ảnh đang giới hạn tốc độ hoặc không phản hồi" in e.detail


def test_other_statuses_keep_today_s_answer():
    e = _translate(MediaHTTPError("HTTP 403 forbidden", 403))
    assert e.status == 502 and e.detail.startswith("media source error (HTTP 403)") and e.extra == {}
    e = _translate(MediaHTTPError("HTTP 404", 404))
    assert e.status == 502


def test_an_error_that_is_not_a_media_error_is_untouched_by_the_new_branch():
    class NotFound(Exception):
        pass
    assert _translate(NotFound("gone")).status == 404
    assert _translate(RuntimeError("boom")).status == 502


# ------------------------------------------------------------------------------------------------- through the routes
@pytest.fixture()
def client(root):
    def imp(d, s, i, **kw):
        raise limited(429, 600)

    def se(q, source="commons", kind="image", limit=24):
        if source == "pexels":
            raise limited(503, None)
        if source == "met":
            raise limited(429, None)
        raise limited(429, 301)
    mod = types.SimpleNamespace(search=se, import_candidate=imp, add_upload=lambda *a, **k: None)
    with TestClient(create_app(root, engine_module=None, media_module=mod)) as c:
        yield c


def test_the_import_route_answers_with_the_code_and_the_wait(client):
    r = client.post(f"{P}/assets/import", json={"source": "commons", "source_id": "x"})
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "source_rate_limited" and body["retry_after"] == 600 and body["retryable"] is True


def test_the_search_route_answers_with_the_code_and_the_wait(client):
    r = client.get("/api/media/search", params={"q": "mirror", "source": "commons"})
    assert r.status_code == 503 and r.json()["code"] == "source_rate_limited" and r.json()["retry_after"] == 301
    r = client.get("/api/media/search", params={"q": "mirror", "source": "met"})
    assert r.status_code == 503 and r.json()["code"] == "source_rate_limited" and r.json()["retry_after"] is None
    r = client.get("/api/media/search", params={"q": "mirror", "source": "pexels"})          # 503 with no time: today's answer
    assert r.status_code == 503 and r.json()["code"] != "source_rate_limited" and r.json()["retry_after"] == 10
