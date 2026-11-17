"""The draft spec `bti.draft/1`: what the agent writes, one file per chapter (`out/c03.json`).

    {"schema": "bti.draft/1", "chapter": "c03", "shots": [
      {"beat": "b0031", "start_word": 512, "technique": "CAM-05", "intent": "point_at",
       "slots": {"image": {"asset": "A", "region": "MIRROR"}}, "params": {},
       "overlays": [{"technique": "HI-01", "start_word": 518, "end_word": 524, "slots": {}, "params": {}}],
       "note": "the mirror is named here"}]}

This module checks the SHAPE only (types, unknown keys). Whether a beat exists, whether a technique can be drawn, whether the
pictures tile: that is `compile.py`. Every problem names the chapter and the shot number (1 = the first shot of the file) and says
what to write instead, because the reader of these messages is a model.
"""
from __future__ import annotations

import json
from pathlib import Path

from .inputs import SPEC_SCHEMA, DraftError, _num

# `id`, `locked`, `in_scope`, `start_s`, `end_s` appear in inputs/current/ (edit mode); the compiler ignores them except `id`
SHOT_KEYS = ("beat", "start_word", "technique", "intent", "slots", "params", "overlays", "note", "off", "transition_in",
             "id", "locked", "in_scope", "start_s", "end_s")
OVERLAY_KEYS = ("technique", "start_word", "end_word", "dur", "off", "intent", "slots", "params", "note", "id", "locked")
REGION_KEYS = ("x", "y", "rx", "ry", "label")


def problem(code: str, chapter, shot, message: str, *, overlay=None, field: str | None = None, level: str = "error") -> dict:
    """One issue in the spec's own terms. `shot` and `overlay` count from 1."""
    where = "chapter %s" % chapter if chapter else "spec"
    if shot is not None:
        where += ", shot %d" % shot
    if overlay is not None:
        where += ", overlay %d" % overlay
    return {"level": level, "code": code, "chapter": chapter, "shot": shot, "overlay": overlay, "field": field,
            "message": "%s: %s" % (where, message)}


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _slots_problem(v) -> str | None:
    if v is None:
        return None
    if not isinstance(v, dict):
        return 'slots must be an object like {"image": {"asset": "A", "region": "MIRROR"}}'
    for k, s in v.items():
        if not isinstance(s, dict) or not isinstance(s.get("asset"), str) or not s.get("asset"):
            return 'slot %r must be an object with an "asset" key, like {"asset": "A"}' % k
        extra = sorted(set(s) - {"asset", "region"})
        if extra:
            return "slot %r has unknown key(s) %s (allowed: asset, region)" % (k, ", ".join(extra))
        if s.get("region") is not None and not isinstance(s["region"], str):
            return "slot %r: region must be a region NAME (text), not coordinates" % k
    return None


