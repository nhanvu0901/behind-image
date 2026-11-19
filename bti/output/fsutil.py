"""Small file helpers of the output folder: every write is "write `<name>.part`, then rename over `<name>`", so a reader (or a copy to the owner's Mac) never meets a half-written file.

Big files (the video, the audio) are put in place with `put_file`: a hard link when the drive allows it (no second copy of 900 MB; the app never writes a file in place, it
always renames a new one over the old, so the link keeps the old version when the app makes a new one), else a copy. Either way the file appears under its final name only when it is whole."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from bti.fsio import atomic_replace

PART = ".part"


def part_of(path: Path) -> Path:
    return path.with_name(path.name + PART)


def ensure_dir(path: Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def write_bytes(path: Path, data: bytes) -> bool:
    """Atomic write. Returns False (and writes nothing) when the file already holds exactly these bytes."""
    path = Path(path)
    try:
        if path.is_file() and path.stat().st_size == len(data) and path.read_bytes() == data:
            return False
    except OSError:
        pass
    ensure_dir(path.parent)
    tmp = part_of(path)
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        atomic_replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return True


def write_text(path: Path, text: str) -> bool:
    """UTF-8, `\\n` line ends on every platform."""
    return write_bytes(path, text.encode("utf-8"))


def write_json(path: Path, obj: Any) -> bool:
    return write_text(path, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def same_file(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def put_file(src: Path, dst: Path, *, link: bool = True) -> str:
    """Put a copy of `src` at `dst`, whole or not at all. -> "same" (nothing to do), "link" or "copy"."""
    src, dst = Path(src), Path(dst)
    if dst.is_file():
        if same_file(src, dst):
            return "same"
        try:
            s, d = src.stat(), dst.stat()
            if s.st_size == d.st_size and s.st_mtime_ns == d.st_mtime_ns:      # a copy made by `copy2` of this very file
                return "same"
        except OSError:
            pass
    ensure_dir(dst.parent)
    tmp = part_of(dst)
    try:
        tmp.unlink()
    except OSError:
        pass
    how = "copy"
    try:
        if link:
            try:
                os.link(src, tmp)
                how = "link"
            except OSError:
                shutil.copy2(src, tmp)
        else:
            shutil.copy2(src, tmp)
        atomic_replace(tmp, dst)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return how


def remove(path: Path) -> bool:
    try:
        Path(path).unlink()
        return True
    except OSError:
        return False


def keep_only(folder: Path, names: set[str], *, suffixes: tuple[str, ...] | None = None) -> list[str]:
    """Remove the files directly inside `folder` that are not in `names` (and, with `suffixes`, only those whose name ends with one). Returns what was removed."""
    gone: list[str] = []
    try:
        entries = list(Path(folder).iterdir())
    except OSError:
        return gone
    for p in entries:
        if p.is_file() and p.name not in names and (suffixes is None or p.name.lower().endswith(suffixes)):
            if remove(p):
                gone.append(p.name)
    return gone


def sweep_parts(root: Path) -> int:
    """Remove the `.part` files a crash left behind anywhere under `root`."""
    n = 0
    try:
        for p in Path(root).rglob("*" + PART):
            if p.is_file() and remove(p):
                n += 1
    except OSError:
        pass
    return n


def dir_bytes(path: Path) -> tuple[int, int]:
    """(files, bytes) of everything under `path` (0, 0 when it is not there). Links are not followed."""
    n = size = 0
    path = Path(path)
    if path.is_file():
        try:
            return 1, path.stat().st_size
        except OSError:
            return 0, 0
    for dp, _dn, fn in os.walk(path):
        for f in fn:
            try:
                size += os.lstat(os.path.join(dp, f)).st_size
                n += 1
            except OSError:
                pass
    return n, size
