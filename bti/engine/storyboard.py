"""Storyboard document: load, resolve (anchors to seconds), validate, save.

Schema `bti.storyboard/1` (design section 6).  Keys starting with `_` are derived (`_t`, `_t0`, `_t1`); they are added by
`resolve` and stripped by `save`.  The revision is the sha256 of the canonical JSON (sorted keys, compact, no `_` keys).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from . import registry as R
from .timing import AnchorError, Timing
from .vfx import EASE

SCHEMA = "bti.storyboard/1"
MIN_SHOT_S = 0.2
EPS = 1e-6
INTENTS = ["establish", "explore", "point_at", "isolate", "reveal", "compare", "context", "quantify",
           "explain_mechanism", "quote", "structure", "transition"]


class ValidationError(Exception):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join("%s: %s" % (i["path"], i["message"]) for i in issues if i["level"] == "error")[:600])


# ----------------------------------------------------------------------------- canonical form and revision
def strip_derived(obj):
    if isinstance(obj, dict):
        return {k: strip_derived(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_derived(v) for v in obj]
    return obj


def canonical(sb: dict) -> str:
    return json.dumps(strip_derived(sb), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def revision_of(sb: dict) -> str:
    return hashlib.sha256(canonical(sb).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------- load / save
def load(project_dir: Path) -> dict:
    return json.loads((Path(project_dir) / "storyboard.json").read_text(encoding="utf-8"))


def write_atomic(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def save(project_dir: Path, sb: dict, issues: list[dict]) -> str:
    """Write storyboard.json atomically; back the previous file up to history/. Returns the new revision.
    `issues` is the validation result for `sb`; any error refuses the save."""
    errs = [i for i in issues if i["level"] == "error"]
    if errs:
        raise ValidationError(issues)
    project_dir = Path(project_dir)
    clean = strip_derived(sb)
    rev = revision_of(clean)
    target = project_dir / "storyboard.json"
    if target.exists():
        old = target.read_text(encoding="utf-8")
        try:
            old_rev = revision_of(json.loads(old))
        except Exception:
            old_rev = "unreadable"
        if old_rev == rev:
            return rev                      # nothing changed: no new history entry
        hist = project_dir / "history"
        hist.mkdir(parents=True, exist_ok=True)
        name = "%s-%s.json" % (time.strftime("%Y%m%dT%H%M%S"), old_rev[:8])
        n = 0
        while (hist / name).exists():
            n += 1
            name = "%s-%s-%d.json" % (time.strftime("%Y%m%dT%H%M%S"), old_rev[:8], n)
        write_atomic(hist / name, old)
    write_atomic(target, json.dumps(clean, indent=1, ensure_ascii=False) + "\n")
    return rev


# ----------------------------------------------------------------------------- helpers
def shots_of(sb):
    return sb.get("shots") or []


def primary_slot(shot: dict):
    """(slot name, asset key) of the shot's main image: slot `image`, else the first slot with an asset."""
    slots = shot.get("slots") or {}
    if isinstance(slots.get("image"), dict) and slots["image"].get("asset"):
        return "image", slots["image"]["asset"]
    for k, v in slots.items():
        if isinstance(v, dict) and v.get("asset"):
            return k, v["asset"]
    return None, None


def camera_params(spec: dict) -> list[str]:
    return [p["name"] for p in spec["params"] if p["type"] == "camera"]


def _resolve_anchor(a, tm: Timing, t0=None, t1=None):
    try:
        t = tm.resolve(a, t0, t1)
        a["_t"] = t
        return t
    except AnchorError:
        return None


