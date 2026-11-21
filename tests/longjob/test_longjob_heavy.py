"""The heavy slot: every branch of the lock protocol with fake probes. No real lock folder, no real wait."""
import threading
import time

import pytest

from bti.longjob.config import ServerConfig
from bti.longjob.fakes import FakeClock, FakeLockFolder, FakeProbes
from bti.longjob.heavy import (APP_MARK, Cancelled, DirLockFolder, HeavyError, HeavySlot, ProcInfo, format_owner,
                               parse_owner)

CFG = ServerConfig(lock_dir="X:/fake.lock", memory_floor_kb=12_000_000,
                   production_patterns=("_chatterbox_worker", r"stages\.stage_4", r"stages\.stage_5"))


class HookClock(FakeClock):
    """A fake clock whose sleep can change the world, like time passing on a real machine."""

    def __init__(self):
        super().__init__()
        self.hooks = []

    def sleep(self, seconds):
        super().sleep(seconds)
        for h in list(self.hooks):
            h(self)


def make(probes=None, lock=None, clock=None, cfg=CFG, **kw):
    clock = clock or HookClock()
    probes = probes or FakeProbes()
    lock = lock if lock is not None else FakeLockFolder(clock)
    slot = HeavySlot(cfg, probes=probes, lock=lock, clock=clock, sleep=clock.sleep, **kw)
    return slot, probes, lock, clock


def test_owner_roundtrip():
    text = format_owner("H", 7, "voice: part 1\nsecond line", 1_000_000.0, 1_000_900.0)
    d = parse_owner(text)
    assert d["app"] == APP_MARK and d["host"] == "H" and d["pid"] == "7" and "second line" in d["what"]
    assert "expected_end" in d and "started" in d
    assert parse_owner(None) == {}


def test_free_machine_takes_and_releases_the_lock():
    slot, probes, lock, clock = make()
    seen = {}
    with slot.hold("voice: part 1", expected_seconds=900):
        seen = parse_owner(lock.read_owner())
        assert lock.exists()
    assert seen["host"] == "TESTHOST" and seen["pid"] == "4242" and seen["what"] == "voice: part 1" and "expected_end" in seen
    assert not lock.exists()
    assert clock.slept == []                       # nothing to wait for


def test_lock_released_when_the_body_raises():
    slot, _, lock, _ = make()
    with pytest.raises(RuntimeError):
        with slot.hold("x"):
            raise RuntimeError("boom")
    assert not lock.exists()
    with slot.hold("y"):                           # and the in-process mutex is free again
        pass


def test_no_lock_folder_means_in_process_only():
    slot = HeavySlot(ServerConfig(), probes=FakeProbes(free_kb=0))
    with slot.hold("x"):
        assert slot.current == "x"
    assert slot.current is None


def test_in_process_mutex_serialises_and_tells_the_waiter():
    slot = HeavySlot(ServerConfig(), probes=FakeProbes())
    notes, inside, peak, lk = [], [0], [0], threading.Lock()
    started = threading.Event()

    def first():
        with slot.hold("a"):
            started.set()
            time.sleep(0.3)

    def second():
        started.wait()
        with slot.hold("b", on_wait=notes.append):
            with lk:
                inside[0] += 1
                peak[0] = max(peak[0], inside[0])
            inside[0] -= 1

    ts = [threading.Thread(target=first), threading.Thread(target=second)]
    [t.start() for t in ts]
    [t.join(10) for t in ts]
    assert notes and "Đang chờ máy rảnh" in notes[0] and "trong ứng dụng" in notes[0]
    assert peak[0] == 1


def test_waiting_for_the_mutex_can_be_cancelled():
    slot = HeavySlot(ServerConfig(), probes=FakeProbes())
    flag = threading.Event()
    got = []

    def waiter():
        try:
            with slot.hold("b", cancelled=flag.is_set):
                got.append("ran")
        except Cancelled:
            got.append("cancelled")

    with slot.hold("a"):
        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.2)
        flag.set()
        t.join(5)
    assert got == ["cancelled"]


# ---- memory

def test_low_memory_waits_sixty_seconds_then_goes():
    slot, probes, lock, clock = make(probes=FakeProbes(free_kb=5_000_000))
    notes = []
    clock.hooks.append(lambda c: setattr(probes, "free_kb", 15_000_000) if len(c.slept) >= 120 else None)
    with slot.hold("x", on_wait=notes.append):
        assert lock.exists()
    assert notes and "bộ nhớ trống" in notes[0] and "5.0 GB" in notes[0] and "12.0 GB" in notes[0]
    assert sum(clock.slept) >= 120                 # two retries of 60 s, none of it real time
    assert lock.mkdir_calls == 1                   # the folder is not even tried while memory is short


