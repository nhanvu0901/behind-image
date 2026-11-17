"""Tiny stdlib HTTP layer: generic User-Agent, polite backoff on 429 and 5xx.

Adapted in spirit from comic-book-pipeline art_pipeline/hunt.py (UA and 429 lessons).
No personal details in any header or URL.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

USER_AGENT = "behind-the-image-media/0.1 (art documentary research tool)"
MAX_TRIES = 4
BASE_DELAY = 2.0
MAX_WAIT = 60.0
_RETRY = {429, 500, 502, 503, 504}


class MediaHTTPError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _retry_after(exc: urllib.error.HTTPError) -> float | None:
    try:
        v = exc.headers.get("Retry-After") if exc.headers else None
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def open_url(url: str, *, timeout: float = 30, tries: int = MAX_TRIES,
             sleep: Callable[[float], None] = time.sleep,
             opener: Callable[..., Any] | None = None,
             headers: dict[str, str] | None = None):
    """Open `url`, retrying 429/5xx with a growing wait (2, 4, 8 s; Retry-After honoured,
    capped), at most `tries` attempts. Returns the response object (a context manager)."""
    opener = opener or urllib.request.urlopen
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
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MediaHTTPError(f"request failed ({exc.__class__.__name__}) for {_short(url)}") from exc
    raise MediaHTTPError(f"gave up after {tries} tries for {_short(url)}")  # pragma: no cover


def _short(url: str) -> str:
    return url if len(url) < 120 else url[:117] + "..."


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
    dest.parent.mkdir(parents=not NO_NEW_PARENTS.get(), exist_ok=True)   # set by the facade with require_root: never re-create a project
    tmp = dest.with_name(dest.name + ".part")
    total = 0
    try:
        with open_url(url, timeout=timeout, **kw) as r, open(tmp, "wb") as fh:
            declared = r.headers.get("Content-Length") if getattr(r, "headers", None) else None
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise MediaHTTPError(f"file is {int(declared)} bytes, over the {max_bytes} byte cap")
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise MediaHTTPError(f"download exceeded the {max_bytes} byte cap")
                fh.write(chunk)
        tmp.replace(dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return dest