# ----------------------------------------------------------------------------- resolve
def resolve(sb: dict, tm: Timing, bundle: R.StyleBundle) -> dict:
    """Copy of `sb` with `_t` on anchors and `_t0`/`_t1` on shots, overlays and transitions."""
    sb = copy.deepcopy(strip_derived(sb))
    shots = shots_of(sb)
    end = sb.get("end") or {}
    end_t = _resolve_anchor(end, tm) if isinstance(end, dict) and end else None
    for i, s in enumerate(shots):
        t0 = _resolve_anchor(s.get("start", {}), tm) if isinstance(s.get("start"), dict) else None
        s["_t0"] = t0
    for i, s in enumerate(shots):
        s["_t1"] = shots[i + 1]["_t0"] if i + 1 < len(shots) else end_t
        t0, t1 = s["_t0"], s["_t1"]
        spec = bundle.spec(s.get("technique"))
        if spec and t0 is not None and t1 is not None:
            for name in camera_params(spec):
                for k in (s.get("params") or {}).get(name) or []:
                    if isinstance(k, dict) and isinstance(k.get("at"), dict):
                        _resolve_anchor(k["at"], tm, t0, t1)
        tr = s.get("transition_in")
        if isinstance(tr, dict) and t0 is not None:
            tr["_t0"] = t0
            tr["_t1"] = t0 + float(tr.get("dur", 0) or 0)
        for o in s.get("overlays") or []:
            ot0 = _resolve_anchor(o["start"], tm) if isinstance(o.get("start"), dict) else None
            ot1 = None
            if isinstance(o.get("end"), dict):
                ot1 = _resolve_anchor(o["end"], tm)
            elif isinstance(o.get("dur"), (int, float)) and ot0 is not None:
                ot1 = ot0 + float(o["dur"])
            elif t1 is not None:
                ot1 = t1
            o["_t0"], o["_t1"] = ot0, ot1
    return sb


