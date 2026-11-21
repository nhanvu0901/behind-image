"""Forced alignment worker. Runs in the ALIGNER's Python (`.venv-align`, which has faster-whisper), not in the app's.

    python align_worker.py <wav> <spans.json> <out.json> <model> [model_dir] [language]

`spans.json`: [{"index": int, "start": s, "end": e}] (the span of each sentence in the wav). The worker recognises each sentence
inside its own span (with a small margin) and writes {"<index>": [{"w", "s", "e"}]} in absolute seconds. Only numpy and
faster-whisper are imported, besides the standard library."""
from __future__ import annotations

import json
import subprocess
import sys


def main(argv: list[str]) -> int:
    wav, spans_file, out_file, model_name = argv[1:5]
    model_dir = argv[5] if len(argv) > 5 and argv[5] else None
    lang = argv[6] if len(argv) > 6 and argv[6] else "en"
    import numpy as np
    from faster_whisper import WhisperModel
    with open(spans_file, encoding="utf-8") as fh:
        spans = json.load(fh)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", wav, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    audio = np.frombuffer(raw, np.float32)
    model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=model_dir, cpu_threads=6)
    margin = 0.15
    out: dict[str, list] = {}
    for n, sp in enumerate(spans):
        a = max(0.0, sp["start"] - margin)
        b = sp["end"] + margin
        clip = audio[int(a * 16000):int(b * 16000)]
        words = []
        if len(clip) > 1600:
            segs, _ = model.transcribe(clip, language=lang, word_timestamps=True, beam_size=5, condition_on_previous_text=False)
            for s in segs:
                for w in (s.words or []):
                    words.append({"w": w.word.strip(), "s": round(a + w.start, 4), "e": round(a + w.end, 4)})
        out[str(sp["index"])] = words
        print(json.dumps({"i": n, "of": len(spans)}), flush=True)
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
