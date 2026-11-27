"""Scorecard metrics (design 2026-11-27 section 6) for legacy and `visual.json` projects."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from bti.engine import registry as R
from bti.engine import viewchecks as VC
from bti.engine.timing import Timing
from bti.media import contentbox as CB
from bti.picks.doc import subject_places

from . import targets as T
from . import visual as V

SCHEMA = "bti.scorecard/1"
POINTING_TECHNIQUES = ("HI-01", "X-HI-01", "AN-01")
IDENTITY_CHECK_PREFIXES = ("ID-MARK-", "ID-BRAND-")
SAMPLE_S = 0.25


def _read_json(path: Path) -> dict | None:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _resolve_timeline(sb: dict, timing: dict | None, bundle) -> tuple[list[float | None], float]:
    """Resolve shot start times and end time using `Timing`."""
    shots = [s if isinstance(s, dict) else {} for s in (sb.get("shots") or [])]
    words = (timing or {}).get("words") if isinstance((timing or {}).get("words"), list) else []
    dur = float((timing or {}).get("duration") or 0.0)
    tm = Timing({"duration": dur, "words": words, "beats": (timing or {}).get("beats") or [], "chapters": (timing or {}).get("chapters") or []})
    starts: list[float | None] = []
    for s in shots:
        try:
            starts.append(float(tm.resolve(s["start"])))
        except Exception:       # noqa: BLE001
            starts.append(None)
    try:
        end_t = float(tm.resolve(sb["end"])) if isinstance(sb.get("end"), dict) else dur
    except Exception:           # noqa: BLE001
        end_t = dur
    if end_t <= 0:
        valid = [t for t in starts if t is not None]
        end_t = max(valid) if valid else 0.0
    return starts, end_t


def _ctx_for(project_dir: Path, sb: dict, timing: dict | None, bundle) -> VC._Ctx:
    starts, end_t = _resolve_timeline(sb, timing, bundle)
    words = (timing or {}).get("words") if isinstance((timing or {}).get("words"), list) else []
    dur = float((timing or {}).get("duration") or end_t)
    tm = Timing({"duration": dur, "words": words, "beats": (timing or {}).get("beats") or [], "chapters": (timing or {}).get("chapters") or []})

    def safe_rel(root, rel):
        try:
            p = (Path(root) / str(rel)).resolve()
            return p if p.is_relative_to(Path(root).resolve()) else None
        except Exception:       # noqa: BLE001
            return None

    return VC._Ctx(sb, tm, bundle, Path(project_dir), starts, end_t, safe_rel)


def _main_asset_key(c: VC._Ctx, picks: dict | None) -> str | None:
    pk_main = picks.get("main_asset") if isinstance(picks, dict) else None
    if isinstance(pk_main, str) and pk_main in c.assets:
        return pk_main
    return c.main_asset()


def _person_regions(picks: dict | None, vis: dict | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if vis is not None:
        out.update(V.cast_person_regions(vis))
    if isinstance(picks, dict):
        for s in picks.get("subjects") or []:
            if not isinstance(s, dict) or s.get("kind") != "person":
                continue
            name = str(s.get("name") or s.get("id") or "")
            for pl in subject_places(s):
                reg = pl.get("region")
                if isinstance(reg, str) and reg:
                    out.setdefault(reg, name)
        for entry in picks.get("names") or []:
            if not isinstance(entry, dict):
                continue
            where = entry.get("where") if isinstance(entry.get("where"), dict) else {}
            reg = where.get("region")
            if isinstance(reg, str) and reg:
                out.setdefault(reg, str(entry.get("name") or reg))
    return out


def _strip_catalog(picks: dict | None, vis: dict | None) -> list[dict]:
    entries: list[dict] = []
    if vis is not None:
        entries.extend(V.cast_strip_entries(vis))
    if isinstance(picks, dict):
        for s in picks.get("subjects") or []:
            if not isinstance(s, dict) or not isinstance(s.get("name"), str):
                continue
            entries.append({
                "id": s.get("id"),
                "kind": s.get("kind"),
                "name": s["name"],
                "also": [a for a in (s.get("also") or []) if isinstance(a, str)],
                "strip": s.get("strip"),
                "sub": s.get("sub") or "",
            })
        for n in picks.get("names") or []:
            if not isinstance(n, dict) or not isinstance(n.get("name"), str):
                continue
            entries.append({
                "id": None,
                "kind": "person",
                "name": n["name"],
                "also": [a for a in (n.get("also") or []) if isinstance(a, str)],
                "strip": True,
                "sub": n.get("sub") or "",
            })
    return entries


def _contains_tokens(hay: list[str], needle: list[str]) -> bool:
    if not needle or len(needle) > len(hay):
        return False
    return any(hay[k:k + len(needle)] == needle for k in range(len(hay) - len(needle) + 1))


def _strip_sub_repeats(text: str, sub: str, matched: dict | None) -> bool:
    sub_toks = VC.tokens(sub)
    if not sub_toks:
        return False
    candidates = [VC.tokens(text)]
    if matched:
        candidates.append(VC.tokens(matched.get("name") or ""))
    for toks in candidates:
        if not toks:
            continue
        if len(toks) == 1 and len(toks[0]) < 4:
            continue
        if _contains_tokens(sub_toks, toks):
            return True
    return False


def _match_strip_entry(text: str, catalog: list[dict]) -> dict | None:
    toks = VC.tokens(text)
    if not toks:
        return None
    for entry in catalog:
        names = [entry.get("name") or ""] + list(entry.get("also") or [])
        for n in names:
            if VC.tokens(n) == toks:
                return entry
    return None


def _overlay_at_label(at: Any) -> str:
    if isinstance(at, str):
        return at
    if isinstance(at, (list, tuple)) and len(at) == 2 and _num(at[0]) and _num(at[1]):
        return "[%d, %d]" % (round(float(at[0])), round(float(at[1])))
    return ""


def _default_zoom_for(c: VC._Ctx, i: int) -> float:
    key = c.primary(i)
    sz = c.size(key) if key else None
    if sz is None:
        return 1.0
    w, h = sz
    return min(1920.0 / w, 1080.0 / h)


def _metric_small_painting(c: VC._Ctx, main: str | None, tgt: dict) -> dict:
    cover_thr = float(tgt["small_painting_cover_threshold"])
    max_share = float(tgt["small_painting_max_share"])
    size = c.size(main) if main else None
    items: list[dict] = []
    secs = 0.0
    if size is not None and c.total > 0:
        for i, sp in enumerate(c.spans):
            if sp is None or not c.has_camera(i) or c.primary(i) != main:
                continue
            keys = c.keys_of(i, sp)
            if keys is None:
                continue
            d = sp[1] - sp[0]
            n = max(2, min(240, int(math.ceil(d / SAMPLE_S))))
            small = 0.0
            low = 1.0
            for j in range(n):
                cov = VC.coverage(*VC.camera_at(keys, sp[0] + (j + 0.5) * d / n), size[0], size[1])
                low = min(low, cov)
                if cov < cover_thr:
                    small += d / n
            if small > 0:
                secs += small
                if small >= 0.5:
                    items.append({
                        "shot": c.sid(i),
                        "time": round(sp[0], 2),
                        "seconds": round(small, 2),
                        "min_cover": round(low, 3),
                    })
    share = (secs / c.total) if c.total > 0 else 0.0
    return {
        "key": "small_painting_share",
        "value": round(share, 4),
        "seconds": round(secs, 2),
        "total_seconds": round(c.total, 2),
        "shot_count": len(items),
        "target": max_share,
        "ok": share <= max_share,
        "items": items,
    }


def _collect_marks(c: VC._Ctx) -> list[dict]:
    """Collect every pointing mark overlay (`HI-01`, `X-HI-01`, `AN-01`) with peak frame height share."""
    marks: list[dict] = []
    for i, shot in enumerate(c.shots):
        sp = c.spans[i]
        if sp is None:
            continue
        keys = c.keys_of(i, sp) if c.has_camera(i) else None
        dz = _default_zoom_for(c, i)
        for o in shot.get("overlays") or []:
            if not isinstance(o, dict):
                continue
            tid = o.get("technique")
            if tid not in POINTING_TECHNIQUES:
                continue
            osp = VC._overlay_span(c, o, sp) if isinstance(o.get("start"), dict) else sp
            if osp is None:
                osp = sp
            spec = c.bundle.spec(tid)
            p = {**(c.bundle.param_defaults(tid) if spec else {}), **(o.get("params") or {})}
            zooms = [VC.camera_at(keys, osp[0] + fr * (osp[1] - osp[0]))[2] for fr in (0.0, 0.25, 0.5, 0.75, 1.0)] if keys else [dz]
            z_max = max(zooms)
            if tid == "AN-01":
                r = float(p["radius"]) if _num(p.get("radius")) else 0.0
                h_share = (2.0 * r * z_max) / 1080.0
            else:
                ry = float(p["ry"]) if _num(p.get("ry")) else 0.0
                h_share = (2.0 * ry * z_max) / 1080.0
            at_raw = p.get("at")
            marks.append({
                "shot": c.sid(i),
                "time": round(osp[0], 2),
                "technique": tid,
                "at": _overlay_at_label(at_raw),
                "at_region": at_raw if isinstance(at_raw, str) else None,
                "height_share": round(h_share, 3),
            })
    return marks


def _metric_marks_per_min(marks: list[dict], total_s: float, tgt: dict) -> dict:
    rate = (len(marks) / (total_s / 60.0)) if total_s > 0 else 0.0
    rings = sum(1 for m in marks if m["technique"] == "AN-01")
    spots = sum(1 for m in marks if m["technique"] in ("HI-01", "X-HI-01"))
    max_rate = float(tgt["marks_per_min_max"])
    return {
        "key": "marks_per_minute",
        "value": round(rate, 2),
        "total": len(marks),
        "rings": rings,
        "spotlights": spots,
        "target": max_rate,
        "ok": rate <= max_rate,
        "items": [{k: m[k] for k in ("shot", "time", "technique", "at")} for m in marks],
    }


def _metric_biggest_mark(marks: list[dict], tgt: dict) -> dict:
    limit = float(tgt["mark_max_height_pct"])
    over = sorted([m for m in marks if m["height_share"] > limit + 1e-9], key=lambda m: -m["height_share"])
    biggest = max((m["height_share"] for m in marks), default=0.0)
    giant_count = sum(1 for m in marks if m["height_share"] > 1.0)
    return {
        "key": "biggest_mark",
        "value": round(biggest, 3),
        "over_30_count": len(over),
        "giant_count": giant_count,
        "target": limit,
        "ok": len(over) == 0,
        "items": [{k: m[k] for k in ("shot", "time", "technique", "at", "height_share")} for m in over],
    }


def _metric_marks_on_person(marks: list[dict], person_regs: dict[str, str], tgt: dict) -> dict:
    hits = [
        {
            "shot": m["shot"],
            "time": m["time"],
            "technique": m["technique"],
            "region": m["at_region"],
            "person": person_regs[m["at_region"]],
        }
        for m in marks
        if m["at_region"] and m["at_region"] in person_regs
    ]
    return {
        "key": "marks_on_person",
        "value": len(hits),
        "target": int(tgt["marks_on_person_max"]),
        "ok": len(hits) <= int(tgt["marks_on_person_max"]),
        "items": hits,
    }


def _metric_name_strips(c: VC._Ctx, picks: dict | None, vis: dict | None, tgt: dict) -> dict:
    catalog = _strip_catalog(picks, vis)
    has_catalog = bool(catalog)
    items: list[dict] = []
    sub_rep_n = 0
    on_thing_n = 0 if has_catalog else None
    for i, shot in enumerate(c.shots):
        sp = c.spans[i]
        if sp is None:
            continue
        for o in shot.get("overlays") or []:
            if not isinstance(o, dict) or o.get("technique") != "X-ANN-01":
                continue
            osp = VC._overlay_span(c, o, sp) if isinstance(o.get("start"), dict) else sp
            ot0 = osp[0] if osp else sp[0]
            p = o.get("params") if isinstance(o.get("params"), dict) else {}
            text = str(p.get("text") or "").strip()
            sub = str(p.get("sub") or "").strip()
            matched = _match_strip_entry(text, catalog) if has_catalog else None
            sub_repeats = _strip_sub_repeats(text, sub, matched)
            if sub_repeats:
                sub_rep_n += 1
            on_thing: bool | None = None
            if has_catalog:
                if matched is not None:
                    if matched.get("strip") is True:
                        on_thing = False
                    elif matched.get("kind") == "thing":
                        on_thing = True
                    else:
                        on_thing = matched.get("kind") not in ("person", "place", "work")
                else:
                    on_thing = True
                if on_thing:
                    on_thing_n = (on_thing_n or 0) + 1
            items.append({
                "shot": c.sid(i),
                "time": round(ot0, 2),
                "text": text,
                "sub": sub,
                "sub_repeats": sub_repeats,
                "on_thing": on_thing,
            })
    max_rep = int(tgt["strip_sub_repeats_max"])
    max_thing = int(tgt["strip_on_thing_max"])
    ok = (sub_rep_n <= max_rep) and (on_thing_n is None or on_thing_n <= max_thing)
    return {
        "key": "name_strips",
        "value": {"count": len(items), "sub_repeats": sub_rep_n, "on_thing": on_thing_n},
        "target": {"sub_repeats": max_rep, "on_thing": max_thing},
        "ok": ok,
        "items": items,
    }


def _borrowed_shot_asset(shot: dict, main: str | None, spec: dict | None, style_id: str) -> str | None:
    if VC.is_program_shot(shot, spec, style_id):
        return None
    if shot.get("technique") == "MAP-01":
        return "MAP-01"
    slots = shot.get("slots")
    if not isinstance(slots, dict):
        return None
    img = slots.get("image")
    if isinstance(img, dict) and isinstance(img.get("asset"), str):
        if main and img["asset"] != main:
            return img["asset"]
    for v in slots.values():
        if isinstance(v, dict) and isinstance(v.get("asset"), str) and main and v["asset"] != main:
            return v["asset"]
    return None


def _metric_borrowed_pictures(c: VC._Ctx, main: str | None, tgt: dict) -> dict:
    min_s = float(tgt["borrowed_min_s"])
    max_gap_s = float(tgt["borrowed_max_gap_s"])
    items: list[dict] = []
    for i, sp in enumerate(c.spans):
        if sp is None:
            continue
        asset = _borrowed_shot_asset(c.shots[i], main, c.specs[i], c.bundle.style)
        if not asset:
            continue
        dur = sp[1] - sp[0]
        items.append({
            "shot": c.sid(i),
            "time": round(sp[0], 2),
            "end": round(sp[1], 2),
            "duration": round(dur, 2),
            "asset": asset,
            "under_3s": dur < min_s - 1e-6,
        })
    total_borrowed = sum(x["duration"] for x in items)
    share = (total_borrowed / c.total) if c.total > 0 else 0.0
    first_t = next((sp[0] for sp in c.spans if sp is not None), 0.0)
    end_t = c.end_t if _num(c.end_t) and c.end_t > first_t else (first_t + c.total)
    gaps: list[tuple[float, float, float]] = []
    cursor = first_t
    for it in items:
        if it["time"] > cursor:
            gaps.append((it["time"] - cursor, cursor, it["time"]))
        cursor = max(cursor, it["end"])
    if end_t > cursor:
        gaps.append((end_t - cursor, cursor, end_t))
    longest, g0, g1 = max(gaps, key=lambda g: g[0]) if gaps else (0.0, 0.0, 0.0)
    under_3s = [it for it in items if it["under_3s"]]
    ok = (len(under_3s) == 0) and (longest <= max_gap_s)
    return {
        "key": "borrowed_pictures",
        "value": {
            "count": len(items),
            "seconds": round(total_borrowed, 2),
            "share": round(share, 4),
            "longest_gap_s": round(longest, 1),
            "longest_gap_from": round(g0, 1),
            "longest_gap_to": round(g1, 1),
            "under_3s_count": len(under_3s),
        },
        "target": {"min_s": min_s, "max_gap_s": max_gap_s, "under_3s": 0},
        "ok": ok,
        "items": items,
    }


def _metric_short_shots(c: VC._Ctx, tgt: dict) -> dict:
    floor_s = float(tgt["short_shot_min_s"])
    max_n = int(tgt["short_shots_max"])
    items: list[dict] = []
    for i, sp in enumerate(c.spans):
        if sp is None or VC.is_program_shot(c.shots[i], c.specs[i], c.bundle.style):
            continue
        dur = sp[1] - sp[0]
        if dur < floor_s - 1e-6:
            items.append({
                "shot": c.sid(i),
                "time": round(sp[0], 2),
                "duration": round(dur, 2),
                "technique": c.shots[i].get("technique"),
            })
    return {
        "key": "short_shots",
        "value": len(items),
        "floor_s": floor_s,
        "target": max_n,
        "ok": len(items) <= max_n,
        "items": items,
    }


def _metric_repeated_regions(c: VC._Ctx, main: str | None, vis: dict | None, tgt: dict) -> dict:
    max_rep = int(tgt["region_repeat_max"])
    regs = (c.assets.get(main) or {}).get("regions") if main and isinstance(c.assets.get(main), dict) else {}
    regs = regs if isinstance(regs, dict) else {}
    moment_region: dict[str, str] = {}
    if vis is not None:
        for m in vis.get("moments") or []:
            if isinstance(m, dict) and isinstance(m.get("id"), str) and isinstance(m.get("show"), dict) and isinstance(m["show"].get("region"), str):
                moment_region[m["id"]] = m["show"]["region"]
    counts: dict[str, list[dict]] = {}
    for i, sp in enumerate(c.spans):
        if sp is None or (main and c.primary(i) != main):
            continue
        if VC.is_program_shot(c.shots[i], c.specs[i], c.bundle.style):
            continue
        slots = c.shots[i].get("slots") if isinstance(c.shots[i].get("slots"), dict) else {}
        rname = (slots.get("image") or {}).get("region") if isinstance(slots.get("image"), dict) else None
        if not isinstance(rname, str) and isinstance(c.shots[i].get("moment"), str):
            rname = moment_region.get(c.shots[i]["moment"])
        if isinstance(rname, str) and rname:
            counts.setdefault(rname, []).append({"shot": c.sid(i), "time": round(sp[0], 2)})
    ranked = sorted(counts.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:5]
    items = [
        {
            "region": rname,
            "label": str((regs.get(rname) or {}).get("label") or rname),
            "count": len(shots),
            "shots": shots,
        }
        for rname, shots in ranked
    ]
    top_count = items[0]["count"] if items else 0
    return {
        "key": "repeated_regions",
        "value": top_count,
        "target": max_rep,
        "ok": top_count <= max_rep,
        "items": items,
    }


def _metric_subject_not_shown(c: VC._Ctx, picks: dict | None, vis: dict | None, timing: dict | None, tgt: dict) -> dict:
    max_n = int(tgt["subject_not_shown_max"])
    if vis is not None:
        by_moment: dict[str, tuple[str, float]] = {}
        for i, sp in enumerate(c.spans):
            mid = c.shots[i].get("moment")
            if sp is not None and isinstance(mid, str) and mid and mid not in by_moment:
                by_moment[mid] = (c.sid(i), sp[0])
        items = V.moments_subject_not_shown(vis, timing, shot_by_moment=by_moment)
        return {
            "key": "subject_not_shown",
            "value": len(items),
            "target": max_n,
            "ok": len(items) <= max_n,
            "items": items,
        }
    if isinstance(picks, dict) and isinstance(picks.get("subjects"), list):
        shot_time = {c.sid(i): round(sp[0], 2) for i, sp in enumerate(c.spans) if sp is not None}
        raw = VC._subject_not_on_screen(c)
        items = []
        for iss in raw:
            args = iss.get("args") or {}
            sid = args.get("shot") or iss.get("shot")
            items.append({
                "shot": sid,
                "time": shot_time.get(sid),
                "beat": args.get("beat"),
                "subject": args.get("subject"),
                "name": args.get("name"),
            })
        return {
            "key": "subject_not_shown",
            "value": len(items),
            "target": max_n,
            "ok": len(items) <= max_n,
            "items": items,
        }
    return {
        "key": "subject_not_shown",
        "value": None,
        "target": max_n,
        "ok": None,
        "items": [],
        "note": "no_subjects",
    }


def _box_coverage(cx: float, cy: float, z: float, box: tuple[float, float, float, float]) -> float:
    vw, vh = 1920.0 / z, 1080.0 / z
    ow = max(0.0, min(box[2], cx + vw / 2.0) - max(box[0], cx - vw / 2.0))
    oh = max(0.0, min(box[3], cy + vh / 2.0) - max(box[1], cy - vh / 2.0))
    return (ow / vw) * (oh / vh)


def _metric_unfilled_identity(c: VC._Ctx, tgt: dict) -> dict:
    min_cov = float(tgt["identity_fill_min_cover"])
    max_n = int(tgt["unfilled_identity_max"])
    items: list[dict] = []
    for i, sp in enumerate(c.spans):
        if sp is None:
            continue
        shot = c.shots[i]
        tid = shot.get("technique")
        if not (isinstance(tid, str) and tid.startswith(IDENTITY_CHECK_PREFIXES)):
            continue
        key = c.primary(i)
        asset = c.assets.get(key) if key else None
        size = c.size(key) if key else None
        if not isinstance(asset, dict) or size is None:
            continue
        box = CB.box_of(asset, c.project_dir) or (0.0, 0.0, size[0], size[1])
        keys = c.keys_of(i, sp)
        if not keys:
            continue
        min_shot_cov = min(_box_coverage(k[1], k[2], k[3], box) for k in keys)
        if min_shot_cov < min_cov - 1e-6:
            title = (shot.get("params") or {}).get("title") or (shot.get("params") or {}).get("text") or tid
            items.append({
                "shot": c.sid(i),
                "time": round(sp[0], 2),
                "technique": tid,
                "title": str(title),
                "min_cover": round(min_shot_cov, 3),
            })
    return {
        "key": "unfilled_identity",
        "value": len(items),
        "min_cover": min_cov,
        "target": max_n,
        "ok": len(items) <= max_n,
        "items": items,
    }


def _metric_loudness(audio: dict | None, tgt: dict) -> dict:
    target = float(tgt["loudness_target_lufs"])
    tol = float(tgt["loudness_tolerance_lu"])
    loud = (audio or {}).get("loudness") if isinstance(audio, dict) else None
    if not isinstance(loud, dict) or loud.get("lufs") is None:
        return {
            "key": "loudness",
            "value": None,
            "target": {"lufs": target, "tolerance": tol},
            "ok": None,
            "items": [],
        }
    lufs = float(loud["lufs"])
    return {
        "key": "loudness",
        "value": {
            "lufs": round(lufs, 1),
            "lra": loud.get("lra"),
            "true_peak": loud.get("true_peak"),
        },
        "target": {"lufs": target, "tolerance": tol},
        "ok": abs(lufs - target) <= tol + 1e-6,
        "items": [],
    }


def _metric_pause_vs_speech(audio: dict | None, tgt: dict) -> dict:
    lo = float(tgt["pause_under_speech_min_db"])
    hi = float(tgt["pause_under_speech_max_db"])
    pvs = (audio or {}).get("pause_vs_speech") if isinstance(audio, dict) else None
    if not isinstance(pvs, dict) or pvs.get("diff_db") is None:
        return {
            "key": "pause_vs_speech",
            "value": None,
            "target": {"min_db": lo, "max_db": hi},
            "ok": None,
            "items": [],
        }
    diff = float(pvs["diff_db"])
    return {
        "key": "pause_vs_speech",
        "value": dict(pvs),
        "target": {"min_db": lo, "max_db": hi},
        "ok": lo - 1e-6 <= diff <= hi + 1e-6,
        "items": [],
    }


def compute_metrics(
    project_dir: Path,
    *,
    sb: dict | None = None,
    picks: dict | None = None,
    timing: dict | None = None,
    visual: dict | None = None,
    targets: dict | None = None,
    audio: dict | None = None,
    exported: bool = False,
    storyboard_rev: str | None = None,
    export_rev: str | None = None,
    style_root: Path | None = None,
) -> dict:
    """Compute all 12 phase-0 scorecard metrics for `project_dir`."""
    pdir = Path(project_dir)
    if sb is None:
        sb = _read_json(pdir / "storyboard.json")
    if not isinstance(sb, dict):
        raise ValueError("storyboard.json is missing or unreadable")
    if picks is None:
        picks = _read_json(pdir / "picks.json")
    if timing is None:
        t_rel = sb.get("timing") if isinstance(sb.get("timing"), str) and sb.get("timing") else "timing.json"
        timing = _read_json(pdir / t_rel)
    if visual is None:
        visual = V.load_visual(pdir)
    style_id = sb.get("style") if isinstance(sb.get("style"), str) else "gae"
    tgt = dict(targets) if targets is not None else T.load_targets(style_id, style_root=style_root)
    bundle = R.load_bundle(style_id)
    ctx = _ctx_for(pdir, sb, timing, bundle)
    main = _main_asset_key(ctx, picks)
    marks = _collect_marks(ctx)
    person_regs = _person_regions(picks, visual)

    metrics = [
        _metric_small_painting(ctx, main, tgt),
        _metric_marks_per_min(marks, ctx.total, tgt),
        _metric_biggest_mark(marks, tgt),
        _metric_marks_on_person(marks, person_regs, tgt),
        _metric_name_strips(ctx, picks, visual, tgt),
        _metric_borrowed_pictures(ctx, main, tgt),
        _metric_short_shots(ctx, tgt),
        _metric_repeated_regions(ctx, main, visual, tgt),
        _metric_subject_not_shown(ctx, picks, visual, timing, tgt),
        _metric_unfilled_identity(ctx, tgt),
        _metric_loudness(audio, tgt),
        _metric_pause_vs_speech(audio, tgt),
    ]
    passed = sum(1 for m in metrics if m["ok"] is True)
    failed = sum(1 for m in metrics if m["ok"] is False)
    na = sum(1 for m in metrics if m["ok"] is None)

    if storyboard_rev is None:
        from bti.editor.common import compute_rev
        storyboard_rev = compute_rev(sb)

    return {
        "schema": SCHEMA,
        "project": pdir.name,
        "storyboard_rev": storyboard_rev,
        "export_rev": export_rev,
        "exported": bool(exported),
        "source": "visual" if visual is not None else "legacy",
        "shots": len(ctx.shots),
        "duration_s": round(ctx.total, 2),
        "summary": {
            "total": len(metrics),
            "passed": passed,
            "failed": failed,
            "na": na,
        },
        "targets": tgt,
        "metrics": metrics,
    }