# ----------------------------------------------------------------------------- validate
def validate(sb: dict, tm: Timing, bundle: R.StyleBundle, project_dir: Path | None = None) -> list[dict]:
    issues: list[dict] = []

    def err(path, msg):
        issues.append({"level": "error", "path": path, "message": msg})

    def warn(path, msg):
        issues.append({"level": "warn", "path": path, "message": msg})

    if not isinstance(sb, dict):
        return [{"level": "error", "path": "", "message": "storyboard must be an object"}]
    if sb.get("schema") != SCHEMA:
        err("schema", "schema must be %r" % SCHEMA)
    canvas = sb.get("canvas") or {}
    if (canvas.get("w"), canvas.get("h")) != (1920, 1080):
        warn("canvas", "renderers are tuned for 1920x1080; the engine always renders 1080p")
    assets = sb.get("assets")
    if not isinstance(assets, dict):
        err("assets", "assets must be an object")
        assets = {}
    for key, a in assets.items():
        p = "assets.%s" % key
        if not isinstance(a, dict):
            err(p, "asset must be an object")
            continue
        if a.get("kind") not in ("image", "video", "mask"):
            err(p + ".kind", "kind must be image, video or mask")
        if not a.get("file"):
            err(p + ".file", "file is required")
        elif project_dir is not None and not (Path(project_dir) / a["file"]).exists():
            err(p + ".file", "file %r does not exist" % a["file"])
        for rn, r in (a.get("regions") or {}).items():
            if not (isinstance(r, dict) and R._is_num(r.get("x")) and R._is_num(r.get("y"))):
                err("%s.regions.%s" % (p, rn), "region needs numeric x and y")

    # -- end and shots ---------------------------------------------------------------------------------------
    end = sb.get("end")
    end_t = None
    if not isinstance(end, dict):
        err("end", "end anchor is required")
    else:
        try:
            end_t = tm.resolve(end)
        except AnchorError as e:
            err("end", str(e))
    shots = shots_of(sb)
    if not shots:
        err("shots", "a storyboard needs at least one shot")
    seen = set()
    starts: list = []
    for i, s in enumerate(shots):
        try:
            starts.append(tm.resolve(s["start"]) if isinstance(s.get("start"), dict) else None)
        except (AnchorError, KeyError) as e:
            starts.append(None)
            err("shots[%d].start" % i, str(e))
        if isinstance(s.get("start"), dict) and "rel" in s["start"]:
            err("shots[%d].start" % i, "'rel' anchors are only allowed for camera keys")
    if starts and starts[0] is not None and starts[0] > 0.05:
        warn("shots[0].start", "the first shot starts at %.2f s: the beginning of the timeline is not covered" % starts[0])
    for i, s in enumerate(shots):
        p = "shots[%d]" % i
        if not isinstance(s, dict):
            err(p, "shot must be an object")
            continue
        sid = s.get("id")
        if not sid:
            err(p + ".id", "id is required")
        elif sid in seen:
            err(p + ".id", "duplicate shot id %r" % sid)
        seen.add(sid)
        t0 = starts[i]
        t1 = starts[i + 1] if i + 1 < len(shots) else end_t
        if t0 is not None:
            for a in (s["start"],):
                m = tm.stale(a)
                if m:
                    err(p + ".start", m)
        if t0 is not None and t1 is not None:
            if t1 - t0 < MIN_SHOT_S - EPS:
                err(p, "shot is shorter than %.1f s (%.3f s)" % (MIN_SHOT_S, t1 - t0))
        if i > 0 and t0 is not None and starts[i - 1] is not None and t0 <= starts[i - 1]:
            err(p + ".start", "shots must be in time order (starts before the previous shot)")
        if s.get("intent") is not None and s["intent"] not in INTENTS:
            warn(p + ".intent", "unknown intent %r" % s["intent"])

        tid = s.get("technique")
        spec = bundle.spec(tid)
        if spec is None:
            err(p + ".technique", "unknown technique %r" % tid)
            continue
        if spec["kind"] not in ("base", "card"):
            err(p + ".technique", "%s is a %s technique; a shot needs kind base or card" % (tid, spec["kind"]))
        if not bundle.available(tid):
            err(p + ".technique", "%s is not available in the engine yet" % tid)
        issues.extend({**x, "path": x["path"]} for x in R.validate_params(spec, s.get("params") or {}, p + ".params"))
        # slots
        slots = s.get("slots") or {}
        sdefs = {x["name"]: x for x in spec["slots"]}
        for sn, sv in slots.items():
            if sn not in sdefs:
                err("%s.slots.%s" % (p, sn), "unknown slot %r for %s (allowed: %s)" % (sn, tid, ", ".join(sdefs) or "none"))
            elif isinstance(sv, dict) and sv.get("asset") is not None and sv["asset"] not in assets:
                err("%s.slots.%s.asset" % (p, sn), "asset %r is not defined" % sv["asset"])
        for sn, sd in sdefs.items():
            if sd["required"] and sd["type"] in ("image", "video") and sn not in slots:
                err("%s.slots" % p, "required slot %r is missing" % sn)
        # camera keys
        for name in camera_params(spec):
            keys = (s.get("params") or {}).get(name)
            if isinstance(keys, list) and t0 is not None and t1 is not None:
                prev = None
                for ki, k in enumerate(keys):
                    kp = "%s.params.%s[%d]" % (p, name, ki)
                    if not isinstance(k, dict) or not isinstance(k.get("at"), dict):
                        continue
                    m = tm.stale(k["at"])
                    if m:
                        err(kp + ".at", m)
                    try:
                        kt = tm.resolve(k["at"], t0, t1)
                    except AnchorError as e:
                        err(kp + ".at", str(e))
                        continue
                    if prev is not None and kt <= prev + 1e-9:
                        err(kp + ".at", "camera keys must be in strictly increasing time order")
                    prev = kt
                    if k.get("ease", "linear") not in EASE:
                        err(kp + ".ease", "unknown ease %r" % k.get("ease"))
        # transition
        tr = s.get("transition_in")
        if tr is not None:
            tp = p + ".transition_in"
            tspec = bundle.spec(tr.get("technique")) if isinstance(tr, dict) else None
            if tspec is None:
                err(tp + ".technique", "unknown transition technique %r" % (tr.get("technique") if isinstance(tr, dict) else tr))
            else:
                if tspec["kind"] != "transition":
                    err(tp + ".technique", "%s is not a transition" % tr["technique"])
                if not bundle.available(tr["technique"]):
                    err(tp + ".technique", "%s is not available in the engine yet" % tr["technique"])
                issues.extend(R.validate_params(tspec, tr.get("params") or {}, tp + ".params"))
                d = tr.get("dur")
                if not R._is_num(d) or d < 0:
                    err(tp + ".dur", "dur must be a number >= 0")
                elif t0 is not None and t1 is not None and d > (t1 - t0) + EPS:
                    err(tp + ".dur", "transition is longer than the shot")
                if i == 0:
                    warn(tp, "the first shot has nothing to transition from")
        # overlays
        _, akey = primary_slot(s)
        regions = (assets.get(akey) or {}).get("regions") or {} if akey else {}
        oseen = set()
        for j, o in enumerate(s.get("overlays") or []):
            op = "%s.overlays[%d]" % (p, j)
            if o.get("id") in oseen:
                err(op + ".id", "duplicate overlay id %r" % o.get("id"))
            oseen.add(o.get("id"))
            ospec = bundle.spec(o.get("technique"))
            if ospec is None:
                err(op + ".technique", "unknown technique %r" % o.get("technique"))
                continue
            if ospec["kind"] != "overlay":
                err(op + ".technique", "%s is a %s technique; an overlay needs kind overlay" % (o["technique"], ospec["kind"]))
            if not bundle.available(o["technique"]):
                err(op + ".technique", "%s is not available in the engine yet" % o["technique"])
            issues.extend(R.validate_params(ospec, o.get("params") or {}, op + ".params"))
            for pd in ospec["params"]:
                v = (o.get("params") or {}).get(pd["name"])
                if pd["type"] == "point" and isinstance(v, str) and v not in regions:
                    err("%s.params.%s" % (op, pd["name"]), "region %r is not defined on asset %r" % (v, akey))
            try:
                ot0 = tm.resolve(o["start"]) if isinstance(o.get("start"), dict) else None
                if ot0 is None:
                    err(op + ".start", "start anchor is required")
                else:
                    m = tm.stale(o["start"])
                    if m:
                        err(op + ".start", m)
                    if "rel" in o["start"]:
                        err(op + ".start", "'rel' anchors are only allowed for camera keys")
            except AnchorError as e:
                ot0 = None
                err(op + ".start", str(e))
            ot1 = None
            if isinstance(o.get("end"), dict):
                try:
                    ot1 = tm.resolve(o["end"])
                    m = tm.stale(o["end"])
                    if m:
                        err(op + ".end", m)
                except AnchorError as e:
                    err(op + ".end", str(e))
            elif o.get("dur") is not None:
                if not R._is_num(o["dur"]) or o["dur"] <= 0:
                    err(op + ".dur", "dur must be a number > 0")
                elif ot0 is not None:
                    ot1 = ot0 + o["dur"]
            elif t1 is not None:
                ot1 = t1
            if ot0 is not None and t0 is not None and t1 is not None:
                if ot0 < t0 - EPS or ot0 >= t1 - EPS:
                    err(op + ".start", "overlay starts outside its shot (%.2f s; shot spans %.2f-%.2f s)" % (ot0, t0, t1))
                elif ot1 is not None and ot1 > t1 + EPS:
                    err(op, "overlay ends outside its shot (%.2f s > %.2f s)" % (ot1, t1))
                if ot1 is not None and ot1 <= ot0:
                    err(op, "overlay ends before it starts")
    if end_t is not None and starts and starts[-1] is not None and end_t <= starts[-1]:
        err("end", "end is not after the last shot start")
    if end_t is not None and tm.duration and end_t > tm.duration + 1.0:
        warn("end", "end %.2f s is after the audio/timing duration %.2f s" % (end_t, tm.duration))
    return issues
