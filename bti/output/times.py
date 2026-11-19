"""When each shot starts and ends, in seconds. The anchors of a shot are `{"t": seconds}` or `{"w": word index, "off": seconds}` (a word of `timing.json`); both are resolved here
without the engine. A shot whose anchor is of another kind is asked of the engine (`Project.resolve`, the same call the export uses); when that fails too its time is None."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("bti.output")


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def anchor_seconds(a: Any, words: list) -> float | None:
    if not isinstance(a, dict):
        return None
    if "t" in a and _num(a["t"]):
        return float(a["t"])
    if "w" in a and isinstance(a["w"], int) and not isinstance(a["w"], bool) and 0 <= a["w"] < len(words):
        w = words[a["w"]]
        if isinstance(w, dict) and _num(w.get("s")):
            return float(w["s"]) + (float(a["off"]) if _num(a.get("off")) else 0.0)
    return None


def shot_times(pdir: Path, sb: dict, timing: dict | None) -> list[tuple[float | None, float | None]]:
    """[(start, end)] of every shot of the storyboard, in its order."""
    shots = [s for s in (sb.get("shots") or []) if isinstance(s, dict)]
    words = (timing or {}).get("words") if isinstance((timing or {}).get("words"), list) else []
    starts = [anchor_seconds(s.get("start"), words) for s in shots]
    end = anchor_seconds(sb.get("end"), words)
    if any(t is None for t in starts) or end is None:
        try:
            from bti.engine.api import open_project
            r = open_project(Path(pdir)).resolve()
            rs = [s for s in (r.get("shots") or []) if isinstance(s, dict)]
            if len(rs) == len(shots):
                starts = [float(s["_t0"]) if _num(s.get("_t0")) else st for s, st in zip(rs, starts)]
                if end is None and isinstance(r.get("end"), dict) and _num(r["end"].get("_t")):
                    end = float(r["end"]["_t"])
        except Exception:       # noqa: BLE001 - a time that cannot be known is shown as a dash
            log.info("the shot times could not be asked of the engine", exc_info=True)
    out = []
    for i, t0 in enumerate(starts):
        t1 = starts[i + 1] if i + 1 < len(starts) else end
        out.append((t0, t1))
    return out
