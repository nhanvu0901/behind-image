"""Technique registry: `style/gae/techniques.json` (what exists) joined to `@technique` renderers (what can be drawn).

Usage in a technique module:

    @technique("HI-01", "overlay")
    class Spotlight(OverlayRenderer): ...

A class can be registered under several ids (the camera family does).  The id must exist in techniques.json and its `kind`
must match; `check_registry()` verifies this and is part of the test suite.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .errors import DataError, StyleError
from .limits import BOX_MIN_PX, CAMERA_ZOOM_MAX, CANVAS_H, CANVAS_W, POINT_ABS_MAX

REPO_ROOT = Path(__file__).resolve().parents[2]
STYLE_ROOT = Path(os.environ.get("BTI_STYLE_ROOT", REPO_ROOT / "style"))

KINDS = ("base", "overlay", "transition", "card")
RENDERERS: dict = {}          # technique id -> (renderer class, kind)

STYLE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_HEX = re.compile(r"#[0-9a-fA-F]{6}")


def technique(tid: str, kind: str):
    """Class decorator: register a renderer under a registry id."""
    if kind not in KINDS:
        raise ValueError("bad kind %r" % kind)

    def deco(cls):
        if tid in RENDERERS and RENDERERS[tid][0] is not cls:
            raise ValueError("technique %s registered twice" % tid)
        RENDERERS[tid] = (cls, kind)
        ids = cls.__dict__.get("technique_ids", ())
        cls.technique_ids = ids if tid in ids else ids + (tid,)
        return cls
    return deco


PATCHABLE = ("params", "slots", "timing", "engine", "preview")


class PatchError(ValueError):
    pass


def apply_patches(techniques: list, patch_dir: Path) -> list:
    """Merge `patch_dir/*.json` ({"<ID>": {field: value}}) over the technique list, in sorted file-name order.
    Any field except `id` is replaced wholesale. Unknown ids raise PatchError. Returns the (new) list; `applied/` is ignored."""
    import copy
    out = copy.deepcopy(techniques)
    by = {t["id"]: t for t in out}
    for f in sorted(Path(patch_dir).glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            raise PatchError("%s: invalid JSON (%s)" % (f.name, e))
        if not isinstance(data, dict):
            raise PatchError("%s: a patch file must be an object {id: fields}" % f.name)
        for tid, fields in data.items():
            if tid not in by:
                raise PatchError("%s: unknown technique id %r" % (f.name, tid))
            if not isinstance(fields, dict) or "id" in fields:
                raise PatchError("%s: %s must be an object of fields without 'id'" % (f.name, tid))
            by[tid].update(copy.deepcopy(fields))
    return out


class StyleBundle:
    """style.json + techniques.json for one style id (cached by `load_bundle`)."""

    def __init__(self, style_id: str, root: Path | None = None):
        self.style_id = style_id
        if not (isinstance(style_id, str) and STYLE_ID.fullmatch(style_id)):
            raise StyleError("unknown style %r" % (style_id,))
        self.dir = (root or STYLE_ROOT) / style_id
        try:
            self.style = json.loads((self.dir / "style.json").read_text(encoding="utf-8"))
            reg = json.loads((self.dir / "techniques.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise StyleError("unknown style %r (there is no style/%s/)" % (style_id, style_id))
        except (OSError, ValueError) as e:
            raise StyleError("style %r is unreadable: %s" % (style_id, str(e)[:120]))
        self.registry = reg
        pdir = self.dir / "patches"
        if pdir.is_dir():
            reg = dict(reg, techniques=apply_patches(reg["techniques"], pdir))
            self.registry = reg
        self.techniques = reg["techniques"]
        self.by_id = {t["id"]: t for t in self.techniques}

    def spec(self, tid: str) -> dict | None:
        return self.by_id.get(tid) if isinstance(tid, str) else None

    def available(self, tid: str) -> bool:
        s = self.by_id.get(tid) if isinstance(tid, str) else None
        return bool(s and s.get("engine", {}).get("available") is True and tid in RENDERERS)

    def sv(self, section: str, key: str, default=None):
        """A style.json constant: style[section][key]['value'] (or the raw value)."""
        v = (self.style.get(section) or {}).get(key)
        if isinstance(v, dict) and "value" in v:
            return v["value"]
        return default if v is None else v

    def param_defaults(self, tid: str) -> dict:
        return {p["name"]: p["default"] for p in self.by_id[tid]["params"]}


_BUNDLES: dict = {}


def load_bundle(style_id: str = "gae", root: Path | None = None) -> StyleBundle:
    """The bundle of a style id; `StyleError` (a DataError and a FileNotFoundError) when there is no such style."""
    if not (isinstance(style_id, str) and STYLE_ID.fullmatch(style_id)):
        raise StyleError("unknown style %r" % (style_id,))
    key = (style_id, str(root))
    b = _BUNDLES.get(key)
    path = (root or STYLE_ROOT) / style_id / "techniques.json"
    mtime = path.stat().st_mtime if path.exists() else 0
    if b is None or getattr(b, "_mtime", None) != mtime:
        b = StyleBundle(style_id, root)
        b._mtime = mtime
        _BUNDLES[key] = b
    return b


# ----------------------------------------------------------------------------- parameter validation
def _is_num(v):
    """A finite number (NaN and infinity are not numbers a document may hold)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float("inf"), float("-inf"))


