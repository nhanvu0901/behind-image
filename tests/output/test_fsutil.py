"""The file helpers: every write is whole or not at all."""
import os

import pytest

from bti.output import fsutil


def test_write_is_atomic_and_skips_identical_content(tmp_path):
    p = tmp_path / "a" / "x.txt"
    assert fsutil.write_text(p, "tiếng Việt\n") is True
    assert p.read_bytes() == "tiếng Việt\n".encode("utf-8") and b"\r" not in p.read_bytes()
    m = p.stat().st_mtime_ns
    assert fsutil.write_text(p, "tiếng Việt\n") is False and p.stat().st_mtime_ns == m
    assert not list(tmp_path.rglob("*.part"))


def test_a_failing_write_leaves_the_old_file_and_no_part_file(tmp_path, monkeypatch):
    p = tmp_path / "x.txt"
    fsutil.write_text(p, "old")
    monkeypatch.setattr(fsutil, "atomic_replace", lambda a, b: (_ for _ in ()).throw(OSError("no")))
    with pytest.raises(OSError):
        fsutil.write_text(p, "new")
    assert p.read_text(encoding="utf-8") == "old" and not list(tmp_path.rglob("*.part"))


def test_put_file_links_or_copies_and_is_whole(tmp_path, monkeypatch):
    src = tmp_path / "src.bin"
    src.write_bytes(b"x" * 1000)
    dst = tmp_path / "out" / "dst.bin"
    assert fsutil.put_file(src, dst) in ("link", "copy") and dst.read_bytes() == src.read_bytes()
    assert fsutil.put_file(src, dst) == "same"
    # a new file renamed over the source by the app (as the app always writes) leaves the published copy as it was
    new = tmp_path / "src.new"
    new.write_bytes(b"y" * 500)
    os.replace(new, src)
    assert dst.read_bytes() == b"x" * 1000
    assert fsutil.put_file(src, dst) in ("link", "copy") and dst.read_bytes() == b"y" * 500
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError("no links")))
    other = tmp_path / "out" / "copy.bin"
    assert fsutil.put_file(src, other) == "copy" and other.read_bytes() == src.read_bytes()


def test_keep_only_and_sweep(tmp_path):
    for n in ("a.jpg", "b.jpg", "notes.txt", "c.jpg.part"):
        (tmp_path / n).write_bytes(b"1")
    assert fsutil.keep_only(tmp_path, {"a.jpg"}, suffixes=(".jpg",)) == ["b.jpg"]
    assert (tmp_path / "notes.txt").exists() and (tmp_path / "a.jpg").exists()
    assert fsutil.sweep_parts(tmp_path) == 1 and not (tmp_path / "c.jpg.part").exists()
    assert fsutil.dir_bytes(tmp_path) == (2, 2)
