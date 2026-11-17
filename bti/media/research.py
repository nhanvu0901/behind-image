"""Visual research: suggest WHAT to show for a script beat.

Lessons applied (R2 section 6.5, comic youcom_scout.py):
- WE own the query plan (narrow, angled queries); You.com only does the digging.
- The domain whitelist is verified after the fact, never trusted.
- Provenance gate: a suggestion survives only if a URL it cites is among the response's
  own returned sources. Labels and dedup from the service are not trusted; we dedup here.
- Live calls are OFF by default. They need `live=True` AND the YDC_API_KEY env var, or
  `LiveCallDisabled` is raised before any request is built. Clients that do not spend money
  (fakes in tests) declare `is_live = False` (or simply lack the attribute).
"""
from __future__ import annotations

import os
import re
from typing import Any, Callable
from urllib.parse import urlparse

from .youcom import YouComClient, compact_search_query, strict

DOMAINS = [
    "metmuseum.org", "nationalgallery.org.uk", "wikipedia.org", "wikimedia.org",
    "wikidata.org", "britishmuseum.org", "louvre.fr", "rijksmuseum.nl", "artic.edu",
    "nga.gov", "getty.edu", "khanacademy.org", "smarthistory.org", "europeana.eu",
    "archive.org", "loc.gov",
]
KINDS = ["artwork", "portrait", "photo", "document", "map", "video", "diagram"]
MAX_QUERIES = 10
_STOP = set("the a an and or of in on at to for with by from is are was were it its this that these those "
            "as be been has have had not but into than then when which who whom he she they his her their "
            "you your we our i".split())


class LiveCallDisabled(RuntimeError):
    """A paid You.com call was requested without live=True and YDC_API_KEY."""


class ResearchError(RuntimeError):
    """The upstream call failed (never includes the key or the prompt). `kind` is one of key_refused, quota, timeout,
    bad_answer, failed; `status` the HTTP status when there was one; `detail` a bounded piece of the service's own words."""

    def __init__(self, message: str, *, kind: str = "failed", status: int | None = None, detail: str = ""):
        super().__init__(message)
        self.kind, self.status, self.detail = kind, status, detail


def _error_kind(status, error: str) -> str:
    err = (error or "").lower()
    if status in (401, 403):
        return "key_refused"
    if status in (402, 429):
        return "quota"
    if "timeout" in err or "timed out" in err:
        return "timeout"
    if status is not None and 400 <= status < 500 or "not valid json" in err:
        return "bad_answer"
    return "failed"


# --------------------------------------------------------------------------- guard

def _require_live(client, live: bool):
    """Return the client to use. Real (paying) clients need live=True and the env key."""
    if client is None:
        client = YouComClient()
    if getattr(client, "is_live", False):
        if not live:
            raise LiveCallDisabled(
                "live You.com calls are OFF by default: pass live=True to enable them "
                "(this is a paid API)")
        if not (getattr(client, "api_key", "") or os.environ.get("YDC_API_KEY", "")).strip():
            raise LiveCallDisabled("live=True but the YDC_API_KEY environment variable is not set")
    return client


# --------------------------------------------------------------------------- query plan

def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'\-]+", text or "")


def _focus_terms(beat_text: str, ctx_text: str, n: int = 3) -> list[str]:
    """Mid-sentence capitalised words, else the longest content words, not already in the context."""
    seen = {w.lower() for w in _words(ctx_text)}
    caps, longest = [], []
    for sent in re.split(r"(?<=[.!?])\s+", beat_text or ""):
        ws = _words(sent)
        for i, w in enumerate(ws):
            lw = w.lower()
            if lw in _STOP or lw in seen:
                continue
            if i > 0 and w[0].isupper() and w not in caps:
                caps.append(w)
            elif len(w) > 5 and w not in longest:
                longest.append(w)
    longest.sort(key=len, reverse=True)
    return (caps + longest)[:n]


def _listify(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v if str(x).strip()]


