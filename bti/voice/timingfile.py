"""`timing.json` from the aligned words: `{duration, words: [{w, s, e}], beats: [...], chapters: [...]}`, the shape the engine
reads (`bti.engine.timing`), with the narration's beat and chapter ids added."""
from __future__ import annotations

from bti.engine.timing import shape_problem

from .errors import VoiceError


def build_timing(plan, spans: list[dict], words: list[dict], ranges: list[tuple[int, int]], duration: float, cfg: dict) -> dict:
    chunks = plan.chunks
    beats: list[dict] = []
    by_beat: dict[str, dict] = {}
    texts = {b.id: b.text for ch in plan.narration.chapters for b in ch.beats}
    for c, (w0, w1) in zip(chunks, ranges):
        b = by_beat.get(c.beat)
        if b is None:
            b = {"id": c.beat, "chapter": c.chapter, "text": " ".join(texts.get(c.beat, "").split()), "w0": w0, "w1": w1}
            by_beat[c.beat] = b
            beats.append(b)
        b["w1"] = w1
    for b in beats:
        if b["w1"] > b["w0"]:
            b["start"] = words[b["w0"]]["s"]
            b["end"] = words[b["w1"] - 1]["e"]
        else:
            b["start"] = b["end"] = words[b["w0"]]["s"] if b["w0"] < len(words) else 0.0
        b["start"], b["end"] = round(b["start"], 4), round(b["end"], 4)
    chapters: list[dict] = []
    first_chunk: dict[str, int] = {}
    for i, c in enumerate(chunks):
        first_chunk.setdefault(c.chapter, i)
    ordered = [ch for ch in plan.narration.chapters if ch.id in first_chunk]
    for k, ch in enumerate(ordered):
        i = first_chunk[ch.id]
        sp = spans[i]
        gap = chunks[i].gap
        start = 0.0 if k == 0 else round(sp["start"] - gap, 4)
        end = duration if k == len(ordered) - 1 else round(spans[first_chunk[ordered[k + 1].id]]["start"] - chunks[first_chunk[ordered[k + 1].id]].gap, 4)
        item = {"id": ch.id, "name": ch.title or ch.id, "start": start, "end": round(end, 4), "card": bool(ch.card)}
        if ch.card:      # the silence the voice left for the chapter card
            item["card_start"] = round(sp["start"] - gap + 0.3, 4)
            item["card_end"] = round(sp["start"] - 0.3, 4)
        chapters.append(item)
    timing = {"duration": round(duration, 4), "words": words, "beats": beats, "chapters": chapters}
    problem = shape_problem(timing)
    if problem:
        raise VoiceError("voice_align_failed", "timing.json would be malformed: " + problem, 500)
    return timing
