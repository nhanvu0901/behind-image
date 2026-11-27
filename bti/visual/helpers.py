"""Pure lookups shared by visual-script consumers."""
from __future__ import annotations

import re


def moment_words(moment: dict, timing: dict) -> tuple[list[str], float, float]:
    """Return the words and speech boundaries of a nonempty half-open span."""
    words = timing["words"]
    start, end = moment["w0"], moment["w1"]
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(words):
        raise ValueError("moment must have a nonempty word range within timing")
    return [w["w"] for w in words[start:end]], words[start]["s"], words[end - 1]["e"]


def sentence_for_word(timing: dict, index: int) -> tuple[int, int]:
    """Return the half-open sentence span using punctuation in the aligned words."""
    words = timing["words"]
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(words):
        raise IndexError(index)
    def ends(word):
        return bool(re.search(r'[.!?][\"\u2019\u201d\')\]]*$', word["w"]))
    start = index
    while start > 0 and not ends(words[start - 1]):
        start -= 1
    end = index + 1
    while end < len(words) and not ends(words[end - 1]):
        end += 1
    return start, end


def cast_member(cast: list[dict], member_id: str) -> dict | None:
    return next ( (member for member in cast if member.get("id") == member_id), None )


def show_matches(show: dict, member: dict) -> bool:
    """Match a concrete region or picture exactly against a cast member's places."""
    return show in member.get("shown_by", [])


def pool_shows(picks: dict) -> dict[str, list[str]]:
    """Return each non-main asset and the cast ids recorded for it."""
    return {key: list(asset.get("shows", [])) for key, asset in picks.get("assets", {}).items()
            if key != picks.get("main_asset")}


def resolve_show(show: dict, wanted: list[dict]) -> dict:
    """Resolve a completed search without altering the original show."""
    import copy
    row = next((item for item in wanted if item.get("id") == show.get("want")), None)
    if row and row.get("status") == "none":
        return copy.deepcopy(show["else"])
    if row and row.get("status") == "found" and row.get("picture"):
        return {"picture": row["picture"]}
    return copy.deepcopy(show)
