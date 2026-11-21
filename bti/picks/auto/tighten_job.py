"""Standalone second-look job (`picks.tighten`: `POST /api/projects/{pid}/picks/tighten`): tightens non-tight regions on the main painting.

Used for projects made before the second look existed (or when a region was left non-tight). Changes ONLY regions on the main painting
(never touches any beat's chosen pictures). Like `picks.auto`, it holds the project's one agent run (`kind="picks"`, `meta.action="tighten"`),
writes through typed operations in one undoable batch as actor `agent:<model id>`, and never approves.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from bti.draft import run as draft_run
from bti.draft.inputs import DraftError
from bti.ops import OpError, runner as ops_runner
from bti.ops.adapters import PicksAdapter
from bti.ops.log import ChangeLog
from bti.picks import context, doc

from . import helper, session, store, texts, tighten, workspace
from .inputs import AutoError

KIND = "picks"
ACTION = "tighten"
ROLE = "picks"
TIGHTEN_LIMITS = session.Limits(minutes=25, steps=120, repairs=2)
EST_SECONDS = {"tighten": 240, "write": 15}


def _manager():
    import bti.longjob as lj
    return lj.manager


def _fail(out: session.Outcome, ctx, *, empty_code: str = "picks_auto_no_output"):
    from bti.longjob import PartError
    if out.status == "tampered":
        return PartError("picks_auto_tampered", out.message)
    if out.status == "limit":
        return PartError("picks_auto_limit", out.message)
    if out.status in ("error", "timeout") and out.code:
        if out.retry_after_seconds:
            ctx.meta.update(draft_run.rate_limit_fields(out.retry_after_seconds))
        return PartError(out.code, out.message or texts.vi(out.code))
    return PartError(empty_code, texts.vi(empty_code))


def _used_in_beats(picks: dict, main_key: str) -> dict[str, list[str]]:
    """Map `region name -> [beat id, ...]` in document order for items pointing at `main_key`."""
    out: dict[str, list[str]] = {}
    for bid, b in (picks.get("beats") or {}).items():
        if not isinstance(b, dict):
            continue
        for it in b.get("items") or []:
            if isinstance(it, dict) and it.get("asset") == main_key and it.get("region"):
                out.setdefault(it["region"], []).append(bid)
    return out


def _narration_texts(pdir: Path) -> dict[str, str]:
    try:
        nv = context.narration_view(pdir)
        return {b["id"]: str(b.get("text") or "") for c in nv.get("chapters") or [] for b in c.get("beats") or []}
    except Exception:       # noqa: BLE001 - projects without narration still tighten using region labels
        return {}


def start(pid: str, pdir: Path, *, regions: list | None = None, base_rev: str | None = None, model: str | None = None,
          manager=None, by_run: bool = False, **seams) -> dict:
    """Start the standalone region-tightening job; -> the job's public record. Raises `AutoError` on refusal."""
    pdir = Path(pdir)
    if model is not None and (not isinstance(model, str) or draft_run._bad_model_name(model)):
        raise AutoError("bad_model", "the model name is not valid", 422)
    picks = doc.load(pdir)
    main_key = (picks or {}).get("main_asset")
    main = (picks or {}).get("assets", {}).get(main_key) if picks and main_key else None
    if not main:
        raise AutoError("picks_no_main", texts.vi("picks_no_main"), 409)
    src_file = pdir / str(main.get("file") or "")
    if main.get("kind") == "video" or not src_file.is_file() or int(main.get("width") or 0) <= 0 or int(main.get("height") or 0) <= 0:
        raise AutoError("main_asset_unreadable", texts.vi("main_asset_unreadable"), 409)

    non_tight = doc.non_tight_regions(picks)
    all_regions = main.get("regions") or {}
    if regions is not None:
        if not (isinstance(regions, list) and regions and all(isinstance(r, str) for r in regions)):
            raise AutoError("invalid", "regions must be a non-empty list of region names, or null for all non-tight regions", 422)
        for name in regions:
            if name not in all_regions:
                raise AutoError("not_found", "region %r is not on the main painting" % str(name)[:40], 404)
        req_set = set(regions)
        todo = [n for n in non_tight if n in req_set]
    else:
        todo = list(non_tight)
    if not todo:
        raise AutoError("tighten_nothing_to_do", texts.vi("tighten_nothing_to_do"), 409)

    if base_rev is not None:
        cur = doc.revision(picks)
        if base_rev != cur:
            raise AutoError("stale", "the picks changed since you read them", 409, rev=cur)

    res = draft_run._resolve(pdir, ROLE, model)
    try:
        session.check_installed(res.model)
    except DraftError as e:
        raise AutoError(e.code, e.message, 409)

    m = manager or _manager()
    other = draft_run.other_agent_job(pid, KIND, m, run_ok=by_run)
    if other is not None:
        raise AutoError("agent_job_running", texts.vi("agent_job_running"), 409, job_id=other.get("id"))

    limits: session.Limits = seams.get("limits") or TIGHTEN_LIMITS
    beat_map = _used_in_beats(picks, main_key)
    nar_texts = _narration_texts(pdir)
    entries = []
    for name in todo:
        raw_r = dict(all_regions[name])
        lines = beat_map.get(name, [])
        entries.append({
            "name": name,
            "raw": raw_r,
            "label": str(raw_r.get("label") or ""),
            "thing": str(raw_r.get("thing") or ""),
            "lines": lines,
            "line_texts": {b: nar_texts[b] for b in lines if b in nar_texts},
        })

    from bti.longjob import Part, PartError
    state_box: dict = {"value": None, "ws_started": time.time()}

    def run_tighten(ctx):
        if ctx.cancelled():
            return None
        workspace.clean_old()
        try:
            ws, _ = workspace.build_tighten(pdir, main, entries, limits)
        except workspace.WorkspaceError as e:
            raise PartError(e.code, texts.vi(e.code, e.message))
        ctx.progress(0.05, "Đã chuẩn bị các ảnh cắt phóng to cho agent.")
        transcript = store.session_dir(pdir, state_box["ws_started"], "tighten") / "tighten-events.jsonl"
        try:
            out = session.run_session(
                ws.root, model=res.model, project_dir=pdir, ctx=ctx, label="Agent đang đo lại khung chi tiết",
                limits=limits, check_fn=lambda: helper.run_check(ws.root).problems(), transcript=transcript,
                python=seams.get("python"), guard_factory=seams.get("guard_factory"),
                allow=session.allow_rules(helpers=("check",)),
            )
        except DraftError as e:
            shutil.rmtree(ws.root, ignore_errors=True)
            raise PartError(e.code, session.refuse_text(e))
        if out.status == "cancelled" or ctx.cancelled():
            shutil.rmtree(ws.root, ignore_errors=True)
            return None
        if out.status == "tampered":
            raise _fail(out, ctx)
        rep = helper.run_check(ws.root)
        if not rep.ok:
            rep = helper.run_check(ws.root, allow_unconfirmed=True)
            if not rep.ok:
                raise _fail(out, ctx)
        state_box["value"] = rep.value
        shutil.rmtree(ws.root, ignore_errors=True)
        store.write(pdir, "tighten.json", {
            "schema": store.SCHEMA, "model": res.model, "agent": res.public(),
            "regions": rep.value["regions"],
            "session": {"steps": out.steps, "turns": out.turns, "repairs": out.repairs, "status": out.status, "elapsed": round(out.elapsed)},
        })
        confirmed_n = sum(1 for r in rep.value["regions"].values() if r.get("action") == "tight" and r.get("confirmed"))
        ctx.progress(1.0, "Đã đo xong %d/%d vùng chi tiết." % (confirmed_n, len(todo)))
        return {"tighten": {"regions": len(todo), "confirmed": confirmed_n,
                            "session": {"steps": out.steps, "turns": out.turns, "repairs": out.repairs, "elapsed": round(out.elapsed)}}}

    def run_write(ctx):
        if ctx.cancelled():
            return None
        val = state_box.get("value")
        if not val:
            raise PartError("picks_auto_no_output", texts.vi("picks_auto_no_output"))
        cur = doc.load(pdir)
        cur_main = (cur or {}).get("main_asset")
        if cur is None or not cur_main or cur_main not in cur.get("assets", {}) or cur_main != main_key:
            raise PartError("picks_auto_stale", texts.vi("picks_auto_stale"))
        cur_regs = cur["assets"][cur_main].get("regions") or {}
        used_now = _used_in_beats(cur, cur_main)
        ops: list[dict] = []
        tightened: list[str] = []
        unconfirmed: list[str] = []
        dropped: list[str] = []
        dropped_in_use: list[str] = []

        for name in todo:
            res_r = val["regions"].get(name)
            if not res_r or name not in cur_regs:
                continue
            if res_r["action"] == "drop":
                if used_now.get(name):
                    dropped_in_use.append(name)
                else:
                    dropped.append(name)
                    ops.append({"op": "remove_region", "asset": cur_main, "region": name})
                continue
            if res_r.get("confirmed") is not True or not res_r.get("stored_box"):
                unconfirmed.append(name)
                continue
            reg = tighten.stored_box_to_region(res_r["stored_box"])
            lbl = str(cur_regs[name].get("label") or "")[:80]
            op_d = {
                "op": "set_region", "asset": cur_main, "region": name,
                "x": reg["x"], "y": reg["y"], "rx": reg["rx"], "ry": reg["ry"], "label": lbl,
                "tight": True,
            }
            thing = str(res_r.get("thing") or cur_regs[name].get("thing") or "").strip()
            if thing:
                op_d["thing"] = thing[:doc.THING_MAX]
            if res_r.get("rough_px") and len(res_r["rough_px"]) == 4:
                op_d["rough"] = [int(v) for v in res_r["rough_px"]]
            ops.append(op_d)
            tightened.append(name)

        batches: list[str] = []
        if ops:
            adapter = PicksAdapter(pdir)
            log = ChangeLog(pdir)
            for attempt in (1, 2):
                _, rev = adapter.read()
                try:
                    bres = ops_runner.run_batch(adapter, {
                        "base_rev": rev, "actor": "agent:" + res.model, "ops": ops,
                        "note": "Đo khung khít cho %d vùng chi tiết trên tranh chính" % len(ops),
                    }, log)
                    if bres.get("batch"):
                        batches.append(bres["batch"])
                    break
                except OpError as e:
                    if e.code == "stale_revision" and attempt == 1:
                        continue
                    raise PartError("write_refused", texts.why("write_refused", what="vùng chi tiết", detail=str(e.detail)[:120]))
        sentence = texts.tighten_sentence(len(tightened), len(todo), len(unconfirmed), len(dropped) + len(dropped_in_use))
        ctx.progress(1.0, sentence)
        return {
            "regions_total": len(todo),
            "tightened": tightened,
            "unconfirmed": unconfirmed,
            "dropped": dropped,
            "dropped_in_use": dropped_in_use,
            "batches": batches,
            "sentence": sentence,
            "agent": res.public(),
            "limits": limits.public(),
        }

    parts = [
        Part(key="tighten", title=texts.TIGHTEN_PART_TITLES["tighten"], run=run_tighten, est_seconds=EST_SECONDS["tighten"]),
        Part(key="write", title=texts.TIGHTEN_PART_TITLES["write"], run=run_write, est_seconds=EST_SECONDS["write"]),
    ]
    meta = {
        "action": ACTION, "model": res.model, "agent": res.public(),
        "regions": todo, "limits": limits.public(),
    }
    try:
        return m.start(kind=KIND, pid=pid, project_dir=pdir, parts=parts, meta=meta)
    except Exception as e:      # noqa: BLE001
        if type(e).__name__ == "Busy":
            raise AutoError("busy", "a picks job is already running for this project", 409, job_id=getattr(e, "job_id", None))
        raise


def active_job(pid: str) -> dict | None:
    try:
        rec = _manager().active(pid, kind=KIND)
    except Exception:       # noqa: BLE001
        return None
    return rec if rec and (rec.get("meta") or {}).get("action") == ACTION else None


def overview(pid: str, pdir: Path) -> dict:
    res = draft_run._resolve(pdir, ROLE, None)
    picks = doc.load(pdir)
    return {
        "running": active_job(pid),
        "non_tight": doc.non_tight_regions(picks),
        "agent": res.public(),
        "limits": TIGHTEN_LIMITS.public(),
    }
