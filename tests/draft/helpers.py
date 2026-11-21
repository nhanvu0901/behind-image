from __future__ import annotations

import json
from pathlib import Path


def _image(path: Path, w: int, h: int, seed: int = 0):
    import numpy as np
    import cv2
    y, x = np.mgrid[0:h, 0:w]
    img = np.stack([(x * 255 // w + seed * 40) % 256, (y * 255 // h) % 256, ((x + y) * 255 // (w + h)) % 256], axis=-1).astype("uint8")
    cv2.rectangle(img, (w // 4, h // 4), (3 * w // 4, h // 2), (20, 200, 240), -1)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 90])


def synth_timing(gap: float = 3.3) -> dict:
    words = []
    for i in range(60):
        s = 0.4 + 0.5 * i + (3.5 + gap - 3.3 if i >= 30 else 0.0)
        words.append({"w": "w%d" % i, "s": round(s, 3), "e": round(s + 0.4, 3)})
    beats = []
    for k in range(6):
        w0, w1 = k * 10, k * 10 + 10
        beats.append({"id": "b%04d" % (k + 1), "chapter": "c01" if k < 3 else "c02", "text": " ".join(w["w"] for w in words[w0:w1]),
                      "start": words[w0]["s"], "end": words[w1 - 1]["e"], "w0": w0, "w1": w1})
    c1_end = words[29]["e"]
    c2_start = round(words[30]["s"] - 0.3, 3)
    return {"duration": round(words[-1]["e"] + 0.5, 3), "words": words, "beats": beats,
            "chapters": [{"id": "c01", "name": "Intro", "start": 0.0, "end": c1_end, "card": False},
                         {"id": "c02", "name": "The mirror", "start": c2_start, "end": words[-1]["e"], "card": True}]}


def make_synth_project(d: Path, gap: float = 3.3) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    _image(d / "media" / "a.jpg", 800, 1200)
    _image(d / "media" / "b.jpg", 600, 400, seed=2)
    (d / "timing.json").write_text(json.dumps(synth_timing(gap)), encoding="utf-8")
    picks = {"schema": "bti.picks/1", "main_asset": "A",
             "assets": {"A": {"file": "media/a.jpg", "kind": "image", "title": "Main Painting", "artist": "Some Painter", "year": "1434",
                              "width": 800, "height": 1200,
                              "regions": {"MIRROR": {"x": 400, "y": 300, "rx": 80, "ry": 80, "label": "Mirror"}}},
                        "B": {"file": "media/b.jpg", "kind": "image", "title": "Street", "artist": "An Etcher", "year": "1500", "width": 600, "height": 400}},
             "beats": {"b0002": {"items": [{"asset": "A", "region": "MIRROR", "role": "detail", "note": ""}], "status": "picked"},
                       "b0004": {"items": [{"asset": "B", "region": None, "role": "context", "note": ""}], "status": "picked"}},
             "approval": {"approved": True}}
    (d / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    return d


def shot(beat, sw, tid="CAM-01", **kw):
    s = {"beat": beat, "start_word": sw, "technique": tid, "slots": kw.pop("slots", {"image": {"asset": "A"}}), "params": kw.pop("params", {}),
         "overlays": kw.pop("overlays", []), "note": kw.pop("note", "")}
    s.update(kw)
    return s


def spec(cid, *shots):
    return {"schema": "bti.draft/1", "chapter": cid, "shots": list(shots)}


def clean_spec(sp, cid=None):
    from bti.draft import spec as S
    import copy
    out, probs = S.shape_problems(copy.deepcopy(sp), cid)
    assert not [p for p in probs if p["level"] == "error"], probs
    return out


GOOD = {
    "c01": spec("c01", shot("b0001", 0, "CAM-01"), shot("b0002", 10, "CAM-05", slots={"image": {"asset": "A", "region": "MIRROR"}},
                                                     overlays=[{"technique": "HI-01", "start_word": 12, "end_word": 16, "params": {"at": "MIRROR"}}]),
                shot("b0003", 20, "CAM-03")),
    "c02": spec("c02", shot("b0004", 30, "X-LAY-01", slots={"image": {"asset": "B"}}), shot("b0005", 40, "STATIC-01"), shot("b0006", 50, "CAM-01")),
}
