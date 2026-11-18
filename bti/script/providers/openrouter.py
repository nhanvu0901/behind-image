"""OpenRouter chat completions (OpenAI-compatible)."""
from __future__ import annotations

import os
import httpx

from ..env import get_key
from . import ProviderError, check_cancel, classify_status, http_client

URL = "https://openrouter.ai/api/v1/chat/completions"


def complete(spec: dict, system: str, user: str, *, timeout: float = 300, on_progress=None, cancel=None) -> str:
    if os.environ.get("BTI_NO_REAL_MODELS") == "1":
        raise ProviderError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1)")
    key_env = spec.get("key_env")
    key = get_key(key_env)
    if not key:
        raise ProviderError("config", f"the key {key_env} is not set")
    check_cancel(cancel)
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    body = {"model": spec["model"], "messages": msgs, "temperature": float(spec.get("temperature", 1.0))}
    try:
        with http_client(timeout) as c:
            r = c.post(URL, json=body, headers={"Authorization": f"Bearer {key}", "content-type": "application/json",
                                                "X-Title": "behind-the-image"})
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
    if isinstance(j.get("error"), dict):
        code = j["error"].get("code")
        msg = str(j["error"].get("message", ""))[:200]
        raise classify_status(int(code) if isinstance(code, int) else 502, msg, (key_env,))
    ch = (j.get("choices") or [{}])[0]
    text = ((ch.get("message") or {}).get("content")) or ""
    if not text.strip():
        raise ProviderError("empty", f"the model returned no text (finish reason: {ch.get('finish_reason')})")
    if on_progress:
        on_progress(1.0)
    return text
