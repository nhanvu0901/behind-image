"""The worked sessions of the documents (AGENTS.md, skills/<step>/SKILL.md): a fenced block in this form,

    # fixture: book narration_approved          <- which fixture project the session runs on
    # owner: auto on                            <- something the owner does on the page between two commands (auto on | approve <gate>)
    $ bti status arn                            <- a command
    project: arn   stage: script ...            <- its output, stdout then stderr
    ...                                         <- any number of lines
    (exit 3)                                    <- the exit code when it is not 0
    $ cat > ops.json <<'EOF'                    <- a file the next commands read
    [...]
    EOF

is PLAYED against the app of the tests, and every output line must match: `<job>`, `<rev>`, `<time>` and `<any>` stand for the parts that differ from
run to run. `transcribe` makes such a block from a list of commands (used to write a document, and by the test of the documents to show what the real
output is). Nothing here starts a model, a voice or a render: the starters are the stood-in ones of conftest.py, which start a quick real long job."""
from __future__ import annotations

import json
import re
from pathlib import Path

PLACEHOLDERS = {"<job>": r"[0-9a-f]{16}", "<rev>": r"[0-9a-f]{40,64}", "<time>": r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", "<any>": r".*"}
VOLATILE = [(re.compile(r"\b[0-9a-f]{40,64}\b"), "<rev>"), (re.compile(r"\b[0-9a-f]{16}\b"), "<job>"), (re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d"), "<time>")]
FENCE = re.compile(r"```text\n(# fixture: .*?)```", re.S)


def blocks(text: str) -> list[str]:
    """The worked sessions of a document (each starts with a `# fixture:` line)."""
    return [m.group(1) for m in FENCE.finditer(text)]


def parse(block: str) -> dict:
    """{fixture, steps: [("owner", text) | ("file", name, content) | ("cmd", argv-string, [expected lines], exit)]}."""
    fixture, steps, cur = None, [], None
    lines = block.rstrip("\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# fixture:"):
            fixture = line.split(":", 1)[1].strip()
        elif line.startswith("# owner:"):
            steps.append(("owner", line.split(":", 1)[1].strip()))
            cur = None
        elif line.startswith("# "):
            pass                                                                    # a comment for the reader
        elif line.startswith("$ cat > "):
            name = line.split()[3]
            body = []
            i += 1
            while lines[i] != "EOF":
                body.append(lines[i])
                i += 1
            steps.append(("file", name, "\n".join(body) + "\n"))
            cur = None
        elif line.startswith("$ "):
            cur = ("cmd", line[2:], [], 0)
            steps.append(cur)
        elif cur is not None:
            m = re.fullmatch(r"\(exit (\d)\)", line)
            if m:
                steps[-1] = cur = ("cmd", cur[1], cur[2], int(m.group(1)))
            else:
                cur[2].append(line)
        i += 1
    return {"fixture": fixture, "steps": steps}


def pattern(expected: str) -> re.Pattern:
    out, i = "", 0
    while i < len(expected):
        for ph, rx in PLACEHOLDERS.items():
            if expected.startswith(ph, i):
                out += rx
                i += len(ph)
                break
        else:
            out += re.escape(expected[i])
            i += 1
    return re.compile(out)


def matches(expected: list[str], actual: list[str]) -> str | None:
    """None when `actual` fits `expected` (a line `...` takes any number of lines); else a sentence about the first difference."""
    pats = [None if e == "..." else pattern(e) for e in expected]

    def go(i: int, j: int) -> bool:
        while i < len(pats):
            if pats[i] is None:
                return any(go(i + 1, k) for k in range(j, len(actual) + 1))
            if j >= len(actual) or not pats[i].fullmatch(actual[j]):
                return False
            i, j = i + 1, j + 1
        return j == len(actual)
    if go(0, 0):
        return None
    for k, p in enumerate(pats):
        if p is None:
            return "after `...` the output does not fit %r (it has %d lines)" % (expected[k + 1:k + 3], len(actual))
        if k >= len(actual) or not p.fullmatch(actual[k]):
            return "line %d: expected %r, got %r" % (k + 1, expected[k], actual[k] if k < len(actual) else "(no more output)")
    return "the output has %d more line(s): %r" % (len(actual) - len(pats), actual[len(pats):][:3])


def volatile(line: str) -> str:
    for rx, ph in VOLATILE:
        line = rx.sub(ph, line)
    return line


# --------------------------------------------------------------------------------------------------------------- the fixtures
def quick_job(kind: str):
    """A starter that starts a REAL long job of the app's runner that ends at once (the real voice, draft and export take an hour, 20 and 25 minutes)."""
    from bti.longjob import Part, manager

    def start(*a, **k):                      # the three starters differ: voice (dir, pid), draft (pid, dir), export (dir)
        pdir = next(x for x in a if isinstance(x, Path))
        pid = next((x for x in a if isinstance(x, str)), pdir.name)

        def run(ctx):
            ctx.progress(0.5, "đang chạy")
            return {"fixture": kind}
        return manager.start(kind, pid, pdir, [Part(key="p1", title="Phần 1", run=run)])
    return start


def quick_title_job():
    """titlestep: a starter that stands in for the title agent: a REAL long job (kind `title`) that ends at once and writes the title document the way the real one does (the real
    agent takes about a minute and its candidates differ)."""
    from bti.longjob import Part, manager as mgr
    from bti.title import store as T
    cands = [{"text": "The Saint Who Was Also an Advertisement", "form": "contradiction", "lines": ["b0001"], "why": "Một vị thánh và một tấm biển quảng cáo: hai thứ trái ngược mà đều đúng.",
              "scores": {"curiosity": 5, "concrete": 5, "central": 5, "clear": 4}},
             {"text": "Why Is a Saint Weighing a Ring?", "form": "question", "lines": ["b0001"], "why": "Câu hỏi mà người lạ chưa thể trả lời.",
              "scores": {"curiosity": 4, "concrete": 5, "central": 5, "clear": 5}}]

    def start(pid, pdir, *, note=None, model=None, actor=None, by_run=False, **kw):
        def run(ctx):
            ctx.progress(0.5, "đang chạy")
            doc = T.write_generated(pdir, cands, by="agent:mock", narration_rev_=T.narration_rev(pdir), written={"model": "mock", "note": note, "requested_by": actor})
            return {"title": doc["chosen"]["text"], "candidates": len(cands), "sentence": "Agent đã viết %d tựa và chọn: \"%s\"." % (len(cands), doc["chosen"]["text"])}
        return mgr.start("title", pid, pdir, [Part(key="title", title="Viết tựa video", run=run)], {"action": "generate", "model": "mock", "agent": None, "requested_by": actor})
    return start


def make_fixture(name: str, root: Path, make_client, monkeypatch):
    """-> (client, project id) for a fixture named in a session."""
    import bti.draft.run as draft_run
    import bti.export.run as export_run
    import bti.title.job as title_job
    import bti.voice.run as voice_run
    from state_helpers import build, make_book_project
    monkeypatch.setattr(voice_run, "start", quick_job("voice"))
    monkeypatch.setattr(draft_run, "start", quick_job("draft"))
    monkeypatch.setattr(export_run, "start", quick_job("export"))
    monkeypatch.setattr(title_job, "start", quick_title_job())                       # titlestep
    kind, _, arg = name.partition(" ")
    if kind == "book":
        stage, *flags = arg.split()
        c = make_client()
        make_book_project(root)
        build(stage, c, monkeypatch)
        if "title" in flags:                                                           # titlestep: the title agent (a test double) is switched on for this session
            import json as _json
            import os
            f = Path(os.environ["BTI_AGENTS_FILE"])
            f.write_text(_json.dumps({**_json.loads(f.read_text(encoding="utf-8")), "script.title": "mock"}), encoding="utf-8")
        return c, "arn"
    if kind == "ops":
        import pytest
        pytest.importorskip("bti.engine.api")
        from bti.engine import api as engine_api
        from ops_helpers import PID, make_project
        make_project(root)
        return make_client(engine_module=engine_api), PID
    raise ValueError("unknown fixture %r" % name)


def owner(client, pid: str, what: str) -> None:
    """Something the owner does on the page, as the page does it (no actor)."""
    P = "/api/projects/%s" % pid
    if what == "auto on":
        rev = client.get(P + "/auto").json()["rev"]
        assert client.put(P + "/auto", json={"base_rev": rev, "enabled": True}).status_code == 200
    elif what.startswith("approve "):
        gate = what.split()[1]
        rev = {"outline": lambda: client.get(P + "/outline").json()["rev"], "narration": lambda: client.get(P + "/narration").json()["rev"],
               "picks": lambda: client.get(P + "/picks").json()["rev"], "storyboard": lambda: client.get(P).json()["rev"]}[gate]()
        route = {"outline": "/outline/approve", "narration": "/narration/approve", "picks": "/picks/approve", "storyboard": "/approve"}[gate]
        r = client.post(P + route, json={"rev": rev})
        assert r.status_code == 200, r.text
    else:
        raise ValueError("unknown owner action %r" % what)


def play(session: dict, root: Path, make_client, monkeypatch, workdir: Path, run) -> list[tuple[str, int, list[str]]]:
    """Run the steps; -> [(command, exit code, output lines)] for every command. `run(client, argv)` runs one `bti` command."""
    import shlex
    client, pid = make_fixture(session["fixture"], root, make_client, monkeypatch)
    monkeypatch.chdir(workdir)
    played = []
    for step in session["steps"]:
        if step[0] == "owner":
            owner(client, pid, step[1])
        elif step[0] == "file":
            (workdir / step[1]).write_text(step[2], encoding="utf-8")
        else:
            argv = shlex.split(step[1])
            assert argv[0] == "bti", step[1]
            res = run(client, argv[1:])
            played.append((step[1], res.code, (res.out + res.err).rstrip("\n").split("\n") if (res.out + res.err).strip() else []))
    return played


def transcribe(played: list[tuple[str, int, list[str]]]) -> str:
    """The text of a session as the document prints it (volatile parts as placeholders)."""
    out = []
    for cmd, code, lines in played:
        out.append("$ " + cmd)
        out += [volatile(l) for l in lines]
        if code:
            out.append("(exit %d)" % code)
    return "\n".join(out)
