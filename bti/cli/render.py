"""The plain text `bti` prints: short lines, no colours, nothing that needs a terminal. The command's own words are English; what the server says
(labels, details) stays in the server's Vietnamese. Every function takes the decoded JSON and returns a list of lines."""
from __future__ import annotations

import json
from typing import Any

GATES = ("outline", "narration", "picks", "storyboard")          # the same four as `bti.auto.GATES` (a test compares them)
STEP_WORD = {"done": "done", "current": "current", "locked": "locked"}


def compact(v: Any, limit: int = 600) -> str:
    s = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    return s if len(s) <= limit else s[: limit - 1] + "…"


def detail_text(detail: Any) -> str:
    """The `detail` of an error as one line (the framework's refusals send a list)."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for d in detail[:5]:
            if isinstance(d, dict):
                loc = ".".join(str(x) for x in d.get("loc", []) if x != "body") if isinstance(d.get("loc"), list) else ""
                parts.append((loc + ": " if loc else "") + str(d.get("msg", d)))
            else:
                parts.append(str(d))
        return "; ".join(parts)
    return "" if detail is None else compact(detail, 300)


# ---------------------------------------------------------------------------------------------------------------------- actions
def pct(v: Any) -> str:
    try:
        return "%d%%" % round(float(v) * 100)
    except (TypeError, ValueError):
        return "?"


def action_flags(a: dict) -> list[str]:
    """What an agent must know about one action before it calls it."""
    flags = []
    if a.get("advances"):
        flags.append("advances")
    if a.get("gate"):
        flags.append("gate: an agent may approve it" if a.get("auto_ok") else "gate: the owner approves it")
    cost = a.get("cost")
    if cost:
        flags.append("costs %s (%s)%s" % (cost.get("kind"), cost.get("about"), "; needs --yes-cost" if a.get("auto_ok") else "; the owner did not allow an agent to spend this"))
    if a.get("long_job"):
        flags.append("long job: add --wait")
    if a.get("fill"):
        flags.append("give: " + ", ".join(a["fill"]))
    ag = a.get("agent")
    if ag and not ag.get("usable"):
        flags.append("agent %s cannot run: %s" % (ag.get("label"), ag.get("reason")))
    return flags


def tags(a: dict) -> str:
    """The marks of an action in a compact list: (cost kind), (give), (needs)."""
    marks = []
    if (a.get("cost") or {}).get("kind"):
        marks.append(a["cost"]["kind"])
    if a.get("fill"):
        marks.append("give")
    if not a.get("ready"):
        marks.append("not ready")
    return " (%s)" % ", ".join(marks) if marks else ""


def action_line(a: dict, width: int) -> str:
    label = a.get("label") or ""
    flags = action_flags(a)
    line = "  %-*s %s" % (width, a["id"], label)
    return line + ("   [" + "; ".join(flags) + "]" if flags else "")


def command_for(project: str, a: dict) -> str | None:
    """The command that makes this action (None when an agent may not: the owner must)."""
    if a.get("gate"):
        return "bti approve %s %s" % (project, a["id"].split(".")[0]) if a.get("auto_ok") else None
    if a.get("cost") and not a.get("auto_ok"):
        return None
    parts = ["bti do %s %s" % (project, a["id"])]
    if a.get("fill") and a.get("body") is None:
        parts += ["--set %s=..." % f for f in a["fill"]]
    if a.get("cost"):
        parts.append("--yes-cost")
    if a.get("long_job"):
        parts.append("--wait")
    return " ".join(parts)


def next_line(st: dict) -> str:
    """The one next command: wait for a running job first, else the first action that is ready and advances the project."""
    project = st["project"]
    jobs = st.get("jobs") or []
    if jobs:
        return "next: bti job %s --wait   (a %s job is %s; never start a second long job on this project)" % (jobs[0]["id"], jobs[0]["kind"], jobs[0]["state"])
    problems = st.get("problems") or []
    for a in st.get("next_actions") or []:
        if a.get("ready") and a.get("advances"):
            cmd = command_for(project, a)
            if cmd:
                return "next: " + cmd + "   (" + (a.get("label") or a["id"]) + ")"
            if a.get("gate"):
                return "next: ask the owner to approve %s on the page (%s), or to turn automatic running on and allow this gate" % (a["id"].split(".")[0], a.get("label"))
            return "next: ask the owner: %s is a %s spend that an agent may not confirm" % (a["id"], (a.get("cost") or {}).get("kind"))
    if problems:
        return "next: repair the problem above (%s)" % problems[0].get("fix", problems[0].get("code"))
    cur = next((s for s in st.get("steps") or [] if s.get("step") == st.get("current")), None)
    if cur:
        return "next: the step %s waits for content: use an action marked `give` above" % cur["step"]
    return "next: nothing to do now"


def approvals_line(st: dict) -> str:
    ap = st.get("approvals") or {}
    parts = []
    for g in GATES:
        r = ap.get(g)
        if not r:
            parts.append("%s -" % g)
        else:
            parts.append("%s %s%s" % (g, r.get("by") or "(not recorded)", "" if r.get("stands") else " (no longer stands)"))
    return "approvals: " + "; ".join(parts)


def title_line(st: dict) -> str | None:
    """titlestep: the video's title as `bti status` shows it (None when the answer carries no `title`, an app of an earlier version)."""
    t = st.get("title")
    if not isinstance(t, dict):
        return None
    if not t.get("text"):
        return "title: none yet (title.generate has an agent write one once the narration is approved; title.set sets your own)"
    who = t.get("by") or "(not recorded)"
    more = "; the narration changed since an agent wrote it: title.generate writes it again" if t.get("stale") else ""
    return 'title: "%s" (%s, %s%s)' % (t["text"], who, t.get("state"), more)


