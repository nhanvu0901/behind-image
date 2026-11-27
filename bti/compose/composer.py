"""Turn resolved visual moments into storyboard documents."""
from __future__ import annotations

from copy import deepcopy
from bisect import bisect_right
import re

from bti import identity
from bti.draft.camera import build_main_camera
from bti.draft.inputs import canon_hash, normalize_timing
from bti.draft import zones, assetmerge
from bti.engine import registry
from bti.engine import techniques  # noqa: F401 - registers renderers
from bti.engine.viewchecks import region_point_box, box_inside_frame, fit_frame_to_box
from bti.media.contentbox import box_of
from bti.engine.timing import Timing
from bti.visual.helpers import sentence_for_word

from .schedule import schedule


def _mark_is_person(name, cast, regions):
    """Protect named people and targets mostly overlapping a head, face or bust."""
    target = region_point_box(regions.get(name))
    for member in cast:
        if member.get("kind") != "person":
            continue
        for where in member.get("shown_by", []):
            person_region = where.get("region")
            if name == person_region:
                return True
            if not person_region or not re.search(r"(?:^|_)(?:head|face|bust)(?:_|$)", person_region, re.I):
                continue
            outer = region_point_box(regions.get(person_region))
            if target and outer:
                area = (target[2] - target[0]) * (target[3] - target[1])
                overlap = max(0, min(target[2], outer[2]) - max(target[0], outer[0])) * max(0, min(target[3], outer[3]) - max(target[1], outer[1]))
                if area > 0 and overlap > area / 2:
                    return True
    return False