def shape_problems(spec, expected_chapter: str | None = None) -> tuple[dict, list[dict]]:
    """(clean spec, problems). `clean` keeps only the shots and overlays whose shape is usable; a dropped one has an error."""
    chap = expected_chapter
    if not isinstance(spec, dict):
        return {"shots": []}, [problem("spec_not_object", chap, None, "the file must be a JSON object with schema, chapter and shots")]
    chap = spec.get("chapter") if isinstance(spec.get("chapter"), str) else expected_chapter
    out: list[dict] = []
    if spec.get("schema") != SPEC_SCHEMA:
        out.append(problem("spec_schema", chap, None, 'schema must be "%s"' % SPEC_SCHEMA, field="schema", level="warn"))
    if expected_chapter and spec.get("chapter") != expected_chapter:
        out.append(problem("spec_chapter", expected_chapter, None,
                           'the file says chapter %r but it is out/%s.json: write "chapter": "%s"' % (spec.get("chapter"), expected_chapter, expected_chapter),
                           field="chapter", level="warn"))
    extra = sorted(set(spec) - {"schema", "chapter", "shots", "note"})
    if extra:
        out.append(problem("spec_unknown_key", chap, None, "unknown top-level key(s): %s (allowed: schema, chapter, shots)" % ", ".join(extra), level="warn"))
    shots = spec.get("shots")
    if not isinstance(shots, list) or not shots:
        out.append(problem("spec_no_shots", chap, None, '"shots" must be a non-empty list'))
        return {"shots": []}, out
    clean: list[dict] = []
    for i, s in enumerate(shots, 1):
        sp = lambda code, msg, **kw: out.append(problem(code, chap, i, msg, **kw))     # noqa: E731
        if not isinstance(s, dict):
            sp("shot_not_object", "a shot must be an object")
            continue
        bad = sorted(set(s) - set(SHOT_KEYS))
        if bad:
            sp("shot_unknown_key", "unknown key(s) %s (allowed: %s)" % (", ".join(bad), ", ".join(SHOT_KEYS)), level="warn")
        if not isinstance(s.get("beat"), str) or not s.get("beat"):
            sp("shot_beat", 'every shot needs "beat": the id of the beat it belongs to, like "b0031"', field="beat")
            continue
        if not _int(s.get("start_word")) or s["start_word"] < 0:
            sp("shot_start_word", '"start_word" must be a whole number >= 0: the index of the first word of the shot (column 1 of inputs/words.tsv)', field="start_word")
            continue
        if not isinstance(s.get("technique"), str) or not s.get("technique"):
            sp("shot_technique", '"technique" must be a technique id like "CAM-05"', field="technique")
            continue
        m = _slots_problem(s.get("slots"))
        if m:
            sp("shot_slots", m, field="slots")
            continue
        if s.get("params") is not None and not isinstance(s["params"], dict):
            sp("shot_params", '"params" must be an object (use {} to keep every default)', field="params")
            continue
        if s.get("intent") is not None and not isinstance(s["intent"], str):
            sp("shot_intent", '"intent" must be text', field="intent")
            continue
        if s.get("note") is not None and not isinstance(s["note"], str):
            sp("shot_note", '"note" must be text', field="note")
            continue
        if s.get("off") is not None and not (_num(s["off"]) and -60 <= s["off"] <= 60):
            sp("shot_off", '"off" must be a number of seconds between -60 and 60', field="off")
            continue
        tr = s.get("transition_in")
        if tr is not None and not (isinstance(tr, dict) and isinstance(tr.get("technique"), str) and _num(tr.get("dur", 1.0))):
            sp("shot_transition", '"transition_in" must be null or {"technique": "TR-01", "dur": 1.0, "params": {}}', field="transition_in")
            continue
        ovs_in = s.get("overlays")
        if ovs_in is not None and not isinstance(ovs_in, list):
            sp("shot_overlays", '"overlays" must be a list', field="overlays")
            continue
        ovs: list[dict] = []
        for j, o in enumerate(ovs_in or [], 1):
            op = lambda code, msg, **kw: out.append(problem(code, chap, i, msg, overlay=j, **kw))     # noqa: E731
            if not isinstance(o, dict):
                op("overlay_not_object", "an overlay must be an object")
                continue
            ob = sorted(set(o) - set(OVERLAY_KEYS))
            if ob:
                op("overlay_unknown_key", "unknown key(s) %s (allowed: %s)" % (", ".join(ob), ", ".join(OVERLAY_KEYS)), level="warn")
            if not isinstance(o.get("technique"), str) or not o.get("technique"):
                op("overlay_technique", '"technique" must be an overlay technique id like "HI-01"', field="technique")
                continue
            if not _int(o.get("start_word")) or o["start_word"] < 0:
                op("overlay_start_word", '"start_word" must be a whole number >= 0 (a word index inside the shot)', field="start_word")
                continue
            if o.get("end_word") is not None and not (_int(o["end_word"]) and o["end_word"] >= o["start_word"]):
                op("overlay_end_word", '"end_word" must be a whole word index >= start_word (the overlay lasts until that word is spoken)', field="end_word")
                continue
            if o.get("dur") is not None and not (_num(o["dur"]) and o["dur"] > 0):
                op("overlay_dur", '"dur" must be a number of seconds > 0', field="dur")
                continue
            if o.get("off") is not None and not (_num(o["off"]) and -60 <= o["off"] <= 60):
                op("overlay_off", '"off" must be a number of seconds between -60 and 60', field="off")
                continue
            m = _slots_problem(o.get("slots"))
            if m:
                op("overlay_slots", m, field="slots")
                continue
            if o.get("params") is not None and not isinstance(o["params"], dict):
                op("overlay_params", '"params" must be an object', field="params")
                continue
            ovs.append(o)
        clean.append(dict(s, overlays=ovs, _n=i))
    return {"schema": SPEC_SCHEMA, "chapter": chap, "shots": clean}, out


