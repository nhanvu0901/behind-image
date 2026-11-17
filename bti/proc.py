"""Child-process control that works on macOS, Linux and Windows.

POSIX: the child leads its own session, so a signal to the group reaches its children too.
Windows: the child gets its own process group and no console window; the whole tree is ended with `taskkill /T /F`
(there is no `os.killpg` there)."""
from __future__ import annotations

import os
import signal
import subprocess

IS_WINDOWS = os.name == "nt"


def group_kwargs() -> dict:
    """Extra keyword arguments for subprocess.Popen so that kill_tree() can end the child and all it started."""
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def kill_tree(proc: subprocess.Popen, grace: float = 2.0) -> None:
    """End `proc` and everything it started. Never raises. `grace` is only used on POSIX (SIGTERM first, then SIGKILL)."""
    if IS_WINDOWS:
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=20,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            break
        try:
            proc.wait(timeout=grace)
            break
        except subprocess.TimeoutExpired:
            continue
    try:
        proc.kill()
    except OSError:
        pass
