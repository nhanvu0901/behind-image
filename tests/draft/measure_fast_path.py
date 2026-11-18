"""Times the fast path's own work (everything except the model call) on a copy of a reference project with media.

    tools/deploy/snapshot_py.sh NAME tests/draft/measure_fast_path.py [project] [n_shots]

The model is the `mock` provider with a canned answer (the scope's shots echoed with a note changed). The project is copied to a
temp folder (nothing is written into projects/). Two rounds in one process: the first is cold (registry, images), the second is
what a running server sees. Prints: prompt, compile (includes its validate), validate, draw check, apply."""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti.draft import decompile as D                      # noqa: E402
from bti.draft import fastedit as F                       # noqa: E402
from bti.draft import merge as M                          # noqa: E402
from bti.draft.inputs import clone_inputs, load_inputs, resolve_edit_scope   # noqa: E402
from bti.engine import api as engine_api                  # noqa: E402
from bti.engine.scene import Scene                        # noqa: E402
from bti.script.providers import mock                     # noqa: E402

T: dict = {}


def timed(key, fn):
    def run(*a, **kw):
        t0 = time.perf_counter()
        try:
            return fn(*a, **kw)
        finally:
            T[key] = T.get(key, 0.0) + time.perf_counter() - t0
    return run


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "arnolfini"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    tmp = Path(tempfile.mkdtemp(prefix="bti-measure-"))
    dst = tmp / name
    try:
        shutil.copytree(REPO / "projects" / name, dst, ignore=shutil.ignore_patterns("cache", "history", "proposals", "renders", "exports", "*.mp4"))
        orig_complete = mock.complete
        F.prepare_prompt = timed("prompt", F.prepare_prompt)
        F.compile_specs = timed("compile_total", F.compile_specs)
        F._draw_check_changed_shots = timed("draw", F._draw_check_changed_shots)
        engine_api.Project.validate = timed("validate", engine_api.Project.validate)
        engine_api.Project._scene = timed("scene", engine_api.Project._scene)
        Scene.frame_at = timed("frames", Scene.frame_at)
        M.apply_direct_edit = timed("apply", M.apply_direct_edit)

        def model(*a, **kw):
            t0 = time.perf_counter()
            try:
                return orig_complete(*a, **kw)
            finally:
                T["model"] = time.perf_counter() - t0
        mock.complete = model

        mock.DELAY = 4.0                       # a model that thinks for 4 s: the warm-up runs inside that time
        for rnd in (1, 2):
            T.clear()
            inp0 = load_inputs(dst, for_edit=True)
            content = [s for d in D.decompile(inp0).values() for s in d["spec"]["shots"]]
            mid = len(content) // 2
            ids = [s["id"] for s in content[mid:mid + n]]
            es, sc, _ = resolve_edit_scope(inp0, {"shots": ids})
            if rnd == 1:
                print("project %s: %d shots in the storyboard, edit scope %s" % (name, len(inp0.current["shots"]), ids))
            shots = [copy.deepcopy(s) for s in content if s["id"] in set(ids)]
            for s in shots:
                s["note"] = "measured edit round %d" % rnd
            mock.set_canned([json.dumps({"result": "edit", "summary": "Đã đổi.", "shots": shots,
                                         "changes": [{"shot": s["id"], "what": "Đổi."} for s in shots]}, ensure_ascii=False)])
            inp = clone_inputs(inp0, scope=sc, edit_shots=es)
            t_all = time.perf_counter()
            res = F.fast_edit(inp, "đổi cảnh", model="mock", project_dir=dst)
            out = M.apply_direct_edit(dst, "t_measure%d" % rnd, base_sb=inp0.current, result_sb=res.storyboard,
                                      timing=inp0.timing, scope_shot_ids=es)
            total = time.perf_counter() - t_all - T.get("model", 0.0)
            print("--- round %d (%s): fast_edit %s, apply %s, %d changes" % (
                rnd, "cold process" if rnd == 1 else "warm process", res.status, out["status"], len(out["changes"])))
            for label, key in (("prompt building", "prompt"), ("compile (compile_specs, includes its validate)", "compile_total"),
                               ("  validate, all calls (compile + apply)", "validate"), ("draw check", "draw"),
                               ("  of it: scene compile, all calls", "scene"), ("  of it: frames, sum over threads", "frames"),
                               ("apply (merge, validate, save)", "apply")):
                print("%-48s %6.2f s" % (label, T.get(key, 0.0)))
            print("%-48s %6.2f s" % ("TOTAL without the model (mock %.2f s)" % T.get("model", 0.0), total))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
