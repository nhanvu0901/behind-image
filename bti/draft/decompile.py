"""The reverse of the compiler: a saved storyboard -> draft specs by chapter (`inputs/current/` of a workspace), and the scope check
of the edit mode (design section 7.4).

`decompile` is faithful on purpose: every shot becomes a spec shot that carries its id and ALL its parameters. The compiler
recognises a spec shot that is identical to the decompiled form of the saved shot with the same id and copies the saved shot
through verbatim (anchors, params, overlays, ids). So a storyboard that nobody touched compiles back to itself.

Where a round trip is not exact by construction (listed in docs/qa/BUILD_draft.md): an anchor `{"t": ...}` is described as the
nearest word plus an offset (the compiler copies the saved anchor, so it comes back as `t`); card shots are not part of the specs
(chapter cards and title cards belong to the compiler; in edit mode they are carried through as they are); the shot's `source` and
`locked` flags and the `approvals` block are carried over from the saved shot, not from the spec.
"""
from __future__ import annotations

import copy
import json

from bti.engine.timing import AnchorError, Timing

from . import spec as S
from .inputs import SPEC_SCHEMA, DraftInputs

COMPARE_SHOT = ("beat", "start_word", "off", "technique", "intent", "slots", "params", "overlays", "note", "transition_in")
COMPARE_OVERLAY = ("technique", "start_word", "off", "dur", "intent", "slots", "params", "note")


def clean(obj):
    """JSON round trip without the derived `_` keys: what two documents are compared by."""
    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if not str(k).startswith("_")}
        if isinstance(o, list):
            return [strip(v) for v in o]
        return o
    return json.loads(json.dumps(strip(obj), sort_keys=True))


def _word_of(tm: Timing, anchor: dict, t: float) -> tuple[int, float]:
    if isinstance(anchor, dict) and isinstance(anchor.get("w"), int) and 0 <= anchor["w"] < len(tm.words):
        i = anchor["w"]
    else:
        i = tm.nearest_word(t)
    return i, round(t - tm.word_start(i), 4)


def beat_of(inp: DraftInputs, w: int) -> str | None:
    beats = inp.timing["beats"]
    for b in beats:
        if b["w0"] <= w < b["w1"]:
            return b["id"]
    before = [b for b in beats if b["w0"] <= w]
    return before[-1]["id"] if before else (beats[0]["id"] if beats else None)


def chapter_of(inp: DraftInputs, w: int) -> str | None:
    for c in inp.timing["chapters"]:
        if c["w0"] <= w < c["w1"]:
            return c["id"]
    before = [c for c in inp.timing["chapters"] if c["w0"] <= w]
    return before[-1]["id"] if before else (inp.timing["chapters"][0]["id"] if inp.timing["chapters"] else None)


def shot_to_spec(inp: DraftInputs, tm: Timing, shot: dict, t0: float, t1: float) -> dict:
    """One saved shot as a spec shot (without `id`/flags, which `decompile` adds)."""
    w, off = _word_of(tm, shot.get("start") or {}, t0)
    ovs = []
    for o in shot.get("overlays") or []:
        try:
            ts = tm.resolve(o["start"])
            if isinstance(o.get("end"), dict):
                te = tm.resolve(o["end"])
            elif isinstance(o.get("dur"), (int, float)):
                te = ts + float(o["dur"])
            else:
                te = t1
        except (AnchorError, KeyError, TypeError):
            continue
        ow, ooff = _word_of(tm, o["start"], ts)
        ovs.append({"technique": o.get("technique"), "start_word": ow, "off": ooff, "dur": round(te - ts, 3),
                    "intent": o.get("intent"), "slots": copy.deepcopy(o.get("slots") or {}), "params": copy.deepcopy(o.get("params") or {}),
                    "note": o.get("note") or "", "id": o.get("id"), "locked": bool(o.get("locked"))})
    return {"beat": beat_of(inp, w), "start_word": w, "off": off, "technique": shot.get("technique"), "intent": shot.get("intent"),
            "slots": {k: {"asset": v.get("asset")} for k, v in (shot.get("slots") or {}).items() if isinstance(v, dict) and v.get("asset")},
            "params": copy.deepcopy(shot.get("params") or {}), "overlays": ovs, "note": shot.get("note") or "",
            "transition_in": copy.deepcopy(shot.get("transition_in"))}


