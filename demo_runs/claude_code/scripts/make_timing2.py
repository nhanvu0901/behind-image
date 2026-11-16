"""Mac-side planning/QA: builds timing2.json (final-time beats, words, cards), audio_spec2.json, subtitles.srt.
python make_timing2.py [--fake] [atempo]   (venv_align python for real alignment)"""
import json, os, re, sys, difflib, wave
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["HF_HOME"] = os.path.join(HERE, "hf_cache")
V = os.path.join(HERE, "v2", "voice")
FAKE = "--fake" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
B = json.load(open(os.path.join(HERE, "v2", "server", "beats_v2.json")))
CARDS = {"THE MERCHANT CITY", "THE ARNOLFINIS", "FASHIONS AND FABRICS", "THE ROOM", "THE MIRROR", "THE ALCHEMIST"}
norm = lambda w: re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))


def whisper_words(g):
    cache = os.path.join(V, f"whisper_J{g}.json")
    if os.path.exists(cache): return json.load(open(cache))
    from faster_whisper import WhisperModel
    import subprocess
    m = WhisperModel("small.en", device="cpu", compute_type="int8", download_root=os.path.join(HERE, "hf_cache"), cpu_threads=4)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(V, f"voice_J{g}.wav"), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    segs, _ = m.transcribe(np.frombuffer(raw, np.float32), language="en", word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    out = [{"w": w.word.strip(), "s": w.start, "e": w.end} for s in segs for w in s.words]
    json.dump(out, open(cache, "w")); return out


beats = []   # global list
stats = {"matched": 0, "total": 0}
for g in ("1", "2", "3"):
    d = B[g]
    if FAKE:
        # even estimate: 144 wpm raw
        t = 0.0; est = []
        for b in d["beats"]:
            ws = b.split(); du = len(ws) / 144 * 60
            est += [{"word": w, "start": t + du * i / len(ws), "end": t + du * (i + 1) / len(ws)} for i, w in enumerate(ws)]; t += du
        wj = {"word_timestamps": est}
    else:
        wj = json.load(open(os.path.join(V, f"voice_J{g}_words.json")))
    est = wj["word_timestamps"]
    script = []
    for bi, b in enumerate(d["beats"]):
        for w in b.split(): script.append({"bi": bi, "w": w, "n": norm(w)})
    assert len(script) == len(est), (g, len(script), len(est))
    if FAKE:
        for x, e in zip(script, est): x.update(s=e["start"], e=e["end"], src="est")
    else:
        ww = whisper_words(g)
        a = [x["n"] for x in script]; b_ = [norm(x["w"]) for x in ww]
        sm = difflib.SequenceMatcher(None, a, b_, autojunk=False); amap = {}
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
                for k in range(i2 - i1): amap[i1 + k] = j1 + k
        for i, x in enumerate(script):
            if i in amap: x.update(s=ww[amap[i]]["s"], e=ww[amap[i]]["e"], src="whisper")
            else: x["src"] = "interp"
        idx = [i for i, x in enumerate(script) if x["src"] == "whisper"]
        for i, x in enumerate(script):
            if x["src"] == "interp":
                lo = max([j for j in idx if j < i], default=None); hi = min([j for j in idx if j > i], default=None)
                lo_t = script[lo]["e"] if lo is not None else 0; hi_t = script[hi]["s"] if hi is not None else lo_t + .3
                n_gap = (hi if hi is not None else i + 1) - (lo if lo is not None else -1) - 1; k = i - (lo if lo is not None else -1) - 1
                x["s"] = lo_t + (hi_t - lo_t) * k / n_gap; x["e"] = lo_t + (hi_t - lo_t) * (k + 1) / n_gap
        stats["matched"] += len(amap)
    stats["total"] += len(script)
    pos = 0
    for bi, b in enumerate(d["beats"]):
        n = len(b.split())
        beats.append({"group": g, "chapter": d["beat_chapter"][bi], "text": b, "raw_start": est[pos]["start"], "raw_end": est[pos + n - 1]["end"],
                      "words": [{"w": x["w"], "s": x["s"], "e": x["e"], "src": x["src"], "est": est[pos + k]["start"]} for k, x in enumerate(script[pos:pos + n])]})
        pos += n

GAP_IN, GAP_CH, CARD_T, TITLE_T, LEAD, TAIL = 0.65, 0.8, 2.0, 2.6, 0.35, 3.2


def layout(at):
    t = LEAD; out = []; cards = []; prev = None
    for b in beats:
        if prev is not None:
            if b["chapter"] != prev["chapter"]:
                if prev["chapter"] == "COLD_OPEN":
                    t += 0.4; cards.append({"text": "__title__", "t0": t, "t1": t + TITLE_T}); t += TITLE_T + 0.3
                if b["chapter"] in CARDS:
                    if prev["chapter"] != "COLD_OPEN": t += GAP_CH
                    cards.append({"text": b["chapter"], "t0": t, "t1": t + CARD_T}); t += CARD_T + GAP_CH
                else:
                    t += 0.8
            else:
                t += GAP_IN
        du = (b["raw_end"] - b["raw_start"]) / at
        out.append((t, t + du)); t += du; prev = b
    return out, cards, t


nwords = stats["total"]
at = float(args[0]) if args else None
if at is None:
    best = None
    for cand in np.arange(1.00, 1.2001, 0.005):
        lay, _, _ = layout(cand); wpm = nwords / ((lay[-1][1] - lay[0][0]) / 60)
        if best is None or abs(wpm - 140) < abs(best[1] - 140): best = (cand, wpm)
    at = round(float(best[0]), 3)
lay, cards, tend = layout(at)
span = lay[-1][1] - lay[0][0]; wpm = nwords / (span / 60)
raw_total = sum(b["raw_end"] - b["raw_start"] for b in beats)
timing = {"atempo": at, "wpm_first_to_last_incl_pauses_and_cards": round(wpm, 1), "wpm_speech_only": round(nwords / (raw_total / at / 60), 1), "span_s": round(span, 2), "words": nwords,
          "alignment": {"tool": "faster-whisper small.en int8 CPU", "matched": stats["matched"], "total": nwords, "fake": FAKE}, "cards": [{k: round(v, 3) if isinstance(v, float) else v for k, v in c.items()} for c in cards], "beats": []}
for b, (fs, fe) in zip(beats, lay):
    rs = b["raw_start"]
    timing["beats"].append({"group": b["group"], "chapter": b["chapter"], "text": b["text"], "start": round(fs, 3), "end": round(fe, 3), "raw_start": round(rs, 3), "raw_end": round(b["raw_end"], 3),
                            "words": [{"w": w["w"], "s": round(fs + (w["s"] - rs) / at, 3), "e": round(fs + (w["e"] - rs) / at, 3), "src": w["src"], "est": round(fs + (w["est"] - rs) / at, 3)} for w in b["words"]]})
timing["end"] = round(lay[-1][1] + TAIL, 3)
# frame-align end
timing["end"] = round(int(timing["end"] * 30) / 30, 4)
out = os.path.join(HERE, "v2", "timing2_fake.json" if FAKE else "timing2.json")
json.dump(timing, open(out, "w"), indent=1)
if not FAKE:
    json.dump({"atempo": at, "end": timing["end"], "segments": [{"wav": f"voice_J{b['group']}.wav", "raw_start": b["raw_start"], "raw_end": b["raw_end"], "final_start": tb["start"]} for b, tb in zip(beats, timing["beats"])]},
              open(os.path.join(HERE, "v2", "server", "audio_spec2.json"), "w"))
print(out, "atempo", at, "wpm", round(wpm, 1), "speech-only", timing["wpm_speech_only"], "end", timing["end"], "=", round(timing["end"] / 60, 2), "min; matched", stats["matched"], "/", nwords)

# ---- subtitles.srt (sidecar only)
def srt_t(t):
    return "%02d:%02d:%02d,%03d" % (int(t // 3600), int(t % 3600 // 60), int(t % 60), int(round((t - int(t)) * 1000)) % 1000)
cues = []
for b in timing["beats"]:
    ws = b["words"]; text = " ".join(w["w"] for w in ws)
    groups = []; i = 0
    while i < len(ws):
        j = i; ln = 0
        while j < len(ws) and ln + len(ws[j]["w"]) + 1 <= 84: ln += len(ws[j]["w"]) + 1; j += 1
        if j < len(ws) and j - i > 4:
            for k in range(j, i + (j - i) // 2, -1):
                if ws[k - 1]["w"].endswith(","): j = k; break
        groups.append((i, j)); i = j
    if len(groups) > 1 and groups[-1][1] - groups[-1][0] < 4: groups[-2:] = [(groups[-2][0], groups[-1][1])]
    for gi, (i, j) in enumerate(groups):
        t = " ".join(w["w"] for w in ws[i:j])
        if len(t) > 42:
            tw = t.split(); best = min(((abs(len(" ".join(tw[:k])) - len(" ".join(tw[k:]))), k) for k in range(1, len(tw))))[1]
            t = " ".join(tw[:best]) + "\n" + " ".join(tw[best:])
        cues.append([ws[i]["s"] if gi else b["start"], ws[j - 1]["e"] if gi < len(groups) - 1 else b["end"], t])
for i in range(len(cues) - 1):
    if cues[i][1] > cues[i + 1][0] - .02: cues[i][1] = cues[i + 1][0] - .02
if not FAKE:
    with open(os.path.join(HERE, "subtitles.srt"), "w") as f:
        for i, (s, e, t) in enumerate(cues, 1): f.write("%d\n%s --> %s\n%s\n\n" % (i, srt_t(max(0, s - .05)), srt_t(e + .1), t))
    print("subtitles.srt", len(cues), "cues")
