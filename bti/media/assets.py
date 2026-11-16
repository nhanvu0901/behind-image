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

INDEX_NAME = "sources.json"
_STOP = {"with", "from", "by", "for", "the", "of", "a", "an", "and", "de", "la", "le", "in", "on", "at", "file"}
MAX_KEY = 24


def slugify(title: str, fallback: str = "img") -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", textfold.fold(title)) if w not in _STOP]
    slug = "_".join(words[:3])[:MAX_KEY].strip("_")
    return slug or fallback


def media_dir(project_dir: Path) -> Path:
    d = Path(project_dir) / "media"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_index(project_dir: Path) -> dict:
    doc = read_json(Path(project_dir) / "media" / INDEX_NAME, {}) or {}
    doc.setdefault("items", {})
    return doc


def save_index(project_dir: Path, doc: dict) -> None:
    write_json_atomic(media_dir(project_dir) / INDEX_NAME, doc)


def taken_keys(project_dir: Path, index: dict) -> set[str]:
    keys = {v.get("key") for v in index["items"].values()}
    sb = read_json(Path(project_dir) / "storyboard.json", {}) or {}
    if isinstance(sb.get("assets"), dict):
        keys |= set(sb["assets"])
    return {k for k in keys if k}


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


def register(project_dir: Path, ident: str, key: str, asset: dict) -> None:
    idx = load_index(project_dir)
    idx["items"][ident] = {"key": key, "asset": asset}
    save_index(project_dir, idx)
