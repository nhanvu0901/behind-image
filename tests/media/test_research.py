import json

import pytest

from bti.media import research
from bti.media.research import (LiveCallDisabled, ResearchError, confirm_claim, plan_visual_queries,
                                resolve_suggestion, visual_research)
from bti.media.youcom import RawCall, YouComClient, strict

CTX = {"title": "The Arnolfini Portrait", "artist": "Jan van Eyck", "year": "1434", "place": "Bruges",
       "people": ["Giovanni Arnolfini"], "motifs": ["convex mirror"], "technique": "oil glazing"}
BEAT = "Notice the mirror behind the couple, where Van Eyck painted two figures in the doorway."


class FakeClient:
    is_live = False

    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def research(self, prompt, schema, profile, *, effort="standard"):
        self.calls.append({"prompt": prompt, "schema": schema, "profile": profile, "effort": effort})
        return RawCall(api="research", payload=self.payload, status_code=200)


def resp(suggestions=None, sources=(), content=None):
    return {"output": {"content": content if content is not None else {"suggestions": suggestions or []},
                       "sources": [{"url": u} for u in sources]}}


def sugg(what, urls, terms=("a",), kind="artwork"):
    return {"what": what, "kind": kind, "why": "because", "search_terms": list(terms), "source_urls": list(urls)}


# ---- planner
def test_planner_has_all_angles():
    qs = plan_visual_queries(BEAT, CTX)
    text = " | ".join(qs).lower()
    assert 1 < len(qs) <= 10 and len(set(q.lower() for q in qs)) == len(qs)
    assert "jan van eyck" in text                        # same artist
    assert "convex mirror" in text                       # motif
    assert "bruges" in text                              # place
    assert "giovanni arnolfini portrait" in text         # people
    assert "document" in text                            # documents
    assert "oil glazing" in text                         # technique
    assert all(len(q.split()) <= 45 for q in qs)


def test_planner_skips_missing_angles_and_is_deterministic():
    qs = plan_visual_queries("A plain line.", {"title": "Mona Lisa"})
    assert qs == plan_visual_queries("A plain line.", {"title": "Mona Lisa"})
    assert plan_visual_queries("", None)           # never crashes


def test_planner_uses_beat_focus_terms():
    qs = plan_visual_queries("He hid a signature above the Chandelier.", {"title": "T", "artist": "A"})
    assert any("Chandelier" in q for q in qs)


# ---- live guard
def test_live_off_by_default_for_real_client(monkeypatch):
    monkeypatch.setenv("YDC_API_KEY", "dummy")
    with pytest.raises(LiveCallDisabled, match="OFF by default"):
        visual_research(BEAT, CTX, client=YouComClient("dummy"))
    with pytest.raises(LiveCallDisabled):
        visual_research(BEAT, CTX)                     # no client given: default client is real
    with pytest.raises(LiveCallDisabled):
        confirm_claim("x", CTX)


def test_live_needs_env_key(monkeypatch):
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    with pytest.raises(LiveCallDisabled, match="YDC_API_KEY"):
        visual_research(BEAT, CTX, live=True)
    with pytest.raises(LiveCallDisabled, match="YDC_API_KEY"):
        confirm_claim("x", CTX, live=True)


def test_guard_accepts_a_key_held_by_the_client_not_the_environment(monkeypatch):
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    c = YouComClient(api_key="from-dotenv")
    assert research._require_live(c, True) is c            # LR-001
    with pytest.raises(LiveCallDisabled):
        research._require_live(YouComClient(api_key=""), True)


def test_guard_blocks_before_any_request(monkeypatch):
    monkeypatch.setenv("YDC_API_KEY", "dummy")

    def forbid(*a, **k):
        raise AssertionError("network must not be touched")
    monkeypatch.setattr("urllib.request.urlopen", forbid)
    with pytest.raises(LiveCallDisabled):
        visual_research(BEAT, CTX)


