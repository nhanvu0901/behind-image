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

REPO_ROOT = Path(__file__).resolve().parents[2]
STYLE_ROOT = Path(os.environ.get("BTI_STYLE_ROOT", REPO_ROOT / "style"))

KINDS = ("base", "overlay", "transition", "card")
RENDERERS: dict = {}          # technique id -> (renderer class, kind)

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


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
        self.dir = (root or STYLE_ROOT) / style_id
        self.style = json.loads((self.dir / "style.json").read_text(encoding="utf-8"))
        reg = json.loads((self.dir / "techniques.json").read_text(encoding="utf-8"))
        self.registry = reg
        pdir = self.dir / "patches"
        if pdir.is_dir():
            reg = dict(reg, techniques=apply_patches(reg["techniques"], pdir))
            self.registry = reg
        self.techniques = reg["techniques"]
        self.by_id = {t["id"]: t for t in self.techniques}

    def spec(self, tid: str) -> dict | None:
        return self.by_id.get(tid)

    def available(self, tid: str) -> bool:
        s = self.by_id.get(tid)
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
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_point(v):
    if isinstance(v, str):
        return None if v else "empty region name"
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(_is_num(x) for x in v):
        return None
    return "must be a region name or [x, y]"


def _check_camera(v):
    if not isinstance(v, list) or len(v) < 1:
        return "camera must be a non-empty list of keys"
    for i, k in enumerate(v):
        if not isinstance(k, dict):
            return "camera key %d must be an object" % i
        for f in ("at", "cx", "cy", "zoom"):
            if f not in k:
                return "camera key %d is missing %r" % (i, f)
        if not (_is_num(k["cx"]) and _is_num(k["cy"]) and _is_num(k["zoom"])) or k["zoom"] <= 0:
            return "camera key %d: cx, cy, zoom must be numbers and zoom > 0" % i
        if not isinstance(k["at"], dict):
            return "camera key %d: 'at' must be an anchor" % i
    return None


def check_value(p: dict, v):
    """Return an error message when `v` does not fit the registry parameter definition `p`, else None."""
    if v is None:
        return None if p.get("default") is None else "null is not allowed"
    t = p["type"]
    if t == "number":
        if not _is_num(v):
            return "must be a number"
        if p.get("min") is not None and v < p["min"]:
            return "must be >= %s" % p["min"]
        if p.get("max") is not None and v > p["max"]:
            return "must be <= %s" % p["max"]
    elif t == "enum":
        if v not in (p.get("values") or []):
            return "must be one of %s" % ", ".join(p.get("values") or [])
    elif t == "bool":
        if not isinstance(v, bool):
            return "must be true or false"
    elif t in ("string", "text"):
        if not isinstance(v, str):
            return "must be a string"
    elif t == "color":
        if not (isinstance(v, str) and _HEX.match(v)):
            return "must be a #rrggbb colour"
    elif t == "point":
        return _check_point(v)
    elif t == "points":
        if not isinstance(v, (list, tuple)):
            return "must be a list of points"
        for i, x in enumerate(v):
            m = _check_point(x)
            if m:
                return "item %d: %s" % (i, m)
    elif t == "lines":
        if not (isinstance(v, (list, tuple)) and all(isinstance(x, str) for x in v)):
            return "must be a list of strings"
    elif t == "box":
        if not (isinstance(v, (list, tuple)) and len(v) == 4 and all(_is_num(x) for x in v)):
            return "must be [x0, y0, x1, y1]"
    elif t == "camera":
        return _check_camera(v)
    elif t == "asset":
        if not (isinstance(v, str) and v):
            return "must be an asset key"
    return None


def validate_params(spec: dict, params: dict, path: str) -> list[dict]:
    """Issues for one params object against technique `spec` (unknown parameters are errors)."""
    issues = []
    if not isinstance(params, dict):
        return [{"level": "error", "path": path, "message": "params must be an object"}]
    defs = {p["name"]: p for p in spec["params"]}
    for k, v in params.items():
        if k.startswith("_"):
            continue
        if k not in defs:
            issues.append({"level": "error", "path": "%s.%s" % (path, k),
                           "message": "unknown parameter %r for %s (allowed: %s)" % (k, spec["id"], ", ".join(sorted(defs)) or "none")})
            continue
        msg = check_value(defs[k], v)
        if msg:
            issues.append({"level": "error", "path": "%s.%s" % (path, k), "message": "%s: %s" % (k, msg)})
    for k, d in defs.items():
        if d.get("required") and params.get(k) is None:
            issues.append({"level": "error", "path": "%s.%s" % (path, k), "message": "required parameter %r is missing" % k})
    return issues


def merged_params(spec: dict, params: dict | None) -> dict:
    """Registry defaults overlaid with the storyboard's params."""
    out = {p["name"]: p["default"] for p in spec["params"]}
    out.update({k: v for k, v in (params or {}).items() if not k.startswith("_")})
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
