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
from .errors import DataError
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
    f = Path(project_dir) / "storyboard.json"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DataError("storyboard.json is missing", what="storyboard")
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise DataError("storyboard.json is corrupt: %s" % str(e)[:120], what="storyboard")
    if not isinstance(doc, dict):
        raise DataError("storyboard.json is corrupt: the top level must be an object", what="storyboard")
    return doc


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


KEEP_HISTORY = 50


def prune_history(hist: Path, keep: int = KEEP_HISTORY) -> None:
    """Keep the newest `keep` copies in history/ (by modification time, then name)."""
    try:
        files = sorted((f for f in hist.glob("*.json") if f.is_file()), key=lambda f: (f.stat().st_mtime_ns, f.name))
        for f in files[: max(0, len(files) - keep)]:
            f.unlink(missing_ok=True)
    except OSError:
        pass


def save(project_dir: Path, sb: dict, issues: list[dict]) -> str:
    """Write storyboard.json atomically; back the previous file up to history/. Returns the new revision.
    `issues` is the validation result for `sb`; any error refuses the save."""
    errs = [i for i in issues if i["level"] == "error"]
    if errs:
        raise ValidationError(issues)
    project_dir = Path(project_dir)
    clean = strip_derived(sb)
    text = json.dumps(clean, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    text.encode("utf-8")                    # a lone surrogate or a NaN fails HERE, before anything is written
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
        prune_history(hist)
    write_atomic(target, text)
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


# ----------------------------------------------------------------------------- paths and references
_IMAGE_OK: dict = {}          # (path, mtime_ns, size) -> None | problem text; images are checked once per file version


def safe_rel(project_dir, rel) -> Path | None:
    """`project_dir / rel` when `rel` is a relative path that stays inside the project, else None (absolute path, `..`,
    backslash, NUL, or a symlink that leaves the project)."""
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel or rel.startswith("/") or (len(rel) > 1 and rel[1] == ":"):
        return None
    if any(part in ("..", "") for part in rel.split("/")):
        return None
    root = Path(project_dir).resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def image_problem(path: Path) -> str | None:
    """None when `path` decodes as an image header and its data is intact, else a short reason (cached per file version)."""
    try:
        st = path.stat()
    except OSError as e:
        return "cannot be read (%s)" % e.strerror
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _IMAGE_OK:
        return _IMAGE_OK[key]
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        res = None
    except Exception:       # noqa: BLE001
        res = "is not a readable image"
    if len(_IMAGE_OK) > 2000:
        _IMAGE_OK.clear()
    _IMAGE_OK[key] = res
    return res


def slot_kind(sd: dict) -> str | None:
    """The asset kind a registry slot is for: video slots video, a slot named mask* a mask, other image slots an image."""
    if sd.get("type") == "video":
        return "video"
    if sd.get("type") == "image":
        return "mask" if str(sd.get("name", "")).startswith("mask") else "image"
    return None


def slot_accepts(sd: dict) -> tuple[str, ...]:
    """Asset kinds that may sit in a slot. A video slot also takes a still image (the lab projects use one as a stand-in)."""
    k = slot_kind(sd)
    return ("video", "image") if k == "video" else ((k,) if k else ())


def missing_of(spec: dict, item: dict, kind: str, shot: dict | None = None) -> list[tuple[str, str]]:
    """What an item (shot, overlay or transition) still needs: [("slot", name) | ("param", name)].  An item with a
    non-empty result is INCOMPLETE: it validates with a warning, saves, and renders as a placeholder (shot) or is skipped."""
    out: list[tuple[str, str]] = []
    slots = item.get("slots") if isinstance(item.get("slots"), dict) else {}
    for sd in spec.get("slots") or []:
        if kind == "transition":
            break                       # a transition's slots only describe the two shots it joins; it has none of its own
        if not sd.get("required") or sd.get("type") not in ("image", "video"):
            continue
        v = slots.get(sd["name"])
        has = isinstance(v, dict) and bool(v.get("asset"))
        if not has and kind == "overlay" and sd["name"] == "image" and isinstance(shot, dict):
            has = primary_slot(shot)[1] is not None          # an overlay's `image` is the shot's own image
        if not has:
            out.append(("slot", sd["name"]))
    params = item.get("params") if isinstance(item.get("params"), dict) else {}
    for pd in spec.get("params") or []:
        if pd.get("required") and params.get(pd["name"]) is None:
            out.append(("param", pd["name"]))
    return out


# ----------------------------------------------------------------------------- validate
def validate(sb: dict, tm: Timing, bundle: R.StyleBundle, project_dir: Path | None = None) -> list[dict]:
    """Issues of a storyboard. Never raises: a structure the checks did not foresee is reported as an error issue.
    Level `error` blocks a save; level `warn` does not; a warn with code `incomplete` marks unfinished work (blocks approval)."""
    try:
        return _validate(sb, tm, bundle, project_dir)
    except Exception as e:      # noqa: BLE001
        return [{"level": "error", "path": "", "message": "the storyboard has a structure the checks cannot read (%s: %s)"
                 % (type(e).__name__, str(e)[:120])}]


def _validate(sb: dict, tm: Timing, bundle: R.StyleBundle, project_dir: Path | None = None) -> list[dict]:
    issues: list[dict] = []

    def err(path, msg):
        issues.append({"level": "error", "path": path, "message": msg})

    def warn(path, msg):
        issues.append({"level": "warn", "path": path, "message": msg})

    def incomplete(path, what, name, tid):
        issues.append({"level": "warn", "code": "incomplete", "path": path,
                       "message": "incomplete: required %s %r of %s is not set" % (what, name, tid)})

    if not isinstance(sb, dict):
        return [{"level": "error", "path": "", "message": "storyboard must be an object"}]
    if sb.get("schema") != SCHEMA:
        err("schema", "schema must be %r" % SCHEMA)
    canvas = sb.get("canvas")
    if canvas is None:
        canvas = {}
    if not isinstance(canvas, dict):
        err("canvas", "canvas must be an object like {\"w\": 1920, \"h\": 1080}")
        canvas = {}
    if (canvas.get("w"), canvas.get("h")) != (1920, 1080):
        warn("canvas", "renderers are tuned for 1920x1080; the engine always renders 1080p")
    if project_dir is not None and sb.get("project") not in (None, Path(project_dir).name):
        warn("project", "project %r differs from the folder name %r" % (sb.get("project"), Path(project_dir).name))
    if sb.get("audio") is not None:
        a = sb["audio"]
        if not isinstance(a, str) or not a:
            err("audio", "audio must be a file path inside the project")
        elif project_dir is not None:
            f = safe_rel(project_dir, a)
            if f is None:
                err("audio", "audio %r must be a file inside the project" % a)
            elif not f.is_file():
                warn("audio", "audio file %r does not exist" % a)
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
        if not a.get("file") or not isinstance(a.get("file"), str):
            err(p + ".file", "file is required")
        elif project_dir is not None:
            f = safe_rel(project_dir, a["file"])
            if f is None:
                err(p + ".file", "file %r must be a path inside the project" % a["file"])
            elif not f.is_file():
                err(p + ".file", "file %r does not exist" % a["file"])
            elif a.get("kind") in ("image", "mask"):
                m = image_problem(f)
                if m:
                    err(p + ".file", "file %r %s" % (a["file"], m))
        for dim in ("width", "height"):
            if dim in a and a[dim] is not None and not (R._is_num(a[dim]) and a[dim] > 0):
                err("%s.%s" % (p, dim), "%s must be a positive number" % dim)
        regs = a.get("regions")
        if regs is not None and not isinstance(regs, dict):
            err(p + ".regions", "regions must be an object")
            regs = {}
        for rn, r in (regs or {}).items():
            if not (isinstance(r, dict) and R._is_num(r.get("x")) and R._is_num(r.get("y"))):
                err("%s.regions.%s" % (p, rn), "region needs numeric x and y")

    def check_slots(path, slots, spec, tid):
        """Slot names, asset keys and asset kinds of one shot or overlay."""
        if slots is None:
            return
        if not isinstance(slots, dict):
            err(path, "slots must be an object")
            return
        sdefs = {x["name"]: x for x in spec["slots"]}
        for sn, sv in slots.items():
            sp = "%s.%s" % (path, sn)
            if sn not in sdefs:
                err(sp, "unknown slot %r for %s (allowed: %s)" % (sn, tid, ", ".join(sdefs) or "none"))
            elif isinstance(sv, dict) and sv.get("asset") is not None:
                ak = sv["asset"]
                if not isinstance(ak, str) or ak not in assets:
                    err(sp + ".asset", "asset %r is not defined" % (ak,))
                elif isinstance(assets[ak], dict):
                    ok_kinds, got = slot_accepts(sdefs[sn]), assets[ak].get("kind")
                    if ok_kinds and got in ("image", "video", "mask") and got not in ok_kinds:
                        err(sp + ".asset", "slot %r takes %s but asset %r is a %s" % (sn, " or ".join(ok_kinds), ak, got))
            elif sv is not None and not isinstance(sv, dict):
                err(sp, "a slot must be an object like {\"asset\": \"<key>\"}")

    def check_asset_params(path, params, spec):
        for pd in spec["params"]:
            if pd["type"] == "asset" and isinstance(params, dict):
                v = params.get(pd["name"])
                if isinstance(v, str) and v and v not in assets:
                    err("%s.%s" % (path, pd["name"]), "asset %r is not defined" % v)

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
        if "fade_s" in end and not (R._is_num(end["fade_s"]) and end["fade_s"] >= 0):
            err("end.fade_s", "fade_s must be a number >= 0")
    shots = shots_of(sb)
    if not isinstance(shots, list):
        err("shots", "shots must be a list")
        return issues
    if not shots:
        err("shots", "a storyboard needs at least one shot")
    seen = set()
    starts: list = []
    for i, s in enumerate(shots):
        if not isinstance(s, dict):
            starts.append(None)
            continue
        if not isinstance(s.get("start"), dict):
            err("shots[%d].start" % i, "start anchor is required (an object like {\"t\": 12.5})")
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
        if not sid or not isinstance(sid, str):
            err(p + ".id", "id is required (a string)")
        elif sid in seen:
            err(p + ".id", "duplicate shot id %r" % sid)
        else:
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
        if isinstance(s.get("intent"), str) and s["intent"] not in INTENTS:
            warn(p + ".intent", "unknown intent %r" % s["intent"])

        tid = s.get("technique")
        spec = bundle.spec(tid)
        if spec is None:
            err(p + ".technique", "unknown technique %r" % (tid,))
            continue
        if spec["kind"] not in ("base", "card"):
            err(p + ".technique", "%s is a %s technique; a shot needs kind base or card" % (tid, spec["kind"]))
        if not bundle.available(tid):
            err(p + ".technique", "%s is not available in the engine yet" % tid)
        issues.extend(R.validate_params(spec, s.get("params") or {}, p + ".params"))
        check_asset_params(p + ".params", s.get("params"), spec)
        check_slots(p + ".slots", s.get("slots"), spec, tid)
        for what, name in missing_of(spec, s, "base"):
            if what == "slot":
                incomplete(p + ".slots", "slot", name, tid)
        # camera keys
        for name in camera_params(spec):
            keys = (s.get("params") or {}).get(name) if isinstance(s.get("params"), dict) else None
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
                    ease = k.get("ease", "linear")
                    if not isinstance(ease, str) or ease not in EASE:
                        err(kp + ".ease", "unknown ease %r" % (ease,))
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
        _, akey = primary_slot(s) if isinstance(s.get("slots"), dict) else (None, None)
        regions = ((assets.get(akey) or {}).get("regions") or {}) if isinstance(akey, str) else {}
        if not isinstance(regions, dict):
            regions = {}
        oseen = set()
        ovs = s.get("overlays")
        if ovs is not None and not isinstance(ovs, list):
            err(p + ".overlays", "overlays must be a list")
            ovs = []
        for j, o in enumerate(ovs or []):
            op = "%s.overlays[%d]" % (p, j)
            if not isinstance(o, dict):
                err(op, "overlay must be an object")
                continue
            oid = o.get("id")
            if isinstance(oid, str) and oid in oseen:
                err(op + ".id", "duplicate overlay id %r" % oid)
            if isinstance(oid, str):
                oseen.add(oid)
            ospec = bundle.spec(o.get("technique"))
            if ospec is None:
                err(op + ".technique", "unknown technique %r" % (o.get("technique"),))
                continue
            if ospec["kind"] != "overlay":
                err(op + ".technique", "%s is a %s technique; an overlay needs kind overlay" % (o["technique"], ospec["kind"]))
            if not bundle.available(o["technique"]):
                err(op + ".technique", "%s is not available in the engine yet" % o["technique"])
            issues.extend(R.validate_params(ospec, o.get("params") or {}, op + ".params"))
            check_asset_params(op + ".params", o.get("params"), ospec)
            check_slots(op + ".slots", o.get("slots"), ospec, o["technique"])
            for what, name in missing_of(ospec, o, "overlay", s):
                if what == "slot":
                    incomplete(op + ".slots", "slot", name, o["technique"])
            oparams = o.get("params") if isinstance(o.get("params"), dict) else {}
            for pd in ospec["params"]:
                v = oparams.get(pd["name"])
                if pd["type"] == "point" and isinstance(v, str) and akey is not None and v not in regions:
                    err("%s.params.%s" % (op, pd["name"]), "region %r is not defined on asset %r" % (v, akey))
            names = {pd["name"] for pd in ospec["params"]}
            if {"at", "screen", "text"} <= names and oparams.get("at") is None and oparams.get("screen") is None:
                warn(op + ".params", "neither `at` nor `screen` is set: the label has no position and is not drawn")
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
