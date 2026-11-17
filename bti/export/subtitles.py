"""Subtitle cues from the timing words (design section 8, item 2). Pure functions; times are integer milliseconds so that no
rounding can make two cues overlap.

Rules: at most two lines of 42 characters; a cue breaks at a sentence end, at a pause, at the start of a beat or chapter, and
inside a long sentence preferably after a comma or before a pause; no cue under 0.8 s or over 6 s; no two cues overlap (a gap of
at least 40 ms). Subtitles are written to a sidecar `.srt` and a soft `mov_text` track; they are never drawn into the picture.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_LINE = 42
MAX_LINES = 2
MIN_MS = 800
MAX_MS = 6000
GAP_MS = 40               # smallest gap between two cues
PAUSE_MS = 600            # a silence this long between two words ends a cue
SOFT_PAUSE_MS = 250       # a silence this long is a good place to break inside a sentence
LINGER_MS = 120           # a cue stays a little after its last word when there is room

_SENT_END = re.compile(r"""[.!?…]["'”’)\]]*$""")
_ABBREV = {"mr.", "mrs.", "ms.", "dr.", "st.", "vs.", "no.", "nos.", "ca.", "c.", "fig.", "figs.", "vol.", "p.", "pp.", "ft.",
           "jr.", "sr.", "prof.", "rev.", "mt.", "e.g.", "i.e.", "approx.", "inc.", "co.", "ltd.", "op.", "cf.", "viz."}


@dataclass(frozen=True)
class Cue:
    start: int                      # ms
    end: int                        # ms
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def ms(self) -> int:
        return self.end - self.start


@dataclass
class _W:
    text: str
    s: int
    e: int


def _is_sentence_end(w: str) -> bool:
    lw = w.lower()
    if lw in _ABBREV or re.fullmatch(r"[A-Z]\.", w):
        return False
    return bool(_SENT_END.search(w))


def clean_words(words) -> list[_W]:
    """Words of the timing as `_W` (text, start ms, end ms): empty words dropped, starts never go backwards, every word lasts
    at least 1 ms."""
    out: list[_W] = []
    for w in words or []:
        if not isinstance(w, dict):
            continue
        t = re.sub(r"\s+", " ", str(w.get("w", ""))).strip()
        try:
            s, e = float(w.get("s")), float(w.get("e"))
        except (TypeError, ValueError):
            continue
        if not t or s != s or e != e:
            continue
        s_ms = max(0, int(round(s * 1000)))
        if out:
            s_ms = max(s_ms, out[-1].s)
        e_ms = max(s_ms + 1, int(round(e * 1000)))
        out.append(_W(t, s_ms, e_ms))
    return out


def wrap(texts: list[str]) -> list[str] | None:
    """The words of one cue as at most two lines of at most 42 characters, balanced, preferring a break after punctuation;
    None when they do not fit."""
    one = " ".join(texts)
    if len(one) <= MAX_LINE:
        return [one]
    best = None
    for k in range(1, len(texts)):
        a, b = " ".join(texts[:k]), " ".join(texts[k:])
        if len(a) > MAX_LINE or len(b) > MAX_LINE:
            continue
        cost = abs(len(a) - len(b)) - (8 if a[-1] in ",;:.?!" else 0)
        if best is None or cost < best[0]:
            best = (cost, [a, b])
    return best[1] if best else None


def _break_cost(ws: list[_W], i: int, j: int, n: int) -> float:
    """Cost of ending a cue after word j-1 (a piece of the words i..j-1 of a segment of n words)."""
    c = 1.0
    last = ws[j - 1].text
    if j < n:
        gap = ws[j].s - ws[j - 1].e
        if last[-1] in ",;:—-":
            c += 0.0
        elif gap >= SOFT_PAUSE_MS:
            c += 0.3
        else:
            c += 2.0
    if j - i < 3 and n > 3:
        c += 1.5
    if ws[j - 1].e - ws[i].s < MIN_MS:
        c += 1.0
    length = len(" ".join(w.text for w in ws[i:j]))
    if n > 1 and length < 25 and (j - i) < n:
        c += (25 - length) / 25.0
    return c


