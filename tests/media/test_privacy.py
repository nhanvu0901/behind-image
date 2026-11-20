"""The owner's privacy rule: no request of the app to an outside service carries this project's name, a repository address, a person's name,
an e-mail address or an account name (in a header, a query or a body); one generic client string, from one place (`bti.media.http.USER_AGENT`).
No real request: every source gets a recording transport."""
import ast
import re
from pathlib import Path

import httpx
import pytest

from bti.media import http
from bti.media.sources import commons, met, osm, pexels, pixabay, web, wikipedia
from bti.media.youcom import YouComClient
from bti.script import providers as script_providers
from bti.script.providers import get_provider

from conftest import FakeResp, png_bytes

ROOT = Path(__file__).resolve().parents[2]

# what must never leave the machine: the project's names (long and short), its repository, the owner and an address
FORBIDDEN = re.compile(r"behind[-_ ]?the[-_ ]?image|behind[-_ ]image|\bbti\b|nhanvu|vu[-_ ]trong|github|gitlab|mailto|@|noreply", re.I)


def clean(text: str) -> bool:
    return FORBIDDEN.search(text) is None


class Rec:
    """A transport that records every request (address, headers, body) and answers an empty JSON object."""

    def __init__(self, body: bytes = b"{}", ctype: str = "application/json"):
        self.reqs, self.body, self.ctype = [], body, ctype

    def __call__(self, req, timeout=None):
        data = req.data.decode("utf-8", "replace") if isinstance(req.data, (bytes, bytearray)) else str(req.data or "")
        self.reqs.append((req.full_url, {k.lower(): v for k, v in req.header_items()}, data))
        return FakeResp(self.body, {"Content-Type": self.ctype})


def tolerate(fn, *a, **k):
    """The recording transport answers nothing useful: the source may refuse the answer; only what it SENT matters."""
    try:
        return fn(*a, **k)
    except Exception:       # noqa: BLE001
        return None


def check_all(rec: Rec, expect_ua: str = http.USER_AGENT):
    assert rec.reqs, "the source sent nothing"
    for url, headers, data in rec.reqs:
        assert headers.get("user-agent") == expect_ua, url
        assert clean(url) and clean(data), (url, data)
        for name, value in headers.items():
            assert clean(name) and clean(str(value)), (name, value)
        assert "referer" not in headers and "x-title" not in headers and "from" not in headers      # nothing that names a caller or a contact


# ---------------------------------------------------------------------------------------------------------------- the string itself
def test_the_client_string_is_generic():
    ua = http.USER_AGENT
    assert ua.startswith("ImageResearch/") and clean(ua) and "http" not in ua.lower() and "." not in ua.split("/")[0]


