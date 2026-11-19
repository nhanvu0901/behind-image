"""Word counts, estimated minutes, per-chapter budgets, sentence-length profile."""
from __future__ import annotations

import re
import statistics

from .store import Narration, Outline

WPS_DEFAULT = 2.41          # words per second, measured for this voice

# THE sentence limit: the prompts say it (prompts/script.md, prompts/rules_voice.md, filled in by prompting.py), `long_sentence` checks it
# (validate.py), the bench criterion `narration.max_sentence_words` defaults to it, and the documents quote it. One number, one place:
# it used to be 28 in the prompts and the check but 25 in the profile and the documents, so a 26-word sentence passed silently.
MAX_SENTENCE_WORDS = 25

# style targets for the sentence profile (research: corpus median 17, p90 36, 23% over 25;
# the spoken-text rule of the comic channel: mostly 8-22, never a fragment under 4). The longest sentence is not a target any more:
# it is the limit above, and every sentence over it is a `long_sentence` warning of its line.
STYLE_TARGETS = {"median": (12, 22), "max": MAX_SENTENCE_WORDS, "share_under_4_max": 0.05}

_ABBREV = {"mr", "mrs", "ms", "dr", "st", "vs", "c", "no", "vol", "fig", "ca", "jr", "sr", "prof", "e.g", "i.e"}
_SPLIT = re.compile(r"(?<=[.!?])[\"”’')\]]*\s+(?=[\"“‘'(\[]*[A-Z0-9])")


def count_words(text: str) -> int:
    return sum(1 for t in text.split() if re.search(r"\w", t))


def minutes(words: int, wps: float = WPS_DEFAULT) -> float:
    return round(words / wps / 60.0, 2) if wps > 0 else 0.0


def sentences(text: str) -> list[str]:
    parts, buf = [], ""
    for chunk in _SPLIT.split(text.strip()):
        buf = (buf + " " + chunk).strip() if buf else chunk
        last = re.sub(r"[^\w.]", "", buf.split()[-1]).rstrip(".").lower() if buf.split() else ""
        if last in _ABBREV and buf.rstrip().endswith("."):
            continue
        parts.append(buf)
        buf = ""
    if buf:
        parts.append(buf)
    return [p for p in parts if count_words(p)]


def _pct(sorted_vals: list[int], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def sentence_profile(texts: list[str]) -> dict:
    lens = sorted(count_words(s) for t in texts for s in sentences(t))
    n = len(lens)
    if not n:
        return {"sentences": 0, "median": 0, "mean": 0, "p90": 0, "max": 0, "share_over_25": 0.0,
                "share_under_4": 0.0, "targets": STYLE_TARGETS, "notes": []}
    prof = {"sentences": n, "median": statistics.median(lens), "mean": round(sum(lens) / n, 1),
            "p90": round(_pct(lens, 0.9), 1), "max": lens[-1],
            "share_over_25": round(sum(1 for x in lens if x > MAX_SENTENCE_WORDS) / n, 3),      # the share over THE limit (25: the key keeps its name)
            "share_under_4": round(sum(1 for x in lens if x < 4) / n, 3), "targets": STYLE_TARGETS}
    t, notes = STYLE_TARGETS, []
    if not (t["median"][0] <= prof["median"] <= t["median"][1]):
        notes.append(f"median sentence length {prof['median']} words is outside {t['median'][0]}-{t['median'][1]}")
    if prof["share_over_25"] > 0:
        notes.append(f"{prof['share_over_25']:.0%} of the sentences are longer than {MAX_SENTENCE_WORDS} words (the limit; each one is a warning of its line)")
    if prof["share_under_4"] > t["share_under_4_max"]:
        notes.append(f"{prof['share_under_4']:.0%} of the sentences are shorter than 4 words (target {t['share_under_4_max']:.0%} at most)")
    if n >= 8 and prof["max"] - lens[0] < 6:
        notes.append("the sentences are almost all the same length; vary short and long")
    prof["notes"] = notes
    return prof


def narration_stats(n: Narration, outline: Outline | None = None, wps: float = WPS_DEFAULT) -> dict:
    chapters, total = [], 0
    for c in n.chapters:
        w = sum(count_words(b.text) for b in c.beats)
        total += w
        oc = outline.chapter(c.id) if outline else None
        budget = oc.word_budget if oc else 0
        chapters.append({"id": c.id, "title": c.title, "role": c.role, "beats": len(c.beats), "words": w,
                         "minutes": minutes(w, wps), "budget": budget,
                         "ratio": round(w / budget, 3) if budget else None})
    target = outline.target_words if outline else 0
    return {"words": total, "minutes": minutes(total, wps), "wps": wps, "beats": sum(len(c.beats) for c in n.chapters),
            "target_words": target, "target_ratio": round(total / target, 3) if target else None,
            "chapters": chapters,
            "sentence_profile": sentence_profile([b.text for c in n.chapters for b in c.beats])}
