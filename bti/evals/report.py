"""What a run of the bench writes and what a person reads: one JSON file per run, a summary table (Markdown), and `compare` of two runs.

    <out>/<run id>.json            the whole record: the command, the app, the agent and model, the briefing's hash, and for every case and every repeat each
                                   criterion with its measured value, the time taken, any error, and where the outputs are kept
    <out>/<run id>/<case>-<n>.json the outputs of one repeat (the documents the criteria read)
    <out>/<run id>.md              the summary table

The summary: per case how many of the repeats passed EVERY criterion and which criterion failed most; at the end the totals. A repeat that was skipped (the sample or the app
cannot do the case yet) is shown as skipped, with its sentence, and is in no count of passes or failures.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

RUN_SCHEMA = "bti.eval.run/1"


def repeat_state(rep: dict) -> str:
    """passed | failed | skipped | error: `error` is a repeat the driver could not finish (a refused call, a job that did not end): its criteria are failed."""
    if rep.get("skipped"):
        return "skipped"
    return "passed" if rep.get("passed") else "failed"


def case_stats(case: dict) -> dict:
    reps = case.get("repeats") or []
    run = [r for r in reps if not r.get("skipped")]
    fails: Counter = Counter()
    checks = passed = 0
    for r in run:
        for c in r.get("criteria") or []:
            checks += 1
            if c.get("passed"):
                passed += 1
            else:
                fails[c["id"]] += 1
    seconds = [r["seconds"] for r in run if isinstance(r.get("seconds"), (int, float))]
    return {"repeats": len(reps), "ran": len(run), "skipped": len(reps) - len(run), "passed_repeats": sum(1 for r in run if r.get("passed")), "checks": checks, "checks_passed": passed,
            "fails": fails, "seconds": round(sum(seconds) / len(seconds), 1) if seconds else None, "errors": sum(1 for r in run if r.get("error"))}


def totals(run: dict) -> dict:
    cases = [case_stats(c) for c in run.get("cases") or []]
    return {"cases": len(cases), "repeats": sum(c["repeats"] for c in cases), "ran": sum(c["ran"] for c in cases), "skipped": sum(c["skipped"] for c in cases),
            "passed_repeats": sum(c["passed_repeats"] for c in cases), "checks": sum(c["checks"] for c in cases), "checks_passed": sum(c["checks_passed"] for c in cases)}


def summary_lines(run: dict) -> list[str]:
    """The lines printed at the end of a run (and the last lines of the Markdown)."""
    t = totals(run)
    lines = ["%d cases x repeats = %d runs: %d ran, %d skipped" % (t["cases"], t["repeats"], t["ran"], t["skipped"]),
             "repeats that passed every criterion: %d of %d%s" % (t["passed_repeats"], t["ran"], " (%.0f%%)" % (100 * t["passed_repeats"] / t["ran"]) if t["ran"] else ""),
             "criteria checks passed: %d of %d%s" % (t["checks_passed"], t["checks"], " (%.0f%%)" % (100 * t["checks_passed"] / t["checks"]) if t["checks"] else "")]
    if "sample_unchanged" in run:
        lines.append("the sample projects were %s" % ("not touched (byte for byte the same)" if run["sample_unchanged"] else "CHANGED: something wrote into a sample"))
    return lines


def _cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def summary_table(run: dict) -> str:
    """The Markdown summary: a header, the table (one row per case), the totals."""
    ag = run.get("agent") or {}
    cmd = run.get("command") or {}
    head = ["# Bench run %s" % run.get("run_id"), "",
            "step %s, agent %s (%s), %s repeats, briefing %s, app %s" % (cmd.get("step"), ag.get("id"), ag.get("model"), cmd.get("repeat"), (run.get("briefing") or {}).get("hash"), (run.get("app") or {}).get("url")), "",
            "| case | passed | criteria | failed most | seconds |", "|---|---|---|---|---|"]
    rows = []
    for c in run.get("cases") or []:
        s = case_stats(c)
        if s["ran"] == 0:
            reason = next((r.get("skipped") for r in c.get("repeats") or [] if r.get("skipped")), "")
            rows.append("| %s | skipped | - | %s | - |" % (c["name"], _cell(reason)))
            continue
        worst = ", ".join("%s (%dx)" % (k, v) for k, v in s["fails"].most_common(1)) or "-"
        rows.append("| %s | %d/%d%s | %d/%d | %s | %s |" % (c["name"], s["passed_repeats"], s["ran"], " (+%d skipped)" % s["skipped"] if s["skipped"] else "", s["checks_passed"], s["checks"], _cell(worst),
                                                         s["seconds"] if s["seconds"] is not None else "-"))
    return "\n".join(head + rows + ["", *["- " + x for x in summary_lines(run)], ""])


def write_run(run: dict, out_dir: Path | str, outputs: dict[str, Any] | None = None) -> Path:
    """Write the JSON record, the outputs and the Markdown summary; returns the path of the JSON file."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rid = run["run_id"]
    for name, data in (outputs or {}).items():
        f = out / rid / (name + ".json")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    p = out / (rid + ".json")
    p.write_text(json.dumps(run, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / (rid + ".md")).write_text(summary_table(run), encoding="utf-8")
    return p


def load_run(ref: str, out_dir: Path | str) -> dict:
    """A run by its path, or by its id inside `out_dir`."""
    p = Path(ref)
    if not p.is_file():
        p = Path(out_dir) / (ref if ref.endswith(".json") else ref + ".json")
    try:
        run = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise FileNotFoundError("no run file %s" % p)
    if not isinstance(run, dict) or run.get("schema") != RUN_SCHEMA:
        raise ValueError("%s is not a bench run file" % p)
    return run


def _rates(case: dict) -> dict[str, tuple[int, int]]:
    """criterion id -> (repeats that passed it, repeats that ran)."""
    out: dict[str, list[int]] = {}
    for r in case.get("repeats") or []:
        if r.get("skipped"):
            continue
        for c in r.get("criteria") or []:
            x = out.setdefault(c["id"], [0, 0])
            x[0] += 1 if c.get("passed") else 0
            x[1] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}


