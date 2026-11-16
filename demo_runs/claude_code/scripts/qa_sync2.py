"""Measure highlight/label onsets in the rendered final_demo.mp4 vs the aligned word start times.
usage: qa_sync2.py final_demo.mp4 v2/timing2.json"""
import sys, json, subprocess, re, numpy as np
V, tj = sys.argv[1], sys.argv[2]
T = json.load(open(tj)); words = [(re.sub(r"[^a-z0-9]", "", w["w"].lower()), w["s"]) for b in T["beats"] for w in b["words"]]
def at(phrase, nth=0, wi=0):
    p = [re.sub(r"[^a-z0-9]", "", x.lower()) for x in phrase.split()]; k = 0
    for i in range(len(words) - len(p) + 1):
        if all(words[i + j][0] == p[j] for j in range(len(p))):
            if k == nth: return words[i + wi][1]
            k += 1
    raise KeyError(phrase)
W, H = 480, 270
def clip(t0, t1):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(max(0, t0)), "-t", str(t1 - t0), "-i", V, "-vf", f"fps=30,scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    n = len(raw) // (W * H * 3); return np.frombuffer(raw, np.uint8)[:n * W * H * 3].reshape(n, H, W, 3).astype(np.float32), max(0, t0)
def onset(sig, base_t, rising, frac=.10):
    b = np.median(sig[:6]); e = sig[-1] if rising else sig[-1]
    d = (sig - b) / (np.max(sig) - b + 1e-6) if rising else (sig - b) / (np.min(sig) - b + 1e-6)
    k = int(np.argmax(d > frac)); return base_t + k / 30
rows = []
def ev(name, word, t_exp, kind, win=(-.6, 1.4)):
    f, t0 = clip(t_exp + win[0], t_exp + win[1]); g = f.mean(-1)
    if kind == "dim":      # spotlight: global luminance falls
        sig = g.mean((1, 2)); o = onset(sig, t0, False)
    elif kind == "white":  # label / text / annotation: count of near-white pixels in lower strip or whole frame
        sig = (g > 225).sum((1, 2)).astype(np.float32); o = onset(sig, t0, True)
    elif kind in ("ring", "ring2"):   # light-grey ring pixels
        gr = (g > 165) & (g < 225) & (f.max(-1) - f.min(-1) < 22); sig = gr.sum((1, 2)).astype(np.float32); o = onset(sig, t0, True)
    rows.append((name, word, t_exp, o))
ev("Spotlight on the mirror (cold open)", "mirror", at("Notice the mirror", wi=2), "dim")
ev("Dimension annotation lines (AN-05)", "eighty-two", at("eighty-two"), "white")
ev("Label GREEN WOOL GOWN", "green", at("that green dress", wi=1), "white")
ev("Year caption 1433", "1433", at("dead by 1433", wi=2), "white")
ev("Spotlight on the mirror (mirror chapter)", "mirror", at("The mirror pulls the whole room together", wi=1), "dim")
ev("Two circles on the roundels", "roundels", at("Ten tiny roundels", wi=2), "ring")
ev("Circle on the lit candle", "candle", at("one candle is lit", wi=1), "ring")
ev("Circle on the snuffed-out candle", "snuffed", at("another has been snuffed out", wi=3), "ring2")
ev("Spotlight on the joined hands", "joined", at("Look at the joined hands", wi=3), "dim")
print("| highlight | word | expected onset (s) | measured onset in mp4 (s) | offset (s) | within +-0.25 |\n|---|---|---|---|---|---|")
ok = 0
for name, word, te, o in rows:
    off = o - te; g = abs(off) <= .25; ok += g
    print(f"| {name} | {word} | {te:.2f} | {o:.2f} | {off:+.2f} | {'yes' if g else 'NO'} |")
print(f"\n{ok}/{len(rows)} within +-0.25 s")