def test_the_client_string_is_written_once_in_the_code():
    """One place: `bti/media/http.py`. No other module of the app writes a User-Agent value of its own."""
    holders, literal_agents = [], []
    for path in sorted((ROOT / "bti").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "ImageResearch" in text:
            holders.append(path.relative_to(ROOT).as_posix())
        if re.search(r"""["']user-agent["']\s*:\s*["']""", text, re.I):     # a header written with a string literal as its value
            literal_agents.append(path.relative_to(ROOT).as_posix())
    assert holders == ["bti/media/http.py"] and literal_agents == []


def test_no_module_that_calls_an_outside_service_names_the_project_the_owner_or_the_repository():
    """A static guard over every module of the app that can open a connection (HTTP, a model provider): none holds a string constant that names
    the project, its repository, a person or an address. (Docstrings and comments are allowed to talk about the project: they are not sent.)"""
    caller = re.compile(r"urllib\.request|httpx|http\.client|open_url|urlopen|aiohttp|requests\.")
    own = re.compile(r"behind[-_ ]?the[-_ ]?image|behind[-_ ]image|nhanvu|github\.com|noreply", re.I)       # (a filter that REFUSES "mailto:" links is not a send)
    bad = []
    for path in sorted((ROOT / "bti").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if not caller.search(text):
            continue
        tree = ast.parse(text)
        docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body
                      and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings and own.search(n.value):
                bad.append(f"{path.relative_to(ROOT).as_posix()}:{n.lineno}")
    assert bad == []


def test_no_header_that_names_the_calling_app_is_written_anywhere():
    """`X-Title`, `HTTP-Referer` and `Referer` name the app (OpenRouter shows them): the code writes none."""
    found = []
    for path in sorted((ROOT / "bti").rglob("*.py")):
        if re.search(r"""["'](x-title|http-referer|referer)["']""", path.read_text(encoding="utf-8"), re.I):
            found.append(path.relative_to(ROOT).as_posix())
    assert found == []


# ---------------------------------------------------------------------------------------------------------------- each source, as sent
def test_the_free_sources_send_the_generic_client_and_nothing_else_about_us(tmp_path):
    rec = Rec()
    q = "Noyon Cathedral"
    tolerate(commons.CommonsSource(opener=rec, sleep=lambda s: None).search, q)
    tolerate(met.MetSource(opener=rec, sleep=lambda s: None).search, q)
    tolerate(pexels.PexelsSource(key="test-key", opener=rec, sleep=lambda s: None).search, q)
    tolerate(pixabay.PixabaySource(key="test-key", opener=rec, sleep=lambda s: None).search, q)
    tolerate(osm.OsmSource(opener=rec, sleep=lambda s: None, cache_dir=tmp_path / "osm").search, q)
    tolerate(wikipedia.WikipediaSource(opener=rec, sleep=lambda s: None, clock=lambda: 0.0).search, q)
    hosts = {http._host(u) for u, _, _ in rec.reqs}
    assert {"commons.wikimedia.org", "pixabay.com", "en.wikipedia.org"} <= hosts and len(hosts) >= 5, hosts
    check_all(rec)


def test_a_download_of_a_file_and_of_a_web_picture_send_the_generic_client(tmp_path):
    rec = Rec(png_bytes(700, 500), "image/png")
    http.download_file("https://upload.wikimedia.org/a.png", tmp_path / "a.png", max_bytes=10 ** 6, opener=rec)
    web.fetch_image("https://img.example.org/b.png", tmp_path / "b.png", opener=rec)
    assert len(rec.reqs) == 2
    check_all(rec)


def test_the_youcom_client_sends_the_generic_client_in_a_search_and_in_a_research():
    rec = Rec()
    client = YouComClient(api_key="test-key", timeout=5, opener=rec)
    client.search("Noyon Cathedral", None)
    client.research("Which picture shows the cathedral?", {"type": "object"}, {"domains": ["commons.wikimedia.org"]})
    assert [u.split("?")[0] for u, _, _ in rec.reqs] == ["https://api.you.com/v1/search", "https://api.you.com/v1/research"]
    check_all(rec)
    assert all(h["x-api-key"] == "test-key" for _, h, _ in rec.reqs)       # the one thing that is the caller's own: the key, in a header


def test_the_search_for_a_picture_by_the_web_source_sends_only_what_the_caller_asked(monkeypatch):
    """The words of the search are the wanted thing's own words; nothing is added to them."""
    rec = Rec()
    client = YouComClient(api_key="test-key", timeout=5, opener=rec)
    tolerate(client.search, "portrait of a man in a red turban", {"domains": []})
    url = rec.reqs[0][0]
    assert "query=portrait+of+a+man+in+a+red+turban" in url and clean(url)


# ---------------------------------------------------------------------------------------------------------------- the model providers (httpx)
@pytest.mark.parametrize("provider,key_env", [("openrouter", "K_OR"), ("gemini", "K_GM")])
def test_a_model_request_over_http_names_neither_the_app_nor_a_person(monkeypatch, provider, key_env):
    monkeypatch.delenv("BTI_NO_REAL_MODELS", raising=False)
    monkeypatch.setenv(key_env, "FAKEKEY1234567890")
    seen = []

    def handler(req: httpx.Request):
        seen.append(req)
        body = ({"choices": [{"message": {"role": "assistant", "content": "A"}, "finish_reason": "stop"}]} if provider == "openrouter"
                else {"candidates": [{"content": {"parts": [{"text": "A"}]}}]})
        return httpx.Response(200, json=body)

    script_providers.set_transport(httpx.MockTransport(handler))
    try:
        got = get_provider(provider)({"id": "x", "provider": provider, "model": "m/x", "key_env": key_env}, "SYS", "USER", timeout=5)
    finally:
        script_providers.set_transport(None)
    assert got == "A" and len(seen) == 1
    req = seen[0]
    assert clean(str(req.url))
    for name, value in req.headers.items():
        assert name.lower() not in ("x-title", "http-referer", "referer", "from"), name
        assert name.lower() in ("authorization", "x-goog-api-key") or clean(value), (name, value)       # the key is the caller's own
    assert clean(req.content.decode("utf-8"))
    assert "x-title" not in req.headers and "http-referer" not in req.headers
