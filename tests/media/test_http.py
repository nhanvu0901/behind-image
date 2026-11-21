import socket
import time
import urllib.error
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
import pytest

from bti.media import http
from bti.media.http import FileTooLarge, MediaHTTPError, open_url, download_file


def test_file_too_large_is_value_error_and_media_http_error():
    err = FileTooLarge("file too large: 65 MB", code="too_large")
    assert isinstance(err, ValueError)
    assert isinstance(err, MediaHTTPError)
    assert err.code == "too_large"
    assert err.status == 413
    assert "65 MB" in str(err)


def test_timeout_retries_four_times_with_backoff():
    waits = []
    calls = {"n": 0}

    def opener(req, timeout=None):
        calls["n"] += 1
        raise TimeoutError("timed out")

    with pytest.raises(MediaHTTPError):
        open_url("https://example.org/test", timeout=1, tries=4, sleep=waits.append, opener=opener)

    assert calls["n"] == 4
    assert waits == [2.0, 4.0, 8.0]


def test_timeout_recovers_after_retry():
    calls = {"n": 0}

    class DummyResp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    def opener(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("timed out")
        return DummyResp()

    waits = []
    res = open_url("https://example.org/test", timeout=1, sleep=waits.append, opener=opener)
    assert calls["n"] == 2
    assert waits == [2.0]
    assert isinstance(res, DummyResp)


def test_urllib_timeout_is_retried():
    calls = {"n": 0}

    def opener(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.URLError(socket.timeout("The read operation timed out"))

    waits = []
    with pytest.raises(MediaHTTPError):
        open_url("https://example.org/test", timeout=1, tries=3, sleep=waits.append, opener=opener)

    assert calls["n"] == 3
    assert waits == [2.0, 4.0]


class _Dummy:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def _limited(code, retry_after=None, url="https://example.org/test"):
    hdrs = {} if retry_after is None else {"Retry-After": str(retry_after)}
    return urllib.error.HTTPError(url, code, "limited", hdrs, None)


def _opener(*answers):
    """An opener that raises or returns each answer in turn; `calls` counts the requests that went out."""
    seq = list(answers)
    calls = {"n": 0}

    def opener(req, timeout=None):
        calls["n"] += 1
        a = seq.pop(0)
        if isinstance(a, BaseException):
            raise a
        return a
    opener.calls = calls
    return opener


def test_429_with_a_short_retry_after_is_retried_once_after_that_wait():
    waits = []
    op = _opener(_limited(429, 3), _Dummy())
    assert isinstance(open_url("https://example.org/test", sleep=waits.append, opener=op), _Dummy)
    assert op.calls["n"] == 2 and waits == [3.0]


def test_a_second_refusal_after_the_one_retry_fails_at_once_with_the_time():
    waits = []
    op = _opener(_limited(429, 2), _limited(429, 4), _Dummy())
    with pytest.raises(MediaHTTPError) as ei:
        open_url("https://example.org/test", sleep=waits.append, opener=op)
    assert op.calls["n"] == 2 and waits == [2.0]               # never a third request
    assert ei.value.status == 429 and ei.value.rate_limited and ei.value.retry_after == 4


def test_429_with_a_long_retry_after_fails_at_once_without_waiting():
    waits = []
    op = _opener(_limited(429, 7), _Dummy())                    # 7 s is more than "a few seconds"
    with pytest.raises(MediaHTTPError) as ei:
        open_url("https://example.org/test", sleep=waits.append, opener=op)
    assert op.calls["n"] == 1 and waits == []
    assert ei.value.status == 429 and ei.value.rate_limited and ei.value.retry_after == 7


def test_429_with_retry_after_of_minutes_carries_the_seconds():
    op = _opener(_limited(429, 600))
    with pytest.raises(MediaHTTPError) as ei:
        open_url("https://example.org/test", sleep=lambda s: None, opener=op)
    assert ei.value.retry_after == 600 and "600" in str(ei.value) and op.calls["n"] == 1


def test_429_without_retry_after_fails_at_once_and_says_no_time():
    waits = []
    op = _opener(_limited(429), _Dummy())
    with pytest.raises(MediaHTTPError) as ei:
        open_url("https://example.org/test", sleep=waits.append, opener=op)
    assert op.calls["n"] == 1 and waits == []
    assert ei.value.status == 429 and ei.value.rate_limited and ei.value.retry_after is None


def test_503_with_retry_after_as_an_http_date():
    future = datetime.now(timezone.utc) + timedelta(seconds=12)
    err = urllib.error.HTTPError("https://example.org/test", 503, "busy", {"Retry-After": format_datetime(future)}, None)
    waits = []
    op = _opener(err, _Dummy())
    with pytest.raises(MediaHTTPError) as ei:                   # 12 s is not a short wait
        open_url("https://example.org/test", sleep=waits.append, opener=op)
    assert op.calls["n"] == 1 and waits == []
    assert ei.value.status == 503 and ei.value.rate_limited and 11 <= ei.value.retry_after <= 13


def test_503_with_a_short_retry_after_is_retried_once():
    waits = []
    op = _opener(_limited(503, 1), _Dummy())
    open_url("https://example.org/test", sleep=waits.append, opener=op)
    assert op.calls["n"] == 2 and waits == [1.0]


def test_503_without_retry_after_is_not_retried_and_is_not_called_a_rate_limit():
    waits = []
    op = _opener(_limited(503), _Dummy())
    with pytest.raises(MediaHTTPError) as ei:
        open_url("https://example.org/test", sleep=waits.append, opener=op)
    assert op.calls["n"] == 1 and waits == []
    assert ei.value.status == 503 and ei.value.retry_after is None and not ei.value.rate_limited


def test_500_and_502_keep_the_growing_backoff():
    waits = []
    op = _opener(_limited(500), _limited(502), _Dummy())
    open_url("https://example.org/test", sleep=waits.append, opener=op)
    assert op.calls["n"] == 3 and waits == [2.0, 4.0]


def test_a_host_that_said_wait_is_left_alone_until_the_time_has_passed(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(http, "_now", lambda: clock["t"])
    op = _opener(_limited(429, 120), _Dummy())
    with pytest.raises(MediaHTTPError):
        open_url("https://upload.example.org/a.jpg", sleep=lambda s: None, opener=op)
    assert op.calls["n"] == 1
    clock["t"] += 30                                             # 90 s are left: nothing is sent
    with pytest.raises(MediaHTTPError) as ei:
        open_url("https://upload.example.org/b.jpg", sleep=lambda s: None, opener=op)
    assert op.calls["n"] == 1 and ei.value.status == 429 and ei.value.rate_limited and ei.value.retry_after == 90
    assert open_url("https://other.example.org/c.jpg", sleep=lambda s: None, opener=_opener(_Dummy())) is not None   # another host
    clock["t"] += 91                                             # the time is over
    assert isinstance(open_url("https://upload.example.org/b.jpg", sleep=lambda s: None, opener=op), _Dummy)
    assert op.calls["n"] == 2


def test_a_429_without_a_time_starts_no_cooldown():
    op = _opener(_limited(429), _Dummy())
    with pytest.raises(MediaHTTPError):
        open_url("https://example.org/a", sleep=lambda s: None, opener=op)
    assert isinstance(open_url("https://example.org/b", sleep=lambda s: None, opener=op), _Dummy)     # the next request goes out


def test_a_silly_retry_after_does_not_lock_a_host_for_ever(monkeypatch):
    clock = {"t": 0.0}
    monkeypatch.setattr(http, "_now", lambda: clock["t"])
    op = _opener(_limited(429, 10 ** 9), _Dummy())
    with pytest.raises(MediaHTTPError):
        open_url("https://example.org/a", sleep=lambda s: None, opener=op)
    clock["t"] += http.MAX_COOLDOWN + 1
    assert isinstance(open_url("https://example.org/b", sleep=lambda s: None, opener=op), _Dummy)


def test_download_of_a_refused_file_leaves_nothing_behind(tmp_path):
    dest = tmp_path / "media" / "a.jpg"
    op = _opener(_limited(429, 300))
    with pytest.raises(MediaHTTPError) as ei:
        download_file("https://example.org/a.jpg", dest, max_bytes=1000, opener=op, sleep=lambda s: None)
    assert ei.value.retry_after == 300 and op.calls["n"] == 1
    assert not dest.exists() and not list(dest.parent.glob("*.part"))


def test_the_user_agent_names_the_client_and_nothing_personal():
    seen = {}

    def opener(req, timeout=None):
        seen.update({k.lower(): v for k, v in req.header_items()})
        return _Dummy()

    open_url("https://example.org/a", opener=opener)
    ua = seen["user-agent"]
    assert ua == http.USER_AGENT and ua.startswith("ImageResearch/")
    low = ua.lower()
    assert "@" not in ua and "http" not in low and "nhanvu" not in low and "mailto" not in low
    assert "behind" not in low and "bti" not in low and "github" not in low                      # nothing that names the project or its repository


def test_error_messages_never_carry_a_key_from_the_query():
    """Pixabay takes its key in the query string; a failing request must not put it into the message."""
    def opener(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    with pytest.raises(MediaHTTPError) as e:
        open_url("https://pixabay.com/api/?key=SECRET-KEY-123&q=rocks", sleep=lambda s: None, opener=opener)
    assert "SECRET-KEY-123" not in str(e.value) and "q=rocks" in str(e.value) and e.value.status == 403
