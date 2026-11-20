"""A one-off look at what the free source `wikipedia` offers for the eleven pictures the first real run of the automatic choice (project `eligius`) could not find
(run by the worker websearch, once, from its snapshot on the server: `tools/deploy/snapshot_py.sh websearch tests/e2e/picks_auto/websearch_proof.py`). Not a test:
nothing imports it and no test runs it.

Limits it keeps (the brief): only the free Wikipedia and Wikimedia APIs, at most EIGHTY requests in all (every API request AND every thumbnail), one a second, a generic
User-Agent with no person and no project in it, nothing written outside the snapshot's own folder `proof_out/`, no You.com (the paid source is never built here), no model.
It runs the job's own code (`bti.picks.auto.search.search_want` with the Wikipedia step; the other sources are not asked), with the `entity` that the new plan would
give each want, and builds the contact sheet the choosing session would see.

Input (read-only copies, made by the caller): proof_in/search.json = projects/eligius/cache/picks_auto/search.json."""
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
os.environ.pop("BTI_NO_REAL_MODELS", None)                      # the one place in this work where the A7 switch is down: the free Wikipedia proof
os.environ["BTI_REAL_NETWORK_PROOF"] = "1"

from bti.media import api, http                                 # noqa: E402
from bti.media.sources import wikipedia as W                    # noqa: E402
from bti.picks import service                                   # noqa: E402
from bti.picks.auto import images, search as asearch            # noqa: E402

GENERIC = "ImageResearch/1.0 (art documentary research; generic client)"
http.USER_AGENT = GENERIC                                        # the Commons and thumbnail requests of this process say the same generic thing
MAX_REQUESTS = 80
PER_SHEET = 6
OUT = REPO / "proof_out"
IN = REPO / "proof_in"

# the `entity` a plan written under the new rules would give each want (the name under which an encyclopedia knows the thing); `search` stays the old plan's words
ENTITY = {"b0015.1": "Eligius", "b0020.1": "Noyon Cathedral", "b0026.2": "Philip the Good", "b0028.1": "Caravel", "b0029.1": "Philip the Good",
          "b0035.1": "Charles the Bold", "b0045.1": "Arnolfini Portrait", "b0046.1": "Falconry", "b0051.1": "Jan van Eyck", "b0055.1": "Charles the Bold",
          "b0061.1": "Pope John Paul II"}

ARGS = [a for a in sys.argv[1:] if not a.startswith("--used=")]
state = {"thumbs": 0, "api_before": int(next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("--used=")), "0"))}      # `--used=N`: requests an earlier run of this proof already made
wiki = api.get_source("wikipedia")
assert isinstance(wiki, W.WikipediaSource) and wiki.min_interval >= 1.0


def used() -> int:
    return state["api_before"] + wiki.requests + state["thumbs"]


def thumb(pdir, cand, limited=None, clock=time.time):
    if used() >= MAX_REQUESTS:
        print("   (request limit reached: no thumbnail for %s)" % cand["source_id"])
        return None
    dest = asearch.store.thumb_path(pdir, cand["source"], cand["source_id"])
    cached = dest.is_file()
    rel = asearch.default_fetch_thumb(pdir, cand, limited, clock)           # the job's own pacing (one a second per Wikimedia host) applies
    if not cached and rel:
        state["thumbs"] += 1
    return rel


def real_wiki_search(pdir, query, beat, sources, limit, kind="image"):
    time.sleep(0.0)
    return service.search(pdir, query, beat, sources, limit, kind=kind)


def nothing_else(pdir, query, beat, sources, limit, kind="image"):
    return {"query": query, "items": [], "errors": []}          # the other sources are not asked in this proof


def main():
    OUT.mkdir(exist_ok=True)
    pdir = OUT / "proj"
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    asearch.PER_WANT_WEB, asearch.SPARE_WEB = PER_SHEET, 0
    search_json = json.loads((IN / "search.json").read_text(encoding="utf-8"))
    st = asearch.new_state()
    report = []
    only = ARGS or list(ENTITY)                       # a second run can take up the wants a first one left (a wait that Wikipedia asked for)
    for wid in only:
        ent = ENTITY[wid]
        old = search_json["wants"][wid]
        want = {"id": wid, "beat": wid.split(".")[0], "n": 1, "type": "context", "kind": old["kind"], "search": old["queries"][0], "alt": old["queries"][1:], "what": old["what"],
                "entity": ent}
        st["wants"][wid] = asearch._new_want(want)
        t0, u0 = time.time(), used()
        asearch.search_want(pdir, want, st, main_key="none", search=nothing_else, wiki_search=real_wiki_search, fetch_thumb=thumb, clock=time.time, cancelled=lambda: False)
        w = st["wants"][wid]
        if st["limited"]:
            print("   waits asked for (seconds left): %s" % {k: int(v - time.time()) for k, v in st["limited"].items()})
        print("%s | entity=%r | old search=%r | status=%s code=%s | %d candidates | requests used so far %d (this want %d) | %.0f s" % (
            wid, ent, want["search"], w["status"], w["code"], len(w["candidates"]), used(), used() - u0, time.time() - t0))
        for c in w["candidates"]:
            print("   %d. %s | article=%r | %s x %s | %s | %s" % (c["n"], c["source_id"][:80], c.get("page_title"), c["width"], c["height"], c["licence"], (c.get("author") or "")[:30]))
        tiles = [(str(c["n"]), (pdir / c["thumb"]) if c.get("thumb") else None) for c in w["candidates"]]
        if tiles:
            images.contact_sheet(tiles, OUT / ("sheet_%s.jpg" % wid.replace(".", "_")))
        report.append({"id": wid, "entity": ent, "what": want["what"], "old_search": want["search"], "status": w["status"], "candidates": [
            {k: c.get(k) for k in ("n", "source_id", "page_title", "site", "snippet", "width", "height", "licence", "author", "page_url")} for c in w["candidates"]]})
    (OUT / ("report_%s.json" % "_".join(x.replace(".", "") for x in only[:1]))).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TOTAL requests: %d (this run: API %d + thumbnails %d; earlier runs: %d), limit %d" % (used(), wiki.requests, state["thumbs"], state["api_before"], MAX_REQUESTS))


if __name__ == "__main__":
    main()
