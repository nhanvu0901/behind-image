"""The long-job manager: parts, progress, cancel with a child process, overrun, resume, restart, busy, heavy overlap."""
import json
import sys
import threading
import time

import pytest

from bti.longjob import Busy, LongJobManager, Part, PartError
from bti.longjob.config import ServerConfig
from bti.longjob.fakes import FakeClock, FakeLockFolder, FakeProbes
from bti.longjob.heavy import HeavySlot
from bti.longjob.manager import RESTART_MESSAGE, ProjectGone
from bti.proc import IS_WINDOWS


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "projects"
    (r / "p1").mkdir(parents=True)
    (r / "p2").mkdir()
    return r


@pytest.fixture
def mgr(root):
    return LongJobManager(HeavySlot(ServerConfig(), probes=FakeProbes()), projects_root=root, cancel_grace=2.0)


def alive(pid: int) -> bool:
    from bti.longjob.heavy import SystemProbes
    return SystemProbes().pid_alive(pid)


def until(pred, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(0.01)
    raise AssertionError("timed out waiting for a condition")


def sleeper_cmd(seconds=60):
    return [sys.executable, "-c", f"import os,time;print(os.getpid(),flush=True);time.sleep({seconds})"]


def test_parts_run_in_order_and_results_merge(mgr, root):
    order = []

    def mk(n):
        def run(ctx):
            order.append(n)
            ctx.progress(0.5, f"half {n}")
            ctx.log(f"line {n}")
            return {f"r{n}": n, "last": n}
        return run

    job = mgr.start("voice", "p1", root / "p1", [Part(f"s{n}", f"Phần {n}", mk(n)) for n in (1, 2, 3)], meta={"a": 1})
    rec = mgr.wait(job)
    assert order == [1, 2, 3]
    assert rec["state"] == "done" and rec["progress"] == 1.0 and rec["error"] is None
    assert rec["result"] == {"r1": 1, "r2": 2, "r3": 3, "last": 3}
    assert [p["state"] for p in rec["parts"]] == ["done"] * 3 and all(p["progress"] == 1.0 for p in rec["parts"])
    assert all(p["started"] and p["ended"] for p in rec["parts"])
    assert rec["meta"] == {"a": 1} and rec["log_tail"] == ["line 1", "line 2", "line 3"]
    assert (root / "p1" / "cache" / "longjobs" / f"{rec['id']}.json").is_file()
    assert mgr.active("p1") is None


def test_progress_is_visible_while_running_and_weighted(mgr, root):
    go, in_second = threading.Event(), threading.Event()

    def second(ctx):
        ctx.progress(0.5, "đang đọc")
        in_second.set()
        go.wait(10)

    job = mgr.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: None, est_seconds=100),
                                                  Part("b", "B", second, est_seconds=300)])
    in_second.wait(10)
    until(lambda: mgr.get(job)["parts"][1]["note"] == "đang đọc")
    rec = mgr.get(job)
    assert rec["state"] == "running" and rec["parts"][0]["state"] == "done" and rec["parts"][1]["state"] == "running"
    assert rec["progress"] == pytest.approx((100 + 150) / 400, abs=0.01)
    assert mgr.active("p1", "voice")["id"] == job["id"] and mgr.active("p1", "export") is None
    go.set()
    assert mgr.wait(job)["state"] == "done"


def test_progress_outside_a_running_part_is_ignored_and_clamped(mgr, root):
    def run(ctx):
        ctx.progress(5, "x")
        ctx.progress("bad")
    rec = mgr.wait(mgr.start("k", "p1", root / "p1", [Part("a", "A", run)]))
    assert rec["state"] == "done"


def test_same_kind_refused_other_kind_and_other_project_allowed(mgr, root):
    go = threading.Event()
    j1 = mgr.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: go.wait(10))])
    with pytest.raises(Busy) as e:
        mgr.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: None)])
    assert e.value.job["id"] == j1["id"] and e.value.job_id == j1["id"]
    j2 = mgr.start("export", "p1", root / "p1", [Part("a", "A", lambda c: None)])
    j3 = mgr.start("voice", "p2", root / "p2", [Part("a", "A", lambda c: None)])
    assert mgr.wait(j2)["state"] == "done" and mgr.wait(j3)["state"] == "done"
    go.set()
    assert mgr.wait(j1)["state"] == "done"
    mgr.wait(mgr.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: None)]))      # free again


