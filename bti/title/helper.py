"""The helper command of the agent's work folder (`./check`, a one-line wrapper around this module; the folder is the current directory).

    check      validate out/title.json the way the program will, in plain sentences; the last line is `N error(s), M warning(s)`

Nothing here reaches outside the work folder and nothing is written."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bti.picks.auto.shapes import read_json_file

from . import check as C

MODE_FILE = "inputs/context.json"
OUT_FILE = "out/title.json"


def load_lines(root: Path) -> dict:
    f = Path(root) / MODE_FILE
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d["mode"] != "title" or not isinstance(d["lines"], dict):
            raise KeyError("mode")
        return {str(k): str(v) for k, v in d["lines"].items()}
    except (OSError, ValueError, KeyError):
        raise SystemExit("ERROR this is not a title work folder (inputs/context.json is missing or unreadable)")


def run_check(root: Path) -> C.Report:
    """The report of the work folder's output file. The session uses this too (the repair message is its text)."""
    lines = load_lines(root)
    obj, problem = read_json_file(Path(root) / OUT_FILE, OUT_FILE)
    if problem:
        rep = C.Report()
        rep.errors.append(problem)
        return rep
    return C.check_choice(obj, lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="helper", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="validate your output file")
    ap.parse_args(argv)
    rep = run_check(Path.cwd())
    print(rep.text())
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
