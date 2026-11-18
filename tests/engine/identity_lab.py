"""Shots that carry the seven ID-* techniques (channel identity), for the sweeps that need one reference item per technique.

`projects/technique_lab` was built before the family existed; `append_identity_shots` adds one shot (or overlay) per technique to a
COPY of its storyboard, each at its nominal length, so the registry sweeps cover all 78 ids without touching the lab project.
"""
from __future__ import annotations

import json
from pathlib import Path

IDENTITY_IDS = ["ID-OPEN-01", "ID-LABEL-01", "ID-OPEN-02", "ID-BRAND-01", "ID-BRAND-02", "ID-MARK-01", "ID-MARK-02"]


def _shot(n, start, tech, asset, camera, extra=None, overlays=None, transition=None):
    return {"id": "id%02d" % n, "start": {"t": round(start, 3)}, "technique": tech, "intent": "structure" if tech.startswith("ID-") else "explore",
            "slots": {"image": {"asset": asset}}, "params": dict({"camera": camera}, **(extra or {})), "transition_in": transition,
            "overlays": overlays or [], "locked": False, "source": "agent", "note": "identity sweep"}


def _ov(n, tech, start, dur):
    return {"id": "ido%02d" % n, "technique": tech, "intent": "establish", "start": {"t": round(start, 3)}, "dur": dur, "params": {},
            "locked": False, "source": "agent", "note": ""}


def append_identity_shots(sb: dict, asset: str, camera: list) -> dict:
    """Append the seven techniques after the last shot of `sb` (in place; returns it). `camera` is a camera key list that looks at `asset`."""
    t = float(sb["end"]["t"])                      # the new shots start where the last old shot ended
    plan = [("CAM-01", 12.0, [("ID-OPEN-01", 0.0, 9.0), ("ID-LABEL-01", 6.2, 4.5)]),
            ("CAM-01", 6.0, [("ID-OPEN-02", 0.0, 5.0)]),
            ("ID-BRAND-01", 5.0, []), ("ID-BRAND-02", 4.0, []), ("ID-MARK-01", 3.2, []), ("ID-MARK-02", 3.0, [])]
    n = 0
    for tech, length, overlays in plan:
        n += 1
        ovs = [_ov(10 * n + k, o, t + off, dur) for k, (o, off, dur) in enumerate(overlays)]
        extra = {"title": "5. The Mirror"} if tech.startswith("ID-MARK") else ({"text": "RAKING LIGHT"} if tech.startswith("ID-BRAND") else None)
        sb["shots"].append(_shot(n, t, tech, asset, camera, extra, ovs))
        t += length
    sb["end"] = {"t": round(t + 3.0, 3), "fade_s": 0}
    return sb


def add_to_project_dir(project_dir: Path) -> None:
    """Edit storyboard.json of a COPY of technique_lab on disk (the first shot's camera and asset are reused)."""
    p = Path(project_dir) / "storyboard.json"
    sb = json.loads(p.read_text(encoding="utf-8"))
    first = sb["shots"][0]
    append_identity_shots(sb, first["slots"]["image"]["asset"], first["params"]["camera"])
    p.write_text(json.dumps(sb, indent=1), encoding="utf-8")
