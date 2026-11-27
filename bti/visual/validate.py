"""Non-destructive shape and visual-script validity checks.

Checks use timing and, where provided, the picks record as evidence. Semantic
claims that cannot be decided from these inputs remain a matter for review.
"""
from __future__ import annotations

from collections import Counter
import re
from .helpers import cast_member, moment_words, show_matches
from .schema import VALIDATOR


def _tokens(text):
    return re.findall(r"[^\W_]+", str(text).casefold(), re.UNICODE)


def _contains(text, phrase):
    a, b = _tokens(text), _tokens(phrase)
    return bool(b) and any(a[i:i + len(b)] == b for i in range(len(a) - len(b) + 1))


def validate(doc: dict, timing: dict, picks: dict | None = None) -> list[dict]:
    """Return all determinable issues without changing the supplied documents."""
    issues = []
    def issue(rule, moment, message, path=None, subject=None, level="error"):
        row = {"rule": rule, "moment": moment, "message": message}
        if path is not None:
            row["path"] = path
        if subject is not None:
            row["subject"] = subject
        if level != "error":
            row["level"] = level
        issues.append(row)
    shape = sorted(VALIDATOR.iter_errors(doc), key=lambda e: tuple(map(str, e.absolute_path)))
    for error in shape:
        path = ".".join(map(str, error.absolute_path)) or "document"
        issue("shape", None, f"{path}: {error.message}; supply the specified shape.", path)
    safe_shape = all((len(e.absolute_path) >= 3 and e.absolute_path[0] == "moments" and e.absolute_path[2] in ("move", "from", "why"))
                     or (len(e.absolute_path) >= 1 and e.absolute_path[0] in ("schema", "made_from")) for e in shape)
    if shape and not safe_shape:
        # Check speech duration independently when malformed unrelated fields
        # do not prevent identifying the moment's word span.
        words = timing.get("words", []) if isinstance(timing, dict) else []
        moments = doc.get("moments", []) if isinstance(doc, dict) else []
        if isinstance(words, list) and isinstance(moments, list):
            for moment in moments:
                if not isinstance(moment, dict):
                    continue
                w0, w1 = moment.get("w0"), moment.get("w1")
                if not all(isinstance(w, int) and not isinstance(w, bool) for w in (w0, w1)) or not 0 <= w0 < w1 <= len(words):
                    continue
                try:
                    _, start, end = moment_words(moment, timing)
                    if end - start < 1.5:
                        mid = moment.get("id", "?")
                        issue("V2", mid, f"{mid}: extend the speech span to at least 1.5 seconds.")
                except (KeyError, TypeError, ValueError):
                    pass
        return issues
    words = timing.get("words", [])
    beats = {b.get("id"): b for b in timing.get("beats", [])}
    cursor = 0
    regions = Counter()
    intros = set()
    cast = doc["cast"]
    members = {m["id"]: m for m in cast}
    wanted = {w["id"]: w for w in doc["wanted"]}
    assets = (picks or {}).get("assets", {})
    main = (picks or {}).get("main_asset")
    main_regions = (assets.get(main) or {}).get("regions", {})
    narration = " ".join(w.get("w", "") for w in words)
    def forbidden_text(text):
        if re.search(r"\b[\w-]+\.[a-z0-9]{2,5}\b", text, re.I):
            return True
        for asset in assets.values():
            filename = str(asset.get("file", "")).replace("\\", "/").rsplit("/", 1)[-1]
            source = (asset.get("credit") or {}).get("source")
            if filename and _contains(text, filename):
                return True
            if isinstance(source, str) and source and _tokens(text) == _tokens(source):
                return True
        return False
    for kind, rows in (("cast", cast), ("wanted", doc["wanted"]), ("moments", doc["moments"])):
        counts = Counter(row["id"] for row in rows)
        for ident, n in counts.items():
            if n > 1:
                issue("shape", ident if kind == "moments" else None, f"{kind}: id {ident} occurs {n} times; give each entry a unique id.")
    for w in doc["wanted"]:
        if w["subject"] not in members:
            issue("V4", None, f"{w['id']}: choose one existing cast subject.")
        if w["status"] == "found" and not w["picture"]:
            issue("V4", None, f"{w['id']}: provide the found picture or change status.")
    def depicts(show, member):
        if show_matches(show, member):
            return True
        if "want" in show:
            entry = wanted.get(show["want"], {})
            if entry.get("status") == "none":
                return depicts(show["else"], member)
            return entry.get("subject") == member["id"]
        if "pair" in show:
            return any(show_matches(part, member) for part in show["pair"])
        if "map" in show:
            return member["kind"] == "place" and any(_contains(place, member["name"]) for place in show["map"]["places"])
        return False
    for index, m in enumerate(doc["moments"]):
        mid, w0, w1 = m["id"], m["w0"], m["w1"]
        beat = beats.get(m["line"])
        valid = 0 <= w0 < w1 <= len(words)
        if not valid:
            issue("V1", mid, f"{mid}: use a nonempty word range within the narration.")
        else:
            if w0 != cursor or not beat or w0 < beat.get("w0", 0) or w1 > beat.get("w1", 0):
                issue("V1", mid, f"{mid}: start at word {cursor} and keep the range inside line {m['line']}.")
            cursor = w1
            _, start, end = moment_words(m, timing)
            if end - start < 1.5:
                issue("V2", mid, f"{mid}: extend the speech span to at least 1.5 seconds.")
        show, about = m["show"], m["about"]
        member = members.get(about)
        if about is not None and member is None:
            issue("V3", mid, f"{mid}: use a cast id for about or null.")
        elif member and member["kind"] in ("person", "place", "work", "thing") and not m.get("about_not_shown") and not depicts(show, member):
            issue("V3", mid, f"{mid}: show a listed depiction of {about} or explain about_not_shown.")
        if "want" in show and show["want"] not in wanted:
            issue("V4", mid, f"{mid}: use a wanted id that exists.")
        if "region" in show:
            regions[show["region"]] += 1
        if "whole" in show and index not in (0, len(doc["moments"]) - 1):
            chapter_start = any(ch.get("w0") == w0 for ch in timing.get("chapters", []))
            about_whole = bool(member and member["kind"] == "work")
            if not chapter_start and not about_whole:
                issue("V9", mid, f"{mid}: verify this whole view is the cold open end or otherwise allowed; choose a detail if not.", level="review")
        if "map" in show and len(set(show["map"]["places"])) < 2:
            issue("V11", mid, f"{mid}: a map requires at least two distinct named places.")
        if "pair" in show and show["pair"][0] == show["pair"][1]:
            issue("V11", mid, f"{mid}: compare two different pictures.")
        elif "pair" in show:
            issue("V11", mid, f"{mid}: verify the narration compares these pictures or names both portraits within three seconds.", level="review")
        if "map" in show and len(set(show["map"]["places"])) >= 2:
            issue("V11", mid, f"{mid}: verify the narration describes a journey or a connection between these places.", level="review")
        for intent in m["say"]:
            if "intro" in intent:
                who, word = intent["intro"], intent["word"]
                introduced = members.get(who)
                if who in intros:
                    issue("V5", mid, f"{mid}: remove the repeated introduction of {who}.")
                intros.add(who)
                if not introduced or not depicts(show, introduced):
                    issue("V5", mid, f"{mid}: introduce {who} while showing a listed depiction.")
                if not valid or not w0 <= word < w1:
                    issue("V5", mid, f"{mid}: put the intro word inside this moment.")
                elif introduced:
                    spoken = " ".join(w["w"] for w in words[word:w1])
                    if not any(_contains(spoken, name) and _tokens(spoken)[:len(_tokens(name))] == _tokens(name) for name in [introduced["name"], *introduced["also"]]):
                        issue("V5", mid, f"{mid}: move the intro word to where {who}'s name or alias is spoken.")
            for point in intent.get("point", []):
                region = point["region"]
                if not valid or not w0 <= point["word"] < w1:
                    issue("V8", mid, f"{mid}: put point word inside the moment.")
                if "picture" not in show and any(c["kind"] == "person" and {"region": region} in c["shown_by"] for c in cast):
                    issue("V8", mid, f"{mid}: do not point at person region {region}.")
                visible_regions = (assets.get(show["picture"], {}).get("regions", {}) if "picture" in show else main_regions)
                if visible_regions and region not in visible_regions and "pair" not in show and "map" not in show:
                    issue("V8", mid, f"{mid}: use a region present on the displayed picture.")
                issue("V8", mid, f"{mid}: verify {region} is not a person and can be framed with the shown picture.", level="review")
            texts = []
            if "read" in intent:
                texts.append(intent["read"]["text"])
            if "labels" in intent:
                texts.extend(label["text"] for label in intent["labels"])
            for text in texts:
                evidence = narration + " " + " ".join(str(value) for a in assets.values() for key, value in a.items() if key in ("caption", "title", "description"))
                if forbidden_text(text):
                    issue("V12", mid, f"{mid}: replace file or source text {text!r} with a supported label.")
                elif not _contains(evidence, text):
                    issue("V12", mid, f"{mid}: verify screen text against the narration or picture record: {text!r}.", level="review")
    if cursor != len(words):
        issue("V1", None, f"Cover all words through word {len(words)}; coverage ends at {cursor}.")
    for member in cast:
        sub = member["sub"]
        if len(sub.split()) > 6 or any(_contains(sub, name) for name in [member["name"], *member["also"]]):
            issue("V7", None, f"{member['id']}: shorten sub to six words and omit the name and aliases.", subject=member["id"])
        if member["kind"] == "thing":
            issue("V6", None, f"{member['id']}: verify the strip is used only if the narration explains an unfamiliar term.", subject=member["id"], level="review")
        if member["kind"] in ("person", "place", "work") and member["name"][:1].isupper() and not member["strip"]:
            issue("V6", None, f"{member['id']}: verify whether this is a proper name that needs a strip.", subject=member["id"], level="review")
        if sub:
            issue("V7", None, f"{member['id']}: verify the subtitle is no more certain than the narration.", subject=member["id"], level="review")
        if member["kind"] in ("idea", "text") and member["strip"]:
            issue("V6", None, f"{member['id']}: disable the strip for ideas and text.", subject=member["id"])
        if sub and forbidden_text(sub):
            issue("V12", None, f"{member['id']}: replace file or source text in the subtitle.", subject=member["id"])
        elif sub and not _contains(narration, sub) and not any(_contains(str(a.get("caption", "")), sub) for a in assets.values()):
            issue("V12", None, f"{member['id']}: verify the subtitle against the narration or picture record.", subject=member["id"], level="review")
    for region, count in regions.items():
        if count > 4:
            for m in doc["moments"]:
                if m["show"] == {"region": region}:
                    issue("V10", m["id"], f"{m['id']}: {region} appears in {count} moments; choose another view or subject.", level="review")
    return issues
