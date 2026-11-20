"""Round two of the web search of the automatic picks job (only when the owner's switch `auto_web_search` is on; see `bti.picks.websettings`).

The job's four parts (plan, search, choose, write) become six: after the first choosing session

    web      (code)   every wanted picture the session answered null, and every one that had no candidate, gets a web search (PAID, counted
                      against the run's budget) with its `search` and, when that gives nothing new, with its first alternative; queries a want
                      already had (round one) are not repeated. The new candidates are appended to the want (numbered on from its last one, `round`: 2)
    choose2  (model)  ONE more choosing session, which sees only those wants and only their NEW candidates (numbered 1..k on its own sheet)
                      -> cache/picks_auto/choice2.json

The write part reads the first choice and the second one as ONE choice (`merge_choice`): the second session's pick k of a want becomes the want's own
candidate number. A want that could not be searched because the budget was spent has its answer taken out of the merged choice and keeps the code
`web_budget` in the search state, so that the line says plainly why it has no picture (instead of "the agent found none fit").

Everything here is plain code; the only model call is the session the job starts for `choose2`. With the switch off none of this runs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from bti.picks import service as psvc

from . import search as asearch

PART_TITLES_WEB = {
    "plan": "Lập danh sách hình cần tìm (1/6)",
    "search": "Tìm hình (2/6)",
    "choose": "Chọn hình (3/6)",
    "web": "Tìm thêm trên web (4/6)",
    "choose2": "Chọn lại trong hình mới tìm (5/6)",
    "write": "Ghi vào chọn hình (6/6)",
}


def part_titles(web_on: bool, plain: dict) -> dict:
    """The part titles of a run: the plain four, or six when the web search is on (the numbers in the titles say so)."""
    return dict(PART_TITLES_WEB) if web_on else plain


def web_sentence(web: dict | None) -> str:
    """` Đã tìm trên web 12/80 lần.` for the closing sentence of a run that had the web search on; '' otherwise."""
    if not web or not web.get("on"):
        return ""
    return " Đã tìm trên web %d/%d lần." % (int(web.get("searches") or 0), int(web.get("max") or 0))


def cost_line(max_searches: int) -> str:
    """What the cost line of `picks.auto` adds while the switch is on: `, up to 80 web searches (You.com, paid)`."""
    return ", up to %d web searches (You.com)" % int(max_searches)


# ---------------------------------------------------------------------------------------------------------------- which wants
def first_look_null(choice: dict | None, wid: str) -> bool:
    ch = ((choice or {}).get("wants") or {}).get(wid)
    return ch is not None and ch.get("pick") is None


def wants_for_round_two(wants: list[dict], st: dict, choice: dict | None) -> list[dict]:
    """The context wants the web is searched again for: the ones the first session answered null and the ones that had no candidate."""
    out = []
    for want in wants:
        if want["type"] != "context":
            continue
        w = (st.get("wants") or {}).get(want["id"]) or {}
        if not w.get("candidates") or first_look_null(choice, want["id"]):
            out.append(want)
    return out


def second_wants(st: dict) -> list[str]:
    """The wants the second session sees (those that got new candidates in round two), sorted."""
    return sorted((st.get("round2") or {}).get("wants") or [])


def searched(st: dict) -> bool:
    return bool((st.get("round2") or {}).get("searched"))


# ---------------------------------------------------------------------------------------------------------------- the search
def search_round_two(pdir: Path, wants: list[dict], st: dict, choice: dict | None, *, main_key: str, web: asearch.Web, fetch_thumb, clock: Callable[[], float],
                     cancelled: Callable[[], bool], progress: Callable[[float, str], None], save: Callable[[dict], None],
                     search=None, wiki_search=None) -> dict:
    """The web search of round two. Updates `st` (new candidates on the wants, `st["round2"]`, `st["web"]`) and saves it after every want; a cancel
    leaves `round2.searched` false so that a resumed run goes on (the queries already made are not made again). Returns `st`."""
    r2 = st.setdefault("round2", {"searched": False, "wants": [], "map": {}, "budget": []})
    if r2.get("searched"):
        return st
    todo = wants_for_round_two(wants, st, choice)
    cap = asearch.PER_WANT_WEB
    search_fn = search or psvc.search
    wiki_fn = wiki_search or psvc.search
    for i, want in enumerate(todo):
        if cancelled():
            return st
        wid = want["id"]
        w = st["wants"][wid]
        if wid in r2["wants"] or wid in r2["budget"]:
            continue                                                                   # done by the attempt this run resumes
        progress(i / max(1, len(todo)), "Đang tìm thêm trên web %d/%d: %s" % (i + 1, len(todo), (w.get("what") or "")[:60]))
        existing = {(c["source"], c["source_id"]) for c in w.get("candidates") or []}
        kept: list[dict] = []
        w.pop("web_short", None)
        wider = want.get("wider")

        # 1. The web search of the thing itself (its 'search', then its first 'alt')
        done_q = set((w.get("web") or {}).get("queries") or [])
        alt = (want.get("alt") or [None])[0]
        queue = [q for q in dict.fromkeys([want.get("search"), alt]) if q and q not in done_q]
        step1_cap = 4 if wider else cap
        for q in queue:
            ask, by_source, _seen, skipped, _failed = asearch.make_asker(
                pdir, want, st, main_key=main_key, search=search_fn, clock=clock, cancelled=cancelled,
                round_no=2, seen=set(existing)
            )
            if web_search_for(pdir, w, st, web, q, ask, clock, skipped) < 0:
                break                                                                  # the web is not usable, the budget is spent or it asked us to wait
            pool = asearch._interleave(by_source, step1_cap + asearch.SPARE_WEB)
            step1_kept, _no_thumb = asearch.pick_with_thumbs(
                pdir, want, pool, step1_cap, fetch_thumb=fetch_thumb, limited=st["limited"], clock=clock, cancelled=cancelled
            )
            if cancelled():
                return st
            if step1_kept:
                kept.extend(step1_kept)
                existing.update((c["source"], c["source_id"]) for c in step1_kept)
                break                                                                  # something new: the alternative is not needed

        # 2. Then step 2 and step 3 (if wider is present and budget/slots remain)
        if wider:
            remaining = max(0, 8 - len(kept))
            for step_info in wider:
                if remaining <= 0:
                    break
                step_cap = min(4, remaining)
                step_no = int(step_info.get("step") or 2)
                step_q = step_info.get("search") or ""
                step_kind = step_info.get("kind") or "other"
                if not step_q:
                    continue
                step_want = {**want, "type": "context", "kind": step_kind, "search": step_q, "step": step_no}
                step_sources = asearch.sources_for(step_want)
                ask, by_source, _seen, skipped, _failed = asearch.make_asker(
                    pdir, step_want, st, main_key=main_key, search=search_fn, wiki_search=wiki_fn,
                    clock=clock, cancelled=cancelled, round_no=2, seen=set(existing), step=step_no
                )
                if not cancelled():
                    ask("wikipedia", step_q, asearch.WIKI_LIMIT)
                for src in step_sources:
                    if cancelled():
                        return st
                    ask(src, step_q, asearch.FIRST_LIMIT)
                if web is not None and web.usable() and sum(len(v) for v in by_source.values()) < asearch.ENOUGH:
                    if not cancelled():
                        web_search_for(pdir, w, st, web, step_q, ask, clock, skipped)
                by_source = asearch._order(by_source)
                extra = any(k in by_source for k in ("wikipedia", "web"))
                pool = asearch._interleave(by_source, step_cap + (asearch.SPARE_WEB if extra else 0))
                step_kept, _no_thumb = asearch.pick_with_thumbs(
                    pdir, step_want, pool, step_cap, fetch_thumb=fetch_thumb, limited=st["limited"], clock=clock, cancelled=cancelled
                )
                if cancelled():
                    return st
                if step_kept:
                    for c in step_kept:
                        c["step"] = step_no
                    kept.extend(step_kept)
                    existing.update((c["source"], c["source_id"]) for c in step_kept)
                    remaining = max(0, remaining - len(step_kept))
        if kept:
            first = max([int(c.get("n") or 0) for c in w.get("candidates") or []] or [0])
            for k, c in enumerate(kept, 1):
                c["n"] = first + k
            w["candidates"] = list(w.get("candidates") or []) + kept
            w.update({"status": "found", "code": None, "source": None, "seconds": None})
            r2["wants"].append(wid)
            r2["map"][wid] = [c["n"] for c in kept]
        else:
            if w.get("web_short"):
                r2["budget"].append(wid)
                w["code"] = "web_budget"
            else:
                w["code"] = "no_candidates"
            if not w.get("candidates"):
                w.update({"status": "none"})
        if web is not None:
            st["web"] = web.public()
        save(st)
    r2["searched"] = True
    if web is not None:
        st["web"] = web.public()
    save(st)
    return st


def web_search_for(pdir: Path, w: dict, st: dict, web: asearch.Web | None, query: str, ask, clock, skipped: dict) -> int:
    """One counted web search for the want state `w`; the candidates go to `ask`'s sheet. -1: no search was made."""
    if web is None or not web.usable():
        return -1
    return asearch.web_ask(pdir, w, st, web, query, ask_take=ask.take, clock=clock, skipped=skipped)


