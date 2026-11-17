"""Atomic JSON writes. Adapted from comic-book-pipeline/utils/atomic_json.py (no Windows retry)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from bti.fsio import atomic_replace


def write_json_atomic(path: Path, doc: Any, *, indent: int = 2, parents: bool = True) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=parents, exist_ok=True)       # parents=False: FileNotFoundError when the folder above is gone
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=indent, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        atomic_replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


def read_json(path: Path, default: Any = None) -> Any:
    """Read JSON; a corrupt file is moved to `<name>.corrupt` (never overwritten silently)."""
    path = Path(path)
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        try:
            atomic_replace(path, path.with_name(path.name + ".corrupt"))
        except OSError:
            pass
        return default
