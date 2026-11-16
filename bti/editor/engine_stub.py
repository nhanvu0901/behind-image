"""Stub implementation of the engine facade (design section 8.1 and 8.3).

Used when `bti.engine.api` is missing or broken. It loads and saves the
storyboard itself, resolves anchors, does basic validation against the
technique registry, and draws a placeholder frame with Pillow.
"""
from __future__ import annotations

import math
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .common import (ApiError, SCHEMA, STYLE_RE, compute_rev, read_json, safe_join,
                     strip_derived, write_json_atomic)

MIN_SHOT = 0.2
ITEM_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
SOURCES = ("import", "agent", "human")
_REG_CACHE: dict[str, tuple[float, dict]] = {}
_REG_LOCK = threading.Lock()


def load_style_stub(style_root: Path, style_id: str) -> dict:
    if not STYLE_RE.fullmatch(style_id or ""):
        raise ApiError(404, "style not found")
    d = style_root / style_id
    tp = d / "techniques.json"
    if not tp.is_file():
        raise ApiError(404, "style not found")
    mt = tp.stat().st_mtime_ns
    with _REG_LOCK:
        hit = _REG_CACHE.get(str(tp))
        if hit and hit[0] == mt:
            return hit[1]
        raw = read_json(tp)
        techniques = raw["techniques"] if isinstance(raw, dict) else raw
        style = {}
        sp = d / "style.json"
        if sp.is_file():
            try:
                style = read_json(sp)
            except Exception:
                style = {}
        intents = sorted({i for t in techniques for i in (t.get("intents") or [])})
        out = {"style": style, "techniques": techniques, "intents": intents}
        _REG_CACHE[str(tp)] = (mt, out)
        return out


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _is_anchor(a: Any) -> bool:
    return isinstance(a, dict) and any(k in a for k in ("t", "w", "rel"))


