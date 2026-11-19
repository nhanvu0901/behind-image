"""R2U-002: every issue the engine's validate emits carries a stable `code` and an `args` dict, and the code is listed in
`bti.engine.storyboard.ISSUE_CODES`."""
from __future__ import annotations

import ast
import copy
from pathlib import Path

from bti.engine import storyboard as SB

ENGINE = Path(SB.__file__).parent


def _codes_in_source():
    """All literal codes passed to err()/warn() in storyboard.py and to _P() in registry.py (static scan, so rare branches count)."""
    found = set()
    for fname, funcs, pos in (("storyboard.py", ("err", "warn"), 2), ("registry.py", ("_P",), 0)):
        tree = ast.parse((ENGINE / fname).read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in funcs and len(n.args) > pos \
                    and isinstance(n.args[pos], ast.Constant):
                found.add(n.args[pos].value)
    return found


def test_every_code_in_the_source_is_documented():
    missing = _codes_in_source() - set(SB.ISSUE_CODES)
    assert not missing, missing


def _map_codes():
    """The `map_*` codes MAP-01 returns from its `check_params` (a hook of the registry check, so they are not in the two files scanned above)."""
    import re
    tree = ast.parse((ENGINE / "techniques" / "maps.py").read_text())
    return {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch(r"map_[a-z_]+", n.value)}


def _explain_codes():
    """The codes KEY-01 / DOC-01 return from `check_base` and `check_params` (hooks of the registry and of validate, so they are not in the two files scanned above)."""
    import re
    tree = ast.parse((ENGINE / "techniques" / "explain_over.py").read_text())
    return {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch(r"(doc_[a-z_]+|overlay_needs_camera)", n.value)}


def test_documented_codes_are_all_used():
    used = _codes_in_source() | _map_codes() | _explain_codes() | {"undrawable", "incomplete", "not_an_object", "unreadable_structure", "style_unusable", "timing_unusable",
                                 "params_not_object", "unknown_param"}
    assert set(SB.ISSUE_CODES) - used == set()


def _broken(base):
    docs = {}

    def mk(name, f):
        d = copy.deepcopy(base)
        f(d)
        docs[name] = d
    mk("schema", lambda d: d.update(schema="x"))
    mk("canvas", lambda d: d.update(canvas=5))
    mk("fps", lambda d: d["canvas"].update(fps=0))
    mk("title", lambda d: d.update(title=3))
    mk("assets", lambda d: d.update(assets=[]))
    mk("asset_kind", lambda d: d["assets"]["A"].update(kind="x"))
    mk("asset_file", lambda d: d["assets"]["A"].update(file="../x.jpg"))
    mk("asset_missing", lambda d: d["assets"]["A"].update(file="media/none.jpg"))
    mk("region", lambda d: d["assets"]["A"]["regions"].update(BAD={"x": "a"}))
    mk("audio", lambda d: d.update(audio=""))
    mk("no_shots", lambda d: d.update(shots=[]))
    mk("shots_list", lambda d: d.update(shots={}))
    mk("end", lambda d: d.update(end=None))
    mk("locked", lambda d: d["shots"][0].update(locked="yes"))
    mk("start_neg", lambda d: d["shots"][0].update(start={"t": -3.0}))
    mk("dup_id", lambda d: d["shots"][1].update(id="s1"))
    mk("tech", lambda d: d["shots"][0].update(technique="NOPE-1"))
    mk("tech_kind", lambda d: d["shots"][0].update(technique="HI-01"))
    mk("param_unknown", lambda d: d["shots"][1]["params"].update(zzz=1))
    mk("param_type", lambda d: d["shots"][1]["params"].update(title=5))
    mk("slot", lambda d: d["shots"][0]["slots"].update(nope={"asset": "A"}))
    mk("slot_asset", lambda d: d["shots"][0]["slots"].update(image={"asset": "Q"}))
    mk("ov_outside", lambda d: d["shots"][0]["overlays"][0].update(start={"t": 15.0}))
    mk("ov_region", lambda d: d["shots"][0]["overlays"][0]["params"].update(at="NOPE"))
    mk("ov_dur", lambda d: d["shots"][0]["overlays"][0].update(dur=-1))
    mk("tr_dur", lambda d: d["shots"][2]["transition_in"].update(dur=-1))
    mk("tr_tech", lambda d: d["shots"][2]["transition_in"].update(technique="HI-01"))
    mk("cam_ease", lambda d: d["shots"][0]["params"]["camera"][0].update(ease="zzz"))
    mk("cam_rel", lambda d: d["shots"][0]["params"]["camera"][1].update(at={"rel": 7}))
    mk("cam_zoom", lambda d: d["shots"][0]["params"]["camera"][0].update(zoom=1e9))
    mk("anchor", lambda d: d["shots"][1].update(start={"w": 9999, "off": 0}))
    mk("order", lambda d: d["shots"][2].update(start={"t": 1.0}))
    mk("overlays", lambda d: d["shots"][0].update(overlays=5))
    mk("not_dict", lambda d: d["shots"].append(5))
    mk("intent", lambda d: d["shots"][0].update(intent=4))
    mk("source", lambda d: d["shots"][0].update(source="alien"))
    return docs


def test_validate_emits_a_known_code_and_args_on_every_issue(tiny_project):
    base = tiny_project.storyboard()
    assert all(i["code"] in SB.ISSUE_CODES and isinstance(i["args"], dict) for i in tiny_project.validate())
    docs = _broken(base)
    docs["not_a_dict"] = []
    docs["top_string"] = "x"
    seen = 0
    for name, doc in docs.items():
        for i in tiny_project.validate(doc):
            seen += 1
            assert i.get("code"), (name, i)
            assert i["code"] in SB.ISSUE_CODES, (name, i)
            assert isinstance(i.get("args"), dict), (name, i)
    assert seen > len(docs)


def test_style_and_timing_problems_have_codes(tiny_project):
    base = tiny_project.storyboard()
    for key, val in (("style", "nope"), ("timing", "../x.json")):
        d = copy.deepcopy(base)
        d[key] = val
        iss = tiny_project.validate(d)
        assert iss and all(i["code"] in SB.ISSUE_CODES for i in iss), iss


# R3U-003: an issue about an asset or its file names the asset key; an issue about one camera key names its index
ASSET_CODES = ("asset_not_object", "asset_kind", "asset_file_required", "asset_file_outside_project", "asset_file_missing",
               "asset_file_unreadable", "credit_not_object", "asset_size", "regions_not_object", "region_xy", "region_radius",
               "asset_undefined", "slot_asset_kind", "region_undefined")


def test_asset_issues_carry_the_asset_key(tiny_project):
    base = tiny_project.storyboard()
    key = next(iter(base["assets"]))
    docs = _broken(base)
    d = copy.deepcopy(base)
    a = d["assets"][key]
    a.update(kind="x", credit=3, width=-1, regions=5)
    docs["many"] = d
    d2 = copy.deepcopy(base)
    d2["assets"][key]["regions"] = {"R": {"x": 1, "y": 2, "rx": -1}, "S": {"x": "a"}}
    docs["regions"] = d2
    d3 = copy.deepcopy(base)
    d3["assets"][key]["file"] = None
    docs["nofile"] = d3
    seen = set()
    for name, doc in docs.items():
        for i in tiny_project.validate(doc):
            if i["code"] in ASSET_CODES:
                seen.add(i["code"])
                assert isinstance(i["args"].get("asset"), str) and i["args"]["asset"], (name, i)
    assert {"asset_kind", "asset_file_missing", "asset_file_outside_project", "region_xy", "asset_undefined", "asset_size",
            "regions_not_object", "credit_not_object", "region_radius", "asset_file_required"} <= seen, seen


def test_camera_issues_carry_the_key_index(tiny_project):
    docs = _broken(tiny_project.storyboard())
    for name in ("cam_ease", "cam_rel"):
        found = [i for i in tiny_project.validate(docs[name]) if i["code"] in ("unknown_ease", "camera_rel_range", "camera_keys_order")]
        assert found and all(isinstance(i["args"].get("index"), int) and i["args"].get("param") for i in found), (name, found)
