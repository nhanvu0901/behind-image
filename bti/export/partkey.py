"""Content-based cache keys for export render parts.

A part's key hashes everything the engine reads to draw frames in [spec.f0, spec.f1) and nothing else:
- the engine render version (`bti.engine.RENDER_VERSION`), style bundle signature (style.json, techniques.json + patches, font/serif signatures, geo files), output width, fps, quality, and exact frame range [f0, f1)
- every shot active in [f0, f1) (by Scene.shot_index semantics), plus the preceding shot when an active transition_in overlaps f0
- each included shot's resolved span [t0, t1], technique, slots, visual params, active transition_in, and overlapping overlays
- word start times (`timing["words"][w]["s"]`) for every word anchor referenced by those shots or the next shot/end boundary
- only the assets referenced by those shots/overlays (plus `aligned_to` masks): file path + content/stat signature, kind, width, height, aligned_to, content_box, and ONLY the named regions those shots/overlays reference (without region `label`, `credit`, or unused assets/regions)
- `identity` only when an included shot or overlay uses an `ID-*` technique
- `end` fade parameters only when the end fade window overlaps [t_lo, t_hi]
"""
from __future__ import annotations

import bisect
import copy
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

from bti.export.plan import PartSpec

KEY_SCHEMA_VERSION = 2
SMALL_FILE_HASH_LIMIT = 2 * 1024 * 1024
EDGE_CHUNK_BYTES = 64 * 1024

_STYLE_LOCK = threading.RLock()
_STYLE_CACHE: dict[tuple, str] = {}


def engine_render_version() -> int:
    try:
        from bti.engine import RENDER_VERSION
        return int(RENDER_VERSION)
    except Exception:       # noqa: BLE001
        return 1


def _safe_rel(project_dir: Path, rel: Any) -> Path | None:
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel or rel.startswith("/") or (len(rel) > 1 and rel[1] == ":"):
        return None
    if any(part in ("..", "") for part in rel.split("/")):
        return None
    try:
        root = Path(project_dir).resolve()
        target = (root / rel).resolve()
        target.relative_to(root)
        return target
    except (OSError, ValueError):
        return None


def asset_file_signature(project_dir: Path | None, rel: Any) -> str:
    """Stable file signature: full SHA-1 for files up to 2 MiB (catches in-place same-size/same-mtime edits); size+mtime+head/tail SHA-1 for larger files."""
    if project_dir is None:
        return "no_dir"
    path = _safe_rel(Path(project_dir), rel)
    if path is None:
        return "invalid"
    try:
        st = path.stat()
        if not path.is_file():
            return "missing"
        size = st.st_size
        if size <= SMALL_FILE_HASH_LIMIT:
            digest = hashlib.sha1(path.read_bytes()).hexdigest()[:16]
            return "sha1:%d:%s" % (size, digest)
        with open(path, "rb") as f:
            head = f.read(EDGE_CHUNK_BYTES)
            f.seek(max(0, size - EDGE_CHUNK_BYTES))
            tail = f.read(EDGE_CHUNK_BYTES)
        digest = hashlib.sha1(head + tail).hexdigest()[:16]
        return "stat:%d:%d:%s" % (size, st.st_mtime_ns, digest)
    except OSError:
        return "missing"


def _dir_stamp(folder: Path) -> tuple:
    if not folder.is_dir():
        return ()
    rows = []
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            try:
                st = p.stat()
                rows.append((p.relative_to(folder).as_posix(), st.st_size, st.st_mtime_ns))
            except OSError:
                rows.append((p.relative_to(folder).as_posix(), -1, -1))
    return tuple(rows)


