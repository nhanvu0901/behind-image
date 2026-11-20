"""The draft compiler: chapter specs (`bti.draft/1`) -> one full `bti.storyboard/1` document, then validate and draw check.

What it does (design section 7.2), in order:
  1. assets: the picks' assets, the saved storyboard's assets on top (the storyboard wins for a key both have), then the regions
     the agent added in `out/regions.json` (a new name only; a name that exists is never overwritten);
  2. per chapter: every spec shot becomes a shot with a start anchor `{w, off, text}`; the first shot of a chapter starts at the
     chapter's start; the engine's `default_params` fill slots and parameters (camera key lists come from there), the agent's
     `params` are laid over them; overlays get an end from `end_word`, `dur` or the technique's default length, clamped to the shot;
  3. chapter cards (X-CARD-01) and, when the silence is long enough, a title card (X-CARD-02) in the silences the voice left;
  4. locked shots of the saved storyboard are copied through untouched; new shots that start inside one are dropped; a
     continuation shot starts where a locked shot ends, so that the locked shot keeps its length;
  5. ids: a shot that starts on the same word as a saved shot keeps that id; new ids are never one that was ever handed out;
  6. `validate` and `draw_check` of the engine; every issue is rewritten in the spec's terms (chapter, shot number, field);
  7. with `degrade=True` (the proposal run) a shot that still has an error is replaced by a plain push-in on a picture, an overlay
     with an error is dropped, a chapter with no usable shot is drafted by `auto`; so the document always validates.
  8. the channel identity: before the check, `bti.identity.apply_identity` turns the title card, the chapter cards and the opening
     overlays into the style the project chose (`identity.style` of the saved storyboard), else the style's default, so that a new
     video has its identity with no step by anyone. Edit mode never applies it (it only carries `identity` over).

Shot numbers count from 1 within a chapter's file. Nothing here calls a model.
"""
from __future__ import annotations

import copy
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from bti import identity as ID
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import viewchecks as VC
from bti.engine.timing import AnchorError, Timing, norm
from bti.media.assets import scale_regions

from . import spec as S
from . import decompile as D
from . import zones as Z
from .engine import DraftProject
from .inputs import DraftError, DraftInputs, beat_picks

CARD_S = Z.CARD_S
TITLE_CARD_S = Z.TITLE_CARD_S
MIN_CARD_S = Z.MIN_CARD_S
PACE_SHORT_S, PACE_LONG_S = 1.5, 30.0
REPEAT_RUN = 4
NARRATION_GRAM = 5
EPS = 1e-6
REGION_CAMERAS = ("CAM-01", "CAM-03", "CAM-05")
CARD_KIND = "card"


@dataclass
class CompileResult:
    storyboard: dict
    issues: list = field(default_factory=list)       # in the spec's terms, errors and warnings
    origin: list = field(default_factory=list)       # one entry per shot of the storyboard
    degraded: list = field(default_factory=list)     # issues that made `degrade` replace something
    stats: dict = field(default_factory=dict)
    drawn: bool = False
    violations: list = field(default_factory=list)      # edit mode: changes outside the scope (an acceptable result has none)
    identity: dict | None = None                        # report of the identity style that was applied ({style, changed, skipped}), else None

    @property
    def errors(self) -> list:
        return [i for i in self.issues if i["level"] == "error"]

    @property
    def warnings(self) -> list:
        return [i for i in self.issues if i["level"] != "error"]

    def shot_index(self, chapter: str, n: int) -> int | None:
        for i, o in enumerate(self.origin):
            if o.get("chapter") == chapter and o.get("n") == n and o.get("kind") == "agent":
                return i
        return None


def _num_tail(sid) -> int:
    m = re.search(r"(\d+)$", str(sid))
    return int(m.group(1)) if m else 0


def _key(rel, cx, cy, z, ease="linear"):
    return {"at": {"rel": rel}, "cx": round(float(cx), 2), "cy": round(float(cy), 2), "zoom": round(float(z), 5), "ease": ease}


def _strings(obj, path=""):
    """(path, text) of every string value in a params/slots structure."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, "%s.%s" % (path, k) if path else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _strings(v, "%s[%d]" % (path, i))


PANEL_CAMERAS = {"LAY-01": (("left", "camera_left"), ("right", "camera_right")), "X-CMP-01": (("anchor", "camera_anchor"),)}      # catalogue pass: the slot whose region frames a panel


def panel_region_camera(info: dict, region_name: str, panel_w: float, panel_h: float) -> list | None:
    """The camera of a panel of LAY-01 or X-CMP-01 that shows a region of the picture (a detail beside another work), static: the region fills about 80% of the panel.
    None when the picture's size or the region is unknown. Without it the panel shows the whole painting small and the detail is not what the viewer sees."""
    r = (info.get("regions") or {}).get(region_name) if info else None
    if not (r and info.get("w") and info.get("h") and panel_w and panel_h):
        return None
    w, h = float(info["w"]), float(info["h"])
    rx = float(r.get("rx") or 0.08 * w)
    ry = float(r.get("ry") or rx)
    z = min(0.8 * panel_w / (2 * rx), 0.8 * panel_h / (2 * ry), 6.0)
    z = max(z, 0.94 * panel_h / h)
    return [_key(0.0, float(r["x"]), float(r["y"]), z), _key(1.0, float(r["x"]), float(r["y"]), z)]


