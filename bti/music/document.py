"""Validate music cue placement against a recording index and video timing."""
from __future__ import annotations

import math


class MusicError(ValueError):
    """A structured refusal suitable for conversion to the API error shape."""

    def __init__(self, detail, *, field=None):
        super().__init__(detail)
        self.code = "music_invalid"
        self.detail = detail
        self.fix = "Correct the music cue and try again."
        self.retry = "after_fix"
        self.field = field


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(doc, library, timing, duration, landmarks=None):
    """Validate and resolve cues; raise MusicError without changing the document.

    Standard timing anchors work alongside {"chapter": index}, {"ident": true}
    and {"end": true}; landmarks supplies ident and chapter times.
    """
    if not isinstance(doc, dict) or not isinstance(doc.get("cues"), list):
        raise MusicError("cues must be a list", field="cues")
    if not _number(duration) or duration <= 0:
        raise MusicError("video duration must be positive")
    landmarks = landmarks or {}

    def anchor(a):
        if not isinstance(a, dict):
            raise ValueError("anchor must be an object")
        if a.get("end") is True:
            return float(duration)
        if a.get("ident") is True:
            return float(landmarks["ident"])
        if "chapter" in a:
            i = a["chapter"]
            if not isinstance(i, int) or isinstance(i, bool) or i < 0:
                raise ValueError("chapter must be a nonnegative index")
            return float(landmarks["chapters"][i])
        stale = timing.stale(a)
        if stale:
            raise ValueError(stale)
        return timing.resolve(a)

    result = []
    for i, cue in enumerate(doc["cues"]):
        try:
            if not isinstance(cue, dict):
                raise ValueError("cue must be an object")
            if "level_db" in cue:
                error = MusicError("This music uses old numeric levels; choose the music again.", field="cues[%d]" % i)
                error.fix = "Choose the music again."
                raise error
            recording = cue.get("recording")
            if not isinstance(recording, str) or recording not in library:
                raise ValueError("recording is not in the library")
            start, end = anchor(cue.get("start")), anchor(cue.get("end"))
            offset, level = cue.get("offset"), cue.get("level")
            fade_in, fade_out = cue.get("fade_in"), cue.get("fade_out")
            if not all(_number(x) for x in (start, end, offset, fade_in, fade_out)):
                raise ValueError("times, offset and fades must be finite numbers")
            length = end - start
            if start < 0 or end > duration or length <= 0:
                raise ValueError("cue must lie within the video and have positive duration")
            recording_duration = library[recording].get("duration")
            if not _number(recording_duration) or offset < 0 or offset + length > recording_duration:
                raise ValueError("recording is too short for the selected passage")
            if level not in ("soft", "normal", "strong"):
                raise ValueError("level must be soft, normal, or strong")
            if min(fade_in, fade_out) < 0 or fade_in + fade_out > length:
                raise ValueError("fades must fit within the cue")
            if cue.get("role") not in ("bed", "swell", "ident", "ending"):
                raise ValueError("unknown cue role")
            if recording_duration < 45 and cue["role"] != "swell":
                raise ValueError("a recording under 45 seconds can only be used as a swell")
            if not isinstance(cue.get("why"), str) or not cue["why"].strip():
                raise ValueError("cue needs a reason")
            result.append({**cue, "start": start, "end": end})
        except MusicError:
            raise
        except (ValueError, KeyError, IndexError, TypeError, OverflowError) as exc:
            raise MusicError(str(exc), field="cues[%d]" % i) from exc
    result.sort(key=lambda c: c["start"])
    for i, (a, b) in enumerate(zip(result, result[1:])):
        overlap = a["end"] - b["start"]
        if overlap > min(a["fade_out"], b["fade_in"]):
            raise MusicError("overlap exceeds the cross-fade", field="cues[%d]" % (i + 1))
        if i and result[i - 1]["end"] > b["start"]:
            raise MusicError("three cues overlap", field="cues[%d]" % (i + 1))
    return result
