"""Where does the time of a fast turn go, apart from the model? (worker c2box; replaces the script of the full-compile fast path.) Times each server step
of one turn of the prompt box on the fixture project of tests/ops with a canned answer (no model is called): the briefing, the dry run, the batch, the
undo. Run on the server through the snapshot helper:

    BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_py.sh c2box tests/draft/measure_fast_path.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO, REPO / "tests" / "ops", REPO / "tests" / "picks", REPO / "tests" / "script"):
    sys.path.insert(0, str(p))

from bti.draft import boxops as B, fastedit            # noqa: E402
from bti.draft.inputs import load_inputs               # noqa: E402
from ops_helpers import make_project                   # noqa: E402

OPS = [{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 260, "ry": 260}}]


def timed(label, fn, rows):
    t0 = time.time()
    out = fn()
    rows.append((label, time.time() - t0))
    return out


def main():
    tmp = Path(tempfile.mkdtemp(prefix="bti-measure-"))
    try:
        d = make_project(tmp / "p")
        be = B.Backend(d)
        for rnd in ("cold", "warm"):
            rows = []
            inp = timed("load the inputs", lambda: load_inputs(d, for_edit=True), rows)
            doc, rev = timed("read the storyboard", lambda: be.read("storyboard"), rows)
            facts = timed("the project's facts", lambda: be.adapter("storyboard").facts(doc), rows)
            scope = fastedit.storyboard_scope(inp, doc, {"shots": ["s0002"]})
            text = timed("the briefing", lambda: fastedit.build_briefing(inp, doc, facts, scope, "làm vòng sáng to hơn", []), rows)
            body = {"base_rev": rev, "actor": "agent:mock", "ops": OPS, "scope": scope.ops, "note": "x"}
            timed("dry run", lambda: be.run("storyboard", {**body, "dry_run": True}), rows)
            ans = timed("the batch (write and log)", lambda: be.run("storyboard", body), rows)
            _, rev2 = be.read("storyboard")
            timed("the undo of the batch", lambda: be.undo("storyboard", ans["batch"], {"base_rev": rev2, "actor": "human", "note": ""}), rows)
            print("--- %s: briefing %d characters" % (rnd, len(text)))
            for label, sec in rows:
                print("  %-28s %6.3f s" % (label, sec))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