def auto_line(st: dict) -> list[str]:
    auto = st.get("auto") or {}
    if not auto.get("enabled"):
        return ["automatic running: off (an agent approves no gate; the owner approves on the page or turns it on there)"]
    gates = [g for g in GATES if (auto.get("gates") or {}).get(g)]
    spend = [k for k, v in (auto.get("spend") or {}).items() if v and k != "paid"]
    return ["automatic running: on (an agent may approve: %s; may confirm: %s; paid never)" % (", ".join(gates) or "no gate", ", ".join(spend) or "no spend")]


def status_text(st: dict) -> list[str]:
    cur = next((s for s in st.get("steps") or [] if s.get("step") == st.get("current")), None)
    out = ["project: %s   stage: %s   current step: %s" % (st["project"], st.get("stage"), ("%s (%s)" % (cur["step"], cur.get("label"))) if cur else "none")]
    out += auto_line(st)
    out.append(approvals_line(st))
    if st.get("pipeline"):
        out.append("pipeline: %s" % st["pipeline"]["value"])
    tl = title_line(st)
    if tl:
        out.append(tl)
    out.append("steps:")
    for s in st.get("steps") or []:
        extra = " (blocked by %s)" % s["blocked_by"] if s.get("blocked_by") else ""
        out.append("  %-8s %-9s %s: %s%s" % (s.get("state"), s["step"], s.get("label"), s.get("detail") or "", extra))
    jobs = st.get("jobs") or []
    if jobs:
        out.append("jobs running:")
        for j in jobs:
            out.append("  %s  %s  %s %s   follow: bti job %s --wait" % (j["id"], j["kind"], j.get("state"), pct(j.get("progress")), j["id"]))
    else:
        out.append("jobs running: none")
    problems = st.get("problems") or []
    if problems:
        out.append("problems:")
        for p in problems:
            out.append("  %s (step %s): %s -> %s" % (p.get("code"), p.get("step"), p.get("detail"), p.get("fix")))
    warns = st.get("warnings") or []                    # outfolder: a problem with the output folder
    if warns:
        out.append("warnings:")
        for w in warns:
            out.append("  %s: %s" % (w.get("code"), w.get("sentence") or w.get("detail")))
    acts = st.get("next_actions") or []
    here = {x["step"] for x in st.get("steps") or [] if x.get("state") == "current"}
    main = [a for a in acts if a.get("step") in here or a.get("advances") or a.get("gate")]       # the work of the open steps, and every gate
    other = [a for a in acts if a not in main]
    ready, ahead = [a for a in main if a.get("ready")], [a for a in main if not a.get("ready")]
    width = max([len(a["id"]) for a in main] + [8])
    out.append("can do now:" if ready else "can do now: nothing")
    out += [action_line(a, width) for a in ready]
    if ahead:
        out.append("not ready yet:")
        for a in ahead:
            out.append(action_line(a, width) + "   needs: " + ", ".join(a.get("needs") or []))
    if other:
        out.append("also (other steps): " + ", ".join(a["id"] + tags(a) for a in other) + "   (bti status <project> --json has every field)")
    out.append(next_line(st))
    return out


def projects_text(rows: list) -> list[str]:
    if not rows:
        return ["no projects"]
    out = ["projects (bti status <project> for one):"]
    for r in rows:
        if not isinstance(r, dict):
            continue
        tail = "DAMAGED: " + str(r.get("data_error")) if r.get("data_error") else (r.get("title") or "")
        out.append("  %-24s %-12s %s" % (r.get("id"), r.get("stage") or "-", tail))
    return out


