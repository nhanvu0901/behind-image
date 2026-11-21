"""Tiny stdlib HTTP layer: one generic User-Agent, a polite client when a source says "too many requests".

Adapted in spirit from comic-book-pipeline art_pipeline/hunt.py (UA and 429 lessons).

Privacy rule of the owner: NO request of the app to an outside service carries this project's name, a repository address, a person's name, an
e-mail address or an account name, in a header, in a query or in a body. `USER_AGENT` is the one client string of every request the app makes
itself (Wikimedia Commons, Wikipedia, the Met, Pexels, Pixabay, OpenStreetMap, You.com, the download of a picture from the web, thumbnails); a
source that builds its own headers takes it from here and never writes a string of its own (`tests/media/test_privacy.py` pins both).

HTTP 429 (and 503 that carries `Retry-After`) means "stop asking": this layer waits and tries once more only when the source
asks for a few seconds (`SHORT_RETRY_AFTER`); otherwise it fails at once with a `MediaHTTPError` that has `rate_limited` and
`retry_after` (seconds, None when the source gave no time), and it sends nothing more to that host until the time the source
named has passed (`_COOLDOWN`). Other 5xx answers and timeouts keep the growing backoff (2, 4, 8 s) up to `tries` attempts.

A DOWNLOAD of a picture (the import path of `bti.media.api`, run under `polite()`) is politer and more patient than a search: no two requests go to
the same host (for Wikimedia: the same service, `commons.`, `upload.`, `en.wikipedia.org` ...) less than `PACE_INTERVAL` (one second) apart, and
a 429 (or a 503 that carries `Retry-After`) is waited out: the time the host asks, else 10 s, then 30 s, then 90 s, and the request is sent again, three
times in all (`PATIENT_WAITS`); a host that asks for more than `PATIENT_MAX_WAIT` is not waited for (the error carries its time, as before).
"""
from __future__ import annotations

import contextvars
import email.utils
import json
import math
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable
from bti.fsio import atomic_replace
from .safety import refuse_if_real_models_off

# What the sources' own rules ask for at the least: a descriptive client name (the default of the standard library is refused by some of them)
# and nothing that names the owner or the project.
USER_AGENT = "ImageResearch/1.0 (art documentary research; generic client)"
MAX_TRIES = 4
BASE_DELAY = 2.0
MAX_WAIT = 60.0
SHORT_RETRY_AFTER = 5.0           # "a few seconds": a longer Retry-After is not waited out inside one request
MAX_COOLDOWN = 3600.0             # the longest a source's own "wait" is honoured locally (a silly value must not lock a host for ever)
PACE_INTERVAL = 1.0               # a polite request: at least this many seconds after the last one to the same host (service)
PATIENT_WAITS = (10.0, 30.0, 90.0)  # a polite request that is answered "too many requests" with no time: the waits before the three new tries
PATIENT_MAX_WAIT = 120.0          # a host that asks for longer than this is not waited for (the caller reports its time and goes on)
_RETRY = {500, 502, 504}          # transient server answers: growing backoff
_LIMITED = {429, 503}             # "too many requests" / "come back later": one short honoured retry, else fail at once

_now = time.monotonic             # tests replace it
_COOLDOWN: dict[str, tuple[float, int]] = {}      # host -> (monotonic time until which the source asked us to wait, status)
POLITE: contextvars.ContextVar = contextvars.ContextVar("bti_media_polite", default=False)   # set by `polite()`: paced requests (one a second per host)
PATIENT: contextvars.ContextVar = contextvars.ContextVar("bti_media_patient", default=False)  # set by `polite()`: "too many requests" is waited out
_PACE_LOCK = threading.Lock()
_PACE_LAST: dict[str, float] = {}                 # host key -> monotonic time of the last polite request to it


