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
import threading
import time
from pathlib import Path

from . import registry as R
from . import limits as L
from .errors import DataError
from .timing import AnchorError, Timing
from .vfx import EASE
from bti.fsio import atomic_replace

SCHEMA = "bti.storyboard/1"
MIN_SHOT_S = 0.2
EPS = 1e-6
SOURCES = ("import", "agent", "human", "identity")      # `identity`: written by bti.identity.apply_identity
INTENTS = ["establish", "explore", "point_at", "isolate", "reveal", "compare", "context", "quantify",
           "explain_mechanism", "quote", "structure", "transition"]


class ValidationError(Exception):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join("%s: %s" % (i["path"], i["message"]) for i in issues if i["level"] == "error")[:600])


# ----------------------------------------------------------------------------- canonical form and revision
MAX_DEPTH = 64


def check_depth(obj, limit: int = MAX_DEPTH) -> None:
    """DataError when `obj` (dicts and lists) is nested deeper than `limit` levels. Iterative: it never recurses."""
    stack = [(obj, 1)]
    while stack:
        o, d = stack.pop()
        if isinstance(o, dict):
            kids = o.values()
        elif isinstance(o, list):
            kids = o
        else:
            continue
        if d > limit:
            raise DataError("the document is nested more than %d levels deep" % limit, what="storyboard")
        stack.extend((k, d + 1) for k in kids if isinstance(k, (dict, list)))


def strip_derived(obj):
    """Copy of `obj` without the keys that start with `_`. Over MAX_DEPTH levels of nesting it raises DataError (never RecursionError)."""
    check_depth(obj)
    return _strip(obj)


