"""Fit the storyboard to the voice again (worker introflow; the function is `bti/draft/retime.py`).

    POST /api/projects/{pid}/storyboard/retime   {base_rev, actor?}   -> {rev, changed: [shot ids], report}

Why: the cards, the channel-name beat and the end of the video are anchored by absolute time, so a voice assembled again (another lead or title
silence, a sentence read again) leaves them where the old voice put them. `report` is `retime`'s own (inserted, removed, moved, end, left,
identity, video_title). It commits the way the identity route does (the storyboard lock, validation, the page's save with its `history/` copy), adds ONE
batch to the change log (`bti changes`, `bti undo`: the whole document the batch changed comes back, the shots, the end of the video and the `identity`
object, see `bti.ops.undo`) and leaves the storyboard's approval to go stale by the existing rule (its revision changed). When nothing changes it writes
nothing and the answer's `rev` is the one the caller sent, `changed` empty.

The video's title is written onto the channel-name beat here too: the title document of the project (`title.json`, `bti.title.chosen_text`) wins over the
`identity.video_title` the storyboard carries, as it does in a full compile. A title set while the storyboard was off the voice (`title.set` and
`title.generate` store it and say the storyboard takes it later; `PUT .../identity` refuses with `storyboard_off_voice`) reaches the beat by this call.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Body

from bti.draft import retime as RT
from bti.draft.inputs import DraftError
from bti.engine import registry as R
from bti.ops import things
from bti.ops.batch import ACTOR_FORMS, _ACTOR
from bti.ops.log import ChangeLog
from bti.script.store import now_iso
from bti.title import chosen_text

from .common import ApiError, compute_rev, read_json, strip_derived
from .engine_adapter import ENGINE_LOCK

NOTE = "khớp lại với giọng đọc"


def make_router(root: Path, *, pdir: Callable, project: Callable, saved_storyboard: Callable, commit: Callable, slock: Callable,
                load_style: Callable) -> APIRouter:
    """The app's own helpers, as the identity route takes them (`create_app` gives them)."""
    router = APIRouter(prefix="/api/projects/{pid}/storyboard")

    def main_asset(d: Path) -> str | None:
        try:
            picks = read_json(d / "picks.json")
        except (OSError, ValueError):
            return None
        m = picks.get("main_asset") if isinstance(picks, dict) else None
        return m if isinstance(m, str) and m else None

    def what_of(sid: str, report: dict) -> str:
        """The Vietnamese sentence of the change log for one shot."""
        if sid in report["inserted"]:
            return "Cảnh %s: thêm cảnh mở đầu cho cả bức tranh" % sid
        if sid in report["removed"]:
            return "Cảnh %s: bỏ cảnh mở đầu (giọng đọc bắt đầu sớm)" % sid
        if any(o["shot"] == sid for o in report["overlays"]):
            return "Cảnh %s: điều chỉnh lớp phủ cho khớp thời lượng" % sid
        if any(m["shot"] == sid for m in report["moved"]):
            return "Cảnh %s: dời cho khớp với giọng đọc" % sid
        return "Cảnh %s: làm lại phần mở đầu và tên kênh cho khớp" % sid

    @router.post("/retime")
    def post_retime(pid: str, body: dict = Body(default={})):
        body = body if isinstance(body, dict) else {}
        base = body.get("base_rev")
        if not isinstance(base, str) or not base:
            raise ApiError(422, "base_rev (string) is required", code="invalid_request", field="base_rev")
        actor = body.get("actor", "human")
        if not isinstance(actor, str) or not _ACTOR.match(actor):
            raise ApiError(422, "actor must be human, agent:<model id> or cli:<name>", code="invalid_request", field="actor", allowed=ACTOR_FORMS)
        p = project(pid)
        d = pdir(pid)
        with slock(pid):
            saved = saved_storyboard(pid)               # also re-checks, under the lock, that the project still exists
            cur = compute_rev(saved)
            if base != cur:
                raise ApiError(409, "base_rev does not match the saved revision", rev=cur, code="stale_revision")
            style_id = saved.get("style") if isinstance(saved.get("style"), str) and saved.get("style") else "gae"
            try:
                style = load_style(style_id)
            except Exception:                           # noqa: BLE001 - a style that cannot be read has no identity block: the old cards are judged
                style = {}
            with ENGINE_LOCK:
                timing = p.timing()
            meta: dict[str, Any] = {}
            m = main_asset(d)
            if m:
                meta["main_asset"] = m
            try:
                bundle = R.load_bundle(style_id)
            except Exception:                           # noqa: BLE001 - no registry, no defaults
                bundle = None
            try:
                new, report = RT.retime(saved, timing, style if isinstance(style, dict) else {}, meta, defaults=bundle.param_defaults if bundle else None,
                                        video_title=chosen_text(d), project_dir=d)
            except DraftError as e:
                raise ApiError(422, e.message, code="timing_unusable")
            if things.canon(new) == things.canon(saved):
                return {"rev": cur, "changed": [], "report": report}
            doc = strip_derived(new)
            doc["approvals"] = saved.get("approvals") or {"storyboard": None}      # server-owned: the approval names the old revision, so it stops standing
            done = commit(pid, p, doc)
            after = saved_storyboard(pid)
            changed = RT.changed_ids(saved, after)
            try:                                        # one batch in the change log, like a batch of typed operations
                record = {"doc": "storyboard", "time": now_iso(), "actor": actor, "note": NOTE, "ops": [{"op": "retime"}], "applied": 1,
                          "changes": ([{"target": {"shot": sid}, "time": None, "what": what_of(sid, report)} for sid in changed]
                                      + [{"target": {"shot": o["shot"], "overlay": o["overlay"]}, "time": None,
                                          "what": "Cảnh %s, lớp phủ %s: %s" % (o["shot"], o["overlay"], {"shortened": "rút ngắn", "moved": "dời sớm", "removed": "đã bỏ"}[o["what"]]),
                                          "from": o["from"], "to": o["to"]} for o in report["overlays"]]),
                          "created": {"shots": list(report["inserted"]), "overlays": [], "assets": [], "refs": {}},
                          "rev_before": cur, "rev_after": done["rev"], "touched": things.changed_keys("storyboard", saved, after),
                          "undo_of": None, "scope": None}
                batch = ChangeLog(d).write(record, saved, after)
            except OSError:
                batch = None                            # the document stays written even if the log cannot be
        return {"rev": done["rev"], "changed": changed, "batch": batch, "report": report}

    return router