def compare(a: dict, b: dict) -> str:
    """What changed between two runs: the agent, the model, the briefing, and for every case the repeats that passed and every criterion whose rate moved."""
    lines = ["# Bench compare: %s -> %s" % (a.get("run_id"), b.get("run_id")), ""]
    for label, get in (("agent", lambda r: (r.get("agent") or {}).get("id")), ("model", lambda r: (r.get("agent") or {}).get("model")),
                       ("briefing", lambda r: (r.get("briefing") or {}).get("hash")), ("step", lambda r: (r.get("command") or {}).get("step")),
                       ("repeats", lambda r: (r.get("command") or {}).get("repeat"))):
        x, y = get(a), get(b)
        lines.append("- %s: %s" % (label, ("%s (unchanged)" % x) if x == y else "%s -> %s (CHANGED)" % (x, y)))
    ca, cb = {c["name"]: c for c in a.get("cases") or []}, {c["name"]: c for c in b.get("cases") or []}
    lines += ["", "| case | passed A | passed B | change | criteria that moved |", "|---|---|---|---|---|"]
    better = worse = 0
    for name in sorted(set(ca) | set(cb)):
        if name not in ca or name not in cb:
            lines.append("| %s | %s | %s | only in %s | |" % (name, "-" if name not in ca else "", "-" if name not in cb else "", "B" if name not in ca else "A"))
            continue
        sa, sb = case_stats(ca[name]), case_stats(cb[name])
        ra, rb = _rates(ca[name]), _rates(cb[name])
        moved = []
        for k in sorted(set(ra) | set(rb)):
            pa, pb = ra.get(k), rb.get(k)
            if pa is None or pb is None:
                moved.append("%s %s" % (k, "added" if pa is None else "removed"))
            elif pa[0] / max(pa[1], 1) != pb[0] / max(pb[1], 1):
                moved.append("%s %d/%d -> %d/%d" % (k, pa[0], pa[1], pb[0], pb[1]))
        da = sa["passed_repeats"] / sa["ran"] if sa["ran"] else None
        db = sb["passed_repeats"] / sb["ran"] if sb["ran"] else None
        change = "-" if da is None or db is None or da == db else ("better" if db > da else "WORSE")
        better += change == "better"
        worse += change == "WORSE"
        lines.append("| %s | %s | %s | %s | %s |" % (name, "%d/%d" % (sa["passed_repeats"], sa["ran"]) if sa["ran"] else "skipped", "%d/%d" % (sb["passed_repeats"], sb["ran"]) if sb["ran"] else "skipped",
                                                    change, _cell("; ".join(moved) or "-")))
    lines += ["", "- cases better: %d, worse: %d" % (better, worse)]
    for tag, r in (("A", a), ("B", b)):
        lines += ["- %s: %s" % (tag, "; ".join(summary_lines(r)[:3]))]
    return "\n".join(lines) + "\n"
