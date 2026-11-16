"""Model providers: one function each, `complete(spec, system, user, *, timeout, on_progress, cancel) -> text`.

`spec` is an entry of config/models.json. Providers read their key through bti.script.env and never return or log it.
"""
from __future__ import annotations

import threading
from typing import Callable

import httpx


class ProviderError(Exception):
    """kind: auth | rate_limit | timeout | http | empty | blocked | cancelled | config"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


_transport: httpx.BaseTransport | None = None


def set_transport(t: httpx.BaseTransport | None) -> None:
    """Tests install an httpx.MockTransport here; nothing else touches the network layer."""
    global _transport
    _transport = t


def http_client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(timeout, connect=min(20.0, timeout)), transport=_transport)


def check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise ProviderError("cancelled", "cancelled")


def classify_status(status: int, body: str, key_names: tuple[str, ...]) -> ProviderError:
    from ..env import redact
    snippet = redact(body[:300].replace("\n", " "), *key_names)
    if status in (401, 403):
        return ProviderError("auth", f"the provider refused the key (HTTP {status}); check the key and its permissions")
    if status == 429:
        return ProviderError("rate_limit", "rate limit or quota reached (HTTP 429)")
    if status in (408, 504):
        return ProviderError("timeout", f"the provider timed out (HTTP {status})")
    return ProviderError("http", f"HTTP {status}: {snippet}")


Complete = Callable[..., str]


def get_provider(name: str) -> Complete:
    if name == "gemini":
        from .gemini import complete
    elif name == "openrouter":
        from .openrouter import complete
    elif name == "mock":
        from .mock import complete
    else:
        raise ProviderError("config", f"unknown provider {name!r}")
    return complete
