"""Providers against recorded-shape fakes (httpx.MockTransport). No network, no real key."""
import json
import threading

import httpx
import pytest

from bti.script import env as env_mod, models as models_mod
from bti.script.providers import ProviderError, get_provider, set_transport

FAKE_KEY = "AIzaFAKEKEY1234567890"


def spec(provider, key_env="K", model="m1"):
    return {"id": "x", "provider": provider, "model": model, "key_env": key_env}


def serve(handler):
    set_transport(httpx.MockTransport(handler))


def test_env_parser_and_precedence(tmp_path, monkeypatch):
    f = tmp_path / "x.env"
    f.write_text("# comment\nK1=abc\nexport OPENROUTER_API_KEY = \"quoted value\"\nYDC_API_KEY='single'\nGEMINI_API_KEY=val # trailing\nEMPTY=\n", encoding="utf-8")
    assert env_mod.parse_env(f.read_text(), only=None) == {"K1": "abc", "OPENROUTER_API_KEY": "quoted value", "YDC_API_KEY": "single", "GEMINI_API_KEY": "val", "EMPTY": ""}
    assert env_mod.parse_env(f.read_text()) == {"OPENROUTER_API_KEY": "quoted value", "YDC_API_KEY": "single", "GEMINI_API_KEY": "val"}
    monkeypatch.setenv("BTI_ENV_FILE", str(f))
    env_mod._cache.clear()
    assert env_mod.get_key("YDC_API_KEY") == "single" and env_mod.get_key("K1") is None and env_mod.get_key("NOPE") is None
    monkeypatch.setenv("YDC_API_KEY", "from-process")
    assert env_mod.get_key("YDC_API_KEY") == "from-process"            # the process environment wins
    import os
    assert "GEMINI_API_KEY" not in os.environ                          # the loader never exports values
    assert env_mod.redact("the key is from-process ok", "YDC_API_KEY") == "the key is *** ok"


def test_env_loader_ignores_every_line_that_is_not_ours(tmp_path, monkeypatch):
    f = tmp_path / "comic.env"
    f.write_text("FFMPEG_PATH=/opt/ffmpeg\nTTS_PROVIDER=chatterbox\nMODEL_LIST=a,b,c\nOPENROUTER_API_KEY=sk-or-ONLYTHIS\nOTHER_SECRET=zzz\n", encoding="utf-8")
    monkeypatch.setenv("BTI_ENV_FILE", str(f))
    env_mod._cache.clear()
    import os
    before = dict(os.environ)
    assert env_mod._dotenv() == {"OPENROUTER_API_KEY": "sk-or-ONLYTHIS"}      # nothing else is even held in memory
    for name in ("FFMPEG_PATH", "TTS_PROVIDER", "MODEL_LIST", "OTHER_SECRET"):
        assert env_mod.get_key(name) is None
    assert dict(os.environ) == before                                          # and nothing was exported


def test_models_listing_never_shows_keys(monkeypatch, tmp_path):
    cfg = tmp_path / "m.json"
    cfg.write_text(json.dumps([{"id": "g", "provider": "gemini", "model": "gm", "key_env": "GEMINI_API_KEY", "default": True},
                               {"id": "o", "provider": "openrouter", "model": "a/b", "key_env": "OPENROUTER_API_KEY"},
                               {"id": "m", "provider": "mock", "model": "mock"}, {"id": "bad", "provider": "nope"}]))
    pub = models_mod.public_models(cfg)
    assert [m["id"] for m in pub] == ["g", "o", "m"]
    assert pub[0]["enabled"] is False and pub[0]["missing_env"] == "GEMINI_API_KEY" and pub[2]["enabled"] is True
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    pub = models_mod.public_models(cfg)
    assert pub[0]["enabled"] is True and pub[0]["missing_env"] is None
    assert FAKE_KEY not in json.dumps(pub)


