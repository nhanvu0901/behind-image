"""A one-off look at what the search part of the automatic picks job finds on the REAL sources (run by the worker c3picks, once, from its
snapshot on the server: `tools/deploy/snapshot_py.sh c3picks tests/e2e/picks_auto/real_search.py`). Not a test: nothing imports it and no test runs it.

Limits it keeps (the brief): at most SIX real searches (one query to one source each), no download of an original, at most TWO thumbnails, a
pause of three seconds before every request, the polite client of `bti.media.http` (a plain User-Agent, a source that says "wait" is left alone),
and nothing about the owner in any request. The four wanted pictures are those of a plan for the lines of a painting video; the sources and the
queries are those `bti.picks.auto.search` would use (`sources_for`, `queries_for`), and the answers are read through `bti.picks.service.search`, the
route the job uses. It prints what it asked and what came back."""
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
os.environ.pop("BTI_NO_REAL_MODELS", None)          # the one place in this work where the switch is off: six real searches and two thumbnails

from bti.picks import service                                    # noqa: E402
from bti.picks.auto import search as asearch                     # noqa: E402

WANTS = [
    {"id": "w1", "type": "context", "kind": "portrait", "search": "Jan van Eyck self portrait", "alt": [], "what": "portrait of the painter"},
    {"id": "w2", "type": "context", "kind": "work", "search": "Madonna of Chancellor Rolin Jan van Eyck", "alt": [], "what": "a related work"},
    {"id": "w3", "type": "map", "place": "Bruges, Belgium", "what": "a map of Bruges"},
    {"id": "w4", "type": "clip", "search": "canal boat Bruges", "alt": [], "what": "a clip of a canal"},
]
MAX_SEARCHES, MAX_THUMBS = 6, 2
count = {"search": 0, "thumb": 0}
work = Path(tempfile.mkdtemp(prefix="c3picks-real-", dir=str(REPO)))          # inside the snapshot folder
(work / "media").mkdir()


def real_search(pdir, query, beat, sources, limit, kind="image"):
    if count["search"] >= MAX_SEARCHES:
        raise SystemExit("refusing a seventh search")
    count["search"] += 1
    time.sleep(3)
    t0 = time.time()
    r = service.search(pdir, query, beat, sources, 4 if sources == ["met"] else limit, kind=kind)
    print("SEARCH %d: source=%s kind=%s query=%r -> %d result(s), %d error(s), %.1f s" % (count["search"], sources[0], kind, query, len(r["items"]), len(r["errors"]),
                                                                                        time.time() - t0))
    for e in r["errors"]:
        print("   error:", e)
    for it in r["items"][:4]:
        print("   - %s | %s | %sx%s | licence=%s | flag=%s | author=%s" % (it.get("source_id")[:70], (it.get("title") or "")[:50], it.get("width"), it.get("height"),
                                                                      it.get("licence") or "-", it.get("flag"), (it.get("author") or "")[:30]))
    return r


def thumb(pdir, cand, limited=None, clock=time.time):
    if count["thumb"] >= MAX_THUMBS:
        placeholder = Path(pdir) / "media" / "stand_in.jpg"
        if not placeholder.exists():
            import cv2
            import numpy as np
            cv2.imwrite(str(placeholder), np.full((48, 64, 3), 128, dtype=np.uint8))
        return "media/stand_in.jpg"                 # a stand-in so the candidate is kept in the printout; no request
    count["thumb"] += 1
    time.sleep(3)
    t0 = time.time()
    rel = asearch.default_fetch_thumb(pdir, cand, limited, clock)
    print("THUMB %d: %s %s -> %s (%.1f s)" % (count["thumb"], cand["source"], cand["source_id"][:50], rel or "none", time.time() - t0))
    if rel:
        from bti.picks.auto import images
        im = images.read(Path(pdir) / rel)
        print("   thumbnail stored at %d x %d (the picture the agent would be shown)" % (im.shape[1], im.shape[0]))
    return rel


wants = [{**w, "beat": "b0001", "n": i + 1} for i, w in enumerate(WANTS)]
state = None
state = asearch.run(work, {}, state, wants, main_key="A", cancelled=lambda: False, progress=lambda f, n: None, save=lambda s: None, search=real_search,
                    fetch_thumb=thumb)
print("\nWHAT THE SEARCH PART KEPT")
for wid, w in state["wants"].items():
    print("%s %-4s status=%-8s code=%s candidates=%d" % (wid, w["type"], w["status"], w.get("code"), len(w["candidates"])))
    for c in w["candidates"]:
        print("   n=%d %s | %s | %s | %s" % (c["n"], c["source"], c["source_id"][:60], (c["title"] or "")[:40], c["media"]))
print("\nsearches made: %d, thumbnails fetched: %d, limited sources: %s" % (count["search"], count["thumb"], state["limited"]))
