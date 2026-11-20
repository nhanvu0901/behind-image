"""`picks.retry_missing`: finish a run of the pictures agent whose chosen pictures could not be downloaded. No model session, no search: only downloads.

The write part of `picks.auto` (`bti.picks.auto.write`) lists, on the line, a picture the agent chose and that the source refused to give (`missing` holds
`{what, code: "import_limited"}`; the line was written with its fallback). The choice itself is kept in the saved files of the run (`cache/picks_auto/`):

    plan.json     the plan: what each line shows, in order, and its fallback
    search.json   the candidates of every wanted picture (`round2.map[want]` says which candidates the second round added)
    choice.json   the agent's first choice: `pick` is `["c", n]` (candidate n of the want) or `["b", n]` (picture n of the books)
    choice2.json  the second choice (only with the owner's switch for the web search): its `n` counts inside `search.json`'s `round2.map[want]`

`bti.picks.auto.webround.merge_choice` reads the two choices as ONE, exactly as the write part did, so this module finds the very candidate the agent chose, imports
it (`bti.picks.service.fetch_asset`: polite and patient, see `bti.media.http.polite`) and writes the line again the way the write part would have written it with the
picture in hand: the plan's items in the plan's order (the picture with the agent's reason as its note), `missing` without the entries it fixed, the line's note
without the sentence "Chưa tìm được ...". A `web_budget` is NOT retried here (that is a search that was not made, it needs the paid search: `picks.auto`).

A line is rewritten only while it is still as the write part left it: the plan's items for the picture that was missing and nothing else. A line the owner (or the
operations) changed since is left alone and listed. The change log has one batch per line, with the actor the caller names. This module never approves anything.

The saved files must belong to the picks: the plan has to hold the line, and the wanted picture's own words (`what`) have to be the ones the line's `missing` names.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from bti.media import assets as media_assets
from bti.ops import OpError
from bti.picks import doc as pdoc
from bti.picks import service as psvc

from . import inputs as ainputs
from . import search as asearch
from . import store, texts, webround
from . import write as awrite
from .inputs import AutoError

KIND = "picks"
ACTION = "retry"
CODE = "import_limited"                           # the only code this action retries
FILES = ("plan.json", "search.json", "choice.json")      # what must be in cache/picks_auto/ (choice2.json is read when it is there)
RESULT_FILE = "retry.json"
EST_SECONDS = 60
TITLE = "Tải lại các hình đã chọn"


# ---------------------------------------------------------------------------------------------------------------- what the state answer asks
def _norm(what: str) -> str:
    return " ".join(str(what or "").split())[: pdoc.MISSING_WHAT_MAX]


def lines_with_limit(picks: dict | None) -> list[str]:
    """The lines of the picks document whose `missing` holds `import_limited`, in line order of their ids."""
    beats = (picks or {}).get("beats") or {}
    return sorted(bid for bid, b in beats.items() if any(m.get("code") == CODE for m in (b or {}).get("missing") or []))


def files_ready(pdir: Path) -> bool:
    """Are the saved files of the last run in the project? (a cheap look: the files are there, not that they fit)"""
    return all((store.cache_dir(pdir) / n).is_file() for n in FILES)


def tried(pdir: Path) -> set[str]:
    """The lines an earlier call of this action already looked at since the last run of `picks.auto` (a run forgets it: `store.reset`)."""
    d = store.read(pdir, RESULT_FILE) or {}
    return {b for b in d.get("tried") or [] if isinstance(b, str)}


def facts(pdir: Path, picks: dict | None) -> dict:
    """What the state answer needs: the lines that say `import_limited`, whether the saved files are there, and the lines that were not looked at yet."""
    lines = lines_with_limit(picks)
    if not lines:
        return {"lines": [], "files": False, "untried": []}
    seen = tried(pdir)
    return {"lines": lines, "files": files_ready(pdir), "untried": [b for b in lines if b not in seen]}


# ---------------------------------------------------------------------------------------------------------------- the saved files
def load_saved(pdir: Path) -> tuple[dict, dict, dict]:
    """(plan, search state, the two choices as one) from `cache/picks_auto/`; `AutoError` `retry_no_files` when they are not there or do not belong together."""
    plan, search, c1 = (store.read(pdir, n) for n in FILES)
    c2 = store.read(pdir, "choice2.json")
    if not (plan and search and c1) or not isinstance((plan.get("plan") or {}).get("lines"), list) or not isinstance(search.get("wants"), dict) \
            or not isinstance(c1.get("choice"), dict):
        raise AutoError("retry_no_files", "the saved files of the last run (cache/picks_auto: plan, search, choice) are not in the project or cannot be read")
    keys = {d.get("key") for d in (plan, search, c1)}
    if len(keys) != 1:
        raise AutoError("retry_no_files", "the saved files of the last run belong to different runs")
    second = c2["choice"] if c2 and c2.get("key") in keys and isinstance(c2.get("choice"), dict) else None
    return plan["plan"], search, webround.merge_choice(c1["choice"], second, search)


# ---------------------------------------------------------------------------------------------------------------- one line
def _index_key(index: dict, pdir: Path, src: str, sid: str) -> str | None:
    """The asset key of a picture the project already holds (`index` is `load_index(pdir)["items"]`; its file is there), else None. Nothing is downloaded."""
    hit = index.get("%s:%s" % (src, sid))
    return hit["key"] if hit and (Path(pdir) / (hit.get("asset") or {}).get("file", "")).is_file() else None


def _name(src: str) -> str:
    return asearch.SOURCE_VI.get(src, src)


def analyse(pdir: Path, index: dict, inp, plan_line: dict | None, rows: dict, cur: dict, names: dict, dropped: list, main_key: str) -> dict:
    """What can be done for one line: `{"skip": code, "why": sentence}`, or `{"limited": [want ids], "got": {pick: asset key}, "failed": {pick: (code, ...)}}` (the pictures
    of the line as the write part left them: `got` the ones it had, `failed` the ones it listed in `missing`, each with its code).

    The line is only taken when it is STILL as the write part wrote it (`line_changed` otherwise): the items that `build_lines` gives for exactly this state must be the line's items."""
    if plan_line is None:
        return {"skip": "not_in_plan", "why": texts.why("retry_not_in_plan")}
    mine = {wid: r for wid, r in rows.items() if r["beat"] == plan_line["beat"]}
    codes: dict = {}
    for m in cur.get("missing") or []:
        codes.setdefault(_norm(m["what"]), m["code"])
    limited = [wid for wid, r in mine.items() if r["pick"] and codes.get(_norm(r["what"])) == CODE]
    if not limited:
        return {"skip": "no_saved_choice", "why": texts.why("retry_no_choice")}
    got, failed = {}, {}
    for wid, r in mine.items():
        if not r["pick"]:
            continue
        key = (r["pick"]["source"], r["pick"]["source_id"])
        code = codes.get(_norm(r["what"]))
        held = _index_key(index, pdir, *key)
        if code is not None:
            failed[key] = (code, "", _name(key[0]), None)
        elif held:
            got[key] = held
        else:                                                # a picture the line was written with is not in the project: the line is not what the write part left
            return {"skip": "line_changed", "why": texts.why("retry_line_changed")}
    before = awrite.build_lines(inp, {"lines": [plan_line]}, rows, got, failed, names, dropped, set())[0]
    want = [(main_key if i["asset"] == "main" else got[i["src"]], i["region"], i["role"]) for i in before["items"]]
    have = [(i["asset"], i.get("region"), i["role"]) for i in cur.get("items") or []]
    if want != have:
        return {"skip": "line_changed", "why": texts.why("retry_line_changed")}
    return {"limited": limited, "got": got, "failed": failed}


