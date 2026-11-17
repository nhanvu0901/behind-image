"""The heavy slot: one heavy part at a time, and on the server the benchmark's lock-folder protocol.

In-process: a mutex, so two heavy parts of any two projects never overlap inside this app.
Server (a lock folder is configured): before a part starts, in this order
  1. no production process (command line matching a configured pattern) and no ffmpeg that is not ours,
  2. free virtual memory at least the configured floor,
  3. an atomic `mkdir` of the lock folder, then `owner.txt` (host, process id, time, what runs, expected end).
If any step fails the part is `waiting` (the note says why, in Vietnamese) and everything is retried every 60 seconds.
The lock is released in `finally`, and only when its `owner.txt` is ours. A lock that is not ours is never removed: when it is
older than 60 minutes it is reported (`alerts`, and the note) and we keep waiting. At start-up (and while waiting) a lock of
ours whose process is dead is released.

Every probe (memory, process list, process liveness, the lock folder) is behind a small interface; `fakes.py` has twins, so
the whole protocol runs on any machine with a clock and a sleep that tests inject."""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Protocol

from .config import ServerConfig

APP_MARK = "behind-the-image"
RETRY_SECONDS = 60.0
STALE_SECONDS = 60 * 60.0
IS_WINDOWS = os.name == "nt"


class Cancelled(Exception):
    """The job was cancelled while it waited for, or held, the heavy slot."""


class HeavyError(Exception):
    """The lock folder cannot be used (not writable, owner.txt cannot be written)."""


@dataclass(frozen=True)
class ProcInfo:
    pid: int
    ppid: int
    name: str
    cmdline: str


class Probes(Protocol):
    def host(self) -> str: ...
    def own_pid(self) -> int: ...
    def free_virtual_kb(self) -> int | None: ...
    def processes(self) -> list[ProcInfo]: ...
    def pid_alive(self, pid: int) -> bool: ...


class LockFolder(Protocol):
    def mkdir(self) -> bool: ...                          # atomic: False when it already exists
    def exists(self) -> bool: ...
    def read_owner(self) -> str | None: ...
    def write_owner(self, text: str) -> None: ...
    def age_seconds(self, now: float) -> float | None: ...
    def remove(self) -> None: ...


# ---------------------------------------------------------------- real probes

def _quiet() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}


def _run_text(cmd: list[str], timeout: float = 40.0) -> str | None:
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, **_quiet())
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    return p.stdout.decode("utf-8", "replace")


class SystemProbes:
    """The real machine. Windows: PowerShell + CIM (as the benchmark's guard.ps1 did). Elsewhere: /proc and `ps`, best effort."""

    def host(self) -> str:
        return socket.gethostname()

    def own_pid(self) -> int:
        return os.getpid()

    def free_virtual_kb(self) -> int | None:
        if IS_WINDOWS:
            out = _run_text(["powershell", "-NoProfile", "-Command",
                             "(Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory"])
            try:
                return int((out or "").strip().splitlines()[-1])
            except (ValueError, IndexError):
                return None
        try:
            info = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, _, v = line.partition(":")
                info[k] = int(v.split()[0])
            return info["MemAvailable"] + info.get("SwapFree", 0)
        except (OSError, KeyError, ValueError, IndexError):
            return None

    def processes(self) -> list[ProcInfo]:
        out: list[ProcInfo] = []
        if IS_WINDOWS:
            text = _run_text(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine "
                              "| ConvertTo-Json -Compress"], timeout=60)
            try:
                rows = json.loads(text or "[]")
            except ValueError:
                return out
            if isinstance(rows, dict):
                rows = [rows]
            for r in rows:
                try:
                    out.append(ProcInfo(int(r["ProcessId"]), int(r.get("ParentProcessId") or 0),
                                        str(r.get("Name") or ""), str(r.get("CommandLine") or "")))
                except (KeyError, TypeError, ValueError):
                    continue
            return out
        text = _run_text(["ps", "-axo", "pid=,ppid=,comm=,args="])
        for line in (text or "").splitlines():
            parts = line.split(None, 3)
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                out.append(ProcInfo(int(parts[0]), int(parts[1]), os.path.basename(parts[2]),
                                    parts[3] if len(parts) > 3 else parts[2]))
        return out

    def pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        if IS_WINDOWS:
            import ctypes
            k32 = ctypes.windll.kernel32          # type: ignore[attr-defined]
            h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            try:
                code = ctypes.c_ulong()
                return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
            finally:
                k32.CloseHandle(h)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