def comparable(spec_shot: dict) -> dict:
    d = {k: spec_shot.get(k) for k in COMPARE_SHOT if k != "overlays"}
    d["overlays"] = [{k: o.get(k) for k in COMPARE_OVERLAY} for o in spec_shot.get("overlays") or []]
    d["slots"] = {k: {"asset": v.get("asset")} for k, v in (spec_shot.get("slots") or {}).items()}
    for k in ("intent", "note", "transition_in"):
        d[k] = d.get(k) or None
    for o in d["overlays"]:
        o["intent"], o["note"] = o.get("intent") or None, o.get("note") or None
    return clean(d)


def is_card(bundle, shot: dict) -> bool:
    sp = bundle.spec(shot.get("technique"))
    return bool(sp and sp.get("kind") == "card")


def resolve_shots(doc: dict | None, tm: Timing, default_dur: float) -> list[dict]:
    """[{shot, t0, t1}] for a storyboard document."""
    if not isinstance(doc, dict):
        return []
    shots = [s for s in doc.get("shots") or [] if isinstance(s, dict)]
    ts = []
    for s in shots:
        try:
            ts.append(tm.resolve(s["start"]))
        except (AnchorError, KeyError, TypeError):
            ts.append(None)
    end_t = default_dur
    try:
        if isinstance(doc.get("end"), dict):
            end_t = tm.resolve(doc["end"])
    except AnchorError:
        pass
    out = []
    for i, s in enumerate(shots):
        if ts[i] is None:
            continue
        nxt = next((ts[j] for j in range(i + 1, len(shots)) if ts[j] is not None), end_t)
        out.append({"shot": s, "t0": ts[i], "t1": nxt})
    return out


def resolved_current(inp: DraftInputs, tm: Timing) -> list[dict]:
    """[{shot, t0, t1}] of the saved storyboard (shots whose start cannot be resolved are skipped)."""
    return resolve_shots(inp.current, tm, inp.timing["duration"])


def decompile(inp: DraftInputs, scope_ids: set | None = None) -> dict:
    """chapter id -> {"spec": <bti.draft/1 document>, "cards": [shot ids of cards in the chapter's zone]}.
    Every spec shot has `id`, `locked`, `in_scope` (true when `scope_ids` is None or holds its id), `start_s`, `end_s`, and its
    number `_n`... the numbers are the 1-based positions in the chapter's file."""
    from bti.engine import registry as R
    bundle = R.load_bundle(inp.style)
    tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
    out = {c["id"]: {"spec": {"schema": SPEC_SCHEMA, "chapter": c["id"], "shots": []}, "cards": []} for c in inp.timing["chapters"]}
    for rc in resolved_current(inp, tm):
        shot = rc["shot"]
        w, _ = _word_of(tm, shot.get("start") or {}, rc["t0"])
        cid = chapter_of(inp, w)
        if cid is None:
            continue
        if is_card(bundle, shot):
            out[cid]["cards"].append(shot.get("id"))
            continue
        ss = shot_to_spec(inp, tm, shot, rc["t0"], rc["t1"])
        ss.update({"id": shot.get("id"), "locked": bool(shot.get("locked")),
                   "in_scope": scope_ids is None or shot.get("id") in scope_ids,
                   "start_s": round(rc["t0"], 3), "end_s": round(rc["t1"], 3)})
        out[cid]["spec"]["shots"].append(ss)
    return out


def chapters_of_shots(inp: DraftInputs, shot_ids: set) -> list[str]:
    """The chapter ids (in timeline order) that hold any of `shot_ids`."""
    tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
    hit = set()
    for rc in resolved_current(inp, tm):
        if rc["shot"].get("id") in shot_ids:
            w, _ = _word_of(tm, rc["shot"].get("start") or {}, rc["t0"])
            hit.add(chapter_of(inp, w))
    return [c for c in inp.chapter_ids() if c in hit]


