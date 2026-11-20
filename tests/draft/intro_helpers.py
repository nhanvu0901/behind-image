"""Shared by the tests of the new opening (worker introflow) in tests/draft, tests/state, tests/editor, tests/export and tests/cli: a timing built the way the
voice code builds it, the specs of a small video, a project folder, and the fixture `brand03`.

The registry may not know `ID-BRAND-03` yet (the renderer is built by another worker): `brand03` adds it for the test when it is missing (a copy of the entry
of `ID-BRAND-01` with the contract's two more texts, `title` and `subtitle`) and takes it away again; once the real entry exists it does nothing."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bti.draft.compile import compile_specs, summary_text
from bti.draft.inputs import load_inputs
from bti.engine import registry as R
from helpers import clean_spec, make_synth_project, shot, spec

CARD, CARD_LEN = 3.2, 2.8


def intro_timing(lead: float = 5.0, title: float = 10.2, spacing: float = 0.5) -> dict:
    """Three chapters of twenty words (a cold open, a chapter with the title and a card, a chapter with a card) as the voice code writes them."""
    words, chapters, beats = [], [], []
    prev_end = 0.0
    for k in range(3):
        first = lead if k == 0 else prev_end + (title + CARD if k == 1 else CARD)
        for j in range(20):
            s = round(first + spacing * j, 4)
            words.append({"w": "w%d" % len(words), "s": s, "e": round(s + 0.4, 4)})
        end = words[-1]["e"]
        c = {"id": "c%02d" % (k + 1), "name": ["COLD OPEN", "The mirror", "The room"][k], "start": 0.0 if k == 0 else prev_end, "end": end, "card": k > 0,
             "lead": {"kind": ["plain", "title", "card"][k], "start": 0.0 if k == 0 else prev_end, "end": first}}
        if k > 0:
            c["card_start"], c["card_end"] = round(first - CARD_LEN, 4), first
        if k == 1:
            c["title_start"], c["title_end"] = prev_end, round(prev_end + title, 4)
        chapters.append(c)
        prev_end = end
    for b in range(6):
        w0, w1 = b * 10, b * 10 + 10
        beats.append({"id": "b%04d" % (b + 1), "chapter": "c%02d" % (b // 2 + 1), "text": " ".join(w["w"] for w in words[w0:w1]),
                      "start": words[w0]["s"], "end": words[w1 - 1]["e"], "w0": w0, "w1": w1})
    chapters[-1]["end"] = round(words[-1]["e"] + 2.5, 4)
    return {"duration": round(words[-1]["e"] + 2.5, 4), "words": words, "beats": beats, "chapters": chapters}


SPECS = {
    "c01": spec("c01", shot("b0001", 0, "CAM-01"), shot("b0002", 10, "CAM-05", slots={"image": {"asset": "A", "region": "MIRROR"}})),
    "c02": spec("c02", shot("b0003", 20, "CAM-03"), shot("b0004", 30, "X-LAY-01", slots={"image": {"asset": "B"}})),
    "c03": spec("c03", shot("b0005", 40, "STATIC-01"), shot("b0006", 50, "CAM-01")),
}


def specs():
    return {c: clean_spec(s, c) for c, s in SPECS.items()}


def make_project(tmp_path: Path, timing: dict, name: str = "intro") -> Path:
    d = make_synth_project(tmp_path / "projects" / name)
    (d / "timing.json").write_text(json.dumps(timing), encoding="utf-8")
    return d


@pytest.fixture()
def brand03():
    b = R.load_bundle("gae")
    added = "ID-BRAND-03" not in b.by_id
    if added:
        base = copy.deepcopy(b.by_id["ID-BRAND-01"])
        base["id"], base["key"] = "ID-BRAND-03", "brand_raking_light_title"
        for n in ("title", "subtitle"):
            base["params"].append({"name": n, "type": "string", "default": "", "min": None, "max": None, "unit": None, "values": None, "measured": None})
        b.by_id["ID-BRAND-03"] = base
        b.techniques.append(base)
        R.RENDERERS["ID-BRAND-03"] = R.RENDERERS["ID-BRAND-01"]
    yield b
    if added:
        b.techniques.remove(base)
        del b.by_id["ID-BRAND-03"]
        del R.RENDERERS["ID-BRAND-03"]


def compiled(proj: Path, **kw):
    res = compile_specs(load_inputs(proj), specs(), draw=False, **kw)
    assert not res.errors, summary_text(res)
    return res


def style_doc():
    return R.load_bundle("gae").style
