"""R2B-012, permanent form: whatever `validate` accepts without an error, the engine can draw.

For every one of the 82 techniques (taken from its reference configuration in `projects/technique_lab`; the ID-*, TIME-01, TREE-01, STATE-01 and MAP-01 ones from `identity_lab.py`) and for every
parameter of every one of the thirteen registry types (number, enum, bool, string, text, color, point, points, lines, box, camera,
asset, items), the parameter is replaced one at a time by a set of odd values: wrong but well typed, extreme, empty, degenerate.
The draft is validated; when validate reports no error the frame in the middle of the item MUST be drawn (no exception, and
a failure of the engine would also have to be a `RenderError`, never a bare exception).  Every value validate refuses is
simply skipped.  A value the engine cannot draw is a hole in the registry (a missing `pattern`, `min_items`, range...).

Run:  .venv-engine/bin/python -m pytest tests/engine/test_validate_draw_sweep.py -q         (about 4 minutes; marked slow)
      .venv-engine/bin/python -m pytest tests/engine -q -m "not slow"                       (everything else, skips it)
"""
from __future__ import annotations

import copy
import json
import shutil
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from bti.engine.api import open_project  # noqa: E402
from bti.engine import registry as R  # noqa: E402
from bti.engine.errors import RenderError  # noqa: E402

# Safety net for a shared machine (R2B-017): while a sweep test runs, a background thread ends the whole process when it has grown
# by more than 2 GB (peak resident size), because one huge allocation never returns to Python in time for an exception to help.
MEMORY_GROWTH_LIMIT = 2 * 1024 ** 3
CURRENT = None


def _maxrss() -> int:
    if os.name == "nt":                                          # no `resource` module there: the peak working set, in bytes
        import ctypes
        from ctypes import wintypes

        class _PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = _PMC()
        pmc.cb = ctypes.sizeof(_PMC)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
        k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return int(pmc.PeakWorkingSetSize)
    import resource
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r if sys.platform == "darwin" else r * 1024          # bytes on macOS, kilobytes on Linux


@pytest.fixture(autouse=True)
def memory_watchdog():
    import os
    import threading
    import time
    base, stop = _maxrss(), threading.Event()

    def watch():
        while not stop.is_set():
            if _maxrss() - base > MEMORY_GROWTH_LIMIT:
                sys.stderr.write("\nSWEEP WATCHDOG: memory grew by more than 2 GB; last mutation: %r\n" % (CURRENT,))
                sys.stderr.flush()
                os._exit(3)
            time.sleep(0.02)
    th = threading.Thread(target=watch, daemon=True)
    th.start()
    yield
    stop.set()


pytestmark = pytest.mark.slow

LAB = REPO / "projects" / "technique_lab"
TYPES = {"number", "enum", "bool", "string", "text", "color", "point", "points", "lines", "box", "camera", "asset", "items"}


def _bundle():
    return R.load_bundle("gae")