def scope_violations(inp: DraftInputs, new_doc: dict, scope_ids: set) -> list[dict]:
    """Problems (errors) for everything the new document changed outside the scope or in a locked shot. Empty = acceptable.
    Allowed: any change to an unlocked shot whose id is in `scope_ids`; new shots that start inside the time span of such a shot;
    regions added to an asset. Everything else must come back identical, start anchors included."""
    tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
    cur = {rc["shot"].get("id"): rc for rc in resolved_current(inp, tm)}
    new = {s.get("id"): s for s in new_doc.get("shots") or [] if isinstance(s, dict)}
    new_resolved = {rc["shot"].get("id"): rc for rc in resolve_shots(new_doc, tm, inp.timing["duration"])}
    out: list[dict] = []

    def bad(code, sid, msg):
        p = S.problem(code, None, None, "shot %s: %s" % (sid, msg))
        p["shot_id"] = sid
        out.append(p)

    spans = [(rc["t0"], rc["t1"]) for sid, rc in cur.items() if sid in scope_ids and not rc["shot"].get("locked")]
    for sid, rc in cur.items():
        s = rc["shot"]
        free = sid in scope_ids and not s.get("locked")
        if free:
            cur_ovs = [o for o in s.get("overlays") or [] if isinstance(o, dict) and o.get("locked")]
            if cur_ovs:
                if sid not in new:
                    bad("edit_locked_changed", sid, "in-scope shot with locked overlays was removed")
                    continue
                new_s = new[sid]
                new_ovs_by_id = {o.get("id"): o for o in new_s.get("overlays") or [] if isinstance(o, dict) and o.get("id")}
                for lk_o in cur_ovs:
                    oid = lk_o.get("id")
                    if not oid or oid not in new_ovs_by_id:
                        bad("edit_locked_changed", sid, "locked overlay %s was removed" % (oid or "unknown"))
                    elif clean(lk_o) != clean(new_ovs_by_id[oid]):
                        bad("edit_locked_changed", sid, "locked overlay %s was changed" % oid)
            continue
        why = "a locked shot" if s.get("locked") else "outside the scope"
        if sid not in new:
            bad("edit_outside_scope", sid, "was removed (%s)" % why)
            continue
        a, b = clean(s), clean(new[sid])
        if a != b:
            keys = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
            bad("edit_locked_changed" if s.get("locked") else "edit_outside_scope", sid, "was changed (%s): %s" % (why, ", ".join(keys)))
        n_rc = new_resolved.get(sid)
        if n_rc is not None:
            if abs(n_rc["t0"] - rc["t0"]) > 1e-3:
                bad("edit_locked_changed" if s.get("locked") else "edit_outside_scope", sid,
                    "effective start was changed (%.3f s -> %.3f s) by neighbor edit" % (rc["t0"], n_rc["t0"]))
            if abs(n_rc["t1"] - rc["t1"]) > 1e-3:
                bad("edit_locked_changed" if s.get("locked") else "edit_outside_scope", sid,
                    "effective end was changed (%.3f s -> %.3f s) by neighbor edit" % (rc["t1"], n_rc["t1"]))
    for sid, s in new.items():
        if sid in cur:
            continue
        try:
            t = tm.resolve(s["start"])
        except (AnchorError, KeyError, TypeError):
            bad("edit_outside_scope", sid, "is new and its start cannot be read")
            continue
        if not any(a - 1e-6 <= t < b - 1e-6 for a, b in spans):
            bad("edit_outside_scope", sid, "is new and starts at %.2f s, outside the time of the shots in scope" % t)
    cur_assets = (inp.current or {}).get("assets") or {}
    for key, a in cur_assets.items():
        b = (new_doc.get("assets") or {}).get(key)
        if b is None:
            bad("edit_outside_scope", key, "asset was removed")
            continue
        ra, rb = dict(a), dict(b)
        regs_a, regs_b = ra.pop("regions", None) or {}, rb.pop("regions", None) or {}
        if clean(ra) != clean(rb) or any(clean(regs_b.get(n)) != clean(r) for n, r in regs_a.items()):
            bad("edit_outside_scope", key, "asset record was changed (only new regions may be added)")
    return out
