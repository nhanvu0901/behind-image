"""Word lookup and anchor resolution over `timing.json`.

Anchors (design section 6):
    {"t": seconds}                          absolute time
    {"w": index, "off": s, "text": word}    spoken word; resolves to words[w].s + off
    {"rel": 0..1}                           fraction of the parent shot (camera keys only)
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .errors import DataError
from ..textfold import squash


def norm(w: str) -> str:
    """Normalise a word: case-fold, fold accents, keep letters and digits of any script (same result as the benchmark for ASCII)."""
    return squash(w)


class AnchorError(ValueError):
    pass


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def shape_problem(data) -> str | None:
    """None when `data` has the shape the engine reads: {duration?, words: [{w, s}], beats?, chapters?}."""
    if not isinstance(data, dict):
        return "the top level must be an object"
    if "duration" in data and not _num(data["duration"]):
        return "duration must be a number"
    words = data.get("words", [])
    if not isinstance(words, list):
        return "words must be a list"
    for i, w in enumerate(words):
        if not (isinstance(w, dict) and isinstance(w.get("w"), str) and _num(w.get("s"))):
            return "word %d needs a text `w` and a numeric start `s`" % i
    for k in ("beats", "chapters"):
        if k in data and not isinstance(data[k], list):
            return "%s must be a list" % k
    return None


class Timing:
    def __init__(self, data: dict):
        self.data = data
        self.duration = float(data.get("duration", 0.0))
        self.words = data.get("words", [])
        self.beats = data.get("beats", [])
        self.chapters = data.get("chapters", [])
        self._norm = None

    @classmethod
    def load(cls, path: Path) -> "Timing":
        """Read a timing file. Anything wrong with it (missing, not JSON, wrong shape) is a DataError that names the file."""
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise DataError("%s is missing" % path.name, what="timing")
        except (OSError, UnicodeDecodeError, ValueError) as e:
            raise DataError("%s is corrupt: %s" % (path.name, str(e)[:120]), what="timing")
        msg = shape_problem(data)
        if msg:
            raise DataError("%s is not a timing file: %s" % (path.name, msg), what="timing")
        return cls(data)

    # -- words ---------------------------------------------------------------------------------------------
    def word_start(self, i: int) -> float:
        return float(self.words[i]["s"])

    def word_text(self, i: int) -> str:
        return self.words[i]["w"]

    def _normed(self):
        if self._norm is None:
            self._norm = [norm(w["w"]) for w in self.words]
        return self._norm

    def find(self, phrase: str, nth: int = 0) -> int:
        """Index of the first word of the nth occurrence of `phrase` (KeyError when absent)."""
        p = [norm(x) for x in phrase.split()]
        n = self._normed()
        hits = 0
        for i in range(len(n) - len(p) + 1):
            if all(n[i + k] == p[k] for k in range(len(p))):
                if hits == nth:
                    return i
                hits += 1
        raise KeyError(phrase)

    def anchor_for(self, phrase: str, nth: int = 0, wi: int = 0, off: float = 0.0) -> dict:
        """Build a word anchor from a phrase (the benchmark's `tt(phrase, nth, wi, off)`)."""
        i = self.find(phrase, nth) + wi
        return {"w": i, "off": off, "text": self.words[i]["w"]}

    def nearest_word(self, t: float) -> int:
        """Index of the word being spoken at (or last spoken before) time t."""
        lo, hi = 0, len(self.words)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.words[mid]["s"] <= t:
                lo = mid + 1
            else:
                hi = mid
        return max(0, lo - 1)

    def anchor_at(self, t: float, snap: bool = True) -> dict:
        """Anchor for an absolute time: a word anchor when `snap`, else {"t": t}."""
        if not snap or not self.words:
            return {"t": round(float(t), 4)}
        i = self.nearest_word(t)
        return {"w": i, "off": round(t - self.word_start(i), 4), "text": self.words[i]["w"]}

    # -- anchors ---------------------------------------------------------------------------------------------
    def resolve(self, a: dict, t0: float | None = None, t1: float | None = None) -> float:
        """Resolve an anchor to seconds. `rel` needs the parent span (t0, t1)."""
        if not isinstance(a, dict):
            raise AnchorError("anchor must be an object")
        def num(key, default=None):
            v = a.get(key, default)
            if not _num(v):
                raise AnchorError("anchor field %r must be a number, not %r" % (key, v))
            return float(v)

        if "t" in a:
            return num("t")
        if "w" in a:
            i = a["w"]
            if not isinstance(i, int) or isinstance(i, bool) or i < 0 or i >= len(self.words):
                raise AnchorError("word index %r out of range 0..%d" % (i, len(self.words) - 1))
            return self.word_start(i) + num("off", 0.0)
        if "rel" in a:
            if t0 is None or t1 is None:
                raise AnchorError("'rel' anchors are only allowed inside a shot (camera keys)")
            return t0 + num("rel") * (t1 - t0)
        raise AnchorError("anchor needs one of t, w, rel")

    def stale(self, a: dict) -> str | None:
        """Return a message when a word anchor's `text` no longer matches the word at its index."""
        if isinstance(a, dict) and "w" in a and "text" in a:
            i = a["w"]
            if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(self.words) and isinstance(a["text"], str) \
                    and norm(a["text"]) != norm(self.words[i]["w"]):
                return "anchor text %r does not match word %d %r (script changed?)" % (a["text"], i, self.words[i]["w"])
        return None
