"""What the owner reads about an edit, in plain Vietnamese (contract A5, follow-up 13.3).

The owner does not know editing terms and reads Vietnamese. Two layers:

1. `shot_facts` builds, BY CODE and always true, a list of short sentences from the difference between a shot before and after:
   "Máy quay đi chậm hơn", "Thêm: vòng khoanh quanh chiếc gương", "Bỏ dòng chữ", "Cảnh bắt đầu sớm hơn 1,2 giây". Technique names are the
   registry's `label_vi` (the names the page shows); no shot id, technique id or parameter name ever appears.
2. The model's own sentence (`what`, `summary`, `reason`) is used only when `sentence_ok` accepts it: it has Vietnamese letters with
   diacritics, and no shot id, technique id, parameter name or bare parameter number (seconds are fine). Otherwise the facts are used
   (`what_source: "code"`), and the summary is built by `code_summary`. No second model call."""
from __future__ import annotations

import copy
import json
import math
import re

from bti.engine import registry as R
from bti.engine.timing import AnchorError, Timing

# ---------------------------------------------------------------------------------------------------- the check of a model sentence
_VI_LETTERS = re.compile(r"[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]", re.I)
_SHOT_ID = re.compile(r"\bs\d{3,6}\b", re.I)
_TECH_ID = re.compile(r"\b(?:[A-Z]{1,6}-)+\d{1,3}\b")
_NUMBER = re.compile(r"(?<![\w])(\d+(?:[.,]\d+)?)(?:\s*)(giây|giây|s\b)?", re.I)
# words that are parameter or format names, never owner words. Names with an underscore are always refused.
_TECH_WORDS = {"camera", "ease", "easing", "shadow", "cx", "cy", "rx", "ry", "start_word", "params", "param", "overlay", "overlays", "slots",
               "slot", "technique", "transition_in", "anchor", "json", "null", "true", "false", "inout_cubic", "in_cubic", "out_cubic",
               "inout_sine", "in_quad", "out_quad", "linear", "rel", "keyframe", "keyframes", "region", "regions", "asset", "beat"}


def _param_names() -> set[str]:
    try:
        b = R.load_bundle("gae")
        return {p["name"] for t in b.techniques for p in t.get("params") or [] if isinstance(p.get("name"), str)}
    except Exception:       # noqa: BLE001
        return set()


_PARAMS: set[str] | None = None


def sentence_ok(text) -> bool:
    """True when `text` is something to show the owner as the model wrote it."""
    global _PARAMS
    if not isinstance(text, str) or not text.strip() or len(text) > 400:
        return False
    if not _VI_LETTERS.search(text):
        return False
    if _SHOT_ID.search(text) or _TECH_ID.search(text):
        return False
    if _PARAMS is None:
        _PARAMS = {p for p in _param_names() if "_" in p}
    words = set(re.findall(r"[A-Za-z_]+", text.lower()))
    if words & _TECH_WORDS or any(p in text for p in _PARAMS):
        return False
    for m in _NUMBER.finditer(text):
        num, unit = m.group(1), m.group(2)
        if unit:
            continue
        if "." in num or "," in num or len(num) >= 3:      # 0.4075, 1,5, 1920: a parameter value, not something to say to the owner
            return False
    return True


# ---------------------------------------------------------------------------------------------------- words
EASE = {"linear": "đều", "in_quad": "chậm rồi nhanh", "out_quad": "nhanh rồi chậm", "in_cubic": "chậm rồi nhanh", "out_cubic": "nhanh rồi chậm",
        "inout_sine": "mượt hai đầu", "inout_cubic": "mượt hai đầu"}
SMOOTH = {"inout_sine", "inout_cubic", "in_quad", "out_quad", "in_cubic", "out_cubic"}
TEXT_PREFIXES = ("TXT-", "X-ANN-01", "X-ANN-02", "X-ANN-03", "STATIC-02", "STATIC-04", "STATIC-05", "STATIC-08", "STATIC-09", "SHORT-03", "SHORT-04")


def seconds_words(x: float) -> str:
    x = abs(x)
    s = ("%.1f" % x) if x < 10 else ("%d" % round(x))
    return s.replace(".", ",").replace(",0", "") + " giây"


def _bundle(sb: dict | None):
    try:
        return R.load_bundle((sb or {}).get("style") or "gae")
    except Exception:       # noqa: BLE001
        return None


def tech_label(bundle, tid) -> str:
    sp = bundle.spec(tid) if bundle is not None else None
    return (sp or {}).get("label_vi") or "một kiểu khác"