def test_two_simultaneous_starts_only_one_wins(mgr, root):
    go = threading.Event()
    wins, busy = [], []

    def go_start():
        try:
            wins.append(mgr.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: go.wait(10))]))
        except Busy:
            busy.append(1)

    ts = [threading.Thread(target=go_start) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(wins) == 1 and len(busy) == 7
    go.set()
    mgr.wait(wins[0])


def test_bad_arguments(mgr, root):
    ok = [Part("a", "A", lambda c: None)]
    with pytest.raises(ValueError):
        mgr.start("Bad Kind", "p1", root / "p1", ok)
    with pytest.raises(ValueError):
        mgr.start("k", "../x", root / "p1", ok)
    with pytest.raises(ValueError):
        mgr.start("k", "p1", root / "p1", [])
    with pytest.raises(ValueError):
        mgr.start("k", "p1", root / "p1", ok + ok)
    with pytest.raises(ProjectGone):
        mgr.start("k", "p1", root / "nope", ok)


def test_cancel_kills_the_child_process_tree(mgr, root):
    pids, got = [], threading.Event()

    def run(ctx):
        rc = ctx.run_process(sleeper_cmd(), on_line=lambda l: (pids.append(int(l)), got.set()))
        return {"rc": rc}

    job = mgr.start("voice", "p1", root / "p1", [Part("a", "A", run), Part("b", "B", lambda c: pids.append("ran b"))])
    assert got.wait(15)
    child = pids[0]
    assert alive(child)
    assert mgr.cancel(job) is True
    rec = mgr.wait(job, 20)
    assert rec["state"] == "cancelled" and rec["parts"][0]["state"] == "cancelled" and rec["parts"][1]["state"] == "cancelled"
    until(lambda: not alive(child), 10)
    assert "ran b" not in pids
    assert mgr.cancel(job) is False                       # already over


def test_cancel_kills_a_grandchild_too(mgr, root):
    if IS_WINDOWS:
        pytest.skip("the grandchild check uses a POSIX shell")
    pids, got = [], threading.Event()
    code = ("import subprocess,sys,os;"
            "p=subprocess.Popen([sys.executable,'-c','import os,time;print(os.getpid(),flush=True);time.sleep(60)']);"
            "print(os.getpid(),flush=True);p.wait()")

    def run(ctx):
        ctx.run_process([sys.executable, "-c", code], on_line=lambda l: (pids.append(int(l)), len(pids) >= 1 and got.set()))

    job = mgr.start("voice", "p1", root / "p1", [Part("a", "A", run)])
    until(lambda: len(pids) >= 2, 15)
    assert mgr.cancel(job)
    mgr.wait(job, 20)
    for pid in pids:
        until(lambda pid=pid: not alive(pid), 10)


def test_run_process_returns_code_and_feeds_lines(mgr, root):
    lines = []

    def run(ctx):
        rc = ctx.run_process([sys.executable, "-c", "import sys;print('a');print('b',file=sys.stderr);sys.exit(3)"],
                             on_line=lines.append)
        return {"rc": rc}

    rec = mgr.wait(mgr.start("k", "p1", root / "p1", [Part("a", "A", run)]))
    assert rec["result"] == {"rc": 3} and sorted(lines) == ["a", "b"] and sorted(rec["log_tail"]) == ["a", "b"]
    log = (root / "p1" / "cache" / "longjobs" / f"{rec['id']}.log").read_text(encoding="utf-8")
    assert "a" in log


def test_a_broken_line_callback_does_not_kill_the_child(mgr, root):
    def boom(line):
        raise RuntimeError("x")

    rec = mgr.wait(mgr.start("k", "p1", root / "p1", [Part("a", "A", lambda c: {"rc": c.run_process(
        [sys.executable, "-c", "print('x');print('y')"], on_line=boom)})]))
    assert rec["result"] == {"rc": 0}


def test_part_overrun_is_stopped_and_the_child_is_gone(root):
    clock = FakeClock()
    m = LongJobManager(HeavySlot(ServerConfig(), probes=FakeProbes()), projects_root=root, clock=clock, cancel_grace=3.0)
    pids, got = [], threading.Event()

    def run(ctx):
        ctx.run_process(sleeper_cmd(), on_line=lambda l: (pids.append(int(l)), got.set()))

    job = m.start("voice", "p1", root / "p1", [Part("a", "Đọc phần 1/4", run), Part("b", "B", lambda c: pids.append("b"))])
    assert got.wait(15)
    clock.advance(35 * 60 + 1)                            # no real wait
    rec = m.wait(job, 20)
    assert rec["state"] == "error" and rec["error_code"] == "part_timeout" and "35" in rec["error"]
    assert rec["parts"][0]["state"] == "error" and rec["parts"][0]["error"] and rec["parts"][1]["state"] == "cancelled"
    until(lambda: not alive(pids[0]), 10)
    assert "b" not in pids


def test_part_within_the_limit_is_not_stopped(root):
    clock = FakeClock()
    m = LongJobManager(HeavySlot(ServerConfig(), probes=FakeProbes()), projects_root=root, clock=clock)
    go = threading.Event()
    job = m.start("k", "p1", root / "p1", [Part("a", "A", lambda c: go.wait(10))])
    clock.advance(34 * 60)
    time.sleep(0.2)
    go.set()
    assert m.wait(job)["state"] == "done"


def test_a_part_that_ignores_cancel_is_abandoned(root):
    m = LongJobManager(HeavySlot(ServerConfig(), probes=FakeProbes()), projects_root=root, cancel_grace=0.2)
    release = threading.Event()
    job = m.start("k", "p1", root / "p1", [Part("a", "A", lambda c: release.wait(30))])
    until(lambda: m.get(job)["parts"][0]["state"] == "running")
    m.cancel(job)
    assert m.wait(job, 10)["state"] == "cancelled"
    release.set()


def test_exception_and_parterror_codes(mgr, root):
    def boom(ctx):
        raise KeyError("zz")

    rec = mgr.wait(mgr.start("k", "p1", root / "p1", [Part("a", "Bước A", boom), Part("b", "B", lambda c: None)]))
    assert rec["state"] == "error" and rec["error_code"] == "part_failed" and "KeyError" in rec["error"]
    assert rec["parts"][0]["state"] == "error" and rec["parts"][1]["state"] == "cancelled"

    def own(ctx):
        raise PartError("voice_worker_failed", "Giọng đọc lỗi ở câu 3.")

    rec = mgr.wait(mgr.start("k", "p1", root / "p1", [Part("a", "A", own)]))
    assert rec["error_code"] == "voice_worker_failed" and rec["error"] == "Giọng đọc lỗi ở câu 3."


def test_resume_skips_parts_that_are_already_done(mgr, root):
    made = {"s1": False}
    runs = []

    def s1(ctx):
        runs.append("s1")
        made["s1"] = True

    def s2(ctx):
        runs.append("s2")
        if len(runs) == 2:
            raise PartError("x_failed", "lỗi")
        return {"ok": True}

    def parts():
        return [Part("s1", "Phần 1", s1, is_done=lambda c: made["s1"]), Part("s2", "Phần 2", s2)]

    r1 = mgr.wait(mgr.start("voice", "p1", root / "p1", parts()))
    assert r1["state"] == "error" and runs == ["s1", "s2"]
    r2 = mgr.wait(mgr.start("voice", "p1", root / "p1", parts()))
    assert r2["state"] == "done" and runs == ["s1", "s2", "s2"]          # s1 not run again
    assert r2["parts"][0]["state"] == "done" and "Đã có sẵn" in r2["parts"][0]["note"]


def test_failing_is_done_check_means_do_the_work(mgr, root):
    def bad(ctx):
        raise RuntimeError("x")

    ran = []
    rec = mgr.wait(mgr.start("k", "p1", root / "p1", [Part("a", "A", lambda c: ran.append(1), is_done=bad)]))
    assert rec["state"] == "done" and ran == [1]


def test_workdir_is_stable_per_kind_and_inside_the_project(mgr, root):
    seen = []
    mgr.wait(mgr.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: seen.append(c.workdir))]))
    mgr.wait(mgr.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: seen.append(c.workdir))]))
    assert seen[0] == seen[1] == root / "p1" / "cache" / "longjobs" / "work" / "voice" and seen[0].is_dir()


