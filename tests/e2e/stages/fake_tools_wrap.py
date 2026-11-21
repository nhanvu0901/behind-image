"""Fake engine, ffmpeg and ffprobe for the export in the stages e2e run. Wraps tests/export/fake_tools.py, but tolerates the REAL
audio mix made by the voice step: ffprobe on a file that is not a fake JSON document is handed to the real ffprobe, and the fake
mux treats a real audio file as AAC. Usage: python fake_tools_wrap.py engine|ffmpeg|ffprobe <args>."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("BTI_REPO") or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(REPO / "tests" / "export"))
import fake_tools  # noqa: E402

_load = fake_tools.load


def tolerant_load(path):
    try:
        return _load(path)
    except (ValueError, UnicodeDecodeError):
        return {"kind": "audio", "codec": "aac", "duration": 600.0}


fake_tools.load = tolerant_load


def real_probe_needed(path):
    try:
        with open(path, "rb") as f:
            return f.read(1) != b"{"
    except OSError:
        return False


if __name__ == "__main__":
    prog, argv = sys.argv[1], sys.argv[2:]
    if prog == "engine":
        import time
        time.sleep(float(os.environ.get("FAKE_ENGINE_DELAY", "0")))      # a slow render, so that progress and cancel can be tried
    if prog == "ffprobe" and real_probe_needed(argv[-1]):
        sys.exit(subprocess.call(["ffprobe"] + argv))
    sys.exit({"engine": fake_tools.engine, "ffmpeg": fake_tools.ffmpeg, "ffprobe": fake_tools.ffprobe}[prog](argv))