def test_unknown_memory_is_not_free():
    slot, probes, lock, clock = make(probes=FakeProbes(free_kb=None))
    notes = []
    clock.hooks.append(lambda c: setattr(probes, "free_kb", 20_000_000))
    with slot.hold("x", on_wait=notes.append):
        pass
    assert "không đọc được" in notes[0]


# ---- production processes and ffmpeg

@pytest.mark.parametrize("cmd", ["python _chatterbox_worker.py job.json", r"python -m stages.stage_4.run",
                                 r"python -m stages.stage_5.render"])
def test_production_process_blocks(cmd):
    probes = FakeProbes(procs=[ProcInfo(900, 1, "python.exe", cmd)])
    slot, _, lock, clock = make(probes=probes)
    notes = []
    clock.hooks.append(lambda c: probes.procs.clear())
    with slot.hold("x", on_wait=notes.append):
        pass
    assert notes and "việc sản xuất khác" in notes[0] and "python.exe" in notes[0]
    assert sum(clock.slept) >= 60


def test_foreign_ffmpeg_blocks_but_ours_does_not():
    probes = FakeProbes(procs=[
        ProcInfo(900, 1, "ffmpeg.exe", "ffmpeg -i other.mp4 out.mp4"),                       # foreign
        ProcInfo(901, 4242, "ffmpeg.exe", "ffmpeg -i a b"),                                  # child of ours
        ProcInfo(902, 55, "ffmpeg.exe", r"ffmpeg -i D:\code\behind-the-image\projects\p\x"),  # our path
        ProcInfo(903, 901, "ffmpeg.exe", "ffmpeg grandchild")])                              # grandchild of ours
    slot, _, lock, clock = make(probes=probes, own_markers=(r"D:\code\behind-the-image",))
    notes = []
    clock.hooks.append(lambda c: probes.procs.__delitem__(0) if probes.procs and probes.procs[0].pid == 900 else None)
    with slot.hold("x", on_wait=notes.append):
        pass
    assert len(notes) == 1 and "ffmpeg.exe" in notes[0]


def test_ffmpeg_that_is_ours_alone_does_not_block():
    probes = FakeProbes(procs=[ProcInfo(901, 4242, "ffmpeg", "ffmpeg -i a b"),
                               ProcInfo(950, 1, "Python.EXE", "python app.py")])
    slot, _, lock, clock = make(probes=probes)
    with slot.hold("x"):
        pass
    assert clock.slept == []


# ---- the lock folder

def test_foreign_lock_waits_and_is_never_removed():
    slot, probes, lock, clock = make()
    lock.hold_for("OTHERHOST", 77, "bench tts")
    notes = []
    clock.hooks.append(lambda c: lock.remove() if len(c.slept) >= 180 else None)       # the other agent finishes
    with slot.hold("x", on_wait=notes.append):
        assert parse_owner(lock.read_owner())["pid"] == "4242"
    assert notes and "OTHERHOST" in notes[0] and "bench tts" in notes[0]
    assert lock.removed == 2                       # one by "the other agent", one by our release; none by the waiting loop
    assert slot.alerts == []


def test_waiting_loop_never_removes_a_foreign_lock():
    slot, _, lock, clock = make()
    lock.hold_for("OTHERHOST", 77)
    removed_by_us = []
    flag = {"n": 0}

    def cancelled():
        return len(clock.slept) >= 300

    with pytest.raises(Cancelled):
        with slot.hold("x", cancelled=cancelled):
            pass
    assert lock.exists() and lock.removed == 0 and "OTHERHOST" in lock.read_owner()


def test_old_foreign_lock_is_reported_not_removed():
    slot, _, lock, clock = make()
    lock.hold_for("OTHERHOST", 77, "bench render")
    clock.advance(61 * 60)
    notes = []
    with pytest.raises(Cancelled):
        with slot.hold("x", cancelled=lambda: len(clock.slept) >= 130, on_wait=notes.append):
            pass
    assert lock.exists() and lock.removed == 0
    assert len(slot.alerts) == 1 and slot.alerts[0]["host"] == "OTHERHOST" and slot.alerts[0]["age_minutes"] >= 61
    assert "báo cho chủ máy" in notes[0] and "không tự gỡ" in notes[0]


def test_young_foreign_lock_raises_no_alert():
    slot, _, lock, clock = make()
    lock.hold_for("OTHERHOST", 77)
    clock.advance(59 * 60)
    with pytest.raises(Cancelled):
        with slot.hold("x", cancelled=lambda: len(clock.slept) >= 60):
            pass
    assert slot.alerts == []


