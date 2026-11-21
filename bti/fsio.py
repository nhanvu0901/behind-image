"""File-finishing helper shared by the whole code base.

Every write in bti/ is "write `<name>.part`, then rename over `<name>`". On Windows another process (antivirus, the indexer,
a reader that still has the file open) can hold a file for a moment, and the rename then fails with PermissionError
(WinError 5) or a sharing violation (WinError 32). `atomic_replace` retries for about three seconds in that case and
then raises the original error. Elsewhere it is a plain `os.replace`."""
from __future__ import annotations

import os
import time

IS_WINDOWS = os.name == "nt"
SHARING_ERRORS = (5, 32)           # ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION
PAUSES = (0.05, 0.1, 0.15, 0.25, 0.4, 0.6, 0.8, 0.65)   # about 3.0 s in all

# hooks, replaced in tests. `_replace` is None unless a test injects its own function: then `os.replace` is looked up at
# every call, so a caller that patches `os.replace` itself still reaches the write.
_replace = None
_sleep = time.sleep


def _do_replace(src, dst) -> None:
    (_replace or os.replace)(src, dst)


def _retryable(e: OSError) -> bool:
    return isinstance(e, PermissionError) or getattr(e, "winerror", None) in SHARING_ERRORS


def atomic_replace(src, dst) -> None:
    """os.replace(src, dst); on Windows retried on PermissionError / WinError 5 / 32 with a growing pause (about 3 s
    in all), then the last error is raised."""
    if not IS_WINDOWS:
        _do_replace(src, dst)
        return
    for pause in PAUSES:
        try:
            _do_replace(src, dst)
            return
        except OSError as e:
            if not _retryable(e):
                raise
        _sleep(pause)
    _do_replace(src, dst)             # the last try: its error (if any) is the one raised
