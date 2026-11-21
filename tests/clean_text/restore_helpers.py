"""Invented fixtures for the restore tool: a two-work book in the clean page format, and canned model answers.
No text of any real book is used."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# A machine-garbled invented text ("Bel" for the artist Pell, "wrote" for "painted") and the way a good model fixes it.
FIXES = [
    ("Odran Bel", "Odran Pell"),
    ("Bel's", "Pell's"),
    ("Bel ", "Pell "),
    ("wrote this picture", "painted this picture"),
    ("hangs down", "sinks"),
    ("the hand that bakes the thing of the lamp", "[[? the hand that bakes the thing of the lamp ?]]"),
]
READING_FROM, READING_TO = "truly festive", "truly sombre"
READINGS = f"{READING_FROM} => {READING_TO}"
NAMES = "Odran Bel => Odran Pell\nBel => Pell"

P1 = ("Bel's lamp-lighting man is a painting that remained in the dark for a century. It shows a worker of the city who climbs "
      "a ladder at the hour when the sun hangs down, lighting the street's flame one by one. The ladder leans on a wall of grey brick "
      "and the worker does not look at us.")
P2 = ("The artist Odran Bel was born in a fishing village and did not study in the academy. He wrote this picture in a small room, "
      "which he rented with his brother, and sold it in 1871 for the price of a coat to a baker who loved it. The baker kept it above "
      "his oven for thirty years and showed it to no one.")
P3 = ("The strangeness of the picture lies in the hand that bakes the thing of the lamp, which the critics of that time called the "
      "grammar of the street. Nobody agreed what they meant, and the phrase stayed in the books for a very long time after them.")
P4 = ("Bel painted two more pictures of the city before he died. Both show the same ladder, though in the second one the worker has "
      "turned his back. Critics thought the second picture truly festive, though the street is empty. A small dog sits at the foot of the wall waiting for the lamps to be lit, as dogs do in the evening.")
P5 = ("When the baker died, the painting passed to his daughter, who sold it for 500 coins to a dealer. The dealer sold it again "
      "the same year, and from that day it was shown in the museums of the north, where visitors still stop to look at the ladder.")
P6 = ("The second work in this invented book is about a harbour at night. Bel's harbour shows boats tied side by side, and the "
      "water between them is painted with such care that the whole picture seems to move, even when the visitor stands still.")
P7 = ("A critic wrote that the harbour was the quietest picture of its age. The quiet came from the way the painter left the sky "
      "almost empty, with only one thin cloud that hangs down toward the masts like a piece of cloth that someone forgot.")

PAGE1 = f"""[page-type] body

# 01 Odran Pell, The Lamplighter

[meta] (1871)

{P1}

{P2}

{P3}
"""

PAGE2 = f"""[page-type] body

{P4}

{P5}

[quote] The lamps are lit.
[quote] The ladder is still.

[caption] Odran Bel, The Lamplighter (1871)

[continues]
"""

PAGE3 = """[page-type] plate

[caption] The Lamplighter (1871), detail of the ladder

[credit] Collection of the invented museum
"""

PAGE4 = f"""[page-type] body

# 02 Odran Pell, The Harbour at Night

[meta] (1873)

{P6}

{P7}
"""

PAGE5 = """[page-type] plate

[caption] The Harbour at Night (1873)
"""

PAGE6 = """[page-type] body

# 03 Nobody, A Plate Only

[caption] The Empty Frame
"""

PAGES = {1: PAGE1, 2: PAGE2, 3: PAGE3, 4: PAGE4, 5: PAGE5, 6: PAGE6}

WORKS = [
    {"id": "inv_book/001", "n": 1, "title": "The Lamplighter", "artist": "Odran Pell", "year": "1871", "pdf_pages": [1, 3]},
    {"id": "inv_book/002", "n": 2, "title": "The Harbour at Night", "artist": "Odran Pell", "year": "1873", "pdf_pages": [4, 5]},
    {"id": "inv_book/003", "n": 3, "title": "A Plate Only", "artist": None, "year": None, "pdf_pages": [6, 6]},
]


def write_clean(clean_dir: Path, pages: dict | None = None) -> None:
    clean_dir.mkdir(parents=True, exist_ok=True)
    for n, t in (pages or PAGES).items():
        (clean_dir / f"page_{n:04d}.txt").write_bytes(t.encode("utf-8"))


def fix(text: str) -> str:
    for a, b in FIXES:
        text = text.replace(a, b)
    return text


def rfix(text: str) -> str:
    """`fix` plus the declared reading."""
    return fix(text).replace(READING_FROM, READING_TO)


def answer(page_nums, *, names: str | None = NAMES, transform=fix, pages: dict | None = None, wrap: str = "",
           readings: str | None = None) -> str:
    """A good canned answer for the BODY pages among page_nums. `transform` is applied to each page's text."""
    src = pages or PAGES
    out = []
    for n in page_nums:
        t = src[n]
        if not t.startswith("[page-type] body"):
            continue
        out.append(f"=== page_{n:04d} ===\n{transform(t).rstrip()}\n")
    text = "\n".join(out)
    if names is not None:
        text += "\n=== names ===\n" + names + "\n"
    if readings is not None:
        text += "\n=== readings ===\n" + readings + "\n"
    return wrap + text
