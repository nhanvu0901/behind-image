import json

import pytest

from bti.engine import registry as R
from bti.engine.api import load_style
from conftest import REPO


def available_ids(project):
    return [t["id"] for t in project.bundle.techniques if project.bundle.available(t["id"])]


def test_every_available_technique_has_valid_default_params(arnolfini):
    ids = available_ids(arnolfini)
    assert len(ids) >= 20
    ctx = {"asset": "A", "region": "MIRROR", "focus": "MIRROR", "text": "A LABEL"}
    for tid in ids:
        spec = arnolfini.bundle.spec(tid)
        params = arnolfini.default_params(tid, ctx)
        assert isinstance(params, dict), tid
        issues = R.validate_params(spec, params, tid)
        assert [i for i in issues if i["level"] == "error"] == [], (tid, issues)
        # no required parameter may be left empty
        for p in spec["params"]:
            if p.get("required"):
                assert params.get(p["name"]) is not None, (tid, p["name"])


def test_default_params_without_context_still_validate(arnolfini):
    for tid in available_ids(arnolfini):
        spec = arnolfini.bundle.spec(tid)
        params = arnolfini.default_params(tid, {})
        errs = [i for i in R.validate_params(spec, params, tid) if i["level"] == "error"]
        # required point/size params cannot be known without context; everything else must be fine
        errs = [i for i in errs if "required parameter" not in i["message"]]
        assert errs == [], (tid, errs)


def test_camera_defaults_use_the_asset_and_style_presets(arnolfini):
    for tid in ("CAM-01", "CAM-03", "CAM-04", "CAM-05", "STATIC-01", "X-LAY-01"):
        p = arnolfini.default_params(tid, {"asset": "A"})
        keys = p["camera"]
        assert len(keys) == 2 and keys[0]["at"] == {"rel": 0.0} and keys[1]["at"] == {"rel": 1.0}
        assert all(k["zoom"] > 0 for k in keys)
    push = arnolfini.default_params("CAM-01", {"asset": "A"})["camera"]
    assert push[1]["zoom"] / push[0]["zoom"] == pytest.approx(1.142, rel=1e-3)           # style.json camera_presets.excerpt_push_in
    back = arnolfini.default_params("CAM-03", {"asset": "A"})["camera"]
    assert back[0]["zoom"] / back[1]["zoom"] == pytest.approx(1.312, rel=1e-3)
    pan = arnolfini.default_params("CAM-04", {"asset": "A"})["camera"]
    assert pan[0]["cy"] > pan[1]["cy"]                                                  # pan up: the view moves up the image


def test_camera_default_focuses_on_a_region(arnolfini):
    p = arnolfini.default_params("CAM-05", {"asset": "A", "focus": "MIRROR"})["camera"]
    assert (p[1]["cx"], p[1]["cy"]) == (2220, 1790)


def test_overlay_defaults_take_region_and_style(arnolfini):
    sp = arnolfini.default_params("HI-01", {"asset": "A", "region": "MIRROR"})
    assert sp["at"] == "MIRROR" and sp["rx"] == 440 and sp["floor"] == 0.2
    ring = arnolfini.default_params("AN-01", {"asset": "A", "region": "DOG"})
    assert ring["at"] == "DOG" and ring["radius"] > 0 and ring["hold_s"] == 2.0
    lab = arnolfini.default_params("X-ANN-02", {"asset": "V"})
    assert lab["title"] == "Virgin and Child with Canon van der Paele" and lab["artist_year"] == "Jan van Eyck, 1434" and lab["case"] == "upper"
    assert lab["strip_y_top_pct"] == 79.4
    card = arnolfini.default_params("X-CARD-01", {"title": "the room"})
    assert card["title"] == "THE ROOM" and card["text_leave_at_s"] == 1.7


def test_default_params_for_unavailable_technique_are_registry_defaults(arnolfini, monkeypatch):
    spec = arnolfini.bundle.spec("CMP-01")
    monkeypatch.setitem(spec["engine"], "available", False)                              # synthetic unavailable entry
    assert arnolfini.default_params("CMP-01", {}) == {p["name"]: p["default"] for p in spec["params"]}
    with pytest.raises(KeyError):
        arnolfini.default_params("NOPE-01", {})


def test_registry_file_is_valid_and_consistent():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO / "style/gae/techniques.schema.json").read_text())
    reg = json.loads((REPO / "style/gae/techniques.json").read_text())
    jsonschema.validate(reg, schema)
    assert len(reg["techniques"]) == 86
    assert all("available" in t["engine"] for t in reg["techniques"])
    b = R.load_bundle("gae")
    from bti.engine import techniques  # noqa: F401
    assert R.check_registry(b) == []
    for t in reg["techniques"]:                                  # every available technique's declared defaults pass their own checks
        if t["engine"]["available"]:
            for p in t["params"]:
                if p["default"] is not None:
                    assert R.check_value(p, p["default"]) is None, (t["id"], p["name"])


def test_load_style_shape():
    s = load_style("gae")
    assert set(s) == {"style", "techniques", "intents"} and len(s["techniques"]) == 86 and "point_at" in s["intents"]


def test_ring_default_radius_is_relative_to_the_visible_frame(arnolfini):
    whole = arnolfini.default_params("AN-01", {"asset": "A"})["radius"]
    assert 0 < whole < 4386 * 0.15                                   # was 1307 px of a 4386 px wide picture: covered everything
    close = arnolfini.default_params("AN-01", {"asset": "A", "camera": {"zoom": 1.0}})["radius"]
    assert close == pytest.approx(0.234 * 1920 / 2, rel=0.02)
    assert arnolfini.default_params("AN-01", {"asset": "A", "region": "DOG"})["radius"] == pytest.approx(379.5)


def test_norm_folds_accents():
    from bti.engine.timing import norm, Timing
    assert norm("Dürer,") == "durer" and norm("Velázquez") == "velazquez" and norm("it's") == "its"
    tm = Timing({"duration": 1, "words": [{"w": "Dürer", "s": 0, "e": 1}, {"w": "Durer", "s": 1, "e": 2}]})
    assert tm.stale({"w": 0, "text": "Durer"}) is None and tm.stale({"w": 0, "text": "Dorer"})


def test_ring_radius_covers_tall_region(arnolfini):
    asset = arnolfini._saved['assets']['A']
    asset['regions']['TALL_TEST'] = {'x': 1000, 'y': 1000, 'rx': 16, 'ry': 80}
    assert arnolfini.default_params('AN-01', {'asset': 'A', 'region': 'TALL_TEST', 'camera': {'zoom': 1.0}})['radius'] == pytest.approx(92)