def _lower(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def _is_text(tid) -> bool:
    return isinstance(tid, str) and tid.startswith(TEXT_PREFIXES)


def region_label(assets: dict | None, asset, name) -> str | None:
    if not (isinstance(asset, str) and isinstance(name, str) and name):
        return None
    reg = (((assets or {}).get(asset) or {}).get("regions") or {}).get(name) or {}
    lab = reg.get("label")
    if isinstance(lab, str) and lab.strip() and lab.strip() != name:
        return lab.strip()
    return name.replace("_", " ").lower()


def _slot_region(shot: dict):
    for sl in (shot.get("slots") or {}).values():
        if isinstance(sl, dict) and sl.get("region"):
            return sl.get("asset"), sl.get("region")
    p = shot.get("params") or {}
    if isinstance(p.get("at"), str):
        return None, p["at"]
    return None, None


def _clean(o):
    return json.loads(json.dumps(o, sort_keys=True, default=str)) if o is not None else None


def _camera_motion(cam) -> tuple[float, float, float]:
    """(motion amount, final zoom, final centre x/visible width) of a camera key list; motion = zoom change + panning, in frame units."""
    keys = [k for k in cam or [] if isinstance(k, dict) and all(isinstance(k.get(n), (int, float)) for n in ("cx", "cy", "zoom")) and k["zoom"] > 0]
    if len(keys) < 2:
        return 0.0, (keys[-1]["zoom"] if keys else 0.0), 0.0
    motion = 0.0
    for a, b in zip(keys, keys[1:]):
        vis_w = 1920.0 / ((a["zoom"] + b["zoom"]) / 2)
        motion += abs(math.log(b["zoom"] / a["zoom"])) + math.hypot(b["cx"] - a["cx"], b["cy"] - a["cy"]) / vis_w
    return motion, keys[-1]["zoom"], keys[-1]["cx"]


def _camera_facts(b_cam, a_cam) -> list[str]:
    if _clean(b_cam) == _clean(a_cam):
        return []
    out: list[str] = []
    mb, zb, _ = _camera_motion(b_cam)
    ma, za, _ = _camera_motion(a_cam)
    if mb > 1e-6 and ma < mb * 0.9:
        out.append("Máy quay đi chậm hơn")
    elif ma > mb * 1.1 + 1e-6:
        out.append("Máy quay đi nhanh hơn")
    if zb > 0 and za > 0 and abs(math.log(za / zb)) > 0.05:
        out.append("Cảnh kết thúc gần hơn" if za > zb else "Cảnh kết thúc xa hơn")
    eb = [k.get("ease") for k in b_cam or [] if isinstance(k, dict)]
    ea = [k.get("ease") for k in a_cam or [] if isinstance(k, dict)]
    if eb != ea:
        if set(ea) <= SMOOTH and not set(eb) <= SMOOTH:
            out.append("Máy quay chuyển động mượt hơn")
        elif set(eb) <= SMOOTH and set(ea) == {"linear"}:
            out.append("Máy quay chuyển động đều hơn")
        else:
            out.append("Đổi nhịp chuyển động của máy quay")
    if not out:
        out.append("Chỉnh nhẹ chuyển động của máy quay")
    return out


def _match_overlays(before: list, after: list):
    """(pairs, added, removed): overlays matched by id, else by technique in order."""
    b_left = list(before)
    pairs, added = [], []
    for a in after:
        hit = None
        if a.get("id"):
            hit = next((b for b in b_left if b.get("id") == a.get("id")), None)
        if hit is None:
            hit = next((b for b in b_left if not b.get("id") and b.get("technique") == a.get("technique")), None) \
                if not a.get("id") else None
        if hit is None:
            added.append(a)
        else:
            b_left.remove(hit)
            pairs.append((hit, a))
    return pairs, added, b_left


def _main_asset(shot: dict):
    return next((v.get("asset") for v in (shot.get("slots") or {}).values() if isinstance(v, dict) and v.get("asset")), None)


def _overlay_phrase(bundle, o: dict, assets, default_asset=None) -> str:
    tid = o.get("technique")
    if _is_text(tid):
        return "dòng chữ"
    asset, name = _slot_region(o)
    lab = region_label(assets, asset or _main_asset(o) or default_asset, name)
    prep = "quanh" if isinstance(tid, str) and tid.startswith(("AN-01", "AN-02")) else "ở"
    return _lower(tech_label(bundle, tid)) + (" %s %s" % (prep, lab) if lab else "")


def shot_facts(before: dict, after: dict, *, assets: dict | None = None, bundle=None, tm: Timing | None = None) -> list[str]:
    """Plain Vietnamese sentences for what differs between two versions of ONE shot (stored shot form). Never an id or a parameter name."""
    bundle = bundle or _bundle(after)
    facts: list[str] = []
    tb, ta = before.get("technique"), after.get("technique")
    if tb != ta:
        facts.append("Đổi cách dựng: %s thành %s" % (tech_label(bundle, tb), _lower(tech_label(bundle, ta))))
    if tm is not None and isinstance(before.get("start"), dict) and isinstance(after.get("start"), dict):
        try:
            d = tm.resolve(after["start"]) - tm.resolve(before["start"])
        except (AnchorError, KeyError, TypeError):
            d = 0.0
        if abs(d) >= 0.05:
            facts.append("Cảnh bắt đầu %s hơn %s" % ("muộn" if d > 0 else "sớm", seconds_words(d)))
    if tb == ta:
        pb, pa = dict(before.get("params") or {}), dict(after.get("params") or {})
        cb, ca = pb.pop("camera", None), pa.pop("camera", None)
        facts += _camera_facts(cb, ca)
        if "shadow" in pb or "shadow" in pa:
            sb_, sa_ = pb.pop("shadow", None), pa.pop("shadow", None)
            if sb_ != sa_:
                facts.append("Tắt bóng đổ" if sa_ is False else "Bật bóng đổ")
        if _clean(pb) != _clean(pa):
            facts.append("Chỉnh một số thiết lập của kiểu dựng này")
    rb, ra = _slot_region(before), _slot_region(after)
    asset_b = next((v.get("asset") for v in (before.get("slots") or {}).values() if isinstance(v, dict)), None)
    asset_a = next((v.get("asset") for v in (after.get("slots") or {}).values() if isinstance(v, dict)), None)
    if asset_b != asset_a:
        facts.append("Đổi sang hình khác")
    elif rb[1] != ra[1] and (rb[1] or ra[1]):
        new = region_label(assets, ra[0] or asset_a, ra[1])
        old = region_label(assets, rb[0] or asset_b, rb[1])
        facts.append("Nhìn vào %s%s" % (new, (" thay vì %s" % old) if old else "") if new else "Bỏ vùng nhìn đã chọn")
    pairs, added, removed = _match_overlays(before.get("overlays") or [], after.get("overlays") or [])
    for o in added:
        facts.append("Thêm: " + _overlay_phrase(bundle, o, assets, asset_a))
    for o in removed:
        facts.append("Bỏ " + _overlay_phrase(bundle, o, assets, asset_b) if _is_text(o.get("technique")) else "Bỏ: " + _overlay_phrase(bundle, o, assets, asset_b))
    for b, a in pairs:
        if _clean({k: v for k, v in b.items() if not str(k).startswith("_")}) != _clean({k: v for k, v in a.items() if not str(k).startswith("_")}):
            facts.append("Chỉnh: " + _overlay_phrase(bundle, a, assets, asset_a))
    if _clean(before.get("transition_in")) != _clean(after.get("transition_in")):
        facts.append("Đổi cách chuyển vào cảnh")
    if (before.get("note") or "") != (after.get("note") or ""):
        facts.append("Đổi ghi chú của cảnh")
    if not facts:
        facts.append("Chỉnh lại cảnh")
    return facts


def added_facts(shot: dict, *, bundle=None) -> list[str]:
    bundle = bundle or _bundle(shot)
    return ["Thêm cảnh: " + tech_label(bundle, shot.get("technique"))]


def removed_facts(shot: dict, *, bundle=None) -> list[str]:
    return ["Xóa cảnh"]


def sentence_from_facts(facts: list[str]) -> str:
    return "; ".join(f.rstrip(".") for f in facts) + "."


def what_for(model_what, facts: list[str]) -> tuple[str, str]:
    """(sentence, source): the model's sentence when it passes the check, else one built from the facts."""
    if sentence_ok(model_what):
        return model_what.strip(), "model"
    return sentence_from_facts(facts), "code"


def code_summary(changes: list[dict]) -> str:
    """'Đã sửa 4 cảnh, thêm 1 cảnh: Máy quay đi chậm hơn; Thêm: vòng khoanh ...' from the turn's changes (their `facts`)."""
    ch = [c for c in changes if c.get("op") == "changed"]
    ad = [c for c in changes if c.get("op") == "added"]
    rm = [c for c in changes if c.get("op") == "removed"]
    parts = []
    if ch:
        parts.append("sửa %d cảnh" % len(ch))
    if ad:
        parts.append("thêm %d cảnh" % len(ad))
    if rm:
        parts.append("xóa %d cảnh" % len(rm))
    if not parts:
        return "Không có gì thay đổi."
    seen: list[str] = []
    for c in ch + ad + rm:
        for f in c.get("facts") or []:
            if f not in seen:
                seen.append(f)
    head = "Đã " + ", ".join(parts)
    tail = "; ".join(seen[:3])
    return head + (": " + tail if tail else "") + "."


def summary_for(model_summary, changes: list[dict]) -> tuple[str, str]:
    if sentence_ok(model_summary):
        return model_summary.strip(), "model"
    return code_summary(changes), "code"
