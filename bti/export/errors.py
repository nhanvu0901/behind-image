"""Errors of the export. `code` is a stable word the page maps to a sentence in Vietnamese (errmsg.js)."""
from __future__ import annotations


class ExportError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra

    def body(self) -> dict:
        return {"detail": self.message, "code": self.code, **self.extra}


# The sentence the owner reads when a job part fails with this code (the page has the same table in views/export.js).
VI = {
    "render_failed": "Dựng hình bị dừng giữa chừng. Bấm Xuất video lần nữa để làm tiếp: những đoạn đã dựng xong được giữ lại.",
    "frames_mismatch": "Số khung hình của video không đúng với kế hoạch, nên đã dừng để không tạo ra tệp sai.",
    "join_failed": "Không ghép được các đoạn video lại với nhau.",
    "part_missing": "Thiếu một đoạn video đã dựng. Bấm Xuất video lần nữa.",
    "mux_failed": "Không ghép được tiếng và mục lục vào video.",
    "project_gone": "Dự án đã bị xóa.",
}


def part_error(e: "ExportError"):
    """The runner's `PartError` for an ExportError raised inside a job part."""
    from bti.longjob import PartError
    return PartError(e.code, VI.get(e.code, e.message))