def test_client_never_reads_a_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("YDC_API_KEY=from-file\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    assert YouComClient().api_key == ""


def test_client_without_key_returns_error_not_request(monkeypatch):
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    call = YouComClient().research("p", {}, {"domains": []})
    assert not call.ok and "YDC_API_KEY" in call.error


# ---- provenance gate
def test_provenance_gate_drops_uncited_and_unreturned():
    good, other = "https://www.metmuseum.org/art/collection/search/1", "https://commons.wikimedia.org/wiki/File:A.jpg"
    c = FakeClient(resp([
        sugg("Mirror detail", [good]),
        sugg("Invented portrait", ["https://metmuseum.org/art/never-returned"]),
        sugg("No urls", []),
        sugg("Off domain", ["https://evil.example.com/x"]),
        sugg("Mixed", [good, "https://nationalgallery.org.uk/not-returned"], terms=("b",)),
    ], sources=[good, other, "https://evil.example.com/x"]))
    out = visual_research(BEAT, CTX, c)
    assert [s["what"] for s in out] == ["Mirror detail", "Mixed"]
    assert all(set(s) == {"what", "kind", "why", "search_terms", "source_urls"} for s in out)
    assert out[0]["source_urls"] == [good] and out[1]["source_urls"] == [good]


def test_url_normalisation_matches_returned_sources():
    c = FakeClient(resp([sugg("Detail", ["https://metmuseum.org/art/1/"])], sources=["https://www.metmuseum.org/art/1"]))
    assert len(visual_research(BEAT, CTX, c)) == 1


def test_dedup_on_our_side():
    u = "https://metmuseum.org/a"
    c = FakeClient(resp([sugg("Arnolfini Portrait mirror detail", [u], ("m1", "m2")),
                         sugg("Mirror detail of Arnolfini Portrait", [u], ("zz",)),
                         sugg("Other", [u], ("M2", "m1")),
                         sugg("Wedding portrait of Giovanni", [u], ("w",))], sources=[u]))
    assert [s["what"] for s in visual_research(BEAT, CTX, c)] == [
        "Arnolfini Portrait mirror detail", "Wedding portrait of Giovanni"]


def test_request_shape_and_schema_is_strict():
    c = FakeClient(resp([], sources=[]))
    visual_research(BEAT, CTX, c, effort="standard")
    call = c.calls[0]
    assert call["profile"]["domains"] == research.DOMAINS and call["effort"] == "standard"
    assert len(call["prompt"]) < 40_000 and BEAT in call["prompt"] and "convex mirror" in call["prompt"]

    def check(node):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False and set(node["required"]) == set(node["properties"])
            for v in node["properties"].values():
                check(v)
        if node.get("type") == "array":
            check(node["items"])
    check(call["schema"])


def test_content_as_json_string_and_failed_call():
    u = "https://metmuseum.org/a"
    payload = resp(content=json.dumps({"suggestions": [sugg("X thing", [u])]}), sources=[u])
    assert len(visual_research(BEAT, CTX, FakeClient(payload))) == 1

    class Bad(FakeClient):
        def research(self, *a, **k):
            return RawCall(api="research", payload={}, error="HTTP 422")
    with pytest.raises(ResearchError, match="HTTP 422"):
        visual_research(BEAT, CTX, Bad({}))


# ---- confirm_claim
def test_confirm_claim_contradicted_with_evidence():
    u = "https://nationalgallery.org.uk/paintings/x"
    c = FakeClient(resp(content={"verdict": "contradicted", "evidence_urls": [u, "https://nope.org"], "note": "dated 1434"},
                        sources=[u]))
    r = confirm_claim("Painted in 1500", CTX, c)
    assert r == {"verdict": "contradicted", "evidence_urls": [u], "note": "dated 1434"}
    assert "FALSE" in c.calls[0]["prompt"]


def test_confirm_claim_without_evidence_downgrades():
    c = FakeClient(resp(content={"verdict": "contradicted", "evidence_urls": ["https://metmuseum.org/z"], "note": "n"},
                        sources=["https://metmuseum.org/other"]))
    r = confirm_claim("claim", CTX, c)
    assert r["verdict"] == "insufficient" and r["evidence_urls"] == [] and "downgraded" in r["note"]
    r2 = confirm_claim("claim", CTX, FakeClient(resp(content={"verdict": "maybe"})))
    assert r2["verdict"] == "insufficient"


# ---- resolve
def test_resolve_suggestion_merges_sources_and_orders_by_licence():
    def fake(term, source="commons", kind="image", limit=6):
        if source == "met":
            raise RuntimeError("down")
        return [{"source": "commons", "source_id": f"File:{term}-bad", "licence_ok": False},
                {"source": "commons", "source_id": f"File:{term}", "licence_ok": True},
                {"source": "commons", "source_id": "File:dup", "licence_ok": True}]
    out = resolve_suggestion({"what": "w", "kind": "artwork", "search_terms": ["a", "b"]}, search_fn=fake)
    assert [c["source_id"] for c in out] == ["File:a", "File:dup", "File:b", "File:a-bad", "File:b-bad"]


def test_resolve_video_uses_commons_video_only():
    seen = []

    def fake(term, source, kind, limit):
        seen.append((source, kind))
        return []
    resolve_suggestion({"what": "w", "kind": "video", "search_terms": ["a"]}, search_fn=fake)
    assert seen == [("commons", "video")]


def test_strict_helper():
    s = strict({"a": {"type": "string"}})
    assert s["required"] == ["a"] and s["additionalProperties"] is False
