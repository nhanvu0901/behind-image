"""The real voice: the comic pipeline's Chatterbox worker, run as a child process with the comic voice Python. Both are only
read: the worker is a stand-alone script (no import from the comic repository) that takes a job file and writes one WAV per
chunk. Paths come from `config/server.json`.

Job file: {"chunks": [{"text", "exaggeration", "cfg_weight", "seed"}], "out_dir", "audio_prompt", "temperature", "device", "seed"}.
The worker writes `out_dir/chunk_<i:05d>.wav` and prints one JSON line per chunk: {"i", "sec", "sr"} or {"i", "error"}.
Every chunk carries its own seed, so a sentence sounds the same wherever it stands in a part."""
from __future__ import annotations

import json
import os
import time
import wave
from pathlib import Path

from ..errors import VoiceError


def wav_seconds(path: Path) -> float | None:
    """Duration of a WAV file, None when it is missing, empty or not a WAV."""
    try:
        with wave.open(str(path), "rb") as wf:
            n, sr = wf.getnframes(), wf.getframerate()
        return n / sr if n > 0 and sr > 0 else None
    except (OSError, EOFError, wave.Error):
        return None


class ChatterboxProvider:
    name = "chatterbox"

    def __init__(self, worker: dict):
        self.w = worker
        self.timing: dict = {}

    def command(self, job_file: Path) -> list[str]:
        return [self.w["python"], "-B", self.w["worker"], str(job_file)]

    def job(self, chunks, out_dir: Path) -> dict:
        w = self.w
        return {"chunks": [{"text": c.spoken, "exaggeration": float(w["exaggeration"]), "cfg_weight": float(w["cfg_weight"]),
                            "seed": int(c.seed)} for c in chunks],
                "out_dir": str(out_dir), "audio_prompt": w["reference"], "temperature": float(w["temperature"]),
                "device": w["device"], "seed": 42}

    def synth(self, chunks, dest_dir: Path, ctx, workdir: Path | None = None) -> dict:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        work = Path(workdir or ctx.workdir) / "chatterbox"
        out_dir = work / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob("chunk_*.wav"):
            try:
                old.unlink()
            except OSError:
                pass
        job_file = work / "job.json"
        job_file.write_text(json.dumps(self.job(chunks, out_dir), ensure_ascii=False), encoding="utf-8")
        errors: dict[int, str] = {}
        done = {"n": 0}
        t0 = time.monotonic()
        self.timing = {"load_s": None, "total_s": None, "chunks": 0}

        def on_line(line: str) -> None:
            line = (line or "").strip()
            if not line.startswith("{"):
                return
            try:
                d = json.loads(line)
            except ValueError:
                return
            if not isinstance(d, dict):
                return
            if d.get("ready"):
                self.timing["load_s"] = round(time.monotonic() - t0, 1)
                ctx.log("voice model ready after %.1f s" % self.timing["load_s"])
                return
            if "error" in d and isinstance(d.get("i"), int):
                errors[d["i"]] = str(d["error"])[:300]
                done["n"] += 1
            elif isinstance(d.get("i"), int) and "sec" in d:
                done["n"] += 1
            else:
                return
            ctx.progress(min(done["n"] / max(len(chunks), 1), 1.0), f"{done['n']}/{len(chunks)}")

        rc = ctx.run_process(self.command(job_file), cwd=str(work), on_line=on_line)
        self.timing["total_s"] = round(time.monotonic() - t0, 1)
        self.timing["chunks"] = done["n"]
        ctx.log("voice part: %s" % json.dumps(self.timing))
        res: dict[str, dict] = {}
        for i, c in enumerate(chunks):
            src = out_dir / f"chunk_{i:05d}.wav"
            sec = wav_seconds(src)
            if sec is None:
                why = errors.get(i) or ("the voice worker stopped (exit code %s)" % rc if rc else "the voice worker wrote no audio")
                res[c.id] = {"ok": False, "error": why}
                continue
            os.replace(src, dest_dir / f"{c.id}.wav")
            res[c.id] = {"ok": True, "sec": sec}
        if not any(r["ok"] for r in res.values()) and rc and not ctx.cancelled():
            raise VoiceError("voice_worker_failed", "the voice worker failed (exit code %s)" % rc)
        return res
