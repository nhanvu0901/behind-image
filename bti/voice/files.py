"""Where the voice stage keeps its files, and how it reads and writes them (through the script stage's loader and atomic
writers, so a damaged file is a `DataError`-style 409 and a write never brings back a deleted project)."""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from bti.script import store

SCHEMA = "bti.voice/1"


def voice_dir(pdir: Path) -> Path:
    return Path(pdir) / "voice"


def chunks_dir(pdir: Path) -> Path:
    return voice_dir(pdir) / "chunks"


def chunk_path(pdir: Path, cid: str) -> Path:
    return chunks_dir(pdir) / f"{cid}.wav"


def manifest_path(pdir: Path) -> Path:
    return voice_dir(pdir) / "voice.json"


def pronounce_path(pdir: Path) -> Path:
    return voice_dir(pdir) / "pronounce.json"


def settings_path(pdir: Path) -> Path:
    return voice_dir(pdir) / "settings.json"


def mix_path(pdir: Path) -> Path:
    return Path(pdir) / "audio" / "mix.m4a"


def dry_path(pdir: Path) -> Path:
    return Path(pdir) / "audio" / "voice.wav"


def timing_path(pdir: Path) -> Path:
    return Path(pdir) / "timing.json"


def workdir(pdir: Path, name: str = "voice") -> Path:
    return Path(pdir) / "cache" / name


def read_manifest(pdir: Path) -> dict | None:
    return store.read_object(manifest_path(pdir), "voice")


def read_pronounce(pdir: Path) -> dict[str, str]:
    d = store.read_object(pronounce_path(pdir), "voice")
    t = (d or {}).get("table") if d else None
    return {str(k): str(v) for k, v in t.items()} if isinstance(t, dict) else {}


def write_pronounce(pdir: Path, table: dict[str, str]) -> None:
    store.write_json_atomic(pronounce_path(pdir), {"schema": "bti.pronounce/1", "table": table})


def read_settings(pdir: Path) -> dict:
    return store.read_object(settings_path(pdir), "voice") or {}


def write_settings(pdir: Path, settings: dict) -> None:
    store.write_json_atomic(settings_path(pdir), settings)


@contextmanager
def project_lock(pdir: Path):
    """The per-project lock, and (under it) a check that the project still exists. Taken only for the final write of a result."""
    with store.script_lock(pdir):
        if not Path(pdir).is_dir():
            raise store.ProjectGone("the project folder is gone")
        yield


def update_manifest(pdir: Path, fn) -> dict:
    """Read the manifest (or a new one), let `fn(doc)` change it in place, write it atomically, all under the project lock."""
    with project_lock(pdir):
        doc = read_manifest(pdir) or {"schema": SCHEMA}
        doc.setdefault("schema", SCHEMA)
        fn(doc)
        store.write_json_atomic(manifest_path(pdir), doc)
        return doc


def write_timing(pdir: Path, timing: dict) -> None:
    with project_lock(pdir):
        store.write_json_atomic(timing_path(pdir), timing, levels=1)


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
