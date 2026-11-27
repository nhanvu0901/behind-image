"""Bounded, deterministic scheduling of the resolved visual moments."""
from __future__ import annotations

from copy import deepcopy


def _borrowed(show):
    return any(key in show for key in ("picture", "pair", "map"))


def schedule(moments: list[dict], end: float, *, floor: float,
             borrowed_floor: float) -> tuple[list[dict], list[dict]]:
    """Schedule contiguous moments without mutating input.

    Entries have id, start, sentence_start, line and resolved show. Boundaries
    may move into adjacent shots only while preserving their own floors. Each
    unsuccessful repair removes one entry, so the algorithm always terminates.
    """
    shots = deepcopy(moments)
    notes: list[dict] = []
    segment_start = shots[0]["start"] if shots else 0.0

    def note(shot, rule, what):
        notes.append({"moment": shot["id"], "rule": rule, "what": what})

    def duration(i):
        return (shots[i + 1]["start"] if i + 1 < len(shots) else end) - shots[i]["start"]

    def minimum(i):
        shot = shots[i]
        intro_min = max(0, shot.get("intro_end", 0) - shot["start"]) if not shot.get("intro_unavailable") else 0
        return max(shot.get("min_duration", floor), borrowed_floor if _borrowed(shot["show"]) else floor, intro_min)

    # C1: equal neighbours are one uninterrupted view, even across sentences.
    i = 1
    while i < len(shots):
        if shots[i - 1]["show"] == shots[i]["show"]:
            note(shots[i], "C1", "joined into " + shots[i - 1]["id"])
            shots[i - 1].setdefault("joined", []).append(shots[i])
            shots[i - 1]["intro_end"] = max(shots[i - 1].get("intro_end", 0), shots[i].get("intro_end", 0))
            shots[i - 1]["min_duration"] = max(shots[i - 1].get("min_duration", floor), shots[i].get("min_duration", floor))
            del shots[i]
        else:
            i += 1

    # Move every borrowed view toward its sentence start, not only short ones.
    for i in range(1, len(shots)):
        shot = shots[i]
        if not _borrowed(shot["show"]):
            continue
        earliest = max(shots[i - 1]["start"] + minimum(i - 1), shot.get("sentence_start", shot["start"]))
        if earliest < shot["start"]:
            shot["start"] = earliest
            note(shot, "C1", "extended backward toward sentence start")
            note(shots[i - 1], "C1", "shortened to make room for the following picture")

    while len(shots) > 1:
        i = next ( (j for j in range(len(shots))
                    if duration(j) < minimum(j) - 1e-9), None )
        if i is None:
            break
        shot = shots[i]
        need = minimum(i) - duration(i)
        if shot.get("intro_end", 0) > shot["start"] + duration(i) and not shot.get("intro_unavailable"):
            if i + 1 < len(shots):
                take = min(need, max(0.0, duration(i + 1) - minimum(i + 1)))
                if take:
                    shots[i + 1]["start"] += take
                    note(shot, "C4", "extended forward for introduction")
                    note(shots[i + 1], "C4", "start moved later to fit the previous introduction")
                    need = minimum(i) - duration(i)
                if need > 1e-9 and not _borrowed(shots[i + 1]["show"]):
                    child = shots.pop(i + 1)
                    shot.setdefault("joined", []).append(child)
                    shot["intro_end"] = max(shot.get("intro_end", 0), child.get("intro_end", 0))
                    shot["min_duration"] = max(shot.get("min_duration", floor), child.get("min_duration", floor))
                    note(child, "C1", "joined into " + shot["id"] + " to fit introduction")
                    note(shot, "C4", "extended forward for introduction by joining the next moment")
                    continue
            if need > 1e-9:
                shot["intro_unavailable"] = True
                note(shot, "C4", "introduction has too little time after the spoken word")
                continue
            continue
        if _borrowed(shot["show"]):
            # Sentence start first, then any remaining slack before the picture.
            if i:
                limit = shots[i - 1]["start"] + minimum(i - 1)
                sentence = min(shot["start"], shot.get("sentence_start", shot["start"]))
                new = max(limit, sentence, shot["start"] - need)
                if new < shot["start"]:
                    shot["start"] = new
                    note(shot, "C1", "extended backward toward sentence start")
                    note(shots[i - 1], "C1", "shortened to make room for the following picture")
                    need = minimum(i) - duration(i)
            if need > 1e-9 and i + 1 < len(shots):
                take = min(need, max(0.0, duration(i + 1) - minimum(i + 1)))
                if take:
                    shots[i + 1]["start"] += take
                    note(shot, "C1", "extended forward")
                    note(shots[i + 1], "C1", "shortened to make room for the preceding picture")
                    need -= take
            if need > 1e-9 and i:
                take = min(need, max(0.0, duration(i - 1) - minimum(i - 1)))
                if take:
                    shot["start"] -= take
                    note(shot, "C1", "extended backward")
                    note(shots[i - 1], "C1", "shortened to make room for the following picture")
                    need -= take
            if need <= 1e-9:
                continue
            # A pair is meaningful only for two distinct pictures in a sentence.
            for j in (i - 1, i + 1):
                if (0 <= j < len(shots) and shot.get("sentence_start") == shots[j].get("sentence_start")
                        and "picture" in shot["show"] and "picture" in shots[j]["show"]
                        and shot["show"] != shots[j]["show"]):
                    left, right = sorted((i, j))
                    first, second = shots[left], shots[right]
                    first["show"] = {"pair": [first["show"], second["show"]]}
                    first.setdefault("joined", []).append(second)
                    first["intro_end"] = max(first.get("intro_end", 0), second.get("intro_end", 0))
                    first["min_duration"] = max(first.get("min_duration", floor), second.get("min_duration", floor))
                    note(second, "C2", "paired with " + first["id"])
                    del shots[right]
                    break
            else:
                j = None
            if j is not None:
                continue
            # Preserve the borrowed picture by joining an adjacent main view
            # before considering dropping the picture itself.
            neighbour = next((j for j in (i - 1, i + 1)
                              if 0 <= j < len(shots) and not _borrowed(shots[j]["show"])), None)
            if neighbour is not None:
                child = shots.pop(neighbour)
                if neighbour < i:
                    shot["start"] = child["start"]
                shot.setdefault("joined", []).append(child)
                shot["intro_end"] = max(shot.get("intro_end", 0), child.get("intro_end", 0))
                shot["min_duration"] = max(shot.get("min_duration", floor), child.get("min_duration", floor))
                note(child, "C1", "joined into " + shot["id"] + " to keep the picture")
                continue
        candidates = [j for j in (i - 1, i + 1) if 0 <= j < len(shots)]
        same = [j for j in candidates if shots[j]["show"] == shot["show"]]
        target = same[0] if same else (i - 1 if i else i + 1)
        if target > i:
            shots[target]["start"] = shot["start"]
        note(shot, "C1", "joined into " + shots[target]["id"])
        if _borrowed(shot["show"]):
            note(shot, "C2", "picture dropped after no room for a pair")
        shots[target].setdefault("joined", []).append(shot)
        shots[target]["intro_end"] = max(shots[target].get("intro_end", 0), shot.get("intro_end", 0))
        shots[target]["min_duration"] = max(shots[target].get("min_duration", floor), shot.get("min_duration", floor))
        del shots[i]
    # A pair covers its entire sentence, joining neighbours if the floor would
    # otherwise be violated. Program boundaries remain absolute.
    i = 0
    while i < len(shots):
        shot = shots[i]
        if "pair" not in shot["show"]:
            i += 1
            continue
        requested = shot.get("sentence_start", shot["start"])
        start = max(segment_start, requested)
        if start > requested + 1e-9:
            note(shot, "C2", "pair starts after the sentence because a program boundary occupies it")
        while i and start < shots[i - 1]["start"] + minimum(i - 1) - 1e-9:
            child = shots.pop(i - 1)
            i -= 1
            start = min(start, child["start"])
            shot.setdefault("joined", []).append(child)
            note(child, "C2", "joined into pair " + shot["id"] + " to cover the sentence")
            if _borrowed(child["show"]):
                note(child, "C2", "picture dropped because the pair occupies the sentence")
        shot["start"] = min(shot["start"], start)
        requested_end = shot.get("sentence_end", shot["start"])
        stop = min(end, requested_end)
        if stop < requested_end - 1e-9:
            note(shot, "C2", "pair ends before the sentence because a program boundary occupies it")
        while i + 1 < len(shots) and shots[i + 1]["start"] < stop - 1e-9:
            next_end = shots[i + 2]["start"] if i + 2 < len(shots) else end
            if next_end - stop >= minimum(i + 1) - 1e-9:
                shots[i + 1]["start"] = stop
                note(shots[i + 1], "C2", "start moved to the end of the pair's sentence")
                break
            child = shots.pop(i + 1)
            shot.setdefault("joined", []).append(child)
            note(child, "C2", "joined into pair " + shot["id"] + " to cover the sentence")
            if _borrowed(child["show"]):
                note(child, "C2", "picture dropped because the pair occupies the sentence")
        i += 1
    if shots and duration(0) < minimum(0) - 1e-9:
        note(shots[0], "C1", "entire available duration is shorter than the minimum")
    return shots, notes