def load_spec(path: Path | str, expected_chapter: str | None = None) -> tuple[dict, list[dict]]:
    """Read one chapter file -> (clean spec, problems). A file that cannot be read gives an empty spec and one error."""
    path = Path(path)
    try:
        if path.stat().st_size > 2_000_000:
            return {"shots": []}, [problem("spec_too_big", expected_chapter, None, "%s is over 2 MB; write a shorter shot list" % path.name)]
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"shots": []}, [problem("spec_missing", expected_chapter, None, "out/%s is missing: write one file per chapter" % path.name)]
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return {"shots": []}, [problem("spec_json", expected_chapter, None, "out/%s is not valid JSON (%s)" % (path.name, str(e)[:100]))]
    return shape_problems(data, expected_chapter)


def regions_problems(data, assets: dict) -> tuple[dict, list[dict]]:
    """`out/regions.json`: {"<asset key>": {"<NAME>": {"x", "y", "rx", "ry", "label"}}} in SOURCE pixels. -> (clean, problems)."""
    out: list[dict] = []
    clean: dict = {}
    if data is None:
        return clean, out
    if not isinstance(data, dict):
        return clean, [problem("regions_shape", None, None, 'out/regions.json must be {"<asset key>": {"<NAME>": {"x":..,"y":..,"rx":..,"ry":..,"label":".."}}}')]
    for key, regs in data.items():
        a = assets.get(key)
        if not isinstance(a, dict) or not isinstance(regs, dict):
            out.append(problem("regions_asset", None, None, "regions.json: %r is not an asset key, or its value is not an object" % key))
            continue
        w, h = a.get("width"), a.get("height")
        for name, r in regs.items():
            if not (isinstance(name, str) and name and name.replace("_", "").isalnum()):
                out.append(problem("region_name", None, None, "regions.json: region name %r must be letters, digits and _ only (like MIRROR)" % (name,)))
                continue
            if not (isinstance(r, dict) and _num(r.get("x")) and _num(r.get("y"))):
                out.append(problem("region_xy", None, None, "regions.json: %s.%s needs numeric x and y (source pixels)" % (key, name)))
                continue
            if _num(w) and _num(h) and not (0 <= r["x"] <= w and 0 <= r["y"] <= h):
                out.append(problem("region_outside", None, None, "regions.json: %s.%s centre (%s, %s) is outside the image (%sx%s source pixels); coordinates are in SOURCE pixels, not the downscaled copy" % (key, name, r["x"], r["y"], w, h)))
                continue
            reg = {"x": r["x"], "y": r["y"]}
            for k in ("rx", "ry"):
                if r.get(k) is not None:
                    if not (_num(r[k]) and r[k] > 0):
                        out.append(problem("region_radius", None, None, "regions.json: %s.%s %s must be a number > 0" % (key, name, k)))
                        reg = None
                        break
                    reg[k] = r[k]
            if reg is None:
                continue
            reg["label"] = str(r.get("label") or name)
            clean.setdefault(key, {})[name] = reg
    return clean, out


def raise_if(problems: list[dict]) -> None:
    errs = [p for p in problems if p["level"] == "error"]
    if errs:
        raise DraftError("spec_invalid", "; ".join(p["message"] for p in errs[:5]))
