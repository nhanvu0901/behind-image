"""Validate the music document produced in a model workspace."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from bti.engine.timing import Timing
from bti.title.check import Report
from .document import MusicError, validate


def run_check(root):
    report = Report()
    try:
        data = json.loads((Path(root) / "inputs" / "context.json").read_text(encoding="utf-8"))
        doc = json.loads((Path(root) / "out" / "music.json").read_text(encoding="utf-8"))
        validate(doc, data["library"], Timing(data["timing"]), data["duration"], data["landmarks"])
        report.value = doc
    except (OSError, ValueError, KeyError, TypeError, MusicError) as exc:
        report.errors.append(str(exc))
    return report


def main():
    if sys.argv[1:] != ["check"]:
        raise SystemExit("usage: python -m bti.music.helper check")
    report = run_check(Path.cwd())
    print(report.text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
