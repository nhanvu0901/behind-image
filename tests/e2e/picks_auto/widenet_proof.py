"""Real network proof for worker widenet on the 9 wants of project eligius that had no picture in the first run.
Runs on the Windows server via tools/deploy/snapshot_py.sh widenet tests/e2e/picks_auto/widenet_proof.py.

Rules kept:
- Free sources only: Wikipedia, Commons, Met.
- No You.com (web source is NOT used).
- At most 120 requests in all (API + thumbnails), >= 1.0 s pacing per host.
- Generic User-Agent: ImageResearch/1.0
- Step 2 searched first; if candidates found, stop at Step 2; else step 3.
- Generates contact sheets in .scratch/widenet/sheets/sheet_<beat>.jpg.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
os.environ.pop("BTI_NO_REAL_MODELS", None)
os.environ["BTI_REAL_NETWORK_PROOF"] = "1"

from bti.media import api, http
from bti.picks import service as psvc
from bti.picks.auto import images, search as asearch, webround

assert http.USER_AGENT.startswith("ImageResearch/") and "behind" not in http.USER_AGENT.lower()

MAX_REQUESTS = 120
PER_SHEET = 8
OUT_DIR = REPO / ".scratch" / "widenet" / "sheets"
REPORT_FILE = REPO / ".scratch" / "widenet" / "report_proof.json"

state = {"thumbs": 0, "api_requests": 0}

WANTS_DATA = [
    {
        "id": "b0007.1",
        "beat": "b0007",
        "n": 1,
        "type": "context",
        "kind": "document",
        "period": "then",
        "search": "statutes of medieval goldsmiths guild Netherlandish towns 14th century",
        "what": "Điều lệ phường thợ kim hoàn thế kỷ 14",
        "wider": [
            {"step": 2, "search": "medieval guild charter manuscript illuminated 15th century", "kind": "document", "what": "Bản thảo điều lệ phường hội thế kỷ 15"},
            {"step": 3, "search": "medieval guild seal chest brass museum", "kind": "object", "what": "Hòm hoặc con dấu phường hội thế kỷ 15 trong bảo tàng"},
        ],
    },
    {
        "id": "b0008.1",
        "beat": "b0008",
        "n": 1,
        "type": "context",
        "kind": "work",
        "period": "then",
        "search": "Hanse merchants weighing goods Bruges 1282",
        "what": "Thương nhân Hanse cân hàng hóa ở Bruges",
        "wider": [
            {"step": 2, "search": "merchants weighing goods miniature 15th century", "kind": "work", "what": "Tranh tiểu họa thương nhân cân hàng thế kỷ 15"},
            {"step": 3, "search": "medieval balance scales nested weights museum", "kind": "object", "what": "Cân tiểu ly và quả cân lồng thời trung cổ trong bảo tàng"},
        ],
    },
    {
        "id": "b0016.1",
        "beat": "b0016",
        "n": 1,
        "type": "context",
        "kind": "work",
        "period": "then",
        "search": "Saint Eligius patron of blacksmiths goldsmiths banner Bruges",
        "what": "Thánh Eligius bổn mạng thợ rèn và thợ kim hoàn",
        "wider": [
            {"step": 2, "search": "Saint Eligius in goldsmith workshop 15th century miniature", "kind": "work", "what": "Tiểu họa Thánh Eligius trong xưởng kim hoàn thế kỷ 15"},
            {"step": 3, "search": "medieval goldsmith guild banner badge museum", "kind": "object", "what": "Huy hiệu hoặc cờ hiệu phường thợ kim hoàn trong bảo tàng"},
        ],
    },
    {
        "id": "b0021.1",
        "beat": "b0021",
        "n": 1,
        "type": "context",
        "kind": "work",
        "period": "then",
        "search": "Saint Godeberta receiving gold ring Saint Eligius",
        "what": "Thánh Godeberta nhận nhẫn từ Thánh Eligius",
        "wider": [
            {"step": 2, "search": "Saint Godeberta manuscript illumination medieval", "kind": "work", "what": "Tiểu họa bản thảo về Thánh Godeberta"},
            {"step": 3, "search": "merovingian gold ring museum 7th century", "kind": "object", "what": "Nhẫn vàng thời Merovingian trong bảo tàng"},
        ],
    },
    {
        "id": "b0026.1",
        "beat": "b0026",
        "n": 1,
        "type": "context",
        "kind": "object",
        "period": "then",
        "search": "cavalier d'or Philip the Good gold rider coin Burgundy",
        "what": "Đồng tiền vàng cavalier d'or của Philip the Good",
        "wider": [
            {"step": 2, "search": "Burgundian coin", "kind": "object", "what": "Đồng tiền thời Burgundy thế kỷ 15"},
            {"step": 3, "search": "medieval gold coin museum", "kind": "object", "what": "Đồng tiền vàng thời trung cổ trong bảo tàng"},
        ],
    },
    {
        "id": "b0028.1",
        "beat": "b0028",
        "n": 1,
        "type": "context",
        "kind": "work",
        "period": "then",
        "search": "harbour of Sluis 1457 caravels Venetian galleys",
        "what": "Cảng biển Sluis năm 1457",
        "wider": [
            {"step": 2, "search": "medieval port harbor manuscript", "kind": "work", "what": "Tiểu họa cảnh cảng biển buôn bán thời trung cổ"},
            {"step": 3, "search": "caravel ship model museum", "kind": "object", "what": "Mô hình thuyền buồm caravel trong bảo tàng"},
        ],
    },
    {
        "id": "b0030.1",
        "beat": "b0030",
        "n": 1,
        "type": "context",
        "kind": "work",
        "period": "then",
        "search": "Burgundian salt cellar sirens 900 ducats",
        "what": "Hũ muối trang trí người cá 900 ducats",
        "wider": [
            {"step": 2, "search": "saltcellar 15th century miniature", "kind": "work", "what": "Tranh tiểu họa hũ muối vàng trên bàn tiệc thế kỷ 15"},
            {"step": 3, "search": "medieval saltcellar silver gold museum", "kind": "object", "what": "Hũ muối vàng hoặc bạc thời trung cổ trong bảo tàng"},
        ],
    },
    {
        "id": "b0031.1",
        "beat": "b0031",
        "n": 1,
        "type": "context",
        "kind": "object",
        "period": "then",
        "search": "Burgundian ducal treasure travelling gold chains jewelled boxes",
        "what": "Kho báu triều đình Burgundy dây chuyền vàng hộp trang sức",
        "wider": [
            {"step": 2, "search": "Burgundian court treasury miniature", "kind": "work", "what": "Tiểu họa kho báu và đồ trang sức triều đình Burgundy thế kỷ 15"},
            {"step": 3, "search": "15th-century gold chain reliquary museum", "kind": "object", "what": "Dây chuyền vàng hoặc tráp nạm đá quý thế kỷ 15 trong bảo tàng"},
        ],
    },
    {
        "id": "b0046.1",
        "beat": "b0046",
        "n": 1,
        "type": "context",
        "kind": "work",
        "period": "then",
        "search": "falconry Burgundian court 15th century",
        "what": "Cảnh săn chim ưng của triều đình Burgundy thế kỷ 15",
        "wider": [
            {"step": 2, "search": "Falconry", "kind": "work", "what": "Tiểu họa cảnh săn chim ưng thời trung cổ"},
            {"step": 3, "search": "falconry hood museum", "kind": "object", "what": "Mũ chụp chim ưng trong bảo tàng"},
        ],
    },
]


def total_requests() -> int:
    wiki = api.get_source("wikipedia")
    wiki_req = getattr(wiki, "requests", 0)
    return state["api_requests"] + wiki_req + state["thumbs"]


def counting_search(pdir, query, beat, sources, limit, kind="image"):
    if total_requests() >= MAX_REQUESTS:
        print("   [LIMIT] Max requests reached (%d), skipping search for %r" % (MAX_REQUESTS, query))
        return {"query": query, "items": [], "errors": []}
    state["api_requests"] += 1
    # Only allow free sources: wikipedia, commons, met
    allowed = [s for s in sources if s in ("wikipedia", "commons", "met")]
    res = psvc.search(pdir, query, beat, allowed, limit, kind=kind)
    items = res.get("items", [])
    print(f"   [SEARCH] {beat} {query!r} via {allowed} -> {len(items)} items")
    return res


def counting_wiki_search(pdir, query, beat, sources, limit, kind="image"):
    if total_requests() >= MAX_REQUESTS:
        print("   [LIMIT] Max requests reached (%d), skipping wiki search for %r" % (MAX_REQUESTS, query))
        return {"query": query, "items": [], "errors": []}
    res = psvc.search(pdir, query, beat, ["wikipedia"], limit, kind=kind)
    items = res.get("items", [])
    print(f"   [WIKI] {beat} {query!r} -> {len(items)} items")
    return res


def counting_fetch_thumb(pdir, cand, limited=None, clock=time.time):
    if total_requests() >= MAX_REQUESTS:
        print("   [LIMIT] Max requests reached (%d), skipping thumb for %s" % (MAX_REQUESTS, cand.get("source_id")))
        return None
    dest = asearch.store.thumb_path(pdir, cand["source"], cand["source_id"])
    cached = dest.is_file()
    rel = asearch.default_fetch_thumb(pdir, cand, limited, clock)
    if not cached and rel:
        state["thumbs"] += 1
    return rel


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdir = REPO / ".scratch" / "widenet" / "proj"
    (pdir / "media").mkdir(parents=True, exist_ok=True)

    asearch.PER_WANT = PER_SHEET
    asearch.PER_WANT_WEB = PER_SHEET
    asearch.SPARE_WEB = 0

    st = asearch.new_state()
    for w in WANTS_DATA:
        st["wants"][w["id"]] = asearch._new_want(w)

    print("=== STARTING WIDENET PROOF ON 9 WANTS (MAX_REQUESTS=%d) ===" % MAX_REQUESTS)
    t0_all = time.time()

    # Run round two search with web disabled (free sources only)
    web_obj = asearch.Web(on=False, max=0, spent=0)
    st = webround.search_round_two(
        pdir,
        WANTS_DATA,
        st,
        choice=None,  # No first round choice -> searches all wants
        main_key="none",
        web=web_obj,  # NO paid web search!
        fetch_thumb=counting_fetch_thumb,
        clock=time.time,
        cancelled=lambda: False,
        progress=lambda p, msg: print("Progress [%.0f%%]: %s" % (p * 100, msg)),
        save=lambda s: None,
        search=counting_search,
        wiki_search=counting_wiki_search,
    )

    report = []
    print("\n=== RESULTS SUMMARY ===")
    for w in WANTS_DATA:
        wid = w["id"]
        res = st["wants"][wid]
        cands = res.get("candidates") or []
        step_found = cands[0].get("step") if cands else None
        print(f"\n[{wid}] {w['beat']} | {w['what']}")
        print(f"   Status: {res.get('status')} | Code: {res.get('code')} | Found: {len(cands)} candidates at Step {step_found}")

        tiles = []
        c_report = []
        for c in cands:
            step_no = c.get("step")
            src = c.get("source")
            sid = c.get("source_id")
            title = c.get("page_title") or c.get("title") or sid
            w_px, h_px = c.get("width"), c.get("height")
            lic = c.get("licence")
            author = c.get("author") or ""
            thumb_path = (pdir / c["thumb"]) if c.get("thumb") else None
            tiles.append((f"{c['n']} (S{step_no})", thumb_path))
            print(f"   - #{c['n']} [Step {step_no}] ({src}) {title[:60]} | {w_px}x{h_px} | Lic: {lic} | {author[:25]}")
            c_report.append({
                "n": c.get("n"),
                "step": step_no,
                "source": src,
                "source_id": sid,
                "title": title,
                "width": w_px,
                "height": h_px,
                "licence": lic,
                "author": author,
                "snippet": c.get("snippet"),
                "url": c.get("url") or c.get("page_url"),
            })

        if tiles:
            sheet_dest = OUT_DIR / f"sheet_{w['beat']}.jpg"
            images.contact_sheet(tiles, sheet_dest)
            print(f"   -> Saved contact sheet: {sheet_dest}")

        report.append({
            "id": wid,
            "beat": w["beat"],
            "what": w["what"],
            "status": res.get("status"),
            "step_found": step_found,
            "candidate_count": len(cands),
            "candidates": c_report,
        })

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    dt_all = time.time() - t0_all
    print(f"\n=== PROOF FINISHED in {dt_all:.1f}s ===")
    print(f"Total requests used: {total_requests()} / {MAX_REQUESTS} (Thumbs: {state['thumbs']}, API: {state['api_requests']})")
    print(f"Report written to: {REPORT_FILE}")


if __name__ == "__main__":
    main()