class MediaHTTPError(RuntimeError):
    """A request that failed. `status` is the HTTP status when there was one. `retry_after`: seconds the source asked us to
    wait (429 or 503 with `Retry-After`), None when it gave no time. `rate_limited`: the source said "too many requests"."""

    def __init__(self, message: str, status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = None if retry_after is None else int(math.ceil(max(0.0, retry_after)))

    @property
    def rate_limited(self) -> bool:
        return self.status == 429 or (self.status == 503 and self.retry_after is not None)


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
                if dt.tzinfo is None:                       # an HTTP date is GMT
                    dt = dt.replace(tzinfo=timezone.utc)
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


def reset_cooldowns() -> None:
    """Forget every "wait until" a source asked for (tests, and a restart-like reset)."""
    _COOLDOWN.clear()


def reset_pacing() -> None:
    """Forget when the last polite request to each host went out (tests)."""
    with _PACE_LOCK:
        _PACE_LAST.clear()


def host_key(url: str) -> str:
    """The host a request is paced by. Wikimedia's hosts (`commons.`, `upload.`, `en.wikipedia.org` ...) are ONE service with one rule ("about one request a
    second"), so they share one key; any other host is its own."""
    host = _host(url).lower()
    for service in ("wikimedia.org", "wikipedia.org"):
        if host == service or host.endswith("." + service):
            return "wikimedia"
    return host


def pace(url: str, *, sleep: Callable[[float], None] = time.sleep, interval: float = PACE_INTERVAL, clock: Callable[[], float] | None = None) -> None:
    """Wait (with `sleep`) so that two requests to the same host (see `host_key`) are at least `interval` seconds apart, whoever makes them; then count this
    one. The lock is held while waiting: concurrent callers queue up, which is the point."""
    now_fn = clock or _now
    key = host_key(url)
    with _PACE_LOCK:
        now = now_fn()
        last = _PACE_LAST.get(key)
        if last is not None and 0 <= now - last < interval:
            sleep(interval - (now - last))
            now = now_fn()
        _PACE_LAST[key] = now


@contextmanager
def polite():
    """Inside this block every request that goes through `open_url` is paced (one a second per host) and patient (a 429 is waited out, see the module's
    words). Used by the import path of `bti.media.api` (the downloads of pictures); searches are not polite, they fail fast and say when to come back."""
    t1, t2 = POLITE.set(True), PATIENT.set(True)
    try:
        yield
    finally:
        PATIENT.reset(t2)
        POLITE.reset(t1)


@contextmanager
def hasty():
    """Inside a `polite()` block: do not wait out "too many requests" for the requests of this block (they are still paced). For a request that has a way
    round (Commons: a refused original has a rendition to fall back on), where waiting would only delay the other way."""
    token = PATIENT.set(False)
    try:
        yield
    finally:
        PATIENT.reset(token)


def _cooldown_check(url: str, wait_out: Callable[[float], None] | None = None) -> None:
    """Send nothing to a host that said "wait N seconds" while those seconds are not over. A polite caller (`wait_out` is its `sleep`) waits those seconds
    out when they are not more than `PATIENT_MAX_WAIT`, then goes on."""
    host = _host(url)
    until = _COOLDOWN.get(host)
    if until is None:
        return
    left = until[0] - _now()
    if left <= 0:
        _COOLDOWN.pop(host, None)
        return
    if wait_out is not None and left <= PATIENT_MAX_WAIT:
        wait_out(left)
        _COOLDOWN.pop(host, None)
        return
    raise MediaHTTPError(f"HTTP {until[1]} for {_short(url)}: the source asked us to wait, {int(math.ceil(left))} s left",
                         until[1], retry_after=left)


def _limited(url: str, status: int, wait: float | None) -> MediaHTTPError:
    """The error of an answer that said "too many requests"; remembers the wait so no request goes out meanwhile."""
    if wait is not None and wait > 0:
        _COOLDOWN[_host(url)] = (_now() + min(wait, MAX_COOLDOWN), status)
    extra = f" (retry after {int(math.ceil(wait))} s)" if wait is not None else ""
    return MediaHTTPError(f"HTTP {status} for {_short(url)}{extra}", status, retry_after=wait)


def open_url(url: str, *, timeout: float = 30, tries: int = MAX_TRIES,
             sleep: Callable[[float], None] = time.sleep,
             opener: Callable[..., Any] | None = None,
             headers: dict[str, str] | None = None):
    """Open `url` and return the response object (a context manager).

    HTTP 429, and 503, are answers that say "too many requests": with a `Retry-After` of at most `SHORT_RETRY_AFTER` seconds
    this waits that long and tries ONCE more; in every other case (no `Retry-After`, a longer one, or a second refusal) it
    raises `MediaHTTPError` at once, with `retry_after` set when the source gave a time, and the host is left alone until
    that time has passed. 500, 502, 504 and timeouts are retried with a growing wait (2, 4, 8 s; `Retry-After` honoured,
    capped) up to `tries` attempts.

    Under `polite()` (a download of a picture) the request is also paced (see `pace`) and a "too many requests" is waited out: the `Retry-After` time,
    else `PATIENT_WAITS` (10, 30, 90 s), and the request is sent again, three times; a time of more than `PATIENT_MAX_WAIT` is not waited for."""
    if opener is None:                                   # no injected transport: this would be a real request (A7 safety switch)
        refuse_if_real_models_off(f"network request to {_host(url)}")
        opener = urllib.request.urlopen
    paced, patient = POLITE.get(), PATIENT.get()
    _cooldown_check(url, sleep if patient else None)
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*", **(headers or {})}
    delay = BASE_DELAY
    attempt = 0
    limited_retried = False
    patience = 0                                         # how many times a polite request waited out "too many requests"
    while True:
        attempt += 1
        if paced:
            pace(url, sleep=sleep)
        req = urllib.request.Request(url, headers=hdrs)
        try:
            return opener(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in _LIMITED:
                wait = _retry_after(exc)
                if patient:
                    if (exc.code == 429 or wait is not None) and patience < len(PATIENT_WAITS):
                        pause = wait if wait is not None else PATIENT_WAITS[patience]
                        if pause <= PATIENT_MAX_WAIT:
                            patience += 1
                            attempt -= 1                 # a patient wait is not one of the `tries` of the 5xx / timeout backoff
                            sleep(pause)                 # what the host asked for (else 10, 30, 90 s), then the same request again
                            continue
                elif wait is not None and wait <= SHORT_RETRY_AFTER and not limited_retried:
                    limited_retried = True
                    sleep(wait)
                    continue
                if exc.code == 429 or wait is not None:
                    raise _limited(url, exc.code, wait) from exc
                raise MediaHTTPError(f"HTTP {exc.code} for {_short(url)}", exc.code) from exc     # 503 with no time: not retried either
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
                raise MediaHTTPError(f"timed out after {attempt} tries for {_short(url)}") from exc
            if isinstance(exc, (urllib.error.URLError, TimeoutError, OSError)):
                raise MediaHTTPError(f"request failed ({exc.__class__.__name__}) for {_short(url)}") from exc
            raise


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