def plan_visual_queries_tagged(beat_text: str, artwork_context: dict | None) -> list[tuple[str, str]]:
    """[(angle, query)]. Narrow angled queries; an angle without context data is skipped."""
    c = artwork_context or {}
    title, artist = str(c.get("title") or "").strip(), str(c.get("artist") or "").strip()
    place, technique = str(c.get("place") or "").strip(), str(c.get("technique") or "").strip()
    year = str(c.get("year") or "").strip()
    out: list[tuple[str, str]] = []
    if artist:
        out.append(("same_artist", f"{artist} other works related to {title}".strip()))
        out.append(("same_artist", f"{artist} paintings of the same period {year}".strip()))
    for m in _listify(c.get("motifs"))[:3]:
        out.append(("motif", f"{m} motif in other paintings compared with {title}".strip()))
    if place:
        out.append(("place", f"{place} {year} historic view photograph".strip()))
    for p in _listify(c.get("people"))[:3]:
        out.append(("people", f"{p} portrait"))
    docs = _listify(c.get("documents"))
    for d in docs[:2]:
        out.append(("documents", f"{d} archival document"))
    if title and not docs:
        out.append(("documents", f"{title} historical document inventory archive record"))
    out.append(("technique", f"{technique or 'infrared reflectography x-ray'} analysis of {title}".strip()
                if (technique or title) else "painting technique analysis"))
    ctx_text = " ".join([title, artist, place, technique] + _listify(c.get("people")) + _listify(c.get("motifs")))
    focus = _focus_terms(beat_text, ctx_text)
    if focus:
        out.append(("beat", f"{title} {' '.join(focus)}".strip()))
    seen, tagged = set(), []
    for angle, q in out:
        q = compact_search_query(" ".join(q.split()))
        if q and q.lower() not in seen:
            seen.add(q.lower())
            tagged.append((angle, q))
    return tagged[:MAX_QUERIES]


def plan_visual_queries(beat_text: str, artwork_context: dict | None) -> list[str]:
    return [q for _, q in plan_visual_queries_tagged(beat_text, artwork_context)]


# --------------------------------------------------------------------------- helpers

def _norm_url(u: str) -> str:
    p = urlparse((u or "").strip())
    host = p.netloc.lower().removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}" + (f"?{p.query}" if p.query else "")


def _host_ok(u: str, domains: list[str]) -> bool:
    host = (urlparse((u or "").strip()).hostname or "").lower().removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in domains)


def _jaccard(a: str, b: str) -> float:
    ta = {w.lower() for w in _words(a) if w.lower() not in _STOP}
    tb = {w.lower() for w in _words(b) if w.lower() not in _STOP}
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def _gate_urls(urls, returned: set[str], domains: list[str]) -> list[str]:
    """Keep URLs that the response itself returned as sources AND that are on the whitelist."""
    kept, seen = [], set()
    for u in urls or []:
        n = _norm_url(str(u))
        if n in returned and _host_ok(str(u), domains) and n not in seen:
            seen.add(n)
            kept.append(str(u))
    return kept


def _unpack(call) -> tuple[dict, set[str]]:
    if not getattr(call, "ok", False):
        status, err = getattr(call, "status_code", None), str(getattr(call, "error", None) or "unknown error")
        raise ResearchError(f"You.com call failed: {err}", kind=_error_kind(status, err), status=status,
                            detail=str(getattr(call, "response_text", "") or "")[:300])
    out = (call.payload or {}).get("output") or {}
    content = out.get("content")
    if isinstance(content, str):
        import json
        try:
            content = json.loads(content)
        except ValueError:
            content = {}
    sources = {_norm_url(s.get("url", "")) for s in out.get("sources") or [] if isinstance(s, dict) and s.get("url")}
    return (content if isinstance(content, dict) else {}), sources


def _context_lines(ctx: dict | None) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in (ctx or {}).items() if v)


SUGGESTION_SCHEMA = strict({"suggestions": {"type": "array", "items": strict({
    "what": {"type": "string"},
    "kind": {"type": "string", "enum": KINDS},
    "why": {"type": "string"},
    "search_terms": {"type": "array", "items": {"type": "string"}},
    "source_urls": {"type": "array", "items": {"type": "string"}},
})}})

CLAIM_SCHEMA = strict({
    "verdict": {"type": "string", "enum": ["contradicted", "not_contradicted", "insufficient"]},
    "evidence_urls": {"type": "array", "items": {"type": "string"}},
    "note": {"type": "string"},
})


# --------------------------------------------------------------------------- research

