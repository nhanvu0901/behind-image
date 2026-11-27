"""Measure and build a voice-relative music mix without changing picture streams."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def mix_command(ffmpeg, voice, cues, out, duration):
    """Return a cancellable worker command; its plan is stored alongside the output."""
    if not cues:
        raise ValueError("a music mix needs at least one cue")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".music-plan.json",
                                     prefix="mix-", dir=Path(out).parent, delete=False) as f:
        json.dump({"ffmpeg": list(ffmpeg), "voice": str(voice), "cues": [[str(p), c] for p, c in cues],
                   "out": str(out), "duration": duration}, f)
        plan = f.name
    return [sys.executable, str(Path(__file__).resolve()), plan]


def _run(cmd):
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    return result.stderr


def _measure(ffmpeg, path, start=None, length=None, *, speech=None, temp_dir=None):
    cmd = [*ffmpeg, "-hide_banner", "-nostdin"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", path]
    if length is not None:
        cmd += ["-t", str(length)]
    if speech:
        select = "+".join("between(t,%.6f,%.6f)" % (a, b) for a, b in speech if b > a)
        if not select:
            raise ValueError("no speech intervals to measure")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=temp_dir,
                                         prefix="speech-", suffix=".filter", delete=False) as f:
            f.write("aselect='" + select + "',asetpts=N/SR/TB,ebur128=peak=true")
            script = Path(f.name)
        try:
            text = _run([*cmd, "-filter_complex_script", str(script), "-f", "null", "-"])
        finally:
            script.unlink(missing_ok=True)
    else:
        text = _run([*cmd, "-filter_complex", "ebur128=peak=true", "-f", "null", "-"])
    loud = re.findall(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS", text)
    peaks = re.findall(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", text)
    if not loud or not peaks or float(loud[-1]) <= -70:
        raise ValueError("cannot measure audible audio: " + str(path))
    return float(loud[-1]), float(peaks[-1])


def _envelope(cue):
    """A one-second raised plateau in a 1.2s pause; smooth both edges."""
    windows = [(max(cue["start"], x["start"]), min(cue["end"], x["end"]))
               for x in cue.get("pauses", []) if cue["role"] == "bed" and x["end"] - x["start"] >= 1.2]
    if cue["role"] == "ending" and cue.get("voice_end") is not None:
        windows.append((max(cue["start"], cue["voice_end"]), cue["end"]))
    terms = []
    for start, end in windows:
        if end <= start:
            continue
        start -= cue["start"]
        end -= cue["start"]
        terms.append("clip(min((t-%.4f)/0.1,(%.4f-t)/0.1),0,1)" % (start, end))
    return "+".join(terms) or "0"


def _build_filters(cues, levels, duration):
    filters = ["[0:a]aformat=channel_layouts=stereo,apad=whole_dur=%.6f,atrim=duration=%.6f[voice]" % (duration, duration)]
    tracks = []
    for i, ((_, cue), gain) in enumerate(zip(cues, levels), 1):
        length = cue["end"] - cue["start"]
        expr = "%.6f" % gain
        if cue["role"] in ("bed", "ending"):
            expr += "+6*(%s)" % _envelope(cue)
        track = ("[%d:a]atrim=start=%.6f:duration=%.6f,asetpts=PTS-STARTPTS,"
                 "volume='pow(10,(%s)/20)':eval=frame" % (i, cue["offset"], length, expr))
        if cue["fade_in"]:
            track += ",afade=t=in:st=0:d=%.6f" % cue["fade_in"]
        if cue["fade_out"]:
            track += ",afade=t=out:st=%.6f:d=%.6f" % (length-cue["fade_out"], cue["fade_out"])
        filters.append(track + ",adelay=%d:all=1[m%d]" % (round(cue["start"]*1000), i))
        tracks.append("[m%d]" % i)
    filters.append("[voice]" + "".join(tracks) + "amix=inputs=%d:duration=first:normalize=0[out]" % (len(tracks)+1))
    return ";".join(filters)


def _level_bed(ffmpeg, path, cue, out):
    """Slowly level only the selected bed excerpt, before pause automation."""
    _run([*ffmpeg, "-y", "-v", "error", "-nostdin", "-ss", str(cue["offset"]), "-i", str(path),
          "-t", str(cue["end"] - cue["start"]), "-af",
          "dynaudnorm=f=500:g=5:p=0.95:m=100:r=0.1:b=1", "-c:a", "pcm_f32le", str(out)])


def render(plan):
    ffmpeg, cues = plan["ffmpeg"], plan["cues"]
    voice_loudness, _ = _measure(ffmpeg, plan["voice"], speech=cues[0][1].get("speech"),
                                  temp_dir=Path(plan["out"]).parent)
    root = Path(plan["out"]).parent
    paths = []
    try:
        prepared = []
        levels = []
        for path, cue in cues:
            if cue["role"] == "bed":
                with tempfile.NamedTemporaryFile(dir=root, prefix="bed-", suffix=".wav", delete=False) as f:
                    bed_path = Path(f.name)
                paths.append(bed_path)
                _level_bed(ffmpeg, path, cue, bed_path)
                path, cue = str(bed_path), {**cue, "offset": 0}
            recording, _ = _measure(ffmpeg, path, cue["offset"], cue["end"]-cue["start"])
            role = {"bed": -20, "swell": -8, "ident": -8, "ending": -12}[cue["role"]]
            step = {"soft": -3, "normal": 0, "strong": 3}[cue["level"]]
            levels.append(voice_loudness + role + step - recording)
            prepared.append((path, cue))
        cues = prepared
        for suffix in (".wav", ".filter"):
            with tempfile.NamedTemporaryFile(dir=root, prefix="mix-", suffix=suffix, delete=False) as f:
                paths.append(Path(f.name))
        audio, script = paths[-2:]
        script.write_text(_build_filters(cues, levels, plan["duration"]), encoding="utf-8")
        cmd = [*ffmpeg, "-y", "-v", "error", "-nostdin", "-i", plan["voice"]]
        for path, _ in cues:
            cmd += ["-i", path]
        _run([*cmd, "-filter_complex_script", str(script), "-map", "[out]", "-c:a", "pcm_f32le", "-ar", "48000", str(audio)])
        loud, peak = _measure(ffmpeg, str(audio))
        gain = -14 - loud
        limit = 0.84
        for _ in range(4):
            _run([*ffmpeg, "-y", "-v", "error", "-nostdin", "-i", str(audio), "-af", ("volume=%.5fdB,aresample=192000,alimiter=limit=%.6f:attack=1:release=40:level=0:latency=1,aresample=48000" % (gain, limit)),
                  "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", str(plan["duration"]), plan["out"]])
            final_loudness, final_peak = _measure(ffmpeg, plan["out"])
            if final_peak <= -1 and abs(final_loudness + 14) <= 0.5:
                break
            if final_peak > -1:
                limit *= 10 ** ((-1.3 - final_peak) / 20)
            gain += -14 - final_loudness
        else:
            raise ValueError("cannot reach programme loudness and encoded true-peak targets")
        print("voice %.1f LUFS; mix %.1f LUFS, %.1f dBTP; final gain %.2f dB; encoded %.1f LUFS, %.1f dBTP" %
              (voice_loudness, loud, peak, gain, final_loudness, final_peak))
        return {"voice": voice_loudness, "mix": loud, "mix_peak": peak, "gain": gain,
                "limit": limit, "output": final_loudness, "output_peak": final_peak}
    finally:
        for path in paths:
            path.unlink(missing_ok=True)


def main():
    path = Path(sys.argv[1])
    try:
        render(json.loads(path.read_text(encoding="utf-8")))
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
