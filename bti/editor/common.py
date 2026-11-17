"""Shared helpers: id validation, safe paths, atomic JSON, revisions.

Atomic JSON write and corrupt-file quarantine follow the pattern of the comic
pipeline (utils/atomic_json.py and ui/bridge.py::_quarantine_corrupt), rewritten
here; nothing is imported from that repo.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
import os
import re
import tempfile
import threading
import time
from itertools import accumulate
from pathlib import Path
from typing import Any

from bti.script.store import ProjectGone, make_parent

PID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
STYLE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
ITEM_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
SCHEMA = "bti.storyboard/1"

REPO_ROOT = Path(__file__).resolve().parents[2]


_ABS_PATH = re.compile(r"(?<![\w:/.~])/(?:[^\s'\",;:()\[\]<>]+/)+([^\s'\",;:()\[\]<>]+)")


def scrub_paths(text: Any) -> Any:
    """A message for the owner never shows a server path: every absolute path (two or more segments) becomes its last
    component. Anything that is not a string is returned unchanged."""
    return _ABS_PATH.sub(r"\1", text) if isinstance(text, str) else text


class ApiError(Exception):
    """Error carried to the client as JSON `{detail, ...extra}`. The detail is scrubbed of server paths (R3B-010)."""

    def __init__(self, status: int, detail: str, **extra: Any):
        detail = scrub_paths(detail)
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.extra = extra


def valid_pid(pid: str) -> bool:
    return isinstance(pid, str) and PID_RE.fullmatch(pid) is not None


MAX_SEGMENT_BYTES = 255            # the file system limit of one name; longer is "not found" without asking the file system
MAX_BODY_DEPTH = 40                # deepest nesting of a JSON request body (checked by `DepthLimitMiddleware`)


def segment_ok(seg: Any) -> bool:
    """A name that can be one path segment: a non-empty string without NUL, at most 255 bytes."""
    if not isinstance(seg, str) or not seg or "\x00" in seg:
        return False
    try:
        return len(seg.encode("utf-8")) <= MAX_SEGMENT_BYTES
    except UnicodeEncodeError:          # a lone surrogate cannot be a file name
        return False


def safe_join(root: Path, rel: str) -> Path:
    """Resolve `rel` under `root`; raise ApiError(404) when it escapes, is malformed, has a segment longer than the
    file system allows, or the file system refuses the look-up (any OSError is "not found", never a 500)."""
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel:
        raise ApiError(404, "not found")
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        raise ApiError(404, "not found")
    parts = rel.split("/")
    if any(p in ("..", "") for p in parts) or not all(segment_ok(p) for p in parts):
        raise ApiError(404, "not found")
    try:
        root_r = root.resolve()
        target = (root_r / rel).resolve()
        target.relative_to(root_r)
    except (ValueError, OSError, RuntimeError):
        raise ApiError(404, "not found")
    return target


# ---------------------------------------------------------------- input helpers: one per kind of value, used by every route
def finite_number(v: Any, name: str, lo: float | None = None, hi: float | None = None, *, integer: bool = False,
                  default: Any = ... ) -> float | int:
    """A finite number (or integer) inside [lo, hi]. ApiError 422 naming `name` for a string, a boolean, null, NaN,
    infinity, a whole number too large for a float, or a value out of range. `default` is returned for None when given."""
    if v is None and default is not ...:
        return default
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ApiError(422, f"{name} must be {'an integer' if integer else 'a number'}")
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ApiError(422, f"{name} must be a finite number")
        if integer:
            if not v.is_integer():
                raise ApiError(422, f"{name} must be an integer")
            v = int(v)
    kind = "an integer" if integer else "a number"
    try:                                               # an int beyond float range compares exactly, never converts
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            if lo is not None and hi is not None:
                raise ApiError(422, f"{name} must be {kind} from {lo} to {hi}")
            raise ApiError(422, f"{name} must be {kind} {'>= ' + str(lo) if lo is not None else '<= ' + str(hi)}")
    except OverflowError:
        raise ApiError(422, f"{name} out of range")
    return v


def string_list(v: Any, name: str, *, max_items: int = 500, max_len: int = 4000, allow_none: bool = True) -> list[str] | None:
    """A list of strings. None is allowed (returns None) unless `allow_none` is false. 422 naming `name` otherwise."""
    if v is None and allow_none:
        return None
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ApiError(422, f"{name} must be a list of strings")
    if len(v) > max_items or any(len(x) > max_len for x in v):
        raise ApiError(422, f"{name} is too long")
    return v


def text_field(body: Any, key: str, required: bool = False, max_len: int = 2_000_000) -> str:
    """A string field of a JSON body ("" when absent and not required)."""
    v = body.get(key) if isinstance(body, dict) else None
    if v is None:
        if required:
            raise ApiError(422, f"{key} (string) is required")
        return ""
    if not isinstance(v, str):
        raise ApiError(422, f"{key} must be a string")
    if len(v) > max_len:
        raise ApiError(422, f"{key} is too long")
    return v


def id_field(v: Any, name: str, rx: re.Pattern, hint: str) -> str:
    """An id that matches `rx` entirely (never coerced, never trimmed)."""
    if not isinstance(v, str) or rx.fullmatch(v) is None:
        raise ApiError(422, f"{name} must be {hint}")
    return v


_DEPTH_SKELETON = re.compile(rb'(?:[^"]++|"(?:[^"\\]++|\\.)*+")*+', re.S)      # whole strings and the text between them, possessive: no backtracking
_DEPTH_STRING = re.compile(rb'"(?:[^"\\]++|\\.)*+"', re.S)
_DEPTH_NOT_BRACKET = bytes(b for b in range(256) if b not in b"[]{}")
_DEPTH_DELTA = [0] * 256
_DEPTH_DELTA[ord("[")] = _DEPTH_DELTA[ord("{")] = 1
_DEPTH_DELTA[ord("]")] = _DEPTH_DELTA[ord("}")] = -1
MAX_JSON_BODY_BYTES = 8 * 1024 * 1024            # a JSON request body over this is refused with 413 before it is parsed
_DEPTH_CHUNK = 256 * 1024


class DepthLimitMiddleware:
    """Pure ASGI middleware: a JSON request body nested deeper than MAX_BODY_DEPTH is answered 422 before any route, parser or
    walker of the product sees it, and a body over MAX_JSON_BODY_BYTES is answered 413.

    The scan is ONE linear pass in C-speed steps (R3B-002): whole strings are matched with possessive quantifiers (no
    backtracking, so an unterminated string cannot make the cost grow with its number of quotes), removed, and the remaining
    brackets are counted. The text after an unterminated string is not scanned (the document is not JSON anyway; the parser
    refuses it). The async path scans one chunk of about 256 KB at a time and yields to the event loop between chunks."""

    def __init__(self, app, limit: int = MAX_BODY_DEPTH, max_bytes: int = MAX_JSON_BODY_BYTES):
        self.app, self.limit, self.max_bytes = app, limit, max_bytes

    def _steps(self, body: bytes):
        """Generator: yields after every chunk, returns True when the nesting depth exceeds the limit."""
        n, pos, depth = len(body), 0, 0
        window = _DEPTH_CHUNK
        while pos < n:
            end = _DEPTH_SKELETON.match(body, pos, min(n, pos + window)).end()
            if end == pos:
                if pos + window >= n:
                    break                   # an unterminated string up to the end of the body
                window *= 2                 # a string longer than the window: widen it (geometric, so still linear)
                continue
            window = _DEPTH_CHUNK
            chunk = _DEPTH_STRING.sub(b"", body[pos:end]).translate(None, _DEPTH_NOT_BRACKET)
            if chunk:
                levels = list(accumulate(map(_DEPTH_DELTA.__getitem__, chunk), initial=depth))
                if max(levels) > self.limit:
                    return True
                depth = levels[-1]
            pos = end
            yield
        return False

    def too_deep(self, body: bytes) -> bool:
        it = self._steps(body)
        while True:
            try:
                next(it)
            except StopIteration as done:
                return bool(done.value)

    async def too_deep_async(self, body: bytes) -> bool:
        it = self._steps(body)
        while True:
            try:
                next(it)
            except StopIteration as done:
                return bool(done.value)
            await asyncio.sleep(0)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        ctype = dict(scope.get("headers") or []).get(b"content-type", b"")
        if b"json" not in ctype.lower():
            return await self.app(scope, receive, send)
        chunks, total, more = [], 0, True
        while more:
            msg = await receive()
            if msg["type"] != "http.request":
                break
            chunks.append(msg.get("body", b""))
            total += len(chunks[-1])
            more = msg.get("more_body", False)
            if total > self.max_bytes:
                payload = json.dumps({"detail": f"the request body is larger than {self.max_bytes // (1024 * 1024)} MB",
                                      "code": "too_large"}).encode()
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]})
                await send({"type": "http.response.body", "body": payload})
                return
        body = b"".join(chunks)
        if await self.too_deep_async(body):
            payload = json.dumps({"detail": f"the request body is nested deeper than {self.limit} levels",
                                  "code": "too_deep"}).encode()
            await send({"type": "http.response.start", "status": 422,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]})
            await send({"type": "http.response.body", "body": payload})
            return
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        await self.app(scope, replay, send)


# ---------------------------------------------------------------- one storyboard lock per project
# See the LOCK ORDER comment in bti/script/store.py: this lock is number 2 (after the script lock, before the engine lock).
_SAVE_LOCKS: dict[str, threading.RLock] = {}
_SAVE_GUARD = threading.Lock()


def save_lock(pdir: Path) -> threading.RLock:
    """The storyboard lock of a project: held by every save, approval, restore, regions edit and proposal apply."""
    key = str(Path(pdir).resolve())
    with _SAVE_GUARD:
        return _SAVE_LOCKS.setdefault(key, threading.RLock())


def forget_save_lock(pdir: Path) -> None:
    with _SAVE_GUARD:
        _SAVE_LOCKS.pop(str(Path(pdir).resolve()), None)


def storyboard_shape_problem(doc: Any) -> str | None:
    """None when `doc` has the shape every route can read (an object; `shots` a list of objects; each `overlays` a list of
    objects), else a short sentence. The engine validates values; this keeps a wrong TYPE from reaching code that expects one."""
    if not isinstance(doc, dict):
        return "the top level must be an object"
    shots = doc.get("shots")
    if shots is None:
        return None
    if not isinstance(shots, list):
        return "shots must be a list"
    for i, sh in enumerate(shots):
        if not isinstance(sh, dict):
            return "shots[%d] must be an object" % i
        ov = sh.get("overlays")
        if ov is not None:
            if not isinstance(ov, list):
                return "shots[%d].overlays must be a list" % i
            for j, o in enumerate(ov):
                if not isinstance(o, dict):
                    return "shots[%d].overlays[%d] must be an object" % (i, j)
    return None


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: Any, levels: int = 1) -> None:
    """Atomic write. At most `levels` missing folders are made, never the project folder itself (ProjectGone)."""
    make_parent(path, levels)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def quarantine(path: Path) -> Path | None:
    """Move a corrupt file aside so it is not re-read; returns the new path."""
    try:
        dest = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
        os.replace(path, dest)
        return dest
    except OSError:
        return None


def strip_derived(obj: Any) -> Any:
    """Deep copy without keys that start with `_`."""
    if isinstance(obj, dict):
        return {k: strip_derived(v) for k, v in obj.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(obj, list):
        return [strip_derived(v) for v in obj]
    return copy.deepcopy(obj)


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def storyboard_approval(sb: Any) -> str:
    """THE one rule for "is the storyboard approved?": "none" (no approval record), "fresh" (the record names the current
    revision) or "stale" (it names another one: the storyboard was edited after it was approved). The pipeline step, the stage
    (`infer_stage`), the home list and the library project index all call this."""
    if not isinstance(sb, dict):
        return "none"
    ap = (sb.get("approvals") or {}).get("storyboard") if isinstance(sb.get("approvals"), dict) else None
    if not ap:
        return "none"
    return "fresh" if isinstance(ap, dict) and ap.get("rev") == compute_rev(sb) else "stale"


def compute_rev(storyboard: dict) -> str:
    """sha256 of the canonical JSON, without `_` keys and without `approvals`
    (approving must not change the revision it approves)."""
    doc = strip_derived(storyboard)
    doc.pop("approvals", None)
    return hashlib.sha256(canonical(doc).encode("utf-8")).hexdigest()


def file_signature(path: Path) -> str:
    st = path.stat()
    return hashlib.sha1(f"{path.name}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")