def test_restart_reports_interrupted(root):
    d = root / "p1" / "cache" / "longjobs"
    d.mkdir(parents=True)
    rec = {"id": "0123456789abcdef", "kind": "voice", "pid": "p1", "state": "running", "progress": 0.4, "created": 1.0,
           "parts": [{"key": "a", "title": "A", "state": "done"}, {"key": "b", "title": "B", "state": "running"},
                     {"key": "c", "title": "C", "state": "queued"}], "error": None, "error_code": None, "result": {}}
    (d / "0123456789abcdef.json").write_text(json.dumps(rec), encoding="utf-8")
    m = LongJobManager(HeavySlot(ServerConfig(), probes=FakeProbes()), projects_root=root)       # a new process
    got = m.get("0123456789abcdef")
    assert got["state"] == "interrupted" and got["error_code"] == "interrupted" and got["error"] == RESTART_MESSAGE
    assert [p["state"] for p in got["parts"]] == ["done", "interrupted", "interrupted"]
    assert json.loads((d / "0123456789abcdef.json").read_text(encoding="utf-8"))["state"] == "interrupted"     # persisted
    assert m.active("p1") is None
    m.wait(m.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: None)]))       # resume is allowed
    assert m.get("0123456789abcdef")["state"] == "interrupted"


def test_unknown_and_malformed_ids(mgr):
    assert mgr.get("0123456789abcdef") is None and mgr.get("../x") is None and mgr.cancel("nope") is False


