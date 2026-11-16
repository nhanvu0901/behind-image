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

    def project(self, pid: str):
        p = self._projects.get(pid)
        if p is not None:
            return p
        pdir = self.projects_root / pid
        with ENGINE_LOCK:
            p = self._projects.get(pid)
            if p is None:
                if self.module is not None:
                    try:
                        p = self.module.open_project(pdir)
                    except BaseException as e:  # noqa: BLE001
                        if isinstance(e, (KeyboardInterrupt, SystemExit)):
                            raise
                        self.fallbacks[pid] = f"{type(e).__name__}: {e}"[:300]
                        p = None
                if p is None:
                    p = StubProject(pdir, self.style_root)
                self._projects[pid] = p
        return p

    def forget(self, pid: str) -> None:
        self._projects.pop(pid, None)

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
