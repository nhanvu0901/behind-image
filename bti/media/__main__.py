"""CLI: python -m bti.media {search,import,licence} ..."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import api
from .errors import MediaError


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bti.media")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="search a source")
    s.add_argument("query")
    s.add_argument("--source", choices=["commons", "met"], default="commons")
    s.add_argument("--kind", choices=["image", "video"], default="image")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--json", action="store_true")
    i = sub.add_parser("import", help="import one item into a project's media folder")
    i.add_argument("project_dir", type=Path)
    i.add_argument("source", choices=["commons", "met"])
    i.add_argument("source_id")
    i.add_argument("--min-short-side", type=int, default=None)
    l = sub.add_parser("licence", help="run the licence gate on a text")
    l.add_argument("text")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "licence":
            ok, name, reason = api.check_licence({"licence": a.text})
            print(json.dumps({"allowed": ok, "licence": name, "reason": reason}, ensure_ascii=False))
            return 0 if ok else 1
        if a.cmd == "search":
            rows = api.search(a.query, a.source, a.kind, a.limit)
            if a.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            for r in rows:
                if not a.json:
                    flag = "OK " if r["licence_ok"] else "NO "
                    print(f"{flag} {r['source_id']}  {r['width']}x{r['height']}  [{r['licence']}]  {r['title'][:60]}")
            return 0
        if a.cmd == "import":
            res = api.import_candidate(a.project_dir, a.source, a.source_id, min_short_side=a.min_short_side)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0
    except api.LicenceRejected as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 2
    except (MediaError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
