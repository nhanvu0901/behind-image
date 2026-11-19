"""The command of the bench: `python -m bti.evals list | run | compare | show`. The words are English (it is for the people and the agents that run the bench).

    list [--step S] [--criteria]            the cases (name, step, sample, criteria), or the kinds of criteria with their parameters
    run --step S --agent ID [--repeat 3] [--case NAME ...] [--yes-cost] [--url URL] [--samples-root DIR] [--projects-root DIR] [--out DIR] [--keep]
                                            run the cases of a step several times on a copy of the sample project and count; says first how many agent runs it is about
                                            to ask for and needs --yes-cost to go on (exit 3 without it, nothing is started)
    compare A B                             what changed between two runs (files or run ids under --out)
    show RUN                                the summary of one run

Exit codes: 0 done; 2 typed wrong; 3 `--yes-cost` is missing or the agent cannot run; 4 the run could not start; 6 the app cannot be reached.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from bti.cli.transport import DEFAULT_URL, HttpTransport

from . import cases as cases_mod, criteria, driver, report, runner

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / ".scratch" / "evals"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m bti.evals", description="A bench for the agents of the app: sample requests, several repeats, counted against criteria a program checks.")
    sub = p.add_subparsers(dest="command", metavar="command")
    sp = sub.add_parser("list", help="the cases, or the kinds of criteria")
    sp.add_argument("--step", choices=cases_mod.STEPS)
    sp.add_argument("--criteria", action="store_true", help="list the kinds of criteria with their parameters instead of the cases")
    sp = sub.add_parser("run", help="run the cases of a step several times and count")
    sp.add_argument("--step", required=True, choices=cases_mod.STEPS)
    sp.add_argument("--agent", required=True, metavar="ID", help="the agent id (GET /api/agents lists them)")
    sp.add_argument("--repeat", type=int, default=3, metavar="N", help="how many times each case is run (default 3)")
    sp.add_argument("--case", action="append", default=[], metavar="NAME", help="only this case (repeatable)")
    sp.add_argument("--yes-cost", dest="yes_cost", action="store_true", help="go on after the line that says how many agent runs this asks for")
    sp.add_argument("--url", default=None, help="the app's address (default BTI_URL, else %s)" % DEFAULT_URL)
    sp.add_argument("--samples-root", default=None, metavar="DIR", help="where the sample projects are (default: the projects folder of this repository)")
    sp.add_argument("--projects-root", default=None, metavar="DIR", help="the projects folder of the app the bench talks to, where the copies are made (default BTI_PROJECTS_ROOT, else the one of this repository)")
    sp.add_argument("--cases-root", default=None, metavar="DIR", help="the case files (default evals/cases of this repository)")
    sp.add_argument("--out", default=None, metavar="DIR", help="where the run file, the outputs and the summary are written (default .scratch/evals)")
    sp.add_argument("--keep", action="store_true", help="leave the copies of the projects in the app (they are named eval-...)")
    sp.add_argument("--poll", type=float, default=2.0, metavar="SECONDS", help="seconds between two looks at a job (default 2)")
    sp.add_argument("--job-timeout", dest="job_timeout", type=float, default=3 * 3600.0, metavar="SECONDS", help="stop waiting for one job after this long (default 3 hours)")
    sp = sub.add_parser("compare", help="what changed between two runs")
    sp.add_argument("a")
    sp.add_argument("b")
    sp.add_argument("--out", default=None, metavar="DIR")
    sp = sub.add_parser("show", help="the summary of one run")
    sp.add_argument("run")
    sp.add_argument("--out", default=None, metavar="DIR")
    return p


def cmd_list(a, out) -> int:
    if a.criteria:
        for c in criteria.describe():
            out.write("%s   needs: %s\n    %s\n    parameters: %s\n" % (c["kind"], ", ".join(c["needs"]) or "-", c["doc"], json.dumps(c["params"]) if c["params"] else "none"))
        return 0
    cs = cases_mod.load_cases(a.step)
    for c in cs:
        out.write("%-42s %-16s %s/%s   %s\n    %s\n" % (c.name, c.step, c.sample["project"], c.sample["start"], c.title, "criteria: " + ", ".join(x["id"] for x in c.criteria)))
    out.write("%d cases\n" % len(cs))
    return 0


def cmd_run(a, out, err, *, transport=None, sleep=time.sleep, clock=time.monotonic) -> int:
    if a.repeat < 1 or a.repeat > 20:
        err.write("usage: --repeat must be from 1 to 20\n")
        return 2
    url = a.url or os.environ.get("BTI_URL") or DEFAULT_URL
    t = transport or HttpTransport(url)
    samples_root = Path(a.samples_root) if a.samples_root else REPO / "projects"
    projects_root = Path(a.projects_root or os.environ.get("BTI_PROJECTS_ROOT") or REPO / "projects")
    try:
        cs = cases_mod.load_cases(a.step, a.case or None, a.cases_root)
        if not cs:
            err.write("there are no cases of step %s\n" % a.step)
            return 2
        agent = runner.find_agent(t, a.agent)
        for line in runner.plan(a.step, cs, a.repeat, agent):
            out.write(line + "\n")
        if not a.yes_cost:
            out.write("nothing was started: add --yes-cost to go on (it asks the agent for real work)\n")
            return 3
        rec, outputs = runner.run(step=a.step, agent_id=a.agent, repeat=a.repeat, transport=t, case_names=a.case or None, samples_root=samples_root, projects_root=projects_root,
                                  app_url=url, cases_root=a.cases_root, keep=a.keep, poll=a.poll, job_timeout=a.job_timeout, say=lambda s: out.write(s + "\n"), sleep=sleep, clock=clock)
    except cases_mod.CaseError as e:
        err.write("a case file is wrong: %s\n" % e)
        return 2
    except runner.RunError as e:
        err.write("%s\n" % e)
        return e.exit_code
    path = report.write_run(rec, Path(a.out) if a.out else DEFAULT_OUT, outputs)
    out.write("\n" + report.summary_table(rec) + "\nrun file: %s\n" % path)
    return 0


def main(argv: list[str] | None = None, *, stdout=None, stderr=None, transport=None, sleep=time.sleep, clock=time.monotonic) -> int:
    out, err = stdout or sys.stdout, stderr or sys.stderr
    if stdout is None and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    p = build_parser()
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    try:
        if a.command == "list":
            return cmd_list(a, out)
        if a.command == "run":
            return cmd_run(a, out, err, transport=transport, sleep=sleep, clock=clock)
        if a.command in ("compare", "show"):
            d = Path(a.out) if a.out else DEFAULT_OUT
            if a.command == "show":
                out.write(report.summary_table(report.load_run(a.run, d)))
            else:
                out.write(report.compare(report.load_run(a.a, d), report.load_run(a.b, d)))
            return 0
    except cases_mod.CaseError as e:
        err.write("a case file is wrong: %s\n" % e)
        return 2
    except (FileNotFoundError, ValueError) as e:
        err.write("%s\n" % e)
        return 2
    p.print_usage(err)
    return 2
