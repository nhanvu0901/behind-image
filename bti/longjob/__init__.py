"""Long jobs and the heavy slot (shared by the voice, picks-suggest, draft and export stages).

    from bti.longjob import manager, Part
    job_id = manager.start(kind="voice", pid=pid, project_dir=d, parts=[Part(key=..., title=..., run=fn, heavy=True, est_seconds=900)])

`router` (FastAPI, three routes) is imported on first use so that this package does not need FastAPI to be imported."""
from .config import ServerConfig, load as load_config
from .heavy import Cancelled, HeavySlot
from .manager import Busy, Context, LongJobManager, Part, PartError, ProcessHandle, ProjectGone, manager

__all__ = ["manager", "Part", "Context", "ProcessHandle", "Busy", "PartError", "ProjectGone", "LongJobManager", "HeavySlot", "Cancelled",
           "ServerConfig", "load_config", "router"]


def __getattr__(name: str):
    if name == "router":
        from .api import router
        return router
    raise AttributeError(name)
