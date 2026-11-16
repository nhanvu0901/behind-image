"""Paths and the fixed list of books of the library (no LLM, no network)."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOKS_DIR = REPO_ROOT / "books"
LIB_DIR = REPO_ROOT / "library"
PROJECTS_DIR = REPO_ROOT / "projects"

WORK_ID_RE = re.compile(r"([a-z0-9_]{1,40})/(\d{3})")
BOOK_ID_RE = re.compile(r"[a-z0-9_]{1,40}")

BOOKS = [
    dict(id="payne_gae", key="Great_Art_Explained", title="Great Art Explained", author="James Payne",
         pdf_type="digital", unit="chapter_per_artwork"),
    dict(id="hodge_aid", key="Art in detail", title="Art in Detail: 100 Masterpieces", author="Susie Hodge",
         pdf_type="scan", unit="fixed_spread"),
    dict(id="hagen_wgps", key="What Great Paintings Say", title="What Great Paintings Say, Vol. 2",
         author="Rose-Marie and Rainer Hagen", pdf_type="scan", unit="fixed_spread"),
    dict(id="grovier_nws", key="A_New_Way_of_Seeing", title="A New Way of Seeing", author="Kelly Grovier",
         pdf_type="digital", unit="chapter_per_artwork"),
    dict(id="brookehitching_mad", key="Madmans_Gallery", title="The Madman's Gallery",
         author="Edward Brooke-Hitching", pdf_type="digital", unit="short_entries"),
    dict(id="dasal_artcurious", key="ArtCurious", title="ArtCurious", author="Jennifer Dasal",
         pdf_type="digital", unit="themed_chapter"),
]
TRUST_NOTE_LOW = "Bản dịch máy, không dùng làm nguồn sự kiện: văn xuôi thiếu tin cậy, nhiều tên riêng bị dịch sai."
BOOK_BY_ID = {b["id"]: b for b in BOOKS}


def book_pdf(book_id: str) -> Path | None:
    key = BOOK_BY_ID[book_id]["key"]
    for f in sorted(BOOKS_DIR.glob("*.pdf")):
        if key in f.name:
            return f
    return None


def book_dir(book_id: str) -> Path:
    return LIB_DIR / "books" / book_id