class StubProject:
    mode = "stub"

    def __init__(self, project_dir: Path, style_root: Path):
        self.dir = Path(project_dir)
        self.style_root = Path(style_root)
        self._draft: dict | None = None
        self._font_cache: dict[int, Any] = {}

    # ----- documents -----
    @property
    def _sb_path(self) -> Path:
        return self.dir / "storyboard.json"

    def storyboard(self) -> dict:
        return read_json(self._sb_path)

    def timing(self) -> dict:
        sb = self.storyboard() if self._sb_path.is_file() else {}
        return self._timing_for(sb)

    def _timing_for(self, sb: dict) -> dict:
        rel = sb.get("timing") or "timing.json"
        try:
            p = safe_join(self.dir, rel)
            if p.is_file():
                return read_json(p)
        except Exception:
            pass
        return {"duration": float((sb.get("end") or {}).get("t") or 0), "words": [], "beats": [], "chapters": []}

    def _style_id(self, sb: dict) -> str:
        return sb.get("style") or "gae"

    def _registry(self, sb: dict) -> dict[str, dict]:
        try:
            st = load_style_stub(self.style_root, self._style_id(sb))
        except ApiError:
            return {}
        return {t["id"]: t for t in st["techniques"]}

    # ----- resolve -----
    def resolve(self, storyboard: dict | None = None) -> dict:
        sb = strip_derived(storyboard if storyboard is not None else self.storyboard())
        words = (self._timing_for(sb)).get("words") or []

        def at(a: dict, t0: float | None = None, t1: float | None = None) -> float | None:
            t = None
            try:
                if "t" in a and _num(a["t"]):
                    t = float(a["t"])
                elif "w" in a and isinstance(a["w"], int) and not isinstance(a["w"], bool) \
                        and 0 <= a["w"] < len(words):
                    t = float(words[a["w"]]["s"]) + float(a.get("off") or 0.0)
                elif "rel" in a and _num(a["rel"]) and t0 is not None and t1 is not None:
                    t = t0 + float(a["rel"]) * (t1 - t0)
            except (TypeError, ValueError, KeyError):
                t = None
            if t is not None:
                a["_t"] = round(t, 4)
            return t

        def walk(obj: Any, t0: float, t1: float) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ("at", "start", "end") and _is_anchor(v):
                        at(v, t0, t1)
                    else:
                        walk(v, t0, t1)
            elif isinstance(obj, list):
                for v in obj:
                    walk(v, t0, t1)

        shots = sb.get("shots") or []
        end_t = (sb.get("end") or {}).get("t")
        end_t = float(end_t) if _num(end_t) else None
        starts: list[float | None] = []
        for s in shots:
            a = s.get("start") if isinstance(s, dict) else None
            starts.append(at(a) if _is_anchor(a) else None)
        for i, s in enumerate(shots):
            if not isinstance(s, dict):
                continue
            t0 = starts[i]
            nxt = starts[i + 1] if i + 1 < len(shots) else end_t
            t1 = nxt
            if t0 is not None:
                s["_t0"] = round(t0, 4)
            if t1 is not None:
                s["_t1"] = round(t1, 4)
            span0 = t0 if t0 is not None else 0.0
            span1 = t1 if t1 is not None else span0
            walk(s.get("params"), span0, span1)
            if isinstance(s.get("transition_in"), dict):
                walk(s["transition_in"], span0, span1)
            for o in s.get("overlays") or []:
                if not isinstance(o, dict):
                    continue
                ot0 = at(o["start"], span0, span1) if _is_anchor(o.get("start")) else None
                ot1 = None
                if ot0 is not None:
                    if _num(o.get("dur")):
                        ot1 = ot0 + float(o["dur"])
                    elif _is_anchor(o.get("end")):
                        ot1 = at(o["end"], span0, span1)
                    else:
                        ot1 = span1
                if ot0 is not None:
                    o["_t0"] = round(ot0, 4)
                if ot1 is not None:
                    o["_t1"] = round(ot1, 4)
                walk(o.get("params"), ot0 if ot0 is not None else span0, ot1 if ot1 is not None else span1)
        return sb

    # ----- validate -----
    def validate(self, storyboard: dict | None = None) -> list[dict]:
        issues: list[dict] = []

        def add(level: str, path: str, msg: str) -> None:
            issues.append({"level": level, "path": path, "message": msg})

        try:
            sb = storyboard if storyboard is not None else self.storyboard()
        except Exception as e:
            return [{"level": "error", "path": "", "message": f"cannot load storyboard: {e}"}]
        if not isinstance(sb, dict):
            return [{"level": "error", "path": "", "message": "storyboard must be an object"}]
        if sb.get("schema") != SCHEMA:
            add("error", "schema", f"schema must be {SCHEMA!r}")
        if sb.get("project") not in (None, self.dir.name):
            add("warn", "project", f"project {sb.get('project')!r} differs from folder {self.dir.name!r}")
        reg = self._registry(sb)
        if not reg:
            add("error", "style", f"style {self._style_id(sb)!r} not found")
        canvas = sb.get("canvas")
        if not (isinstance(canvas, dict) and all(_num(canvas.get(k)) and canvas[k] > 0 for k in ("w", "h", "fps"))):
            add("error", "canvas", "canvas needs positive w, h and fps")
        timing = self._timing_for(sb)
        words = timing.get("words") or []
        duration = timing.get("duration")
        assets = sb.get("assets")
        if not isinstance(assets, dict):
            add("error", "assets", "assets must be an object")
            assets = {}
        for k, a in assets.items():
            p = f"assets.{k}"
            if not isinstance(a, dict):
                add("error", p, "asset must be an object")
                continue
            if a.get("kind") not in ("image", "video", "mask"):
                add("error", p + ".kind", "kind must be image, video or mask")
            f = a.get("file")
            if not isinstance(f, str) or not f:
                add("error", p + ".file", "file is required")
            else:
                try:
                    if not safe_join(self.dir, f).is_file():
                        add("warn", p + ".file", f"file {f!r} not found")
                except ApiError:
                    add("error", p + ".file", "file path escapes the project")
            for rn, r in (a.get("regions") or {}).items():
                if not (isinstance(r, dict) and _num(r.get("x")) and _num(r.get("y"))):
                    add("error", f"{p}.regions.{rn}", "region needs numeric x and y")

        def check_params(path: str, tech: dict, params: Any) -> None:
            if params is None:
                return
            if not isinstance(params, dict):
                add("error", path, "params must be an object")
                return
            defs = {d["name"]: d for d in tech.get("params") or []}
            for name, val in params.items():
                if name.startswith("_"):
                    continue
                d = defs.get(name)
                if d is None:
                    add("error", f"{path}.{name}", f"unknown parameter {name!r} for {tech['id']}")
                    continue
                ty = d.get("type")
                if val is None:
                    continue
                if ty == "number":
                    if not _num(val):
                        add("error", f"{path}.{name}", "must be a number")
                    else:
                        if d.get("min") is not None and val < d["min"] or d.get("max") is not None and val > d["max"]:
                            add("warn", f"{path}.{name}", f"{val} outside {d.get('min')}..{d.get('max')}")
                elif ty == "enum":
                    if val not in (d.get("values") or []):
                        add("error", f"{path}.{name}", f"must be one of {d.get('values')}")
                elif ty == "bool" and not isinstance(val, bool):
                    add("error", f"{path}.{name}", "must be true or false")
                elif ty in ("string", "color") and not isinstance(val, str):
                    add("error", f"{path}.{name}", "must be a string")

        def check_anchor(path: str, a: Any, allow_rel: bool) -> float | None:
            if not _is_anchor(a):
                add("error", path, "anchor needs t, w or rel")
                return None
            if "rel" in a:
                if not allow_rel:
                    add("error", path, "rel anchors are allowed only inside a shot (camera keys)")
                return None
            if "w" in a:
                w = a["w"]
                if not isinstance(w, int) or isinstance(w, bool) or not 0 <= w < len(words):
                    add("error", path, f"word index {w!r} outside timing.words")
                    return None
                if a.get("text") not in (None, words[w].get("w")):
                    add("warn", path, f"stale anchor: word {w} is {words[w].get('w')!r}, anchor says {a.get('text')!r}")
                return float(words[w]["s"]) + float(a.get("off") or 0.0)
            if not _num(a.get("t")):
                add("error", path, "t must be a number")
                return None
            return float(a["t"])

        shots = sb.get("shots")
        if not isinstance(shots, list) or not shots:
            add("error", "shots", "shots must be a non-empty list")
            shots = []
        end_t = (sb.get("end") or {}).get("t") if isinstance(sb.get("end"), dict) else None
        if not _num(end_t):
            add("error", "end.t", "end.t is required")
            end_t = None
        elif _num(duration) and end_t > duration + 0.5:
            add("warn", "end.t", f"end {end_t} is past the timing duration {duration}")
        ids: set[str] = set()
        t0s: list[float | None] = []
        for i, s in enumerate(shots):
            p = f"shots[{i}]"
            if not isinstance(s, dict):
                add("error", p, "shot must be an object")
                t0s.append(None)
                continue
            sid = s.get("id")
            if not isinstance(sid, str) or not ITEM_ID.fullmatch(sid):
                add("error", p + ".id", "id must match [A-Za-z0-9_-]+")
            elif sid in ids:
                add("error", p + ".id", f"duplicate shot id {sid!r}")
            else:
                ids.add(sid)
            t0s.append(check_anchor(p + ".start", s.get("start"), False))
            for flag in ("locked",):
                if flag in s and not isinstance(s[flag], bool):
                    add("error", f"{p}.{flag}", "must be true or false")
            if s.get("source") not in (None, *SOURCES):
                add("warn", p + ".source", f"source should be one of {SOURCES}")
        for i, s in enumerate(shots):
            if not isinstance(s, dict):
                continue
            p = f"shots[{i}]"
            t0 = t0s[i]
            nxt = t0s[i + 1] if i + 1 < len(shots) else end_t
            if t0 is not None and nxt is not None and nxt - t0 < MIN_SHOT - 1e-6:
                add("error", p + ".start", f"shot is {nxt - t0:.3f}s long; minimum is {MIN_SHOT}s "
                    "(shots must be in time order)")
            tid = s.get("technique")
            tech = reg.get(tid) if isinstance(tid, str) else None
            if tech is None:
                add("error", p + ".technique", f"unknown technique {tid!r}")
            else:
                if tech.get("kind") not in ("base", "card"):
                    add("error", p + ".technique", f"{tid} is a {tech.get('kind')}, a shot needs base or card")
                if (tech.get("engine") or {}).get("available") is False:
                    add("warn", p + ".technique", f"{tid} is not available in the engine yet")
                check_params(p + ".params", tech, s.get("params"))
                slots = s.get("slots") or {}
                if not isinstance(slots, dict):
                    add("error", p + ".slots", "slots must be an object")
                    slots = {}
                sdefs = {d["name"]: d for d in tech.get("slots") or []}
                for sn in slots:
                    if sn not in sdefs:
                        add("error", f"{p}.slots.{sn}", f"unknown slot {sn!r} for {tid}")
                for sn, d in sdefs.items():
                    if d.get("required") and d.get("type") in ("image", "video") and sn not in slots:
                        add("warn", f"{p}.slots.{sn}", f"required slot {sn!r} is empty")
            for sn, sv in (s.get("slots") or {}).items() if isinstance(s.get("slots"), dict) else []:
                if isinstance(sv, dict) and "asset" in sv and sv["asset"] not in assets:
                    add("error", f"{p}.slots.{sn}.asset", f"unknown asset {sv['asset']!r}")
            tr = s.get("transition_in")
            if tr is not None:
                ttech = reg.get(tr.get("technique")) if isinstance(tr, dict) else None
                if ttech is None or ttech.get("kind") != "transition":
                    add("error", p + ".transition_in", "needs a transition technique")
                elif not (_num(tr.get("dur")) and tr["dur"] > 0):
                    add("error", p + ".transition_in.dur", "dur must be positive")
                else:
                    check_params(p + ".transition_in.params", ttech, tr.get("params"))
            oids: set[str] = set()
            ovs = s.get("overlays") or []
            if not isinstance(ovs, list):
                add("error", p + ".overlays", "overlays must be a list")
                ovs = []
            for j, o in enumerate(ovs):
                op = f"{p}.overlays[{j}]"
                if not isinstance(o, dict):
                    add("error", op, "overlay must be an object")
                    continue
                oid = o.get("id")
                if not isinstance(oid, str) or not ITEM_ID.fullmatch(oid):
                    add("error", op + ".id", "id must match [A-Za-z0-9_-]+")
                elif oid in oids:
                    add("error", op + ".id", f"duplicate overlay id {oid!r} in shot")
                else:
                    oids.add(oid)
                otech = reg.get(o.get("technique"))
                if otech is None or otech.get("kind") != "overlay":
                    add("error", op + ".technique", f"{o.get('technique')!r} is not an overlay technique")
                else:
                    if (otech.get("engine") or {}).get("available") is False:
                        add("warn", op + ".technique", f"{otech['id']} is not available in the engine yet")
                    check_params(op + ".params", otech, o.get("params"))
                ot0 = check_anchor(op + ".start", o.get("start"), False)
                ot1 = None
                if ot0 is not None:
                    if "dur" in o:
                        if not (_num(o["dur"]) and o["dur"] > 0):
                            add("error", op + ".dur", "dur must be a positive number")
                        else:
                            ot1 = ot0 + o["dur"]
                    elif o.get("end") is not None:
                        ot1 = check_anchor(op + ".end", o["end"], False)
                    if t0 is not None and ot0 < t0 - 0.01:
                        add("error", op + ".start", f"starts at {ot0:.2f}s, before its shot ({t0:.2f}s)")
                    if nxt is not None and ot0 >= nxt:
                        add("error", op + ".start", f"starts at {ot0:.2f}s, after its shot ends ({nxt:.2f}s)")
                    if ot1 is not None and nxt is not None and ot1 > nxt + 0.01:
                        add("error", op, f"ends at {ot1:.2f}s, after its shot ends ({nxt:.2f}s)")
        return issues

    # ----- defaults -----
    def default_params(self, technique_id: str, context: dict) -> dict:
        tech = self._registry(self.storyboard() if self._sb_path.is_file() else {}).get(technique_id)
        if tech is None:
            raise ApiError(422, f"unknown technique {technique_id!r}")
        out = {}
        for d in tech.get("params") or []:
            if d.get("default") is not None:
                out[d["name"]] = d["default"]
        return out

    # ----- save -----
    def save(self, storyboard: dict) -> str:
        sb = strip_derived(storyboard)
        errs = [i for i in self.validate(sb) if i["level"] == "error"]
        if errs:
            raise ApiError(422, "validation failed", issues=errs)
        if self._sb_path.is_file():
            hist = self.dir / "history"
            hist.mkdir(exist_ok=True)
            try:
                old = self._sb_path.read_bytes()
                (hist / f"storyboard_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 10**6:06d}.json").write_bytes(old)
                files = sorted(hist.glob("storyboard_*.json"))
                for f in files[:-60]:
                    f.unlink(missing_ok=True)
            except OSError:
                pass
        write_json_atomic(self._sb_path, sb)
        return compute_rev(sb)

    # ----- frames -----
    def use_draft(self, storyboard: dict | None) -> None:
        self._draft = strip_derived(storyboard) if storyboard is not None else None

    def _font(self, size: int):
        f = self._font_cache.get(size)
        if f is None:
            try:
                f = ImageFont.load_default(size=size)
            except TypeError:
                f = ImageFont.load_default()
            self._font_cache[size] = f
        return f

    def frame_at(self, t: float, width: int = 960) -> np.ndarray:
        width = max(64, int(width))
        height = max(36, round(width * 9 / 16))
        sb = self._draft if self._draft is not None else self.storyboard()
        res = self.resolve(sb)
        words = self._timing_for(sb).get("words") or []
        shot = None
        for s in res.get("shots") or []:
            if "_t0" in s and s["_t0"] <= t + 1e-9 and (s.get("_t1") is None or t < s["_t1"]):
                shot = s
        word = ""
        for w in words:
            if w["s"] <= t < w["e"] + 0.15:
                word = w["w"]
                break
        img = Image.new("RGB", (width, height), (92, 92, 98))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, width - 1, height - 1], outline=(150, 150, 156), width=max(1, width // 320))
        u = width / 960.0
        reg = self._registry(sb)
        lines = []
        if shot:
            tech = shot.get("technique")
            lines.append((f"{shot.get('id')}", 64, (255, 255, 255)))
            lines.append((f"{tech}  {(reg.get(tech) or {}).get('name', '')}", 28, (230, 230, 235)))
            ovs = [o.get("technique") for o in shot.get("overlays") or []
                   if o.get("_t0") is not None and o["_t0"] <= t < (o.get("_t1") or 1e9)]
            if ovs:
                lines.append(("overlay: " + ", ".join(ovs), 22, (255, 220, 140)))
        else:
            lines.append(("no shot", 48, (255, 200, 200)))
        lines.append((f"t = {t:7.2f} s", 34, (255, 255, 255)))
        lines.append((f"word: {word}" if word else "word: -", 34, (200, 230, 255)))
        y = int(height * 0.12)
        for text, size, col in lines:
            f = self._font(max(8, int(size * u)))
            d.text((int(width * 0.06), y), text, fill=col, font=f)
            y += int(size * u * 1.45)
        if shot and shot.get("_t1") and shot.get("_t0") is not None:
            frac = min(1.0, max(0.0, (t - shot["_t0"]) / max(1e-6, shot["_t1"] - shot["_t0"])))
            bh = max(3, int(8 * u))
            d.rectangle([int(width * 0.06), height - int(height * 0.1), int(width * 0.94), height - int(height * 0.1) + bh],
                        fill=(60, 60, 64))
            d.rectangle([int(width * 0.06), height - int(height * 0.1),
                         int(width * 0.06 + width * 0.88 * frac), height - int(height * 0.1) + bh], fill=(240, 240, 240))
        return np.asarray(img)[:, :, ::-1].copy()  # BGR

    def render_range(self, t0: float, t1: float, out_path: Path, width: int = 640, fps: int = 15,
                     on_progress: Callable[[float], None] | None = None) -> Path:
        width = max(64, int(width)) // 2 * 2
        height = max(36, round(width * 9 / 16)) // 2 * 2
        n = max(1, int(round((t1 - t0) * fps)))
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{width}x{height}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
               "-pix_fmt", "yuv420p", "-preset", "veryfast", "-movflags", "+faststart", str(out_path)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i in range(n):
                fr = self.frame_at(t0 + i / fps, width)
                if fr.shape[0] != height:
                    fr = np.asarray(Image.fromarray(fr[:, :, ::-1]).resize((width, height)))[:, :, ::-1]
                proc.stdin.write(np.ascontiguousarray(fr).tobytes())
                if on_progress:
                    on_progress((i + 1) / n)
            proc.stdin.close()
            err = proc.stderr.read().decode("utf-8", "replace")
            if proc.wait() != 0:
                raise RuntimeError(f"ffmpeg failed: {err[-300:]}")
        except BaseException:
            try:
                proc.kill()
            except Exception:
                pass
            raise
        return out_path
