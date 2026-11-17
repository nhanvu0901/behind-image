"""Shared helpers: asset keys, the per-project source index, asset entries.

The media folder keeps `media/sources.json` (our own index, atomic writes) so that
importing the same source item twice returns the same key and file. Nothing here edits
storyboard.json; it is read (if present) only to avoid key clashes.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

from ._io import read_json, write_json_atomic
from .. import textfold
from bti.fsio import atomic_replace

INDEX_NAME = "sources.json"
_STOP = {"with", "from", "by", "for", "the", "of", "a", "an", "and", "de", "la", "le", "in", "on", "at", "file"}
MAX_KEY = 24


def slugify(title: str, fallback: str = "img") -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", textfold.fold(title)) if w not in _STOP]
    slug = "_".join(words[:3])[:MAX_KEY].strip("_")
    return slug or fallback


def media_dir(project_dir: Path, require_root: bool = False) -> Path:
    """`<project>/media`. `require_root`: the project folder must already exist (FileNotFoundError otherwise) and is never
    created here; the default (stand-alone use) makes the whole path."""
    d = Path(project_dir) / "media"
    if require_root and not Path(project_dir).is_dir():
        raise FileNotFoundError(f"project folder {Path(project_dir).name!r} does not exist")
    d.mkdir(parents=not require_root, exist_ok=True)
    return d


def load_index(project_dir: Path) -> dict:
    doc = read_json(Path(project_dir) / "media" / INDEX_NAME, {}) or {}
    if not isinstance(doc, dict):            # valid JSON of the wrong shape: set aside like a corrupt file, start a new index
        try:
            p = Path(project_dir) / "media" / INDEX_NAME
            atomic_replace(p, p.with_name(p.name + ".corrupt"))
        except OSError:
            pass
        doc = {}
    if not isinstance(doc.get("items"), dict):
        doc["items"] = {}
    doc["items"] = {k: v for k, v in doc["items"].items() if isinstance(v, dict)}
    return doc


def save_index(project_dir: Path, doc: dict, require_root: bool = False) -> None:
    write_json_atomic(media_dir(project_dir, require_root) / INDEX_NAME, doc, parents=not require_root)


def taken_keys(project_dir: Path, index: dict) -> set[str]:
    keys = {v.get("key") for v in index["items"].values()}
    for name in ("storyboard.json", "picks.json"):          # an asset key is shared by the picks and the storyboard
        doc = _peek(Path(project_dir) / name)
        if isinstance(doc.get("assets"), dict):
            keys |= set(doc["assets"])
    return {k for k in keys if k}


def _peek(path: Path) -> dict:
    """The JSON object of a project document, or {} when it is missing or unreadable. Read only: a damaged file is left
    where it is (it belongs to another stage, which reports it)."""
    import json
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def make_key(title: str, ident: str, taken: set[str]) -> str:
    """Short, unique, stable: the slug of the title, plus 4 hex of the id hash on a clash."""
    base = slugify(title)
    if base not in taken:
        return base
    suffix = hashlib.sha1(ident.encode()).hexdigest()[:4]
    key = f"{base[:MAX_KEY - 5]}_{suffix}"
    n = 2
    while key in taken:
        key = f"{base[:MAX_KEY - 7]}_{suffix}{n}"
        n += 1
    return key


def year_of(text: str) -> str:
    m = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", text or "")
    return m.group(1) if m else ""


def build_asset(file_rel: str, kind: str, title: str, artist: str, year: str,
                width: int, height: int, credit: dict) -> dict:
    return {"file": file_rel, "kind": kind, "title": title, "artist": artist, "year": year,
            "width": int(width), "height": int(height), "credit": credit}


def register(project_dir: Path, ident: str, key: str, asset: dict, require_root: bool = False) -> None:
    idx = load_index(project_dir)
    idx["items"][ident] = {"key": key, "asset": asset}
    save_index(project_dir, idx, require_root)
