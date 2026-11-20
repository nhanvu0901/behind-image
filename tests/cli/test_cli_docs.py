"""The documents an agent reads (AGENTS.md and skills/<step>/SKILL.md) never lie: their lists are generated from the code and a test fails when they are stale;
a command, an action id, an operation, an error code, a route, an exit code or a file that a document names must exist; and every worked session is
PLAYED against the app and must print what the document says (tests/cli/sessions.py)."""
import ast
import re
import shlex

import pytest

import sessions as S
from bti.cli import docgen, exitcodes as X, main as M, render as R
from cli_helpers import AppTransport, run_bti

REPO = docgen.REPO
STEPS = ("script", "voice", "picks", "storyboard", "export")
DOCS = ["AGENTS.md"] + ["skills/%s/SKILL.md" % s for s in STEPS] + ["skills/title/SKILL.md"]      # titlestep: the title has a skill of its own
SPAN = re.compile(r"`([^`\n]+)`")


def text(path):
    return (REPO / path).read_text(encoding="utf-8")


def spans(path):
    """Every inline code span and every line of a fenced block of a document (what a document 'names')."""
    out = []
    fenced = False
    for line in text(path).split("\n"):
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            out.append(line)
        else:
            out += SPAN.findall(line)
    return out


# --------------------------------------------------------------------------------------------------------------------- generated
def test_the_generated_parts_are_not_stale():
    assert docgen.main(["--check"]) == 0, "a document is stale: run `python -m bti.cli.docgen`"
    for path, parts in docgen.generated_parts().items():
        assert docgen.render(text(path), parts, path) == text(path), path


def test_every_document_has_exactly_the_generated_parts_the_generator_makes():
    for path, parts in docgen.generated_parts().items():
        begun = re.findall(r"<!-- BEGIN GENERATED: (\w+) -->", text(path))
        ended = re.findall(r"<!-- END GENERATED: (\w+) -->", text(path))
        assert begun == ended and set(begun) == set(parts), (path, begun, sorted(parts))


def test_there_is_one_skill_document_per_step_and_the_old_templates_are_untouched():
    for step in STEPS:
        assert (REPO / "skills" / step / "SKILL.md").is_file()
        assert text("skills/%s/SKILL.md" % step).startswith("---\nname: bti-%s\ndescription: " % step)
    assert (REPO / "skills" / "storyboard_draft" / "TASK.template.md").is_file() and (REPO / "skills" / "storyboard_edit" / "FAST.template.md").is_file()
    assert set(docgen.SKILL_OF.values()) == set(STEPS)


def test_agents_md_says_who_it_is_for_and_sends_a_developer_elsewhere():
    head = text("AGENTS.md")[:1200]
    assert "OPERATES a project" in head and "changing this repository's code" in head and "docs/AGENT_API.md" in head
    assert len(text("AGENTS.md").split("\n")) < 125                                # one page, with its tables


def test_the_tables_come_from_the_code():
    t = text("AGENTS.md")
    for name, usage, _ in M.COMMANDS:
        assert usage.replace("|", "\\|") in t, name
    for n, name, _, _ in X.EXIT_CODES:
        assert "| %d | `%s` |" % (n, name) in t
    from bti.editor import state_api
    for g in R.GATES:
        assert "| `%s` | `%s.approve` |" % (g, g) in t
    for step in STEPS:
        mine = {s.id for s in state_api.SPECS if docgen.SKILL_OF.get(s.step) == step}
        assert mine and all("| `%s` |" % i in text("skills/%s/SKILL.md" % step) for i in mine), step
    from bti.ops import registry
    for doc in ("picks", "storyboard"):
        assert all("| `%s` |" % n in text("skills/%s/SKILL.md" % doc) for n in registry.defs(doc)), doc
    reg = __import__("json").loads((REPO / "style" / "gae" / "techniques.json").read_text(encoding="utf-8"))["techniques"]
    sb = text("skills/storyboard/SKILL.md")
    assert all("`%s`" % t["id"] in sb for t in reg) and all("| %s |" % c in sb for c in {t["category"] for t in reg})


# ---------------------------------------------------------------------------------------------------------------- what they name
def command_spans(path):
    return [s for s in spans(path) if re.match(r"(\$ )?(tools/)?bti( |$)", s)]