def _P(code: str, message: str, **args):
    """A problem found in one value: (code, args, English message)."""
    return code, args, message


def _check_point(v, numeric_only=False):
    if isinstance(v, str):
        if numeric_only:
            return _P("point_numeric_only", "a region name is not accepted here: give [x, y]")
        return None if v else _P("point_empty_region", "empty region name")
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(_is_num(x) for x in v):
        if all(abs(x) <= POINT_ABS_MAX for x in v):
            return None
        return _P("point_out_of_range", "coordinates must be within +-%d" % POINT_ABS_MAX, limit=int(POINT_ABS_MAX))
    return _P("point_bad_form", "must be a region name or [x, y]")


def _check_camera(v):
    if not isinstance(v, list) or len(v) < 1:
        return _P("camera_empty", "camera must be a non-empty list of keys")
    for i, k in enumerate(v):
        if not isinstance(k, dict):
            return _P("camera_key_not_object", "camera key %d must be an object" % i, index=i)
        for f in ("at", "cx", "cy", "zoom"):
            if f not in k:
                return _P("camera_key_missing_field", "camera key %d is missing %r" % (i, f), index=i, field=f)
        if not (_is_num(k["cx"]) and _is_num(k["cy"]) and _is_num(k["zoom"])) or k["zoom"] <= 0:
            return _P("camera_key_numbers", "camera key %d: cx, cy, zoom must be numbers and zoom > 0" % i, index=i)
        if abs(k["cx"]) > POINT_ABS_MAX or abs(k["cy"]) > POINT_ABS_MAX or k["zoom"] > CAMERA_ZOOM_MAX:
            return _P("camera_key_range", "camera key %d: cx, cy within +-%d and zoom up to %d" % (i, POINT_ABS_MAX, CAMERA_ZOOM_MAX),
                      index=i, limit=int(POINT_ABS_MAX), zoom_max=CAMERA_ZOOM_MAX)
        if not isinstance(k["at"], dict):
            return _P("camera_key_anchor", "camera key %d: 'at' must be an anchor" % i, index=i)
    return None


_PATTERNS: dict = {}


def _pattern(src: str):
    c = _PATTERNS.get(src)
    if c is None:
        c = _PATTERNS[src] = re.compile(src)
    return c


def _check_count(p: dict, n: int):
    lo, hi = p.get("min_items"), p.get("max_items")
    if lo is not None and n < lo:
        return _P("param_item_count", ("needs exactly %d items (got %d)" if lo == hi else "needs at least %d items (got %d)") % (lo, n),
                  min=lo, max=hi, got=n)
    if hi is not None and n > hi:
        return _P("param_item_count", ("needs exactly %d items (got %d)" if lo == hi else "needs at most %d items (got %d)") % (hi, n),
                  min=lo, max=hi, got=n)
    return None


def _bad_pattern(p: dict, prefix: str = "", index=None):
    hint = p.get("pattern_hint") or "does not have the required form (%s)" % p.get("pattern")
    return _P("param_bad_form", prefix + hint, pattern=p.get("pattern"), hint=p.get("pattern_hint"), index=index)


