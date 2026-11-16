import json
from pathlib import Path

from bti.script.store import Beat, Fact, NChapter, Narration, OChapter, Outline


def make_outline(approved: bool = False) -> Outline:
    o = Outline("What does the mirror show?", [], None,
                [OChapter("c01", "cold_open", "COLD OPEN", False, "p", 100, ["f01"]),
                 OChapter("c02", "chapter", "THE ROOM", True, "p", 200, ["f02"]),
                 OChapter("c03", "closing", "CLOSING", False, "p", 100, [])],
                [Fact("f01", "The picture is dated 1434.", ["PAY-01"], "established"),
                 Fact("f02", "The couple may be the Arnolfinis.", ["PAY-02"], "disputed", "sources differ")], 400)
    if approved:
        o.approval = {"approved": True, "sha1": o.rev(), "approved_at": "2026-11-16T00:00:00"}
    return o


def words(n: int, w: str = "word") -> str:
    return " ".join([w] * (n - 1)) + " end."


def make_narration(sizes=(100, 200, 100), per_chapter: int = 2) -> Narration:
    n = Narration("t1", "The Test Painting", "en")
    ids = [("c01", "cold_open", "COLD OPEN", False), ("c02", "chapter", "THE ROOM", True), ("c03", "closing", "CLOSING", False)]
    for (cid, role, title, card), size in zip(ids, sizes):
        ch = NChapter(cid, role, title, card)
        per = max(size // per_chapter, 1)
        for _ in range(per_chapter):
            ch.beats.append(Beat(n.new_beat_id(), words(per), ["f01"], ["the mirror"]))
        n.chapters.append(ch)
    return n


SRC_A = """# THE TEST PAINTING

## THE MIRROR

The mirror hangs on the back wall and shows two people who are not in front of us. It is a convex mirror with a wooden frame.

Ten small scenes circle the glass. They show the last days of Christ.

## THE LAMP

A single candle burns in the chandelier above the man. The other holders are empty.
"""
SRC_B = """# TEST PAINTING

A second book says the mirror was a luxury item in that decade. It cost as much as a small house.

> A quoted line from the second book about the glass.

## DETAILS

The signature sits above the mirror.
"""
SRC_LOW = """# TEST PAINTING (machine translation)

The lamp was lit for the wedding according to this unreliable edition.
"""


def make_project(root: Path, pid: str = "t1", *, dossier: bool = True, low: bool = True) -> Path:
    d = root / pid
    (d / "source").mkdir(parents=True)
    (d / "source" / "payne_gae_001.txt").write_text(SRC_A, encoding="utf-8")
    (d / "source" / "hodge_aid_002.txt").write_text(SRC_B, encoding="utf-8")
    sources = [{"work_id": "payne_gae/001", "book_id": "payne_gae", "pdf_pages": [1, 2]},
               {"work_id": "hodge_aid/002", "book_id": "hodge_aid", "pdf_pages": [1, 2]}]
    if low:
        (d / "source" / "grovier_nws_003.txt").write_text(SRC_LOW, encoding="utf-8")
        sources.append({"work_id": "grovier_nws/003", "book_id": "grovier_nws", "pdf_pages": [1, 2]})
    proj = {"id": pid, "title": "The Test Painting", "artist": "A. Painter", "year": "1434", "stage": "selected",
            "sources": sources}
    if dossier:
        proj["dossier"] = "source/dossier.json"
        ds = [{"work_id": s["work_id"], "book_id": s["book_id"], "file": f"{s['book_id']}_{s['work_id'].split('/')[1]}.txt",
               "trust": "low" if s["book_id"] == "grovier_nws" else "normal",
               "trust_note": "machine translation" if s["book_id"] == "grovier_nws" else "",
               "outline": {"meta": ["A. Painter", "1434"]}} for s in sources]
        (d / "source" / "dossier.json").write_text(json.dumps({
            "artwork_key": "x", "identity": {"title": "The Test Painting", "artist": "A. Painter", "year": "1434"},
            "conflicts": [{"field": "year", "values": [{"work_id": "payne_gae/001", "value": "1434"},
                                                      {"work_id": "hodge_aid/002", "value": "1435"}]}],
            "sources": ds}), encoding="utf-8")
    (d / "project.json").write_text(json.dumps(proj), encoding="utf-8")
    return d


