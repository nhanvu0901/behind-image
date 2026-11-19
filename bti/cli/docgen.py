"""The lists inside the documents an agent reads, generated from the code: `AGENTS.md` (the commands, the exit codes and how the server's answers map to them,
the gates) and `skills/<step>/SKILL.md` (the actions of the step, the operations, the technique catalogue's headings).

    python -m bti.cli.docgen             rewrite the generated parts of the documents
    python -m bti.cli.docgen --check     exit 1 when a generated part is stale (tests/cli/test_docs.py runs it)
    python -m bti.cli.docgen --print F   print the fresh text of document F (nothing is written)

A generated part sits between `<!-- BEGIN GENERATED: name -->` and `<!-- END GENERATED: name -->`; everything else is written by hand.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import exitcodes as X
from . import main as M

REPO = Path(__file__).resolve().parents[2]
BEGIN = "<!-- BEGIN GENERATED: {name} -->"
END = "<!-- END GENERATED: {name} -->"

# step id of the pipeline (`steps[].step`, `Spec.step`) -> the folder of its skill document
SKILL_OF = {"script": "script", "voice": "voice", "picks": "picks", "edit": "storyboard", "export": "export"}
# what a gate lets happen, from the design table (docs/design/2026-11-18-agent-first-design.html, "Cổng duyệt và chạy tự động")
AFTER_GATE = {"outline": "writing the narration (a few minutes of a model)", "narration": "the voice (about an hour of machine time)",
              "picks": "the storyboard draft (about 20 minutes of a model)", "storyboard": "the export (about 25 minutes of machine time)"}


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


# ------------------------------------------------------------------------------------------------------------------------ the parts
def commands_table() -> str:
    rows = ["| command | what it does |", "|---|---|"]
    for _name, usage, summary in M.COMMANDS:
        rows.append("| `%s` | %s |" % (_cell(usage), _cell(summary)))
    rows += ["", "Options of every command (before or after the sub-command):", "", "| option | meaning |", "|---|---|"]
    for opt, text in M.COMMON_OPTIONS:
        rows.append("| `%s` | %s |" % (opt, _cell(text)))
    return "\n".join(rows)


def exit_codes_table() -> str:
    rows = ["| exit code | name | meaning | what to do |", "|---|---|---|---|"]
    for n, name, meaning, todo in X.EXIT_CODES:
        rows.append("| %d | `%s` | %s | %s |" % (n, name, _cell(meaning), _cell(todo)))
    return "\n".join(rows)


def exit_mapping_table() -> str:
    rows = ["| rule (the first that matches wins) | exit code |", "|---|---|"]
    for label, code in X.MAPPING:
        rows.append("| %s | %d (`%s`) |" % (_cell(label), code, X.NAME_OF[code]))
    rows += ["", "A job that ends (`bti do ... --wait`, `bti job ... --wait`) maps like this: `done` is 0; `cancelled` and `interrupted` are 5; `error` goes by the job's "
             "`error_code` through the same rules (a code in the person list is 3, a code whose `retry` is `later` is 5, any other is 4); a script job has an "
             "`error_kind` instead: " + ", ".join("`%s` %d" % (k, v) for k, v in sorted(X.JOB_KIND_EXIT.items(), key=lambda kv: (kv[1], kv[0]))) + "."]
    return "\n".join(rows)


def gates_table() -> str:
    from bti import auto
    from bti.editor import state_api
    rows = ["| gate | action id | route | what follows it | who approves it |", "|---|---|---|---|---|"]
    for g in auto.GATES:
        spec = state_api.SPEC[g + ".approve"]
        rows.append("| `%s` | `%s` | `%s %s` | %s | the owner on the page; an agent only when the owner turned automatic running on for the project and allowed this gate "
                    "(`auto` of `bti status`) |" % (g, spec.id, spec.method, spec.path, AFTER_GATE[g]))
    return "\n".join(rows)


def _actions_rows(specs) -> list[str]:
    rows = ["| id | step | page button | gate | cost | long job |", "|---|---|---|---|---|---|"]
    for s in specs:
        rows.append("| `%s` | %s | %s | %s | %s | %s |" % (s.id, s.step, _cell(s.label), "yes" if s.gate else "", _cell("%s: %s" % s.cost) if s.cost else "",
                                                          "yes" if s.long_job else ""))
    return rows


def actions_table(step: str | None = None) -> str:
    """Every action id (or those of one pipeline step), from the catalogue of the state answer."""
    from bti.editor import state_api
    specs = [s for s in state_api.SPECS if step is None or s.step == step]
    return "\n".join(_actions_rows(specs))


def ops_table(doc: str) -> str:
    from bti.ops import registry
    rows = ["| operation | what it does |", "|---|---|"]
    for name, o in registry.defs(doc).items():
        rows.append("| `%s` | %s |" % (name, _cell(o.summary)))
    return "\n".join(rows)


def techniques_table() -> str:
    """The catalogue of the registry under its headings (the `category` of each technique), with the id and the name of each."""
    reg = json.loads((REPO / "style" / "gae" / "techniques.json").read_text(encoding="utf-8"))["techniques"]
    cats: dict[str, list[dict]] = {}
    for t in reg:
        cats.setdefault(t["category"], []).append(t)
    rows = ["| heading | techniques (id, name) |", "|---|---|"]
    for cat in sorted(cats):
        rows.append("| %s | %s |" % (cat, "; ".join("`%s` %s" % (t["id"], _cell(t["name"])) for t in sorted(cats[cat], key=lambda t: t["id"]))))
    rows.append("")
    rows.append("%d techniques in %d headings; `bti` does not list their parameters: GET /api/styles/{style} does, and `bti schema ops storyboard` shows how `set_technique` and `set_params` take them." % (len(reg), len(cats)))
    return "\n".join(rows)


def generated_parts() -> dict[str, dict[str, str]]:
    """document (path from the repository root) -> {part name: markdown}."""
    out: dict[str, dict[str, str]] = {"AGENTS.md": {"commands": commands_table(), "exit_codes": exit_codes_table(), "exit_mapping": exit_mapping_table(),
                                                    "gates": gates_table()}}
    for step, folder in SKILL_OF.items():
        parts = {"actions": actions_table(step)}
        if folder == "picks":
            parts["ops"] = ops_table("picks")
        if folder == "storyboard":
            parts["ops"] = ops_table("storyboard")
            parts["techniques"] = techniques_table()
        out["skills/%s/SKILL.md" % folder] = parts
    return out


def render(text: str, parts: dict[str, str], path: str = "") -> str:
    """`text` with each generated part replaced between its markers; a marker that is missing is an error."""
    for name, body in parts.items():
        b, e = BEGIN.format(name=name), END.format(name=name)
        i, j = text.find(b), text.find(e)
        if i < 0 or j < i:
            raise ValueError("%s has no %s ... %s block" % (path or "the document", b, e))
        text = text[:i + len(b)] + "\n" + body + "\n" + text[j:]
    return text


def fresh(path: str, parts: dict[str, str] | None = None) -> str:
    text = (REPO / path).read_text(encoding="utf-8")
    return render(text, parts if parts is not None else generated_parts()[path], path)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    all_parts = generated_parts()
    if "--print" in argv:
        path = argv[argv.index("--print") + 1]
        sys.stdout.buffer.write(fresh(path, all_parts[path]).encode("utf-8"))
        return 0
    stale = []
    for path, parts in all_parts.items():
        f = REPO / path
        if not f.is_file():
            stale.append(path + " (missing)")
            continue
        text = f.read_text(encoding="utf-8")
        new = render(text, parts, path)
        if new != text:
            stale.append(path)
            if "--check" not in argv:
                f.write_text(new, encoding="utf-8")
    if "--check" in argv:
        if stale:
            print("stale: %s: run `python -m bti.cli.docgen`" % ", ".join(stale), file=sys.stderr)
            return 1
        return 0
    print("updated: " + ", ".join(stale) if stale else "the documents are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
