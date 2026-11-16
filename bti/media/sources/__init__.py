"""Image/video sources behind one small protocol."""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from pathlib import Path


@runtime_checkable
class MediaSource(Protocol):
    name: str

    def search(self, query: str, kind: str = "image", limit: int = 24) -> list[dict]:
        """Normalised metadata dicts (see commons.parse_page for the shape)."""

    def fetch_meta(self, source_id: str) -> dict: ...

    def download(self, meta: dict, dest: Path, **kw) -> Path: ...

    def licence(self, meta: dict) -> tuple[bool, str, str]: ...

    def credit(self, meta: dict) -> dict: ...
