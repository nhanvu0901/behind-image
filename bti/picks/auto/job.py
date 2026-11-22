"""The long job "Để agent chọn hình" (`POST /api/projects/{pid}/picks/auto`): it fills step 4 by itself, in four parts, and never approves.

    1. plan     (model)  the agent reads the narration lines and the facts and looks at the main painting; for each line it says what should
                         be on screen and proposes boxes for the details of the main painting            -> cache/picks_auto/plan.json
    2. search   (code)   candidates for every picture the plan wants from elsewhere, from the free sources, with thumbnails
                         (never the paid suggestion service)                                              -> cache/picks_auto/search.json
    3. choose   (model)  the agent looks at the candidates (contact sheets) and at each proposed box (a crop), and chooses
                                                                                                          -> cache/picks_auto/choice.json
    4. write    (code)   regions, imports and the lines' pictures, by the typed operations, in batches with the actor `agent:<model id>`

Why two work-folder sessions and not one kept open: see `docs/qa/FIX_c3_picks_agent.md` (short: the search between them can take minutes and must
not hold an agent process or a quota; each session has its own limits and its own repair round; a cancelled run resumes from the files of the
parts that finished, and a different agent can take over after a quota failure).

With the owner's switch `auto_web_search` ON (`bti.picks.websettings`) there are two more parts after the choosing session (`bti.picks.auto.webround`):
a second round of searches (the web, PAID, counted against `auto_web_search_max`) for the wants the session answered null, and ONE more choosing session
that sees only those wants (`cache/picks_auto/choice2.json`). With the switch off the job is exactly the four parts above and nothing paid is called.

The job is the same kind as the other long jobs of step 4 (`picks`): one at a time per project. Starting it again RESUMES a run that did not
finish (same narration, same main painting, same lines): a part whose file is there is skipped, the search only does what is left, and the
write part skips the lines it already wrote. A line that already has pictures is not worked on unless the request says `redo`.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from bti import agents as AG
from bti.draft import run as draft_run
from bti.draft.inputs import DraftError

from bti.picks import websettings

from . import helper, inputs as ainputs, search as asearch, session, shapes, store, texts, webround, workspace
from . import write as awrite
from .inputs import AutoError

KIND = "picks"
ACTION = "auto"
ROLE = "picks"
# `write`: the downloads are paced one a second per host and may wait out a "too many requests" (`awrite.WRITE_SECONDS` says why the limit stays 25 minutes):
# about 25 pictures at 3 requests each and their transfer, then the batches, is about 5 minutes (it was 2 when the downloads were not paced).
EST_SECONDS = {"plan": 600, "search": 120, "choose": 600, "write": 300, "web": 180, "choose2": 240}
# The limits of the two sessions of a run. What the real 61-line run of the first test video (project eligius, 2026-11-19) took: the plan 36 steps and 210 s
# (20 boxes, a crop looked at for each), the choice of 21 pictures and 20 boxes 51 steps and 120 s (a little over one step for each sheet or crop it looked at).
# A plan now asks for a picture on every outside line up to `shapes.MAX_WANTS` = 60 and up to `shapes.MAX_REGIONS` = 30 rough regions (one thing each).
# In the choosing session, each region gets a full-res 1,024-px gridded cut-out (30 steps), plus up to ~6 `wider` re-cuts (12 steps) and up to 5
# 6-up check sheets plus confirmation (8 steps), adding ~50 steps and ~4-5 minutes on top of the 60 want sheets, so:
#   PLAN_LIMITS = 30 min / 140 steps (1 repair), CHOOSE_LIMITS = 45 min / 280 steps (2 repairs: check sheets + optional 1 correction).
PLAN_LIMITS = session.Limits(minutes=30, steps=140, repairs=1)
CHOOSE_LIMITS = session.Limits(minutes=45, steps=280, repairs=2)


def _manager():
    import bti.longjob as lj
    return lj.manager


def actor_of(model: str) -> str:
    return "agent:" + model


# ---------------------------------------------------------------------------------------------------------------- the run
class _Run:
    """What the four parts share."""

    def __init__(self, pdir: Path, pid: str, inp: ainputs.Inputs, resolved, *, limits: dict, seams: dict):
        self.pdir, self.pid, self.inp, self.res = Path(pdir), pid, inp, resolved
        self.limits = limits
        self.s = seams
        self.key = store.run_key(inp.narration_rev, inp.painting.key, inp.requested, inp.redo, inp.owner_note, limited=inp.limited)
        self.state: dict | None = None
        self.resumed = False
        self.plan: dict | None = None
        self.search: dict | None = None
        self.choice: dict | None = None
        self.choice2: dict | None = None
        self.model = resolved.model
        cfg = seams.get("web")                                  # tests: {"on", "max", "search"}; else the owner's switch as it is when the run starts
        cfg = cfg if isinstance(cfg, dict) else websettings.for_run()
        self.web_on, self.web_max, self.web_search = bool(cfg.get("on")), int(cfg.get("max", websettings.DEFAULT_MAX)), cfg.get("search")

    def web(self, st: dict) -> "asearch.Web | None":
        """The paid web search of this run (None when the owner's switch was off when it started: then nothing paid is ever called)."""
        return asearch.Web.from_state(st, True, self.web_max, search=self.web_search) if self.web_on else None

    def begin(self) -> dict:
        if self.state is None:
            self.state, self.resumed = store.begin(self.pdir, self.key, self.inp.targets, self.inp.redo)
            if not self.resumed:                                # a new run forgets the second session of an earlier one too (`store.reset` knows only the first four files)
                try:
                    (store.cache_dir(self.pdir) / "choice2.json").unlink(missing_ok=True)
                except OSError:
                    pass
            if self.resumed:                                    # the lines the earlier attempt planned for, not only the ones still without pictures
                self.inp.targets = [b["id"] for b in self.inp.beats if b["id"] in set(self.state.get("targets") or [])]
            self.state["model"] = self.model
            self.state["agent"] = self.res.public()
            store.save_run(self.pdir, self.state)
        return self.state

    # -- saved parts
    def load_plan(self) -> dict | None:
        d = store.read(self.pdir, "plan.json")
        if d and d.get("key") == self.key and isinstance(d.get("plan"), dict) and isinstance(d["plan"].get("lines"), list):
            self.plan = d["plan"]
            return self.plan
        return None

    def load_search(self) -> dict | None:
        d = store.read(self.pdir, "search.json")
        if d and d.get("key") == self.key and isinstance(d.get("wants"), dict):
            self.search = d
            return d
        return None

    def load_choice(self) -> dict | None:
        d = store.read(self.pdir, "choice.json")
        if d and d.get("key") == self.key and isinstance(d.get("choice"), dict):
            self.choice = d["choice"]
            return d
        return None

    def load_choice2(self) -> dict | None:
        d = store.read(self.pdir, "choice2.json")
        if d and d.get("key") == self.key and isinstance(d.get("choice"), dict):
            self.choice2 = d["choice"]
            return d
        return None

    def transcript(self, part: str) -> Path:
        return store.session_dir(self.pdir, self.state["started"], part) / ("%s-events.jsonl" % part)


def _fail(out: session.Outcome, ctx, *, empty_code: str = "picks_auto_no_output") -> "PartError":
    """The failure of a part whose session left no usable file."""
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


def _session(r: _Run, ctx, ws: workspace.Workspace, part: str, label: str, limits: session.Limits):
    """Run one agent session in `ws` and read its file with the program's own check. -> (Outcome, Report)."""
    from bti.longjob import PartError
    try:
        out = session.run_session(ws.root, model=r.model, project_dir=r.pdir, ctx=ctx, label=label, limits=limits,
                                  check_fn=lambda: helper.run_check(ws.root).problems(), transcript=r.transcript(part),
                                  python=r.s.get("python"), guard_factory=r.s.get("guard_factory"))
    except DraftError as e:
        shutil.rmtree(ws.root, ignore_errors=True)
        raise PartError(e.code, session.refuse_text(e))
    return out, helper.run_check(ws.root)


def _finish_workspace(ws: workspace.Workspace, ok: bool) -> None:
    """A work folder of a session that gave a usable file is removed; one that did not is kept for a look (the draft does the same)."""
    if ok:
        shutil.rmtree(ws.root, ignore_errors=True)


# ---------------------------------------------------------------------------------------------------------------- part 1: plan
def make_parts(r: _Run):
    from bti.longjob import Part, PartError
    lim = r.limits

    def plan_done(ctx) -> bool:
        r.begin()
        return r.load_plan() is not None

    def run_plan(ctx):
        r.begin()
        if ctx.cancelled():
            return None
        workspace.clean_old()
        try:
            ws = workspace.build_plan(r.inp, lim["plan"])
        except workspace.WorkspaceError as e:
            raise PartError(e.code, texts.vi(e.code, e.message))
        ctx.progress(0.02, "Đã chuẩn bị dữ liệu cho agent.")
        out, rep = _session(r, ctx, ws, "plan", "Agent đang lập danh sách hình", lim["plan"])
        if out.status == "cancelled" or ctx.cancelled():
            shutil.rmtree(ws.root, ignore_errors=True)
            return None
        if out.status == "tampered":
            raise _fail(out, ctx)
        if not rep.ok:
            raise _fail(out, ctx)
        store.write(r.pdir, "plan.json", {"schema": store.SCHEMA, "key": r.key, "model": r.model, "agent": r.res.public(), "plan": rep.value,
                                          "notes": rep.notes, "warnings": rep.warnings, "session": {"steps": out.steps, "turns": out.turns,
                                                                                                    "repairs": out.repairs, "status": out.status,
                                                                                                    "elapsed": round(out.elapsed)}})
        r.plan = rep.value
        _finish_workspace(ws, True)
        wants = shapes.wants_of(rep.value)
        ctx.progress(1.0, "Đã có danh sách: %d hình cần tìm, %d vùng chi tiết." % (len(wants), len(rep.value["regions"])))
        return {"plan": {"lines": len(rep.value["lines"]), "wants": len(wants), "regions": len(rep.value["regions"]), "notes": rep.notes,
                         "session": {"steps": out.steps, "turns": out.turns, "repairs": out.repairs, "elapsed": round(out.elapsed)}}}

    # ---------------------------------------------------------------------------------------------------------- part 2: search
    def search_done(ctx) -> bool:
        r.begin()
        plan = r.plan or r.load_plan()
        if plan is None:
            return False
        if not shapes.wants_of(plan):
            return True
        st = r.load_search()
        return bool(st and not asearch.todo(st) and st.get("books") is not None)

    def run_search(ctx):
        r.begin()
        plan = r.plan or r.load_plan()
        if plan is None:
            raise PartError("picks_auto_no_output", texts.vi("picks_auto_no_output"))
        wants = shapes.wants_of(plan)
        st = r.load_search() or asearch.new_state()
        st["key"] = r.key

        def save(s):
            s["key"] = r.key
            store.write(r.pdir, "search.json", s)
        st = asearch.run(r.pdir, plan, st, wants, main_key=r.inp.painting.key, cancelled=ctx.cancelled, progress=ctx.progress, save=save,
                         search=r.s.get("search"), fetch_thumb=r.s.get("fetch_thumb"), clock=r.s.get("clock") or time.time,
                         budget_s=r.s.get("search_budget_s") or asearch.SEARCH_SECONDS, web=r.web(st), wiki_search=r.s.get("wiki_search"))
        if ctx.cancelled():
            return None
        if st.get("books") is None:
            has_context = any(w["type"] == "context" for w in wants)
            st["books"] = asearch.collect_books(r.pdir, r.inp.painting.key, fetch=r.s.get("fetch_book_thumb")) if has_context else []
            save(st)
        r.search = st
        found = sum(1 for w in st["wants"].values() if w["status"] == "found")
        ctx.progress(1.0, "Tìm xong: %d/%d hình có ứng viên." % (found, len(st["wants"])))
        out = {"wants": len(st["wants"]), "found": found, "books": len(st["books"] or []),
               "limited": sorted({w["source"] for w in st["wants"].values() if w["status"] == "limited" and w.get("source")})}
        if r.web_on:
            out["web"] = st.get("web")
        return {"search": out}

    # ---------------------------------------------------------------------------------------------------------- part 3: choose
    def shown_of(st: dict) -> list[str]:
        """The wants the FIRST choosing session sees: those with candidates of round one (the second round's candidates are not part of it)."""
        return sorted(wid for wid, w in st["wants"].items() if any(c.get("round", 1) == 1 for c in w.get("candidates") or []))

    def regions_of(plan: dict) -> list[str]:
        return sorted(workspace.plan_regions_to_tighten(r.inp, plan))

    def choose_done(ctx) -> bool:
        r.begin()
        plan = r.plan or r.load_plan()
        st = r.search or r.load_search() or asearch.new_state()
        if plan is None:
            return False
        if not shown_of(st) and not regions_of(plan):
            return True                                           # nothing to look at: the model is not called
        d = r.load_choice()
        return bool(d and d.get("shown") == shown_of(st) and d.get("regions") == regions_of(plan))

    def run_choose(ctx):
        r.begin()
        plan = r.plan or r.load_plan()
        st = r.search or r.load_search() or asearch.new_state()
        if plan is None:
            raise PartError("picks_auto_no_output", texts.vi("picks_auto_no_output"))
        if not shown_of(st) and not regions_of(plan):
            r.choice = {"schema": shapes.CHOICE_SCHEMA, "wants": {}, "regions": {}}
            ctx.progress(1.0, "Không có hình nào để chọn: bỏ qua bước này.")
            return {"choose": {"wants": 0, "regions": 0, "skipped": True}}
        if ctx.cancelled():
            return None
        try:
            ws, cctx = workspace.build_choose(r.inp, plan, st, lim["choose"], books=_books_for(r.pdir, st))
        except workspace.WorkspaceError as e:
            raise PartError(e.code, texts.vi(e.code, e.message))
        ctx.progress(0.02, "Đã chuẩn bị các tờ hình cho agent.")
        out, rep = _session(r, ctx, ws, "choose", "Agent đang chọn hình", lim["choose"])
        if out.status == "cancelled" or ctx.cancelled():
            shutil.rmtree(ws.root, ignore_errors=True)
            return None
        if out.status == "tampered":
            raise _fail(out, ctx)
        if not rep.ok:
            rep_fb = helper.run_check(ws.root, allow_unconfirmed=True)
            if rep_fb.ok:
                rep = rep_fb                                      # keep unconfirmed regions as non-tight rather than discarding valid choices
            else:
                raise _fail(out, ctx)
        # A subject whose period candidates were all rejected gets a separate, free modern-photo search and a second visual choice.
        rejected_wants = asearch.modern_retry_wants(shapes.wants_of(plan), st)
        if rejected_wants:
            retry = asearch.modern_after_rejection(r.pdir, rejected_wants, rep.value, main_key=r.inp.painting.key,
                     cancelled=ctx.cancelled, fetch_thumb=r.s.get("fetch_thumb") or asearch.default_fetch_thumb,
                     clock=r.s.get("clock") or time.time, search=r.s.get("search"))
            if ctx.cancelled():
                return None
            if retry["wants"]:
                for wid, row in retry["wants"].items():
                    row["earlier"] = ((rep.value.get("wants") or {}).get(wid) or {}).get("reason", "")
                try:
                    second_ws, _ = workspace.build_choose(r.inp, plan, retry, lim["choose"], books=[], second=True)
                except workspace.WorkspaceError as e:
                    raise PartError(e.code, texts.vi(e.code, e.message))
                second_out, second_rep = _session(r, ctx, second_ws, "choose_modern", "Agent đang chọn ảnh hiện đại", lim["choose"])
                if second_out.status == "cancelled" or ctx.cancelled():
                    shutil.rmtree(second_ws.root, ignore_errors=True)
                    shutil.rmtree(ws.root, ignore_errors=True)
                    return None
                if second_out.status == "tampered" or not second_rep.ok:
                    raise _fail(second_out, ctx)
                for wid, row in retry["wants"].items():
                    existing = st["wants"][wid]["candidates"]
                    offset = max([int(candidate.get("n") or 0) for candidate in existing] or [0])
                    for n, candidate in enumerate(row["candidates"], 1):
                        candidate["n"] = offset + n
                        candidate["round"] = 1
                    existing.extend(row["candidates"])
                    st["wants"][wid]["modern_fallback"] = True
                    selected = second_rep.value["wants"][wid]
                    pick = selected.get("pick")
                    if pick and pick[0] == "c":
                        selected = {**selected, "pick": ("c", offset + pick[1])}
                    rep.value["wants"][wid] = selected
                st["key"] = r.key
                store.write(r.pdir, "search.json", st)
                r.search = st
                _finish_workspace(second_ws, True)
        store.write(r.pdir, "choice.json", {"schema": store.SCHEMA, "key": r.key, "model": r.model, "agent": r.res.public(), "choice": rep.value,
                                            "shown": shown_of(st), "regions": regions_of(plan),
                                            "session": {"steps": out.steps, "turns": out.turns, "repairs": out.repairs, "status": out.status,
                                                        "elapsed": round(out.elapsed)}})
        r.choice = rep.value
        _finish_workspace(ws, True)
        picked = sum(1 for w in rep.value["wants"].values() if w["pick"])
        tight_n = sum(1 for reg in rep.value["regions"].values() if reg.get("action") == "tight" and reg.get("confirmed"))
        ctx.progress(1.0, "Agent đã chọn %d/%d hình." % (picked, len(rep.value["wants"])))
        return {"choose": {"wants": len(rep.value["wants"]), "picked": picked, "regions": len(rep.value["regions"]), "regions_tight": tight_n,
                           "session": {"steps": out.steps, "turns": out.turns, "repairs": out.repairs, "elapsed": round(out.elapsed)}}}

    # ---------------------------------------------------------------------------------------------------------- the web round (only with the owner's switch on)
    def first_choice() -> dict:
        d = r.load_choice()
        return d["choice"] if d else (r.choice or {"wants": {}, "regions": {}})

    def web_done(ctx) -> bool:
        r.begin()
        st = r.search or r.load_search()
        return bool(st and webround.searched(st))

    def run_web(ctx):
        r.begin()
        plan = r.plan or r.load_plan()
        st = r.search or r.load_search() or asearch.new_state()
        if plan is None:
            raise PartError("picks_auto_no_output", texts.vi("picks_auto_no_output"))

        def save(s):
            s["key"] = r.key
            store.write(r.pdir, "search.json", s)
        web = r.web(st)
        st = webround.search_round_two(r.pdir, shapes.wants_of(plan), st, first_choice(), main_key=r.inp.painting.key, web=web,
                                       fetch_thumb=r.s.get("fetch_thumb") or asearch.default_fetch_thumb, clock=r.s.get("clock") or time.time,
                                       cancelled=ctx.cancelled, progress=ctx.progress, save=save)
        if ctx.cancelled():
            return None
        r.search = st
        again = webround.second_wants(st)
        ctx.progress(1.0, "Tìm thêm xong: %d hình có ứng viên mới." % len(again))
        return {"web": {**(st.get("web") or {}), "wants_with_new_candidates": len(again), "budget_short": len((st.get("round2") or {}).get("budget") or [])}}

    def choose2_done(ctx) -> bool:
        r.begin()
        st = r.search or r.load_search()
        if st is None:
            return False
        again = webround.second_wants(st)
        if not again:
            return True                                           # nothing new to look at: the model is not called
        d = r.load_choice2()
        return bool(d and d.get("shown") == again)

    def run_choose2(ctx):
        r.begin()
        plan = r.plan or r.load_plan()
        st = r.search or r.load_search() or asearch.new_state()
        if plan is None:
            raise PartError("picks_auto_no_output", texts.vi("picks_auto_no_output"))
        again = webround.second_wants(st)
        if not again:
            ctx.progress(1.0, "Không có hình mới nào để chọn lại: bỏ qua bước này.")
            return {"choose2": {"wants": 0, "skipped": True}}
        if ctx.cancelled():
            return None
        try:
            ws, cctx = workspace.build_choose(r.inp, plan, webround.second_search_view(st, first_choice()), lim["choose"], books=[], second=True)
        except workspace.WorkspaceError as e:
            raise PartError(e.code, texts.vi(e.code, e.message))
        ctx.progress(0.02, "Đã chuẩn bị các tờ hình mới cho agent.")
        out, rep = _session(r, ctx, ws, "choose2", "Agent đang chọn lại hình", lim["choose"])
        if out.status == "cancelled" or ctx.cancelled():
            shutil.rmtree(ws.root, ignore_errors=True)
            return None
        if out.status == "tampered" or not rep.ok:
            raise _fail(out, ctx)
        store.write(r.pdir, "choice2.json", {"schema": store.SCHEMA, "key": r.key, "model": r.model, "agent": r.res.public(), "choice": rep.value,
                                             "shown": again, "session": {"steps": out.steps, "turns": out.turns, "repairs": out.repairs,
                                                                         "status": out.status, "elapsed": round(out.elapsed)}})
        r.choice2 = rep.value
        _finish_workspace(ws, True)
        picked = sum(1 for w in rep.value["wants"].values() if w["pick"])
        ctx.progress(1.0, "Agent đã chọn %d/%d hình trong số hình mới." % (picked, len(rep.value["wants"])))
        return {"choose2": {"wants": len(rep.value["wants"]), "picked": picked,
                            "session": {"steps": out.steps, "turns": out.turns, "repairs": out.repairs, "elapsed": round(out.elapsed)}}}

    # ---------------------------------------------------------------------------------------------------------- part 4: write
    def run_write(ctx):
        r.begin()
        plan = r.plan or r.load_plan()
        st = r.search or r.load_search() or asearch.new_state()
        if plan is None:
            raise PartError("picks_auto_no_output", texts.vi("picks_auto_no_output"))
        choice = r.choice
        if choice is None:
            d = r.load_choice()
            choice = d["choice"] if d else {"wants": {}, "regions": {}}
        if r.web_on:                                            # the first and the second session as one choice (their picks mean the same candidates)
            second = r.choice2 or (r.load_choice2() or {}).get("choice")
            choice = webround.merge_choice(choice, second, st)
        if _stale(r):
            raise PartError("picks_auto_stale", texts.vi("picks_auto_stale"))
        try:
            res = awrite.run(r.pdir, r.inp, plan, st, choice, r.state, actor=actor_of(r.model), cancelled=ctx.cancelled,
                             progress=ctx.progress, fetch_asset=r.s.get("fetch_asset"), clock=r.s.get("clock") or time.time,
                             budget_s=r.s.get("write_budget_s") or awrite.WRITE_SECONDS)
        except awrite.WriteError as e:
            raise PartError(e.code, texts.vi(e.code, e.message))
        if res.get("stopped") == "cancelled":                      # a cancelled write is not a finished run: it resumes from what was written
            return None
        sentence = texts.result_sentence(res["lines_done"], res["lines_total"], len(res["lines_without"]))
        if res["lines_removed"]:
            sentence += " Đã bỏ %d đoạn không còn trong lời dẫn." % res["lines_removed"]
        out = {k: v for k, v in res.items() if k != "reasons"}
        if r.web_on:                                            # how many web searches the run made (kept in search.json and in last.json too)
            out["web"] = st.get("web") or asearch.Web.from_state(st, True, r.web_max).public()
            sentence += webround.web_sentence(out["web"])
        out.update(sentence=sentence, agent=r.res.public(), limits={"plan": lim["plan"].public(), "choose": lim["choose"].public()})
        _finish_run(r, out, res.get("reasons") or {}, ctx)
        ctx.progress(1.0, sentence)
        return out

    titles = webround.part_titles(r.web_on, texts.PART_TITLES)
    parts = [
        Part(key="plan", title=titles["plan"], run=run_plan, est_seconds=EST_SECONDS["plan"], is_done=plan_done),
        Part(key="search", title=titles["search"], run=run_search, est_seconds=EST_SECONDS["search"], is_done=search_done),
        Part(key="choose", title=titles["choose"], run=run_choose, est_seconds=EST_SECONDS["choose"], is_done=choose_done),
    ]
    if r.web_on:                                                # the second round: more searches (paid, counted) and one more choosing session
        parts += [Part(key="web", title=titles["web"], run=run_web, est_seconds=EST_SECONDS["web"], is_done=web_done),
                  Part(key="choose2", title=titles["choose2"], run=run_choose2, est_seconds=EST_SECONDS["choose2"], is_done=choose2_done)]
    return parts + [Part(key="write", title=titles["write"], run=run_write, est_seconds=EST_SECONDS["write"])]


def _books_for(pdir: Path, st: dict) -> list[dict]:
    return [{"n": b["n"], "label": b["label"], "source_id": b["source_id"], "thumb": (Path(pdir) / b["thumb"]) if b.get("thumb") else None}
            for b in (st.get("books") or [])]


def _stale(r: _Run) -> bool:
    """Did the narration or the main painting change while the agent worked? Then what it chose does not fit any more."""
    from bti.picks import context, doc
    try:
        nv = context.narration_view(r.pdir)
        return nv["rev"] != r.inp.narration_rev or doc.load_or_new(r.pdir).get("main_asset") != r.inp.painting.key
    except Exception:       # noqa: BLE001 - a damaged document is for the write part to say
        return False


def _finish_run(r: _Run, result: dict, reasons: dict, ctx) -> None:
    prev = store.read(r.pdir, "last.json") or {}
    merged = dict(prev.get("reasons") or {})
    merged.update({b: v["reason"] for b, v in reasons.items()})
    for b in list(merged):                                       # a line that was redone without a reason (a keep line has one too) keeps none
        if b in r.inp.targets and b not in reasons:
            merged.pop(b)
    store.write(r.pdir, "last.json", {"schema": store.SCHEMA, "finished": time.time(), "job_id": ctx.job_id, "result": result, "reasons": merged,
                                      "model": r.model, "agent": r.res.public()})
    r.state["stage"] = "done"
    store.save_run(r.pdir, r.state)
    store.prune_runs(r.pdir)


# ---------------------------------------------------------------------------------------------------------------- start
def _limits(kw: dict) -> dict:
    return {"plan": kw.get("plan_limits") or PLAN_LIMITS, "choose": kw.get("choose_limits") or CHOOSE_LIMITS}


def start(pid: str, pdir: Path, *, beats: list | None = None, redo: bool = False, base_rev: str | None = None, model: str | None = None,
          owner_note: str = "", manager=None, by_run: bool = False, **seams) -> dict:
    """Start the job; -> the job's public record (`["id"]`). Raises `AutoError` (the refusals of the route, with their HTTP status).
    `by_run`: the caller is the automatic run (it takes this action itself as its step): the run's own job is not a reason to refuse, any other caller
    is refused while a run goes on. `seams` (tests): search, wiki_search, web (`{"on", "max", "search"}`: the owner's switch, the budget and the web search),
    fetch_thumb, fetch_book_thumb, fetch_asset, clock, python, guard_factory, plan_limits, choose_limits, search_budget_s, write_budget_s."""
    pdir = Path(pdir)
    if not isinstance(redo, bool):
        raise AutoError("invalid", "redo must be true or false", 422)
    if model is not None and (not isinstance(model, str) or draft_run._bad_model_name(model)):
        raise AutoError("bad_model", "the model name is not valid", 422)
    inp = ainputs.load(pdir, beats, redo=redo, owner_note=owner_note)
    if base_rev is not None:
        from bti.picks import doc
        cur = doc.revision(inp.picks)
        if base_rev != cur:
            raise AutoError("stale", "the picks changed since you read them", 409, rev=cur)
    res = draft_run._resolve(pdir, ROLE, model)
    try:
        session.check_installed(res.model)
    except DraftError as e:
        raise AutoError(e.code, e.message, 409)
    run = _Run(pdir, pid, inp, res, limits=_limits(seams), seams=seams)
    m = manager or _manager()
    other = draft_run.other_agent_job(pid, KIND, m, run_ok=by_run)      # join2: a prompt-box turn, a draft or an automatic run holds the one agent: one at a time
    if other is not None:
        raise AutoError("agent_job_running", "%s is working on this project: wait for it or cancel it, then call again" % draft_run.AGENT_JOB_WHO.get(other.get("kind"), "another job"),
                        409, job_id=other.get("id"))
    meta = {"action": ACTION, "model": res.model, "agent": res.public(), "beats": list(inp.targets), "redo": bool(redo),
            "limits": {"plan": run.limits["plan"].public(), "choose": run.limits["choose"].public()},
            "web": {"on": run.web_on, "max": run.web_max}}
    try:
        return m.start(kind=KIND, pid=pid, project_dir=pdir, parts=make_parts(run), meta=meta)
    except Exception as e:      # noqa: BLE001
        if type(e).__name__ == "Busy":
            raise AutoError("busy", "a picks job is already running for this project", 409, job_id=getattr(e, "job_id", None))
        raise


def escalate(pid: str, pdir: Path, beat_ids: list[str], *, note: str = "", model: str | None = None, base_rev: str | None = None, **seams) -> dict:
    """The plain function the instruction box of step 4 calls when a request needs more than typed operations can do (a new picture to be
    found and chosen): the agent works on exactly these lines, choosing them again (`redo`), with the owner's words (`note`) in front of it.
    Same refusals and the same answer as `start`."""
    return start(pid, pdir, beats=list(beat_ids), redo=True, base_rev=base_rev, model=model, owner_note=note, **seams)


# ---------------------------------------------------------------------------------------------------------------- what the page asks
def active_job(pid: str) -> dict | None:
    """The running automatic job of the project (its public record), else None."""
    try:
        rec = _manager().active(pid, kind=KIND)
    except Exception:       # noqa: BLE001
        return None
    return rec if rec and (rec.get("meta") or {}).get("action") == ACTION else None


def overview(pid: str, pdir: Path) -> dict:
    """`GET /api/projects/{pid}/picks/auto`: the running job, the last result, the reasons the agent gave per line, the agent that would run."""
    last = store.read(pdir, "last.json") or {}
    res = draft_run._resolve(pdir, ROLE, None)
    return {"running": active_job(pid), "last": {k: last.get(k) for k in ("finished", "job_id", "result", "model", "agent")} if last else None,
            "reasons": last.get("reasons") or {}, "agent": res.public(),
            "limits": {"plan": PLAN_LIMITS.public(), "choose": CHOOSE_LIMITS.public(),
                       "search_seconds": asearch.SEARCH_SECONDS, "write_seconds": awrite.WRITE_SECONDS},
            "web": websettings.for_run()}
