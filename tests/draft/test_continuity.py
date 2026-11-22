import json

from bti.draft.compile import compile_specs
from bti.draft.inputs import load_inputs
from helpers import clean_spec, shot, spec


def pose(key):
    return tuple(key[k] for k in ("cx", "cy", "zoom"))


def test_repeated_region_holds_previous_stored_frame(proj):
    path = proj / "picks.json"
    picks = json.loads(path.read_text(encoding="utf-8"))
    picks["assets"]["A"]["regions"].update({
        "WOMAN_BUST": {"x": 360, "y": 650, "rx": 180, "ry": 220},
        "WOMAN_HEAD": {"x": 400, "y": 400, "rx": 90, "ry": 100},
    })
    path.write_text(json.dumps(picks), encoding="utf-8")
    slots = {"image": {"asset": "A", "region": "WOMAN_HEAD"}}
    specs = {"c01": clean_spec(spec("c01",
        shot("b0001", 0, "CAM-05", slots=slots, **{"from": "WOMAN_BUST"}),
        shot("b0002", 10, "CAM-05", slots=slots, **{"from": "WOMAN_BUST"}),
    ), "c01")}
    result = compile_specs(load_inputs(proj), specs, draw=False, identity=False)
    shots = [s for s in result.storyboard["shots"] if s.get("source") == "agent" and s.get("technique") == "CAM-05"]
    first, second = [s["params"]["camera"] for s in shots[:2]]
    assert pose(second[0]) == pose(first[-1])
    assert pose(second[-1]) == pose(first[-1])


def test_small_step_starts_at_previous_frame():
    from bti.draft.camera import build_main_camera
    asset = {"width": 3840, "height": 5253, "regions": {
        "START": {"x": 1920, "y": 2600, "rx": 500, "ry": 500},
        "TARGET": {"x": 2300, "y": 2200, "rx": 200, "ry": 200},
    }}
    previous = (1930.0, 2600.0, 0.68)
    keys = build_main_camera("CAM-05", "TARGET", "START", asset, None, previous, 0, 10)
    assert pose(keys[0]) == previous