# ---------------------------------------------------------------------------------------------------------------- the second session
def second_search_view(st: dict, choice: dict | None) -> dict:
    """The search state the second session is built from: only the wants that got new candidates, each with ONLY its new candidates numbered 1..k,
    and what the first session said about it (`earlier`)."""
    r2 = st.get("round2") or {}
    wants = {}
    for wid in second_wants(st):
        w = st["wants"][wid]
        new = [dict(c) for c in w.get("candidates") or [] if c.get("round") == 2]
        for k, c in enumerate(new, 1):
            c["n"] = k
        ch = ((choice or {}).get("wants") or {}).get(wid)
        wants[wid] = {**w, "candidates": new, "earlier": (ch or {}).get("reason") or ""}
    return {**{k: v for k, v in st.items() if k not in ("wants", "round2")}, "wants": wants, "books": []}


def merge_choice(choice: dict | None, second: dict | None, st: dict) -> dict:
    """The first choice and the second one as ONE choice for the write part (see the module's words)."""
    base = choice or {"wants": {}, "regions": {}}
    out = {**base, "wants": dict(base.get("wants") or {})}
    r2 = st.get("round2") or {}
    for wid, ch in ((second or {}).get("wants") or {}).items():
        pick = ch.get("pick")
        if pick and pick[0] == "c":
            mapping = (r2.get("map") or {}).get(wid) or []
            pick = ("c", mapping[pick[1] - 1]) if 1 <= pick[1] <= len(mapping) else None
        out["wants"][wid] = {"pick": pick, "reason": ch.get("reason") or ""}
    for wid in r2.get("budget") or []:
        out["wants"].pop(wid, None)                                                    # the line says `web_budget`, not "the agent found none fit"
    return out
