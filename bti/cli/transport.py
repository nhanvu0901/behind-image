"""How the command talks to the app: one `request` call that answers a `Reply`. The tests swap the transport (the app in the test process, or a script
of answers); the real one is `HttpTransport` (urllib, the standard library; no proxy: the app is on this machine)."""
from __future__ import annotations

import http.client
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_URL = "http://127.0.0.1:8560"


class Unreachable(Exception):
    """Nothing answered, or the connection broke."""


@dataclass
class Reply:
    status: int
    data: Any = None            # the decoded JSON, or None when the body was not JSON
    text: str = ""              # the body as text when it was not JSON

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class Transport:
    def request(self, method: str, path: str, body: Any = None, timeout: float = 60.0) -> Reply:       # pragma: no cover - the interface
        raise NotImplementedError


class HttpTransport(Transport):
    def __init__(self, base: str | None = None):
        base = (base or DEFAULT_URL).strip().rstrip("/")
        if urllib.parse.urlsplit(base).scheme not in ("http", "https") or not urllib.parse.urlsplit(base).netloc:
            raise ValueError("the app's address must start with http:// or https://")
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, method: str, path: str, body: Any = None, timeout: float = 60.0) -> Reply:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Accept": "application/json", **({"Content-Type": "application/json"} if data is not None else {})})
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                return _reply(resp.status, resp.read())
        except urllib.error.HTTPError as e:
            return _reply(e.code, e.read())
        except (urllib.error.URLError, socket.timeout, http.client.HTTPException, ConnectionError, OSError) as e:
            raise Unreachable(str(getattr(e, "reason", None) or e)[:200])


def _reply(status: int, raw: bytes) -> Reply:
    text = raw.decode("utf-8", errors="replace")
    try:
        return Reply(status, json.loads(text) if text.strip() else None, "")
    except ValueError:
        return Reply(status, None, text[:2000])