def test_repo_models_file_is_valid():
    ms = models_mod.load_models()
    raw = models_mod.load_raw()
    assert {m["provider"] for m in raw} == {"antigravity", "openrouter", "mock"}                # no Gemini API entry
    assert [m["id"] for m in raw if m.get("default")] == ["agy"] and "trả tiền" in raw[1]["label"]
    assert all("key" not in m for m in ms)                              # only the NAME of the variable is stored


def test_gemini_request_and_response_shape(monkeypatch):
    monkeypatch.setenv("K", FAKE_KEY)
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["headers"], seen["body"] = str(req.url), req.headers, json.loads(req.content)
        return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [{"text": "Hello "}, {"text": "world"}]},
                                                         "finishReason": "STOP"}], "usageMetadata": {"totalTokenCount": 9}})
    serve(handler)
    out = get_provider("gemini")(spec("gemini", model="gemini-x"), "SYS", "USER", timeout=5)
    assert out == "Hello world"
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-x:generateContent"
    assert FAKE_KEY not in seen["url"] and seen["headers"]["x-goog-api-key"] == FAKE_KEY
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "USER"


def test_openrouter_request_and_response_shape(monkeypatch):
    monkeypatch.setenv("K", "sk-or-FAKEKEY12345")
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        return httpx.Response(200, json={"id": "gen-1", "choices": [{"message": {"role": "assistant", "content": "Answer"}, "finish_reason": "stop"}]})
    serve(handler)
    assert get_provider("openrouter")(spec("openrouter", model="anthropic/x"), "SYS", "USER", timeout=5) == "Answer"
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions" and seen["auth"] == "Bearer sk-or-FAKEKEY12345"
    assert seen["body"]["model"] == "anthropic/x" and [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]


@pytest.mark.parametrize("provider", ["gemini", "openrouter"])
@pytest.mark.parametrize("status,kind", [(401, "auth"), (403, "auth"), (429, "rate_limit"), (504, "timeout"), (500, "http")])
def test_error_kinds_and_keys_never_leak(monkeypatch, provider, status, kind):
    monkeypatch.setenv("K", FAKE_KEY)
    serve(lambda req: httpx.Response(status, text=f"bad request, your key {FAKE_KEY} is wrong"))
    with pytest.raises(ProviderError) as e:
        get_provider(provider)(spec(provider), "s", "u", timeout=5)
    assert e.value.kind == kind and FAKE_KEY not in e.value.message


def test_missing_key_empty_text_blocked_and_inline_error(monkeypatch):
    serve(lambda req: httpx.Response(200, json={}))
    with pytest.raises(ProviderError) as e:
        get_provider("gemini")(spec("gemini"), "s", "u", timeout=5)
    assert e.value.kind == "config" and "K" in e.value.message                       # names the variable, not a value
    monkeypatch.setenv("K", FAKE_KEY)
    with pytest.raises(ProviderError) as e:
        get_provider("gemini")(spec("gemini"), "s", "u", timeout=5)
    assert e.value.kind == "empty"
    serve(lambda req: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(ProviderError) as e:
        get_provider("gemini")(spec("gemini"), "s", "u", timeout=5)
    assert e.value.kind == "blocked"
    serve(lambda req: httpx.Response(200, json={"error": {"code": 429, "message": "quota"}}))
    with pytest.raises(ProviderError) as e:
        get_provider("openrouter")(spec("openrouter"), "s", "u", timeout=5)
    assert e.value.kind == "rate_limit"


def test_timeout_and_cancel(monkeypatch):
    monkeypatch.setenv("K", FAKE_KEY)

    def slow(req):
        raise httpx.ReadTimeout("slow", request=req)
    serve(slow)
    with pytest.raises(ProviderError) as e:
        get_provider("openrouter")(spec("openrouter"), "s", "u", timeout=1)
    assert e.value.kind == "timeout"
    ev = threading.Event()
    ev.set()
    with pytest.raises(ProviderError) as e:
        get_provider("gemini")(spec("gemini"), "s", "u", timeout=1, cancel=ev)
    assert e.value.kind == "cancelled"


def test_unknown_provider():
    with pytest.raises(ProviderError):
        get_provider("zzz")
