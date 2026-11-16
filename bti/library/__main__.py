"""python -m bti.library build | regroup | dossiers   (deterministic, no LLM)."""
from __future__ import annotations

import json
import sys

from . import catalogue, dossiers


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
        done = dossiers.build_all(argv[1:] or None)
        print(json.dumps(dossiers.summary(done), ensure_ascii=False, indent=1))
    else:
        print("usage: python -m bti.library build [book_id ...] | regroup | dossiers [artwork_key ...]")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
