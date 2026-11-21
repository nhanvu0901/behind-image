"""Part 4 of the automatic picks job: write what was chosen, through the typed operations of `bti.ops` (docs/OPS.md), in batches.

    regions     one batch: `set_region` for every box that was kept or adjusted (a name that the painting already has with the same
                box is reused, a name that is taken by another box becomes NAME_2: an existing region is never overwritten)
    chapters    one batch per chapter: the `import` operations for the pictures that chapter uses (each with a ref), then `set_picks` or
                `skip_beat` for each line, written with `$ref`s. The actor is `agent:<model id>`, the note says what the batch is, and the
                reason of the line (the plan's) is the `reason` of `set_picks`, which the document keeps as the note of the line.

So every write is a batch of the change log, and the newest ones can be undone. Pictures are downloaded BEFORE the batches (outside any
lock, each one alone, so that one source that refuses does not sink a chapter); the `import` operation then finds them in the project's
index and costs nothing. A line whose pictures could not all be had is written with the ones that were, and says what is missing in its
note and in the line's `missing` (`{what, code}`). A line about something outside the painting whose picture was not found at all (no candidates,
or the choosing session answered null) is written with its plan's `fallback` (the part of the painting it named) and the same `missing`, never left
unwritten; a line of an older plan, which names no fallback, with nothing found is left as it was and listed. Every line is written with its `kinds`
(a plan saved before they existed has none, and then none are written). This module never approves anything.
"""
from __future__ import annotations

import copy
import re
import time
from pathlib import Path
from typing import Callable

from bti.media import contentbox as pcb          # panelbox: the painted area of the main painting
from bti.ops import OpError
from bti.ops import runner as ops_runner
from bti.ops.adapters import PicksAdapter
from bti.ops.log import ChangeLog
from bti.picks import doc as pdoc
from bti.picks import service as psvc
from bti.picks.errors import PicksError

from . import inputs as ainputs
from . import search as asearch
from . import shapes, store, texts, tighten

# The write part's own deadline: 25 minutes, as before, and it still fits. It was set for a part that took about 2 minutes. Downloads are now polite
# (`bti.media.http.polite`: a Commons picture is 3 requests, so 3 s apart at the least, then its transfer: up to 60 pictures is about 6 minutes) and patient
# (a host that answers "too many requests" is waited for: 10 + 30 + 90 s, or what it asks, up to 120 s a time, so 2 to 6 minutes for the picture it happens to;
# the first picture that is still refused after those tries closes its source for the rest of the part). That is 6 + 6 + the batches (a few minutes) = about
# 15 minutes in the worst honest case. The deadline is only looked at before each download, and the long-job manager stops a whole part at 35 minutes
# (`bti.longjob.manager.PART_LIMIT_SECONDS`): 25 minutes + the one download that is waiting when the deadline comes (6 minutes at the most) + the batches stay
# inside it, 30 would not.
WRITE_SECONDS = 25 * 60
NOTE_MAX = 400


