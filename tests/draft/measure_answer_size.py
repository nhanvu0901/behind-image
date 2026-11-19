"""How long is the answer a model has to write? (worker c2box; replaces the script that measured the delta answer of the full-compile fast path.) The
output is what costs the time of a call, not the briefing. Prints the size, in characters of compact JSON, of typical answers of the prompt box (typed
operations) next to the size of the shot a model would have had to write whole in the old contract. No model is called.

    python tests/draft/measure_answer_size.py          (needs only the repository: no project, no server)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

CAMERA = [{"at": {"rel": 0}, "cx": 812, "cy": 520, "zoom": 0.62, "ease": "inout_cubic"}, {"at": {"rel": 1}, "cx": 790, "cy": 470, "zoom": 0.74, "ease": "inout_cubic"}]
RING = {"id": "o1", "technique": "AN-01", "intent": "point_at", "start": {"w": 218, "off": 0.0}, "dur": 3.0, "params": {"at": "MIRROR", "radius": 180, "draw_s": 0.5, "hold_s": 2.0, "fade_s": 0.4}}
SHOT = {"id": "s0004", "beat": "b0007", "start_word": 212, "off": 0.0, "technique": "CAM-01", "intent": "point_at", "slots": {"image": {"asset": "A", "region": "MIRROR"}},
        "params": {"camera": CAMERA}, "overlays": [RING], "note": ""}


def size(o) -> int:
    return len(json.dumps(o, ensure_ascii=False, separators=(",", ":")))


def main():
    answers = {
        "a ring made bigger (1 operation)": {"status": "applied", "summary": "Vòng sáng ở cảnh này to hơn.", "reason": "", "ops": [{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 260, "ry": 260}}]},
        "a slower camera and a ring (2 operations)": {"status": "applied", "summary": "Máy quay đi chậm hơn và có thêm vòng khoanh quanh chiếc gương.", "reason": "", "ops": [
            {"op": "set_params", "shot": "s0004", "params": {"camera": CAMERA}}, {"op": "add_overlay", "shot": "s0004", "technique": "AN-01", "params": {"at": "MIRROR"}, "start": {"w": 218}, "dur": 3.0}]},
        "a refusal (cannot)": {"status": "cannot", "summary": "", "reason": "Cần chọn thêm cảnh sau để kéo dài cảnh này.", "ops": []},
        "twelve shots, a slower camera on each": {"status": "applied", "summary": "Máy quay ở cả mười hai cảnh đi chậm hơn.", "reason": "",
                                                     "ops": [{"op": "set_params", "shot": "s%04d" % i, "params": {"camera": CAMERA}} for i in range(12)]},
    }
    for label, a in answers.items():
        print("%-46s %5d characters" % (label, size(a)))
    print("the one shot the old contract had to write whole    %5d characters (x 12 shots = %d)" % (size(SHOT), 12 * size(SHOT)))


if __name__ == "__main__":
    main()
