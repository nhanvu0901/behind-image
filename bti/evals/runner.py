"""A run of the bench: cases x repeats, each on its own COPY of the sample project, driven through the app's API like any agent, every criterion recorded.

    plan(...)       what the run is about to do and how much model work it asks for (printed before anything starts)
    run(...)        the run itself; returns the record (bti/evals/report.py writes it)

A run never touches a project of the owner: it copies a sample project of the samples root into the projects root of the app under the name `eval-<run>-<case>-<n>`,
points the copy's agent at the one asked for, asks the model through the routes a person's buttons call, reads the documents back, checks the criteria, and removes
the copy again through the app's own delete route (only copies it made itself; `--keep` leaves them). The sample itself is hashed before and after: the record says it did
not change.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from bti.cli.transport import Transport, Unreachable

from . import cases as cases_mod, criteria, driver, report, samples

REPO = Path(__file__).resolve().parents[2]
RUN_PREFIX = "eval-"

# the files a step's briefing is made of: their hash says whether the prompt changed between two runs
BRIEFINGS = {"outline": ["prompts/outline.md", "prompts/rules_format.md"],
             "narration": ["prompts/script.md", "prompts/rules_format.md", "prompts/rules_voice.md"],
             "draft": ["skills/storyboard_draft/TASK.template.md"],
             "edit_storyboard": ["skills/storyboard_edit/FAST.template.md", "skills/storyboard_draft/TASK.template.md"],
             "edit_picks": [], "picks_agent": []}


class RunError(Exception):
    """The run cannot start (the app does not answer, the agent is not there): one sentence, and the command's exit code."""

    def __init__(self, message: str, exit_code: int = 4):
        super().__init__(message)
        self.exit_code = exit_code


def briefing(step: str, root: Path | None = None) -> dict:
    root = Path(root) if root else REPO
    h, files, missing = hashlib.sha1(), [], []
    for rel in BRIEFINGS.get(step, []):
        f = root / rel
        if f.is_file():
            h.update(rel.encode("utf-8") + b"\0" + f.read_bytes() + b"\1")
            files.append(rel)
        else:
            missing.append(rel)
    return {"hash": ("sha1:" + h.hexdigest()[:12]) if files else "sha1:none", "files": files, "missing": missing}


def find_agent(t: Transport, agent_id: str) -> dict:
    """The agent `agent_id` of GET /api/agents, or a RunError that says which ones there are and why one cannot run."""
    try:
        r = t.request("GET", "/api/agents", None, 120.0)
    except Unreachable as e:
        raise RunError("the app cannot be reached: %s" % e, 6)
    if not r.ok or not isinstance(r.data, dict):
        raise RunError("GET /api/agents answered HTTP %s: is this the app?" % r.status, 6)
    agents = r.data.get("agents") or []
    a = next((x for x in agents if x.get("id") == agent_id), None)
    if a is None:
        raise RunError("the app has no agent %r (it has: %s)" % (agent_id, ", ".join(str(x.get("id")) for x in agents) or "none"), 2)
    if a.get("available") is False:
        raise RunError("the agent %s cannot run on this machine: %s" % (agent_id, a.get("reason") or "no reason given"), 3)
    return a


def plan(step: str, cs: list, repeat: int, agent: dict) -> list[str]:
    """The sentences printed before a run: how many runs, which agent, how much model work."""
    words, per = driver.COST[step]
    runs = len(cs) * repeat
    return ["bench: step %s, agent %s (%s)" % (step, agent.get("id"), agent.get("model")),
            "  %d cases x %d repeats = %d runs; each run asks the agent for: %s" % (len(cs), repeat, runs, words),
            "  that is at least %d agent run(s) in all (%d x %d); a failed answer may be asked again once" % (runs * per, runs, per),
            "  cases: " + ", ".join(c.name for c in cs)]


def new_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def _remove_copy(t: Transport, pid: str, created: set[str]) -> str | None:
    """Delete the copy through the app (only a project this run made). Returns a sentence when it could not be removed."""
    if pid not in created or not pid.startswith(RUN_PREFIX):
        return "refused to remove %s: this run did not make it" % pid
    try:
        r = t.request("DELETE", "/api/projects/%s?confirm=%s" % (quote(pid, safe=""), quote(pid, safe="")), None, 120.0)
    except Unreachable as e:
        return "the copy %s could not be removed: %s" % (pid, e)
    if r.ok:
        return None
    d = r.data if isinstance(r.data, dict) else {}
    return "the copy %s could not be removed: HTTP %s %s" % (pid, r.status, d.get("code") or "")