def _strip(obj):
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def canonical(sb: dict) -> str:
    return json.dumps(strip_derived(sb), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def revision_of(sb: dict) -> str:
    return hashlib.sha256(canonical(sb).encode("utf-8")).hexdigest()


def _bad(where: str, want: str):
    raise DataError("storyboard.json is corrupt: %s must be %s" % (where, want), what="storyboard")


def _dict_or_none(v, where: str):
    if v is not None and not isinstance(v, dict):
        _bad(where, "an object")


def check_shape(doc) -> None:
    """DataError when the document has a wrong TYPE somewhere the engine walks (top level, `shots`, a shot, `params`, `slots`,
    `overlays`, an overlay, an anchor, `transition_in`, `assets`, an asset, `regions`). Missing keys and bad VALUES are not
    this function's business (validate reports them); only a shape that would make a walker fail with AttributeError / TypeError.
    Iterative over the shots, so it is linear in the size of the document."""
    if not isinstance(doc, dict):
        _bad("the top level", "an object")
    for k in ("canvas", "end", "approvals", "assets"):
        _dict_or_none(doc.get(k), k)
    for key, a in (doc.get("assets") or {}).items():
        _dict_or_none(a, "assets.%s" % key)
        if isinstance(a, dict):
            _dict_or_none(a.get("regions"), "assets.%s.regions" % key)
            for rn, r in (a.get("regions") or {}).items():
                _dict_or_none(r, "assets.%s.regions.%s" % (key, rn))
    shots = doc.get("shots")
    if shots is None:
        return
    if not isinstance(shots, list):
        _bad("shots", "a list")
    for i, s in enumerate(shots):
        _check_item(s, "shots[%d]" % i, True)
        for j, o in enumerate(s.get("overlays") or []):
            _check_item(o, "shots[%d].overlays[%d]" % (i, j), False)
        tr = s.get("transition_in")
        _dict_or_none(tr, "shots[%d].transition_in" % i)
        if isinstance(tr, dict):
            _dict_or_none(tr.get("params"), "shots[%d].transition_in.params" % i)


def _check_item(s, where: str, is_shot: bool) -> None:
    if not isinstance(s, dict):
        _bad(where, "an object")
    for k in ("start", "end", "params", "slots"):
        _dict_or_none(s.get(k), "%s.%s" % (where, k))
    for k, v in (s.get("slots") or {}).items():
        _dict_or_none(v, "%s.slots.%s" % (where, k))
    if is_shot:
        if s.get("overlays") is not None and not isinstance(s["overlays"], list):
            _bad(where + ".overlays", "a list")
        for k, v in (s.get("params") or {}).items():
            if isinstance(v, list):
                for n, key in enumerate(v):
                    if isinstance(key, dict) and not R._is_num(key.get("at")):     # a number is a time in seconds inside an `items` record
                        _dict_or_none(key.get("at"), "%s.params.%s[%d].at" % (where, k, n))


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
    check_shape(doc)
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
        atomic_replace(tmp, path)
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
    check_shape(sb)
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
                keys = (s.get("params") or {}).get(name)
                for k in keys if isinstance(keys, list) else []:
                    if isinstance(k, dict) and isinstance(k.get("at"), dict):
                        _resolve_anchor(k["at"], tm, t0, t1)
        if spec and t0 is not None and t1 is not None:
            _resolve_item_anchors(spec, s.get("params"), tm, t0, t1)
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
            ospec = bundle.spec(o.get("technique"))
            if ospec and ot0 is not None and ot1 is not None:
                _resolve_item_anchors(ospec, o.get("params"), tm, ot0, ot1)
    return sb


def _resolve_item_anchors(spec: dict, params, tm: Timing, t0: float, t1: float) -> None:
    """Word anchors in the `at` fields of `items` params (a place that appears on its word): resolved the way a camera key's `at`
    is, to absolute seconds in `_t`; `rel` anchors count from the element's own start to its end."""
    if not isinstance(params, dict):
        return
    for name, fields in R.items_at_fields(spec):
        items = params.get(name)
        for it in items if isinstance(items, list) else []:
            for f in fields:
                if isinstance(it, dict) and isinstance(it.get(f), dict):
                    _resolve_anchor(it[f], tm, t0, t1)
    for name in R.at_params(spec):                      # a param that is one moment: its word anchor is resolved the same way
        if isinstance(params.get(name), dict):
            _resolve_anchor(params[name], tm, t0, t1)


# ----------------------------------------------------------------------------- paths and references
_MEDIA_OK: dict = {}          # (path, mtime_ns, size, kind) -> None | (code, reason); media files are checked once per file version
_MEDIA_LOCK = threading.RLock()


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


def media_problem(path: Path, kind: str) -> tuple[str, str] | None:
    """None when the media file is intact, else `(issue code, short reason)`.

    image / mask: the header must read (`asset_file_unreadable`: zero bytes, not an image) AND all the pixel data must decode
    (`asset_file_truncated`: a picture cut off part way, which OpenCV would draw half grey without a word). A JPEG is decoded at 1/8
    scale, which still reads every compressed byte but costs a fraction of the time.
    video: the file must open and give a first frame (`asset_video_unreadable`).
    The answer is cached by (path, size, modification time, kind): a file is decoded once per version, so validating a project
    whose files did not change costs a dictionary lookup per asset."""
    try:
        st = path.stat()
    except OSError as e:
        return "asset_file_unreadable", "cannot be read (%s)" % e.strerror
    key = (str(path), st.st_mtime_ns, st.st_size, kind)
    with _MEDIA_LOCK:
        if key in _MEDIA_OK:
            return _MEDIA_OK[key]
    res = _check_media(path, kind)
    with _MEDIA_LOCK:
        if len(_MEDIA_OK) > 4000:
            _MEDIA_OK.clear()
        _MEDIA_OK[key] = res
    return res


def _check_media(path: Path, kind: str) -> tuple[str, str] | None:
    if kind == "video":
        try:
            import cv2
            cap = cv2.VideoCapture(str(path))
            try:
                ok = cap.isOpened() and cap.read()[0]
            finally:
                cap.release()
        except Exception:       # noqa: BLE001
            ok = False
        return None if ok else ("asset_video_unreadable", "cannot be opened as a video or has no frame")
    from PIL import Image
    try:
        with Image.open(path) as im:
            im.verify()
    except Exception:       # noqa: BLE001
        return "asset_file_unreadable", "is not a readable image"
    try:
        with Image.open(path) as im:                    # verify() leaves the file unusable: open it again to decode
            if im.format == "JPEG":
                im.draft("RGB", (max(im.width // 8, 1), max(im.height // 8, 1)))
            im.load()
    except Exception:       # noqa: BLE001
        return "asset_file_truncated", "is cut off: its picture does not decode completely"
    return None


def size_mismatch(path: Path, a: dict) -> tuple[int, int] | None:
    """`(stored width, stored height)` when asset `a` declares a positive `width` and `height` that differ from the pixels of the
    image file at `path` (the size the engine draws; `bti.media.assets.stored_size`, header only, remembered per path, modification
    time and file size, so a validation on every edit does not read an unchanged file again), else None. A size that is not
    declared, a file that cannot be measured, or a size that agrees all give None."""
    w, h = a.get("width"), a.get("height")
    if not (R._is_num(w) and R._is_num(h) and w > 0 and h > 0):
        return None
    from bti.media.assets import stored_size
    sw, sh = stored_size(path)
    return (sw, sh) if sw and sh and (sw != w or sh != h) else None


def image_problem(path: Path) -> str | None:
    """Short reason when `path` is not an intact image, else None (kept for older callers; see `media_problem`)."""
    m = media_problem(path, "image")
    return m[1] if m else None


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


# Every `code` a validation issue can carry, with a one-line English meaning (`args` keys are named in the text). A test checks
# that validate never emits a code that is missing here.
ISSUE_CODES = {
    "undrawable": "A technique cannot draw this shot, overlay or transition with the values it has (found by drawing a frame). args: shot, technique, overlay, asset (the asset key, when the failure is about an asset file or key; else null).",
    "incomplete": "A required slot or parameter is not set yet; saving is allowed, approval is not. args: what (slot|param), name, technique.",
    "not_an_object": "The storyboard document is not a JSON object. args: none.",
    "unreadable_structure": "The document has a structure the checks cannot read. args: error.",
    "wrong_schema": "`schema` is not the supported schema id. args: schema.",
    "canvas_not_object": "`canvas` is not an object. args: none.",
    "canvas_size": "canvas.w or canvas.h is not a positive number. args: field.",
    "canvas_fps": "canvas.fps is not a number in range. args: min, max.",
    "canvas_not_1080p": "The canvas is not 1920x1080 (warning). args: none.",
    "not_a_string": "A field that must be text is not. args: field (asset, when the field belongs to an asset).",
    "approvals_not_object": "`approvals` is not an object. args: none.",
    "project_name_differs": "`project` differs from the folder name (warning). args: project, folder.",
    "audio_invalid": "`audio` is not a file path. args: none.",
    "audio_outside_project": "`audio` points outside the project folder. args: file.",
    "audio_missing": "The audio file does not exist (warning). args: file.",
    "assets_not_object": "`assets` is not an object. args: none.",
    "asset_not_object": "An asset is not an object. args: asset.",
    "asset_kind": "An asset's kind is not image, video or mask. args: asset.",
    "asset_file_required": "An asset has no file. args: asset.",
    "asset_file_outside_project": "An asset file path leaves the project. args: file, asset.",
    "asset_file_missing": "An asset file does not exist. args: file, asset.",
    "asset_file_unreadable": "An image or mask file is not a readable image (zero bytes, not an image, cannot be read). args: file, asset.",
    "asset_file_truncated": "An image or mask file is cut off: its header reads but its picture does not decode completely. args: file, asset.",
    "asset_video_unreadable": "A video file cannot be opened or has no frame. args: file, asset.",
    "asset_size_mismatch": "An image or mask asset declares a width/height that differs from the pixels of its stored file (warning): its regions and the camera keys (cx, cy, zoom) written for it are in the wrong space. Nothing is rewritten. args: asset, width, height, stored_width, stored_height.",
    "credit_not_object": "An asset's credit is not an object. args: asset.",
    "asset_size": "An asset width/height is not a positive number. args: field, asset.",
    "regions_not_object": "An asset's regions are not an object. args: asset.",
    "region_xy": "A region has no numeric x and y. args: region, asset.",
    "region_radius": "A region rx/ry is not a number >= 0. args: region, field, asset.",
    "slots_not_object": "`slots` is not an object. args: none.",
    "unknown_slot": "A slot name the technique does not have. args: slot, technique, allowed.",
    "asset_undefined": "An asset key that is not in `assets`. args: asset.",
    "slot_asset_kind": "The asset in a slot has the wrong kind. args: slot, asset, takes, got.",
    "slot_not_object": "A slot value is not an object. args: slot.",
    "locked_not_bool": "`locked` is not true/false. args: none.",
    "unknown_source": "`source` is not import, agent, human or identity (warning). args: source.",
    "unknown_intent": "`intent` is not in the fixed list (warning). args: intent.",
    "region_undefined": "A region name that the asset does not define. args: region, asset, param.",
    "end_required": "The `end` anchor is missing. args: none.",
    "anchor_invalid": "An anchor cannot be resolved (bad form, word index out of range, rel without a shot). args: param, index (camera key, 0-based) when it is a camera key.",
    "end_fade": "end.fade_s is not a number >= 0. args: none.",
    "shots_not_list": "`shots` is not a list. args: none.",
    "no_shots": "The storyboard has no shot. args: none.",
    "start_required": "A start anchor is missing. args: none.",
    "rel_anchor_not_allowed": "A `rel` anchor is used outside a camera key. args: none.",
    "start_negative": "A shot starts before 0 s. args: start.",
    "first_shot_late": "The first shot starts after 0 s (warning). args: start.",
    "shot_not_object": "A shot is not an object. args: none.",
    "id_required": "A shot or overlay id is missing or empty. args: none.",
    "duplicate_shot_id": "Two shots share an id. args: id.",
    "stale_anchor": "A word anchor's text no longer matches the word at its index. args: param, index (camera key, 0-based) when it is a camera key.",
    "shot_too_short": "A shot is shorter than the minimum. args: min, got.",
    "shots_out_of_order": "Shots are not in time order. args: none.",
    "unknown_technique": "The technique id is not in the registry. args: technique.",
    "wrong_technique_kind": "The technique has the wrong kind for its place. args: technique, kind, needs.",
    "technique_unavailable": "The technique exists but the engine cannot draw it yet. args: technique.",
    "camera_keys_order": "Camera keys are not in strictly increasing time order. args: param, index (the key, 0-based).",
    "camera_rel_range": "A camera key `rel` is outside 0..1. args: param, index.",
    "unknown_ease": "A camera key has an unknown ease name. args: ease, param, index.",
    "transition_dur": "A transition `dur` is not a number >= 0. args: none.",
    "transition_too_long": "A transition is longer than its shot. args: dur, shot_dur.",
    "first_shot_transition": "The first shot has a transition but nothing to come from (warning). args: none.",
    "overlays_not_list": "`overlays` is not a list. args: none.",
    "overlay_not_object": "An overlay is not an object. args: none.",
    "duplicate_overlay_id": "Two overlays of a shot share an id. args: id.",
    "label_without_position": "A label has neither `at` nor `screen` (warning). args: none.",
    "overlay_dur": "An overlay `dur` is not a number > 0. args: none.",
    "overlay_outside_shot": "An overlay starts or ends outside its shot. args: start|end, shot_start, shot_end.",
    "overlay_ends_before_start": "An overlay ends before it starts. args: none.",
    "end_before_last_start": "`end` is not after the last shot start. args: none.",
    "end_after_audio": "`end` is after the audio/timing duration (warning). args: end, duration.",
    "style_unusable": "The style id is unknown or unreadable. args: style.",
    "timing_unusable": "The timing file is missing, outside the project or malformed. args: file.",
    "params_not_object": "`params` is not an object. args: none.",
    "unknown_param": "A parameter the technique does not have. args: param, technique, allowed.",
    "param_null": "null where a value is required. args: param, technique.",
    "param_not_number": "A number parameter holds something else. args: param, technique.",
    "param_below_min": "A number is below the minimum. args: param, technique, min.",
    "param_above_max": "A number is above the maximum. args: param, technique, max.",
    "param_not_in_values": "The value is not one of the allowed values. args: param, technique, values.",
    "param_not_bool": "A true/false parameter holds something else. args: param, technique.",
    "param_not_string": "A text parameter holds something else. args: param, technique.",
    "param_bad_form": "A text value does not have the required form. args: param, technique, pattern, hint (Vietnamese sentence), index (line number for lists).",
    "param_bad_color": "Not a #rrggbb colour. args: param, technique.",
    "param_not_points": "A points parameter is not a list. args: param, technique.",
    "param_not_lines": "A lines parameter is not a list of strings. args: param, technique.",
    "param_item_count": "A list has too few or too many items. args: param, technique, min, max, got.",
    "param_bad_box": "A box is not [x0, y0, x1, y1]. args: param, technique.",
    "param_box_range": "A box leaves the canvas or is too small. args: param, technique, w, h, min_px.",
    "param_not_asset": "Not an asset key. args: param, technique.",
    "point_bad_form": "A point is neither a region name nor [x, y]. args: param, technique, index (in lists).",
    "point_empty_region": "An empty region name. args: param, technique, index.",
    "point_out_of_range": "A coordinate is absurdly large. args: param, technique, limit, index.",
    "point_numeric_only": "A region name where only [x, y] is accepted. args: param, technique, index.",
    "camera_empty": "The camera has no keys. args: param, technique.",
    "camera_key_not_object": "A camera key is not an object. args: param, technique, index.",
    "camera_key_missing_field": "A camera key lacks at, cx, cy or zoom. args: param, technique, index, field.",
    "camera_key_numbers": "A camera key cx/cy/zoom is not a number or zoom <= 0. args: param, technique, index.",
    "camera_key_range": "A camera key cx/cy/zoom is out of range. args: param, technique, index, limit, zoom_max.",
    "camera_key_anchor": "A camera key `at` is not an anchor. args: param, technique, index.",
    "identity_style_unknown": "`identity` is not an object with a `style` the style's identity block lists (error). args: style, allowed.",
    "param_bad_at": "A parameter that is one moment (type `at`) is neither a number of seconds nor a word anchor. args: param, technique.",
    "param_not_items": "An items parameter (a list of records) is not a list. args: param, technique.",
    "item_not_object": "An item of an items parameter is not an object. args: param, technique, index (0-based), item (its name).",
    "item_unknown_field": "An item has a field its parameter does not declare. args: param, technique, index, field, item, allowed.",
    "item_field_missing": "A required field of an item is missing or null. args: param, technique, index, field, item.",
    "item_field_bad_type": "A field of an item has the wrong kind of value (not text, number, true/false, region or point). args: param, technique, index, field, item, want.",
    "item_field_below_min": "A number field of an item is below its minimum. args: param, technique, index, field, item, min.",
    "item_field_above_max": "A number field of an item is above its maximum. args: param, technique, index, field, item, max.",
    "item_field_not_in_values": "An enum field of an item holds a value that is not allowed. args: param, technique, index, field, item, values.",
    "item_field_bad_form": "A text field of an item does not have the required form. args: param, technique, index, field, item, pattern, hint (Vietnamese sentence).",
    "item_field_bad_lonlat": "A longitude/latitude field is not [lon, lat] or is out of range (lon -180..180, lat -85..85). args: param, technique, index, field, item, reason (form|lon|lat).",
    "item_field_bad_at": "A time field of an item is neither a number of seconds nor a word anchor. args: param, technique, index, field, item.",
    "item_anchor_invalid": "A word anchor inside an item cannot be resolved (word index out of range). args: param, index, field, item.",
    "item_anchor_stale": "A word anchor inside an item names a word that is no longer at that index (the script changed). args: param, index, field, item.",
    "map_duplicate_place": "Two places of a MAP-01 share an id. args: param, technique, id, index.",
    "map_route_unknown_place": "A route end of a MAP-01 names no place. args: param, technique, index (the route), field (from|to), place.",
    "map_bad_via": "A route's `via` of a MAP-01 is not a list of `lon,lat` pairs inside the world. args: param, technique, index (the route).",
    "map_bad_center": "A view centre of a MAP-01 is not `lon, lat` inside the world (lon -180..180, lat -85..85). args: param, technique.",
    "map_view_coarse": "The start or the end view of a MAP-01 is narrower than 300 km (warning): Natural Earth has no detail at that scale. args: param, technique, width_km.",
    "map_unknown_iso": "A region code of a MAP-01 is not an ISO 3166-1 alpha-2 code of the bundled countries. args: param, technique, index, code.",
    "element_too_short": "A shot or overlay of the channel identity (`ID-`) or of an explanatory component (`MAP-`, `KEY-`, `TIME-`, `NUM-`, `TREE-`, `STATE-`, `DOC-`) is shorter than the technique's `timing.min_s` (error). args: technique, min, got.",
    "identity_technique_mismatch": "A structure shot (title slot or chapter card) uses a technique that is not the one of the chosen identity style (warning). args: shot, technique, style, wanted."
}


# ----------------------------------------------------------------------------- validate
def validate(sb: dict, tm: Timing, bundle: R.StyleBundle, project_dir: Path | None = None) -> list[dict]:
    """Issues of a storyboard. Never raises: a structure the checks did not foresee is reported as an error issue.
    Level `error` blocks a save; level `warn` does not; a warn with code `incomplete` marks unfinished work (blocks approval)."""
    try:
        return _validate(sb, tm, bundle, project_dir)
    except Exception as e:      # noqa: BLE001
        return [{"level": "error", "path": "", "code": "unreadable_structure", "args": {"error": type(e).__name__},
                 "message": "the storyboard has a structure the checks cannot read (%s: %s)" % (type(e).__name__, str(e)[:120])}]


def _validate(sb: dict, tm: Timing, bundle: R.StyleBundle, project_dir: Path | None = None) -> list[dict]:
    issues: list[dict] = []

    def err(path, msg, code, **args):
        issues.append({"level": "error", "path": path, "message": msg, "code": code, "args": args})

    def warn(path, msg, code, **args):
        issues.append({"level": "warn", "path": path, "message": msg, "code": code, "args": args})

    def incomplete(path, what, name, tid):
        issues.append({"level": "warn", "code": "incomplete", "path": path, "args": {"what": what, "name": name, "technique": tid},
                       "message": "incomplete: required %s %r of %s is not set" % (what, name, tid)})

    if not isinstance(sb, dict):
        return [{"level": "error", "path": "", "code": "not_an_object", "args": {}, "message": "storyboard must be an object"}]
    if sb.get("schema") != SCHEMA:
        err("schema", "schema must be %r" % SCHEMA, "wrong_schema", schema=SCHEMA)
    canvas = sb.get("canvas")
    if canvas is None:
        canvas = {}
    if not isinstance(canvas, dict):
        err("canvas", "canvas must be an object like {\"w\": 1920, \"h\": 1080}", "canvas_not_object")
        canvas = {}
    for dim in ("w", "h"):
        if dim in canvas and not (R._is_num(canvas[dim]) and canvas[dim] > 0):
            err("canvas." + dim, "%s must be a positive number" % dim, "canvas_size", field=dim)
    if "fps" in canvas and not (R._is_num(canvas["fps"]) and L.CANVAS_FPS_MIN <= canvas["fps"] <= L.CANVAS_FPS_MAX):
        err("canvas.fps", "fps must be a number from %d to %d" % (L.CANVAS_FPS_MIN, L.CANVAS_FPS_MAX), "canvas_fps", min=L.CANVAS_FPS_MIN, max=L.CANVAS_FPS_MAX)
    if (canvas.get("w"), canvas.get("h")) != (1920, 1080):
        warn("canvas", "renderers are tuned for 1920x1080; the engine always renders 1080p", "canvas_not_1080p")
    for k in ("project", "title"):
        if k in sb and sb[k] is not None and not isinstance(sb[k], str):
            err(k, "%s must be a string" % k, "not_a_string", field=k)
    if "approvals" in sb and sb["approvals"] is not None and not isinstance(sb["approvals"], dict):
        err("approvals", "approvals must be an object", "approvals_not_object")
    if project_dir is not None and sb.get("project") not in (None, Path(project_dir).name):
        warn("project", "project %r differs from the folder name %r" % (sb.get("project"), Path(project_dir).name), "project_name_differs", project=sb.get("project"), folder=Path(project_dir).name)
    if sb.get("audio") is not None:
        a = sb["audio"]
        if not isinstance(a, str) or not a:
            err("audio", "audio must be a file path inside the project", "audio_invalid")
        elif project_dir is not None:
            f = safe_rel(project_dir, a)
            if f is None:
                err("audio", "audio %r must be a file inside the project" % a, "audio_outside_project", file=a)
            elif not f.is_file():
                warn("audio", "audio file %r does not exist" % a, "audio_missing", file=a)
    assets = sb.get("assets")
    if not isinstance(assets, dict):
        err("assets", "assets must be an object", "assets_not_object")
        assets = {}
    for key, a in assets.items():
        p = "assets.%s" % key
        if not isinstance(a, dict):
            err(p, "asset must be an object", "asset_not_object", asset=key)
            continue
        if a.get("kind") not in ("image", "video", "mask"):
            err(p + ".kind", "kind must be image, video or mask", "asset_kind", asset=key)
        if not a.get("file") or not isinstance(a.get("file"), str):
            err(p + ".file", "file is required", "asset_file_required", asset=key)
        elif project_dir is not None:
            f = safe_rel(project_dir, a["file"])
            if f is None:
                err(p + ".file", "file %r must be a path inside the project" % a["file"], "asset_file_outside_project", file=a["file"], asset=key)
            elif not f.is_file():
                err(p + ".file", "file %r does not exist" % a["file"], "asset_file_missing", file=a["file"], asset=key)
            elif a.get("kind") in ("image", "mask", "video"):
                m = media_problem(f, a["kind"])
                msg = "file %r %s" % (a["file"], m[1]) if m else ""
                if m and m[0] == "asset_file_truncated":
                    err(p + ".file", msg, "asset_file_truncated", file=a["file"], asset=key)
                elif m and m[0] == "asset_video_unreadable":
                    err(p + ".file", msg, "asset_video_unreadable", file=a["file"], asset=key)
                elif m:
                    err(p + ".file", msg, "asset_file_unreadable", file=a["file"], asset=key)
                elif a["kind"] in ("image", "mask"):
                    got = size_mismatch(f, a)
                    if got:
                        warn(p, "asset %r is recorded as %sx%s but its file is %sx%s pixels: its regions and camera keys are in the wrong space"
                             % (key, a["width"], a["height"], got[0], got[1]), "asset_size_mismatch",
                             asset=key, width=a["width"], height=a["height"], stored_width=got[0], stored_height=got[1])
        for k in ("title", "artist", "year"):
            v = a.get(k)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (str, int))):
                err("%s.%s" % (p, k), "%s must be a string" % k, "not_a_string", field=k, asset=key)
        if a.get("credit") is not None:
            cr = a["credit"]
            if not isinstance(cr, dict):
                err(p + ".credit", "credit must be an object", "credit_not_object", asset=key)
            else:
                for k, v in cr.items():
                    if v is not None and not isinstance(v, str):
                        err("%s.credit.%s" % (p, k), "%s must be a string" % k, "not_a_string", field=k, asset=key)
        for dim in ("width", "height"):
            if dim in a and a[dim] is not None and not (R._is_num(a[dim]) and a[dim] > 0):
                err("%s.%s" % (p, dim), "%s must be a positive number" % dim, "asset_size", field=dim, asset=key)
        regs = a.get("regions")
        if regs is not None and not isinstance(regs, dict):
            err(p + ".regions", "regions must be an object", "regions_not_object", asset=key)
            regs = {}
        for rn, r in (regs or {}).items():
            if not (isinstance(r, dict) and R._is_num(r.get("x")) and R._is_num(r.get("y"))):
                err("%s.regions.%s" % (p, rn), "region needs numeric x and y", "region_xy", region=rn, asset=key)
                continue
            for k in ("rx", "ry"):
                if r.get(k) is not None and not (R._is_num(r[k]) and r[k] >= 0):
                    err("%s.regions.%s.%s" % (p, rn, k), "%s must be a number >= 0" % k, "region_radius", region=rn, field=k, asset=key)
            if r.get("label") is not None and not isinstance(r["label"], str):
                err("%s.regions.%s.label" % (p, rn), "label must be a string", "not_a_string", field="label", asset=key)

    def check_slots(path, slots, spec, tid):
        """Slot names, asset keys and asset kinds of one shot or overlay."""
        if slots is None:
            return
        if not isinstance(slots, dict):
            err(path, "slots must be an object", "slots_not_object")
            return
        sdefs = {x["name"]: x for x in spec["slots"]}
        for sn, sv in slots.items():
            sp = "%s.%s" % (path, sn)
            if sn not in sdefs:
                err(sp, "unknown slot %r for %s (allowed: %s)" % (sn, tid, ", ".join(sdefs) or "none"), "unknown_slot", slot=sn, technique=tid, allowed=list(sdefs))
            elif isinstance(sv, dict) and sv.get("asset") is not None:
                ak = sv["asset"]
                if not isinstance(ak, str) or ak not in assets:
                    err(sp + ".asset", "asset %r is not defined" % (ak,), "asset_undefined", asset=ak)
                elif isinstance(assets[ak], dict):
                    ok_kinds, got = slot_accepts(sdefs[sn]), assets[ak].get("kind")
                    if ok_kinds and got in ("image", "video", "mask") and got not in ok_kinds:
                        err(sp + ".asset", "slot %r takes %s but asset %r is a %s" % (sn, " or ".join(ok_kinds), ak, got), "slot_asset_kind", slot=sn, asset=ak, takes=list(ok_kinds), got=got)
            elif sv is not None and not isinstance(sv, dict):
                err(sp, "a slot must be an object like {\"asset\": \"<key>\"}", "slot_not_object", slot=sn)

    def check_asset_params(path, params, spec):
        for pd in spec["params"]:
            if pd["type"] == "asset" and isinstance(params, dict):
                v = params.get(pd["name"])
                if isinstance(v, str) and v and v not in assets:
                    err("%s.%s" % (path, pd["name"]), "asset %r is not defined" % v, "asset_undefined", asset=v)

    def item_fields(path, item):
        """locked / source / note / intent of one shot or overlay."""
        if "locked" in item and not isinstance(item["locked"], bool):
            err(path + ".locked", "locked must be true or false", "locked_not_bool")
        if item.get("source") is not None:
            if not isinstance(item["source"], str):
                err(path + ".source", "source must be a string", "not_a_string", field="source")
            elif item["source"] not in SOURCES:      # older lab projects carry other labels: a warning, not a refusal
                warn(path + ".source", "unknown source %r (expected %s)" % (item["source"], ", ".join(SOURCES)), "unknown_source", source=item["source"])
        if item.get("note") is not None and not isinstance(item["note"], str):
            err(path + ".note", "note must be a string", "not_a_string", field="note")
        if item.get("intent") is not None:
            if not isinstance(item["intent"], str):
                err(path + ".intent", "intent must be a string", "not_a_string", field="intent")
            elif item["intent"] not in INTENTS:
                warn(path + ".intent", "unknown intent %r" % item["intent"], "unknown_intent", intent=item["intent"])

    def check_regions(path, params, spec, akey, regions):
        """A `point` / `points` value that names a region must name one that exists on the asset in use."""
        if not isinstance(params, dict):
            return
        for pd in spec["params"]:
            v = params.get(pd["name"])
            if pd.get("numeric_only"):
                continue                  # a name there is already an error from the registry check
            if pd["type"] == "point":
                names = [(pd["name"], v)] if isinstance(v, str) else []
            elif pd["type"] == "points" and isinstance(v, (list, tuple)):
                names = [("%s[%d]" % (pd["name"], k), x) for k, x in enumerate(v) if isinstance(x, str)]
            elif pd["type"] == "items" and isinstance(v, (list, tuple)):
                refs = [f["name"] for f in pd.get("fields") or [] if f.get("type") == "ref"]
                names = [("%s[%d].%s" % (pd["name"], k, f), it[f]) for k, it in enumerate(v) if isinstance(it, dict) for f in refs if isinstance(it.get(f), str)]
            else:
                continue
            for label, nm in names:
                if not nm:
                    continue
                if akey is None:
                    continue              # no image yet: the item is incomplete (placeholder / skipped), nothing is drawn from the region
                if nm not in regions:
                    err("%s.%s" % (path, label), "region %r is not defined on asset %r" % (nm, akey), "region_undefined", region=nm, asset=akey, param=pd["name"])

    def check_item_anchors(path, params, spec, t0, t1):
        """Word anchors inside the `at` fields of `items` params: they must resolve and still name the word they were set on."""
        if not isinstance(params, dict):
            return
        for name, fields in R.items_at_fields(spec):
            items = params.get(name)
            for i, it in enumerate(items if isinstance(items, list) else []):
                for f in fields:
                    a = it.get(f) if isinstance(it, dict) else None
                    if not isinstance(a, dict):
                        continue
                    ip = "%s.params.%s[%d].%s" % (path, name, i, f)
                    lab = R.item_label(it)
                    m = tm.stale(a)
                    if m:
                        err(ip, m, "item_anchor_stale", param=name, index=i, field=f, item=lab)
                    try:
                        tm.resolve(a, t0, t1)
                    except AnchorError as e:
                        err(ip, str(e), "item_anchor_invalid", param=name, index=i, field=f, item=lab)
        for name in R.at_params(spec):                  # a param that is one moment
            a = params.get(name)
            if isinstance(a, dict):
                m = tm.stale(a)
                if m:
                    err("%s.params.%s" % (path, name), m, "stale_anchor", param=name)
                try:
                    tm.resolve(a, t0, t1)
                except AnchorError as e:
                    err("%s.params.%s" % (path, name), str(e), "anchor_invalid", param=name)

    # -- end and shots ---------------------------------------------------------------------------------------
    end = sb.get("end")
    end_t = None
    if not isinstance(end, dict):
        err("end", "end anchor is required", "end_required")
    else:
        try:
            end_t = tm.resolve(end)
        except AnchorError as e:
            err("end", str(e), "anchor_invalid")
        if "fade_s" in end and not (R._is_num(end["fade_s"]) and end["fade_s"] >= 0):
            err("end.fade_s", "fade_s must be a number >= 0", "end_fade")
    shots = shots_of(sb)
    if not isinstance(shots, list):
        err("shots", "shots must be a list", "shots_not_list")
        return issues
    if not shots:
        err("shots", "a storyboard needs at least one shot", "no_shots")
    seen = set()
    starts: list = []
    for i, s in enumerate(shots):
        if not isinstance(s, dict):
            starts.append(None)
            continue
        if not isinstance(s.get("start"), dict):
            err("shots[%d].start" % i, "start anchor is required (an object like {\"t\": 12.5})", "start_required")
        try:
            starts.append(tm.resolve(s["start"]) if isinstance(s.get("start"), dict) else None)
        except (AnchorError, KeyError) as e:
            starts.append(None)
            err("shots[%d].start" % i, str(e), "anchor_invalid")
        if isinstance(s.get("start"), dict) and "rel" in s["start"]:
            err("shots[%d].start" % i, "'rel' anchors are only allowed for camera keys", "rel_anchor_not_allowed")
        elif starts[-1] is not None and starts[-1] < -EPS:
            err("shots[%d].start" % i, "start must be >= 0 s (got %.3f s)" % starts[-1], "start_negative", start=starts[-1])
    if starts and starts[0] is not None and starts[0] > 0.05:
        warn("shots[0].start", "the first shot starts at %.2f s: the beginning of the timeline is not covered" % starts[0], "first_shot_late", start=starts[0])
    for i, s in enumerate(shots):
        p = "shots[%d]" % i
        if not isinstance(s, dict):
            err(p, "shot must be an object", "shot_not_object")
            continue
        sid = s.get("id")
        if not sid or not isinstance(sid, str):
            err(p + ".id", "id is required (a string)", "id_required")
        elif sid in seen:
            err(p + ".id", "duplicate shot id %r" % sid, "duplicate_shot_id", id=sid)
        else:
            seen.add(sid)
        t0 = starts[i]
        t1 = starts[i + 1] if i + 1 < len(shots) else end_t
        if t0 is not None:
            for a in (s["start"],):
                m = tm.stale(a)
                if m:
                    err(p + ".start", m, "stale_anchor")
        if t0 is not None and t1 is not None:
            if t1 - t0 < MIN_SHOT_S - EPS:
                err(p, "shot is shorter than %.1f s (%.3f s)" % (MIN_SHOT_S, t1 - t0), "shot_too_short", min=MIN_SHOT_S, got=t1 - t0)
        if i > 0 and t0 is not None and starts[i - 1] is not None and t0 <= starts[i - 1]:
            err(p + ".start", "shots must be in time order (starts before the previous shot)", "shots_out_of_order")
        item_fields(p, s)

        tid = s.get("technique")
        spec = bundle.spec(tid)
        if spec is None:
            err(p + ".technique", "unknown technique %r" % (tid,), "unknown_technique", technique=tid)
            continue
        if spec["kind"] not in ("base", "card"):
            err(p + ".technique", "%s is a %s technique; a shot needs kind base or card" % (tid, spec["kind"]), "wrong_technique_kind", technique=tid, kind=spec["kind"], needs="base or card")
        if not bundle.available(tid):
            err(p + ".technique", "%s is not available in the engine yet" % tid, "technique_unavailable", technique=tid)
        floor = _element_floor(spec)
        if floor is not None and t0 is not None and t1 is not None and t1 - t0 < floor - EPS:
            err(p, "%s lasts %.2f s but needs at least %s s" % (tid, t1 - t0, floor), "element_too_short", technique=tid, min=floor, got=t1 - t0)
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
                        err(kp + ".at", m, "stale_anchor", param=name, index=ki)
                    try:
                        kt = tm.resolve(k["at"], t0, t1)
                    except AnchorError as e:
                        err(kp + ".at", str(e), "anchor_invalid", param=name, index=ki)
                        continue
                    if prev is not None and kt <= prev + 1e-9:
                        err(kp + ".at", "camera keys must be in strictly increasing time order", "camera_keys_order", param=name, index=ki)
                    if "rel" in k["at"] and not 0 <= k["at"]["rel"] <= 1:
                        err(kp + ".at", "rel must be between 0 and 1", "camera_rel_range", param=name, index=ki)
                    prev = kt
                    ease = k.get("ease", "linear")
                    if not isinstance(ease, str) or ease not in EASE:
                        err(kp + ".ease", "unknown ease %r" % (ease,), "unknown_ease", ease=ease if isinstance(ease, str) else str(ease), param=name, index=ki)
        check_item_anchors(p, s.get("params"), spec, t0, t1)
        # transition
        tr = s.get("transition_in")
        if tr is not None:
            tp = p + ".transition_in"
            tspec = bundle.spec(tr.get("technique")) if isinstance(tr, dict) else None
            if tspec is None:
                err(tp + ".technique", "unknown transition technique %r" % (tr.get("technique") if isinstance(tr, dict) else tr), "unknown_technique", technique=tr.get("technique") if isinstance(tr, dict) else None)
            else:
                if tspec["kind"] != "transition":
                    err(tp + ".technique", "%s is not a transition" % tr["technique"], "wrong_technique_kind", technique=tr["technique"], kind=tspec["kind"], needs="transition")
                if not bundle.available(tr["technique"]):
                    err(tp + ".technique", "%s is not available in the engine yet" % tr["technique"], "technique_unavailable", technique=tr["technique"])
                issues.extend(R.validate_params(tspec, tr.get("params") or {}, tp + ".params"))
                d = tr.get("dur")
                if not R._is_num(d) or d < 0:
                    err(tp + ".dur", "dur must be a number >= 0", "transition_dur")
                elif t0 is not None and t1 is not None and d > (t1 - t0) + EPS:
                    err(tp + ".dur", "transition is longer than the shot", "transition_too_long", dur=d, shot_dur=t1 - t0)
                if i == 0:
                    warn(tp, "the first shot has nothing to transition from", "first_shot_transition")
        # overlays
        _, akey = primary_slot(s) if isinstance(s.get("slots"), dict) else (None, None)
        regions = ((assets.get(akey) or {}).get("regions") or {}) if isinstance(akey, str) else {}
        if not isinstance(regions, dict):
            regions = {}
        check_regions(p + ".params", s.get("params"), spec, akey, regions)
        oseen = set()
        ovs = s.get("overlays")
        if ovs is not None and not isinstance(ovs, list):
            err(p + ".overlays", "overlays must be a list", "overlays_not_list")
            ovs = []
        for j, o in enumerate(ovs or []):
            op = "%s.overlays[%d]" % (p, j)
            if not isinstance(o, dict):
                err(op, "overlay must be an object", "overlay_not_object")
                continue
            oid = o.get("id")
            if isinstance(oid, str) and oid in oseen:
                err(op + ".id", "duplicate overlay id %r" % oid, "duplicate_overlay_id", id=oid)
            if isinstance(oid, str):
                oseen.add(oid)
            ospec = bundle.spec(o.get("technique"))
            if ospec is None:
                err(op + ".technique", "unknown technique %r" % (o.get("technique"),), "unknown_technique", technique=o.get("technique") if isinstance(o.get("technique"), str) else None)
                continue
            if ospec["kind"] != "overlay":
                err(op + ".technique", "%s is a %s technique; an overlay needs kind overlay" % (o["technique"], ospec["kind"]), "wrong_technique_kind", technique=o["technique"], kind=ospec["kind"], needs="overlay")
            if not bundle.available(o["technique"]):
                err(op + ".technique", "%s is not available in the engine yet" % o["technique"], "technique_unavailable", technique=o["technique"])
            issues.extend(R.validate_params(ospec, o.get("params") or {}, op + ".params"))
            check_asset_params(op + ".params", o.get("params"), ospec)
            check_slots(op + ".slots", o.get("slots"), ospec, o["technique"])
            for what, name in missing_of(ospec, o, "overlay", s):
                if what == "slot":
                    incomplete(op + ".slots", "slot", name, o["technique"])
            oparams = o.get("params") if isinstance(o.get("params"), dict) else {}
            check_regions(op + ".params", oparams, ospec, akey, regions)
            item_fields(op, o)
            if oid is not None and not (isinstance(oid, str) and oid):
                err(op + ".id", "id must be a non-empty string", "id_required")
            names = {pd["name"] for pd in ospec["params"]}
            if {"at", "screen", "text"} <= names and oparams.get("at") is None and oparams.get("screen") is None:
                warn(op + ".params", "neither `at` nor `screen` is set: the label has no position and is not drawn", "label_without_position")
            try:
                ot0 = tm.resolve(o["start"]) if isinstance(o.get("start"), dict) else None
                if ot0 is None:
                    err(op + ".start", "start anchor is required", "start_required")
                else:
                    m = tm.stale(o["start"])
                    if m:
                        err(op + ".start", m, "stale_anchor")
                    if "rel" in o["start"]:
                        err(op + ".start", "'rel' anchors are only allowed for camera keys", "rel_anchor_not_allowed")
            except AnchorError as e:
                ot0 = None
                err(op + ".start", str(e), "anchor_invalid")
            ot1 = None
            if isinstance(o.get("end"), dict):
                try:
                    ot1 = tm.resolve(o["end"])
                    m = tm.stale(o["end"])
                    if m:
                        err(op + ".end", m, "stale_anchor")
                except AnchorError as e:
                    err(op + ".end", str(e), "anchor_invalid")
            elif o.get("dur") is not None:
                if not R._is_num(o["dur"]) or o["dur"] <= 0:
                    err(op + ".dur", "dur must be a number > 0", "overlay_dur")
                elif ot0 is not None:
                    ot1 = ot0 + o["dur"]
            elif t1 is not None:
                ot1 = t1
            check_item_anchors(op, oparams, ospec, ot0, ot1)
            ofloor = _element_floor(ospec)
            if ofloor is not None and ot0 is not None and ot1 is not None and ot1 - ot0 < ofloor - EPS:
                err(op, "%s lasts %.2f s but needs at least %s s" % (o["technique"], ot1 - ot0, ofloor), "element_too_short", technique=o["technique"], min=ofloor, got=ot1 - ot0)
            if ot0 is not None and t0 is not None and t1 is not None:
                if ot0 < t0 - EPS or ot0 >= t1 - EPS:
                    err(op + ".start", "overlay starts outside its shot (%.2f s; shot spans %.2f-%.2f s)" % (ot0, t0, t1), "overlay_outside_shot", start=ot0, shot_start=t0, shot_end=t1)
                elif ot1 is not None and ot1 > t1 + EPS:
                    err(op, "overlay ends outside its shot (%.2f s > %.2f s)" % (ot1, t1), "overlay_outside_shot", end=ot1, shot_start=t0, shot_end=t1)
                if ot1 is not None and ot1 <= ot0:
                    err(op, "overlay ends before it starts", "overlay_ends_before_start")
    if end_t is not None and starts and starts[-1] is not None and end_t <= starts[-1]:
        err("end", "end is not after the last shot start", "end_before_last_start")
    if end_t is not None and tm.duration and end_t > tm.duration + 1.0:
        warn("end", "end %.2f s is after the audio/timing duration %.2f s" % (end_t, tm.duration), "end_after_audio", end=end_t, duration=tm.duration)
    _check_identity(sb, shots, bundle, err, warn)
    return issues


# Families whose elements must last at least their technique's `timing.min_s`: the channel identity (`ID-`, contract
# 2026-11-18-identity-raking-light, "an element is never shorter than 1.5 s") and the explanatory components of
# docs/design/2026-11-18-explainer-components.md (section 2: an element shorter than its `timing.min_s` is `element_too_short`).
ELEMENT_FLOOR_FAMILIES = ("ID-", "MAP-", "KEY-", "TIME-", "NUM-", "TREE-", "STATE-", "DOC-")


def _element_floor(spec: dict) -> float | None:
    """The shortest an element of those families (a technique whose id starts with one of `ELEMENT_FLOOR_FAMILIES`) may be: the
    registry's `timing.min_s` of that technique; None for any other technique."""
    tid = spec.get("id")
    if not (isinstance(tid, str) and tid.startswith(ELEMENT_FLOOR_FAMILIES)):
        return None
    m = (spec.get("timing") or {}).get("min_s")
    return float(m) if R._is_num(m) and m > 0 else None


def _check_identity(sb: dict, shots: list, bundle: R.StyleBundle, err, warn) -> None:
    """The optional top-level `identity: {"style": ...}` (contract 2026-11-18, section 5 and 6): the style must be one the style.json
    block lists (error), and a structure shot whose technique is part of the identity but not of the chosen style is a warning."""
    ident = sb.get("identity")
    if ident is None:
        return
    from bti.identity import config as IDC
    cfg = IDC.read(bundle.style)
    allowed = cfg.ids() if cfg else []
    sid = ident.get("style") if isinstance(ident, dict) else None
    if not isinstance(ident, dict):
        err("identity", "identity must be an object like {\"style\": \"%s\"}" % (allowed[0] if allowed else "raking"), "identity_style_unknown", style=None, allowed=allowed)
        return
    if not isinstance(sid, str) or sid not in allowed:
        err("identity.style", "unknown identity style %r (choose one of: %s)" % (sid, ", ".join(allowed) or "none: this style has no identity block"),
            "identity_style_unknown", style=sid if isinstance(sid, str) else None, allowed=allowed)
        return
    sd = cfg.style(sid)
    for i, s in enumerate(shots):
        if isinstance(s, dict) and s.get("intent") == "structure" and IDC.is_mismatch(cfg, sid, s.get("technique")):
            t = s.get("technique")
            wanted = sd.brand if (t in IDC.LEGACY_TITLE or cfg.is_family(t, "brand")) else sd.mark
            warn("shots[%d].technique" % i, "%s does not belong to the identity style %r; its %s is %s" % (t, sid, "channel-name beat" if wanted == sd.brand else "chapter mark", wanted),
                 "identity_technique_mismatch", shot=s.get("id"), technique=t, style=sid, wanted=wanted)