def _split_segment(ws: list[_W]) -> list[tuple[int, int]]:
    """Best way to cut one segment (a sentence, or a part of one) into cues: the pieces as (i, j) word ranges."""
    n = len(ws)
    INF = float("inf")
    best = [INF] * (n + 1)
    prev = [0] * (n + 1)
    best[0] = 0.0
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            if j - i > 1:
                if ws[j - 1].e - ws[i].s > MAX_MS:
                    break                                   # a longer piece only gets longer
                if wrap([w.text for w in ws[i:j]]) is None:
                    continue
            cost = best[i] + _break_cost(ws, i, j, n) + (50.0 if j - i == 1 and len(ws[i].text) > MAX_LINE else 0.0)
            if cost < best[j]:
                best[j], prev[j] = cost, i
    out = []
    j = n
    while j > 0:
        out.append((prev[j], j))
        j = prev[j]
    return out[::-1]


def segments(ws: list[_W], forced_starts=(), group_starts=()) -> list[tuple[int, int, int]]:
    """Cut the word list into segments `(i, j, group)`: at sentence ends, at pauses, at `forced_starts` (word indexes: beat
    starts) and at `group_starts` (chapter starts; the group number counts them). Cues never merge across groups."""
    forced, groups = set(forced_starts), set(group_starts)
    out, i, g = [], 0, 0
    for k in range(1, len(ws) + 1):
        if k == len(ws) or k in forced or k in groups or _is_sentence_end(ws[k - 1].text) or ws[k].s - ws[k - 1].e >= PAUSE_MS:
            out.append((i, k, g))
            if k in groups:
                g += 1
            i = k
    return out


def _finalize(raw: list[list], ws_len: int) -> list[Cue]:
    """`raw` = [[start, end, lines, group, word_count]] in order -> merge the cues that are too short, then fix every time."""
    cues = [list(c) for c in raw]
    # 1. a cue that stays under the minimum even with the free silence around it is merged into a neighbour when it fits
    k = 0
    while k < len(cues):
        c = cues[k]
        prv = cues[k - 1] if k else None
        nxt = cues[k + 1] if k + 1 < len(cues) else None
        room_after = (nxt[0] - GAP_MS - c[1]) if nxt else MIN_MS
        room_before = (c[0] - (prv[1] + GAP_MS)) if prv else MIN_MS
        short = (c[1] - c[0]) + LINGER_MS + max(0, room_after - LINGER_MS) + max(0, room_before) < MIN_MS
        merged = False
        if short:
            for nb, first in ((prv, True), (nxt, False)):
                if nb is None or nb[3] != c[3]:
                    continue
                a, b = (nb, c) if first else (c, nb)
                texts = " ".join(a[2] + b[2]).split()
                lines = wrap(texts)
                if lines is not None and b[1] - a[0] <= MAX_MS:
                    new = [a[0], b[1], tuple(lines), c[3], a[4] + b[4]]
                    lo = k - 1 if first else k
                    cues[lo:lo + 2] = [new]
                    k = max(0, lo)
                    merged = True
                    break
        if not merged:
            k += 1
    # 2. times: never overlap, length within limits
    out: list[Cue] = []
    for k, c in enumerate(cues):
        s, e = c[0], c[1]
        if out:
            s = max(s, out[-1].end + GAP_MS)
        e = max(e, s + 1)
        nxt_start = cues[k + 1][0] if k + 1 < len(cues) else None
        limit = (nxt_start - GAP_MS) if nxt_start is not None else None
        want = max(e + LINGER_MS, s + MIN_MS)
        if limit is not None:
            want = min(want, limit)
        e = max(e, want)
        if e - s < MIN_MS:                                   # still short: start earlier, into the silence before
            s = max(out[-1].end + GAP_MS if out else 0, e - MIN_MS)
        if e - s > MAX_MS:
            e = s + MAX_MS
        out.append(Cue(s, e, tuple(c[2])))
    return out