# ---------------------------------------------------------------------------------------------------------------- the work
def run(pdir: Path, *, beats: list[str] | None = None, actor: str, cancelled: Callable[[], bool], progress: Callable[[float, str], None],
        fetch_asset=None, clock: Callable[[], float] = time.time, budget_s: float = awrite.WRITE_SECONDS, job_id: str | None = None) -> dict:
    """Import the pictures the agent chose for the lines that say `import_limited` and write those lines again. -> the result:
    `{lines_total, lines_fixed: [beats], lines_still_limited: [{beat, no, code, why}], lines_left: [{beat, no, code, why}], pictures_imported, batches, stopped, job_id}`."""
    from bti.picks import context
    pdir = Path(pdir)
    fetch_asset = fetch_asset or psvc.fetch_asset
    picks = pdoc.load_or_new(pdir)
    lines = [b for b in lines_with_limit(picks) if beats is None or b in beats]
    result: dict = {"lines_total": len(lines), "lines_fixed": [], "lines_still_limited": [], "lines_left": [], "pictures_imported": 0, "batches": [],
                    "stopped": None, "job_id": job_id}
    if not lines:
        return result
    plan, search, choice = load_saved(pdir)
    known = set(context.narration_view(pdir)["beat_ids"])
    here = [b for b in lines if b in known]
    for bid in lines:
        if bid not in known:                                 # a line the narration no longer has
            result["lines_left"].append({"beat": bid, "no": None, "code": "not_in_plan", "why": texts.why("retry_not_in_plan")})
    if not here:
        return result
    inp = ainputs.load(pdir, here, redo=True, need_targets=False)
    main_key = inp.painting.key
    main = picks["assets"][main_key]
    rows = awrite.resolve_picks(plan, search, choice, search.get("books") or [])
    keep, dropped = awrite.final_regions(plan, choice)
    region_ops, names, _made = awrite.region_ops(main_key, main, keep, int(main["width"]), int(main["height"]))
    plan_lines = {ln["beat"]: ln for ln in plan["lines"]}
    index = media_assets.load_index(pdir)["items"]
    deadline = clock() + budget_s

    # 1. what each line needs (a line that is not as the write part left it is left alone)
    todo: list[tuple[str, dict, dict]] = []                  # (beat, plan line, analysis)
    for bid in here:
        a = analyse(pdir, index, inp, plan_lines.get(bid), rows, dict(picks["beats"][bid]), names, dropped, main_key)
        if "skip" in a:
            result["lines_left"].append({"beat": bid, "no": inp.beat(bid)["no"], "code": a["skip"], "why": a["why"]})
        else:
            todo.append((bid, plan_lines[bid], a))
    # 2. the downloads, one at a time (polite and patient: see `bti.picks.auto.write.download_all`)
    wanted = {wid: rows[wid] for _b, _ln, a in todo for wid in a["limited"]}
    progress(0.02, "Đang tải lại các hình đã chọn.")
    got, failed = awrite.download_all(pdir, wanted, fetch_asset=fetch_asset, cancelled=cancelled, clock=clock, deadline=deadline,
                                      progress=lambda k, n, note: progress(0.02 + 0.7 * k / max(1, n), note))
    if cancelled():
        result["stopped"] = "cancelled"
        return result
    # 3. the lines, one batch each
    w = awrite.Writer(pdir, actor, redo=True)
    sent_regions = False
    for k, (bid, plan_line, a) in enumerate(todo):
        no = inp.beat(bid)["no"]
        keys = {wid: (rows[wid]["pick"]["source"], rows[wid]["pick"]["source_id"]) for wid in a["limited"]}
        if not set(keys.values()) & set(got):                # nothing of this line could be had: it stays as it is
            wid = a["limited"][0]
            code, _d, source, secs = failed.get(keys[wid], (CODE, "", None, None))
            result["lines_still_limited"].append({"beat": bid, "no": no, "code": code, "why": texts.why(code, what=rows[wid]["what"], source=source or "", seconds=secs)})
            continue
        progress(0.72 + 0.26 * k / max(1, len(todo)), "Đang ghi lại đoạn %d." % no)
        if cancelled():
            result["stopped"] = "cancelled"
            break
        line = awrite.build_lines(inp, {"lines": [plan_line]}, rows, {**a["got"], **got},
                                  {key: v for key, v in {**a["failed"], **failed}.items() if key not in got}, names, dropped, set())[0]
        try:
            if region_ops and not sent_regions:
                w.send(region_ops, "Tải lại hình đã chọn: các vùng chi tiết còn thiếu")
                sent_regions = True
            w.send(awrite._ops_for([line], main_key), "Tải lại hình đã chọn: đoạn %s" % bid)
        except (OpError, awrite.WriteError) as e:
            result["lines_left"].append({"beat": bid, "no": no, "code": "write_refused",
                                         "why": texts.why("write_refused", what="đoạn %d" % no, detail=awrite._cut(str(getattr(e, "detail", None) or getattr(e, "message", "")), 120))})
            continue
        result["lines_fixed"].append(bid)
        result["lines_still_limited"] += [{"beat": bid, "no": no, "code": m["code"], "why": m["why"]} for m in line["missing"] if m["code"] == CODE]
    result["pictures_imported"] = w.created_assets
    result["batches"] = list(w.batches)
    return result


