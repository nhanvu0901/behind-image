"""The video's title (worker titlestep; the package is `bti/title/`, the skill is `skills/title/`).

    GET  /api/projects/{pid}/title            -> {rev, state, title, candidates, narration_rev, current_narration_rev, stale, agent, running, history, written, limits, storyboard, problems}
        `state` is `none` | `done` | `stale` (an agent's title written from a narration that has changed). `title` is the title in use ({text, by, at, source, option}).
    POST /api/projects/{pid}/title/generate   {note?, model?, actor?}  -> {job_id, model, agent}       (a long job of kind `title`: /api/longjobs/{id})
        An agent reads the approved narration and writes the title by the skill; the first of its candidates becomes the title in use. `note` is the owner's wish in their
        words (at most 600 characters), put into the agent's task. 409 `narration_not_approved`, `agent_job_running`, `busy`, and the codes of an agent that cannot run.
    PUT  /api/projects/{pid}/title            {base_rev, text | option, actor?}  -> {rev, state, title, candidates, storyboard}
        A person or an operator sets the title: `text` (one line of at most 60 characters; the banned phrases are not looked for) or `option` (the number, from 1, of a
        candidate). Never stale afterwards. When the project has a storyboard the channel identity is applied again with the new title in the same request: its
        revision changes, its approval stops standing, and `storyboard.sentence` says so. 409 `stale_revision` (`rev`), 422 `title_invalid` / `title_not_one_line` /
        `title_too_long` / `title_option_unknown` / `title_choice_needed`.

Mounted by `create_app` (it needs the app's own storyboard lock, revision and save path, as the identity route does); `create_app` also registers the function that applies a
title to the storyboard (`bti.title.apply`) for the job that writes one."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Body

from bti import auto as rule
from bti import identity as ID
from bti.engine import registry as R
from bti.ops import things
from bti.title import apply as tapply, job as tjob, store, texts, view
from bti.title.store import TitleError

from .auto_api import actor_of
from .common import ApiError, compute_rev, read_json, storyboard_approval, strip_derived
from .engine_adapter import ENGINE_LOCK


def _api(e: TitleError) -> ApiError:
    return ApiError(e.status, e.message, code=e.code, **e.extra)


def make_router(root: Path, *, pdir: Callable, project: Callable, saved_storyboard: Callable, commit: Callable, slock: Callable, load_style: Callable) -> APIRouter:
    """The app's own helpers, as the identity route takes them (`create_app` gives them)."""
    router = APIRouter(prefix="/api/projects/{pid}/title")

    def main_asset(d: Path) -> str | None:
        try:
            picks = read_json(d / "picks.json")
        except (OSError, ValueError):
            return None
        m = picks.get("main_asset") if isinstance(picks, dict) else None
        return m if isinstance(m, str) and m else None

    def apply_title(pid: str, title: str | None) -> dict | None:
        """Apply the channel identity again with `title` on the saved storyboard, under the storyboard lock and through the app's save path. None: the project has no storyboard,
        or its style has no identity block. When nothing would change nothing is written (the storyboard's approval keeps standing)."""
        d = pdir(pid)
        if not (d / "storyboard.json").is_file():
            return None
        p = project(pid)
        with slock(pid):
            saved = saved_storyboard(pid)
            style_id = saved.get("style") if isinstance(saved.get("style"), str) and saved.get("style") else "gae"
            try:
                style = load_style(style_id)
            except Exception:           # noqa: BLE001 - a style that cannot be read has no identity styles
                style = {}
            style = style if isinstance(style, dict) else {}
            cfg = ID.read(style)
            if cfg is None:
                return None
            want = ID.chosen_style(saved, style) or cfg.default_style
            if not want or cfg.style(want) is None:
                return None
            with ENGINE_LOCK:
                timing = p.timing()
            meta: dict[str, Any] = {}
            m = main_asset(d)
            if m:
                meta["main_asset"] = m
            try:
                bundle = R.load_bundle(style_id)
            except Exception:           # noqa: BLE001
                bundle = None
            try:
                new, report = ID.apply_identity(ID.with_video_title(saved, title), want, style, timing, meta, defaults=bundle.param_defaults if bundle else None)
            except ID.IdentityError as e:
                raise ApiError(422, e.message, code=e.code)
            fresh = storyboard_approval(saved) == "fresh"
            if things.canon(new) == things.canon(saved):
                return {"rev": compute_rev(saved), "changed": [], "approval_was_fresh": False, "sentence": texts.storyboard_sentence(0, False)}
            doc = strip_derived(new)
            doc["approvals"] = saved.get("approvals") or {"storyboard": None}      # server-owned: the approval names the old revision, so it stops standing
            done = commit(pid, p, doc)
        return {"rev": done["rev"], "changed": report["changed"], "approval_was_fresh": fresh, "sentence": texts.storyboard_sentence(len(report["changed"]), fresh)}

    tapply.register(root, apply_title)

    @router.get("")
    def get_title(pid: str):
        return view.overview(pid, pdir(pid))

    @router.post("/generate")
    def post_generate(pid: str, body: dict = Body(default={})):
        d = pdir(pid)
        body = body if isinstance(body, dict) else {}
        actor = actor_of(body)
        model = body.get("model")
        if model is not None and not isinstance(model, str):
            raise ApiError(422, "model must be text", code="bad_model", field="model")
        try:
            rec = tjob.start(pid, d, note=body.get("note"), model=model or None, actor=actor, by_run=actor == rule.RUN_ACTOR)
        except TitleError as e:
            raise _api(e)
        meta = rec.get("meta") or {}
        return {"job_id": rec["id"], "model": meta.get("model"), "agent": meta.get("agent")}

    @router.put("")
    def put_title(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        if not isinstance(body, dict):
            raise ApiError(422, "the body must be an object", code="invalid_request")
        actor = actor_of(body)
        try:
            doc = store.set_title(d, base_rev=body.get("base_rev"), actor=actor, text=body.get("text"), option=body.get("option"))
        except TitleError as e:
            raise _api(e)
        sb = tapply.apply_to_storyboard(d, doc["chosen"]["text"])
        out = {"rev": store.revision(doc), "state": store.state_of(doc, store.narration_rev(d)), "title": doc["chosen"], "candidates": doc["candidates"]}
        out["storyboard"] = sb
        return out

    return router
