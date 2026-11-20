"""How the title reaches the storyboard when one already exists. The app registers one function per projects folder (`register`, called by `create_app`): it applies the
channel identity again with the new title under the project's storyboard lock and the app's save path (the revision changes, so the storyboard's approval goes stale by the
existing rule). The job that writes a title and the route that sets one both call `apply_to_storyboard`; with no function registered (a bare test, a script) nothing is done.

    apply_to_storyboard(pdir, title) -> {"rev", "changed": [shot ids], "approval_was_fresh": bool, "sentence": str} | None     (None: no storyboard, or none registered)

It never raises: a title is written whether or not the storyboard could take it (the compiler writes it at the next draft, and the answer says what happened)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

log = logging.getLogger("bti.title")

_APPLIERS: dict[str, Callable] = {}


def register(projects_root: Path | str, fn: Callable | None) -> None:
    key = str(Path(projects_root).resolve())
    if fn is None:
        _APPLIERS.pop(key, None)
    else:
        _APPLIERS[key] = fn


def applier_for(pdir: Path | str) -> Callable | None:
    return _APPLIERS.get(str(Path(pdir).resolve().parent))


def apply_to_storyboard(pdir: Path | str, title: str | None) -> dict | None:
    fn = applier_for(pdir)
    if fn is None:
        return None
    try:
        return fn(Path(pdir).name, title)
    except Exception as e:      # noqa: BLE001 - the title is written; the storyboard takes it at the next draft or the next call
        log.warning("title: the storyboard of %s could not take the title", Path(pdir).name, exc_info=True)
        return {"rev": None, "changed": [], "approval_was_fresh": False, "error": str(getattr(e, "detail", None) or e)[:200],
                "sentence": "Chưa cập nhật được tựa video trên storyboard: %s" % (str(getattr(e, "detail", None) or e)[:160])}