class WriteError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _cut(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _role(it: dict) -> str:
    if it["type"] == "map":
        return "map"
    if it["type"] == "clip":
        return "video"
    return "document" if it.get("kind") == "document" else "context"


# ---------------------------------------------------------------------------------------------------------------- resolve the choices
def resolve_picks(plan: dict, search: dict, choice: dict, books: list[dict]) -> dict:
    """`want id -> {"pick": {"source", "source_id"} | None, "reason", "code", ...}` from the choice and the search."""
    out: dict[str, dict] = {}
    by_book = {b["n"]: b for b in books}
    for ln in plan["lines"]:
        for n, it in enumerate(ln["show"], 1):
            if it["type"] not in ("context", "map", "clip"):
                continue
            wid = "%s.%d" % (ln["beat"], n)
            w = (search.get("wants") or {}).get(wid) or {}
            ch = (choice.get("wants") or {}).get(wid)
            row = {"id": wid, "beat": ln["beat"], "item": it, "pick": None, "reason": "", "code": None, "source": w.get("source"),
                   "seconds": w.get("seconds"), "what": it.get("what") or it.get("place") or ""}
            if ch is None:                                       # the want was not shown to the agent: nothing was found for it
                row["code"] = w.get("code") or "no_candidates"
            elif ch["pick"] is None:
                row.update({"code": "agent_none", "reason": ch["reason"]})
            else:
                kind, k = ch["pick"]
                if kind == "c":
                    cand = next((c for c in w.get("candidates") or [] if c["n"] == k), None)
                    if cand:
                        row.update(pick={"source": cand["source"], "source_id": cand["source_id"], "media": cand.get("media")}, reason=ch["reason"])
                        if cand.get("step") in (2, 3):
                            row["step"] = cand["step"]
                else:
                    b = by_book.get(k)
                    if b:
                        row.update(pick={"source": "book", "source_id": b["source_id"], "media": "image"}, reason=ch["reason"])
                if row["pick"] is None:
                    row["code"] = "agent_none"
            out[wid] = row
    return out



def resolve_names(plan: dict, picks: dict, got: dict, regions: dict, dropped: set) -> list[dict]:
    """Translate a plan's region/want references to the pictures actually kept."""
    out = []
    for entry in plan.get("names") or []:
        where = entry["where"]
        if "region" in where:
            old = where["region"]
            target = regions.get(old, old)
            if old in dropped or target is None:
                continue
            target_where = {"region": target}
        else:
            picked = (picks.get(where.get("want")) or {}).get("pick")
            key = (picked["source"], picked["source_id"]) if picked else None
            target = got.get(key)
            if not target:
                continue
            target_where = {"asset": target}
        row = copy.deepcopy(entry)
        row["where"] = target_where
        out.append(row)
    return out

def final_regions(plan: dict, choice: dict) -> tuple[dict, list[str]]:
    """The boxes to make/update: `name -> {...}` (`tight` stored pixels when confirmed, else rough fractional box), and the names dropped."""
    keep, dropped = {}, []
    ch_regions = choice.get("regions") or {}
    seen_names = list(plan.get("regions") or {})
    for n in ch_regions:
        if n not in plan.get("regions", {}):
            seen_names.append(n)
    for name in seen_names:
        pr = (plan.get("regions") or {}).get(name)
        ch = ch_regions.get(name)
        if ch and ch.get("action") == "drop":
            dropped.append(name)
            continue
        if ch and ch.get("action") == "tight":
            if ch.get("confirmed") is True and ch.get("stored_box"):
                keep[name] = {
                    "stored_box": list(ch["stored_box"]),
                    "tight": True,
                    "thing": ch.get("thing") or (pr or {}).get("thing") or "",
                    "rough": list(ch["rough_px"]) if ch.get("rough_px") else None,
                    "what": ch.get("what") or (pr or {}).get("what") or "",
                    "existing": bool(ch.get("existing") and pr is None),
                }
            elif ch.get("existing") and pr is None:
                # Existing region on the main painting was never confirmed on the check sheet: leave it unchanged (not tight).
                continue
            elif pr is not None:
                # Newly planned region never confirmed on the check sheet: store rough box WITHOUT tight: true.
                keep[name] = {
                    "box": pr["box"],
                    "what": pr["what"],
                    **({"thing": pr["thing"]} if pr.get("thing") else {}),
                    "tight": False,
                }
            continue
        if pr is not None:
            ch_or_keep = ch or {"action": "keep", "box": None}
            keep[name] = {
                "box": ch_or_keep["box"] if ch_or_keep.get("action") == "adjust" and ch_or_keep.get("box") else pr["box"],
                "what": pr["what"],
                **({"thing": pr["thing"]} if pr.get("thing") else {}),
            }
    return keep, dropped


# ---------------------------------------------------------------------------------------------------------------- downloads
def download_all(pdir: Path, picks: dict, *, fetch_asset, cancelled, clock, deadline: float, progress) -> tuple[dict, dict]:
    """Bring every chosen picture into the project's media (not into picks.json yet). -> (`{(source, id): asset key}`,
    `{(source, id): (code, detail, source name, seconds)}` for the ones that could not be had).

    One at a time, and polite: `fetch_asset` (`bti.picks.service.fetch_asset`) goes through `bti.media.api.import_candidate`, which sends at most one request a
    second to a host and waits out a "too many requests" (what the host asks, else 10, 30, 90 s) before it gives up on a picture. A picture that is still
    refused after that closes its source for the rest of this part (the host said no three times: asking for more pictures would only be rude): the others of
    that source are listed as `import_limited` without a request, and `picks.retry_missing` imports them later, from the files of this run."""
    got: dict = {}
    failed: dict = {}
    closed: dict = {}                                            # source -> the seconds it asked us to wait, once a picture of it was refused for good
    todo = list(dict.fromkeys((p["pick"]["source"], p["pick"]["source_id"]) for p in picks.values() if p["pick"]))
    for k, (src, sid) in enumerate(todo, 1):
        if cancelled():
            break
        if clock() > deadline:
            failed[(src, sid)] = ("time_up", "", None, None)
            continue
        if src in closed:
            failed[(src, sid)] = ("import_limited", "", asearch.SOURCE_VI.get(src, src), closed[src])
            continue
        progress(k - 1, len(todo), "Đang tải hình %d/%d" % (k, len(todo)))
        try:
            res = fetch_asset(pdir, src, sid)
            got[(src, sid)] = res["asset_key"]
        except PicksError as e:
            if e.code == "source_rate_limited":
                wait = int(e.extra.get("retry_after") or asearch.DEFAULT_WAIT)
                closed[src] = wait
                failed[(src, sid)] = ("import_limited", "", asearch.SOURCE_VI.get(src, src), wait)
            else:
                failed[(src, sid)] = ("import_failed", e.code or "", asearch.SOURCE_VI.get(src, src), None)
        except FileNotFoundError:
            raise WriteError("project_gone", "the project folder is gone")
        except Exception as e:      # noqa: BLE001 - one picture that cannot be had never stops the rest
            failed[(src, sid)] = ("import_failed", type(e).__name__, asearch.SOURCE_VI.get(src, src), None)
    return got, failed


# ---------------------------------------------------------------------------------------------------------------- the lines
def region_ops(main_key: str, main_asset: dict, keep: dict, width: int, height: int) -> tuple[list[dict], dict, int]:
    """`set_region` operations for the kept boxes, the names to use in the lines (`plan name -> final name`) and how many are new.
    A region the painting already has under that name with the same place is reused; an existing non-tight region tightened by the second look is
    updated in place; under another place a new region gets NAME_2.

    panelbox: fractional plan boxes are cut to `content_box` (`bti.media.contentbox`); boxes of which under half lies inside the painted area
    map to None (lines show whole painting). Tight boxes come from cut-outs already clamped to `content_box` and store `tight`, `thing`, `rough`."""
    have = dict(main_asset.get("regions") or {})
    taken = set(have)
    ops, names, made = [], {}, 0
    box = pcb.box_of(main_asset)
    for name, r in keep.items():
        extra: dict = {}
        if r.get("tight") is True and r.get("stored_box"):
            want = tighten.stored_box_to_region(r["stored_box"])
            extra["tight"] = True
            if r.get("thing"):
                extra["thing"] = _cut(r["thing"], pdoc.THING_MAX)
            if r.get("rough") and len(r["rough"]) == 4:
                extra["rough"] = [int(v) for v in r["rough"]]
        else:
            want = shapes.box_to_region(r["box"], width, height)
            if r.get("thing"):
                extra["thing"] = _cut(r["thing"], pdoc.THING_MAX)
        if box is not None:
            fitted = pcb.clamp_region(want, box)
            if fitted is None:
                names[name] = None
                continue
            want = {k: fitted[k] for k in ("x", "y", "rx", "ry")}
        if r.get("existing") and name in have:
            names[name] = name
            made += 1
            lbl = _cut(r.get("what") or have[name].get("label") or "", 80)
            ops.append({"op": "set_region", "asset": main_key, "region": name, **want, "label": lbl, **extra})
            continue
        same = next((n for n, h in have.items() if re.fullmatch(re.escape(name) + r"(_\d+)?", n)
                     and bool(h.get("tight")) == bool(extra.get("tight"))
                     and all(abs(int(h.get(k) or 0) - want[k]) <= 2 for k in ("x", "y", "rx", "ry"))), None)
        if same:
            names[name] = same
            continue
        final = shapes.region_name(name, taken)
        taken.add(final)
        names[name] = final
        made += 1
        ops.append({"op": "set_region", "asset": main_key, "region": final, **want, "label": _cut(r.get("what") or "", 80), **extra})
    return ops, names, made


def build_lines(inp: ainputs.Inputs, plan: dict, picks: dict, got: dict, failed: dict, names: dict, dropped: list[str], lost: set) -> list[dict]:
    """For each line of the plan: what to write (`items`), what is missing and why. A box the agent dropped (`dropped`, said in the line's
    notes) or that could not be made (`lost`) shows the whole painting instead."""
    lines = []
    for ln in plan["lines"]:
        b = inp.beat(ln["beat"])
        items, missing, notes = [], [], []

        def whole():
            if not any(i["asset"] == "main" and not i["region"] for i in items):
                items.append({"asset": "main", "region": None, "role": "main", "note": ""})

        def painting(it: dict) -> None:
            """A `whole` or `detail` item of the plan (a line's own, or its fallback) as an item of the picks."""
            if it["type"] == "whole":
                whole()
            elif it["region"] in dropped:
                notes.append(texts.why("box_dropped", what=it["region"]))
                whole()
            elif it["region"] in lost:
                whole()
            else:
                items.append({"asset": "main", "region": names.get(it["region"], it["region"]), "role": "detail", "note": ""})
        for n, it in enumerate(ln["show"], 1):
            if it["type"] in ("whole", "detail"):
                painting(it)
            else:
                p = picks["%s.%d" % (ln["beat"], n)]
                if p["pick"]:
                    key = (p["pick"]["source"], p["pick"]["source_id"])
                    if key in got:
                        note = p["reason"]
                        if it["type"] == "clip":
                            note = "%s (clip khoảng %g giây)" % (p["reason"], it["seconds"])
                        item_dict = {"src": key, "asset": None, "region": None, "role": _role(it), "note": _cut(note, NOTE_MAX)}
                        if p.get("step") in (2, 3):
                            item_dict["step"] = p["step"]
                        items.append(item_dict)
                        continue
                    code, detail, source, secs = failed.get(key, ("import_failed", "", None, None))
                    missing.append({"want": p["id"], "what": p["what"], "code": code,
                                    "why": texts.why(code, what=p["what"], source=source or "", seconds=secs, detail=detail)})
                else:
                    missing.append({"want": p["id"], "what": p["what"], "code": p["code"] or "no_candidates",
                                    "why": texts.why(p["code"] or "no_candidates", what=p["what"], source=p.get("source") or "", seconds=p.get("seconds"),
                                                     detail=p["reason"])})
        fallback = ln.get("fallback")
        if fallback and ln["show"] and not items:                  # nothing asked for was found: the line shows the part of the painting its plan named
            painting(fallback)
        lines.append({"beat": ln["beat"], "no": b["no"], "chapter": b["chapter"], "reason": ln["reason"], "show": ln["show"], "items": items,
                      "missing": missing, "notes": notes, "kinds": list(ln.get("kinds") or [])})
    return lines


def line_note(line: dict) -> str:
    note = line["reason"]
    if line["missing"]:
        note += " Chưa tìm được: " + "; ".join(m["what"] for m in line["missing"]) + "."
    return _cut(note, NOTE_MAX)


# ---------------------------------------------------------------------------------------------------------------- the batches
class Writer:
    def __init__(self, pdir: Path, actor: str, *, redo: bool):
        self.pdir, self.actor, self.redo = Path(pdir), actor, redo
        self.adapter = PicksAdapter(self.pdir)
        self.log = ChangeLog(self.pdir)
        self.batches: list[str] = []
        self.created_assets = 0

    def send(self, ops: list[dict], note: str) -> dict:
        """One batch. A stale revision (the owner saved meanwhile) is read again once; any other refusal is raised as the `OpError` it is."""
        for attempt in (1, 2):
            _, rev = self.adapter.read()
            try:
                res = ops_runner.run_batch(self.adapter, {"base_rev": rev, "actor": self.actor, "ops": ops, "note": note[:2000]}, self.log)
            except OpError as e:
                if e.code == "stale_revision" and attempt == 1:
                    continue
                raise
            if res.get("batch"):
                self.batches.append(res["batch"])
            self.created_assets += len((res.get("created") or {}).get("assets") or [])
            return res
        raise WriteError("write_refused", "the picks kept changing while they were written")

    def settled(self, bid: str) -> bool:
        """Is this line already settled by someone else (the owner, meanwhile)? Then it is left as it is (unless the request said redo)."""
        return (not self.redo) and ainputs.has_pictures(pdoc.load_or_new(self.pdir), bid)


def _ops_for(lines: list[dict], main_key: str) -> list[dict]:
    """The operations of a group of lines: the imports (one ref per picture), then `set_picks` / `skip_beat` for each line."""
    ops, refs = [], {}
    for ln in lines:
        for it in ln["items"]:
            if it.get("src") and it["src"] not in refs:
                refs[it["src"]] = "p%d" % (len(refs) + 1)
                ops.append({"op": "import", "source": it["src"][0], "source_id": it["src"][1], "ref": refs[it["src"]]})
    for ln in lines:
        kinds = {"kinds": list(ln["kinds"])} if ln.get("kinds") else {}
        if "names" in ln:
            kinds["names"] = ln["names"]
        if not ln["show"]:
            ops.append({"op": "skip_beat", "beat": ln["beat"], "reason": _cut(ln["reason"], NOTE_MAX), **kinds})
            continue
        items = []
        for it in ln["items"]:
            asset = main_key if it["asset"] == "main" else "$" + refs[it["src"]]
            item_data = {"asset": asset, "region": it["region"], "role": it["role"], **({"note": it["note"]} if it["note"] else {})}
            if it.get("step") in (2, 3):
                item_data["step"] = it["step"]
            items.append(item_data)
        ops.append({"op": "set_picks", "beat": ln["beat"], "items": items, "reason": line_note(ln), **kinds,
                    "missing": [{"what": _cut(m["what"], pdoc.MISSING_WHAT_MAX), "code": m["code"]} for m in ln["missing"][:pdoc.MAX_MISSING]]})
    return ops


def run(pdir: Path, inp: ainputs.Inputs, plan: dict, search: dict, choice: dict, run_state: dict, *, actor: str, cancelled: Callable[[], bool],
        progress: Callable[[float, str], None], save_run: Callable[[dict], None] | None = None, fetch_asset=None,
        clock: Callable[[], float] = time.time, budget_s: float = WRITE_SECONDS) -> dict:
    """Write the chosen pictures. -> the result dict (see `bti.picks.auto.job`), also when it stopped early (`stopped`: "time" | "cancelled").

    `run_state["lines"]` remembers, line by line, what an earlier attempt of the same run already wrote (so that a resumed run neither writes
    it again nor forgets to count it), with the counters of that attempt."""
    pdir = Path(pdir)
    fetch_asset = fetch_asset or psvc.fetch_asset
    save_run = save_run or (lambda st: store.save_run(pdir, st))
    deadline = clock() + budget_s
    prev = run_state.setdefault("lines", {})
    books = search.get("books") or []
    picks = resolve_picks(plan, search, choice, books)
    keep, dropped = final_regions(plan, choice)
    main_key = inp.painting.key
    w = Writer(pdir, actor, redo=inp.redo)
    left = {b["beat"] for b in plan["lines"] if b["beat"] not in prev and not w.settled(b["beat"])}      # lines this part still has to write
    progress(0.02, "Đang tải các hình đã chọn.")
    got, failed = download_all(pdir, {k: p for k, p in picks.items() if p["beat"] in left}, fetch_asset=fetch_asset, cancelled=cancelled,
                               clock=clock, deadline=deadline, progress=lambda k, n, note: progress(0.02 + 0.5 * k / max(1, n), note))
    if cancelled():
        return {"stopped": "cancelled"}
    main = pdoc.load_or_new(pdir)["assets"][main_key]
    pcb.ensure(main, pdir)                                      # panelbox: a project made before the painted area existed (in memory: the document is saved by the batches below)
    ops, names, made = region_ops(main_key, main, keep, int(main["width"]), int(main["height"]))
    lost: set = {n for n, v in names.items() if v is None}      # panelbox: boxes drawn on the ground of the photograph
    problems: list[dict] = []
    if ops:
        try:
            w.send(ops, "Agent chọn hình: %d vùng chi tiết trên tranh chính" % len(ops))
            run_state["regions_made"] = int(run_state.get("regions_made") or 0) + made
            run_state["regions_tight"] = int(run_state.get("regions_tight") or 0) + sum(1 for o in ops if o.get("tight") is True)
        except OpError as e:
            lost = set(keep)                                    # the lines that use these boxes show the whole painting instead
            problems.append({"want": "regions", "beat": None, "no": None, "what": "vùng chi tiết", "code": "write_refused",
                             "why": texts.why("write_refused", what="vùng chi tiết", detail=_cut(str(e.detail), 120))})
    lines = build_lines(inp, plan, picks, got, failed, names, dropped, lost)
    if "names" in plan:
        cast = resolve_names(plan, picks, got, names, set(dropped) | lost)
        for line in lines:
            line["names"] = [n for n in cast if n["line"] == line["beat"]]
    chapters: dict[str, list] = {}
    for ln in lines:
        if ln["beat"] in prev:
            ln["state"] = "prev"                                # written by an earlier attempt of this run
        elif w.settled(ln["beat"]):
            ln["state"] = "others"                              # settled by the owner meanwhile
        else:
            ln["state"] = "todo"
            chapters.setdefault(ln["chapter"], []).append(ln)
    titles = {c["id"]: c["title"] for c in inp.chapters}
    stopped = None
    for k, (cid, group) in enumerate(chapters.items()):
        progress(0.55 + 0.4 * k / max(1, len(chapters)), "Đang ghi chương %s (%d/%d)." % (titles.get(cid) or cid, k + 1, len(chapters)))
        if cancelled():
            stopped = "cancelled"
            break
        if clock() > deadline:
            stopped = "time"
            break
        writable = [ln for ln in group if (not ln["show"]) or ln["items"]]       # a line with nothing found stays as it was
        name = "Agent chọn hình: chương %s, %d đoạn" % (titles.get(cid) or cid, len(writable))
        try:
            if writable:
                w.send(_ops_for(writable, main_key), name)
            ok = writable
        except OpError:
            ok = []
            for ln in writable:                                 # isolate the line that the document refuses
                try:
                    w.send(_ops_for([ln], main_key), "Agent chọn hình: đoạn %s" % ln["beat"])
                    ok.append(ln)
                except (OpError, WriteError) as e:
                    ln["refused"] = _cut(str(getattr(e, "detail", None) or getattr(e, "message", "")), 120)
        for ln in ok:
            ln["state"] = "written"
            prev[ln["beat"]] = {"reason": line_note(ln), "kind": "pictures" if ln["show"] else "keep",
                                "clips": sum(1 for i in ln["items"] if i["role"] == "video"), "missing": ln["missing"], "no": ln["no"],
                                "outside_without": bool(set(ln.get("kinds") or ()) & set(pdoc.OUTSIDE_KINDS) and not any(i["role"] in ("context", "document", "map", "video")
                                                                                                                      for i in ln["items"]))}
        run_state["imported"] = int(run_state.get("imported") or 0) + w.created_assets
        w.created_assets = 0
        run_state["batches"] = list(run_state.get("batches") or []) + w.batches
        w.batches = []
        save_run(run_state)
    # ---- the result
    result = {"lines_total": 0, "lines_done": 0, "lines_with_pictures": 0, "lines_kept": 0, "lines_without": [], "missing": list(problems),
              "pictures_imported": int(run_state.get("imported") or 0), "regions_made": int(run_state.get("regions_made") or 0),
              "regions_tight": int(run_state.get("regions_tight") or 0), "regions_dropped": list(dropped), "clips": 0, "batches": list(run_state.get("batches") or []), "stopped": stopped,
              "lines_by_others": 0, "reasons": {}, "outside_without": []}
    for ln in lines:
        st = ln["state"]
        if st == "others":
            result["lines_by_others"] += 1
            continue
        result["lines_total"] += 1
        if st in ("prev", "written"):
            rec = prev[ln["beat"]]
            result["lines_done"] += 1
            result["lines_kept" if rec["kind"] == "keep" else "lines_with_pictures"] += 1
            result["clips"] += int(rec.get("clips") or 0)
            if rec.get("outside_without"):
                result["outside_without"].append(ln["beat"])      # about something outside the painting, written with the painting only (it is in `missing` too)
            result["reasons"][ln["beat"]] = {"reason": rec["reason"], "kind": rec["kind"]}
            result["missing"] += [{**m, "beat": ln["beat"], "no": ln["no"]} for m in rec.get("missing") or []]
            continue
        if ln.get("refused"):
            code, text = "write_refused", texts.why("write_refused", what="đoạn %d" % ln["no"], detail=ln["refused"])
        elif ln["missing"] and not ln["items"]:
            code, text = ln["missing"][0]["code"], " ".join(m["why"] for m in ln["missing"])
        else:
            code, text = "time_up", texts.why("time_up", what="đoạn %d" % ln["no"])
        result["lines_without"].append({"beat": ln["beat"], "no": ln["no"], "code": code, "why": text})
        result["missing"] += [{**m, "beat": ln["beat"], "no": ln["no"]} for m in ln["missing"]]
    return result