def test_every_command_a_document_names_exists_and_every_concrete_one_parses():
    names = {n for n, _, _ in M.COMMANDS}
    assert names == set(M.HANDLERS) and names == {c for c in M.build_parser()._subparsers._group_actions[0].choices}
    seen = 0
    for path in DOCS:
        for sp in command_spans(path):
            words = sp.replace("$ ", "", 1).split()
            words = words[1:] if words[0] == "bti" else words[1:]                     # drop `bti` or `tools/bti`
            if not words or words[0].startswith(("-", "<")):
                continue
            seen += 1
            if len(words) == 1:                                                               # a bare mention of a command
                assert words[0] in names, "%s names the command `%s`" % (path, sp)
                continue
            assert words[0] in names or words[0] == "...", "%s names the command `%s`" % (path, sp)
            if not re.search(r"[<>\[\]|]|\.\.\.", sp):                                    # a concrete line: it must parse
                try:
                    M.build_parser().parse_args(shlex.split(" ".join(words)))
                except M.UsageError as e:
                    raise AssertionError("%s: `%s` does not parse: %s" % (path, sp, e))
    assert seen > 40


ACTION = re.compile(r"[a-z]+\.[a-z_]+")
FILE_EXT = {"json", "md", "html", "txt", "py", "m4a", "mp4", "tgz", "bat", "sh", "js", "mjs", "css", "template"}


def test_every_action_id_a_document_names_exists():
    from bti.editor import state_api
    resources = {s.id.split(".")[0] for s in state_api.SPECS}
    named = 0
    for path in DOCS:
        for sp in spans(path):
            for tok in re.findall(r"[a-z]+\.[a-z_]+", re.sub(r"[A-Za-z0-9_/{}.-]*/[A-Za-z0-9_/{}.-]*", " ", sp)):       # a path is not an action
                head, _, tail = tok.partition(".")
                if head in resources and tail not in FILE_EXT:
                    named += 1
                    assert tok in state_api.SPEC, "%s names the action `%s`, which does not exist" % (path, tok)
    assert named > 60


def test_every_route_a_document_names_exists():
    from state_helpers import route_ok
    import tempfile
    from bti.editor.app import create_app
    app = create_app(projects_root=tempfile.mkdtemp(), engine_module=None, media_module=None)
    bad, named = [], 0
    for path in DOCS:
        for m in re.finditer(r"\b(GET|POST|PUT|DELETE) (/api/[A-Za-z0-9_/{}.-]+)", text(path)):
            p = re.sub(r"\{[^}]*\}", "x", m.group(2).rstrip(".,"))
            named += 1
            if not route_ok(app, m.group(1), p):
                bad.append((path, m.group(1), m.group(2)))
    assert named > 10 and not bad, bad


def test_every_exit_code_a_document_names_exists():
    valid = {str(n) for n, *_ in X.EXIT_CODES}
    named = 0
    for path in DOCS:
        for m in re.finditer(r"\b[Ee]xit(?: code)? (\d)\b|^\(exit (\d)\)$", text(path), re.M):
            named += 1
            assert (m.group(1) or m.group(2)) in valid, (path, m.group(0))
    assert named > 12


def test_every_file_a_document_names_exists():
    named = 0
    for path in DOCS:
        for sp in spans(path):
            if re.fullmatch(r"(docs|skills|tools|bti|config|style)/[A-Za-z0-9_./-]+\.\w+", sp) and not re.search(r"[<>{}]", sp):
                named += 1
                assert (REPO / sp).is_file(), "%s names the file `%s`" % (path, sp)
    assert named > 10


def cli_codes():
    """The codes `bti` makes itself: `ctx.fail(<exit>, "<code>", ...)` and `fail(...)` calls in bti/cli/main.py."""
    out = set()
    for n in ast.walk(ast.parse((REPO / "bti" / "cli" / "main.py").read_text(encoding="utf-8"))):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", None)) == "fail" and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant):
            out.add(n.args[1].value)
    return out


def vocabulary():
    """Every word a document may put in code ticks as a field, a code or a name: the app's own documents, tables and registries."""
    from bti.editor import hints, state_api
    from bti.ops import registry
    words = set(hints.HINTS) | set(state_api.NEEDS) | cli_codes() | set(X.PERSON_CODES) | set(X.NAME_OF.values()) | {x.id for x in state_api.SPECS}
    for doc in ("picks", "storyboard"):
        words |= set(registry.defs(doc))
    for d in ("docs/AGENT_API.md", "docs/OPS.md", "docs/APP_GUIDE.md"):
        words |= set(SPAN.findall(text(d)))
    for h in hints.HINTS.values():
        words |= set(SPAN.findall(h["fix"]))
    import json
    for t in json.loads((REPO / "style" / "gae" / "techniques.json").read_text(encoding="utf-8"))["techniques"]:
        words |= {t["id"]} | {p["name"] for p in t["params"]} | {s["name"] for s in t["slots"]}
    # the narration's own operations (bti/script/ops.py `apply_op`)
    words |= {"split", "merge", "drop", "insert", "move", "drop_chapter", "add_chapter", "order_like_outline"}
    return words