def test_for_project_lists_memory_and_disk_newest_first_and_filters(mgr, root):
    a = mgr.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: None)])
    mgr.wait(a)
    time.sleep(0.01)
    b = mgr.start("export", "p1", root / "p1", [Part("a", "A", lambda c: None)])
    mgr.wait(b)
    rows = mgr.for_project("p1")
    assert [r["id"] for r in rows] == [b["id"], a["id"]]
    assert [r["id"] for r in mgr.for_project("p1", kind="voice")] == [a["id"]]
    other = LongJobManager(projects_root=root)
    assert {r["id"] for r in other.for_project("p1")} == {a["id"], b["id"]}
    assert mgr.for_project("p2") == []


def test_old_records_are_pruned(mgr, root, monkeypatch):
    monkeypatch.setattr(sys.modules["bti.longjob.manager"], "KEEP_PER_PROJECT", 3)   # the package attribute `manager` is the instance
    for _ in range(6):
        mgr.wait(mgr.start("k", "p1", root / "p1", [Part("a", "A", lambda c: None)]))
        time.sleep(0.02)
    mgr.start("k", "p1", root / "p1", [Part("a", "A", lambda c: None)])
    time.sleep(0.2)
    assert len(list((root / "p1" / "cache" / "longjobs").glob("*.json"))) <= 4


def test_deleted_project_is_never_recreated(mgr, root):
    import shutil
    go = threading.Event()
    job = mgr.start("k", "p1", root / "p1", [Part("a", "A", lambda c: go.wait(10)), Part("b", "B", lambda c: None)])
    until(lambda: mgr.get(job)["parts"][0]["state"] == "running")
    shutil.rmtree(root / "p1")
    go.set()
    rec = mgr.wait(job)
    assert rec["state"] == "error" and rec["error_code"] == "project_gone"
    assert not (root / "p1").exists()


# ---- the heavy slot inside the manager

def test_two_heavy_parts_of_two_projects_never_overlap(mgr, root):
    inside, peak, lk = [0], [0], threading.Lock()

    def heavy(ctx):
        with lk:
            inside[0] += 1
            peak[0] = max(peak[0], inside[0])
        time.sleep(0.15)
        with lk:
            inside[0] -= 1

    light_overlap = []
    jobs = [mgr.start("voice", pid, root / pid, [Part("a", "A", heavy, heavy=True), Part("b", "B", heavy, heavy=True)])
            for pid in ("p1", "p2")]
    recs = [mgr.wait(j, 20) for j in jobs]
    assert [r["state"] for r in recs] == ["done", "done"]
    assert peak[0] == 1


def test_light_parts_do_not_take_the_slot(mgr, root):
    go = threading.Event()
    h = mgr.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: go.wait(10), heavy=True)])
    until(lambda: mgr.get(h)["parts"][0]["state"] == "running")
    l = mgr.start("export", "p2", root / "p2", [Part("a", "A", lambda c: None)])
    assert mgr.wait(l, 5)["state"] == "done"
    go.set()
    mgr.wait(h)


class _World(FakeClock):
    """A fake clock whose sleep can change the world (the other agent's lock goes away after a while)."""

    def __init__(self, lock):
        super().__init__()
        self.lock = lock

    def sleep(self, seconds):
        super().sleep(seconds)
        time.sleep(0.002)                      # let the job thread and the test thread look at the waiting state
        if len(self.slept) >= 150 and self.lock.exists() and "OTHER" in (self.lock.read_owner() or ""):
            self.lock.remove()


