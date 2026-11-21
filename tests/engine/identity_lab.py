"""Shots that carry the eight ID-* techniques (channel identity), for the sweeps that need one reference item per technique.

`projects/technique_lab` was built before the family existed; `append_identity_shots` adds one shot (or overlay) per technique to a
COPY of its storyboard, each at its nominal length, so the registry sweeps cover all 86 ids without touching the lab project (the eight ID-* ones, then TIME-01, TREE-01 and STATE-01, then MAP-01, which came later still, then the overlays
KEY-01, NUM-01 and DOC-01).
"""
from __future__ import annotations

import json
from pathlib import Path

IDENTITY_IDS = ["ID-OPEN-01", "ID-LABEL-01", "ID-OPEN-02", "ID-BRAND-01", "ID-BRAND-02", "ID-MARK-01", "ID-MARK-02", "ID-BRAND-03"]


def _shot(n, start, tech, asset, camera, extra=None, overlays=None, transition=None):
    return {"id": "id%02d" % n, "start": {"t": round(start, 3)}, "technique": tech, "intent": "structure" if tech.startswith("ID-") else "explore",
            "slots": {"image": {"asset": asset}}, "params": dict({"camera": camera}, **(extra or {})), "transition_in": transition,
            "overlays": overlays or [], "locked": False, "source": "agent", "note": "identity sweep"}


def _ov(n, tech, start, dur):
    return {"id": "ido%02d" % n, "technique": tech, "intent": "establish", "start": {"t": round(start, 3)}, "dur": dur, "params": {},
            "locked": False, "source": "agent", "note": ""}


def append_identity_shots(sb: dict, asset: str, camera: list) -> dict:
    """Append the eight techniques after the last shot of `sb` (in place; returns it). `camera` is a camera key list that looks at `asset`."""
    t = float(sb["end"]["t"])                      # the new shots start where the last old shot ended
    plan = [("CAM-01", 12.0, [("ID-OPEN-01", 0.0, 9.0), ("ID-LABEL-01", 6.2, 4.5)]),
            ("CAM-01", 6.0, [("ID-OPEN-02", 0.0, 5.0)]),
            ("ID-BRAND-01", 5.0, []), ("ID-BRAND-02", 4.0, []), ("ID-MARK-01", 3.2, []), ("ID-MARK-02", 3.0, []), ("ID-BRAND-03", 9.1, [])]
    n = 0
    for tech, length, overlays in plan:
        n += 1
        ovs = [_ov(10 * n + k, o, t + off, dur) for k, (o, off, dur) in enumerate(overlays)]
        extra = {"title": "5. The Mirror"} if tech.startswith("ID-MARK") else ({"text": "RAKING LIGHT"} if tech.startswith("ID-BRAND") else None)
        if tech == "ID-BRAND-03":                                                        # the beat that writes the video's title: give it both lines
            extra = {"text": "RAKING LIGHT", "title": "The Mirror in the Arnolfini Portrait", "subtitle": "The Arnolfini Portrait \u00b7 Jan van Eyck, 1434"}
        sb["shots"].append(_shot(n, t, tech, asset, camera, extra, ovs))
        t += length
    sb["end"] = {"t": round(t + 3.0, 3), "fade_s": 0}
    return sb


def append_explain_base_shots(sb: dict, asset: str) -> dict:
    """One shot each of TIME-01 and TREE-01 (the default examples, 8 s) and STATE-01 (both slots hold `asset`, 7.5 s) after the last shot of `sb`."""
    t = float(sb["end"]["t"])
    for tid, slots, dur in (("TIME-01", {}, 8.0), ("TREE-01", {}, 8.0), ("STATE-01", {"a": {"asset": asset}, "b": {"asset": asset}}, 7.5)):
        sb["shots"].append({"id": "eb_" + tid.lower().replace("-", ""), "start": {"t": round(t, 3)}, "technique": tid, "intent": "context", "slots": slots, "params": {},
                            "transition_in": None, "overlays": [], "locked": False, "source": "agent", "note": tid + " sweep"})
        t += dur
    sb["end"] = {"t": round(t, 3), "fade_s": 0}
    return sb


def append_map_shot(sb: dict) -> dict:
    """One MAP-01 shot of 8 s (the default example: Bruges to Lucca, Belgium) after the last shot of `sb`."""
    t = float(sb["end"]["t"])
    sb["shots"].append({"id": "map01", "start": {"t": round(t, 3)}, "technique": "MAP-01", "intent": "context", "slots": {}, "params": {},
                        "transition_in": None, "overlays": [], "locked": False, "source": "agent", "note": "MAP-01 sweep"})
    sb["end"] = {"t": round(t + 8.0, 3), "fade_s": 0}
    return sb


# compover: KEY-01, NUM-01 and DOC-01 are overlays on a shot that shows the Arnolfini Portrait (the regions of their default data are the lab picture's own).
EXPLAIN_OVERLAYS = [("KEY-01", [(2220, 1410, 0.5), (2220, 1410, 0.54)]), ("NUM-01", [(3218, 2987, 0.822), (3218, 2987, 0.822)]), ("DOC-01", [(2220, 1302.5, 0.727), (2220, 1455, 1.2)])]


def append_explain_shots(sb: dict, asset: str) -> dict:
    """Three CAM-01 shots of 7.5 s after the last shot of `sb`, each carrying one default overlay of 7 s (KEY-01, NUM-01, DOC-01) on a camera that frames the example."""
    t = float(sb["end"]["t"])
    for n, (tid, cams) in enumerate(EXPLAIN_OVERLAYS):
        camera = [{"at": {"rel": 0.0}, "cx": cams[0][0], "cy": cams[0][1], "zoom": cams[0][2], "ease": "linear"}, {"at": {"rel": 1.0}, "cx": cams[1][0], "cy": cams[1][1], "zoom": cams[1][2], "ease": "linear"}]
        sb["shots"].append({"id": "ex%02d" % n, "start": {"t": round(t, 3)}, "technique": "CAM-01", "intent": "explore", "slots": {"image": {"asset": asset}}, "params": {"camera": camera},
                            "transition_in": None, "locked": False, "source": "agent", "note": tid + " sweep",
                            "overlays": [{"id": "exo%02d" % n, "technique": tid, "intent": "point_at", "start": {"t": round(t + 0.25, 3)}, "dur": 7.0, "params": {}, "locked": False, "source": "agent", "note": ""}]})
        t += 7.5
    sb["end"] = {"t": round(t, 3), "fade_s": 0}
    return sb


def add_to_project_dir(project_dir: Path) -> None:
    """Edit storyboard.json of a COPY of technique_lab on disk (the first shot's camera and asset are reused)."""
    p = Path(project_dir) / "storyboard.json"
    sb = json.loads(p.read_text(encoding="utf-8"))
    first = sb["shots"][0]
    append_identity_shots(sb, first["slots"]["image"]["asset"], first["params"]["camera"])
    append_explain_base_shots(sb, first["slots"]["image"]["asset"])
    append_map_shot(sb)
    append_explain_shots(sb, first["slots"]["image"]["asset"])
    p.write_text(json.dumps(sb, indent=1), encoding="utf-8")