def result_sentence(res: dict) -> str:
    return texts.retry_sentence(len(res["lines_fixed"]), res["lines_total"], len(res["lines_still_limited"]), len(res["lines_left"]))


def remember(pdir: Path, res: dict, looked_at: list[str], job_id: str | None) -> None:
    """Keep what was done (`cache/picks_auto/retry.json`): the lines looked at (the state answer does not offer them as advancing a second time), and the result."""
    prev = tried(pdir)
    store.write(pdir, RESULT_FILE, {"schema": store.SCHEMA, "finished": time.time(), "job_id": job_id, "tried": sorted(prev | set(looked_at)),
                                    "result": {k: v for k, v in res.items() if k != "tried"}})


# ---------------------------------------------------------------------------------------------------------------- the job
def _manager():
    import bti.longjob as lj
    return lj.manager


def start(pid: str, pdir: Path, *, beats: list | None = None, actor: str = "human", by_run: bool = False, manager=None, **seams) -> dict:
    """Start the job (kind `picks`, `meta.action` `retry`); -> its public record. Raises `AutoError` (the refusals of the route). `seams` (tests): fetch_asset, clock, budget_s."""
    from bti.draft import run as draft_run
    from bti.longjob import Part, PartError
    pdir = Path(pdir)
    if beats is not None and not (isinstance(beats, list) and beats and all(isinstance(b, str) for b in beats)):
        raise AutoError("invalid", "beats must be null or a list of narration line ids", 422)
    picks = pdoc.load_or_new(pdir)
    lines = [b for b in lines_with_limit(picks) if beats is None or b in beats]
    if not lines:
        raise AutoError("retry_nothing_to_do", "no line says that a chosen picture could not be downloaded (`missing` with the code import_limited)")
    if not files_ready(pdir):
        raise AutoError("retry_no_files", "the saved files of the last run (cache/picks_auto: plan, search, choice) are not in the project: run picks.auto again for these lines")
    m = manager or _manager()
    other = draft_run.other_agent_job(pid, KIND, m, run_ok=by_run)
    if other is not None:
        raise AutoError("agent_job_running", "%s is working on this project: wait for it or cancel it, then call again" % draft_run.AGENT_JOB_WHO.get(other.get("kind"), "another job"),
                        409, job_id=other.get("id"))

    def part(ctx):
        try:
            res = run(pdir, beats=lines, actor=actor, cancelled=ctx.cancelled, progress=ctx.progress, fetch_asset=seams.get("fetch_asset"),
                      clock=seams.get("clock") or time.time, budget_s=seams.get("budget_s") or awrite.WRITE_SECONDS, job_id=ctx.job_id)
        except AutoError as e:
            raise PartError(e.code, texts.vi(e.code, e.message))
        except awrite.WriteError as e:
            raise PartError(e.code, texts.vi(e.code, e.message))
        if res["stopped"] == "cancelled":
            return None
        remember(pdir, res, lines, ctx.job_id)
        res["sentence"] = result_sentence(res)
        ctx.progress(1.0, res["sentence"])
        return res

    meta = {"action": ACTION, "beats": list(lines), "actor": actor}
    try:
        return m.start(kind=KIND, pid=pid, project_dir=pdir, parts=[Part(key="retry", title=TITLE, run=part, est_seconds=EST_SECONDS)], meta=meta)
    except Exception as e:      # noqa: BLE001
        if type(e).__name__ == "Busy":
            raise AutoError("busy", "a picks job is already running for this project", 409, job_id=getattr(e, "job_id", None))
        raise