# words that are real but are written in the documents only (a command's own options, fields of a body, notes of the app's page)
EXTRA_WORDS = {"error_kind", "transition_in"}      # a field of a job record that fails (bti/script/runner.py) and of a shot (the draft's briefing)


def test_every_name_in_code_ticks_is_a_word_the_app_has():
    known = vocabulary() | EXTRA_WORDS
    unknown = {}
    for path in DOCS:
        for sp in spans(path):
            for tok in re.findall(r"(?<![\w$./-])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?![\w/-])", re.sub(r"https?://\S+|[A-Za-z0-9_.]*/[A-Za-z0-9_/{}.-]*", " ", sp)):
                if tok not in known and not re.fullmatch(r"batch_\d+", tok):
                    unknown.setdefault(tok, path)
    assert not unknown, "words in code ticks that the app does not have: %s" % unknown


def test_the_refusals_tables_name_error_codes_with_the_exit_the_command_gives():
    """In the `refusals you will meet` tables a code followed by (exit N) must really give that exit (by the hint table's retry word)."""
    from bti.editor import hints
    checked = 0
    for path in DOCS[1:]:
        for m in re.finditer(r"^\| ((?:`[a-z_]+`(?:, )?)+)(?: \(exit (\d)\))? \|", text(path), re.M):
            codes = re.findall(r"`([a-z_]+)`", m.group(1))
            if not m.group(2):
                continue
            want = int(m.group(2))
            for c in codes:
                h = hints.HINTS.get(c)
                if h is None:
                    continue
                got = X.exit_for_error(409, {"code": c, "retry": h["retry"]})
                checked += 1
                assert got == want, "%s says `%s` is exit %d, the table of the command gives %d" % (path, c, want, got)
    assert checked > 10


# ------------------------------------------------------------------------------------------------------------------ the sessions
def session_params():
    out = []
    for path in DOCS:
        for i, block in enumerate(S.blocks(text(path))):
            out.append(pytest.param(path, i, block, id="%s#%d" % (path, i)))
    return out


def test_every_skill_document_has_a_worked_session_and_agents_md_has_none_needed():
    for path in DOCS[1:]:
        assert len(S.blocks(text(path))) == 1, path
        sess = S.parse(S.blocks(text(path))[0])
        assert sess["fixture"] and sum(1 for s in sess["steps"] if s[0] == "cmd") >= 3, path


@pytest.mark.parametrize("path, i, block", session_params())
def test_the_worked_session_prints_what_the_document_says(path, i, block, root, make_client, monkeypatch, tmp_path):
    sess = S.parse(block)
    played = S.play(sess, root, make_client, monkeypatch, tmp_path, lambda client, argv: run_bti(AppTransport(client), *argv))
    cmds = [s for s in sess["steps"] if s[0] == "cmd"]
    assert len(played) == len(cmds)
    for (cmd, code, lines), step in zip(played, cmds):
        assert cmd == step[1]
        assert code == step[3], "%s: `%s` exited %d, the document says %d\n%s" % (path, cmd, code, step[3], "\n".join(lines))
        why = S.matches(step[2], lines)
        assert why is None, "%s: `%s`: %s\n--- the real output:\n%s" % (path, cmd, why, "\n".join(S.volatile(l) for l in lines))


def test_the_session_matcher():
    assert S.matches(["a", "...", "z"], ["a", "x", "y", "z"]) is None and S.matches(["a", "...", "z"], ["a", "z"]) is None
    assert S.matches(["a", "b"], ["a", "c"]) and S.matches(["a"], ["a", "b"]) and S.matches(["a", "b"], ["a"])
    assert S.matches(["job <job>: done <any>"], ["job 0123456789abcdef: done 100%"]) is None
    assert S.matches(["rev <rev>"], ["rev 12"]) is not None
    assert S.transcribe([("bti x", 3, ["rev " + "a" * 40, "job 0123456789abcdef", "2026-11-19T10:11:12"])]) == "$ bti x\nrev <rev>\njob <job>\n<time>\n(exit 3)"