def compose(visual, timing, picks, style, current=None):
    """Compose a storyboard and its notes from in-memory documents."""
    style_id = style.get("id", "gae") if isinstance(style, dict) else style
    bundle = registry.load_bundle(style_id)
    config = dict(bundle.style.get("compose", {}))
    if isinstance(style, dict):
        config.update(style.get("compose", {}))
    words = timing["words"]
    wanted = {w["id"]: w for w in visual.get("wanted", [])}
    cast = {c["id"]: c for c in visual.get("cast", [])}
    main = picks["main_asset"]
    assets = assetmerge.merged_assets(picks["assets"], (current or {}).get("assets"), edit=False)
    for asset in assets.values():
        asset.setdefault("kind", "image")
    entries = []
    initial_notes = []
    for m in visual["moments"]:
        show = deepcopy(m["show"])
        if "want" in show:
            want = wanted.get(show["want"], {})
            if not want:
                initial_notes.append({"moment": m["id"], "rule": "C1", "what": "unknown wanted picture; used its recorded fallback"})
            show = {"picture": want["picture"]} if want.get("status") == "found" and want.get("picture") else show["else"]
        if "map" in show:
            map_key = show["map"].get("picture")
            record = picks["assets"].get(map_key, {})
            places = record.get("places") or (record.get("map") or {}).get("places") or []
            credit = record.get("credit") or {}
            source_url = credit.get("source_url", "") if credit.get("source") == "osm" else ""
            found = re.search(r"#map=\d{1,2}/(-?\d+(?:\.\d+)?)/(-?\d+(?:\.\d+)?)$", source_url)
            if not places and found and record.get("title"):
                lat, lon = map(float, found.groups())
                if abs(lat) <= 90 and abs(lon) <= 180:
                    places = [{"id": "map_center", "name": record["title"], "lonlat": [lon, lat], "at": 0}]
                    initial_notes.append({"moment": m["id"], "rule": "C7", "what": "map record contains only a centre; other place coordinates were not invented"})
            if not places:
                fallback = show.get("else")
                if not fallback:
                    # Legacy conversions did not always record an else; reuse an
                    # actual view in the script rather than inventing a picture.
                    fallback = next((e["show"] for e in reversed(entries) if "region" in e["show"] or "whole" in e["show"]), None)
                    if not fallback:
                        fallback = next((other["show"] for other in visual["moments"] if "region" in other["show"] or "whole" in other["show"]), None)
                    if not fallback and map_key in assets:
                        fallback = {"picture": map_key}
                    if not fallback:
                        raise ValueError("unresolved legacy map has no recorded fallback or reusable view")
                initial_notes.append({"moment": m["id"], "rule": "C7", "what": "map has no resolved place coordinates; used a recorded fallback"})
                show = deepcopy(fallback)
            else:
                show["map"]["resolved_places"] = deepcopy(places)
        sentence_start, sentence_end = sentence_for_word(timing, m["w0"])
        intro_end = 0.0
        for intent in m.get("say", []):
            if "intro" in intent and cast.get(intent["intro"], {}).get("strip"):
                subject = cast[intent["intro"]]
                words_per_line = max(len(subject.get("name", "").split()), len(subject.get("sub", "").split()))
                required = min(config["strip_max_s"], config["strip_line_min_s"] + config["strip_extra_word_s"] * max(0, words_per_line - config["strip_base_words"]))
                intro_end = max(intro_end, words[intent["word"]]["s"] + required)
        entries.append({**deepcopy(m), "show": show, "start": words[m["w0"]]["s"],
                        "sentence_start": words[sentence_start]["s"], "sentence_end": words[sentence_end - 1]["e"], "intro_end": intro_end,
                        "min_duration": config["device_min_s"] if any("read" in it or "number" in it for it in m.get("say", [])) else config["shot_min_s"]})
    opening = zones.opening_span(timing.get("chapters") or [], words)
    if entries:
        entries[0]["start"] = opening["dur"] if opening else 0.0
    normalized = normalize_timing(timing)
    cfg = identity.read(bundle.style)
    placement = zones.place(normalized["chapters"], words, zones.brand_length(cfg, cfg.default_style))
    program_spans = sorted((span["start"], span["start"] + span["dur"])
                           for chapter in placement["chapters"] for span in (chapter.get("title"), chapter.get("card")) if span)
    for item in entries:
        for left, right in program_spans:
            if left <= item["start"] < right:
                item["start"] = right
                initial_notes.append({"moment": item["id"], "rule": "C1", "what": "start moved after a chapter mark"})
    barriers = [left for left, _ in program_spans]
    groups = {}
    for item in entries:
        groups.setdefault(bisect_right(barriers, item["start"]), []).append(item)
    entries, notes = [], []
    for group_index, group in groups.items():
        boundary = barriers[group_index] if group_index < len(barriers) else timing["duration"]
        scheduled, segment_notes = schedule(group, boundary, floor=config["shot_min_s"],
                                            borrowed_floor=config["borrowed_min_s"])
        if scheduled:
            scheduled[-1]["_segment_end"] = boundary
        entries.extend(scheduled)
        notes.extend(segment_notes)
    notes[:0] = initial_notes
    def members(item):
        stack = [item]
        while stack:
            member = stack.pop()
            yield member
            stack.extend(reversed(member.get("joined", [])))

    def safe_sub(subject, moment_id):
        sub = subject.get("sub", "")
        aliases = [subject.get("name", ""), *subject.get("also", [])]
        if len(sub.split()) > 6 or any(a and re.search(r"(?<!\w)" + re.escape(a) + r"(?!\w)", sub, re.IGNORECASE) for a in aliases):
            notes.append({"moment": moment_id, "rule": "C4", "what": "subtitle omitted because it repeats the name or exceeds six words"})
            return ""
        return sub

    tm = Timing(timing)
    cast = {c["id"]: c for c in visual.get("cast", [])}
    shots = []
    prev, prev_region = None, None
    ring_counts = {}
    for i, moment in enumerate(entries):
        start = moment["start"]
        end = min(entries[i + 1]["start"] if i + 1 < len(entries) else timing["duration"],
                  moment.get("_segment_end", timing["duration"]))
        show = moment["show"]
        region = show.get("region")
        key = show.get("picture", main)
        if "map" in show:
            tid, slots = "MAP-01", {}
        elif "pair" in show:
            tid = "LAY-01"
            slots = {"left": {"asset": show["pair"][0]["picture"]},
                     "right": {"asset": show["pair"][1]["picture"]}}
        else:
            tid = "X-LAY-01" if "picture" in show else {"hold": "STATIC-01", "push": "CAM-01", "travel": "CAM-05", "pull": "CAM-03"}.get(moment.get("move"), "STATIC-01")
            slots = {"image": {"asset": key}}
            if region:
                slots["image"]["region"] = region
        asset = assets[key]
        context = {"asset": {"key": key, "w": asset.get("width"), "h": asset.get("height"), "regions": asset.get("regions", {})}}
        if tid == "LAY-01":
            right = assets[slots["right"]["asset"]]
            context["asset"] = {"w": assets[slots["left"]["asset"]].get("width"), "h": assets[slots["left"]["asset"]].get("height")}
            context["asset_right"] = {"w": right.get("width"), "h": right.get("height")}
        entry = registry.RENDERERS.get(tid)
        params = deepcopy(entry[0].default_params(tid, bundle.spec(tid), context, bundle) if entry else bundle.param_defaults(tid))
        if tid == "LAY-01":
            params["entrance"] = "together"
            for side in ("left", "right"):
                picture = slots[side]["asset"]
                text, sub = picks["assets"].get(picture, {}).get("caption", ""), ""
                for item in members(moment):
                    for intent in item.get("say", []):
                        subject = cast.get(intent.get("intro"), {})
                        eligible = subject.get("kind") in ("person", "place", "work") or (subject.get("kind") == "thing" and subject.get("term") is True)
                        if subject.get("strip") and eligible and {"picture": picture} in subject.get("shown_by", []):
                            text, sub = subject["name"], safe_sub(subject, item["id"])
                params["caption_" + side], params["caption_" + side + "_sub"] = text, sub
                if not text:
                    notes.append({"moment": moment["id"], "rule": "C5", "what": "pair picture has no caption"})
        if tid == "MAP-01":
            params.update(places=show["map"]["resolved_places"], route=[], region_iso=[], region_label="", sea_names=False)
        if key == main and tid not in ("LAY-01", "MAP-01"):
            camera_asset, camera_region, camera_from = asset, region, moment.get("from")
            point_names = [point["region"] for item in list(members(moment))
                           for intent in item.get("say", []) for point in intent.get("point", [])]
            regions = asset.get("regions", {})
            if len(point_names) > 1 and all(name in regions for name in point_names):
                boxes = [regions[name] for name in point_names]
                x0 = min(r["x"] - r.get("rx", 0) for r in boxes)
                x1 = max(r["x"] + r.get("rx", 0) for r in boxes)
                y0 = min(r["y"] - r.get("ry", 0) for r in boxes)
                y1 = max(r["y"] + r.get("ry", 0) for r in boxes)
                camera_asset = deepcopy(asset)
                camera_asset.setdefault("regions", {})["_compose_union"] = {"x": (x0+x1)/2, "y": (y0+y1)/2,
                                                                             "rx": max(1, (x1-x0)/2), "ry": max(1, (y1-y0)/2)}
                camera_region, camera_from = "_compose_union", None
                notes.append({"moment": moment["id"], "rule": "C3", "what": "framed the union of listed point targets"})
            params["camera"] = build_main_camera(tid, camera_region, camera_from, camera_asset, None, prev, start, end, tm=tm, prev_region=prev_region)
            if region and asset.get("width") and asset.get("height"):
                w, h = float(asset["width"]), float(asset["height"])
                box = box_of(asset) or (0, 0, w, h)
                fill_zoom = max(1920 / (box[2] - box[0]), 1080 / (box[3] - box[1]))
                raised = False
                for frame in params["camera"]:
                    if frame["zoom"] < fill_zoom:
                        target = camera_asset.get("regions", {}).get(camera_region, {})
                        cx, cy, zoom = fit_frame_to_box(target.get("x", frame["cx"]), target.get("y", frame["cy"]), fill_zoom, w, h, box, z_cap=fill_zoom)
                        frame.update(cx=cx, cy=cy, zoom=zoom)
                        raised = True
                if raised:
                    notes.append({"moment": moment["id"], "rule": "C3", "what": "raised region zoom to fill the frame; a small source may look softer"})
            last = params["camera"][-1]
            prev = (last["cx"], last["cy"], last["zoom"])
            prev_region = region
        else:
            prev, prev_region = None, None
        shot = {"id": "s_" + moment["id"], "moment": moment["id"], "start": {"t": start},
                "technique": tid, "slots": slots, "params": params, "intent": "point_at", "transition_in": None,
                "overlays": [], "locked": False, "source": "agent", "note": ""}
        def overlay(tid, params, at, duration):
            spec = bundle.spec(tid)
            min_duration = (spec.get("timing") or {}).get("min_s") or 0
            if duration + 1e-6 < min_duration:
                notes.append({"moment": moment["id"], "rule": "C8", "what": tid + " omitted because its minimum duration does not fit"})
                return False
            values = deepcopy(bundle.param_defaults(tid))
            values.update(params)
            if tid in ("X-ANN-01", "X-ANN-02"):
                values.update(pop_in_s=config["strip_fade_s"], fade_out_s=config["strip_fade_s"])
            shot["overlays"].append({"id": "o%d" % (len(shot["overlays"]) + 1),
                                     "technique": tid, "intent": spec["intents"][0],
                                     "slots": {}, "params": values, "start": {"t": at},
                                     "dur": round(duration, 3), "locked": False, "source": "agent", "note": ""})
            return True

        for item in list(members(moment)):
            intents = list(item.get("say", []))
            subject = cast.get(item.get("about"), {})
            item_region = item.get("show", {}).get("region")
            explicit = {p.get("region") for intent in intents for p in intent.get("point", [])}
            if subject.get("kind") in ("thing", "text") and item_region and item_region not in explicit:
                tokens = [re.findall(r"\w+", words[i]["w"].casefold()) for i in range(item["w0"], item["w1"])]
                tokens = [part[0] if part else "" for part in tokens]
                matches = []
                for alias in [subject.get("name", ""), *subject.get("also", [])]:
                    parts = re.findall(r"\w+", alias.casefold())
                    if parts:
                        matches.extend(item["w0"] + j for j in range(len(tokens) - len(parts) + 1) if tokens[j:j + len(parts)] == parts)
                intents.append({"point": [{"region": item_region, "word": min(matches) if matches else item["w0"]}]})
            for intent in intents:
                if "intro" in intent:
                    subject = cast.get(intent["intro"])
                    if not subject:
                        notes.append({"moment": item["id"], "rule": "C4", "what": "intro omitted because its cast member is missing"})
                        continue
                    spoken_at = words[intent["word"]]["s"]
                    if spoken_at < start - 1e-6:
                        notes.append({"moment": item["id"], "rule": "C4", "what": "intro omitted because its spoken word precedes the shot"})
                        continue
                    at = spoken_at
                    text, sub = subject["name"], safe_sub(subject, item["id"])
                    required = min(config["strip_max_s"], config["strip_line_min_s"] + config["strip_extra_word_s"] * max(0, max(len(text.split()), len(sub.split())) - config["strip_base_words"]))
                    duration = end - at if key != main else min(end - at, max(config["strip_main_s"], required))
                    shown = subject.get("shown_by", [])
                    matches = show in shown or ("pair" in show and any(part in shown for part in show["pair"]))
                    if not matches and key == main and tid not in ("MAP-01", "LAY-01"):
                        last = shot["params"]["camera"][-1]
                        for where in shown:
                            box = region_point_box(assets[main].get("regions", {}).get(where.get("region")))
                            if box and box_inside_frame(box, last["cx"], last["cy"], last["zoom"])[0]:
                                matches = True
                                break
                    eligible = subject.get("strip") and (subject.get("kind") not in ("idea", "text", "thing") or (subject.get("kind") == "thing" and subject.get("term") is True))
                    if tid == "LAY-01" and matches and eligible:
                        continue
                    if eligible and matches and duration >= required:
                        overlay("X-ANN-01", {"text": text, "sub": sub}, at, duration)
                    else:
                        notes.append({"moment": item["id"], "rule": "C4", "what": "intro could not fit or its cast member has no strip"})
                elif "point" in intent:
                    points = intent["point"]
                    for point in points:
                        name = point["region"]
                        reg = assets[main].get("regions", {}).get(name, {})
                        keys = shot["params"].get("camera", []) if key == main else []
                        rx, ry = reg.get("rx", 0), reg.get("ry", 0)
                        on_person = _mark_is_person(name, list(cast.values()), assets[main].get("regions", {}))
                        own_thing = (name == item.get("show", {}).get("region") and cast.get(item.get("about"), {}).get("kind") in ("thing", "text"))
                        small = bool(keys and rx and ry and not on_person)
                        for frame in keys[-1:]:
                            z = frame["zoom"]
                            width, height = 2 * rx * z / 1920, 2 * ry * z / 1080
                            x, y = (reg.get("x", 0) - frame["cx"]) * z, (reg.get("y", 0) - frame["cy"]) * z
                            small = (small and (height <= config["ring_shown_height_max"] if own_thing else
                                     width < config["mark_side_max"] and height < config["mark_height_max"] and width * height < config["mark_area_max"])
                                     and abs(x) + rx * z <= 960 and abs(y) + ry * z <= 540)
                        at = words[point["word"]]["s"]
                        if not small or at < start - 1e-6 or end - at < 0.3:
                            notes.append({"moment": item["id"], "rule": "C6", "what": "mark " + name + " omitted: person, large, outside frame, or too late"})
                            continue
                        if ring_counts.get(name, 0) >= config["ring_region_max"]:
                            continue
                        z = max(k["zoom"] for k in keys)
                        radius = max(5, config["ring_min_frame_width"] * 1920 / z, 1.15 * max(rx, ry))
                        if own_thing:
                            radius = min(radius, config["ring_max_frame_height"] * 1080 / z)
                        if radius * z > config["ring_max_frame_height"] * 1080 + 1e-6:
                            notes.append({"moment": item["id"], "rule": "C6", "what": "ring omitted: target exceeds maximum radius"})
                            continue
                        _, sentence_end = sentence_for_word(timing, point["word"])
                        ring_end = min(end, at + config["ring_duration_s"], words[sentence_end - 1]["e"])
                        defaults = bundle.param_defaults("AN-01")
                        hold = max(0, min(20, ring_end - at - defaults["draw_s"] - defaults["fade_s"]))
                        if overlay("AN-01", {"at": name, "radius": radius, "hold_s": hold}, at, ring_end - at):
                            ring_counts[name] = ring_counts.get(name, 0) + 1
                elif "read" in intent and key == main and tid not in ("LAY-01", "MAP-01"):
                    data = intent["read"]
                    if data["region"] not in assets[main].get("regions", {}):
                        notes.append({"moment": item["id"], "rule": "C7", "what": "reading omitted: region " + data["region"] + " is missing"})
                        continue
                    overlay("DOC-01", {"lit": [{"ref": data["region"], "box": "", "at": 0, "hold_s": 0}],
                                       "reading": data["text"], "original": "", "reading_at": 0}, start, end - start)
                elif "labels" in intent and key == main and tid not in ("LAY-01", "MAP-01"):
                    labels = []
                    for label in intent["labels"]:
                        if len(label["text"]) > 60 or len(labels) >= 12:
                            notes.append({"moment": item["id"], "rule": "C7", "what": "label omitted: text or label count exceeds the engine limit"})
                        elif label["region"] not in assets[main].get("regions", {}):
                            notes.append({"moment": item["id"], "rule": "C7", "what": "label omitted: region " + label["region"] + " is missing"})
                        else:
                            labels.append({"text": label["text"], "ref": label["region"], "side": "auto", "at": 0, "style": "italic"})
                    if labels:
                        overlay("KEY-01", {"labels": labels}, start, end - start)
                elif "number" in intent:
                    data = intent["number"]
                    if len(data["text"]) > 16 or len(data["of"]) > 60:
                        notes.append({"moment": item["id"], "rule": "C7", "what": "number omitted: text exceeds the engine limit"})
                        continue
                    overlay("NUM-01", {"rows": [{"value": data["text"], "label": data["of"], "units": "", "count": 0, "at": 0}],
                                       "caption": "", "source": ""}, start, end - start)
                else:
                    notes.append({"moment": item["id"], "rule": "C7", "what": "intent omitted because this picture cannot show it"})
        if key != main and tid == "X-LAY-01" and not any(o["technique"] == "X-ANN-01" for o in shot["overlays"]):
            caption = picks["assets"].get(key, {}).get("caption")
            if caption:
                overlay("X-ANN-02", {"title": caption, "artist_year": ""}, start, end - start)
            else:
                notes.append({"moment": moment["id"], "rule": "C5", "what": "picture has no caption"})
        shots.append(shot)
    for chapter, placed in zip(normalized["chapters"], placement["chapters"]):
        for role, tid in (("title", "X-CARD-02"), ("card", "X-CARD-01")):
            span = placed.get(role)
            if not span:
                continue
            entry = registry.RENDERERS.get(tid)
            ctx = {"title": chapter["name"], "asset": {"key": main, "w": assets[main].get("width"), "h": assets[main].get("height"), "regions": assets[main].get("regions", {})}}
            params = deepcopy(entry[0].default_params(tid, bundle.spec(tid), ctx, bundle) if entry else bundle.param_defaults(tid))
            slots = {"background": {"asset": main}} if role == "title" else {}
            if role == "title":
                params.update(title=str((current or {}).get("title") or assets[main].get("title") or ""),
                              artist=str(assets[main].get("artist") or ""), year=str(assets[main].get("year") or ""))
            shots.append({"id": "program_%s_%s" % (chapter["id"], role), "start": {"t": span["start"]},
                          "technique": tid, "slots": slots, "params": params, "intent": "structure", "transition_in": None,
                          "overlays": [], "locked": False, "source": "agent", "note": "chapter " + role})
    shots.sort(key=lambda s: tm.resolve(s["start"]))
    for i, shot in enumerate(shots[:-1]):
        bound = tm.resolve(shots[i + 1]["start"])
        kept = []
        for ov in shot.get("overlays", []):
            at = tm.resolve(ov["start"])
            if at >= bound:
                notes.append({"moment": shot.get("moment", "program"), "rule": "C8", "what": "overlay removed at chapter boundary"})
            else:
                ov["dur"] = min(ov["dur"], max(0.0, bound - at))
                required = ((bundle.spec(ov["technique"]) or {}).get("timing") or {}).get("min_s") or 0
                if ov["dur"] + 1e-6 < required:
                    notes.append({"moment": shot.get("moment", "program"), "rule": "C8", "what": ov["technique"] + " removed at chapter boundary because it no longer fits"})
                else:
                    kept.append(ov)
        shot["overlays"] = kept
    if opening:
        shot = zones.opening_shot(main, assets[main], {"w": 1920, "h": 1080},
                                  identity.read(bundle.style).fit_pct, bundle.param_defaults("CAM-01"))
        shots.insert(0, shot)
    if isinstance(current, dict):
        old = current.get("shots") or []
        spans = []
        for index, previous in enumerate(old):
            if previous.get("locked"):
                left = tm.resolve(previous["start"])
                right = tm.resolve(old[index + 1]["start"]) if index + 1 < len(old) else tm.resolve(current.get("end", {"t": timing["duration"]}))
                spans.append((left, right, deepcopy(previous)))
        kept = []
        for shot in shots:
            at = tm.resolve(shot["start"])
            occupied = next(((a, b) for a, b, _ in spans if a <= at < b), None)
            if occupied:
                notes.append({"moment": shot.get("moment", "opening"), "rule": "C8", "what": "covered by an owner-locked shot"})
            else:
                kept.append(shot)
        locked_ids = {s.get("id") for _, _, s in spans}
        for shot in kept:
            if shot.get("id") in locked_ids:
                shot["id"] += "_new"
                notes.append({"moment": shot.get("moment", "program"), "rule": "C8", "what": "assigned a new id because the old id belongs to a locked shot"})
        shots = sorted(kept + [s for _, _, s in spans], key=lambda s: tm.resolve(s["start"]))
        i = 1
        while i < len(shots):
            left, right = shots[i - 1], shots[i]
            if (right.get("locked") and not left.get("locked") and i > 1
                    and tm.resolve(right["start"]) - tm.resolve(left["start"]) < config["shot_min_s"]):
                notes.append({"moment": left.get("moment", "program"), "rule": "C8", "what": "joined into previous view before a locked shot"})
                del shots[i - 1]
                i -= 1
            else:
                i += 1
        for left, right in zip(shots, shots[1:]):
            if left.get("locked"):
                continue
            boundary = tm.resolve(right["start"])
            kept_overlays = []
            for ov in left.get("overlays", []):
                at = tm.resolve(ov["start"])
                remaining = max(0.0, boundary - at)
                if ov.get("dur", 0) > remaining:
                    required = ((bundle.spec(ov["technique"]) or {}).get("timing") or {}).get("min_s") or 0
                    notes.append({"moment": left.get("moment", "program"), "rule": "C8", "what": "overlay shortened or omitted at a locked boundary"})
                    if remaining + 1e-6 < required:
                        continue
                    ov["dur"] = remaining
                kept_overlays.append(ov)
            left["overlays"] = kept_overlays
    doc = {"schema": "bti.storyboard/1", "style": style_id, "canvas": {"w": 1920, "h": 1080, "fps": 30},
           "assets": assets, "shots": shots, "end": {"t": timing["duration"]}, "compose_notes": notes,
           "made_from": {"visual": canon_hash(visual), "timing": canon_hash(timing), "style": canon_hash(config)}}
    if isinstance(current, dict):
        for field in ("project", "title", "audio", "timing", "approvals", "identity"):
            if field in current:
                doc[field] = deepcopy(current[field])
    identity_config = identity.read(bundle.style)
    if identity_config:
        selected = identity.chosen_style(current, bundle.style) or identity_config.default_style
        doc, _ = identity.apply_identity(doc, selected, bundle.style, tm,
                                         {"main_asset": main, "picks": picks, "title": (current or {}).get("title") or assets[main].get("title"), "artist": assets[main].get("artist"), "year": assets[main].get("year")}, defaults=bundle.param_defaults)
    return doc, notes
