"""Adapter between the editor backend and the engine facade (design 8.1, 8.3).

`bti.engine.api` is imported lazily, once per app start, never at import of
this package. When it is missing or broken, or when it fails to open a
project, the stub in `engine_stub.py` is used. Every call into a project
object must hold `ENGINE_LOCK`: the engine is not guaranteed thread-safe.
"""
from __future__ import annotations

import importlib
import threading
from pathlib import Path
from typing import Any

from bti.engine.errors import DataError

from .engine_stub import StubProject, load_style_stub

ENGINE_LOCK = threading.RLock()


def import_facade(name: str) -> Any | None:
    """Import a facade module; None when missing or broken (never raises)."""
    try:
        return importlib.import_module(name)
    except BaseException as e:  # noqa: BLE001 - a broken facade must not crash the app
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        return None


class EngineAdapter:
    def __init__(self, projects_root: Path, style_root: Path, module: Any = "auto"):
        self.projects_root = Path(projects_root)
        self.style_root = Path(style_root)
        if module == "auto":
            module = import_facade("bti.engine.api")
        if module is not None and not (hasattr(module, "open_project") and hasattr(module, "load_style")):
            module = None
        self.module = module
        self.mode = "real" if module is not None else "stub"
        self.fallbacks: dict[str, str] = {}
        self._projects: dict[str, Any] = {}
        self._previews: dict[str, tuple[Any, threading.RLock]] = {}

    def _open(self, pid: str, record_fallback: bool):
        pdir = self.projects_root / pid
        p = None
        if self.module is not None:
            try:
                p = self.module.open_project(pdir)
            except BaseException as e:  # noqa: BLE001
                if isinstance(e, (KeyboardInterrupt, SystemExit, DataError)):
                    raise                    # damaged data is the project's problem, not a reason to run the stub
                if record_fallback:
                    self.fallbacks[pid] = f"{type(e).__name__}: {e}"[:300]
        return p if p is not None else StubProject(pdir, self.style_root)

    def project(self, pid: str):
        p = self._projects.get(pid)
        if p is not None:
            return p
        with ENGINE_LOCK:
            p = self._projects.get(pid)
            if p is None:
                p = self._projects[pid] = self._open(pid, True)
        return p

    def preview_project(self, pid: str):
        """(project, lock) for preview rendering: a SECOND engine instance of the project with its own lock, so that a long
        render never holds ENGINE_LOCK (stills, validation and opening a project keep answering). The image and layer caches
        are process-wide and thread-safe, so the two instances share them."""
        with ENGINE_LOCK:
            hit = self._previews.get(pid)
            if hit is None:
                hit = self._previews[pid] = (self._open(pid, False), threading.RLock())
        return hit

    def forget(self, pid: str) -> None:
        self._projects.pop(pid, None)
        self._previews.pop(pid, None)

    def load_style(self, style_id: str) -> dict:
        if self.module is not None:
            try:
                with ENGINE_LOCK:
                    out = self.module.load_style(style_id)
                if isinstance(out, dict) and "techniques" in out:
                    out.setdefault("style", {})
                    out.setdefault("intents", sorted({i for t in out["techniques"] for i in (t.get("intents") or [])}))
                    return out
            except FileNotFoundError:
                pass
            except Exception:
                pass
        return load_style_stub(self.style_root, style_id)

    def health(self) -> dict:
        d = {"engine": self.mode}
        if self.fallbacks:
            d["engine_fallbacks"] = dict(self.fallbacks)
        return d
