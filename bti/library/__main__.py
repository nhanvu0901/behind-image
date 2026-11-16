"""python -m bti.library build   -- write library/ catalogue (deterministic, no LLM)."""
from __future__ import annotations

import json
import sys

from . import catalogue


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "build":
        print("usage: python -m bti.library build [book_id ...]")
        return 2
    s = catalogue.build(only=argv[1:] or None)
    print(json.dumps({"books": s["books"], "artworks": s["artworks"], "multi_book": len(s["multi_book"]),
                      "unparsed": len(s["unparsed"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
