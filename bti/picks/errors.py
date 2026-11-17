"""Errors of the picks stage. The API layer turns each into `{detail, code, ...}` with the status."""
from __future__ import annotations


class PicksError(Exception):
    def __init__(self, status: int, detail: str, code: str = "", **extra):
        super().__init__(detail)
        self.status, self.detail, self.code, self.extra = status, detail, code, extra
