"""Google Generative Language REST API (generateContent). The key goes in a header, never in the URL."""
from __future__ import annotations

import os
import httpx

from ..env import get_key
from . import ProviderError, check_cancel, classify_status, http_client

BASE = "https://generativelanguage.googleapis.com/v1beta/models/"


def complete(spec: dict, system: str, user: str, *, timeout: float = 300, on_progress=None, cancel=None) -> str:
    if os.environ.get("BTI_NO_REAL_MODELS") == "1":
        raise ProviderError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1)")
    key_env = spec.get("key_env")
    key = get_key(key_env)
    if not key:
        raise ProviderError("config", f"the key {key_env} is not set")
    check_cancel(cancel)
    body = {"contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": float(spec.get("temperature", 1.0))}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    try:
        with http_client(timeout) as c:
            r = c.post(f"{BASE}{spec['model']}:generateContent", json=body,
                       headers={"x-goog-api-key": key, "content-type": "application/json"})
    except httpx.TimeoutException:
        raise ProviderError("timeout", f"no answer within {int(timeout)} seconds")
    except httpx.HTTPError as e:
        raise ProviderError("http", f"network error: {type(e).__name__}")
    check_cancel(cancel)
    if r.status_code != 200:
        raise classify_status(r.status_code, r.text, (key_env,))
    try:
        j = r.json()
    except ValueError:
        raise ProviderError("http", "the provider answered with something that is not JSON")
    if (j.get("promptFeedback") or {}).get("blockReason"):
        raise ProviderError("blocked", f"the prompt was blocked: {j['promptFeedback']['blockReason']}")
    cands = j.get("candidates") or []
    text = "".join(p.get("text", "") for p in ((cands[0].get("content") or {}).get("parts") or [])) if cands else ""
    if not text.strip():
        fr = cands[0].get("finishReason") if cands else None
        raise ProviderError("empty", f"the model returned no text (finish reason: {fr})")
    if on_progress:
        on_progress(1.0)
    return text
