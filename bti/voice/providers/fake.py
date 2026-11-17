"""The fake voice: a short tone per chunk whose length follows the text (about 0.05 s per character) so that tests can check
spans, silences and counts without a model. Deterministic: the same text and seed give the same samples."""
from __future__ import annotations

import math
import os
import struct
import wave
from pathlib import Path
from bti.fsio import atomic_replace

SR = 24000
SEC_PER_CHAR = 0.05


def tone_samples(text: str, seed: int, sec_per_char: float = SEC_PER_CHAR) -> list[int]:
    n = max(int(SR * max(len(text), 1) * sec_per_char), SR // 10)
    freq = 180 + (seed % 200)
    out = []
    ramp = int(0.01 * SR)
    for i in range(n):
        env = min(1.0, i / ramp, (n - i) / ramp)
        out.append(int(9000 * env * math.sin(2 * math.pi * freq * i / SR)))
    return out


def write_wav(path: Path, samples: list[int], sr: int = SR) -> None:
    tmp = path.with_name(path.name + ".part")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack("<%dh" % len(samples), *samples))
    atomic_replace(tmp, path)


class FakeProvider:
    name = "fake"

    def __init__(self, fail: set[str] | None = None):
        self.fail = set(fail or ())          # chunk spoken texts (or ids) that fail, for tests
        self.calls: list[list[str]] = []

    def synth(self, chunks, dest_dir: Path, ctx, workdir: Path | None = None) -> dict:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        self.calls.append([c.id for c in chunks])
        res: dict[str, dict] = {}
        for k, c in enumerate(chunks):
            if ctx.cancelled():
                break
            if c.id in self.fail or c.spoken in self.fail:
                res[c.id] = {"ok": False, "error": "fake failure"}
            else:
                s = tone_samples(c.spoken, c.seed)
                try:
                    write_wav(dest_dir / f"{c.id}.wav", s)
                except OSError as e:          # a file that cannot be finished fails this chunk only; the next part retries it
                    res[c.id] = {"ok": False, "error": "the audio file could not be finished: %s" % type(e).__name__}
                else:
                    res[c.id] = {"ok": True, "sec": len(s) / SR}
            ctx.progress((k + 1) / len(chunks), f"{k + 1}/{len(chunks)}")
        return res
