"""The case files of the bench: `evals/cases/<step>/<name>.json`, one case each.

    {
      "schema": "bti.eval.case/1",
      "name": "outline-chapter-count",                       the file name without .json (unique over all cases)
      "step": "outline",                                     outline | narration | draft | edit_storyboard | edit_picks | picks_agent
      "title": "...",                                        one line for the summary
      "why": "...",                                          where the criteria come from (a briefing, docs/APP_GUIDE.md)
      "sample": {"project": "arnolfini-from-books", "start": "book"},     the sample project and the state the copy starts from (bti/evals/samples.py)
      "request": {...},                                      what the step is asked: see the table in bti/evals/driver.py
      "criteria": [{"id": "chapters", "kind": "outline.chapters_between", "min": 5, "max": 9}, ...]       each id is a short word, unique in the case
    }

A criterion is checked on what the agent made (bti/evals/criteria.py lists the kinds and their parameters). A case file with a mistake is refused by
`load_case` with one sentence that names the file.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import criteria

REPO = Path(__file__).resolve().parents[2]
CASES_DIR = REPO / "evals" / "cases"
SCHEMA = "bti.eval.case/1"
STEPS = ("outline", "narration", "draft", "edit_storyboard", "edit_picks", "picks_agent")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class CaseError(Exception):
    pass


@dataclass
class Case:
    name: str
    step: str
    title: str
    why: str
    sample: dict
    request: dict
    criteria: list[dict]
    path: Path | None = field(default=None, compare=False)

    def public(self) -> dict:
        return {"name": self.name, "step": self.step, "title": self.title, "sample": self.sample, "request": self.request, "criteria": [c["id"] for c in self.criteria]}


def check_case(raw, where: str = "case") -> list[str]:
    """The problems of a decoded case file (an empty list when it is fine)."""
    if not isinstance(raw, dict):
        return ["%s: a case is a JSON object" % where]
    out: list[str] = []
    if raw.get("schema") != SCHEMA:
        out.append("schema must be %r" % SCHEMA)
    if not isinstance(raw.get("name"), str) or not NAME_RE.match(raw.get("name") or ""):
        out.append("name must be lowercase words joined by - (at most 64 characters)")
    if raw.get("step") not in STEPS:
        out.append("step must be one of %s" % ", ".join(STEPS))
    for k in ("title", "why"):
        if not isinstance(raw.get(k), str) or not raw[k].strip():
            out.append("%s must be a sentence" % k)
    s = raw.get("sample")
    if not (isinstance(s, dict) and isinstance(s.get("project"), str) and isinstance(s.get("start"), str)):
        out.append("sample must be {project, start}")
    if not isinstance(raw.get("request"), dict):
        out.append("request must be an object")
    crit = raw.get("criteria")
    if not isinstance(crit, list) or not crit:
        out.append("criteria must be a list with at least one criterion")
    else:
        ids = [c.get("id") for c in crit if isinstance(c, dict)]
        if len(set(ids)) != len(ids):
            out.append("criteria ids must be unique")
        for c in crit:
            out += criteria.check_spec(c)
    extra = [k for k in raw if k not in ("schema", "name", "step", "title", "why", "sample", "request", "criteria")]
    if extra:
        out.append("unknown keys: %s" % ", ".join(extra))
    return out


def load_case(path: Path | str) -> Case:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CaseError("%s: cannot be read as JSON (%s)" % (path.name, e))
    problems = check_case(raw, path.name)
    if not problems and raw["name"] != path.stem:
        problems.append("name %r must be the file name %r" % (raw["name"], path.stem))
    if not problems:
        from .driver import check_request
        problems += check_request(raw["step"], raw["request"])
    if problems:
        raise CaseError("%s: %s" % (path.name, "; ".join(problems)))
    return Case(raw["name"], raw["step"], raw["title"], raw["why"], raw["sample"], raw["request"], raw["criteria"], path)


def load_cases(step: str | None = None, names: list[str] | None = None, root: Path | str | None = None) -> list[Case]:
    """The cases of a step (all steps when `step` is None), in file order; `names` keeps only those. An unknown name is an error."""
    root = Path(root) if root else CASES_DIR
    out: list[Case] = []
    for f in sorted(root.glob("*/*.json")):
        if step and f.parent.name != step:
            continue
        c = load_case(f)
        if c.step != f.parent.name:
            raise CaseError("%s: the case is of step %s but sits in the folder %s" % (f.name, c.step, f.parent.name))
        out.append(c)
    seen: set[str] = set()
    for c in out:
        if c.name in seen:
            raise CaseError("two cases are called %s" % c.name)
        seen.add(c.name)
    if names:
        missing = [n for n in names if n not in {c.name for c in out}]
        if missing:
            raise CaseError("no such case%s: %s (python -m bti.evals list)" % (" in step " + step if step else "", ", ".join(missing)))
        out = [c for c in out if c.name in names]
    return out