class _Compiler:
    def __init__(self, inp: DraftInputs, specs: dict, regions: dict | None, engine, spec_problems: list, identity: bool = True):
        self.inp = inp
        self.specs = specs or {}
        self.t = inp.timing
        self.words = self.t["words"]
        self.tm = Timing({"duration": self.t["duration"], "words": self.words})
        self.bundle = R.load_bundle(inp.style)
        self.base_issues: list = list(spec_problems or [])
        self.own_engine = engine is None
        self.eng = engine or DraftProject(inp.project_dir, {"schema": SB.SCHEMA, "shots": [], "assets": {}, "end": {"t": 1.0}}, self.t)
        self.assets = self._merge_assets(regions)
        self.main = inp.picks["main_asset"]
        self.eng.set_saved({"schema": SB.SCHEMA, "style": inp.style, "assets": self.assets, "shots": [], "end": {"t": max(1.0, self.t["duration"])}})
        self.beats_by_chapter: dict = {}
        for b in self.t["beats"]:
            self.beats_by_chapter.setdefault(b["chapter"], []).append(b)
        self.in_scope = set(inp.in_scope())
        self.grams = None
        self.cur = self._resolve_current()
        self.cur_by_id = {c["shot"].get("id"): c for c in self.cur}
        self.edit = inp.edit_shots is not None
        self.outside = VC.outside_asset_keys(inp.picks)           # catalogue pass: the pictures that are not the painting (rule 17 holds them to their default fit)
        self.identity_cfg = ID.read(self.bundle.style) if identity else None        # None: the old cards stay as they are
        self._counter = max([_num_tail(x) for x in inp.reserved_ids] + [_num_tail(c["shot"].get("id")) for c in self.cur] + [0])
        self.fallback_specs = None

    def close(self):
        if self.own_engine:
            self.eng.close()

    # ---------------------------------------------------------------- assets
    def _merge_assets(self, regions) -> dict:
        assets = copy.deepcopy(self.inp.picks["assets"])
        for k, a in ((self.inp.current or {}).get("assets") or {}).items():
            if isinstance(a, dict):
                assets[k] = self._saved_asset(a, assets.get(k))
        for key, regs in (regions or {}).items():
            a = assets.get(key)
            if not isinstance(a, dict):
                continue
            have = a.setdefault("regions", {})
            for name, r in regs.items():
                if name in have:
                    self.base_issues.append(S.problem("region_exists", None, None, "regions.json: %s.%s already exists and was kept as it is" % (key, name), level="warn"))
                else:
                    have[name] = dict(r)
        return assets

    # What describes the STORED FILE of a picture: its path, kind, pixel size, the source's own size kept beside it, a video's length. These are
    # facts of the file and always come from the picks (their sizes were corrected to the file by `reconcile_sizes`); a storyboard saved before
    # a correction must not keep the old ones (the warning `asset_size_mismatch` would never clear). Everything else on the saved copy (regions,
    # title, artist, year, credit, anything a person or an agent added there) is kept, as before.
    FILE_FACTS = ("file", "kind", "width", "height", "original_width", "original_height", "duration")

    def _saved_asset(self, saved: dict, pick) -> dict:
        out = copy.deepcopy(saved)
        if not isinstance(pick, dict):
            return out                                   # a picture only the storyboard has: its own record
        old_w, old_h = out.get("width"), out.get("height")
        for k in self.FILE_FACTS:
            if k in pick:
                out[k] = copy.deepcopy(pick[k])
            else:
                out.pop(k, None)                         # a fact the picks do not state is not kept from another file
        new_w, new_h = out.get("width"), out.get("height")
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in (old_w, old_h, new_w, new_h)) and (old_w, old_h) != (new_w, new_h):
            scale_regions(out.get("regions"), new_w / old_w, new_h / old_h)     # the regions were drawn in the old size: the same scaling as `reconcile_sizes`
        return out

    def info(self, key):
        a = self.assets.get(key)
        if not isinstance(a, dict):
            return None
        return {"key": key, "w": a.get("width"), "h": a.get("height"), "title": a.get("title"), "artist": a.get("artist"),
                "year": a.get("year"), "regions": a.get("regions") or {}}

    def is_image(self, key) -> bool:
        a = self.assets.get(key)
        return isinstance(a, dict) and a.get("kind") == "image"

    # ---------------------------------------------------------------- current storyboard
    def _resolve_current(self) -> list:
        out = []
        cur = self.inp.current
        if not isinstance(cur, dict):
            return out
        shots = [s for s in cur.get("shots") or [] if isinstance(s, dict)]
        ts = []
        for s in shots:
            try:
                ts.append(self.tm.resolve(s["start"]) if isinstance(s.get("start"), dict) else None)
            except (AnchorError, KeyError, TypeError):
                ts.append(None)
        end_t = self.t["duration"]
        try:
            if isinstance(cur.get("end"), dict):
                end_t = self.tm.resolve(cur["end"])
        except AnchorError:
            pass
        for i, s in enumerate(shots):
            if ts[i] is None:
                continue
            nxt = next((ts[j] for j in range(i + 1, len(shots)) if ts[j] is not None), end_t)
            nxt_anchor = next((shots[j]["start"] for j in range(i + 1, len(shots)) if ts[j] is not None), None)
            out.append({"shot": s, "t0": ts[i], "t1": nxt, "locked": bool(s.get("locked")), "next_anchor": nxt_anchor})
        return out

    # ---------------------------------------------------------------- zones and cards
    def brand_length(self) -> float:
        """`B` of the beat rule (`zones.title_length`): the nominal length of the channel-name beat of the style the video gets, else 2.9 s."""
        cfg = self.identity_cfg
        style_id = (ID.chosen_style(self.inp.current, self.bundle.style) or cfg.default_style) if cfg is not None else None
        return Z.brand_length(cfg, style_id)

    def fit_pct(self) -> float:
        """The painting's height as a percent of the frame (style.json `matte.painting_height_pct`), whether or not an identity is applied."""
        cfg = ID.read(self.bundle.style)
        return cfg.fit_pct if cfg is not None else Z.DEFAULT_FIT_PCT

    def opening_camera(self) -> list | None:
        """The camera keys of the opening shot (the whole main painting), None when the picture's size is not known."""
        a = self.assets.get(self.main)
        if not (isinstance(a, dict) and a.get("kind") == "image"):
            return None
        return Z.whole_camera(a.get("width"), a.get("height"), {"w": 1920, "h": 1080}, self.fit_pct())

    def zones(self) -> list:
        chs = self.t["chapters"]
        placed = None if self.edit else Z.place(chs, self.words, self.brand_length())      # the pure part: bti/draft/zones.py (the fit to the voice calls it too)
        if placed is not None:
            for cid, msg in placed["issues"]:
                self.base_issues.append(S.problem("card_no_room", cid, None, msg, level="warn"))
        zs = []
        prev_end = 0.0
        for k, c in enumerate(chs):
            z = {"id": c["id"], "name": c["name"], "w0": c["w0"], "w1": c["w1"], "start": c["start"], "end": c["end"],
                 "card": None, "title": None, "kept_cards": [], "opening": None}
            lead = c.get("lead")
            if self.edit:       # edit mode: the cards of the saved storyboard stay exactly as they are
                first_spoken = (
                    float(lead["end"])
                    if isinstance(lead, dict) and isinstance(lead.get("end"), (int, float)) and not isinstance(lead.get("end"), bool)
                    else (
                        self.words[c["w0"]]["s"]
                        if (c.get("w0") is not None and 0 <= c["w0"] < len(self.words))
                        else c["start"]
                    )
                )
                for cc in self.cur:
                    if self.is_card(cc["shot"]) and prev_end - EPS <= cc["t0"] < first_spoken - EPS:
                        z["kept_cards"].append(cc)
            else:
                p = placed["chapters"][k]
                z["card"], z["title"] = p["card"], p["title"]
                if p["first_start"] is not None:
                    z["start"] = p["first_start"]                       # the first shot starts where the cards end
                if k == 0 and placed["opening"] is not None and not (z["card"] or z["title"]) and self.opening_camera() is not None:
                    z["opening"] = placed["opening"]                    # the program's opening shot; the model's first shot starts 0.35 s before the first word
                    z["start"] = z["opening"]["start"] + z["opening"]["dur"]
            z["zone_start"] = min([x["t0"] for x in z["kept_cards"]] + [(z["title"] or z["card"] or {"start": c["start"]})["start"]])
            if k == 0:
                z["zone_start"] = 0.0
            zs.append(z)
            prev_end = c["end"]
        return zs

    # ---------------------------------------------------------------- defaults
    def defaults(self, tid, ctx, where: dict | None = None) -> dict:
        spec = self.bundle.spec(tid)
        if spec is None:
            return {}
        try:
            return self.eng.default_params(tid, ctx)
        except Exception as e:      # noqa: BLE001 - a technique that cannot give defaults is not the agent's fault
            self.base_issues.append(S.problem("defaults_failed", (where or {}).get("chapter"), (where or {}).get("n"),
                                              "the defaults of %s could not be made (%s); the registry defaults were used" % (tid, type(e).__name__), level="warn"))
            return {p["name"]: p["default"] for p in spec["params"]}

    def fit_zoom(self, info) -> float | None:
        if not (info and info.get("w") and info.get("h")):
            return None
        try:
            keys = self.eng.default_params("CAM-03", {"asset": info}).get("camera") or []
            return float(keys[-1]["zoom"]) if keys else None
        except Exception:       # noqa: BLE001
            return 0.955 * 1080.0 / float(info["h"])

    def region_camera(self, tid, info, region_name) -> list | None:
        r = (info.get("regions") or {}).get(region_name) if info else None
        z_fit = self.fit_zoom(info)
        if not (r and z_fit and info.get("w") and info.get("h")):
            return None
        w, h = float(info["w"]), float(info["h"])
        rx = float(r.get("rx") or 0.08 * w)
        ry = float(r.get("ry") or rx)
        z_det = min(1920 * 0.5 / (2 * rx), 1080 * 0.5 / (2 * ry))
        z_det = max(z_fit * 1.3, min(z_det, 6.0))
        cx, cy = float(r["x"]), float(r["y"])
        if tid == "CAM-05":
            return [_key(0.0, w / 2, h / 2, z_fit, "inout_cubic"), _key(1.0, cx, cy, z_det)]
        if tid == "CAM-01":
            z1 = z_det * 0.85
            return [_key(0.0, cx, cy, z1), _key(1.0, cx, cy, z1 * 1.142)]
        if tid == "CAM-03":
            return [_key(0.0, cx, cy, z_det, "in_quad"), _key(1.0, w / 2, h / 2, z_fit)]
        return None

    # ---------------------------------------------------------------- narration on screen
    def narration_grams(self) -> set:
        if self.grams is None:
            toks = [norm(w["w"]) for w in self.words]
            self.grams = {tuple(toks[i:i + NARRATION_GRAM]) for i in range(len(toks) - NARRATION_GRAM + 1)}
        return self.grams

    def copies_narration(self, text: str) -> bool:
        toks = [x for x in (norm(w) for w in text.split()) if x]
        if len(toks) < NARRATION_GRAM:
            return False
        g = self.narration_grams()
        return any(tuple(toks[i:i + NARRATION_GRAM]) in g for i in range(len(toks) - NARRATION_GRAM + 1))

    def screen_text_check(self, tid, params, chapter, n, overlay=None):
        """Remove (in place) every param that carries running narration text; return the problems."""
        spec = self.bundle.spec(tid)
        if spec is None or "quote" in (spec.get("intents") or []):
            return []
        out = []
        for path, text in list(_strings(params)):
            if self.copies_narration(text):
                top = path.split(".")[0].split("[")[0]
                params.pop(top, None)
                out.append(S.problem("narration_on_screen", chapter, n, "params.%s repeats the narration word for word (%d or more words in a row). "
                                     "Subtitles are never drawn into the picture; use a short label of your own (1-5 words) or leave the parameter out" % (path, NARRATION_GRAM),
                                     overlay=overlay, field="params." + top))
        return out

    def _fill_anchors(self, obj):
        if isinstance(obj, dict):
            if isinstance(obj.get("w"), int) and not isinstance(obj.get("w"), bool) and "text" not in obj and set(obj) <= {"w", "off", "text"}:
                if 0 <= obj["w"] < len(self.words):
                    obj["text"] = self.words[obj["w"]]["w"]
            for v in obj.values():
                self._fill_anchors(v)
        elif isinstance(obj, list):
            for v in obj:
                self._fill_anchors(v)

    # ---------------------------------------------------------------- catalogue pass: hidden techniques and outside pictures
    def carried_over(self, ss: dict, tid: str, overlay: bool = False, transition: bool = False) -> bool:
        """True when the saved storyboard already has `tid` on the shot of the same id: a stored shot that uses a hidden technique is never judged (the two finished videos do)."""
        old = self.cur_by_id.get(ss.get("id")) if ss.get("id") else None
        if old is None:
            return False
        shot = old["shot"]
        if transition:
            return (shot.get("transition_in") or {}).get("technique") == tid
        if overlay:
            return any(isinstance(o, dict) and o.get("technique") == tid for o in shot.get("overlays") or [])
        return shot.get("technique") == tid

    def refit_outside(self, tid: str, key, info, params: dict, mine: dict, default_cam, zone, n) -> None:
        """Rule 17: a picture that is not the painting is shown at its default fit. A camera of the model that shows it under 80% of its fit, or a small picture (long side
        under 1000 px) past twice its size, is replaced by the technique's default camera (and the compiler says so); the default itself is held to twice the size of a small
        picture. Only a technique that has a `camera`."""
        spec = self.bundle.spec(tid)
        if key not in self.outside or not info or not (info.get("w") and info.get("h")) or not any(p.get("name") == "camera" for p in (spec or {}).get("params") or []):
            return
        w, h = float(info["w"]), float(info["h"])
        cam = params.get("camera")
        problem = VC.outside_camera_problem([k.get("zoom") for k in cam if isinstance(k, dict)], w, h) if isinstance(cam, list) else None
        if problem and "camera" in mine and default_cam:
            fit = VC.default_fit_zoom(w, h)
            self.base_issues.append(S.problem("outside_camera_refit", zone["id"], n,
                                              "the camera of this shot showed the picture %r %s (rule 17: a picture that is not the painting is shown at its default fit, zoom %.2f); "
                                              "the compiler put the default camera back" % (info.get("title") or key, "under 80% of that fit" if problem == "small" else "enlarged past twice its size",
                                                                                           fit), field="params.camera", level="warn"))
            params["camera"] = copy.deepcopy(default_cam)
            cam = params["camera"]
        if isinstance(cam, list) and VC.is_small_picture(w, h):           # a small picture is never enlarged beyond twice its size
            for k in cam:
                if isinstance(k, dict) and isinstance(k.get("zoom"), (int, float)) and k["zoom"] > VC.SMALL_PICTURE_MAX_ZOOM:
                    k["zoom"] = VC.SMALL_PICTURE_MAX_ZOOM

    # ---------------------------------------------------------------- one spec shot
    def build_shot(self, zone, ss, beat_picks_) -> dict:
        n, tid = ss["_n"], ss["technique"]
        where = {"chapter": zone["id"], "n": n}
        spec = self.bundle.spec(tid)
        slots = {k: {"asset": v["asset"]} for k, v in (ss.get("slots") or {}).items()}
        regs = {k: v.get("region") for k, v in (ss.get("slots") or {}).items()}
        pick0 = beat_picks_[0] if beat_picks_ else None
        if spec is not None and "footage" not in slots and any(sd["name"] == "footage" for sd in spec["slots"]):
            vpick = next((p for p in beat_picks_ if (self.assets.get(p.get("asset")) or {}).get("kind") == "video"), pick0)
            if vpick:
                slots["footage"] = {"asset": vpick["asset"]}
        if spec is not None and "image" not in slots and any(sd["name"] == "image" and sd.get("type") == "image" for sd in spec["slots"]):
            ipick = next((p for p in beat_picks_ if self.is_image(p.get("asset"))), None)
            slots["image"] = {"asset": ipick["asset"] if ipick else self.main}
            if ipick and ipick.get("region"):
                regs.setdefault("image", ipick["region"])
        pslot, akey = SB.primary_slot({"slots": slots})
        region = regs.get(pslot) if pslot else None
        if region is None and akey and pick0 and pick0["asset"] == akey:
            region = pick0.get("region")
        info = self.info(akey) if akey else None
        if region and info and region not in info["regions"]:
            self.base_issues.append(S.problem("region_unknown", zone["id"], n, "region %r does not exist on asset %r (regions: %s). Use one of them, or add it to out/regions.json" % (region, akey, ", ".join(sorted(info["regions"])) or "none"), field="slots.%s.region" % pslot))
            region = None
        label = ((info or {}).get("regions", {}).get(region) or {}).get("label") if region else None
        params: dict = {}
        if spec is not None:
            ctx: dict = {"asset": info} if info else {}
            if region:
                ctx.update(region=region, focus=region, text=label or region)
            second = [v["asset"] for k, v in slots.items() if k != pslot and self.is_image(v["asset"])]
            if second:
                ctx["asset_right"] = self.info(second[0])
            params = self.defaults(tid, ctx, where)
            if tid in REGION_CAMERAS and region:
                cam = self.region_camera(tid, info, region)
                if cam:
                    params["camera"] = cam
            for slot_name, cam_param in PANEL_CAMERAS.get(tid, ()):          # catalogue pass: a detail of the painting beside another work is framed in its panel
                pr = regs.get(slot_name)
                if pr and slot_name in slots and cam_param not in (ss.get("params") or {}):
                    pcam = panel_region_camera(self.info(slots[slot_name]["asset"]), pr, params.get("panel_w_px") or 900, params.get("panel_h_px") or 740)
                    if pcam:
                        params[cam_param] = pcam
        mine = copy.deepcopy(ss.get("params") or {})
        for p in self.screen_text_check(tid, mine, zone["id"], n):
            self.base_issues.append(p)
        self._fill_anchors(mine)
        default_cam = copy.deepcopy(params.get("camera"))
        params.update(mine)
        if spec is not None:
            self.refit_outside(tid, akey, info, params, mine, default_cam, zone, n)
        shot = {"technique": tid, "slots": slots, "params": params,
                "intent": ss.get("intent") or (spec["intents"][0] if spec and spec.get("intents") else None),
                "transition_in": copy.deepcopy(ss.get("transition_in")), "overlays": [], "locked": False, "source": "agent",
                "note": ss.get("note") or ""}
        if spec is not None and (spec.get("channel_usage") == "shorts_only"):
            self.base_issues.append(S.problem("shorts_only_technique", zone["id"], n, "%s is reserved for Shorts; choose another technique" % tid, field="technique"))
            shot["_banned"] = True
        elif spec is not None and not self.bundle.offered(tid) and not self.carried_over(ss, tid):
            ban = self.bundle.not_offered_text(tid)         # catalogue pass: a technique hidden from the models is an error a model can repair
            self.base_issues.append(S.problem("technique_not_offered", zone["id"], n, ban, field="technique"))
            shot["_banned"], shot["_ban"] = True, ("technique_not_offered", ban)
        tr = (ss.get("transition_in") or {}).get("technique") if isinstance(ss.get("transition_in"), dict) else None
        if isinstance(tr, str) and self.bundle.spec(tr) is not None and not self.bundle.offered(tr) and not self.carried_over(ss, tr, transition=True):
            ban = self.bundle.not_offered_text(tr)
            self.base_issues.append(S.problem("technique_not_offered", zone["id"], n, ban, field="transition_in.technique"))
            shot["_banned"], shot["_ban"] = True, ("technique_not_offered", ban)
        return shot

    def build_overlay(self, zone, n, j, os_, shot, carried: bool = False) -> dict | None:
        tid = os_["technique"]
        spec = self.bundle.spec(tid)
        if spec is not None and not self.bundle.offered(tid) and not carried:
            self.base_issues.append(S.problem("technique_not_offered", zone["id"], n, self.bundle.not_offered_text(tid), overlay=j, field="technique"))
            return None                                       # catalogue pass: the overlay is dropped and the model is told
        pslot, akey = SB.primary_slot(shot)
        info = self.info(akey) if akey else None
        mine = copy.deepcopy(os_.get("params") or {})
        for p in self.screen_text_check(tid, mine, zone["id"], n, overlay=j):
            self.base_issues.append(p)
            return None
        at = mine.get("at")
        region = at if isinstance(at, (str, list)) else None
        slots = {k: {"asset": v["asset"]} for k, v in (os_.get("slots") or {}).items()}
        params = {}
        if spec is not None:
            ctx: dict = {"asset": info} if info else {}
            if region is not None:
                ctx["region"] = region
            params = self.defaults(tid, ctx, {"chapter": zone["id"], "n": n})
        self._fill_anchors(mine)
        params.update(mine)
        return {"technique": tid, "intent": os_.get("intent") or (spec["intents"][0] if spec and spec.get("intents") else None),
                "slots": slots, "params": params, "locked": False, "source": "agent", "note": os_.get("note") or ""}

    # ---------------------------------------------------------------- chapter plans
    def _t_of(self, ss) -> float:
        sw = ss["start_word"]
        if 0 <= sw < len(self.words):
            return self.words[sw]["s"] + float(ss.get("off") or 0.0)
        return float("inf")

    def plan_chapter(self, zone, spec) -> list:
        cid = zone["id"]
        beats = {b["id"]: b for b in self.beats_by_chapter.get(cid, [])}
        recs = []
        seen_w: set = set()
        last_t = None
        for ss in sorted(spec.get("shots") or [], key=lambda s: (self._t_of(s), s["_n"])):
            n, sw = ss["_n"], ss["start_word"]
            if self.identity_card_spec(ss):
                if not self.edit:
                    self.base_issues.append(S.problem("card_written_by_agent", cid, n, "%s is a chapter mark or title slot of the channel identity: the compiler places those, so this shot was ignored" % ss.get("technique"), field="technique", level="warn"))
                continue
            b = beats.get(ss["beat"])
            if b is None:
                other = next((x for x in self.t["beats"] if x["id"] == ss["beat"]), None)
                self.base_issues.append(S.problem("beat_unknown" if other is None else "beat_other_chapter", cid, n,
                                                  ("there is no beat %r in inputs/beats.json" % ss["beat"]) if other is None else
                                                  "beat %r belongs to chapter %s, not to this file" % (ss["beat"], other["chapter"]), field="beat"))
                continue
            if not (zone["w0"] <= sw < zone["w1"]):
                self.base_issues.append(S.problem("start_word_outside_chapter", cid, n, "start_word %d is outside this chapter (words %d to %d)" % (sw, zone["w0"], zone["w1"] - 1), field="start_word"))
                continue
            if not (b["w0"] <= sw < b["w1"]):
                self.base_issues.append(S.problem("start_word_outside_beat", cid, n, "start_word %d is not inside beat %s (words %d to %d): a shot starts on a word of its own beat" % (sw, b["id"], b["w0"], b["w1"] - 1), field="start_word"))
            first = not recs
            off = float(ss.get("off") or 0.0)
            if first and not self.edit:
                if sw > zone["w0"]:
                    self.base_issues.append(S.problem("chapter_start_moved", cid, n, "the first shot starts on word %d but the chapter starts on word %d; the shot now starts at the chapter start so that no word is left without a picture" % (sw, zone["w0"]), field="start_word", level="warn"))
                    sw = zone["w0"]
                lead = zone["start"] - self.words[sw]["s"]
                off = lead if lead <= 0 else off
                if zone["zone_start"] == 0.0 and not zone["card"] and not zone["title"] and zone["start"] <= 0.05 + EPS:
                    off = 0.0 - self.words[sw]["s"]
            t0 = self.words[sw]["s"] + off
            if last_t is not None and t0 <= last_t + EPS:
                self.base_issues.append(S.problem("shot_order", cid, n, "this shot would start at %.2f s, not after the previous shot (%.2f s); lower its \"off\" or give it a later start_word" % (t0, last_t), field="start_word"))
                continue
            old = self.cur_by_id.get(ss.get("id")) if ss.get("id") else None
            if old is not None and not D.is_card(self.bundle, old["shot"]) and sw == ss["start_word"] and \
                    D.comparable(ss) == D.comparable(D.shot_to_spec(self.inp, self.tm, old["shot"], old["t0"], old["t1"])):
                recs.append({"shot": copy.deepcopy(old["shot"]), "chapter": cid, "n": n, "beat": ss["beat"], "kind": "agent", "t0": old["t0"],
                             "anchor": copy.deepcopy(old["shot"]["start"]), "ov_specs": [], "sw": sw, "zone": zone,
                             "verbatim": True, "old_id": old["shot"].get("id")})
                seen_w.add(sw)
                last_t = old["t0"]
                continue
            shot = self.build_shot(zone, ss, beat_picks(self.inp.picks, ss["beat"]))
            recs.append({"shot": shot, "chapter": cid, "n": n, "beat": ss["beat"], "kind": "agent", "t0": t0,
                         "anchor": {"w": sw, "off": round(off, 4), "text": self.words[sw]["w"]}, "ov_specs": ss.get("overlays") or [],
                         "sw": sw, "zone": zone})
            seen_w.add(sw)
            last_t = t0
        return recs

    def is_card(self, shot: dict) -> bool:
        """A card of the compiler: `decompile.is_card` (the engine's card kinds and the identity's title slot and chapter marks)."""
        return D.is_card(self.bundle, shot)

    def identity_card_spec(self, ss: dict) -> bool:
        """A spec shot that stands for a title slot or chapter mark of the identity the compiler handles itself: in a draft any such
        shot is ignored (the compiler places the cards); in edit mode a copy of a saved one is (it is carried through as a card), a
        new one without an id (the owner asked for one) is not."""
        cfg = self.identity_cfg
        if cfg is None or not cfg.is_identity_card(ss.get("technique")):
            return False
        if not self.edit:
            return True
        old = self.cur_by_id.get(ss.get("id")) if ss.get("id") else None
        return old is not None and self.is_card(old["shot"])

    def locked_card_near(self, t: float) -> bool:
        return any(c["locked"] and self.is_card(c["shot"]) and abs(c["t0"] - t) < 0.75 for c in self.cur)

    def card_recs(self, zone) -> list:
        out = []
        if zone["title"] and self.locked_card_near(zone["title"]["start"]):
            zone["title"] = None
        if zone["card"] and self.locked_card_near(zone["card"]["start"]):
            zone["card"] = None
        if zone["title"]:
            info = self.info(self.main)
            shot = {"technique": "X-CARD-02", "slots": {"background": {"asset": self.main}}, "intent": "structure", "transition_in": None,
                    "overlays": [], "locked": False, "source": "agent", "note": "title card",
                    "params": self.defaults("X-CARD-02", {"asset": info, "title": self.inp.title} if info else {"title": self.inp.title})}
            out.append({"shot": shot, "chapter": zone["id"], "n": None, "beat": None, "kind": "title", "t0": zone["title"]["start"],
                        "anchor": {"t": round(zone["title"]["start"], 3)}, "ov_specs": [], "zone": zone})
        if zone["card"]:
            shot = {"technique": "X-CARD-01", "slots": {}, "intent": "structure", "transition_in": None, "overlays": [], "locked": False,
                    "source": "agent", "note": "chapter card", "params": self.defaults("X-CARD-01", {"title": zone["name"]})}
            out.append({"shot": shot, "chapter": zone["id"], "n": None, "beat": None, "kind": "card", "t0": zone["card"]["start"],
                        "anchor": {"t": round(zone["card"]["start"], 3)}, "ov_specs": [], "zone": zone})
        if zone.get("opening"):
            out.append(self.opening_rec(zone))
        return out

    def opening_rec(self, zone) -> dict:
        """The program's opening shot (`zones.opening_shot`): the whole main painting from 0 to 0.35 s before the first word, no overlays of its own
        (`apply_identity` puts the opening on it). Its id is the reserved one, so that it is found again after every kind of edit."""
        info = self.info(self.main)
        base = self.defaults(Z.OPENING_TECHNIQUE, {"asset": info} if info else {}, {"chapter": zone["id"], "n": None})
        shot = Z.opening_shot(self.main, self.assets.get(self.main), {"w": 1920, "h": 1080}, self.fit_pct(), base)
        shot.pop("id")
        shot.pop("start")
        return {"shot": shot, "chapter": zone["id"], "n": None, "beat": None, "kind": "opening", "t0": 0.0, "anchor": {"t": 0.0}, "ov_specs": [],
                "zone": zone, "id": Z.OPENING_ID}

    def fallback_shot(self, rec, stage: int) -> dict:
        shot = rec["shot"]
        _, akey = SB.primary_slot(shot)
        zone = rec["zone"]
        if stage >= 2:
            return {"technique": "X-CARD-01", "slots": {}, "intent": "structure", "transition_in": None, "overlays": [], "locked": False,
                    "source": "agent", "note": "plain card: the planned shot could not be drawn",
                    "params": self.defaults("X-CARD-01", {"title": zone["name"]})}
        key = akey if (stage == 0 and akey and self.is_image(akey)) else self.main
        info = self.info(key)
        return {"technique": "CAM-01", "slots": {"image": {"asset": key}}, "intent": "explore", "transition_in": None, "overlays": [],
                "locked": False, "source": "agent", "note": "plain push-in: the planned shot could not be drawn",
                "params": self.defaults("CAM-01", {"asset": info} if info else {})}

    # ---------------------------------------------------------------- all chapters
    def plan(self, degrade: bool) -> tuple[list, list]:
        zones = self.zones()
        recs: list = []
        for k, z in enumerate(zones):
            nxt_start = zones[k + 1]["zone_start"] if k + 1 < len(zones) else float("inf")
            if z["id"] not in self.in_scope:
                for c in self.cur:
                    if z["zone_start"] - EPS <= c["t0"] < nxt_start - EPS:
                        recs.append({"shot": copy.deepcopy(c["shot"]), "chapter": z["id"], "n": None, "beat": None, "kind": "kept",
                                     "t0": c["t0"], "anchor": copy.deepcopy(c["shot"]["start"]), "ov_specs": [], "zone": z,
                                     "old_id": c["shot"].get("id")})
                continue
            spec = self.specs.get(z["id"])
            mine = self.plan_chapter(z, spec) if spec else []
            if not mine:
                self.base_issues.append(S.problem("chapter_missing" if not spec else "chapter_empty", z["id"], None,
                                                  "no usable shot for this chapter: write out/%s.json" % z["id"] if not spec else "none of the shots of this chapter could be used",
                                                  level="warn" if degrade else "error"))
                if degrade:
                    if self.fallback_specs is None:
                        from .providers import auto
                        self.fallback_specs = auto.draft(self.inp)
                    fs = self.fallback_specs.get(z["id"])
                    if fs:
                        shape, _ = S.shape_problems(fs, z["id"])
                        mine = self.plan_chapter(z, shape)
                        self.base_issues.append(S.problem("chapter_filled_by_auto", z["id"], None, "this chapter was drafted by the automatic drafter", level="warn"))
            if self.edit:
                for cc in z["kept_cards"]:
                    recs.append({"shot": copy.deepcopy(cc["shot"]), "chapter": z["id"], "n": None, "beat": None, "kind": "kept", "t0": cc["t0"],
                                 "anchor": copy.deepcopy(cc["shot"]["start"]), "ov_specs": [], "zone": z, "old_id": cc["shot"].get("id")})
                recs += mine
            else:
                recs += mine + self.card_recs(z)
        return recs, zones

    def apply_locked(self, recs: list, zones: list) -> list:
        end_t = self.t["duration"]
        locked = [c for c in self.cur if c["locked"] and any(z["id"] in self.in_scope and z["zone_start"] - EPS <= c["t0"] < (zones[i + 1]["zone_start"] if i + 1 < len(zones) else float("inf")) - EPS for i, z in enumerate(zones))]
        for c in sorted(locked, key=lambda c: c["t0"]):
            ls, le = c["t0"], c["t1"]
            before = [r for r in recs if r["t0"] <= le + EPS]
            active = max(before, key=lambda r: r["t0"]) if before else None
            recs = [r for r in recs if not (ls - EPS <= r["t0"] < le - EPS)]
            zone = active["zone"] if active else zones[0]
            recs.append({"shot": copy.deepcopy(c["shot"]), "chapter": zone["id"], "n": None, "beat": None, "kind": "locked", "t0": ls,
                         "anchor": copy.deepcopy(c["shot"]["start"]), "ov_specs": [], "zone": zone, "old_id": c["shot"].get("id")})
            if le < end_t - 0.05 and not any(abs(r["t0"] - le) < 0.05 for r in recs) and active is not None and active["kind"] in ("agent", "kept", "filler"):
                shot = copy.deepcopy(active["shot"])
                shot["overlays"], shot["locked"], shot["note"] = [], False, "continues after a locked shot"
                shot.pop("id", None)
                anchor = copy.deepcopy(c["next_anchor"]) if isinstance(c["next_anchor"], dict) else self.tm.anchor_at(le)
                recs.append({"shot": shot, "chapter": active["chapter"], "n": None, "beat": active.get("beat"), "kind": "filler",
                             "t0": le, "anchor": anchor, "ov_specs": [], "zone": active["zone"]})
        return recs

    def assign_ids(self, recs: list) -> None:
        used = {r["old_id"] for r in recs if (r["kind"] in ("locked", "kept") or r.get("verbatim")) and r.get("old_id")}
        # the id of the opening shot belongs to that shot alone: no other shot takes it over, and it takes nobody's
        old = [c for c in self.cur if not c["locked"] and c["shot"].get("id") not in used and not Z.is_opening(c["shot"])]
        taken: set = set()
        for r in recs:
            if r["kind"] in ("locked", "kept") or r.get("verbatim"):
                r["id"] = r["old_id"] or self._new_id()
                continue
            if r["kind"] == "opening":
                r["id"] = Z.OPENING_ID
                continue
            match, best = None, None
            r_card = r["kind"] in ("card", "title")
            for c in old:
                oid = c["shot"].get("id")
                if oid in taken or self.is_card(c["shot"]) != r_card:
                    continue
                a, b = c["shot"].get("start") or {}, r["anchor"]
                dt = abs(c["t0"] - r["t0"])
                if ("w" in a and "w" in b and a["w"] == b["w"]) or dt < 0.75:
                    if best is None or dt < best:
                        match, best = oid, dt
                        r["old_shot"] = c["shot"]
            if match:
                taken.add(match)
                r["id"] = match
            else:
                r["id"] = self._new_id()

    def _new_id(self) -> str:
        self._counter += 1
        return "s%04d" % self._counter

    # ---------------------------------------------------------------- build the document
    def build_doc(self, recs: list) -> tuple[dict, list, list]:
        """-> (document, origin per shot, issues made while building overlays)."""
        recs = sorted(recs, key=lambda r: r["t0"])
        issues: list = []
        shots, origin = [], []
        end_t = self.t["duration"]
        for i, r in enumerate(recs):
            t1 = recs[i + 1]["t0"] if i + 1 < len(recs) else end_t
            shot = copy.deepcopy(r["shot"])
            shot.pop("_banned", None)
            shot.pop("_ban", None)
            shot.pop("overlays", None)
            ovs, omap = [], []
            used_o = {o.get("id") for o in (r.get("old_shot") or {}).get("overlays") or []}
            counter = max([_num_tail(x) for x in used_o if x] + [0])
            if r["kind"] in ("locked", "kept") or r.get("verbatim"):
                ovs = copy.deepcopy(r["shot"].get("overlays") or [])
                omap = [None] * len(ovs)
            for j, os_ in enumerate(r["ov_specs"], 1):
                if os_.get("_drop"):
                    continue
                o = self.build_overlay(r["zone"], r["n"], j, os_, shot,           # catalogue pass: an overlay the saved shot already has is never judged
                                       carried=any(isinstance(x, dict) and x.get("technique") == os_["technique"] for x in (r.get("old_shot") or {}).get("overlays") or []))
                if o is None:
                    os_["_drop"] = True
                    continue
                sw = os_["start_word"]
                if not (0 <= sw < len(self.words)):
                    issues.append(S.problem("overlay_start_word", r["chapter"], r["n"], "start_word %d does not exist" % sw, overlay=j, field="start_word"))
                    continue
                ts = self.words[sw]["s"] + float(os_.get("off") or 0.0)
                if ts < r["t0"] - 0.05 or ts >= t1 - 0.3:
                    issues.append(S.problem("overlay_outside_shot", r["chapter"], r["n"], "the overlay starts at %.2f s (word %d) but the shot lasts from %.2f s to %.2f s; start the overlay on a word inside the shot (and at least 0.3 s before it ends)" % (ts, sw, r["t0"], t1), overlay=j, field="start_word"))
                    continue
                ts = max(ts, r["t0"])
                te = None
                ew = os_.get("end_word")
                if ew is not None:
                    if ew < len(self.words):
                        te = self.words[ew]["e"]
                    else:
                        issues.append(S.problem("overlay_end_word", r["chapter"], r["n"], "end_word %d does not exist" % ew, overlay=j, field="end_word", level="warn"))
                elif os_.get("dur") is not None:
                    te = ts + float(os_["dur"])
                else:
                    ospec = self.bundle.spec(os_["technique"])
                    d = ((ospec or {}).get("timing") or {}).get("default_s")
                    if d:
                        te = ts + float(d)
                if te is not None:
                    if te > t1:
                        te = t1
                    if te - ts < 0.3:
                        te = min(t1, ts + 0.3)
                a = self.words[sw]
                o["start"] = {"w": sw, "off": round(ts - a["s"], 4), "text": a["w"]}
                if te is not None:
                    o["dur"] = round(te - ts, 3)
                old_match = next((x for x in (r.get("old_shot") or {}).get("overlays") or []
                                  if x.get("technique") == o["technique"] and (x.get("start") or {}).get("w") == sw), None)
                if old_match and old_match.get("id"):
                    o["id"] = old_match["id"]
                else:
                    counter += 1
                    o["id"] = "o%d" % counter
                    while o["id"] in used_o:
                        counter += 1
                        o["id"] = "o%d" % counter
                used_o.add(o["id"])
                ovs.append(o)
                omap.append(j - 1)
            shot["overlays"] = ovs
            shot["id"] = r["id"]
            shot["start"] = copy.deepcopy(r["anchor"])
            ordered = {"id": shot["id"], "start": shot["start"]}
            for k in ("technique", "slots", "params", "intent", "transition_in", "overlays", "locked", "source", "note"):
                if k in shot:
                    ordered[k] = shot[k]
            for k, v in shot.items():
                ordered.setdefault(k, v)
            shots.append(ordered)
            origin.append({"chapter": r["chapter"], "n": r["n"], "beat": r["beat"], "kind": r["kind"], "technique": shot.get("technique"),
                           "id": shot["id"], "ov_map": omap, "t0": r["t0"], "t1": t1, "banned": bool(r["shot"].get("_banned")), "ban": r["shot"].get("_ban")})
        doc = {"schema": SB.SCHEMA, "project": Path(self.inp.project_dir).name, "title": self.inp.title, "style": self.inp.style,
               "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": self.inp.timing_file,
               "audio": self.inp.audio, "assets": copy.deepcopy(self.assets), "shots": shots, "end": {"t": round(end_t, 4)},
               "approvals": {"storyboard": None}}
        if doc["audio"] is None:
            doc.pop("audio")
        for k in ("approvals",):
            if isinstance((self.inp.current or {}).get(k), dict):
                doc[k] = copy.deepcopy(self.inp.current[k])
        keep = (self.inp.current or {}).get("identity")
        if isinstance(keep, dict) and self.identity_cfg is not None:      # the choice belongs to the project: carried over
            placed = {}
            for k, v in doc.items():
                placed[k] = v
                if k == "style":
                    placed["identity"] = copy.deepcopy(keep)
            doc = placed
        # titlestep: the title the project's title document holds (written by an agent or set by a person) is the video's title on the channel-name beat; it wins over an
        # `identity.video_title` carried over from an earlier storyboard. No document: the field is left as it is (the beat then falls back to the painting's title).
        if self.identity_cfg is not None and not self.edit:
            from bti.title import chosen_text
            vt = chosen_text(self.inp.project_dir) if self.inp.project_dir else None
            if vt:
                doc = ID.with_video_title(doc, vt)
        return doc, origin, issues

    # ---------------------------------------------------------------- the channel identity
    def apply_identity(self, doc: dict, origin: list) -> tuple[dict, dict | None]:
        """The document in the identity style of the project (the saved storyboard's choice, else the style's default).
        `origin` (one entry per shot) is brought in line with the new techniques and overlays. Not in edit mode."""
        cfg = self.identity_cfg
        if self.edit or cfg is None:
            return doc, None
        style_id = ID.chosen_style(self.inp.current, self.bundle.style) or cfg.default_style
        new, report = ID.apply_identity(doc, style_id, self.bundle.style, self.tm, {"title": self.inp.title, "main_asset": self.main},
                                        defaults=self.bundle.param_defaults)
        for o, a, b in zip(origin, doc["shots"], new["shots"]):
            o["technique"] = b.get("technique")
            before = {ov.get("id"): m for ov, m in zip(a.get("overlays") or [], o["ov_map"])}
            o["ov_map"] = [before.get(ov.get("id")) for ov in b.get("overlays") or []]
        return new, report

    # ---------------------------------------------------------------- engine issues in spec terms
    def map_issue(self, iss: dict, origin: list) -> dict:
        path = iss.get("path") or ""
        m = re.match(r"shots\[(\d+)\](?:\.overlays\[(\d+)\])?(?:\.(.*))?$", path)
        idx = int(m.group(1)) if m else None
        o = origin[idx] if idx is not None and idx < len(origin) else None
        out = {"level": iss.get("level", "error"), "code": iss.get("code") or "engine", "chapter": None, "shot": None, "overlay": None,
               "field": None, "engine_path": path, "engine_code": iss.get("code"), "rec": idx, "args": iss.get("args") or {}}
        if iss.get("hint"):
            out["hint"] = iss["hint"]                   # fixdraft: the engine's viewer checks say what to do
        if o is None:
            out["message"] = "the storyboard: %s" % iss.get("message")
            return out
        out["chapter"], out["shot"], out["beat"] = o["chapter"], o["n"], o["beat"]
        ovi = None
        if m.group(2) is not None:
            k = int(m.group(2))
            ovi = (o["ov_map"][k] + 1) if k < len(o["ov_map"]) and o["ov_map"][k] is not None else None
            out["overlay"] = ovi
            out["overlay_doc_index"] = k
        rest = m.group(3) or ""
        rest = re.sub(r"^start$", "start_word", rest)
        out["field"] = rest or None
        kind = {"agent": "", "card": "chapter card ", "title": "title card ", "locked": "locked shot ", "kept": "unchanged shot ", "filler": "continuation shot ", "opening": "opening shot "}[o["kind"]]
        where = "chapter %s, %s" % (o["chapter"], ("%sshot %d" % (kind, o["n"])) if o["n"] else ("%s(%s)" % (kind or "shot ", o["id"])))
        if ovi:
            where += ", overlay %d" % ovi
        out["message"] = "%s (%s)%s: %s" % (where, o["technique"], (", field " + rest) if rest else "", iss.get("message"))
        return out

    # ---------------------------------------------------------------- pacing and stats
    def advice(self, origin: list) -> tuple[list, dict]:
        issues = []
        durs = []
        run = 0
        prev = None
        counts: dict = {}
        for o in origin:
            d = o["t1"] - o["t0"]
            if o["kind"] == "agent":
                durs.append(d)
                counts[o["technique"]] = counts.get(o["technique"], 0) + 1
                if d < PACE_SHORT_S:
                    issues.append(S.problem("pacing_short", o["chapter"], o["n"], "this shot lasts %.1f s; the pacing guide says none under %.1f s (merge it into the previous shot)" % (d, PACE_SHORT_S), level="warn"))
                if d > PACE_LONG_S:
                    issues.append(S.problem("pacing_long", o["chapter"], o["n"], "this shot lasts %.0f s; consider a second shot with a move or a detail" % d, level="warn"))
                run = run + 1 if o["technique"] == prev else 1
                prev = o["technique"]
                if run == REPEAT_RUN:
                    issues.append(S.problem("repeat_technique", o["chapter"], o["n"], "%s is used %d times in a row; vary the technique" % (o["technique"], REPEAT_RUN), level="warn"))
        usage: dict = {}
        for t, n in counts.items():
            u = (self.bundle.spec(t) or {}).get("channel_usage") or "?"
            usage[u] = usage.get(u, 0) + n
        stats = {"shots": len(origin), "agent_shots": len(durs), "median_shot_s": round(statistics.median(durs), 2) if durs else None,
                 "shortest_s": round(min(durs), 2) if durs else None, "longest_s": round(max(durs), 2) if durs else None,
                 "techniques": counts, "usage": usage}
        return issues, stats


