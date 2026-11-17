"""Real voice and real aligner: run ONLY on the Windows server, under the heavy slot (see the contract, sections 4 and 10).
Two short sentences, well under two minutes of compute.

    tools/deploy/remote_test.sh tests/voice -m server
"""
import json
import os
import sys

import pytest

from bti.longjob import manager as _m  # noqa: F401
from bti.longjob.manager import LongJobManager
from bti.voice import files, run as voice_run
from bti.voice.config import aligner_config, load_server_config, voice_worker
from conftest import write_project

pytestmark = pytest.mark.server

TWO = {"c1": [("b0001", "In 1434, Jan van Eyck painted a small portrait."), ("b0002", "A mirror hangs behind the couple.")]}


def test_two_real_sentences_spoken_aligned_and_mixed(tmp_path):
    server = load_server_config()
    if voice_worker(server) is None:
        pytest.skip("no voice worker configured on this machine")
    d = write_project(tmp_path, "vserver", texts=TWO)
    mgr = LongJobManager()
    mgr.configure(projects_root=tmp_path)
    force = "whisper" if aligner_config(server) else "even"
    job = voice_run.start(d, "vserver", server=server, provider_name="chatterbox", aligner_force=force, manager=mgr)
    rec = mgr.wait(job, 15 * 60)
    assert rec["state"] == "done", rec
    mix, timing = files.mix_path(d), files.timing_path(d)
    assert mix.is_file() and timing.is_file() and files.dry_path(d).is_file()
    t = json.loads(timing.read_text(encoding="utf-8"))
    words = [w["w"] for w in t["words"]]
    assert words == "In 1434, Jan van Eyck painted a small portrait. A mirror hangs behind the couple.".split()
    assert all(a["s"] <= b["s"] for a, b in zip(t["words"], t["words"][1:]))
    assert t["duration"] > t["words"][-1]["e"]
    m = files.read_manifest(d)
    from bti.voice.providers.chatterbox import wav_seconds
    speech = sum(wav_seconds(p) or 0 for p in files.chunks_dir(d).glob("*.wav"))
    pm = {p["key"]: (p["ended"] or 0) - (p["started"] or 0) for p in rec["parts"]}
    print("METRICS speech_s=%.2f synth_compute_s=%.1f ratio=%.2f align_s=%.1f match=%s sizes mix=%d voice=%d timing=%d" % (
        speech, pm.get("synth-1", 0), pm.get("synth-1", 0) / max(speech, 0.01), pm.get("align", 0),
        (m.get("timing") or {}).get("match_rate"), files.mix_path(d).stat().st_size, files.dry_path(d).stat().st_size, timing.stat().st_size))
    assert m["timing_quality"] == ("aligned" if force == "whisper" else "even")
    if force == "whisper":
        assert m["timing"]["match_rate"] > 0.6
    assert -17.5 < m["loudness"]["i"] < -12.5 and m["loudness"]["tp"] <= -0.5
    import subprocess
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,sample_rate,channels", "-of", "json", str(mix)], capture_output=True, text=True)
    s = json.loads(pr.stdout)["streams"][0]
    assert (s["codec_name"], int(s["sample_rate"]), s["channels"]) == ("aac", 48000, 2)
