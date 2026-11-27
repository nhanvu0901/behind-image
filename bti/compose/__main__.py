"""Compose a project to stdout, or to an explicit output file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import compose


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    def read(name):
        return json.loads((args.project / name).read_text(encoding="utf-8"))

    current_path = args.project / "storyboard.json"
    current = read("storyboard.json") if current_path.exists() else None
    style = {"id": (current or {}).get("style", "gae")}
    doc, _ = compose(read("visual.json"), read("timing.json"), read("picks.json"), style, current)
    output = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
