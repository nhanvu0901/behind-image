import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True

from bti.engine.api import open_project  # noqa: E402


def make_image(path: Path, w=800, h=1200, seed=1):
    rng = np.random.RandomState(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    img = np.stack([(xx * 255 // w), (yy * 255 // h), ((xx + yy) * 255 // (w + h))], -1).astype(np.uint8)
    cv2.circle(img, (w // 2, h // 3), 90, (255, 255, 255), -1)
    img = np.clip(img.astype(int) + rng.randint(0, 20, img.shape), 0, 255).astype(np.uint8)
    cv2.imwrite(str(path), img)


def words(n=40, step=0.5):
    names = "alpha beta gamma delta epsilon zeta eta theta iota kappa".split()
    return [{"w": names[i % 10] + ("," if i % 7 == 6 else ""), "s": round(i * step, 3), "e": round(i * step + 0.4, 3)} for i in range(n)]


def base_storyboard():
    cam = lambda a, b: [{"at": {"rel": 0.0}, "cx": 400, "cy": 600, "zoom": a, "ease": "inout_cubic"}, {"at": {"rel": 1.0}, "cx": 400, "cy": 500, "zoom": b, "ease": "linear"}]
    return {
        "schema": "bti.storyboard/1", "project": "tiny", "title": "Tiny", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30},
        "timing": "timing.json", "audio": None,
        "assets": {"A": {"file": "media/a.jpg", "kind": "image", "title": "Test", "artist": "Nobody", "year": "1999", "width": 800, "height": 1200,
                         "credit": {"source": "test", "source_url": "", "author": "x", "licence": "PD", "licence_url": ""},
                         "regions": {"FACE": {"x": 400, "y": 400, "rx": 120, "ry": 120, "label": "Face"}}},
                   "B": {"file": "media/b.jpg", "kind": "image", "title": "Other", "artist": "Else", "year": "1500", "width": 900, "height": 700,
                         "credit": {"source": "test", "source_url": "", "author": "x", "licence": "PD", "licence_url": ""}}},
        "shots": [
            {"id": "s1", "start": {"t": 0.0}, "technique": "CAM-05", "intent": "point_at", "slots": {"image": {"asset": "A"}},
             "params": {"camera": cam(0.3, 0.6)}, "transition_in": None,
             "overlays": [
                 {"id": "o1", "technique": "HI-01", "intent": "isolate", "start": {"w": 3, "off": 0.0, "text": "delta"}, "dur": 3.0,
                  "params": {"at": "FACE", "rx": 200, "ry": 200}, "locked": False, "source": "import", "note": ""},
                 {"id": "o2", "technique": "AN-01", "intent": "point_at", "start": {"w": 4, "off": 0.1, "text": "epsilon"}, "dur": 3.0,
                  "params": {"at": [400, 500], "radius": 100}, "locked": False, "source": "import", "note": ""},
                 {"id": "o3", "technique": "X-ANN-01", "intent": "point_at", "start": {"t": 1.0}, "dur": 3.0,
                  "params": {"text": "A label"}, "locked": False, "source": "import", "note": ""}],
             "locked": False, "source": "import", "note": ""},
            {"id": "s2", "start": {"w": 12, "off": 0.0, "text": "gamma"}, "technique": "X-CARD-01", "intent": "structure", "slots": {},
             "params": {"title": "CHAPTER ONE"}, "transition_in": None, "overlays": [], "locked": False, "source": "import", "note": ""},
            {"id": "s3", "start": {"t": 9.0}, "technique": "STATIC-01", "intent": "establish", "slots": {"image": {"asset": "B"}},
             "params": {"camera": cam(0.5, 0.55)}, "transition_in": {"technique": "TR-01", "dur": 1.0, "params": {}}, "overlays": [], "locked": False, "source": "import", "note": ""},
        ],
        "end": {"t": 19.0}, "approvals": {"storyboard": None},
    }


@pytest.fixture()
def tiny(tmp_path):
    d = tmp_path / "tiny"
    (d / "media").mkdir(parents=True)
    make_image(d / "media" / "a.jpg", 800, 1200, 1)
    make_image(d / "media" / "b.jpg", 900, 700, 2)
    (d / "timing.json").write_text(json.dumps({"duration": 20.0, "words": words(), "beats": [], "chapters": []}), encoding="utf-8")
    (d / "storyboard.json").write_text(json.dumps(base_storyboard(), indent=1), encoding="utf-8")
    return d


@pytest.fixture()
def tiny_project(tiny):
    return open_project(tiny)


@pytest.fixture(scope="session")
def arnolfini():
    d = REPO / "projects" / "arnolfini"
    if not (d / "storyboard.json").exists():
        pytest.skip("projects/arnolfini not exported")
    return open_project(d)