def test_lock_without_owner_file_is_foreign():
    slot, _, lock, clock = make()
    lock.present, lock.owner = True, None
    notes = []
    with pytest.raises(Cancelled):
        with slot.hold("x", cancelled=lambda: len(clock.slept) >= 60, on_wait=notes.append):
            pass
    assert lock.exists() and lock.removed == 0 and "chưa rõ" in notes[0]


def test_same_pid_other_host_is_foreign():
    slot, _, lock, clock = make()
    lock.hold_for("OTHERHOST", 4242, app=APP_MARK)
    with pytest.raises(Cancelled):
        with slot.hold("x", cancelled=lambda: len(clock.slept) >= 60):
            pass
    assert lock.exists() and lock.removed == 0


def test_our_dead_lock_is_released_at_startup():
    slot, probes, lock, clock = make()
    lock.hold_for("TESTHOST", 999, app=APP_MARK)          # ours (host + marker), pid 999 is dead
    slot.startup()
    assert not lock.exists() and lock.removed == 1


def test_our_live_lock_is_kept_at_startup():
    probes = FakeProbes(alive={999})
    slot, _, lock, _ = make(probes=probes)
    lock.hold_for("TESTHOST", 999, app=APP_MARK)
    slot.startup()
    assert lock.exists()


def test_startup_never_touches_a_foreign_lock_even_with_a_dead_pid():
    slot, _, lock, _ = make()
    lock.hold_for("OTHERHOST", 999, app=APP_MARK)         # other host
    slot.startup()
    lock.hold_for("TESTHOST", 998, app="bench")           # other marker (not ours)
    slot.startup()
    assert lock.exists() and lock.removed == 0


def test_dead_own_lock_found_while_waiting_is_released():
    slot, _, lock, clock = make()
    slot.startup()
    lock.hold_for("TESTHOST", 999, app=APP_MARK)          # a crashed second instance of the app
    with slot.hold("x"):
        assert parse_owner(lock.read_owner())["pid"] == "4242"
    assert clock.slept == []


def test_release_leaves_a_lock_that_is_no_longer_ours():
    slot, _, lock, _ = make()
    with slot.hold("x"):
        lock.hold_for("OTHERHOST", 5)                     # somebody replaced owner.txt behind our back
    assert lock.exists() and "OTHERHOST" in lock.read_owner()


def test_cancel_while_waiting_leaves_everything_alone():
    slot, _, lock, clock = make()
    lock.hold_for("OTHERHOST", 77)
    with pytest.raises(Cancelled):
        with slot.hold("x", cancelled=lambda: len(clock.slept) >= 5):
            pass
    assert lock.exists() and "OTHERHOST" in lock.read_owner()
    assert slot._mutex.acquire(timeout=1)                 # the in-process mutex was released too
    slot._mutex.release()


def test_retry_cadence_is_sixty_seconds():
    slot, _, lock, clock = make()
    lock.hold_for("OTHERHOST", 77)
    clock.hooks.append(lambda c: lock.remove() if sum(c.slept) >= 600 else None)
    with slot.hold("x"):
        pass
    attempts = lock.mkdir_calls
    assert attempts == 11                                  # t = 0, 60, ..., 600
    assert all(s <= 1.0 for s in clock.slept)              # waits are cut in one-second slices so cancel stays quick


def test_owner_write_failure_removes_the_folder_we_just_made():
    class Bad(FakeLockFolder):
        def write_owner(self, text):
            raise HeavyError("disk full")

    clock = HookClock()
    slot, _, lock, _ = make(lock=Bad(clock), clock=clock)
    with pytest.raises(HeavyError):
        with slot.hold("x"):
            pass
    assert not lock.exists()
    assert slot._mutex.acquire(timeout=1)                  # the mutex is free again
    slot._mutex.release()


# ---- the real folder implementation, on a temp folder

def test_dir_lock_folder_is_atomic(tmp_path):
    f = DirLockFolder(tmp_path / "sub" / "_heavy.lock")
    assert not f.exists() and f.read_owner() is None and f.age_seconds(time.time()) is None
    assert f.mkdir() is True
    assert f.mkdir() is False
    f.write_owner("app=x\n")
    assert f.read_owner() == "app=x\n" and f.age_seconds(time.time() + 5) >= 5
    f.remove()
    assert not f.exists()


def test_slot_with_a_real_temp_lock_folder(tmp_path):
    cfg = ServerConfig(lock_dir=str(tmp_path / "_heavy.lock"), memory_floor_kb=1)
    slot = HeavySlot(cfg, probes=FakeProbes(), sleep=lambda s: None)
    with slot.hold("real folder"):
        d = parse_owner((tmp_path / "_heavy.lock" / "owner.txt").read_text(encoding="utf-8"))
        assert d["what"] == "real folder" and d["app"] == APP_MARK
    assert not (tmp_path / "_heavy.lock").exists()
