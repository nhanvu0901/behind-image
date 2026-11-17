"""A fake engine, ffmpeg and ffprobe in one script: `python fake_tools.py engine|ffmpeg|ffprobe <their arguments>`.

Media files are small JSON documents (`{"kind": "video", "frames": 150, ...}`), so a whole export runs in milliseconds with no
codec, no GPU and no model. Behaviour switches (environment variables, set through `Tools.env`):
  FAKE_LOG        file that gets one JSON line per call (program, argv)
  FAKE_FAIL_T0    the engine call whose --t0 is this number exits with code 1
  FAKE_SHORT      the engine renders one frame fewer than asked
  FAKE_NO_LOUD    the loudness measurement prints no summary
"""
import json
import os
import re
import sys


def log(prog, argv):
    p = os.environ.get("FAKE_LOG")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"prog": prog, "argv": argv}) + "\n")


def arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)


def engine(argv):
    log("engine", argv)
    t0, t1, fps = float(arg(argv, "--t0")), float(arg(argv, "--t1")), int(arg(argv, "--fps", 30))
    f = os.environ.get("FAKE_FAIL_T0")
    if f is not None and abs(float(f) - t0) < 1e-6:
        print("error: a technique cannot draw", file=sys.stderr)
        return 1
    frames = round(t1 * fps) - round(t0 * fps) - (1 if os.environ.get("FAKE_SHORT") else 0)
    for p in range(5, 101, 5):
        print("progress %d%%" % p, flush=True)
    save(arg(argv, "-o"), {"kind": "video", "frames": frames, "fps": fps, "duration": frames / fps})
    return 0


def concat(argv):
    lst = arg(argv, "-i")
    frames = 0
    for line in open(lst, encoding="utf-8").read().splitlines():
        m = re.fullmatch(r"file '(.*)'", line)
        frames += load(m.group(1).replace("'\\''", "'"))["frames"]
    save(argv[-1], {"kind": "video", "frames": frames, "fps": 30, "duration": frames / 30})
    return 0


def mux(argv):
    ins = [argv[i + 1] for i, a in enumerate(argv) if a == "-i"]
    video, audio, srt, meta = ins
    v = load(video)
    a = load(audio)
    out = {"kind": "mux", "frames": v["frames"], "fps": v["fps"], "duration": float(arg(argv, "-t")) if "-t" in argv else v["duration"],
           "audio": {"codec": a.get("codec", "aac") if arg(argv, "-c:a") == "copy" else "aac"},
           "subtitle": {"codec": arg(argv, "-c:s")}, "cues": open(srt, encoding="utf-8").read().count("-->"),
           "chapters": [], "size_hint": 123456}
    text = open(meta, encoding="utf-8").read()
    for m in re.finditer(r"START=(\d+)\nEND=(\d+)\ntitle=(.*)", text):
        out["chapters"].append({"start": int(m.group(1)) / 1000, "end": int(m.group(2)) / 1000, "title": m.group(3)})
    save(argv[-1], out)
    return 0


def ffmpeg(argv):
    log("ffmpeg", argv)
    if "ebur128=peak=true" in argv:
        if not os.environ.get("FAKE_NO_LOUD"):
            print("[Parsed_ebur128_0 @ 0x1] Summary:\n\n  Integrated loudness:\n    I:         -15.1 LUFS\n    Threshold: -25.2 LUFS\n\n"
                  "  Loudness range:\n    LRA:         3.6 LU\n    Threshold: -35.2 LUFS\n    LRA low:   -17.5 LUFS\n    LRA high:  -13.9 LUFS\n\n"
                  "  True peak:\n    Peak:       -1.6 dBFS", file=sys.stderr)
        return 0
    if "concat" in argv:
        return concat(argv)
    return mux(argv)


def ffprobe(argv):
    doc = load(argv[-1])
    streams, chapters = [], []
    kind = doc.get("kind")
    if kind in ("video", "mux"):
        streams.append({"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "%d/1" % doc["fps"],
                        "nb_read_packets": str(doc["frames"]), "duration": str(doc["duration"])})
    if kind == "mux":
        streams.append({"codec_type": "audio", "codec_name": doc["audio"]["codec"], "sample_rate": "48000", "channels": 2, "duration": str(doc["duration"])})
        streams.append({"codec_type": "subtitle", "codec_name": doc["subtitle"]["codec"], "tags": {"language": "eng"}})
        chapters = [{"start_time": str(c["start"]), "end_time": str(c["end"]), "tags": {"title": c["title"]}} for c in doc["chapters"]]
    if kind == "audio":
        streams.append({"codec_type": "audio", "codec_name": doc.get("codec", "aac"), "sample_rate": "48000", "channels": 2, "duration": "10"})
    print(json.dumps({"format": {"duration": str(doc.get("duration", 10)), "size": str(doc.get("size_hint", 1000))}, "streams": streams, "chapters": chapters}))
    return 0


if __name__ == "__main__":
    sys.exit({"engine": engine, "ffmpeg": ffmpeg, "ffprobe": ffprobe}[sys.argv[1]](sys.argv[2:]))
