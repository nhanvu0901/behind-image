import json
import tempfile
from pathlib import Path
import pytest

from bti.draft.inputs import load_inputs, resolve_edit_scope, clone_inputs
from bti.draft import decompile as D
from bti.engine import registry as R
from bti.draft.compile import compile_specs
from bti.draft.workspace import read_out

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "arnolfini_live"


def _run_identity_edit(inp0, scope):
    es, sc, words = resolve_edit_scope(inp0, scope)
    inp = clone_inputs(inp0, scope=sc, edit_shots=es)
    dec = D.decompile(inp, es)
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "out").mkdir()
        for c, v in dec.items():
            if c in inp.in_scope():
                (Path(td) / "out" / (c + ".json")).write_text(json.dumps(v["spec"]), encoding="utf-8")
        out = read_out(Path(td), inp.in_scope(), {**inp.picks["assets"], **((inp.current or {}).get("assets") or {})})
        res = compile_specs(inp, out.specs, regions=out.regions, spec_problems=out.problems, degrade=False, draw=False)
        return res.violations


@pytest.fixture(scope="module")
def arnolfini_inputs():
    assert (FIXTURE_DIR / "storyboard.json").is_file(), "storyboard.json fixture missing"
    assert (FIXTURE_DIR / "timing.json").is_file(), "timing.json fixture missing"
    return load_inputs(FIXTURE_DIR, None, for_edit=True)


def test_arnolfini_live_every_chapter_scope(arnolfini_inputs):
    """Every chapter scope in arnolfini-live has zero scope violations on unchanged specs (E0 blocker fix)."""
    inp0 = arnolfini_inputs
    chapters = inp0.chapter_ids()
    assert len(chapters) == 8
    for cid in chapters:
        viol = _run_identity_edit(inp0, {"chapter": cid})
        assert len(viol) == 0, f"Chapter {cid} had {len(viol)} violations: {[v['message'] for v in viol]}"


def test_arnolfini_live_every_single_shot_scope(arnolfini_inputs):
    """Every single-shot scope in arnolfini-live has zero scope violations on unchanged specs (E0 blocker fix)."""
    inp0 = arnolfini_inputs
    bundle = R.load_bundle(inp0.style)
    shots = [s["id"] for s in inp0.current["shots"] if not D.is_card(bundle, s)]
    assert len(shots) == 86
    for sid in shots:
        viol = _run_identity_edit(inp0, {"shots": [sid]})
        assert len(viol) == 0, f"Shot {sid} had {len(viol)} violations: {[v['message'] for v in viol]}"
