"""Mac-side planning/QA: forced word alignment (faster-whisper small.en, CPU int8, model cache inside workspace) of the raw TTS wav,
then builds timing.json (final-time beat/word times), subtitles.srt, subs.ass and the alignment table.

Run with ./venv_align/bin/python scripts/make_timing.py [atempo]
"""
import json, os, re, sys, difflib, wave, struct
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["HF_HOME"] = os.path.join(HERE, "hf_cache")
sys.path.insert(0, os.path.join(HERE, "scripts"))
from beats_src import BEATS

RAW = os.path.join(HERE, "voice", "voice_raw.wav")
RAWJ = os.path.join(HERE, "voice", "voice_raw_words.json")
GAP_IN, GAP_SEC, TITLE_LEN, TITLE_LEAD, TITLE_TAIL, TAIL = 0.28, 0.50, 2.6, 0.40, 0.15, 1.4
SECTION = {b[0]: b[1].split()[0] for b in BEATS}


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))


def whisper_words():
    cache = os.path.join(HERE, "voice", "whisper_words.json")
    if os.path.exists(cache):
        return json.load(open(cache))
    from faster_whisper import WhisperModel
    m = WhisperModel("small.en", device="cpu", compute_type="int8", download_root=os.path.join(HERE, "hf_cache"), cpu_threads=4)
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", RAW, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    audio = np.frombuffer(raw, np.float32)
    segs, info = m.transcribe(audio, language="en", word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    out = [{"w": w.word.strip(), "s": w.start, "e": w.end} for s in segs for w in s.words]
    json.dump(out, open(cache, "w"), indent=1)
    return out


def main():
    raw = json.load(open(RAWJ))
    est = raw["word_timestamps"]                    # chunk-even estimates; chunk first/last words are exact beat bounds
    ww = whisper_words()
    # --- map script words -> whisper words by sequence alignment
    script = []
    for bi, (bid, sec, text, *_r) in enumerate(BEATS):
        for w in text.split():
            script.append({"beat": bid, "w": w, "n": norm(w)})
    assert len(script) == len(est), (len(script), len(est))
    a = [x["n"] for x in script]
    b = [norm(x["w"]) for x in ww]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    amap = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                amap[i1 + k] = j1 + k
        elif tag == "replace" and (i2 - i1) == (j2 - j1):
            for k in range(i2 - i1):
                amap[i1 + k] = j1 + k
    matched = len(amap)
    for i, x in enumerate(script):
        if i in amap:
            x["s"], x["e"] = ww[amap[i]]["s"], ww[amap[i]]["e"]; x["src"] = "whisper"
        else:
            x["src"] = "interp"
    # interpolate unmatched between neighbours
    idx = [i for i, x in enumerate(script) if x["src"] == "whisper"]
    for i, x in enumerate(script):
        if x["src"] == "interp":
            lo = max([j for j in idx if j < i], default=None)
            hi = min([j for j in idx if j > i], default=None)
            lo_t = script[lo]["e"] if lo is not None else 0
            hi_t = script[hi]["s"] if hi is not None else lo_t + .3
            n_gap = (hi if hi is not None else i + 1) - (lo if lo is not None else -1) - 1
            k = i - (lo if lo is not None else -1) - 1
            x["s"] = lo_t + (hi_t - lo_t) * k / n_gap
            x["e"] = lo_t + (hi_t - lo_t) * (k + 1) / n_gap
    for x, e in zip(script, est):
        x["est_s"] = e["start"]
    # --- raw beat bounds (exact chunk bounds)
    beats_raw = {}
    pos = 0
    for bid, sec, text, *_r in BEATS:
        n = len(text.split())
        beats_raw[bid] = (est[pos]["start"], est[pos + n - 1]["end"])
        pos += n
    raw_total = sum(e - s for s, e in beats_raw.values())
    nwords = len(script)
    # --- choose atempo so that measured speech rate (first word -> last word incl. pauses, title card gap included) is 140 wpm
    def layout(at):
        t = 0.35; out = {}; prev = None
        for bid, sec, text, *_r in BEATS:
            if prev is not None:
                if prev == "B1b":
                    t += TITLE_LEAD + TITLE_LEN + TITLE_TAIL
                elif SECTION[prev] != SECTION[bid]:
                    t += GAP_SEC
                else:
                    t += GAP_IN
            s, e = beats_raw[bid]
            out[bid] = (t, t + (e - s) / at, s)
            t += (e - s) / at
            prev = bid
        return out, t
    target = 140.0
    at = float(sys.argv[1]) if len(sys.argv) > 1 else None
    if at is None:
        best = None
        for cand in np.arange(1.00, 1.2001, 0.005):
            lay_, _ = layout(cand)
            wpm = nwords / ((lay_['B5b'][1] - lay_['B1a'][0]) / 60)
            if best is None or abs(wpm - target) < abs(best[1] - target):
                best = (cand, wpm)
        at = round(float(best[0]), 3)
    lay, span = layout(at)
    wpm = nwords / ((lay['B5b'][1] - lay['B1a'][0]) / 60)
    wpm_speech_only = nwords / (sum(e - s for s, e in beats_raw.values()) / at / 60)
    timing = {"beats": {}, "atempo": at, "wpm_first_to_last_incl_pauses": round(wpm, 1), "wpm_speech_only": round(wpm_speech_only, 1),
              "raw_speech_s": round(raw_total, 2), "span_s": round(lay["B5b"][1] - lay["B1a"][0], 2)}
    for bid, (fs, fe, rs) in lay.items():
        ws = [{"w": x["w"], "s": round(fs + (x["s"] - rs) / at, 3), "e": round(fs + (x["e"] - rs) / at, 3), "src": x["src"],
               "est": round(fs + (x["est_s"] - rs) / at, 3)} for x in script if x["beat"] == bid]
        timing["beats"][bid] = {"start": round(fs, 3), "end": round(fe, 3), "raw_start": round(rs, 3), "raw_end": round(beats_raw[bid][1], 3), "words": ws}
    e_b1b = timing["beats"]["B1b"]["end"]
    timing["title"] = [round(e_b1b + TITLE_LEAD, 3), round(e_b1b + TITLE_LEAD + TITLE_LEN, 3)]
    timing["end"] = round(span + TAIL, 3)
    timing["gaps"] = {"in_section": GAP_IN, "between_sections": GAP_SEC, "title_gap": TITLE_LEAD + TITLE_LEN + TITLE_TAIL}
    timing["alignment"] = {"tool": "faster-whisper small.en int8 CPU", "words_matched": matched, "words_total": nwords}
    json.dump(timing, open(os.path.join(HERE, "timing.json"), "w"), indent=1)
    # raw segment spec for the server audio assembly
    json.dump({"atempo": at, "segments": [{"id": b, "raw_start": timing["beats"][b]["raw_start"], "raw_end": timing["beats"][b]["raw_end"],
                                           "final_start": timing["beats"][b]["start"]} for b in timing["beats"]], "end": timing["end"]},
              open(os.path.join(HERE, "server", "audio_spec.json"), "w"), indent=1)
    print("atempo", at, "wpm(incl pauses)", round(wpm, 1), "wpm(speech only)", round(wpm_speech_only, 1), "total", timing["end"], "matched", matched, "/", nwords)

    # --- alignment table: whisper vs chunk-even estimate
    diffs = [abs(x["s"] - x["est_s"]) / at for x in script if x["src"] == "whisper"]
    with open(os.path.join(HERE, "alignment_table.md"), "w") as f:
        f.write("# Forced alignment (faster-whisper small.en) vs Chatterbox chunk-even estimates\n\n")
        f.write("Words matched to ASR: %d/%d. |whisper start - even-spread estimate| in final time: median %.2fs, p90 %.2fs, max %.2fs.\n\n" % (
            matched, nwords, np.median(diffs), np.percentile(diffs, 90), max(diffs)))
        f.write("| beat | word | whisper start (final t) | even estimate | diff (s) |\n|---|---|---|---|---|\n")
        for bid in timing["beats"]:
            for w in timing["beats"][bid]["words"]:
                if w["src"] == "whisper" and abs(w["s"] - w["est"]) > .25:
                    f.write("| %s | %s | %.2f | %.2f | %+.2f |\n" % (bid, w["w"], w["s"], w["est"], w["s"] - w["est"]))
    write_subs(timing)


def fmt_srt(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return "%02d:%02d:%06.3f" % (h, m, s).replace(".", ",") if False else "%02d:%02d:%02d,%03d" % (h, m, int(s), int(round((s - int(s)) * 1000)) % 1000)


def fmt_ass(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return "%d:%02d:%05.2f" % (h, m, s)


def cues(timing):
    out = []
    for bid, b in timing["beats"].items():
        words = b["words"]
        text = " ".join(w["w"] for w in words)
        if len(text) <= 44:
            groups = [(0, len(words))]
        else:
            # split into cues of <= ~2 lines of <= 36 chars each, breaking after commas where possible
            groups = []; i = 0
            while i < len(words):
                j = i; ln = 0
                while j < len(words) and ln + len(words[j]["w"]) + 1 <= 70:
                    ln += len(words[j]["w"]) + 1; j += 1
                if j < len(words) and j - i > 3:
                    # prefer a comma break in the last third
                    for k in range(j, i + (j - i) // 2, -1):
                        if words[k - 1]["w"].endswith(","):
                            j = k; break
                groups.append((i, j)); i = j
            # avoid orphan tails
            if len(groups) > 1 and groups[-1][1] - groups[-1][0] < 3:
                a, b2 = groups[-2]; c, d = groups[-1]; groups[-2:] = [(a, d)]
        for gi, (i, j) in enumerate(groups):
            t = " ".join(w["w"] for w in words[i:j])
            start = words[i]["s"] if gi else b["start"]
            end = words[j - 1]["e"] if gi < len(groups) - 1 else b["end"]
            # wrap to two balanced lines when long
            if len(t) > 36:
                tw = t.split(); best = None
                for k in range(1, len(tw)):
                    l1, l2 = " ".join(tw[:k]), " ".join(tw[k:])
                    sc = abs(len(l1) - len(l2))
                    if best is None or sc < best[0]:
                        best = (sc, l1, l2)
                t = best[1] + "\\N" + best[2]
            out.append((max(0, start - .05), end + .12, t))
    for i in range(len(out) - 1):
        if out[i][1] > out[i + 1][0] - .02:
            out[i] = (out[i][0], out[i + 1][0] - .02, out[i][2])
    return out


def write_subs(timing):
    cs = cues(timing)
    with open(os.path.join(HERE, "subtitles.srt"), "w") as f:
        for i, (s, e, t) in enumerate(cs, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (i, fmt_srt(s), fmt_srt(e), t.replace("\\N", "\n")))
    ass = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
           "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
           "Style: Default,Century Gothic,46,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0.5,0,1,3,1.5,2,200,200,44,1\n\n"
           "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    for s, e, t in cs:
        ass += "Dialogue: 0,%s,%s,Default,,0,0,0,,%s\n" % (fmt_ass(s), fmt_ass(e), t)
    open(os.path.join(HERE, "server", "subs.ass"), "w").write(ass)


if __name__ == "__main__":
    main()
