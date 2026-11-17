"""`python -m bti.draft.check [workspace] [--chapter c03] [--no-draw] [--json]`

Compiles what is in the workspace's `out/` exactly as the final compiler will (spec -> storyboard, then the engine's validation and
a draw check of every shot) and prints the issues in the spec's terms: chapter, shot number, field. Exit status 0 when there is no
error, 1 otherwise. Warnings (pacing, repeated techniques, incomplete items) do not fail the check but are worth reading."""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="check", description=__doc__.split("\n")[0])
    ap.add_argument("workspace", nargs="?", default=".")
    ap.add_argument("--chapter", help="only report problems of this chapter")
    ap.add_argument("--no-draw", action="store_true", help="skip the draw check (faster)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    from .compile import summary_text
    from .inputs import DraftError
    from .workspace import workspace_compile
    try:
        res, out = workspace_compile(a.workspace, draw=not a.no_draw)
    except DraftError as e:
        print("ERROR %s: %s" % (e.code, e.message))
        return 2
    if a.chapter:
        res.issues = [i for i in res.issues if i.get("chapter") in (a.chapter, None)]
    if a.json:
        print(json.dumps({"errors": len(res.errors), "warnings": len(res.warnings), "issues": [{k: v for k, v in i.items() if k not in ("args", "rec")} for i in res.issues],
                          "stats": res.stats}, indent=1))
    else:
        print(summary_text(res))
        s = res.stats
        if s.get("agent_shots"):
            print("shots: %d, median %.1f s, shortest %.1f s, longest %.1f s; usage: %s" % (s["agent_shots"], s["median_shot_s"], s["shortest_s"], s["longest_s"],
                                                                                          ", ".join("%s %d" % kv for kv in sorted(s["usage"].items()))))
        if out.notes.strip() == "":
            print("note: out/notes.md is missing or empty; write it before you finish")
        if res.drawn:
            print("draw check: done")
    return 1 if res.errors else 0


if __name__ == "__main__":
    sys.exit(main())
