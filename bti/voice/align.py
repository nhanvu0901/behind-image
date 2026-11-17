"""Word times: from the sentence spans of the final audio, give every WRITTEN word a start and an end.

Two aligners behind one interface:

    aligner.heard(chunks, spans, wav, ctx, workdir) -> dict[index, list[{"w", "s", "e"}] | None]

`whisper` runs faster-whisper (in the aligner's own Python) sentence by sentence inside the known span; `even` hears nothing
(None), so the times are spread evenly inside each sentence. `merge_chunk` matches the script's SPOKEN words to the heard ones
(difflib), interpolates the words the recogniser missed, and `written_times` turns spoken-word times into times of the written
tokens (a written token such as "1434" is two spoken words; a pause dash shares the previous word)."""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from bti.textfold import squash

from .errors import VoiceError

_NONWORD = re.compile(r"\W+")


def norm(w: str) -> str:
    return squash(w)


def even_times(words: list[str], a: float, b: float) -> list[tuple[float, float]]:
    """Spread `words` over [a, b] in proportion to their length (at least one character each)."""
    if not words:
        return []
    weights = [max(len(norm(w)), 1) for w in words]
    total = float(sum(weights))
    out, t = [], a
    for wt in weights:
        d = (b - a) * wt / total
        out.append((t, t + d))
        t += d
    return out


def merge_words(spoken: list[str], heard: list[dict] | None, span: tuple[float, float]) -> tuple[list[tuple[float, float]], int]:
    """Times of the spoken words inside `span`. `heard` is the recogniser's [{w, s, e}] or None (spread evenly).
    Returns (times, number of spoken words that matched a heard word)."""
    a, b = span
    if not spoken:
        return [], 0
    if not heard:
        return even_times(spoken, a, b), 0
    sn = [norm(w) for w in spoken]
    hn = [norm(h["w"]) for h in heard]
    sm = difflib.SequenceMatcher(None, sn, hn, autojunk=False)
    amap: dict[int, int] = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                if sn[i1 + k] or hn[j1 + k]:
                    amap[i1 + k] = j1 + k
    times: list[tuple[float, float] | None] = [None] * len(spoken)
    for i, j in amap.items():
        s, e = float(heard[j]["s"]), float(heard[j]["e"])
        times[i] = (min(max(s, a), b), min(max(e, a), b))
    idx = sorted(amap)
    i = 0
    while i < len(spoken):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(spoken) and times[j] is None:
            j += 1
        lo = max([k for k in idx if k < i], default=None)
        hi = min([k for k in idx if k >= j], default=None)
        lo_t = times[lo][1] if lo is not None else a
        hi_t = times[hi][0] if hi is not None else b
        if hi_t < lo_t:
            hi_t = lo_t
        for k, (s, e) in zip(range(i, j), even_times(spoken[i:j], lo_t, hi_t)):
            times[k] = (s, e)
        i = j
    out: list[tuple[float, float]] = []
    prev = a
    for t in times:
        s, e = t  # type: ignore[misc]
        s = min(max(s, prev), b)         # monotonic and inside the span
        e = min(max(e, s), b)
        out.append((s, e))
        prev = s
    return out, len(amap)


def written_times(units, spoken_times: list[tuple[float, float]], a: float, b: float) -> list[dict]:
    """[{w, s, e}] for every written token of the sentence. A unit with spoken words takes the time from the first to the last
    of them and spreads its written tokens evenly over it; a unit that says nothing sits as a zero-length word at the previous end."""
    out: list[dict] = []
    k = 0
    last_end = a
    for u in units:
        n = len(u.spoken.split())
        if n:
            s, e = spoken_times[k][0], spoken_times[k + n - 1][1]
            k += n
        else:
            s = e = last_end
        for w, (ws, we) in zip(u.written, even_times(u.written, s, e) if e > s else [(s, s)] * len(u.written)):
            out.append({"w": w, "s": round(ws, 4), "e": round(we, 4)})
        last_end = max(last_end, e)
    return out


def build_words(chunks, spans: list[dict], heard: dict | None) -> tuple[list[dict], dict]:
    """All written words of the narration with times, plus {matched, total} counts of spoken words. `spans[i]` belongs to
    `chunks[i]`; `heard[i]` is what the aligner heard for it (or missing)."""
    words: list[dict] = []
    matched = total = 0
    ranges: list[tuple[int, int]] = []
    for c, sp in zip(chunks, spans):
        spoken = c.spoken.split()
        h = (heard or {}).get(c.index)
        times, m = merge_words(spoken, h, (sp["start"], sp["end"]))
        matched += m
        total += len(spoken)
        w0 = len(words)
        words.extend(written_times(c.units, times, sp["start"], sp["end"]))
        ranges.append((w0, len(words)))
    return words, {"matched": matched, "total": total, "ranges": ranges}


# ---------------------------------------------------------------- providers
class EvenAligner:
    name = "even"
    quality = "even"

    def heard(self, chunks, spans, wav, ctx=None, workdir=None) -> dict:
        return {}


class WhisperAligner:
    name = "whisper"
    quality = "aligned"

    def __init__(self, aligner_cfg: dict, voice_cfg: dict, language: str = "en"):
        self.a = aligner_cfg
        self.v = voice_cfg["aligner"]
        self.lang = (language or "en").split("-")[0].lower()

    def model_name(self) -> str:
        return (self.a.get("model") or self.v["model_en"]) if self.lang == "en" else self.v["model"]

    def heard(self, chunks, spans, wav, ctx, workdir) -> dict:
        work = Path(workdir) / "align"
        work.mkdir(parents=True, exist_ok=True)
        spans_file, out_file = work / "spans.json", work / "heard.json"
        if out_file.exists():
            out_file.unlink()
        spans_file.write_text(json.dumps([{"index": s["index"], "start": s["start"], "end": s["end"]} for s in spans]), encoding="utf-8")
        script = str(Path(__file__).with_name("align_worker.py"))
        cmd = [self.a["python"], "-B", script, str(wav), str(spans_file), str(out_file), self.model_name(), self.a.get("model_dir", ""), self.lang]
        seen = {"n": 0}

        def on_line(line: str) -> None:
            if (line or "").lstrip().startswith("{"):
                seen["n"] += 1
                ctx.progress(min(seen["n"] / max(len(spans), 1), 1.0), f"câu {seen['n']}/{len(spans)}")

        rc = ctx.run_process(cmd, cwd=str(work), on_line=on_line)
        if ctx.cancelled():
            return {}
        if rc != 0 or not out_file.is_file():
            raise VoiceError("voice_align_failed", "the aligner failed (exit code %s)" % rc)
        try:
            raw = json.loads(out_file.read_text(encoding="utf-8"))
        except ValueError:
            raise VoiceError("voice_align_failed", "the aligner wrote an unreadable file")
        return {int(k): v for k, v in raw.items() if isinstance(v, list)}


def choose(voice_cfg: dict, aligner_cfg: dict | None, language: str = "en", force: str | None = None):
    """`whisper` when asked for or (in `auto`) installed here, else `even`."""
    want = force or voice_cfg["aligner"].get("provider", "auto")
    if want == "even":
        return EvenAligner()
    if want == "whisper" and not aligner_cfg:
        raise VoiceError("voice_not_configured", "the aligner is not installed on this machine")
    if aligner_cfg:
        return WhisperAligner(aligner_cfg, voice_cfg, language)
    return EvenAligner()