def style_signature(style_id: str | None, style_root: Path | None = None) -> str:
    """Hash of the style bundle (style.json, patched techniques.json, font/serif signatures, geo files). Falls back cleanly if style is missing."""
    sid = style_id if isinstance(style_id, str) and style_id else "gae"
    try:
        from bti.engine import registry as R, vfx
        from bti.engine.techniques import _t3common
        bundle = R.load_bundle(sid, root=style_root)
    except Exception:       # noqa: BLE001 - e.g. unit test sets sb["style"] = "other"
        return "missing:%s" % sid

    bdir = bundle.dir
    fdir = vfx.bundled_font_dir() if style_root is None else (Path(style_root) / "gae" / "fonts")
    try:
        vfx.configure_fonts(bundle.style)
        font_sig = vfx.font_signature()
    except Exception:       # noqa: BLE001
        font_sig = ""
    try:
        serif_sig = _t3common.serif_signature()
    except Exception:       # noqa: BLE001
        serif_sig = ""

    geo_stamp = _dir_stamp(bdir / "geo")
    stamp = (
        sid,
        str(bdir),
        _dir_stamp(bdir / "patches"),
        (bdir / "style.json").stat().st_mtime_ns if (bdir / "style.json").is_file() else 0,
        (bdir / "techniques.json").stat().st_mtime_ns if (bdir / "techniques.json").is_file() else 0,
        _dir_stamp(fdir),
        geo_stamp,
        font_sig,
        serif_sig,
    )
    with _STYLE_LOCK:
        hit = _STYLE_CACHE.get(stamp)
        if hit is not None:
            return hit
    payload = {
        "style_id": sid,
        "style": bundle.style,
        "techniques": bundle.techniques,
        "font_sig": font_sig,
        "serif_sig": serif_sig,
        "geo": geo_stamp,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    sig = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    with _STYLE_LOCK:
        if len(_STYLE_CACHE) > 32:
            _STYLE_CACHE.clear()
        _STYLE_CACHE[stamp] = sig
    return sig


def _minimal_resolve(sb: dict, words: list[dict]) -> dict:
    """Fallback anchor resolver used only when the style bundle cannot be loaded (e.g. synthetic unit tests)."""
    out = copy.deepcopy(sb)

    def res_anchor(a, t0=None, t1=None):
        if not isinstance(a, dict):
            return None
        if "_t" in a and isinstance(a["_t"], (int, float)):
            return float(a["_t"])
        if "t" in a and isinstance(a["t"], (int, float)):
            a["_t"] = float(a["t"])
            return a["_t"]
        if "w" in a and isinstance(a["w"], int) and not isinstance(a["w"], bool) and 0 <= a["w"] < len(words):
            off = float(a.get("off", 0.0) or 0.0)
            a["_t"] = float(words[a["w"]]["s"]) + off
            return a["_t"]
        if "rel" in a and isinstance(a["rel"], (int, float)) and t0 is not None and t1 is not None:
            a["_t"] = float(t0) + float(a["rel"]) * (float(t1) - float(t0))
            return a["_t"]
        return None

    end_t = res_anchor(out.get("end"))
    shots = out.get("shots") or []
    for s in shots:
        if isinstance(s, dict):
            s["_t0"] = res_anchor(s.get("start"))
    for i, s in enumerate(shots):
        if not isinstance(s, dict):
            continue
        t0 = s.get("_t0")
        t1 = shots[i + 1].get("_t0") if i + 1 < len(shots) and isinstance(shots[i + 1], dict) else end_t
        s["_t1"] = t1
        tr = s.get("transition_in")
        if isinstance(tr, dict) and t0 is not None:
            tr["_t0"] = t0
            tr["_t1"] = t0 + float(tr.get("dur", 0) or 0)
        for o in s.get("overlays") or []:
            if not isinstance(o, dict):
                continue
            ot0 = res_anchor(o.get("start"))
            ot1 = res_anchor(o.get("end")) if isinstance(o.get("end"), dict) else (ot0 + float(o["dur"]) if isinstance(o.get("dur"), (int, float)) and ot0 is not None else t1)
            o["_t0"], o["_t1"] = ot0, ot1
    return out


def resolve_storyboard(sb: dict, timing: dict | None = None, style_root: Path | None = None) -> dict:
    """Resolve `sb` using the engine's own `storyboard.resolve` (with fallback to `gae` or minimal resolution if style is unknown)."""
    tm_data = timing if isinstance(timing, dict) and isinstance(timing.get("words"), list) else {"duration": 0.0, "words": []}
    try:
        from bti.engine import registry as R, storyboard as SB
        from bti.engine.timing import Timing
        tm = Timing(tm_data)
        sid = sb.get("style", "gae") if isinstance(sb, dict) else "gae"
        try:
            bundle = R.load_bundle(sid, root=style_root)
        except Exception:   # noqa: BLE001
            bundle = R.load_bundle("gae", root=style_root)
        return SB.resolve(sb, tm, bundle)
    except Exception:       # noqa: BLE001
        return _minimal_resolve(sb, tm_data.get("words") or [])


def _clean_value(v: Any) -> Any:
    """Canonicalize engine-visible params/slots: keep resolved anchor time `_t`, strip other `_` derived keys and non-rendered noise."""
    if isinstance(v, dict):
        if "_t" in v and ("t" in v or "w" in v or "rel" in v):
            return {"_t": v["_t"]}
        return {k: _clean_value(val) for k, val in v.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(v, list):
        return [_clean_value(x) for x in v]
    return v


def _collect_word_indices(obj: Any, out: set[int]) -> None:
    if isinstance(obj, dict):
        if "w" in obj and isinstance(obj["w"], int) and not isinstance(obj["w"], bool):
            out.add(obj["w"])
        for val in obj.values():
            _collect_word_indices(val, out)
    elif isinstance(obj, list):
        for x in obj:
            _collect_word_indices(x, out)


def _collect_refs(obj: Any, asset_keys: set[str], strings: set[str], all_assets: dict) -> None:
    if isinstance(obj, dict):
        a = obj.get("asset")
        if isinstance(a, str) and a in all_assets:
            asset_keys.add(a)
        for k, val in obj.items():
            if k != "asset":
                _collect_refs(val, asset_keys, strings, all_assets)
    elif isinstance(obj, list):
        for x in obj:
            _collect_refs(x, asset_keys, strings, all_assets)
    elif isinstance(obj, str):
        strings.add(obj)
        if obj in all_assets:
            asset_keys.add(obj)


def _has_identity_technique(shots: list[dict]) -> bool:
    for s in shots:
        if str(s.get("technique") or "").startswith("ID-"):
            return True
        for o in s.get("overlays") or []:
            if str(o.get("technique") or "").startswith("ID-"):
                return True
    return False


def _shot_entry(s: dict, *, role: str, start_override: float | None, win_lo: float, win_hi: float) -> tuple[dict, list[dict]]:
    """Build the canonical visual dict for one shot plus the raw overlays overlapping [win_lo, win_hi]."""
    kept_raw_ovs = []
    ovs_out = []
    for o in s.get("overlays") or []:
        if not isinstance(o, dict):
            continue
        ot0, ot1 = o.get("_t0"), o.get("_t1")
        if ot0 is not None and ot1 is not None:
            if float(ot1) < win_lo - 0.05 or float(ot0) > win_hi + 0.05:
                continue
        kept_raw_ovs.append(o)
        ovs_out.append({
            "technique": o.get("technique"),
            "t0": ot0,
            "t1": ot1,
            "slots": _clean_value(o.get("slots") or {}),
            "params": _clean_value(o.get("params") or {}),
        })

    entry = {
        "role": role,
        "t0": s.get("_t0"),
        "t1": s.get("_t1"),
        "technique": s.get("technique"),
        "slots": _clean_value(s.get("slots") or {}),
        "params": _clean_value(s.get("params") or {}),
        "overlays": ovs_out,
    }
    if start_override is not None and start_override != s.get("_t0"):
        entry["start_lookup"] = start_override
    if role == "active" and isinstance(s.get("transition_in"), dict):
        tr = s["transition_in"]
        entry["transition_in"] = {
            "technique": tr.get("technique"),
            "dur": float(tr.get("dur", 0.0) or 0.0),
            "params": _clean_value(tr.get("params") or {}),
        }
    return entry, kept_raw_ovs


def part_key_payload(
    resolved_sb: dict,
    spec: PartSpec,
    *,
    project_dir: Path | None = None,
    timing: dict | None = None,
    width: int = 1920,
    quality: str = "final",
    style_sig: str | None = None,
    engine_version: int | None = None,
    style_root: Path | None = None,
) -> dict:
    """Return the structured dict hashed by `part_key`. Exposed for inspection and tests."""
    sid = resolved_sb.get("style", "gae") if isinstance(resolved_sb, dict) else "gae"
    ssig = style_sig if style_sig is not None else style_signature(sid, style_root=style_root)
    ever = engine_render_version() if engine_version is None else int(engine_version)

    raw_shots = [s for s in (resolved_sb.get("shots") or []) if isinstance(s, dict)]
    starts = [float(s["_t0"]) if s.get("_t0") is not None else 0.0 for s in raw_shots]
    if starts:
        starts[0] = min(starts[0], 0.0)

    t_lo = spec.f0 / spec.fps
    t_hi = (spec.f1 - 1) / spec.fps if spec.frames > 0 else spec.t0

    included: list[tuple[int, dict, str, float, float]] = []
    first_idx = last_idx = -1
    if starts:
        first_idx = max(0, bisect.bisect_right(starts, t_lo + 1e-6) - 1)
        last_idx = max(0, bisect.bisect_right(starts, t_hi + 1e-6) - 1)
        if first_idx > 0:
            tr = raw_shots[first_idx].get("transition_in")
            dur = float(tr.get("dur", 0.0) or 0.0) if isinstance(tr, dict) else 0.0
            t0_first = starts[first_idx]
            if dur > 0 and t_lo < t0_first + dur:
                included.append((first_idx - 1, raw_shots[first_idx - 1], "prev", t_lo, min(t_hi, t0_first + dur)))
        for i in range(first_idx, last_idx + 1):
            included.append((i, raw_shots[i], "active", t_lo, t_hi))

    shot_entries: list[dict] = []
    raw_for_refs: list[dict] = []
    raw_for_words: list[Any] = []

    for i, s, role, w_lo, w_hi in included:
        entry, kept_ovs = _shot_entry(s, role=role, start_override=starts[i] if i == 0 else None, win_lo=w_lo, win_hi=w_hi)
        shot_entries.append(entry)
        raw_for_refs.append({"slots": s.get("slots"), "params": s.get("params"),
                             "overlays": [{"slots": o.get("slots"), "params": o.get("params")} for o in kept_ovs],
                             "transition_in": s.get("transition_in") if role == "active" else None})
        raw_for_words.append({"start": s.get("start"), "params": s.get("params"),
                              "overlays": kept_ovs, "transition_in": s.get("transition_in") if role == "active" else None})

    # The next shot's start (or storyboard end) sets `_t1` of `last_idx`.
    if 0 <= last_idx + 1 < len(raw_shots):
        raw_for_words.append(raw_shots[last_idx + 1].get("start"))
    else:
        raw_for_words.append(resolved_sb.get("end"))

    word_idxs: set[int] = set()
    _collect_word_indices(raw_for_words, word_idxs)
    words_list = timing.get("words") if isinstance(timing, dict) and isinstance(timing.get("words"), list) else []
    word_times = {}
    for wi in sorted(word_idxs):
        if 0 <= wi < len(words_list) and isinstance(words_list[wi], dict) and isinstance(words_list[wi].get("s"), (int, float)):
            word_times[str(wi)] = float(words_list[wi]["s"])

    all_assets = resolved_sb.get("assets") if isinstance(resolved_sb.get("assets"), dict) else {}
    used_asset_keys: set[str] = set()
    strings_used: set[str] = set()
    _collect_refs(raw_for_refs, used_asset_keys, strings_used, all_assets)

    # Follow mask `aligned_to` chains.
    queue = list(used_asset_keys)
    while queue:
        k = queue.pop()
        a = all_assets.get(k)
        if isinstance(a, dict):
            al = a.get("aligned_to")
            if isinstance(al, str) and al in all_assets and al not in used_asset_keys:
                used_asset_keys.add(al)
                queue.append(al)

    assets_out: dict[str, dict] = {}
    for k in sorted(used_asset_keys):
        a = all_assets.get(k)
        if not isinstance(a, dict):
            continue
        regs = a.get("regions") if isinstance(a.get("regions"), dict) else {}
        used_regs = {}
        for rname, rval in regs.items():
            if rname in strings_used and isinstance(rval, dict):
                used_regs[rname] = {f: rval[f] for f in ("x", "y", "rx", "ry") if f in rval}
        assets_out[k] = {
            "file": a.get("file"),
            "file_sig": asset_file_signature(project_dir, a.get("file")),
            "kind": a.get("kind"),
            "width": a.get("width"),
            "height": a.get("height"),
            "aligned_to": a.get("aligned_to"),
            "content_box": a.get("content_box"),
            "regions": used_regs,
        }

    included_raw_shots = [s for _, s, _, _, _ in included]
    ident = resolved_sb.get("identity") if _has_identity_technique(included_raw_shots) else None

    end_obj = resolved_sb.get("end") if isinstance(resolved_sb.get("end"), dict) else {}
    end_t = end_obj.get("_t")
    try:
        from bti.engine.scene import DEFAULT_END_FADE_S
    except Exception:       # noqa: BLE001
        DEFAULT_END_FADE_S = 1.6
    fade_s = float(end_obj.get("fade_s", DEFAULT_END_FADE_S) if end_obj.get("fade_s") is not None else DEFAULT_END_FADE_S)
    end_fade = [end_t, fade_s] if (isinstance(end_t, (int, float)) and fade_s > 0 and t_hi > float(end_t) - fade_s - 1e-6) else None

    return {
        "v": KEY_SCHEMA_VERSION,
        "engine_version": ever,
        "style": sid,
        "style_sig": ssig,
        "range": [spec.f0, spec.f1, spec.fps],
        "width": int(width),
        "quality": str(quality),
        "shots": shot_entries,
        "assets": assets_out,
        "word_times": word_times,
        "identity": ident,
        "end_fade": end_fade,
    }


def _digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def part_key(
    storyboard: dict,
    spec: PartSpec,
    *,
    project_dir: Path | None = None,
    timing: dict | None = None,
    width: int = 1920,
    quality: str = "final",
    resolved_sb: dict | None = None,
    style_sig: str | None = None,
    engine_version: int | None = None,
    style_root: Path | None = None,
) -> str:
    """Content key for a single `PartSpec`."""
    rsb = resolved_sb if resolved_sb is not None else resolve_storyboard(storyboard, timing, style_root=style_root)
    payload = part_key_payload(
        rsb,
        spec,
        project_dir=project_dir,
        timing=timing,
        width=width,
        quality=quality,
        style_sig=style_sig,
        engine_version=engine_version,
        style_root=style_root,
    )
    return _digest(payload)


def part_keys(
    project_dir: Path | None,
    storyboard: dict,
    timing: dict | None,
    specs: list[PartSpec],
    *,
    width: int = 1920,
    quality: str = "final",
    engine_version: int | None = None,
    style_root: Path | None = None,
) -> list[str]:
    """Compute keys for all planned parts, resolving the storyboard and hashing the style bundle once."""
    sid = storyboard.get("style", "gae") if isinstance(storyboard, dict) else "gae"
    ssig = style_signature(sid, style_root=style_root)
    rsb = resolve_storyboard(storyboard, timing, style_root=style_root)
    ever = engine_render_version() if engine_version is None else int(engine_version)
    return [
        part_key(
            storyboard,
            s,
            project_dir=project_dir,
            timing=timing,
            width=width,
            quality=quality,
            resolved_sb=rsb,
            style_sig=ssig,
            engine_version=ever,
            style_root=style_root,
        )
        for s in specs
    ]