class DirLockFolder:
    """The lock folder as a real directory. Works on any path, so tests use a temp folder."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def mkdir(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.mkdir()
            return True
        except FileExistsError:
            return False
        except OSError as e:
            raise HeavyError(f"cannot create the lock folder: {e.__class__.__name__}") from e

    def exists(self) -> bool:
        return self.path.is_dir()

    def read_owner(self) -> str | None:
        try:
            return (self.path / "owner.txt").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def write_owner(self, text: str) -> None:
        try:
            (self.path / "owner.txt").write_text(text, encoding="utf-8")
        except OSError as e:
            raise HeavyError(f"cannot write owner.txt: {e.__class__.__name__}") from e

    def age_seconds(self, now: float) -> float | None:
        try:
            return max(0.0, now - self.path.stat().st_mtime)
        except OSError:
            return None

    def remove(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


# ---------------------------------------------------------------- owner.txt

def format_owner(host: str, pid: int, what: str, started: float, expected_end: float | None) -> str:
    def iso(t: float) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))
    lines = [f"app={APP_MARK}", f"host={host}", f"pid={pid}", f"started={iso(started)}", f"started_epoch={int(started)}",
             f"what={what.replace(chr(10), ' ')}"]
    if expected_end:
        lines.append(f"expected_end={iso(expected_end)}")
    return "\n".join(lines) + "\n"


def parse_owner(text: str | None) -> dict:
    d: dict = {}
    for line in (text or "").splitlines():
        k, sep, v = line.partition("=")
        if sep:
            d[k.strip()] = v.strip()
    return d


# ---------------------------------------------------------------- the slot

class HeavySlot:
    def __init__(self, cfg: ServerConfig | None = None, *, probes: Probes | None = None,
                 lock: LockFolder | None = None, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep, own_markers: tuple[str, ...] = (),
                 retry_seconds: float = RETRY_SECONDS, stale_seconds: float = STALE_SECONDS):
        self.cfg = cfg or ServerConfig()
        self.probes: Probes = probes or SystemProbes()
        self.lock: LockFolder | None = lock if lock is not None else (DirLockFolder(self.cfg.lock_dir) if self.cfg.lock_dir else None)
        self.clock, self.sleep = clock, sleep
        self.own_markers = tuple(m.lower() for m in own_markers if m)
        self.retry_seconds, self.stale_seconds = retry_seconds, stale_seconds
        self._patterns = [re.compile(p, re.I) for p in self.cfg.production_patterns]
        self._mutex = threading.Lock()
        self._started = False
        self.alerts: list[dict] = []          # locks that are not ours and older than the limit (reported, never removed)
        self.current: str | None = None       # what the slot holder is doing

    # -- start-up
    def startup(self) -> None:
        """Release a lock of ours whose process is dead. Safe to call more than once."""
        self._started = True
        self._release_dead_own()

    def _owner(self) -> dict | None:
        if self.lock is None or not self.lock.exists():
            return None
        return parse_owner(self.lock.read_owner())

    def _is_ours(self, owner: dict) -> bool:
        return owner.get("app") == APP_MARK and owner.get("host") == self.probes.host()

    def _release_dead_own(self) -> bool:
        owner = self._owner()
        if owner is None or not self._is_ours(owner):
            return False
        try:
            pid = int(owner.get("pid", ""))
        except ValueError:
            return False
        if pid == self.probes.own_pid() or self.probes.pid_alive(pid):
            return False
        self.lock.remove()        # type: ignore[union-attr]
        return True

    # -- checks
    def _descendants(self, procs: list[ProcInfo]) -> set[int]:
        kids: dict[int, list[int]] = {}
        for p in procs:
            kids.setdefault(p.ppid, []).append(p.pid)
        seen, stack = set(), [self.probes.own_pid()]
        while stack:
            for c in kids.get(stack.pop(), []):
                if c not in seen:
                    seen.add(c)
                    stack.append(c)
        return seen

    def _is_ffmpeg(self, name: str) -> bool:
        return os.path.splitext(name.lower())[0] == "ffmpeg"

    def foreign_process(self) -> str | None:
        """A production process or a foreign ffmpeg: its name, or None when the machine is clear."""
        procs = self.probes.processes()
        mine = self._descendants(procs) | {self.probes.own_pid()}
        for p in procs:
            if p.pid in mine:
                continue
            if any(rx.search(p.cmdline) for rx in self._patterns):
                return p.name or "tiến trình sản xuất"
            if self._is_ffmpeg(p.name) and not any(m in p.cmdline.lower() for m in self.own_markers):
                return p.name
        return None

    def blocker(self) -> str | None:
        """A Vietnamese note when the machine is not free to start a heavy part, else None."""
        other = self.foreign_process()
        if other:
            return f"Đang chờ máy rảnh: máy đang chạy việc sản xuất khác ({other}). Sẽ thử lại sau 60 giây."
        free = self.probes.free_virtual_kb()
        floor = self.cfg.memory_floor_kb
        if floor:
            if free is None:
                return "Đang chờ máy rảnh: không đọc được bộ nhớ trống của máy. Sẽ thử lại sau 60 giây."
            if free < floor:
                return (f"Đang chờ máy rảnh: bộ nhớ trống còn {free / 1e6:.1f} GB, cần ít nhất {floor / 1e6:.1f} GB. "
                        "Sẽ thử lại sau 60 giây.")
        return None

    # -- waiting
    def _wait(self, seconds: float, cancelled: Callable[[], bool]) -> None:
        end = self.clock() + seconds
        while True:
            if cancelled():
                raise Cancelled()
            left = end - self.clock()
            if left <= 0:
                return
            self.sleep(min(1.0, left))

    def _note_foreign_lock(self, owner: dict) -> str:
        age = self.lock.age_seconds(self.clock()) if self.lock else None     # type: ignore[union-attr]
        who = (f"{owner['host']} (tiến trình {owner.get('pid', '?')}, {owner.get('what', 'không rõ việc gì')})"
               if owner.get("host") else "một chủ chưa rõ (khóa không có owner.txt)")
        mins = int((age or 0) // 60)
        if age is not None and age > self.stale_seconds:
            alert = {"host": owner.get("host"), "pid": owner.get("pid"), "what": owner.get("what"),
                     "age_minutes": mins, "at": self.clock()}
            if not any(a["host"] == alert["host"] and a["pid"] == alert["pid"] for a in self.alerts):
                self.alerts.append(alert)
            return (f"Khóa máy nặng của {who} đã giữ hơn {mins} phút. Hãy báo cho chủ máy; "
                    "ứng dụng không tự gỡ khóa của người khác. Vẫn đang chờ.")
        return f"Đang chờ máy rảnh: {who} đang giữ khóa máy nặng (khoảng {mins} phút). Sẽ thử lại sau 60 giây."

    def _take_folder(self, what: str, expected_seconds: float | None, cancelled: Callable[[], bool],
                     on_wait: Callable[[str], None]) -> None:
        assert self.lock is not None
        while True:
            if cancelled():
                raise Cancelled()
            self._release_dead_own()
            note = self.blocker()
            if note is None and self.lock.mkdir():
                now = self.clock()
                try:
                    self.lock.write_owner(format_owner(self.probes.host(), self.probes.own_pid(), what, now,
                                                       now + expected_seconds if expected_seconds else None))
                except HeavyError:
                    self.lock.remove()      # we made this folder a moment ago: it is ours to remove
                    raise
                return
            if note is None:                # mkdir lost: someone holds the lock
                note = self._note_foreign_lock(self._owner() or {})
            on_wait(note)
            self._wait(self.retry_seconds, cancelled)

    def _release_folder(self) -> None:
        """Remove the lock only when owner.txt says it is ours (this host, this process)."""
        if self.lock is None:
            return
        owner = self._owner()
        if owner and self._is_ours(owner) and owner.get("pid") == str(self.probes.own_pid()):
            self.lock.remove()

    @contextmanager
    def hold(self, what: str, cancelled: Callable[[], bool] = lambda: False,
             on_wait: Callable[[str], None] = lambda note: None,
             expected_seconds: float | None = None) -> Iterator[None]:
        """Block (cancellably) until this part may run, then hold the slot. `on_wait(note)` is called with a Vietnamese note
        every time the part has to wait. Raises Cancelled when `cancelled()` turns true while waiting."""
        if not self._started:
            self.startup()
        told = False
        while not self._mutex.acquire(timeout=0.05):
            if cancelled():
                raise Cancelled()
            if not told:
                told = True
                on_wait("Đang chờ máy rảnh: một việc nặng khác trong ứng dụng đang chạy.")
        try:
            self.current = what
            took = False
            try:
                if self.lock is not None:
                    self._take_folder(what, expected_seconds, cancelled, on_wait)
                    took = True
                yield
            finally:
                if took:
                    self._release_folder()
        finally:
            self.current = None
            self._mutex.release()
