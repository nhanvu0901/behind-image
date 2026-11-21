"""python -m bti.library build | regroup | dossiers [--book ID | key ...] | trust BOOK_ID   (deterministic, no LLM)."""
from __future__ import annotations

import json
import sys

from . import catalogue, config, dossiers


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "build":
        s = catalogue.build(only=argv[1:] or None)
        print(json.dumps({"books": s["books"], "artworks": s["artworks"], "multi_book": len(s["multi_book"]),
                          "unparsed": len(s["unparsed"])}, ensure_ascii=False))
    elif cmd == "regroup":
        s = catalogue.regroup()
        print(json.dumps({"artworks": s["artworks"], "multi_book": len(s["multi_book"])}))
    elif cmd == "dossiers":
        if argv[1:2] == ["--book"]:       # only the dossiers that hold a work of this book: seconds, not minutes
            if len(argv) != 3 or argv[2] not in config.BOOK_BY_ID:
                print("usage: python -m bti.library dossiers --book BOOK_ID   (one of: " + ", ".join(config.BOOK_BY_ID) + ")")
                return 2
            done = dossiers.build_book(argv[2])
        else:
            done = dossiers.build_all(argv[1:] or None)
        print(json.dumps(dossiers.summary(done), ensure_ascii=False, indent=1))
    elif cmd == "trust":                  # read-only: the level of every work of a book and why (nothing is written)
        if len(argv) != 2 or argv[1] not in config.BOOK_BY_ID:
            print("usage: python -m bti.library trust BOOK_ID")
            return 2
        counts: dict[str, int] = {}
        for w in catalogue.load_works(argv[1]):
            tr, why = catalogue.work_trust_why(w)
            counts[tr["trust"]] = counts.get(tr["trust"], 0) + 1
            print(f"{w['id']}  {tr['trust']:<8}  {why}")
        print(json.dumps({"works_by_trust": counts}))
    else:
        print("usage: python -m bti.library build [book_id ...] | regroup | dossiers [--book BOOK_ID | artwork_key ...] | trust BOOK_ID")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