def build_cues(words, forced_starts=(), group_starts=()) -> list[Cue]:
    """The cues of a narration: `words` are the `{w, s, e}` of timing.json (seconds)."""
    ws = clean_words(words)
    raw = []
    for i, j, g in segments(ws, forced_starts, group_starts):
        for a, b in _split_segment(ws[i:j]):
            piece = ws[i + a:i + b]
            lines = wrap([w.text for w in piece]) or [" ".join(w.text for w in piece)]
            raw.append([piece[0].s, piece[-1].e, tuple(lines), g, len(piece)])
    return _finalize(raw, len(ws))


def cues_from_timing(timing: dict) -> list[Cue]:
    """Cues for a `timing.json` document (words, and beats/chapters for the forced breaks)."""
    words = timing.get("words") or []
    ws = clean_words(words)
    # indexes refer to the ORIGINAL word list; map them to the cleaned list (empty words are dropped)
    keep = []
    for idx, w in enumerate(words):
        if isinstance(w, dict) and re.sub(r"\s+", " ", str(w.get("w", ""))).strip():
            try:
                float(w.get("s")); float(w.get("e"))
            except (TypeError, ValueError):
                continue
            keep.append(idx)
    pos = {orig: new for new, orig in enumerate(keep)}
    forced = set()
    for b in timing.get("beats") or []:
        w0 = b.get("w0") if isinstance(b, dict) else None
        if isinstance(w0, int) and w0 in pos and pos[w0] > 0:
            forced.add(pos[w0])
    group = set()
    starts = sorted(float(c["start"]) for c in (timing.get("chapters") or []) if isinstance(c, dict) and isinstance(c.get("start"), (int, float)))
    for t in starts:
        for k, w in enumerate(ws):
            if w.s >= int(round(t * 1000)) - 1:
                if k > 0:
                    group.add(k)
                break
    return build_cues(words, forced, group)


def srt_time(ms: int) -> str:
    ms = max(0, int(ms))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def to_srt(cues: list[Cue]) -> str:
    parts = []
    for n, c in enumerate(cues, 1):
        parts.append("%d\n%s --> %s\n%s\n" % (n, srt_time(c.start), srt_time(c.end), c.text))
    return "\n".join(parts)


_TIME = re.compile(r"^(\d+):(\d\d):(\d\d)[,.](\d{3}) --> (\d+):(\d\d):(\d\d)[,.](\d{3})")


def parse_srt(text: str) -> list[Cue]:
    """Reads a `.srt` text back (used by the checks)."""
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = block.split("\n")
        if len(lines) < 3:
            continue
        m = _TIME.match(lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        cues.append(Cue(((g[0] * 60 + g[1]) * 60 + g[2]) * 1000 + g[3], ((g[4] * 60 + g[5]) * 60 + g[6]) * 1000 + g[7], tuple(lines[2:])))
    return cues


def check_cues(cues: list[Cue]) -> list[dict]:
    """Every rule of section 8 checked on a list of cues: [{"cue": n (1-based), "code": ..., "detail": ...}]."""
    bad = []
    for n, c in enumerate(cues, 1):
        if len(c.lines) > MAX_LINES or not c.lines:
            bad.append({"cue": n, "code": "lines", "detail": "%d lines" % len(c.lines)})
        for ln in c.lines:
            if len(ln) > MAX_LINE:
                bad.append({"cue": n, "code": "line_length", "detail": "%d characters" % len(ln)})
        if c.ms < MIN_MS:
            bad.append({"cue": n, "code": "too_short", "detail": "%d ms" % c.ms})
        if c.ms > MAX_MS:
            bad.append({"cue": n, "code": "too_long", "detail": "%d ms" % c.ms})
        if n > 1 and c.start < cues[n - 2].end:
            bad.append({"cue": n, "code": "overlap", "detail": "%d ms" % (cues[n - 2].end - c.start)})
    return bad