def compile_specs(inp: DraftInputs, specs: dict, *, regions: dict | None = None, spec_problems: list | None = None,
                  degrade: bool = False, draw: bool = True, engine=None, max_passes: int = 4, identity: bool = True) -> CompileResult:
    """See the module docstring. `specs` maps chapter id -> a spec that already passed `spec.shape_problems` (its clean form).
    `identity=False` leaves the old cards (X-CARD-01, X-CARD-02) as the compiler places them: no identity style is applied."""
    c = _Compiler(inp, specs, regions, engine, spec_problems, identity)
    try:
        return _run(c, degrade, draw, max_passes)
    finally:
        c.close()


def _run(c: _Compiler, degrade: bool, draw: bool, max_passes: int) -> CompileResult:
    recs, zones = c.plan(degrade)
    recs = c.apply_locked(recs, zones)
    recs.sort(key=lambda r: r["t0"])
    # shots closer than the minimum length are not allowed: the later one is dropped, and the agent is told
    keep = []
    for i, r in enumerate(recs):
        nxt = recs[i + 1]["t0"] if i + 1 < len(recs) else c.t["duration"]
        if r["kind"] in ("agent", "filler") and not r.get("verbatim") and nxt - r["t0"] < SB.MIN_SHOT_S + 1e-3:
            c.base_issues.append(S.problem("shot_too_short", r["chapter"], r["n"], "this shot would last under %.1f s; it was removed" % SB.MIN_SHOT_S))
            continue
        keep.append(r)
    recs = keep
    if not recs:
        if degrade:
            raise DraftError("compile_empty", "no shot could be built")
        issues = _dedupe(c.base_issues + [S.problem("compile_empty", None, None, "no shot could be built: write the chapter files in out/")])
        return CompileResult({"schema": SB.SCHEMA, "shots": [], "assets": {}}, issues, [], [], {"shots": 0}, False)
    c.assign_ids(recs)
    if c.inp.edit_shots is not None:
        degrade = False
    degraded: list = []
    for r in recs:
        r.setdefault("fb_stage", -1)
    result = None
    for p in range(max_passes + 1):
        doc, origin, build_issues = c.build_doc(recs)
        doc, identity_report = c.apply_identity(doc, origin)
        mapped: list = []
        errs_engine = c.eng.validate(doc)
        mapped += [c.map_issue(i, origin) for i in errs_engine]
        drawn = False
        if draw and not any(i["level"] == "error" for i in errs_engine):
            mapped += [c.map_issue(i, origin) for i in c.eng.draw_check(doc)]
            drawn = True
        extra, stats = c.advice(origin)
        banned = []
        for o in origin:
            if o.get("banned"):
                code, msg = o["ban"] or ("shorts_only_technique", "%s is reserved for Shorts; choose another technique" % o["technique"])
                banned.append(S.problem(code, o["chapter"], o["n"], msg, field="technique"))
        issues = _dedupe(c.base_issues + build_issues + banned + mapped + extra)
        result = CompileResult(doc, issues, origin, degraded, stats, drawn, identity=identity_report)
        if not degrade or p == max_passes:
            break
        changed = False
        by_rec: dict = {}
        for i in issues:
            if i["level"] == "error" and i.get("rec") is not None:
                by_rec.setdefault(i["rec"], []).append(i)
        for o in origin:
            if o.get("banned"):
                by_rec.setdefault(origin.index(o), [{"level": "error", "code": (o.get("ban") or ("shorts_only_technique", ""))[0], "message": (o.get("ban") or (None, "reserved for Shorts"))[1]}])
        # recs in doc order = recs sorted by t0 (build_doc sorts)
        ordered = sorted(recs, key=lambda r: r["t0"])
        for idx, lst in by_rec.items():
            r = ordered[idx]
            if r["kind"] in ("locked", "kept"):
                continue
            ov_only = all(i.get("overlay_doc_index") is not None for i in lst)
            if any(i["code"] == "shot_too_short" for i in lst):
                if r in recs:
                    recs.remove(r)
                    changed = True
                degraded += lst
            elif ov_only:
                for i in lst:
                    k = i["overlay_doc_index"]
                    m = origin[idx]["ov_map"][k] if k < len(origin[idx]["ov_map"]) else None
                    if m is not None and not r["ov_specs"][m].get("_drop"):
                        r["ov_specs"][m]["_drop"] = True
                        changed = True
                degraded += lst
            else:
                r["fb_stage"] += 1
                r["shot"] = c.fallback_shot(r, r["fb_stage"])
                r["ov_specs"] = []
                r.pop("old_shot", None)
                changed = True
                degraded += lst
        if not changed:
            break
    result.degraded = degraded
    if c.inp.edit_shots is not None:
        viol = D.scope_violations(c.inp, result.storyboard, set(c.inp.edit_shots))
        result.violations = viol
        result.issues = _dedupe(result.issues + viol)
    return result


def _dedupe(issues: list) -> list:
    seen, out = set(), []
    for i in issues:
        k = (i["level"], i["code"], i.get("chapter"), i.get("shot"), i.get("overlay"), i["message"])
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


def summary_text(result: CompileResult, limit: int = 40) -> str:
    """The issues as lines for the agent (`check`) and for repair turns: errors first, then warnings."""
    errs, warns = result.errors, result.warnings
    lines = []
    for tag, items in (("ERROR", errs), ("warning", warns)):
        for i in items[:limit]:
            lines.append("%s %s: %s" % (tag, i["code"], i["message"]))
        if len(items) > limit:
            lines.append("... and %d more %s" % (len(items) - limit, tag.lower() + "s"))
    head = "%d error(s), %d warning(s)." % (len(errs), len(warns))
    if not result.drawn and errs:
        head += " The draw check was skipped until the errors are fixed."
    return head + ("\n" + "\n".join(lines) if lines else "")
