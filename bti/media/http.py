"""Tiny stdlib HTTP layer: generic User-Agent, polite backoff on 429 and 5xx.

Adapted in spirit from comic-book-pipeline art_pipeline/hunt.py (UA and 429 lessons).
No personal details in any header or URL.
"""
from __future__ import annotations

import email.utils
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable
from bti.fsio import atomic_replace
from .safety import refuse_if_real_models_off

USER_AGENT = "behind-the-image-media/0.1 (art documentary research tool)"
MAX_TRIES = 4
BASE_DELAY = 2.0
MAX_WAIT = 60.0
_RETRY = {429, 500, 502, 503, 504}


class MediaHTTPError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class FileTooLarge(ValueError, MediaHTTPError):
    def __init__(self, message: str = "file too large", status: int = 413, code: str = "too_large"):
        ValueError.__init__(self, message)
        MediaHTTPError.__init__(self, message, status)
        self.code = code
        self.status = status


def _retry_after(exc: urllib.error.HTTPError) -> float | None:
    try:
        v = exc.headers.get("Retry-After") if exc.headers else None
        if v is None:
            return None
        try:
            return max(0.0, float(v))
        except ValueError:
            dt = email.utils.parsedate_to_datetime(v)
            if dt is not None:
                now = datetime.now(timezone.utc)
                diff = (dt - now).total_seconds()
                return max(0.0, diff)
            return None
    except Exception:
        return None


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return True
        if "timed out" in str(reason).lower():
            return True
    return False


def open_url(url: str, *, timeout: float = 30, tries: int = MAX_TRIES,
             sleep: Callable[[float], None] = time.sleep,
             opener: Callable[..., Any] | None = None,
             headers: dict[str, str] | None = None):
    """Open `url`, retrying 429/5xx and timeouts with a growing wait (2, 4, 8 s; Retry-After
    honoured, capped), at most `tries` attempts. Returns the response object (a context manager)."""
    if opener is None:                                   # no injected transport: this would be a real request (A7 safety switch)
        refuse_if_real_models_off(f"network request to {_host(url)}")
        opener = urllib.request.urlopen
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*", **(headers or {})}
    delay = BASE_DELAY
    for attempt in range(1, tries + 1):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            return opener(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in _RETRY and attempt < tries:
                sleep(min(_retry_after(exc) or delay, MAX_WAIT))
                delay *= 2
                continue
            raise MediaHTTPError(f"HTTP {exc.code} for {_short(url)}", exc.code) from exc
        except Exception as exc:
            if _is_timeout(exc) and attempt < tries:
                sleep(min(delay, MAX_WAIT))
                delay *= 2
                continue
            if _is_timeout(exc):
                raise MediaHTTPError(f"timed out after {tries} tries for {_short(url)}") from exc
            if isinstance(exc, (urllib.error.URLError, TimeoutError, OSError)):
                raise MediaHTTPError(f"request failed ({exc.__class__.__name__}) for {_short(url)}") from exc
            raise
    raise MediaHTTPError(f"gave up after {tries} tries for {_short(url)}")  # pragma: no cover


_SECRET_PARAM = re.compile(r"([?&](?:key|api_key|apikey|token)=)[^&#\s]*", re.I)


def _short(url: str) -> str:
    url = _SECRET_PARAM.sub(r"\1***", url)               # Pixabay takes its key in the query: it must never reach a message
    return url if len(url) < 120 else url[:117] + "..."


def _host(url: str) -> str:
    """Only the host, for a refusal message: a query string may carry a key."""
    return urllib.parse.urlparse(url).hostname or "?"


def get_json(url: str, params: dict[str, Any] | None = None, **kw) -> Any:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    with open_url(url, headers={"Accept": "application/json"}, **kw) as r:
        body = r.read()
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as exc:
        raise MediaHTTPError(f"response was not JSON for {_short(url)}") from exc


import contextvars
NO_NEW_PARENTS: contextvars.ContextVar = contextvars.ContextVar("bti_media_no_new_parents", default=False)


def download_file(url: str, dest, *, max_bytes: int, timeout: float = 120, **kw):
    """Stream `url` to `dest` (via a .part file), refusing more than `max_bytes`."""
    from pathlib import Path
    dest = Path(dest)
    if kw.get("opener") is None:                         # refuse before anything is created (open_url below checks again)
        refuse_if_real_models_off(f"download from {_host(url)}")
    dest.parent.mkdir(parents=not NO_NEW_PARENTS.get(), exist_ok=True)   # set by the facade with require_root: never re-create a project
    tmp = dest.with_name(dest.name + ".part")
    total = 0
    try:
        with open_url(url, timeout=timeout, **kw) as r, open(tmp, "wb") as fh:
            declared = r.headers.get("Content-Length") if getattr(r, "headers", None) else None
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise FileTooLarge(f"file is {int(declared)} bytes, over the {max_bytes} byte cap")
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise FileTooLarge(f"download exceeded the {max_bytes} byte cap")
                fh.write(chunk)
        atomic_replace(tmp, dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return dest
