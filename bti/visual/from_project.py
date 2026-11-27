"""Convert a legacy storyboard to a visual script without a model.

The source is never modified. Use --pool-out to save a separate picks copy with
inferred picture subjects; the visual document itself has no pool field.
"""
from __future__ import annotations

import argparse
import bisect
import copy
import hashlib
import json
from pathlib import Path
from collections import Counter

from bti.engine.timing import Timing, AnchorError
from bti.engine.viewchecks import is_program_shot
from .validate import validate


def _word(anchor, tm):
    if isinstance(anchor, dict) and isinstance(anchor.get("w"), int) and not isinstance(anchor["w"], bool):
        return max(0, min(len(tm.words), anchor["w"]))
    try:
        t = tm.resolve(anchor)
    except (AnchorError, TypeError, KeyError):
        return None
    return bisect.bisect_left([w["s"] for w in tm.words], t)


def _phrase_words(phrase):
    import re
    return re.findall(r"[^\W_]+", phrase.casefold())


def _find_phrase(words, phrase, start, end):
    needle = _phrase_words(phrase)
    if not needle:
        return None
    for i in range(start, end):
        got = []
        for j in range(i, end):
            got.extend(_phrase_words(words[j]["w"]))
            if got == needle:
                return i
            if len(got) >= len(needle):
                break
    return None


def _shown_by(subject):
    where = subject.get("where")
    places = where if isinstance(where, list) else [where] if isinstance(where, dict) else []
    return [{"picture": p["asset"]} if "asset" in p else {"region": p["region"]}
            for p in places if isinstance(p, dict) and (isinstance(p.get("asset"), str) or isinstance(p.get("region"), str))]


def convert(storyboard, timing, picks, narration_hash, timing_hash, diagnostics=None):
    """Return (visual document, a copy of picks with inferred pool shows)."""
    notes = diagnostics if diagnostics is not None else []
    pool = copy.deepcopy(picks)
    cast = [{"id": s["id"], "kind": s["kind"], "name": s["name"], "also": s.get("also") or [],
             "strip": bool(s.get("strip")), "sub": s.get("sub") or "", "shown_by": _shown_by(s)}
            for s in picks.get("subjects", [])]
    for key, asset in pool.get("assets", {}).items():
        if key != pool.get("main_asset"):
            existing = list(asset.get("shows") or [])
            asset["shows"] = existing + [s["id"] for s in cast if {"picture": key} in s["shown_by"] and s["id"] not in existing]
    words = timing.get("words", [])
    tm = Timing(timing)
    shots = storyboard.get("shots", [])
    starts = [_word(s.get("start"), tm) for s in shots]
    moments = []
    main = picks.get("main_asset")
    for i, shot in enumerate(shots):
        note_start = len(notes)
        if is_program_shot(shot):
            continue
        w0 = starts[i]
        if w0 is None:
            notes.append(f"{shot.get('id')}: unresolved start")
            continue
        w1 = next((v for v in starts[i + 1:] if v is not None), len(words))
        if w0 >= w1 or w0 >= len(words):
            notes.append(f"{shot.get('id')}: no spoken words")
            continue
        beat = next((b for b in timing.get("beats", []) if b["w0"] <= w0 < b["w1"]), None)
        if not beat:
            notes.append(f"{shot.get('id')}: no narration line at word {w0}")
            continue
        slots = shot.get("slots") or {}
        image = slots.get("image") or {}
        key, region = image.get("asset"), image.get("region")
        if shot.get("technique") == "MAP-01":
            places = [(p.get("name") if isinstance(p, dict) else p) for p in (shot.get("params") or {}).get("places", [])]
            places = [p for p in places if isinstance(p, str) and p.strip()]
            if len(places) >= 2:
                show = {"map": {"places": places, **({"picture": key} if key and key != main else {})}, "else": {"whole": True}}
            else:
                show = {"whole": True}
                notes.append(f"{shot.get('id')}: map lacks two named places")
        elif key and key != main:
            show = {"picture": key}
        elif region:
            show = {"region": region}
        else:
            show = {"whole": True}
            notes.append(f"{shot.get('id')}: no named region in main-picture slot; frame is not necessarily whole")
        if shot.get("technique") == "LAY-01":
            pictures = [v.get("asset") for v in slots.values() if isinstance(v, dict) and v.get("asset")]
            if len(pictures) >= 2:
                show = {"pair": [{"picture": pictures[0]}, {"picture": pictures[1]}]}
            else:
                notes.append(f"{shot.get('id')}: pair lacks two named pictures")
        about_rows = ((picks.get("beats") or {}).get(beat["id"]) or {}).get("about") or []
        about = next((a["id"] for a in about_rows if a.get("id") in {c["id"] for c in cast} and _find_phrase(words, a.get("words", ""), w0, w1) is not None), None)
        if about is None:
            about = next((a["id"] for a in about_rows if any(c["id"] == a.get("id") and show in c["shown_by"] for c in cast)), None)
        say = []
        for overlay in shot.get("overlays") or []:
            typ, params = overlay.get("technique"), overlay.get("params") or {}
            at = _word(overlay.get("start"), tm)
            if typ == "X-ANN-01":
                text = str(params.get("text") or "").casefold().strip()
                who = next((c["id"] for c in cast if text and text in [x.casefold().strip() for x in [c["name"], *c["also"]]]), None)
                if who is not None and at is not None:
                    say.append({"intro": who, "word": at})
                else:
                    notes.append(f"{shot.get('id')}: cannot associate strip {text!r} with cast")
            elif typ in ("HI-01", "AN-01"):
                target = params.get("at")
                if isinstance(target, str) and at is not None:
                    say.append({"point": [{"region": target, "word": at}]})
                else:
                    notes.append(f"{shot.get('id')}: point has no named region or word")
            elif typ == "DOC-01":
                lit = params.get("lit") or []
                target = lit[0].get("ref") if lit and isinstance(lit[0], dict) else None
                text = params.get("reading") or params.get("original")
                if isinstance(target, str) and isinstance(text, str) and text:
                    say.append({"read": {"region": target, "text": text}})
                else:
                    notes.append(f"{shot.get('id')}: inscription lacks named region or text")
            elif typ == "KEY-01":
                labels = params.get("labels") or []
                converted = [{"region": x["ref"], "text": x["text"]} for x in labels if isinstance(x, dict) and isinstance(x.get("ref"), str) and isinstance(x.get("text"), str) and x["text"]]
                if len(converted) == len(labels) and len(converted) >= 3:
                    say.append({"labels": converted})
                else:
                    notes.append(f"{shot.get('id')}: labels cannot all be mapped to named regions")
            elif typ == "NUM-01":
                rows = params.get("rows") or []
                if not rows:
                    notes.append(f"{shot.get('id')}: number overlay has no rows")
                for row in rows:
                    if isinstance(row, dict) and row.get("value") is not None and str(row["value"]) and row.get("label"):
                        say.append({"number": {"text": str(row["value"]), "of": str(row["label"])}})
                    else:
                        notes.append(f"{shot.get('id')}: number row lacks a value or label")
            elif typ in ("MAP-01", "LAY-01"):
                notes.append(f"{shot.get('id')}: {typ} overlay has no corresponding INTENT in the contract")
        camera = (shot.get("params") or {}).get("camera") or []
        move = "hold"
        if len(camera) >= 2:
            first, last = camera[0], camera[-1]
            if first.get("zoom", 0) < last.get("zoom", 0):
                move = "push"
            elif first.get("zoom", 0) > last.get("zoom", 0):
                move = "pull"
            elif (first.get("cx"), first.get("cy")) != (last.get("cx"), last.get("cy")):
                move = "travel"
        moments.append({"id": f"m{len(moments) + 1:04d}", "line": beat["id"], "w0": w0, "w1": w1,
                        "about": about, "show": show, "move": move, "from": "previous", "say": say,
                        "why": "Có chi tiết chưa chuyển được; cần kiểm tra." if len(notes) > note_start else "Cảnh theo bản dựng hiện tại."})
    return {"schema": "bti.visual/1", "made_from": {"narration": narration_hash, "timing": timing_hash},
            "cast": cast, "wanted": [], "moments": moments}, pool


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()


