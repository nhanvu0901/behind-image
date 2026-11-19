"""The channel identity of a project: which opening, channel-name beat and chapter marks the video gets (contract
docs/design/2026-11-18-identity-raking-light.md, section 7). Mounted by `create_app` (it needs the app's own storyboard lock,
revision and save path, so that a choice is saved exactly the way a storyboard save is, with the same `history/` copy).

    GET /api/projects/{pid}/identity   -> {style, default, options: [{id, label}]}
        `style` is the style the owner or an agent chose (null while none was: the old cards), `default` the style a new draft gets,
        `options` what may be chosen, with the words the page shows.
    PUT /api/projects/{pid}/identity   {style, base_rev}
        -> {rev, style, changed: [shot ids], skipped: [{shot, reason, what, message}]}
        Applies the style to the saved storyboard under the project's storyboard lock. 409 when `base_rev` is not the saved
        revision (nothing is written), 422 for a style that is not in `options` or a result the engine refuses.

An agent that wants another look for the video calls PUT; it never writes title cards or chapter cards by hand.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Body

from bti import identity as ID
from bti.engine import registry as R

from .common import ApiError, compute_rev, read_json, strip_derived
from .engine_adapter import ENGINE_LOCK


def make_router(root: Path, *, pdir: Callable, project: Callable, saved_storyboard: Callable, commit: Callable, slock: Callable,
                load_style: Callable) -> APIRouter:
    """`pdir(pid)`, `project(pid)`, `saved_storyboard(pid)`, `commit(pid, p, doc)` and `slock(pid)` are the app's own helpers
    (404 for an unknown project or a missing storyboard, 409 for a damaged file, the storyboard lock, validate and save);
    `load_style(style_id)` gives the style.json document of a style."""
    router = APIRouter(prefix="/api/projects/{pid}/identity")

    def style_doc(sb: Any) -> dict:
        style_id = sb.get("style") if isinstance(sb, dict) and isinstance(sb.get("style"), str) and sb.get("style") else "gae"
        try:
            doc = load_style(style_id)
        except Exception:               # noqa: BLE001 - a style that cannot be read has no identity styles
            return {}
        return doc if isinstance(doc, dict) else {}

    def main_asset(d: Path) -> str | None:
        """The main painting the owner chose (picks.json), the same one the draft compiler passes."""
        try:
            picks = read_json(d / "picks.json")
        except (OSError, ValueError):
            return None
        m = picks.get("main_asset") if isinstance(picks, dict) else None
        return m if isinstance(m, str) and m else None

    @router.get("")
    def get_identity(pid: str):
        d = pdir(pid)
        sb: dict = {}
        if (d / "storyboard.json").is_file():
            sb = saved_storyboard(pid)
        style = style_doc(sb)
        cfg = ID.read(style)
        if cfg is None:
            return {"style": None, "default": None, "options": []}
        return {"style": ID.chosen_style(sb, style), "default": cfg.default_style, "options": cfg.options()}

    @router.put("")
    def put_identity(pid: str, body: dict = Body(...)):
        want = body.get("style") if isinstance(body, dict) else None
        base = body.get("base_rev") if isinstance(body, dict) else None
        if not isinstance(want, str) or not want:
            raise ApiError(422, "style (string) is required", code="identity_style_required")
        if not isinstance(base, str) or not base:
            raise ApiError(422, "base_rev (string) is required", code="invalid_request", field="base_rev")
        p = project(pid)
        d = pdir(pid)
        with slock(pid):
            saved = saved_storyboard(pid)               # also re-checks, under the lock, that the project still exists
            style = style_doc(saved)
            cfg = ID.read(style)
            if cfg is None or cfg.style(want) is None:
                allowed = cfg.ids() if cfg else []
                raise ApiError(422, "unknown identity style %r (choose one of: %s)" % (want[:40], ", ".join(allowed) or "none"),
                               code="identity_style_unknown", allowed=allowed)
            cur = compute_rev(saved)
            if base != cur:
                raise ApiError(409, "base_rev does not match the saved revision", rev=cur, code="stale_revision")
            with ENGINE_LOCK:
                timing = p.timing()
            meta = {}
            m = main_asset(d)
            if m:
                meta["main_asset"] = m
            try:
                bundle = R.load_bundle(saved.get("style") if isinstance(saved.get("style"), str) and saved.get("style") else "gae")
            except Exception:           # noqa: BLE001 - no registry, no defaults: the techniques are written with the params the style needs
                bundle = None
            try:
                new, report = ID.apply_identity(saved, want, style, timing, meta, defaults=bundle.param_defaults if bundle else None)
            except ID.IdentityError as e:
                raise ApiError(422, e.message, code=e.code)
            doc = strip_derived(new)
            doc["approvals"] = saved.get("approvals") or {"storyboard": None}      # server-owned
            done = commit(pid, p, doc)
        return {"rev": done["rev"], "style": want, "changed": report["changed"], "skipped": report["skipped"]}

    return router