def visual_research(beat_text: str, context: dict | None, client=None, live: bool = False, *,
                    effort: str = "standard", domains: list[str] | None = None) -> list[dict]:
    """Suggest what to show during `beat_text`. Each item: {what, kind, why, search_terms, source_urls}."""
    client = _require_live(client, live)
    domains = list(domains or DOMAINS)
    tagged = plan_visual_queries_tagged(beat_text, context)
    prompt = (
        "You help an art-documentary editor decide WHAT TO SHOW on screen while a line of narration "
        "is spoken. Find specific, nameable visual material (artworks, portraits, photographs, "
        "documents, maps, video, technical images) that a licence-clear archive such as Wikimedia "
        "Commons or a museum open-access collection is likely to hold.\n\n"
        f"Narration:\n{beat_text}\n\nContext:\n{_context_lines(context)}\n\n"
        "Cover each angle with its query:\n" + "\n".join(f"- [{a}] {q}" for a, q in tagged) + "\n\n"
        "Rules: only suggest items you found on a cited page; each suggestion must list the page URLs "
        "it relies on in source_urls; give 2 to 4 short search_terms a person could type into Commons; "
        "do not invent works; do not repeat a suggestion."
    )
    call = client.research(prompt, SUGGESTION_SCHEMA, {"domains": domains}, effort=effort)
    content, returned = _unpack(call)
    kept: list[dict] = []
    for s in content.get("suggestions") or []:
        if not isinstance(s, dict) or not str(s.get("what", "")).strip():
            continue
        urls = _gate_urls(s.get("source_urls"), returned, domains)
        if not urls:                       # provenance gate
            continue
        item = {
            "what": str(s["what"]).strip(),
            "kind": s.get("kind") if s.get("kind") in KINDS else "artwork",
            "why": str(s.get("why", "")).strip(),
            "search_terms": [str(t).strip() for t in s.get("search_terms") or [] if str(t).strip()][:4],
            "source_urls": urls,
        }
        terms_key = tuple(sorted(t.lower() for t in item["search_terms"]))
        if any(_jaccard(item["what"], k["what"]) >= 0.6 or
               (terms_key and terms_key == tuple(sorted(t.lower() for t in k["search_terms"])))
               for k in kept):
            continue
        kept.append(item)
    return kept


def confirm_claim(claim: str, context: dict | None, client=None, live: bool = False, *,
                  effort: str = "standard", domains: list[str] | None = None) -> dict:
    """Refutation-framed check. Returns {verdict, evidence_urls, note}.

    A verdict without at least one gated evidence URL is downgraded to "insufficient"."""
    client = _require_live(client, live)
    domains = list(domains or DOMAINS)
    prompt = (
        "Try to find evidence that the following claim is FALSE or misleading. Search for sources "
        "that contradict it, then judge. Answer 'contradicted' if a cited source contradicts it, "
        "'not_contradicted' only if reliable sources state it, 'insufficient' if you cannot tell. "
        "Cite the page URLs in evidence_urls. Do not assume the claim is true.\n\n"
        f"Claim: {claim}\n\nContext:\n{_context_lines(context)}"
    )
    call = client.research(prompt, CLAIM_SCHEMA, {"domains": domains}, effort=effort)
    content, returned = _unpack(call)
    urls = _gate_urls(content.get("evidence_urls"), returned, domains)
    verdict = content.get("verdict")
    note = str(content.get("note", "")).strip()
    if verdict not in ("contradicted", "not_contradicted", "insufficient"):
        verdict = "insufficient"
        note = (note + " (unreadable verdict)").strip()
    elif verdict != "insufficient" and not urls:
        note = (f"{note} (downgraded: no evidence URL was among the returned sources)").strip()
        verdict = "insufficient"
    return {"verdict": verdict, "evidence_urls": urls, "note": note}


# --------------------------------------------------------------------------- resolve

def resolve_suggestion(suggestion: dict, *, limit_per_term: int = 6, max_terms: int = 3,
                       search_fn: Callable[..., list[dict]] | None = None) -> list[dict]:
    """Turn a suggestion into Commons (and, for artworks, Met) candidates; licence-ok first."""
    if search_fn is None:
        from . import api
        search_fn = api.search
    kind = suggestion.get("kind", "artwork")
    plan = [("commons", "video")] if kind == "video" else [("commons", "image")]
    if kind in ("artwork", "portrait"):
        plan.append(("met", "image"))
    terms = [t for t in suggestion.get("search_terms") or [] if t][:max_terms] or [suggestion.get("what", "")]
    seen, out = set(), []
    for term in terms:
        for source, k in plan:
            try:
                found = search_fn(term, source=source, kind=k, limit=limit_per_term)
            except Exception:           # one failing source must not sink the rest
                continue
            for c in found:
                ident = (c.get("source"), c.get("source_id"))
                if ident not in seen:
                    seen.add(ident)
                    out.append(c)
    out.sort(key=lambda c: not c.get("licence_ok"))
    return out