def issue_counts(document, issues, rule):
    """Count distinct affected moments and findings, including cast-level findings."""
    selected = [row for row in issues if row["rule"] == rule]
    moments = {row["moment"] for row in selected if row.get("moment") is not None}
    subjects = {row["subject"] for row in selected if row.get("subject") is not None}
    for moment in document["moments"]:
        if moment.get("about") in subjects or any(intent.get("intro") in subjects for intent in moment.get("say", [])):
            moments.add(moment["id"])
    return len(moments), len(selected)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--pool-out", type=Path, help="write a separate picks copy with inferred shows")
    args = parser.parse_args(argv)
    project = args.project
    timing_path = project / "timing.json"
    narration_path = project / "script" / "narration.json"
    if not narration_path.is_file():
        narration_path = project / "narration.json"
    notes = []
    visual, pool = convert(_read(project / "storyboard.json"), _read(timing_path), _read(project / "picks.json"),
                           _hash(narration_path), _hash(timing_path), notes)
    out = args.out or project / "visual.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(visual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.pool_out:
        args.pool_out.parent.mkdir(parents=True, exist_ok=True)
        args.pool_out.write_text(json.dumps(pool, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    issues = validate(visual, _read(timing_path), pool)
    counts = Counter(i["rule"] for i in issues)
    covered = set()
    for moment in visual["moments"]:
        covered.update(range(moment["w0"], moment["w1"]))
    total = len(_read(timing_path).get("words", []))
    print(f"moments={len(visual['moments'])} cast={len(visual['cast'])} words={len(covered)}/{total} ({len(covered) / total if total else 0:.1%})")
    for n in range(1, 13):
        rule = f"V{n}"
        rows = [i for i in issues if i["rule"] == rule]
        affected, findings = issue_counts(visual, issues, rule)
        print(f"{rule}: {affected} moments, {findings} findings")
        for row in rows[:2]:
            print(f"  {row['message']}")
    print(f"shape: {counts['shape']}; conversion notes: {len(notes)}")
    for note in notes[:20]:
        print("  " + note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