def _server_mgr(root, procs=None):
    from bti.longjob.config import ServerConfig as C
    cfg = C(lock_dir="X:/fake", memory_floor_kb=1000)
    lock = FakeLockFolder()
    clock = _World(lock)
    lock._clock = clock
    slot = HeavySlot(cfg, probes=FakeProbes(), lock=lock, clock=clock, sleep=clock.sleep)
    return LongJobManager(slot, projects_root=root), lock, clock


def test_heavy_part_shows_waiting_with_a_note_then_runs(root):
    m, lock, clock = _server_mgr(root)
    lock.hold_for("OTHERHOST", 77, "bench tts")
    ran = []
    job = m.start("voice", "p1", root / "p1", [Part("a", "Đọc phần 1/4", lambda c: ran.append(1), heavy=True, est_seconds=900)])
    seen = {}

    def waiting():
        r = m.get(job)
        if r["state"] == "waiting":
            seen.update(r)
        return r["state"] in ("done", "error")

    until(waiting, 20)
    rec = m.wait(job, 20)
    assert rec["state"] == "done" and ran == [1] and not lock.exists()
    assert seen and seen["parts"][0]["state"] == "waiting" and "Đang chờ máy rảnh" in seen["parts"][0]["note"]
    assert any("OTHERHOST" in l for l in rec["log_tail"])


def test_cancel_while_waiting_for_the_machine(root):
    m, lock, clock = _server_mgr(root)
    lock.hold_for("FOREIGN", 77)               # the fake world only removes locks of OTHERHOST
    ran = []
    job = m.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: ran.append(1), heavy=True)])
    until(lambda: m.get(job)["state"] == "waiting", 20)
    m.cancel(job)
    rec = m.wait(job, 20)
    assert rec["state"] == "cancelled" and ran == [] and rec["parts"][0]["state"] == "cancelled"
    assert lock.exists() and "FOREIGN" in lock.read_owner()


def test_is_done_skips_the_heavy_slot_entirely(root):
    m, lock, clock = _server_mgr(root)
    lock.hold_for("OTHERHOST", 77)               # would block forever, but the part is already done
    job = m.start("voice", "p1", root / "p1", [Part("a", "A", lambda c: 1 / 0, heavy=True, is_done=lambda c: True)])
    rec = m.wait(job, 10)
    assert rec["state"] == "done" and lock.mkdir_calls == 0


def test_the_slot_is_released_after_each_heavy_part(root):
    m, lock, clock = _server_mgr(root)
    held = []
    parts = [Part(f"s{i}", f"S{i}", lambda c: held.append(lock.exists()), heavy=True) for i in range(3)]
    rec = m.wait(m.start("voice", "p1", root / "p1", parts), 10)
    assert rec["state"] == "done" and held == [True, True, True] and not lock.exists() and lock.mkdir_calls == 3


def test_the_slot_is_released_when_a_heavy_part_fails(root):
    m, lock, clock = _server_mgr(root)

    def boom(c):
        raise RuntimeError("x")

    rec = m.wait(m.start("voice", "p1", root / "p1", [Part("a", "A", boom, heavy=True)]), 10)
    assert rec["state"] == "error" and not lock.exists()


def test_routes(mgr, root):
    pytest.importorskip("httpx")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from bti.longjob.api import make_router

    app = FastAPI()
    app.include_router(make_router(mgr))
    c = TestClient(app)
    go = threading.Event()
    job = mgr.start("voice", "p1", root / "p1", [Part("a", "A", lambda ctx: go.wait(10))])
    r = c.get(f"/api/longjobs/{job['id']}")
    assert r.status_code == 200 and r.json()["kind"] == "voice"
    assert c.get("/api/longjobs/0123456789abcdef").json()["code"] == "longjob_not_found"
    assert c.get("/api/longjobs/..%2Fx").status_code == 404
    lst = c.get("/api/projects/p1/longjobs", params={"kind": "voice"}).json()["items"]
    assert [x["id"] for x in lst] == [job["id"]]
    assert c.get("/api/projects/p1/longjobs", params={"kind": "export"}).json()["items"] == []
    assert c.get("/api/projects/nope/longjobs").json()["code"] == "project_not_found"
    assert c.get("/api/projects/p1/longjobs", params={"kind": "BAD KIND"}).status_code == 422
    r = c.post(f"/api/longjobs/{job['id']}/cancel")
    assert r.status_code == 200
    mgr.wait(job, 20)
    assert c.get(f"/api/longjobs/{job['id']}").json()["state"] == "cancelled"
    assert c.post("/api/longjobs/0123456789abcdef/cancel").status_code == 404