# ------------------------------------------------------------------------------------------------------------------------ results
def changes_lines(changes: list) -> list[str]:
    out = []
    for c in changes or []:
        if not isinstance(c, dict):
            continue
        out.append("  %s %s" % ((c.get("time") or "-").ljust(6), c.get("what") or compact(c, 120)))
    return out


def ops_text(res: dict, dry: bool) -> list[str]:
    head = "dry run: nothing was written" if dry else ("batch %s written" % res.get("batch") if res.get("batch") else "nothing changed (no batch)")
    out = ["%s; %s operation(s) applied; revision %s" % (head, res.get("applied"), res.get("rev"))]
    ch = changes_lines(res.get("changes"))
    out += ["changes:"] + ch if ch else ["changes: none"]
    issues = [i for i in res.get("issues") or [] if isinstance(i, dict) and i.get("level") == "error"]
    if issues:
        out.append("errors left in the document: %d (first: %s)" % (len(issues), issues[0].get("message")))
    created = res.get("created") or {}
    made = {k: v for k, v in created.items() if v}
    if made:
        out.append("created: " + compact(made, 300))
    if not dry and res.get("batch"):
        out.append("undo: bti undo <project> %s" % res["batch"])
    return out


def log_text(records: list) -> list[str]:
    if not records:
        return ["no changes in the log"]
    out = ["batch        doc         actor                 time                 note"]
    for r in records:
        out.append(("%-12s %-11s %-21s %-20s %s%s" % (r.get("batch"), r.get("doc"), str(r.get("actor"))[:21], str(r.get("time"))[:19],
                                                         (r.get("note") or "")[:40], "  (undone)" if r.get("undone_by") else ("  (undo of %s)" % r["undo_of"] if r.get("undo_of") else ""))).rstrip())
        for line in changes_lines(r.get("changes"))[:3]:
            out.append("    " + line.strip())
    return out


def schema_text(doc: str, part: dict) -> list[str]:
    out = ["operations of the %s (send them with: bti ops <project> %s --file ops.json):" % (doc, doc)]
    for name, o in part.items():
        required = ((o.get("schema") or {}).get("required") or [])
        out.append("  %s: %s" % (name, o.get("summary")))
        out.append("    required: %s" % (", ".join(r for r in required if r != "op") or "-"))
        out.append("    example: %s" % compact(o.get("example"), 400))
    out.append("(bti schema ops %s --json gives every JSON Schema)" % doc)
    return out


def job_line(job: dict) -> str:
    """One progress line of a job (a long job, a script job or a preview): changes only when something worth saying changed."""
    parts = ["job %s: %s %s" % (job.get("id", "?"), job.get("state"), pct(job.get("progress")))]
    running = next((p for p in job.get("parts") or [] if isinstance(p, dict) and p.get("state") == "running"), None)
    if running:
        parts.append("- %s%s" % (running.get("title") or running.get("key"), (" (%s)" % running["note"]) if running.get("note") else ""))
    else:
        ch = next((c for c in job.get("chapters") or [] if isinstance(c, dict) and c.get("state") in ("running", "retrying")), None)
        if ch:
            parts.append("- chapter %s %s" % (ch.get("id"), ch.get("state")))
        elif job.get("message"):
            parts.append("- %s" % job["message"])
    return " ".join(parts)


def job_end_lines(job: dict) -> list[str]:
    state = job.get("state")
    if state == "done":
        res = job.get("result")
        return ["done" + (": " + compact(res, 400) if res else "")]
    out = ["%s" % state]
    err = job.get("error")
    code = job.get("error_code") or job.get("error_kind")
    if err or code:
        out.append("  error%s: %s" % (" (%s)" % code if code else "", detail_text(err)))
    return out


# ---- outfolder: `bti output`
def output_lines(data: dict) -> list[str]:
    parts = data.get("parts") or {}
    out = ["output folder: %s   (%d file(s) written%s)" % (data.get("folder"), data.get("written") or 0, "; took the folder over from another project" if data.get("takeover") else "")]
    out.append("parts: " + (", ".join("%s%s" % (k, " (OUT OF DATE: %s)" % v.get("reason") if v.get("out_of_date") else "") for k, v in parts.items() if v.get("rev")) or "none yet"))
    cl = data.get("clean")
    if isinstance(cl, dict):
        if cl.get("done"):
            out.append("cleaned the working folder: freed %.1f MB in %d file(s)" % ((cl.get("freed_bytes") or 0) / 1048576.0, cl.get("files") or 0))
        else:
            out.append("did not clean the working folder: %s" % cl.get("reason"))
    for w in data.get("warnings") or []:
        out.append("warning %s: %s" % (w.get("code"), w.get("sentence") or w.get("detail")))
    return out