def run(*, step: str, agent_id: str, repeat: int, transport: Transport, case_names: list[str] | None = None, samples_root: Path | str, projects_root: Path | str,
        app_url: str = "", cases_root: Path | str | None = None, keep: bool = False, poll: float = 2.0, job_timeout: float = 3 * 3600.0,
        say: Callable[[str], None] = lambda s: None, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> tuple[dict, dict]:
    """Run the cases of `step` `repeat` times each with the agent `agent_id`. Returns (the run record, {output name: outputs of each repeat})."""
    cs = cases_mod.load_cases(step, case_names, cases_root)
    if not cs:
        raise RunError("there are no cases of step %s (python -m bti.evals list)" % step, 2)
    agent = find_agent(transport, agent_id)
    run_id = new_run_id()
    before = {c.sample["project"]: samples.tree_hash(Path(samples_root) / c.sample["project"]) for c in cs if (Path(samples_root) / c.sample["project"]).is_dir()}
    rec: dict[str, Any] = {"schema": report.RUN_SCHEMA, "run_id": run_id, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "ended": None,
                           "command": {"step": step, "agent": agent_id, "repeat": repeat, "cases": [c.name for c in cs]},
                           "app": {"url": app_url, "projects_root": str(projects_root), "samples_root": str(samples_root)},
                           "agent": {"id": agent.get("id"), "label": agent.get("label"), "model": agent.get("model")}, "briefing": briefing(step), "cases": []}
    outputs: dict[str, Any] = {}
    created: set[str] = set()
    for ci, case in enumerate(cs):
        crec: dict[str, Any] = {"name": case.name, "title": case.title, "step": case.step, "sample": case.sample, "repeats": []}
        rec["cases"].append(crec)
        for n in range(1, repeat + 1):
            pid = "%s%s-%d-%d" % (RUN_PREFIX, run_id[-4:], ci + 1, n)
            rep = _one(case, n, pid, agent_id, transport, samples_root, projects_root, created, keep, poll, job_timeout, sleep, clock, outputs, run_id)
            crec["repeats"].append(rep)
            say(_line(case.name, n, repeat, rep))
    rec["ended"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    after = {k: samples.tree_hash(Path(samples_root) / k) for k in before}
    rec["sample_unchanged"] = before == after
    rec["summary"] = report.totals(rec)
    return rec, outputs


def _line(name: str, n: int, of: int, rep: dict) -> str:
    if rep.get("skipped"):
        return "[%s %d/%d] skipped: %s" % (name, n, of, rep["skipped"])
    bad = [c["id"] for c in rep["criteria"] if not c["passed"]]
    return "[%s %d/%d] %s %d/%d%s %s s%s" % (name, n, of, "passed" if rep["passed"] else "FAILED", len(rep["criteria"]) - len(bad), len(rep["criteria"]), (" (failed: %s)" % ", ".join(bad)) if bad else "",
                                             rep["seconds"], (" - " + rep["error"]) if rep.get("error") else "")


def _one(case, n: int, pid: str, agent_id: str, t: Transport, samples_root, projects_root, created: set[str], keep: bool, poll: float, job_timeout: float, sleep, clock,
         outputs: dict, run_id: str) -> dict:
    """One repeat: copy, drive, check, clean up. Never raises: whatever goes wrong is in the record."""
    rep: dict[str, Any] = {"n": n, "project": pid, "seconds": None, "error": None, "skipped": None, "criteria": [], "passed": False, "agent": None, "cleanup": None, "model_calls": None}
    t0 = clock()
    outs: dict = {}
    try:
        samples.copy_project(samples_root, case.sample["project"], case.sample["start"], projects_root, pid)
        created.add(pid)
        samples.approve_through_the_app(t, pid, case.sample["start"])
        _set_agent(t, pid, agent_id)
        rep["agent"] = _effective(t, pid, case.step)
        sess = driver.Session(t, pid, case, poll=poll, job_timeout=job_timeout, sleep=sleep, clock=clock)
        try:
            outs = driver.DRIVERS[case.step](sess)
        finally:
            rep["jobs"] = sess.jobs
            rep["model_calls"] = len(sess.jobs)
        rep["error"] = outs.get("error")
    except (driver.Skipped, samples.SampleError) as e:
        rep["skipped"] = str(e)
    except driver.DriverError as e:
        rep["error"] = str(e)
    except Unreachable as e:
        rep["error"] = "the app cannot be reached: %s" % e
    except Exception as e:      # noqa: BLE001 - a bug in a driver is a failed repeat, never a lost run
        rep["error"] = "the driver failed: %s: %s" % (type(e).__name__, str(e)[:200])
    if not rep["skipped"]:
        rep["criteria"] = criteria.evaluate_all(case.criteria, outs)
        rep["passed"] = bool(rep["criteria"]) and all(c["passed"] for c in rep["criteria"]) and not rep["error"]       # a job that did not end well is not a pass, whatever the documents say
        name = "%s-%d" % (case.name, n)
        outputs[name] = {k: v for k, v in outs.items()}
        rep["outputs"] = "%s/%s.json" % (run_id, name)
    rep["seconds"] = round(clock() - t0, 1)
    if pid in created and not keep:
        rep["cleanup"] = _remove_copy(t, pid, created)
    return rep


def _set_agent(t: Transport, pid: str, agent_id: str) -> None:
    P = "/api/projects/%s/agent" % quote(pid, safe="")
    cur = t.request("GET", P, None, 60.0)
    if not cur.ok or not isinstance(cur.data, dict):
        raise driver.DriverError("the agent of the copy cannot be read", "HTTP %s" % cur.status)
    r = t.request("PUT", P, {"agent": agent_id, "base_rev": cur.data.get("rev")}, 60.0)
    if not r.ok:
        d = r.data if isinstance(r.data, dict) else {}
        raise driver.DriverError("the agent %s could not be chosen for the copy" % agent_id, "HTTP %s %s" % (r.status, d.get("code") or ""))


def _effective(t: Transport, pid: str, step: str) -> dict | None:
    r = t.request("GET", "/api/projects/%s/agent" % quote(pid, safe=""), None, 60.0)
    if not r.ok or not isinstance(r.data, dict):
        return None
    eff = r.data.get("effective") or {}
    group = {"outline": "script", "narration": "script", "draft": "storyboard", "edit_storyboard": "storyboard", "edit_picks": "picks", "picks_agent": "picks"}[step]
    return eff.get(group) or next(iter(eff.values()), None)
