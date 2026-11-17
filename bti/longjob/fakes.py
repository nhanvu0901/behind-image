"""Twins of the heavy slot's probes, for tests of any stage on any machine: no PowerShell, no real lock folder, no real wait."""
from __future__ import annotations

from .heavy import ProcInfo


class FakeClock:
    """A clock that only moves when told to; `sleep` moves it, so a 60-second retry costs no real time."""

    def __init__(self, start: float = 1_000_000.0):
        self.t = start
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


class FakeProbes:
    def __init__(self, host: str = "TESTHOST", pid: int = 4242, free_kb: int | None = 20_000_000,
                 procs: list[ProcInfo] | None = None, alive: set[int] | None = None):
        self._host, self._pid = host, pid
        self.free_kb = free_kb
        self.procs: list[ProcInfo] = list(procs or [])
        self.alive: set[int] = set(alive or set()) | {pid}
        self.probe_calls = 0

    def host(self) -> str:
        return self._host

    def own_pid(self) -> int:
        return self._pid

    def free_virtual_kb(self) -> int | None:
        self.probe_calls += 1
        return self.free_kb

    def processes(self) -> list[ProcInfo]:
        return list(self.procs)

    def pid_alive(self, pid: int) -> bool:
        return pid in self.alive


class FakeLockFolder:
    """The lock folder in memory. `created_at` is in the injected clock's time, so age follows the fake clock."""

    def __init__(self, clock=None):
        self._clock = clock
        self.present = False
        self.owner: str | None = None
        self.created_at = 0.0
        self.mkdir_calls = 0
        self.removed = 0

    def _now(self) -> float:
        return self._clock() if self._clock else 0.0

    def mkdir(self) -> bool:
        self.mkdir_calls += 1
        if self.present:
            return False
        self.present, self.owner, self.created_at = True, None, self._now()
        return True

    def exists(self) -> bool:
        return self.present

    def read_owner(self) -> str | None:
        return self.owner if self.present else None

    def write_owner(self, text: str) -> None:
        self.owner = text

    def age_seconds(self, now: float) -> float | None:
        return max(0.0, now - self.created_at) if self.present else None

    def remove(self) -> None:
        if self.present:
            self.removed += 1
        self.present, self.owner = False, None

    def hold_for(self, host: str, pid: int, what: str = "foreign job", app: str = "bench") -> None:
        """Pretend another agent holds the lock."""
        self.present, self.created_at = True, self._now()
        self.owner = f"app={app}\nhost={host}\npid={pid}\nwhat={what}\n"
