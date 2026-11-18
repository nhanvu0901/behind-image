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


def test_retry_after_numeric_seconds():
    waits = []
    hdrs = {"Retry-After": "7"}
    err = urllib.error.HTTPError("https://example.org/test", 429, "rate limited", hdrs, None)
    calls = {"n": 0}

    def opener(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise err
        class Dummy:
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return Dummy()

    open_url("https://example.org/test", sleep=waits.append, opener=opener)
    assert calls["n"] == 2
    assert waits == [7.0]


def test_retry_after_http_date():
    waits = []
    future = datetime.now(timezone.utc) + timedelta(seconds=12)
    hdrs = {"Retry-After": format_datetime(future)}
    err = urllib.error.HTTPError("https://example.org/test", 503, "busy", hdrs, None)
    calls = {"n": 0}

    def opener(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise err
        class Dummy:
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return Dummy()

    open_url("https://example.org/test", sleep=waits.append, opener=opener)
    assert calls["n"] == 2
    assert len(waits) == 1
    # Should be around 11-13 seconds
    assert 10.0 <= waits[0] <= 14.0
