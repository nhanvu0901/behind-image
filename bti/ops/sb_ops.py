"""The operations of the storyboard document (`projects/<pid>/storyboard.json`, schema `bti.storyboard/1`, step 5).

The field names are the ones the document uses: `shot`, `overlay`, `technique`, `params`, `slots`, `start` (an anchor: `{t}` or
`{w, off, text}`), `dur`, `end`, `intent`, `note`, `locked`. A shot lasts from its `start` to the `start` of the next shot (the
last one to `end`), so splitting, merging and moving a boundary are changes of `start`. The editing rules of the page (what a
split does to the camera keys and to the overlays, what a merge keeps) are the page's own, ported in `bti.ops.timeline`.
Every operation checks its fields against the document as the earlier operations of the batch left it and refuses with a typed
error that says what to change; the engine's own validation then judges the whole result (see `bti.ops.batch`).
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any

from bti.engine import registry as R
from bti.engine import storyboard as SB

from . import schemacheck as S
from .registry import op
from .timeline import MIN_SHOT, camera_lists, fmt_time, is_num, jround

INTENTS = list(SB.INTENTS)
_ID = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"
_REF = r"\$[A-Za-z][A-Za-z0-9_]{0,31}"
SHOT = S.string("A shot id of the storyboard (such as s0012), or a $ref made by an earlier operation of the batch.",
                pattern=r"^(%s|%s)$" % (_REF, _ID), hint="a shot id like s0012, or a $name made by an earlier operation")
OVERLAY = S.string("An overlay id of that shot (such as o2), or a $ref made by an earlier add_overlay.",
                   pattern=r"^(%s|%s)$" % (_REF, _ID), hint="an overlay id like o2, or a $name made by an earlier add_overlay")
TECH = S.string("A technique id of the style registry, such as CAM-01 or HI-01.", pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$",
                hint="a technique id like CAM-01")
REF = S.string("A name for what this operation creates; later operations of the batch write it as $name.",
               pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$", hint="a name of letters, digits and _, starting with a letter")
NOTE = S.string("A short note (up to 400 characters).", max_length=400)
INTENT = S.string("What the shot or overlay is for.", enum=INTENTS)
ANCHOR = S.plain_object({
    "t": S.number("A time in seconds from the start of the audio.", minimum=0),
    "w": S.integer("A word of the narration, by its index in timing.json.", minimum=0),
    "off": S.number("Seconds after (or before, when negative) the start of that word."),
    "text": S.string("The word itself (checked against the index; filled in when left out).", max_length=80)},
    description="An anchor in time: {\"t\": seconds} or {\"w\": word index, \"off\": seconds}.",
    title="an anchor {t} or {w, off?, text?}")
ANCHOR["anyOf"] = [{"required": ["t"]}, {"required": ["w"]}]
AT = S.any_of(S.number("seconds", minimum=0), ANCHOR, title="seconds or an anchor",
              description="A time: a number of seconds (snapped to a word start within 0.35 s unless snap is false) or an anchor object.")
SNAP = S.boolean("Snap a time given in seconds to the nearest word start within 0.35 s (default true); false keeps the exact time.")
SLOTS = S.free_object("Slots by name, `{slot: {\"asset\": key}}` (a text slot takes `{\"text\": ...}`).")
OVERLAY_FIELDS = {
    "technique": TECH,
    "start": S.any_of(ANCHOR, title="an anchor", description="When the overlay starts; default: the start of the shot."),
    "dur": S.number("How long it lasts, in seconds; cut to the end of the shot if longer. Leave out for HI-01 to run to the end of its shot (others default to 3 s).", exclusive_minimum=0),
    "end": S.any_of(ANCHOR, title="an anchor", description="When it ends (instead of dur); cut to the end of the shot if later."),
    "params": S.free_object("Parameters by name; those not given take the defaults of the technique."),
    "slots": SLOTS, "intent": INTENT, "note": NOTE}
EPS = 1e-6


# ---------------------------------------------------------------- finding things
def _find(ctx, value, field: str = "shot") -> tuple[int, dict]:
    sid = ctx.resolve(value, "shot", field)
    for i, s in enumerate(ctx.doc["shots"]):
        if s.get("id") == sid:
            return i, s
    ctx.bad(field, "no shot %r in the storyboard" % str(sid)[:40], allowed=[s.get("id") for s in ctx.doc["shots"]], code="unknown_shot")
    raise AssertionError("unreachable")


def _guard(ctx, shot: dict, field: str = "shot", *, allow_locked: bool = False) -> None:
    """The scope, then the lock: every operation on a shot passes here (a locked shot refuses all but `unlock`)."""
    ctx.in_scope(shot["id"], field, "shot")
    if shot.get("locked") is True and not allow_locked:
        ctx.bad(field, "shot %s is locked" % shot["id"], code="locked", shot=shot["id"])


def _overlay(ctx, shot: dict, value, field: str = "overlay") -> dict:
    ref_shot = ctx.ref_shot(value)
    oid = ctx.resolve(value, "overlay", field)
    if ref_shot is not None and ref_shot != shot["id"]:
        ctx.bad(field, "the ref %s is an overlay of shot %s, not of %s" % (value, ref_shot, shot["id"]), code="unknown_overlay")
    for o in shot.get("overlays") or []:
        if o.get("id") == oid:
            return o
    ctx.bad(field, "shot %s has no overlay %r" % (shot["id"], str(oid)[:40]), allowed=[o.get("id") for o in shot.get("overlays") or []],
            code="unknown_overlay")
    raise AssertionError("unreachable")


def _tail(i: Any) -> int:
    m = re.search(r"(\d+)$", str(i))
    return int(m.group(1)) if m else 0


def next_shot_ids(doc: dict, k: int = 1) -> list[str]:
    """`k` fresh shot ids: one more than the largest number in use, padded to four digits (the page's `nextShotId`)."""
    n = max([_tail(s.get("id")) for s in doc.get("shots") or []] + [0])
    return ["s%s" % str(n + 1 + j).zfill(4) for j in range(k)]


def _overlay_floor(doc: dict) -> int:
    return max([_tail(o.get("id")) for s in doc.get("shots") or [] for o in s.get("overlays") or []] + [0])


def next_overlay_id(doc: dict) -> str:
    """The page's `nextOverlayId`: `o` and one more than the largest overlay number anywhere in the storyboard."""
    return "o%d" % (_overlay_floor(doc) + 1)


def _tech(ctx, tid: str, kinds: tuple, field: str = "technique", *, existing: bool = False) -> dict:
    """The registry entry of a technique an operation names, or the refusal. `existing`: the technique is one the shot or the overlay ALREADY has (an operation that only
    changes its parameters or its pictures): never refused for being hidden, the stored storyboards use hidden techniques.

    A batch written by an agent (an actor that is not `human`: `agent:<model id>` or `cli:<name>`, see `Ctx.source`) may only NAME a technique that is offered to models
    (`offered` of the registry, the catalogue of `inputs/techniques.md`): a hidden one is the error `technique_not_offered`, which says why and what to use instead (`use`).
    A batch of a person (the page, the actor `human`) may use any technique that exists."""
    b = ctx.facts.bundle
    spec = b.spec(tid)
    usable = [t["id"] for t in b.techniques if t["kind"] in kinds and b.available(t["id"])]
    if spec is None:
        ctx.bad(field, "no technique %r in the style registry" % str(tid)[:40], allowed=usable, code="unknown_technique")
    if ctx.source == "agent" and not existing and not b.offered(tid):
        use = [u for u in ((spec.get("hidden_reason") or {}).get("use") or []) if b.offered(u)]
        ctx.bad(field, b.not_offered_text(tid), allowed=[t for t in usable if b.offered(t)], code="technique_not_offered", technique=tid, use=use)
    if spec["kind"] not in kinds:
        ctx.bad(field, "%s is a %s technique; a %s technique is needed here" % (tid, spec["kind"], " or ".join(kinds)),
                allowed=usable, code="wrong_technique_kind")
    if not b.available(tid):
        ctx.bad(field, "%s is not available in the engine yet" % tid, allowed=usable, code="technique_unavailable")
    return spec


def _label(ctx, tid: str) -> str:
    return ((ctx.facts.bundle.spec(tid) or {}).get("label_vi") or tid)


def _span(ctx, i: int) -> tuple[float, float]:
    t0, t1 = ctx.facts.timeline.spans(ctx.doc)[i]
    if t0 is None or t1 is None:
        ctx.bad("shot", "the shot %s has no resolvable start or end in time, so the operation cannot place anything in it"
                % ctx.doc["shots"][i].get("id"))
    return t0, t1


def _when(ctx, shot: dict) -> str | None:
    return fmt_time(ctx.facts.timeline.resolve(shot.get("start")))


def _mark(ctx, item: dict) -> None:
    item["source"] = ctx.source


def _stale_note(shot: dict) -> None:
    """A shot that now shows something else (another technique, another main picture) no longer has the reason it was written for: its `note`
    ("over the squirrel photo") is cleared, so the owner never reads a reason that is not true. Camera, parameter and overlay changes keep it."""
    if shot.get("note"):
        shot["note"] = ""


# ---------------------------------------------------------------- slots and parameters
def _asset_kind(a: Any) -> str:
    return "video" if isinstance(a, dict) and a.get("kind") == "video" else "mask" if isinstance(a, dict) and a.get("kind") == "mask" else "image"


def _fits(sd: dict, asset: Any) -> bool:
    k = SB.slot_kind(sd)
    return k is not None and asset is not None and k == _asset_kind(asset)


def carry_slots(new_slots: list, old_slots: Any, assets: dict) -> dict:
    """The slots a shot (or overlay) keeps when its technique changes (the page's `carrySlots`): same-name slots stay when the asset
    still fits; empty image slots then take the old image assets in order, never a picture into a video or mask slot."""
    old = old_slots if isinstance(old_slots, dict) else {}
    out: dict = {}
    used: set = set()
    for sd in new_slots:
        cur = old.get(sd["name"])
        if not isinstance(cur, dict) or not cur:
            continue
        if SB.slot_kind(sd) is None:                                   # a text slot
            if cur.get("text") is not None:
                out[sd["name"]] = dict(cur)
            continue
        if cur.get("asset") and _fits(sd, assets.get(cur["asset"])):
            out[sd["name"]] = dict(cur)
            used.add(cur["asset"])
    spare = [v["asset"] for v in old.values() if isinstance(v, dict) and v.get("asset") and _asset_kind(assets.get(v["asset"])) == "image"
             and v["asset"] not in used]
    i = 0
    for sd in new_slots:
        if sd["name"] in out or SB.slot_kind(sd) != "image" or i >= len(spare):
            continue
        out[sd["name"]] = {"asset": spare[i]}
        i += 1
    return out


def _check_one_slot(ctx, spec: dict, name: str, v: Any, f_name: str, f_value: str, f_asset: str) -> dict:
    """One slot given by an operation, checked against the technique's slots and the assets of the storyboard; returns it clean."""
    sdefs = {s["name"]: s for s in spec["slots"]}
    if name not in sdefs:
        ctx.bad(f_name, "%r is not a slot of %s" % (name, spec["id"]), allowed=sorted(sdefs), code="unknown_slot")
    sd = sdefs[name]
    if SB.slot_kind(sd) is None:
        if not isinstance(v, dict) or not isinstance(v.get("text"), str):
            ctx.bad(f_value, "a text slot takes {\"text\": \"...\"}")
        return {"text": v["text"]}
    if not isinstance(v, dict) or not isinstance(v.get("asset"), str) or set(v) - {"asset"}:
        ctx.bad(f_value, "must be {\"asset\": <asset key>}")
    key = ctx.resolve(v["asset"], "asset", f_asset)
    if key not in ctx.doc["assets"]:
        ctx.bad(f_asset, "no asset %r in the storyboard" % str(key)[:40], allowed=sorted(ctx.doc["assets"]), code="unknown_asset")
    accepted = list(SB.slot_accepts(sd))
    got = ctx.doc["assets"][key].get("kind")
    if got in ("image", "video", "mask") and got not in accepted:
        ctx.bad(f_asset, "slot %r takes %s but asset %r is a %s" % (name, " or ".join(accepted), key, got), allowed=accepted,
                code="slot_kind_mismatch")
    return {"asset": key}


def _check_slots(ctx, spec: dict, slots: dict, base: str) -> dict:
    """The slots given by an operation (`{name: {"asset": key}}`), checked; returns them clean."""
    return {name: _check_one_slot(ctx, spec, name, v, "%s.%s" % (base, name), "%s.%s" % (base, name), "%s.%s.asset" % (base, name))
            for name, v in slots.items()}


def _primary_asset(shot: dict, item: dict | None = None) -> str | None:
    """The asset whose regions a `point` parameter names: the item's own picture, else its shot's."""
    for it in (item, shot):
        if isinstance(it, dict) and isinstance(it.get("slots"), dict):
            key = SB.primary_slot(it)[1]
            if key:
                return key
    return None


def _check_param(ctx, spec: dict, name: str, value: Any, field: str, akey: str | None) -> None:
    defs = {p["name"]: p for p in spec["params"]}
    if name not in defs:
        ctx.bad(field, "%r is not a parameter of %s" % (name, spec["id"]), allowed=sorted(defs), code="unknown_param")
    p = defs[name]
    m = R.check_problem(p, value)
    if m:
        ctx.bad(field, m[2], allowed=m[1].get("values") if m[0] == "param_not_in_values" else None)
    if p.get("numeric_only") or not akey:
        return
    if p["type"] == "point" and isinstance(value, str):
        names = [value]
    elif p["type"] == "points" and isinstance(value, list):
        names = [x for x in value if isinstance(x, str)]
    else:
        return
    regs = (ctx.doc["assets"].get(akey) or {}).get("regions") or {}
    for nm in names:
        if nm and nm not in regs:
            ctx.bad(field, "no region %r on asset %r" % (nm, akey), allowed=sorted(regs), code="unknown_region")


def _assets_ctx(doc: dict, slots: dict) -> dict:
    out = {}
    for v in (slots or {}).values():
        k = v.get("asset") if isinstance(v, dict) else None
        a = doc["assets"].get(k) if k else None
        if isinstance(a, dict):
            out[k] = {"width": a.get("width"), "height": a.get("height"), "title": a.get("title"), "artist": a.get("artist"),
                      "year": a.get("year"), "regions": a.get("regions") or {}}
    return out


def _defaults(ctx, tid: str, item_kind: str, shot: dict, slots: dict, duration: float, camera: dict | None = None) -> dict:
    """The parameters a freshly chosen technique starts with: what `POST /api/projects/{pid}/defaults` gives for the context the
    page sends (item, shot_id, duration, slots, assets, canvas, camera)."""
    context: dict = {"item": item_kind, "shot_id": shot.get("id"), "duration": duration, "slots": slots,
                     "assets": _assets_ctx(ctx.doc, slots), "canvas": ctx.doc.get("canvas")}
    if camera:
        context["camera"] = camera
    return copy.deepcopy(ctx.facts.defaults(tid, context) or {})


def _camera_now(ctx, shot: dict, t0: float, t1: float) -> dict | None:
    for _, keys in camera_lists(shot.get("params")):
        pose = ctx.facts.timeline.pose_at_start(keys, t0, t1)
        if pose:
            return pose
    return None


def _region_of(ctx, params: Any, akey: str | None) -> str | None:
    """The region an item looks at (the first `point` parameter that names one), as a short phrase for a sentence."""
    for k, v in (params or {}).items():
        if isinstance(v, str) and v and k in ("at", "region", "focus", "target"):
            a = (ctx.doc["assets"].get(akey) or {}).get("regions") or {} if akey else {}
            lab = (a.get(v) or {}).get("label")
            return lab.strip() if isinstance(lab, str) and lab.strip() and lab.strip() != v else v.replace("_", " ")
    return None


# ---------------------------------------------------------------- time checks
def _anchor_arg(ctx, value, field: str, *, snap: bool = True) -> tuple[dict, float]:
    a, problem = ctx.facts.timeline.anchor_for(value, snap)
    if problem:
        ctx.bad(field, problem)
    t = ctx.facts.timeline.resolve(a)
    if t is None:
        ctx.bad(field, "the anchor cannot be resolved to a time")
    return a, t


def _cut_dur(ot0: float, t1: float) -> float:
    """Duration from `ot0` to `t1`, rounded down to milliseconds so `ot0 + dur <= t1` never fails engine validation."""
    rem = t1 - ot0
    d = math.floor(rem * 1000.0 + 1e-9) / 1000.0
    return d if d > 0 else rem


def _overlay_window(ctx, ot0: float, ot1: float, t0: float, t1: float, field: str, shot_id: str, end_name: str = "dur") -> tuple[float, bool]:
    """An overlay lies inside its shot [t0, t1]; an end past `t1` is cut to `t1`. Returns `(clamped_ot1, was_cut)`."""
    def at(name: str) -> str:
        return "%s.%s" % (field, name) if field else name
    if ot0 < t0 - EPS or ot0 >= t1 - EPS:
        ctx.bad(at("start"), "starts at %.2f s, outside shot %s (%.2f to %.2f s)" % (ot0, shot_id, t0, t1))
    if ot1 <= ot0 + EPS:
        ctx.bad(at(end_name), "an overlay must last longer than 0 seconds")
    if ot1 > t1 + EPS:
        return t1, True
    return ot1, False


def _build_overlay(ctx, shot: dict, spec_o: dict, t0: float, t1: float, oid: str, base: str, *, existing: bool = False) -> tuple[dict, bool]:
    """A new overlay inside `shot` (which spans [t0, t1]) from the fields of an add_overlay: the page's `addOverlay`, plus the
    checks, cutting any end past `t1` to the shot. `base` is the field prefix of the errors ('' or 'shots[1].overlays[0].')."""
    tl = ctx.facts.timeline
    spec = _tech(ctx, spec_o["technique"], ("overlay",), base + "technique", existing=existing)
    if spec_o.get("start") is not None:
        a, ot0 = _anchor_arg(ctx, spec_o["start"], base + "start")
    else:
        a = copy.deepcopy(shot["start"]) if isinstance(shot.get("start"), dict) else {"t": t0}
        ot0 = tl.resolve(a)
        if ot0 is None:
            a, ot0 = {"t": jround(t0, 3)}, t0
    if ot0 < t0 - EPS or ot0 >= t1 - EPS:
        ctx.bad(base + "start", "starts at %.2f s, outside shot %s (%.2f to %.2f s)" % (ot0, shot["id"], t0, t1))
    if spec_o.get("dur") is not None and spec_o.get("end") is not None:
        ctx.bad(base + "end", "give dur or end, not both")
    ov: dict = {"id": oid, "technique": spec_o["technique"], "intent": spec_o.get("intent") or (spec.get("intents") or [None])[0],
                "start": a}
    cut = False
    has_len = spec_o.get("end") is not None or spec_o.get("dur") is not None
    if spec_o.get("end") is not None:
        e, ot1 = _anchor_arg(ctx, spec_o["end"], base + "end")
        ot1, cut = _overlay_window(ctx, ot0, ot1, t0, t1, base.rstrip("."), shot["id"], "end")
        if cut:
            dur = _cut_dur(ot0, t1)
            ov["dur"] = dur
            ot1 = ot0 + dur
        else:
            ov["end"] = e
    elif spec_o.get("dur") is not None:
        dur = float(spec_o["dur"])
        ot1, cut = _overlay_window(ctx, ot0, ot0 + dur, t0, t1, base.rstrip("."), shot["id"], "dur")
        if cut:
            dur = _cut_dur(ot0, t1)
            ot1 = ot0 + dur
        ov["dur"] = dur
    elif spec_o["technique"] != "HI-01":
        dur = min(3.0, _cut_dur(ot0, t1))
        ov["dur"] = dur
        ot1 = ot0 + dur
    else:
        ot1 = t1
    slots = _check_slots(ctx, spec, spec_o["slots"], base + "slots") if spec_o.get("slots") else {}
    shot_slots = {**(shot.get("slots") or {}), **slots}
    given = spec_o.get("params") or {}
    akey = _primary_asset(shot, {"slots": slots}) if slots else _primary_asset(shot)
    for name, v in given.items():
        if v is not None:
            _check_param(ctx, spec, name, v, "%sparams.%s" % (base, name), akey)
        elif name not in {p["name"] for p in spec["params"]}:
            ctx.bad("%sparams.%s" % (base, name), "%r is not a parameter of %s" % (name, spec["id"]),
                    allowed=sorted(p["name"] for p in spec["params"]), code="unknown_param")
    params = _defaults(ctx, spec_o["technique"], "overlay", shot, shot_slots, max(0.0, ot1 - ot0))
    params.update({k: v for k, v in given.items() if v is not None})
    if not has_len and spec_o["technique"] == "HI-01":
        from bti.draft.defaults import overlay_default_window
        win0, win1 = overlay_default_window("HI-01", ot0, t0, t1, params, [], None)
        if win1 <= win0 + EPS:
            win0, win1 = ot0, t1
        if abs(win0 - ot0) > EPS:
            if "w" in a:
                a = dict(a, off=jround(win0 - float(tl.words[a["w"]]["s"]), 4))
            else:
                a = {"t": jround(win0, 3)}
            resolved = tl.resolve(a)
            if resolved is None or resolved < t0 - EPS:
                a = {"t": jround(max(t0, win0), 3)}
                ot0 = a["t"]
            else:
                ot0 = resolved
            ov["start"] = a
        dur = _cut_dur(ot0, min(t1, win1))
        ov["dur"] = dur
        ot1 = ot0 + dur
    ov["params"] = params
    if slots:
        ov["slots"] = slots
    ov.update({"locked": False, "source": ctx.source, "note": spec_o.get("note") or ""})
    return ov, cut


# ---------------------------------------------------------------- operations: technique, parameters, slots
@op("storyboard", "set_technique",
    summary="Change the technique of a shot. Parameters not given take the defaults of the new technique (the same as POST .../defaults); "
            "slots that still fit are kept; the shot's note (the reason written for the old treatment) is cleared.",
    schema=S.obj("set_technique", ["shot", "technique"], {
        "shot": SHOT, "technique": TECH,
        "params": S.free_object("Parameters of the new technique that differ from its defaults."),
        "intent": INTENT}),
    example={"op": "set_technique", "shot": "s0004", "technique": "CAM-03"},
    sentences="Cảnh {n}: đổi kỹ thuật sang {technique}")
def set_technique(ctx, o):
    i, shot = _find(ctx, o["shot"])
    _guard(ctx, shot)
    spec = _tech(ctx, o["technique"], ("base", "card"), existing=o["technique"] == shot.get("technique"))
    t0, t1 = _span(ctx, i)
    slots = carry_slots(spec["slots"], shot.get("slots"), ctx.doc["assets"])
    akey = _primary_asset({"slots": slots})
    given = o.get("params") or {}
    for name, v in given.items():
        if v is None:
            if name not in {p["name"] for p in spec["params"]}:
                ctx.bad("params.%s" % name, "%r is not a parameter of %s" % (name, spec["id"]),
                        allowed=sorted(p["name"] for p in spec["params"]), code="unknown_param")
        else:
            _check_param(ctx, spec, name, v, "params.%s" % name, akey)
    params = _defaults(ctx, o["technique"], "shot", shot, slots, t1 - t0, _camera_now(ctx, shot, t0, t1))
    params.update({k: v for k, v in given.items() if v is not None})
    ctx.touch("shot:" + shot["id"])
    shot["technique"], shot["params"], shot["slots"] = o["technique"], params, slots
    _stale_note(shot)
    intents = spec.get("intents") or []
    if o.get("intent"):
        shot["intent"] = o["intent"]
    elif shot.get("intent") not in intents and intents:
        shot["intent"] = intents[0]
    _mark(ctx, shot)
    ctx.say({"shot": shot["id"]}, _when(ctx, shot), n=i + 1, technique=_label(ctx, o["technique"]))


@op("storyboard", "set_params",
    summary="Change some parameters of a shot or of one of its overlays. A value of null returns that parameter to its default.",
    schema=S.obj("set_params", ["shot", "params"], {
        "shot": SHOT,
        "overlay": OVERLAY,
        "params": S.free_object("Parameters by name; a null value returns the parameter to its default.", min_properties=1)}),
    example={"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 260, "ry": 260}},
    sentences={"default": "Cảnh {n}: đổi thiết lập {names}", "overlay": "Cảnh {n}: đổi thiết lập {names} của lớp phủ {technique}"})
def set_params(ctx, o):
    i, shot = _find(ctx, o["shot"])
    _guard(ctx, shot)
    t0, t1 = _span(ctx, i)
    ov = _overlay(ctx, shot, o["overlay"]) if o.get("overlay") is not None else None
    item = ov if ov is not None else shot
    if ov is not None and ov.get("locked") is True:
        ctx.bad("overlay", "overlay %s of shot %s is locked" % (ov.get("id"), shot["id"]), code="locked", shot=shot["id"], overlay=ov.get("id"))
    spec = _tech(ctx, item.get("technique"), ("overlay",) if ov is not None else ("base", "card"), "overlay" if ov is not None else "shot", existing=True)
    akey = _primary_asset(shot, ov)
    wanted_default = []
    for name, v in o["params"].items():
        f = "params.%s" % name
        if v is None:
            if name not in {p["name"] for p in spec["params"]}:
                ctx.bad(f, "%r is not a parameter of %s" % (name, spec["id"]), allowed=sorted(p["name"] for p in spec["params"]),
                        code="unknown_param")
            wanted_default.append(name)
        else:
            _check_param(ctx, spec, name, v, f, akey)
    defaults: dict = {}
    if wanted_default:
        if ov is not None:
            ot0, ot1 = ctx.facts.timeline.overlay_span(ov, t0, t1)
            defaults = _defaults(ctx, item["technique"], "overlay", shot, {**(shot.get("slots") or {}), **(ov.get("slots") or {})}, ot1 - ot0)
        else:
            defaults = _defaults(ctx, item["technique"], "shot", shot, shot.get("slots") or {}, t1 - t0)
    ctx.touch("shot:" + shot["id"])
    params = item.setdefault("params", {})
    for name, v in o["params"].items():
        if v is None:
            d = defaults.get(name)
            if d is None:
                params.pop(name, None)
            else:
                params[name] = d
        else:
            params[name] = v
    _mark(ctx, item)
    names = ", ".join(o["params"])
    if ov is not None:
        ctx.say({"shot": shot["id"], "overlay": ov["id"]}, _when(ctx, shot), "overlay", n=i + 1, names=names, technique=_label(ctx, ov["technique"]))
    else:
        ctx.say({"shot": shot["id"]}, _when(ctx, shot), n=i + 1, names=names)


@op("storyboard", "set_slot",
    summary="Put an asset into a slot of a shot or overlay (or empty the slot with asset null). When the main picture of a shot changes, "
            "its camera keys are fitted to the new picture the way the page does and its note (the reason written for the old picture) is cleared.",
    schema=S.obj("set_slot", ["shot", "slot", "asset"], {
        "shot": SHOT, "overlay": OVERLAY,
        "slot": S.string("A slot name of the technique, such as image.", pattern=r"^[A-Za-z0-9_]{1,40}$", hint="a slot name like image"),
        "asset": S.string("An asset key of the storyboard, or null to empty the slot.", nullable=True, max_length=64)}),
    example={"op": "set_slot", "shot": "s0004", "slot": "image", "asset": "C"},
    sentences={"default": "Cảnh {n}: đổi ô {slot} sang {pic}", "clear": "Cảnh {n}: bỏ hình ở ô {slot}",
               "overlay": "Cảnh {n}: đổi ô {slot} của lớp phủ {technique} sang {pic}",
               "overlay_clear": "Cảnh {n}: bỏ hình ở ô {slot} của lớp phủ {technique}"})
def set_slot(ctx, o):
    i, shot = _find(ctx, o["shot"])
    _guard(ctx, shot)
    ov = _overlay(ctx, shot, o["overlay"]) if o.get("overlay") is not None else None
    if ov is not None and ov.get("locked") is True:
        ctx.bad("overlay", "overlay %s of shot %s is locked" % (ov.get("id"), shot["id"]), code="locked", shot=shot["id"], overlay=ov.get("id"))
    item = ov if ov is not None else shot
    spec = _tech(ctx, item.get("technique"), ("overlay",) if ov is not None else ("base", "card"), "overlay" if ov is not None else "shot", existing=True)
    if o["asset"] is None:
        if o["slot"] not in {s["name"] for s in spec["slots"]}:
            ctx.bad("slot", "%r is not a slot of %s" % (o["slot"], spec["id"]), allowed=sorted(s["name"] for s in spec["slots"]),
                    code="unknown_slot")
        new = None
    else:
        new = _check_one_slot(ctx, spec, o["slot"], {"asset": o["asset"]}, "slot", "asset", "asset")
    t0, t1 = _span(ctx, i)
    was_primary = SB.primary_slot(shot)[0] if ov is None else None
    old_asset = ((item.get("slots") or {}).get(o["slot"]) or {}).get("asset")
    ctx.touch("shot:" + shot["id"])
    slots = item.setdefault("slots", {})
    if new is None:
        slots.pop(o["slot"], None)
    else:
        slots[o["slot"]] = new
    if ov is None and new is not None and new.get("asset") != old_asset and (was_primary in (None, o["slot"])):
        _stale_note(shot)
        cams = [p["name"] for p in spec["params"] if p["type"] == "camera"]
        if cams:                                                      # the page's `cameraRefit`: the keys were in the old picture's pixels
            fresh = _defaults(ctx, shot["technique"], "shot", shot, shot["slots"], t1 - t0)
            for n in cams:
                if fresh.get(n):
                    shot.setdefault("params", {})[n] = fresh[n]
    _mark(ctx, item)
    if ov is not None:
        ctx.say({"shot": shot["id"], "overlay": ov["id"]}, _when(ctx, shot), "overlay" if new else "overlay_clear", n=i + 1, slot=o["slot"],
                technique=_label(ctx, ov["technique"]), pic=ctx.pic(new["asset"]) if new and "asset" in new else "")
    else:
        ctx.say({"shot": shot["id"]}, _when(ctx, shot), "default" if new else "clear", n=i + 1, slot=o["slot"],
                pic=ctx.pic(new["asset"]) if new and "asset" in new else "")


# ---------------------------------------------------------------- operations: overlays
@op("storyboard", "add_overlay",
    summary="Add an overlay (a ring of light, a label, an arrow...) to a shot. Parameters not given take the defaults of the technique; "
            "it starts at the start of the shot and, when dur and end are left out, HI-01 runs to the end of its shot while others last 3 s. "
            "A length past the end of the shot is cut to the shot.",
    schema=S.obj("add_overlay", ["shot", "technique"], {"shot": SHOT, "ref": REF, **OVERLAY_FIELDS}),
    example={"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "params": {"at": "CENTRE", "rx": 220, "ry": 220},
             "start": {"w": 70}, "dur": 4, "ref": "ring"},
    sentences={"default": "Cảnh {n}: thêm lớp phủ {technique}", "region": "Cảnh {n}: thêm lớp phủ {technique} ở vùng {region}",
               "default_cut": "Cảnh {n}: thêm lớp phủ {technique} (cắt đến hết cảnh)",
               "region_cut": "Cảnh {n}: thêm lớp phủ {technique} ở vùng {region} (cắt đến hết cảnh)"})
def add_overlay(ctx, o):
    i, shot = _find(ctx, o["shot"])
    _guard(ctx, shot)
    t0, t1 = _span(ctx, i)
    ctx.touch("shot:" + shot["id"])
    ov, cut = _build_overlay(ctx, shot, o, t0, t1, next_overlay_id(ctx.doc), "")
    shot.setdefault("overlays", []).append(ov)
    _mark(ctx, shot)
    ctx.created["overlays"].append({"shot": shot["id"], "overlay": ov["id"]})
    ctx.define_ref(o.get("ref"), "overlay", ov["id"], shot["id"])
    region = _region_of(ctx, ov.get("params"), _primary_asset(shot, ov))
    variant = ("region_cut" if cut else "region") if region else ("default_cut" if cut else "default")
    ctx.say({"shot": shot["id"], "overlay": ov["id"]}, _when(ctx, shot), variant, n=i + 1,
            technique=_label(ctx, ov["technique"]), region=region or "")


@op("storyboard", "set_overlay",
    summary="Change an overlay of a shot: its technique (parameters then take the new defaults), start, duration or end (cut to the shot if past its end), intent or note. "
            "Use set_params for its parameters.",
    schema=S.obj("set_overlay", ["shot", "overlay"], {
        "shot": SHOT, "overlay": OVERLAY, "technique": TECH,
        "start": OVERLAY_FIELDS["start"],
        "dur": S.number("Duration in seconds (cut to the shot if longer), or null to run to the end of the shot.", exclusive_minimum=0, nullable=True),
        "end": S.any_of(ANCHOR, {"type": "null", "title": "null"}, title="an anchor or null",
                        description="When it ends (instead of dur); null removes it."),
        "intent": INTENT, "note": NOTE}),
    example={"op": "set_overlay", "shot": "s0002", "overlay": "o1", "dur": 3.5},
    sentences={"default": "Cảnh {n}: sửa lớp phủ {technique}", "cut": "Cảnh {n}: sửa lớp phủ {technique} (cắt đến hết cảnh)"})
def set_overlay(ctx, o):
    i, shot = _find(ctx, o["shot"])
    _guard(ctx, shot)
    ov = _overlay(ctx, shot, o["overlay"])
    if ov.get("locked") is True:
        ctx.bad("overlay", "overlay %s of shot %s is locked" % (ov.get("id"), shot["id"]), code="locked", shot=shot["id"], overlay=ov.get("id"))
    if not any(k in o for k in ("technique", "start", "dur", "end", "intent", "note")):
        ctx.bad("", "give at least one of technique, start, dur, end, intent, note to change")
    t0, t1 = _span(ctx, i)
    tl = ctx.facts.timeline
    if "dur" in o and o["dur"] is not None and o.get("end") is not None:
        ctx.bad("end", "give dur or end, not both")
    ctx.touch("shot:" + shot["id"])
    new = copy.deepcopy(ov)
    if o.get("technique") is not None:
        spec = _tech(ctx, o["technique"], ("overlay",), "technique", existing=o["technique"] == ov.get("technique"))
        slots = carry_slots(spec["slots"], ov.get("slots"), ctx.doc["assets"])
        s0, s1 = tl.overlay_span(ov, t0, t1)
        new["technique"] = o["technique"]
        new["params"] = _defaults(ctx, o["technique"], "overlay", shot, {**(shot.get("slots") or {}), **slots}, s1 - s0)
        if slots:
            new["slots"] = slots
        else:
            new.pop("slots", None)
        if new.get("intent") not in (spec.get("intents") or []) and spec.get("intents"):
            new["intent"] = spec["intents"][0]
    if "start" in o and o["start"] is not None:
        new["start"], _ = _anchor_arg(ctx, o["start"], "start")
    if "dur" in o:
        if o["dur"] is None:
            new.pop("dur", None)
        else:
            new["dur"] = float(o["dur"])
            new.pop("end", None)
    if "end" in o:
        if o["end"] is None:
            new.pop("end", None)
        else:
            new["end"], _ = _anchor_arg(ctx, o["end"], "end")
            new.pop("dur", None)
    if o.get("intent"):
        new["intent"] = o["intent"]
    if "note" in o:
        new["note"] = o["note"]
    cut = False
    raw0 = tl.resolve(new.get("start"))
    if raw0 is not None and ("start" in o or "dur" in o or "end" in o):
        end_t = (raw0 + float(new["dur"])) if is_num(new.get("dur")) else (tl.resolve(new["end"]) if isinstance(new.get("end"), dict) else t1)
        _, cut = _overlay_window(ctx, raw0, end_t if end_t is not None else t1, t0, t1, "", shot["id"], "end" if isinstance(new.get("end"), dict) else "dur")
        if cut:
            new.pop("end", None)
            new["dur"] = _cut_dur(raw0, t1)
    ov.clear()
    ov.update(new)
    _mark(ctx, ov)
    ctx.say({"shot": shot["id"], "overlay": ov["id"]}, _when(ctx, shot), "cut" if cut else "default", n=i + 1, technique=_label(ctx, ov["technique"]))


@op("storyboard", "remove_overlay",
    summary="Remove an overlay from a shot.",
    schema=S.obj("remove_overlay", ["shot", "overlay"], {"shot": SHOT, "overlay": OVERLAY}),
    example={"op": "remove_overlay", "shot": "s0002", "overlay": "o2"},
    sentences="Cảnh {n}: bỏ lớp phủ {technique}")
def remove_overlay(ctx, o):
    i, shot = _find(ctx, o["shot"])
    _guard(ctx, shot)
    ov = _overlay(ctx, shot, o["overlay"])
    if ov.get("locked") is True:
        ctx.bad("overlay", "overlay %s of shot %s is locked" % (ov.get("id"), shot["id"]), code="locked", shot=shot["id"], overlay=ov.get("id"))
    ctx.touch("shot:" + shot["id"])
    shot["overlays"] = [x for x in shot["overlays"] if x is not ov]
    _mark(ctx, shot)
    ctx.say({"shot": shot["id"], "overlay": ov["id"]}, _when(ctx, shot), n=i + 1, technique=_label(ctx, ov.get("technique")))


# ---------------------------------------------------------------- operations: cutting
@op("storyboard", "split_shot",
    summary="Cut a shot in two at a time. Each half keeps the camera pose it had at that time and the overlays go to the half they start in "
            "(an overlay that crosses the cut is shortened), as when the page cuts.",
    schema=S.obj("split_shot", ["shot", "at"], {"shot": SHOT, "at": AT, "snap": SNAP, "ref": REF}),
    example={"op": "split_shot", "shot": "s0004", "at": 26.0, "ref": "second_half"},
    sentences="Cảnh {n}: tách thành hai cảnh tại {at}")
def split_shot(ctx, o):
    i, shot = _find(ctx, o["shot"])
    _guard(ctx, shot)
    tl = ctx.facts.timeline
    t0, t1 = _span(ctx, i)
    a, at = _anchor_arg(ctx, o["at"], "at", snap=o.get("snap", True))
    lo, hi = t0 + MIN_SHOT, t1 - MIN_SHOT
    if not lo - EPS <= at <= hi + EPS and "w" in a:
        if is_num(o["at"]):                                 # snapping moved it out of the window: keep the exact time
            a = {"t": jround(float(o["at"]), 3)}
            at = a["t"]
    if not lo - EPS <= at <= hi + EPS:
        ctx.bad("at", "%.2f s would leave a piece shorter than %.1f s: choose a time between %.2f and %.2f s (the shot spans %.2f to %.2f s)"
                % (at, MIN_SHOT, lo, hi, t0, t1), code="shot_too_short")
    new_id = next_shot_ids(ctx.doc)[0]
    ctx.touch("shot:" + shot["id"])
    ctx.touch("shot:" + new_id)
    n = {k: copy.deepcopy(v) for k, v in shot.items() if not str(k).startswith("_")}
    n["id"], n["start"], n["transition_in"], n["locked"], n["overlays"] = new_id, a, None, False, []
    for name, keys in camera_lists(shot.get("params")):
        shot["params"][name] = tl.crop_camera(keys, t0, at, t0, t1)
        n["params"][name] = tl.crop_camera(keys, at, t1, t0, t1)
    keep = []
    for ov in shot.get("overlays") or []:
        if tl.overlay_span(ov, t0, t1)[0] >= at - EPS:
            n["overlays"].append(copy.deepcopy(ov))
        else:
            keep.append(ov)
    shot["overlays"] = keep
    tl.fit_overlays(shot["overlays"], t0, at, t0, t1, ctx.source)
    _mark(ctx, shot)
    _mark(ctx, n)
    ctx.doc["shots"].insert(i + 1, n)
    if ctx.scope_ids is not None:
        ctx.scope_ids.add(new_id)
    ctx.created["shots"].append(new_id)
    ctx.define_ref(o.get("ref"), "shot", new_id)
    ctx.say({"shot": shot["id"]}, _when(ctx, shot), n=i + 1, at=fmt_time(at))


@op("storyboard", "merge_shots",
    summary="Merge shots that follow each other into the first of them: it keeps its camera poses over the time it had, takes the overlays "
            "of the others and lasts until the end of the last.",
    schema=S.obj("merge_shots", ["shots"], {
        "shots": S.array(SHOT, "The shot ids, in the order they follow each other in the storyboard (2 to 20); the first one remains.",
                         min_items=2, max_items=20)}),
    example={"op": "merge_shots", "shots": ["s0007", "s0008"]},
    sentences="Cảnh {n}: gộp với cảnh {others}")
def merge_shots(ctx, o):
    tl = ctx.facts.timeline
    found = [_find(ctx, v, "shots[%d]" % k) for k, v in enumerate(o["shots"])]
    ids = [s["id"] for _, s in found]
    if len(set(ids)) != len(ids):
        ctx.bad("shots", "a shot is named twice", code="not_consecutive")
    for k, (i, s) in enumerate(found):
        _guard(ctx, s, "shots[%d]" % k)
        if k and i != found[k - 1][0] + 1:
            nxt = ctx.doc["shots"][found[k - 1][0] + 1]["id"] if found[k - 1][0] + 1 < len(ctx.doc["shots"]) else None
            ctx.bad("shots[%d]" % k, "%s does not follow %s directly%s" % (s["id"], ids[k - 1], (" (the next shot is %s)" % nxt) if nxt else ""),
                    code="not_consecutive")
    spans = tl.spans(ctx.doc)
    i0 = found[0][0]
    if any(sp[0] is None or sp[1] is None for sp in spans[i0:found[-1][0] + 1]):
        ctx.bad("shots", "a shot of the run has no resolvable start or end in time")
    for _, s in found:
        ctx.touch("shot:" + s["id"])
    first = ctx.doc["shots"][i0]
    t0 = spans[i0][0]
    end_t = spans[i0][1]
    for k, (i, s) in enumerate(found[1:], 1):
        new_end = spans[i][1]
        old_dur, new_dur = end_t - t0, new_end - t0
        for name, keys in camera_lists(first.get("params")):
            first["params"][name] = tl.rescale_rel(keys, old_dur, new_dur)
        first["overlays"] = (first.get("overlays") or []) + (s.get("overlays") or [])
        end_t = new_end
    # overlay ids are unique inside their shot: a later duplicate gets a fresh id
    seen: set = set()
    floor = _overlay_floor(ctx.doc)
    for ov in first["overlays"]:
        if ov.get("id") in seen:
            floor += 1
            ov["id"] = "o%d" % floor
        seen.add(ov.get("id"))
    gone = {id(s) for _, s in found[1:]}
    ctx.doc["shots"] = [s for s in ctx.doc["shots"] if id(s) not in gone]
    _mark(ctx, first)
    others = ", ".join(str(i + 1) for i, _ in found[1:])
    ctx.say({"shot": first["id"]}, _when(ctx, first), n=i0 + 1, others=others)


@op("storyboard", "move_boundary",
    summary="Move the cut where a shot begins to another time: the shot before it gets longer or shorter by the same amount. "
            "Overlays that no longer fit their shot are shifted or shortened, as when the page moves a cut.",
    schema=S.obj("move_boundary", ["shot", "to"], {
        "shot": S.string("The shot that begins at the boundary to move (not the first shot of the storyboard).",
                         pattern=SHOT["pattern"], hint=SHOT["x-hint"]),
        "to": AT, "snap": SNAP}),
    example={"op": "move_boundary", "shot": "s0004", "to": 20.0},
    sentences="Cảnh {n}: dời điểm cắt từ {old} sang {new}")
def move_boundary(ctx, o):
    tl = ctx.facts.timeline
    i, cur = _find(ctx, o["shot"])
    if i == 0:
        ctx.bad("shot", "the first shot begins the storyboard: its start cannot move (name the shot after the boundary to move)")
    prev = ctx.doc["shots"][i - 1]
    _guard(ctx, cur)
    _guard(ctx, prev)
    spans = tl.spans(ctx.doc)
    p0, c0 = spans[i - 1][0], spans[i][0]
    c1 = spans[i][1]
    if p0 is None or c0 is None or c1 is None:
        ctx.bad("shot", "the shots around this boundary have no resolvable times")
    lo, hi = p0 + MIN_SHOT, c1 - MIN_SHOT
    a, t = _anchor_arg(ctx, o["to"], "to", snap=o.get("snap", True))
    if not lo - EPS <= t <= hi + EPS and "w" in a and is_num(o["to"]):
        a = {"t": jround(float(o["to"]), 3)}
        t = a["t"]
    if not lo - EPS <= t <= hi + EPS:
        ctx.bad("to", "%.2f s would leave a shot shorter than %.1f s: choose a time between %.2f and %.2f s" % (t, MIN_SHOT, lo, hi),
                code="shot_too_short")
    ctx.touch("shot:" + prev["id"])
    ctx.touch("shot:" + cur["id"])
    tl.fit_overlays(prev.get("overlays") or [], p0, t, p0, c0, ctx.source)
    tl.fit_overlays(cur.get("overlays") or [], t, c1, c0, c1, ctx.source)
    cur["start"] = a
    _mark(ctx, prev)
    _mark(ctx, cur)
    ctx.say({"shot": cur["id"]}, fmt_time(t), n=i + 1, old=fmt_time(c0), new=fmt_time(t))


@op("storyboard", "replace_range",
    summary="Replace a run of consecutive shots by new shots that cover exactly the same span of narration (the shape the fast edit "
            "produces: shots changed or added, others removed). The first new shot starts where the run starts; the others start inside it.",
    schema=S.obj("replace_range", ["from_shot", "to_shot", "shots"], {
        "from_shot": S.string("The first shot of the run.", pattern=SHOT["pattern"], hint=SHOT["x-hint"]),
        "to_shot": S.string("The last shot of the run (the same shot for a run of one).", pattern=SHOT["pattern"], hint=SHOT["x-hint"]),
        "shots": S.array(S.plain_object({
            "technique": TECH,
            "start": S.any_of(ANCHOR, title="an anchor",
                              description="Where the new shot starts; leave out for the first shot (it takes the start of the run)."),
            "intent": INTENT, "note": NOTE,
            "slots": SLOTS,
            "params": S.free_object("Parameters that differ from the defaults of the technique."),
            "overlays": S.array(S.plain_object(OVERLAY_FIELDS, required=["technique"], title="an overlay"),
                                "Overlays of the new shot (as add_overlay, without shot).", max_items=30),
            "ref": REF}, required=["technique"], title="a new shot"),
            "The new shots, in time order (1 to 60).", min_items=1, max_items=60)}),
    example={"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008",
             "shots": [{"technique": "CAM-01", "intent": "explore", "slots": {"image": {"asset": "C"}}, "ref": "first"},
                       {"technique": "STATIC-01", "start": {"w": 154}, "slots": {"image": {"asset": "B"}}}]},
    sentences={"default": "Cảnh {rng}: thay bằng {k} cảnh mới", "cut": "Cảnh {rng}: thay bằng {k} cảnh mới (lớp phủ cắt đến hết cảnh)"})
def replace_range(ctx, o):
    tl = ctx.facts.timeline
    i, first = _find(ctx, o["from_shot"], "from_shot")
    j, last = _find(ctx, o["to_shot"], "to_shot")
    if j < i:
        ctx.bad("to_shot", "shot %s comes before shot %s in the storyboard" % (last["id"], first["id"]), code="not_consecutive")
    run = ctx.doc["shots"][i:j + 1]
    for s in run:
        _guard(ctx, s, "from_shot")
        for ov in s.get("overlays") or []:
            if ov.get("locked") is True:
                ctx.bad("from_shot", "overlay %s of shot %s is locked and would be lost" % (ov.get("id"), s["id"]), code="locked", shot=s["id"])
    spans = tl.spans(ctx.doc)
    t_start, t_end = spans[i][0], spans[j][1]
    if t_start is None or t_end is None:
        ctx.bad("from_shot", "the run has no resolvable start or end in time")
    starts: list[tuple[dict, float]] = []
    for k, ns in enumerate(o["shots"]):
        base = "shots[%d]." % k
        if ns.get("start") is not None:
            a, t = _anchor_arg(ctx, ns["start"], base + "start")
        elif k == 0:
            a = copy.deepcopy(first["start"])
            t = t_start
        else:
            ctx.bad(base + "start", "is required for every new shot after the first")
        starts.append((a, t))
    if abs(starts[0][1] - t_start) > 0.001:
        ctx.bad("shots[0].start", "starts at %.2f s but the shots replaced start at %.2f s: the new shots must cover the same span" % (starts[0][1], t_start),
                code="span_mismatch")
    for k in range(1, len(starts)):
        t = starts[k][1]
        if not starts[k - 1][1] < t < t_end:
            ctx.bad("shots[%d].start" % k, "starts at %.2f s: it must be after the previous new shot (%.2f s) and before the run ends (%.2f s)"
                    % (t, starts[k - 1][1], t_end), code="span_mismatch")
    bounds = [t for _, t in starts] + [t_end]
    for k in range(len(starts)):
        if bounds[k + 1] - bounds[k] < MIN_SHOT - EPS:
            ctx.bad("shots[%d]" % k, "the new shot would last %.2f s: every shot lasts at least %.1f s" % (bounds[k + 1] - bounds[k], MIN_SHOT),
                    code="shot_too_short")
    new_ids = next_shot_ids(ctx.doc, len(o["shots"]))
    # the techniques the replaced shots already have (a shot's own and its overlays'): the deep edit puts a merged storyboard back as ONE `replace_range` that names every technique
    # again, the stored ones included, and the stored storyboards use hidden techniques: an agent is never refused for what the run already holds, only for a new hidden one
    carried_base = {s.get("technique") for s in run}
    carried_overlay = {ov.get("technique") for s in run for ov in s.get("overlays") or []}
    for s in run:
        ctx.touch("shot:" + s["id"])
    for nid in new_ids:
        ctx.touch("shot:" + nid)
    new_shots = []
    oid_floor = _overlay_floor(ctx.doc)
    any_cut = False
    for k, ns in enumerate(o["shots"]):
        base = "shots[%d]." % k
        spec = _tech(ctx, ns["technique"], ("base", "card"), base + "technique", existing=ns["technique"] in carried_base)
        slots = _check_slots(ctx, spec, ns["slots"], base + "slots") if ns.get("slots") else carry_slots(spec["slots"], first.get("slots"), ctx.doc["assets"])
        akey = _primary_asset({"slots": slots})
        given = ns.get("params") or {}
        for name, v in given.items():
            if v is not None:
                _check_param(ctx, spec, name, v, "%sparams.%s" % (base, name), akey)
            elif name not in {p["name"] for p in spec["params"]}:
                ctx.bad("%sparams.%s" % (base, name), "%r is not a parameter of %s" % (name, spec["id"]),
                        allowed=sorted(p["name"] for p in spec["params"]), code="unknown_param")
        n0, n1 = bounds[k], bounds[k + 1]
        shot = {"id": new_ids[k], "start": starts[k][0], "technique": ns["technique"],
                "intent": ns.get("intent") or (spec.get("intents") or ["explore"])[0], "slots": slots, "params": {},
                "transition_in": copy.deepcopy(first.get("transition_in")) if k == 0 else None, "overlays": [],
                "locked": False, "source": ctx.source, "note": ns.get("note") or ""}
        params = _defaults(ctx, ns["technique"], "shot", shot, slots, n1 - n0)
        params.update({n: v for n, v in given.items() if v is not None})
        shot["params"] = params
        for m, so in enumerate(ns.get("overlays") or []):
            oid_floor += 1
            ov, ov_cut = _build_overlay(ctx, shot, so, n0, n1, "o%d" % oid_floor, "%soverlays[%d]." % (base, m), existing=so["technique"] in carried_overlay)
            any_cut = any_cut or ov_cut
            shot["overlays"].append(ov)
        new_shots.append(shot)
    ctx.doc["shots"][i:j + 1] = new_shots
    for k, ns in enumerate(o["shots"]):
        ctx.created["shots"].append(new_ids[k])
        if ctx.scope_ids is not None:
            ctx.scope_ids.add(new_ids[k])
        for ov in new_shots[k]["overlays"]:
            ctx.created["overlays"].append({"shot": new_ids[k], "overlay": ov["id"]})
        ctx.define_ref(ns.get("ref"), "shot", new_ids[k])
    ctx.say({"shot": new_ids[0]}, fmt_time(t_start), "cut" if any_cut else "default", rng=str(i + 1) if i == j else "%d–%d" % (i + 1, j + 1), k=len(new_shots))


# ---------------------------------------------------------------- operations: locks
@op("storyboard", "lock",
    summary="Lock a shot (or one overlay of it): every operation on it is refused until it is unlocked, whoever sends it.",
    schema=S.obj("lock", ["shot"], {"shot": SHOT, "overlay": OVERLAY}),
    example={"op": "lock", "shot": "s0003"},
    sentences={"default": "Cảnh {n}: đã khóa", "overlay": "Cảnh {n}: đã khóa lớp phủ {technique}"})
def lock(ctx, o):
    i, shot = _find(ctx, o["shot"])
    _guard(ctx, shot)
    ov = _overlay(ctx, shot, o["overlay"]) if o.get("overlay") is not None else None
    if ov is not None and ov.get("locked") is True:
        ctx.bad("overlay", "overlay %s of shot %s is already locked" % (ov.get("id"), shot["id"]), code="locked", shot=shot["id"], overlay=ov.get("id"))
    ctx.touch("shot:" + shot["id"])
    if ov is not None:
        ov["locked"] = True
        ctx.say({"shot": shot["id"], "overlay": ov["id"]}, _when(ctx, shot), "overlay", n=i + 1, technique=_label(ctx, ov.get("technique")))
    else:
        shot["locked"] = True
        ctx.say({"shot": shot["id"]}, _when(ctx, shot), n=i + 1)


@op("storyboard", "unlock",
    summary="Unlock a shot (or one overlay of it). The only operation a locked shot accepts; unlocking something that is not locked changes nothing.",
    schema=S.obj("unlock", ["shot"], {"shot": SHOT, "overlay": OVERLAY}),
    example={"op": "unlock", "shot": "s0006"},
    sentences={"default": "Cảnh {n}: đã mở khóa", "overlay": "Cảnh {n}: đã mở khóa lớp phủ {technique}"})
def unlock(ctx, o):
    i, shot = _find(ctx, o["shot"])
    _guard(ctx, shot, allow_locked=True)
    ov = _overlay(ctx, shot, o["overlay"]) if o.get("overlay") is not None else None
    ctx.touch("shot:" + shot["id"])
    if ov is not None:
        ov["locked"] = False
        ctx.say({"shot": shot["id"], "overlay": ov["id"]}, _when(ctx, shot), "overlay", n=i + 1, technique=_label(ctx, ov.get("technique")))
    else:
        shot["locked"] = False
        ctx.say({"shot": shot["id"]}, _when(ctx, shot), n=i + 1)
