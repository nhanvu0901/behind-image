import os
from pathlib import Path

import pytest

from bti.engine import registry as R
from conftest import REPO


def test_all_techniques_available_and_have_previews_on_disk():
    b = R.load_bundle("gae")
    assert len(b.techniques) == 82 and all(b.available(t["id"]) for t in b.techniques)
    for t in b.techniques:
        pv = t.get("preview")
        assert pv, t["id"]
        assert (REPO / "style/gae" / pv["clip"]).stat().st_size > 1000 and (REPO / "style/gae" / pv["thumb"]).stat().st_size > 1000, t["id"]


def test_every_engine_impl_imports():
    import importlib
    for t in R.load_bundle("gae").techniques:
        mod, cls = t["engine"]["impl"].rsplit(".", 1)
        assert hasattr(importlib.import_module(mod), cls), t["id"]


def test_style_json_has_the_ported_constants():
    s = R.load_bundle("gae").style
    for sec, keys in {"diagram": ["label_size_px", "label_tracking"], "shorts": ["panel_w_px", "ambient_blur_sigma", "ambient_darken"], "matte": ["benchmark_painting_width_px"]}.items():
        for k in keys:
            assert "value" in s[sec][k] and s[sec][k]["source"]


@pytest.mark.skipif(not (REPO / "projects/technique_lab/storyboard.json").exists(), reason="showcase not built")
def test_technique_lab_covers_every_technique_and_renders():
    import cv2
    from bti.engine.api import open_project
    p = open_project(REPO / "projects/technique_lab")
    assert [i for i in p.validate() if i["level"] == "error"] == []
    rs = p.resolve()
    ids = [s["note"].split()[0] for s in rs["shots"]]
    assert ids == [t["id"] for t in R.load_bundle("gae").techniques if not t["id"].startswith(("ID-", "MAP-", "KEY-", "NUM-", "DOC-"))]     # the lab predates the ID and MAP families and the overlays KEY, NUM, DOC (tests/engine/test_identity.py, test_map.py, test_explain_over.py)
    for s in rs["shots"][::7]:                                  # a sample keeps the suite fast; the build script checks all 71
        g = cv2.cvtColor(p.frame_at(s["_t0"] + 1.0, 320), cv2.COLOR_BGR2GRAY)
        assert g.std() > 0 or s["technique"].startswith("X-CARD"), s["id"]