def check_problem(p: dict, v):
    """None when `v` fits the registry parameter definition `p`, else `(code, args, message)`."""
    if v is None:
        return None if p.get("default") is None else _P("param_null", "null is not allowed")
    t = p["type"]
    if t == "number":
        if not _is_num(v):
            return _P("param_not_number", "must be a number")
        if p.get("min") is not None and v < p["min"]:
            return _P("param_below_min", "must be >= %s" % p["min"], min=p["min"])
        if p.get("max") is not None and v > p["max"]:
            return _P("param_above_max", "must be <= %s" % p["max"], max=p["max"])
    elif t == "enum":
        if v not in (p.get("values") or []):
            return _P("param_not_in_values", "must be one of %s" % ", ".join(p.get("values") or []), values=list(p.get("values") or []))
    elif t == "bool":
        if not isinstance(v, bool):
            return _P("param_not_bool", "must be true or false")
    elif t in ("string", "text"):
        if not isinstance(v, str):
            return _P("param_not_string", "must be a string")
        if p.get("pattern") is not None and not _pattern(p["pattern"]).fullmatch(one_line(v)):
            return _bad_pattern(p)
    elif t == "color":
        if not (isinstance(v, str) and _HEX.fullmatch(v)):
            return _P("param_bad_color", "must be a #rrggbb colour")
    elif t == "point":
        return _check_point(v, p.get("numeric_only"))
    elif t == "points":
        if not isinstance(v, (list, tuple)):
            return _P("param_not_points", "must be a list of points")
        m = _check_count(p, len(v))
        if m:
            return m
        for i, x in enumerate(v):
            m = _check_point(x, p.get("numeric_only"))
            if m:
                return m[0], dict(m[1], index=i), "item %d: %s" % (i, m[2])
    elif t == "lines":
        if not (isinstance(v, (list, tuple)) and all(isinstance(x, str) for x in v)):
            return _P("param_not_lines", "must be a list of strings")
        m = _check_count(p, len(v))
        if m:
            return m
        if p.get("pattern") is not None:
            for i, x in enumerate(v):
                if not _pattern(p["pattern"]).fullmatch(one_line(x)):
                    return _bad_pattern(p, "item %d: " % i, i)
    elif t == "box":
        if not (isinstance(v, (list, tuple)) and len(v) == 4 and all(_is_num(x) for x in v)):
            return _P("param_bad_box", "must be [x0, y0, x1, y1]")
        x0, y0, x1, y1 = v
        if not (0 <= x0 and x0 + BOX_MIN_PX <= x1 <= CANVAS_W and 0 <= y0 and y0 + BOX_MIN_PX <= y1 <= CANVAS_H):
            return _P("param_box_range", "must lie inside the %dx%d canvas and be at least %d px wide and high" % (CANVAS_W, CANVAS_H, BOX_MIN_PX),
                      w=CANVAS_W, h=CANVAS_H, min_px=BOX_MIN_PX)
    elif t == "camera":
        return _check_camera(v)
    elif t == "asset":
        if not (isinstance(v, str) and v):
            return _P("param_not_asset", "must be an asset key")
    return None


def check_value(p: dict, v):
    """Return an error message when `v` does not fit the registry parameter definition `p`, else None."""
    m = check_problem(p, v)
    return m[2] if m else None


def validate_params(spec: dict, params: dict, path: str) -> list[dict]:
    """Issues for one params object against technique `spec` (unknown parameters are errors).
    Every issue has `level`, `path`, `message`, `code` and `args`."""
    issues = []
    if not isinstance(params, dict):
        return [{"level": "error", "path": path, "message": "params must be an object", "code": "params_not_object", "args": {}}]
    defs = {p["name"]: p for p in spec["params"]}
    for k, v in params.items():
        if k.startswith("_"):
            continue
        if k not in defs:
            issues.append({"level": "error", "path": "%s.%s" % (path, k), "code": "unknown_param",
                           "args": {"param": k, "technique": spec["id"], "allowed": sorted(defs)},
                           "message": "unknown parameter %r for %s (allowed: %s)" % (k, spec["id"], ", ".join(sorted(defs)) or "none")})
            continue
        m = check_problem(defs[k], v)
        if m:
            issues.append({"level": "error", "path": "%s.%s" % (path, k), "code": m[0],
                           "args": dict(m[1], param=k, technique=spec["id"]), "message": "%s: %s" % (k, m[2])})
    for k, d in defs.items():
        if d.get("required") and params.get(k) is None:
            issues.append({"level": "warn", "code": "incomplete", "path": "%s.%s" % (path, k),
                           "args": {"what": "param", "name": k, "technique": spec["id"]},
                           "message": "incomplete: required parameter %r is not set" % k})
    return issues


def one_line(v):
    """Collapse line breaks and runs of blanks: a one-line text field must never reach the text renderer with a newline."""
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v


def merged_params(spec: dict, params: dict | None) -> dict:
    """Registry defaults overlaid with the storyboard's params. Values of one-line text fields (type `string`, and each item
    of `lines`) have their line breaks collapsed: a user pressing Enter in a text box must not break the picture."""
    out = {p["name"]: p["default"] for p in spec["params"]}
    out.update({k: v for k, v in (params or {}).items() if not k.startswith("_")})
    for p in spec["params"]:
        v = out.get(p["name"])
        if p["type"] == "string" and isinstance(v, str):
            out[p["name"]] = one_line(v)
        elif p["type"] == "lines" and isinstance(v, (list, tuple)):
            out[p["name"]] = [one_line(x) for x in v]
    return out


def check_registry(bundle: StyleBundle) -> list[str]:
    """Consistency of renderers against techniques.json (used by tests)."""
    problems = []
    for tid, (cls, kind) in RENDERERS.items():
        s = bundle.by_id.get(tid)
        if s is None:
            problems.append("%s: renderer registered but no registry entry" % tid)
        elif s["kind"] != kind:
            problems.append("%s: renderer kind %s != registry kind %s" % (tid, kind, s["kind"]))
    for s in bundle.techniques:
        av = s.get("engine", {}).get("available")
        if av is True and s["id"] not in RENDERERS:
            problems.append("%s: engine.available but no renderer" % s["id"])
        if av is not True and s["id"] in RENDERERS:
            problems.append("%s: renderer exists but engine.available is not true" % s["id"])
    return problems
