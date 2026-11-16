"""contact_sheet_NN.jpg (every 10 s, 40 tiles/page, timestamps burned in) and reference_compare.jpg (>=10 pairs)."""
import sys, subprocess, os, json, re, cv2, numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = sys.argv[1]; REF = "/Users/nhanvu/Documents/code/behind-the-image/research_media/great-art-explained/T15Kv6dtYO0.mp4"
tmp = "/private/tmp/claude-501/-Users-nhanvu-Documents-code-behind-the-image/d1d99b63-899d-4011-a440-2cba5b3bca9e/scratchpad/qa2"; os.makedirs(tmp, exist_ok=True)
def frame(path, t, w, h):
    out = f"{tmp}/f.png"; subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1", "-vf", f"scale={w}:{h}", out]); return cv2.imread(out)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", V], capture_output=True, text=True).stdout)
# all frames for contact sheets in one ffmpeg pass
ts = list(np.arange(5.0, dur, 10.0)); w, h = 384, 216; cols = 8
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", V, "-vf", "fps=1/10,scale=%d:%d" % (w, h), f"{tmp}/c_%04d.png"])
n = len(ts); page = 40
for p in range(0, n, page):
    chunk = ts[p:p + page]; rows = (len(chunk) + cols - 1) // cols; sh = np.zeros((rows * h, cols * w, 3), np.uint8)
    for i, t in enumerate(chunk):
        im = cv2.imread(f"{tmp}/c_{p + i + 1:04d}.png")
        if im is None: continue
        cv2.putText(im, "%d:%02d" % (t // 60, t % 60), (6, 22), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 255), 2, cv2.LINE_AA)
        sh[(i // cols) * h:(i // cols + 1) * h, (i % cols) * w:(i % cols + 1) * w] = im
    cv2.imwrite(os.path.join(HERE, "contact_sheet_%02d.jpg" % (p // page + 1)), sh, [cv2.IMWRITE_JPEG_QUALITY, 88])
shots = json.load(open(os.path.join(HERE, "v2", "shots_final.json")))
TJ = json.load(open(os.path.join(HERE, "v2", "timing2.json"))); WD = [(re.sub(r"[^a-z0-9]", "", w["w"].lower()), w["s"]) for b in TJ["beats"] for w in b["words"]]
def at(phrase):
    p_ = [re.sub(r"[^a-z0-9]", "", x.lower()) for x in phrase.split()]
    for i in range(len(WD) - len(p_) + 1):
        if all(WD[i + k][0] == p_[k] for k in range(len(p_))): return WD[i][1]
    raise KeyError(phrase)
def find(sub, nth=0, off=1.0):
    hit = [s for s in shots if sub in s["effect"]][nth]; return hit["t0"] + off
pairs = [("cold-open couple detail", 4.0, 22.0), ("full painting on matte after pull-back", find("opening pull-back", off=14), 31.0), ("dimension annotation (AN-05)", find("dimension annotation", off=2.5), 177.0),
         ("chapter card", find("chapter card", 1, off=.9), 180.5), ("title card vs chapter card", find("title card", off=1.5), 180.5), ("detail label strip (single line)", at("that green dress") + 1.2, 329.5),
         ("dress pan", find("long pan down the dress", off=4), 340.0), ("mirror push", at("The mirror pulls the whole room together") + 6.0, 596.0), ("circles", at("one candle is lit") + 1.4, 664.0),
         ("two-line label on another work", find("Bruges still", off=2.0), 182.0), ("recap labels", at("the dark clothes") + 1.0, 862.0), ("closing pull-out", find("closing", off=36), 906.0), ("hands detail", find("joined hands", off=3), 872.0)]
W2, H2 = 800, 450
sh = np.zeros((len(pairs) * (H2 + 30), 2 * W2, 3), np.uint8)
for i, (name, tm, tr) in enumerate(pairs):
    a = frame(V, tm, W2, H2); r = frame(REF, tr, W2, H2)
    for im, txt in ((a, "MINE %d:%04.1f" % (tm // 60, tm % 60)), (r, "REFERENCE %d:%04.1f" % (tr // 60, tr % 60))): cv2.putText(im, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, .9, (0, 255, 255), 2, cv2.LINE_AA)
    y = i * (H2 + 30); sh[y + 30:y + 30 + H2, :W2] = a; sh[y + 30:y + 30 + H2, W2:] = r
    cv2.putText(sh, name, (10, y + 22), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2, cv2.LINE_AA)
cv2.imwrite(os.path.join(HERE, "reference_compare.jpg"), sh, [cv2.IMWRITE_JPEG_QUALITY, 86])
print("sheets:", (n + page - 1) // page, "pages;", len(pairs), "pairs")
