"""How long is the model's answer for "four of twelve shots change": the old contract (the whole replacement list) against the delta.

    tools/deploy/snapshot_py.sh NAME tests/draft/measure_answer_size.py [project]

Characters of compact JSON (what a model writes) and the prompt size; then the delta answer is run through `fast_edit` with the mock to
show it applies. Nothing is written into projects/ (a temp copy)."""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti.draft import decompile as D                                   # noqa: E402
from bti.draft import fastedit as F                                    # noqa: E402
from bti.draft.inputs import clone_inputs, load_inputs, resolve_edit_scope   # noqa: E402
from bti.script.providers import mock                                  # noqa: E402

HELPERS = ("in_scope", "locked", "start_s", "end_s", "beat_text", "duration_s")


def compact(o) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "arnolfini"
    tmp = Path(tempfile.mkdtemp(prefix="bti-size-"))
    dst = tmp / name
    try:
        shutil.copytree(REPO / "projects" / name, dst, ignore=shutil.ignore_patterns("cache", "history", "proposals", "renders", "exports", "*.mp4"))
        inp0 = load_inputs(dst, for_edit=True)
        content = [s for d in D.decompile(inp0).values() for s in d["spec"]["shots"]]
        mid = len(content) // 2 - 6
        scope = content[mid:mid + 12]
        ids = [s["id"] for s in scope]
        es, sc, _ = resolve_edit_scope(inp0, {"shots": ids})
        inp = clone_inputs(inp0, scope=sc, edit_shots=es)
        changed_ids = [ids[1], ids[4], ids[7], ids[10]]

        def whole(s):
            c = copy.deepcopy(s)
            for k in HELPERS:
                c.pop(k, None)
            if s["id"] in changed_ids:
                c["note"] = "changed"
            return c
        changes = [{"shot": i, "what": "Máy quay đi chậm hơn ở cảnh này."} for i in changed_ids]
        old = {"result": "edit", "summary": "Máy quay đi chậm hơn ở bốn cảnh.", "shots": [whole(s) for s in scope], "regions": [], "changes": changes}
        new = {"result": "edit", "summary": "Máy quay đi chậm hơn ở bốn cảnh.", "shots": [whole(s) for s in scope if s["id"] in changed_ids],
               "remove": [], "regions": [], "changes": changes}
        o, n = len(compact(old)), len(compact(new))
        print("project %s: scope of %d shots, %d change" % (name, len(scope), len(changed_ids)))
        print("answer, whole replacement list (old contract): %6d characters" % o)
        print("answer, only the changed shots (new contract): %6d characters  (%.0f%% of the old)" % (n, 100.0 * n / o))
        print("prompt (new template): %d characters" % len(F.prepare_prompt(inp, "làm chậm máy quay")))
        mock.set_canned([json.dumps(new, ensure_ascii=False)])
        res = F.fast_edit(inp, "làm chậm máy quay", model="mock", project_dir=dst)
        print("fast_edit with the delta answer:", res.status, res.issues[:2])
        if res.storyboard:
            cur = {s["id"]: s for s in inp0.current["shots"]}
            diff = [s["id"] for s in res.storyboard["shots"] if s["id"] in cur and json.dumps(s, sort_keys=True) != json.dumps(cur[s["id"]], sort_keys=True)]
            print("shots that differ from the saved ones:", len(diff), "(expected %d)" % len(changed_ids))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