def odd_values(p: dict, ref, asset_keys: list, region: str | None):
    """Values to try for param definition `p`; `ref` is the reference configuration's value (or the default)."""
    t = p["type"]
    vals: list = [None]
    if t == "number":
        vals += ["x", True, 0, -1, 1, 0.5, 10 ** 6, 1e-9, -1e9, 1e9, float("nan"), float("inf")]
        # just outside the declared range (must be refused). The range edges themselves are NOT probed: two in-range pixel
        # values can still overflow the canvas together (panel width + x offset); that case is the job of RenderError and
        # of `draw_check` at approval, not of a per-parameter range.
        if p.get("min") is not None:
            vals.append(p["min"] - 1e-3)
        if p.get("max") is not None:
            vals.append(p["max"] + 1e-3)
    elif t == "enum":
        vals += ["x", ""] + list(p.get("values") or []) + [1, True]
    elif t == "bool":
        vals += [True, False, "yes", 0, 1]
    elif t in ("string", "text"):
        vals += ["", " ", "x", "#zzz", "a\nb", "0", "-1", "1,2,3", "1,2", "1x1", "0x0", "0x2", "2x0", "-1x2", "999x999", "9x9", "a|b|c", "|", "||",
                 ",", ",,", "1e999", "nan", "inf", "-5", "1:0", "0:1", "9:16", "16:9", "x:y", "1:1:1", "é" * 3, "x" * 300, 5, ["a"]]
    elif t == "color":
        vals += ["", "red", "#zzz", "#12345", "#1234567", "#aabbcc\n", "aabbcc", "#AABBCC", 5]
    elif t == "point":
        vals += ["", "x", "nope", [0, 0], [-1e6, 1e6], [1e12, 1e12], [0.5, 0.5], [1, 2, 3], ["a", "b"], [float("nan"), 0], 5]
        if region:
            vals.append(region)
    elif t == "points":
        vals += [[], [[0, 0]], [[0.5, 0.5]] * 2, [[0, 0]] * 4, [[0, 0], [1, 1], [2, 2], [3, 3]], [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
                 [[1e9, 1e9]] * 4, [[0.5, 0.5]] * 40, [[1, 2, 3]], ["x"], "x", [[0, 0]] * 3, [[0, 0]] * 5, [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]]
        if region:
            vals.append([region])
    elif t == "lines":
        vals += [[], [""], ["x"], ["a|b"], ["a | b | c"], ["x"] * 30, ["", ""], ["1,2"], ["#zzz | 1 | 1"], ["|||"], ["x | y | z | w | v"],
                 ["x | 0 | 0,0"], ["x | -1 | 0,0"], ["a | #zzz"], ["a | #123456 | -5"], ["a | 1e999 | 1"], ["left"], ["up", "down"], [5], "x",
                 ["x | 1 | a,b"], ["x | 1 | 1,2,3"], ["fill | #zzzzzz"], ["outline | #fff | x | y"], ["fill | #ffffff | 1 | 1 | 1"]]
    elif t == "box":
        vals += [[0, 0, 0, 0], [10, 10, 5, 5], [0, 0, 1, 1], [-1e6, -1e6, 1e6, 1e6], [0, 0, 1e9, 1e9], [0.2, 0.2, 0.8, 0.8], [1, 2, 3], ["a"] * 4,
                 [float("nan")] * 4]
    elif t == "camera":
        a = {"rel": 0.0}
        b = {"rel": 1.0}
        vals += [[], [{"at": a, "cx": 0, "cy": 0, "zoom": 1e-9}], [{"at": a, "cx": 0, "cy": 0, "zoom": 1e9}],
                 [{"at": a, "cx": 1e12, "cy": -1e12, "zoom": 1}], [{"at": a, "cx": 100, "cy": 100, "zoom": 1, "ease": "nope"}],
                 [{"at": a, "cx": 100, "cy": 100, "zoom": 1}], [{"at": b, "cx": 100, "cy": 100, "zoom": 1}, {"at": a, "cx": 100, "cy": 100, "zoom": 1}],
                 [{"at": {"rel": 5.0}, "cx": 100, "cy": 100, "zoom": 1}], [{"at": {"rel": -5.0}, "cx": 100, "cy": 100, "zoom": 1}],
                 [{"at": {"t": 1e9}, "cx": 100, "cy": 100, "zoom": 1}], "x", [5]]
    elif t == "asset":
        vals += ["", "nope"] + list(asset_keys)
    elif t == "items":
        fields = p.get("fields") or [{"name": "id", "type": "string"}]
        one = {f["name"]: ("x" if f["type"] in ("string", "ref") else 1 if f["type"] in ("number", "at") else [0, 0] if f["type"] == "lonlat" else True if f["type"] == "bool" else (f.get("values") or ["x"])[0]) for f in fields}
        vals += [[], [{}], ["x"], "x", [one], [one] * 3, [one] * 13, [dict(one, zz=1)], [{"id": "a", "name": "a", "lonlat": [180, 85]}, {"id": "b", "name": "b", "lonlat": [-180, -85]}],
                 [{"id": "a", "name": "a", "lonlat": [0, 0], "at": {"w": 0, "off": 0, "text": "alpha"}}], [{"id": "a", "name": "a", "lonlat": [0, 0], "at": {"rel": 0.5}}],
                 [{"id": "a", "name": "a", "lonlat": [0, 0], "at": 1e9}], [{"id": "a", "name": "a\nb", "lonlat": [0.5, 0.5]}], [{"id": "a" * 25, "name": "a", "lonlat": [0, 0]}],
                 [{"id": "a", "name": "a", "lonlat": [0, 0], "label_side": "nw"}] * 2, [{"id": "a", "from": "a", "to": "a", "via": "1,2;3,4"}]]
    return vals


def _locate(sb: dict, tid: str):
    spec = _bundle().spec(tid)
    for i, s in enumerate(sb["shots"]):
        if spec["kind"] in ("base", "card") and s["technique"] == tid:
            return i, None
        for j, o in enumerate(s.get("overlays") or []):
            if spec["kind"] == "overlay" and o["technique"] == tid:
                return i, j
        if spec["kind"] == "transition" and (s.get("transition_in") or {}).get("technique") == tid:
            return i, "tr"
    raise LookupError(tid)


@pytest.fixture(scope="module")
def lab(tmp_path_factory):
    d = tmp_path_factory.mktemp("sweep") / "lab"
    shutil.copytree(LAB, d, ignore=shutil.ignore_patterns("cache", "history"))
    from identity_lab import add_to_project_dir                       # the lab predates the ID-* family: its COPY gets one item per ID technique
    add_to_project_dir(d)
    return open_project(d)


def test_the_sweep_covers_all_twelve_param_types():
    """Every type the registry knows has odd values in this sweep; `asset` is a registry type no technique uses yet."""
    seen = {p["type"] for t in _bundle().techniques for p in t["params"]}
    assert seen <= TYPES, seen - TYPES
    for ty in TYPES:
        assert len(odd_values({"type": ty, "values": ["a"], "min": 0, "max": 1}, None, ["K"], "R")) > 3, ty


@pytest.mark.parametrize("tid", [t["id"] for t in _bundle().techniques])
def test_validate_accepts_only_what_can_be_drawn(lab, tid):
    sb = lab.storyboard()
    i, j = _locate(sb, tid)
    spec = _bundle().spec(tid)
    rs = lab.resolve(sb)
    shot = rs["shots"][i]
    if j is None:
        item, t = sb["shots"][i], (shot["_t0"] + shot["_t1"]) / 2
    elif j == "tr":
        item, t = sb["shots"][i]["transition_in"], shot["_t0"] + (shot["transition_in"].get("dur") or 0) / 2
    else:
        ov = shot["overlays"][j]
        item, t = sb["shots"][i]["overlays"][j], (ov["_t0"] + ov["_t1"]) / 2
    asset_keys = list(sb["assets"])
    akey = None
    for s in (shot.get("slots") or {}).values():
        if isinstance(s, dict) and s.get("asset"):
            akey = s["asset"]
            break
    regions = list(((sb["assets"].get(akey) or {}).get("regions") or {})) if akey else []
    region = regions[0] if regions else None
    holes: list = []
    n_drawn = 0
    for p in spec["params"]:
        ref = (item.get("params") or {}).get(p["name"], p.get("default"))
        for v in odd_values(p, ref, asset_keys, region):
            draft = copy.deepcopy(sb)
            tgt = draft["shots"][i] if j is None else (draft["shots"][i]["transition_in"] if j == "tr" else draft["shots"][i]["overlays"][j])
            tgt.setdefault("params", {})[p["name"]] = v
            if any(x["level"] == "error" for x in lab.validate(draft)):
                continue
            lab.use_draft(draft)
            global CURRENT
            CURRENT = (tid, p["name"], v)
            n_drawn += 1
            try:
                lab.frame_at(t, 160)
            except RenderError as e:
                holes.append((p["name"], v, "RenderError: %s" % e.message[:120]))
            except Exception as e:      # noqa: BLE001
                holes.append((p["name"], v, "%s: %s" % (type(e).__name__, str(e)[:120])))
            finally:
                lab.use_draft(None)
    assert not holes, "%s: validate accepts %d values that cannot be drawn, e.g. %s" % (tid, len(holes), holes[:6])
    assert n_drawn > 0 or not spec["params"], "no mutation was accepted by validate: the sweep drew nothing for %s" % tid


# ----------------------------------------------------------------------------- R3B-008: the bounds themselves
def _bound_values(p: dict) -> list:
    """min, max and the default of a number param (the ones that exist), without duplicates."""
    out: list = []
    for k in ("min", "max", "default"):
        v = p.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v not in out:
            out.append(v)
    return out


def _item_and_time(lab, sb, tid):
    i, j = _locate(sb, tid)
    rs = lab.resolve(sb)
    shot = rs["shots"][i]
    if j is None:
        return i, j, (shot["_t0"] + shot["_t1"]) / 2
    if j == "tr":
        return i, j, shot["_t0"] + (shot["transition_in"].get("dur") or 0) / 2
    ov = shot["overlays"][j]
    return i, j, (ov["_t0"] + ov["_t1"]) / 2


@pytest.mark.parametrize("tid", [t["id"] for t in _bundle().techniques if any(p["type"] == "number" for p in t["params"])])
def test_every_numeric_bound_and_default_draws(lab, tid):
    """R3B-008: for EVERY numeric param, its `min`, its `max` and its default (the other params at the editor's defaults) validate
    without an error AND draw. A bound that validate accepts but the canvas cannot hold is a hole in the registry."""
    sb = lab.storyboard()
    i, j, t = _item_and_time(lab, sb, tid)
    spec = _bundle().spec(tid)
    shot = sb["shots"][i]
    ctx = {"shot_id": shot["id"]}
    base = lab.default_params(tid, ctx)
    # the lab's own values for params the defaults leave empty (a camera, a required text): the reference configuration
    ref_item = shot if j is None else (shot["transition_in"] if j == "tr" else shot["overlays"][j])
    for k, v in (ref_item.get("params") or {}).items():
        if base.get(k) is None:
            base[k] = v
    holes: list = []
    for p in spec["params"]:
        if p["type"] != "number":
            continue
        for v in _bound_values(p):
            draft = copy.deepcopy(sb)
            tgt = draft["shots"][i] if j is None else (draft["shots"][i]["transition_in"] if j == "tr" else draft["shots"][i]["overlays"][j])
            tgt["params"] = {**copy.deepcopy(base), p["name"]: v}
            errs = [x for x in lab.validate(draft) if x["level"] == "error"]
            if errs:
                holes.append((p["name"], v, "validate refuses its own bound: %s" % errs[0]["message"][:100]))
                continue
            lab.use_draft(draft)
            global CURRENT
            CURRENT = (tid, p["name"], v)
            try:
                lab.frame_at(t, 160)
            except Exception as e:      # noqa: BLE001
                holes.append((p["name"], v, "%s: %s" % (type(e).__name__, str(e)[:100])))
            finally:
                lab.use_draft(None)
    assert not holes, "%s: %d bound values do not draw: %s" % (tid, len(holes), holes[:8])
