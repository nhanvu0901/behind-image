"""bti.fsio.atomic_replace: retries on Windows sharing errors, a plain replace elsewhere. No real file lock is needed:
the replace and the sleep are faked."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bti import fsio  # noqa: E402


class Flaky:
    def __init__(self, fails, exc):
        self.fails, self.exc, self.calls = fails, exc, 0

    def __call__(self, src, dst):
        self.calls += 1
        if self.calls <= self.fails:
            raise self.exc


@pytest.fixture()
def pauses(monkeypatch):
    got = []
    monkeypatch.setattr(fsio, "_sleep", got.append)
    return got


def win32():
    return OSError(13, "sharing violation", None, 32)


def test_windows_retries_a_permission_error_until_it_works(monkeypatch, pauses):
    monkeypatch.setattr(fsio, "IS_WINDOWS", True)
    f = Flaky(3, PermissionError(13, "denied", None, 5))
    monkeypatch.setattr(fsio, "_replace", f)
    fsio.atomic_replace("a", "b")
    assert f.calls == 4 and len(pauses) == 3
    assert pauses == sorted(pauses)                      # the pause grows


def test_windows_retries_sharing_violation_that_is_not_a_permission_error(monkeypatch, pauses):
    monkeypatch.setattr(fsio, "IS_WINDOWS", True)
    f = Flaky(1, OSError(0, "x", None, 32))
    monkeypatch.setattr(fsio, "_replace", f)
    fsio.atomic_replace("a", "b")
    assert f.calls == 2


def test_windows_raises_the_last_error_after_about_three_seconds(monkeypatch, pauses):
    monkeypatch.setattr(fsio, "IS_WINDOWS", True)
    errs = [PermissionError(13, "denied %d" % i, None, 5) for i in range(50)]
    calls = []

    def always(src, dst):
        e = errs[len(calls)]
        calls.append(e)
        raise e
    monkeypatch.setattr(fsio, "_replace", always)
    with pytest.raises(PermissionError) as ei:
        fsio.atomic_replace("a", "b")
    assert ei.value is calls[-1] and len(calls) == len(fsio.PAUSES) + 1
    assert 2.5 <= sum(pauses) <= 3.5


def test_windows_does_not_retry_other_errors(monkeypatch, pauses):
    monkeypatch.setattr(fsio, "IS_WINDOWS", True)
    f = Flaky(5, FileNotFoundError(2, "gone", None, 2))
    monkeypatch.setattr(fsio, "_replace", f)
    with pytest.raises(FileNotFoundError):
        fsio.atomic_replace("a", "b")
    assert f.calls == 1 and pauses == []


def test_elsewhere_is_a_plain_replace_without_retry(monkeypatch, pauses):
    monkeypatch.setattr(fsio, "IS_WINDOWS", False)
    f = Flaky(1, PermissionError(13, "denied"))
    monkeypatch.setattr(fsio, "_replace", f)
    with pytest.raises(PermissionError):
        fsio.atomic_replace("a", "b")
    assert f.calls == 1 and pauses == []


def test_really_replaces_a_file(tmp_path):
    (tmp_path / "a.part").write_text("new")
    (tmp_path / "a").write_text("old")
    fsio.atomic_replace(tmp_path / "a.part", tmp_path / "a")
    assert (tmp_path / "a").read_text() == "new" and not (tmp_path / "a.part").exists()


def test_no_bare_rename_is_left_in_bti():
    """Every rename that finishes a write goes through atomic_replace (the only os.replace is the helper's own)."""
    import re
    root = Path(__file__).resolve().parents[2] / "bti"
    bad = []
    for p in root.rglob("*.py"):
        if p.name == "fsio.py":
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
            code = line.split("#")[0]
            if re.search(r"\bos\.(replace|rename)\(|\b(tmp|silent)\.replace\(|shutil\.move\(", code):
                bad.append("%s:%d" % (p.relative_to(root), n))
    assert bad == []
