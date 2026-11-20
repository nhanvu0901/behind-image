"""The plain sentence of a shot ("Zoom vào khuôn mặt · vòng sáng"), for `shots.md`.

This is the Python twin of `bti/editor/static/js/shotsentence.js` (the page's list of shots), made from the same pieces: the registry's Vietnamese names (`label_vi`), the
picture and the region the shot shows, and the overlays on it; the phrase table is `SHOT_WORDS` of `labels.js`, copied below. The two stay in step by ONE shared set of cases:
`tests/output/fixtures/shot_cases.json` holds real shots with the sentences the JavaScript function made for them (`node tests/output/shotsentence_parity.test.mjs`
checks the JavaScript side against it, `tests/output/test_shotwords.py` the Python side), so a change to either side that is not made on the other fails a test.
To change a phrase: change `labels.js` and this table, then regenerate the cases with `UPDATE_GOLDEN=1 node --test tests/output/shotsentence_parity.test.mjs`.

No id of a technique, no file name and no parameter name ever reaches a sentence: when nothing is known the answer is "Một cảnh"."""
from __future__ import annotations

import math
import re
from typing import Any, Callable

from bti.draft.zones import OPENING_ID

MAX = 96
ID_LOOKING = re.compile(r"^[A-Z0-9_]{2,}$")
VI = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)
LOOKS_RAW = re.compile(r"\b[A-Z]{1,6}-[A-Z0-9]{1,3}(-\d+)?\b|\b[a-z]+_[a-z_]+\b|\.(jpg|png|mp4|json)\b")

# ---- labels.js SHOT_WORDS (keep in step; see the module doc)
UNKNOWN = "Một cảnh"
JOINER = " · "
WHOLE = "cả bức tranh"
PAINTING = "bức tranh"
DETAIL = "một chi tiết của tranh"
CAMERA = {
    "CAM-01": {"lead": "Zoom vào", "use": "focus"},
    "CAM-03": {"lead": "Kéo ra, thấy", "use": "whole"},
    "CAM-04": {"lead": "Lia lên", "use": "focus"},
    "CAM-05": {"lead": "Zoom kèm dịch", "use": "focus", "prep": "tới", "otherwise": "trên"},
    "CAM-06": {"lead": "Giữ yên", "use": "target", "tail": ", hiện nhãn"},
    "STATIC-01": {"lead": "Giữ yên", "use": "target"},
    "X-LAY-01": {"lead": "Ảnh tĩnh:", "use": "target"},
}
NAMES = {"MAP-01": "Bản đồ", "STATIC-06": "Bản đồ và tuyến", "TIME-01": "Trục thời gian", "TREE-01": "Sơ đồ quan hệ", "STATE-01": "Một tranh, hai trạng thái"}
CARD = {"X-CARD-01": "Thẻ chương", "X-CARD-02": "Thẻ tiêu đề", "X-CARD-03": "Credit cuối phim", "X-CARD-04": "Thẻ câu hỏi", "TXT-01": "Tiêu đề chương", "ID-MARK-01": "Mốc chương",
        "ID-MARK-02": "Mốc chương", "ID-BRAND-01": "Tên kênh", "ID-BRAND-02": "Tên kênh", "ID-BRAND-03": "Tên kênh và tựa video"}
OPENING = "Mở đầu: cả bức tranh"       # the program's opening shot (the shot with the reserved id `bti.draft.zones.OPENING_ID`)
OVERLAY = {
    "HI-01": "vòng sáng", "AN-01": "khoanh tròn", "AN-02": "viền quanh", "AN-03": "tia phối cảnh", "AN-05": "thước kích thước", "AN-06": "lưới", "X-ANN-01": "nhãn chi tiết",
    "X-ANN-02": "nhãn tác phẩm", "X-ANN-03": "nhãn tóm tắt", "X-ANN-04": "viền từng nhóm", "X-ANN-05": "chấm bản đồ", "AN-04": "bản đồ có đường đi", "X-HI-01": "làm tối xung quanh",
    "STATIC-02": "nhãn nguồn", "STATIC-04": "trích dẫn", "STATIC-05": "nhãn tên người", "STATIC-08": "nhãn tên", "STATIC-09": "năm", "HI-03": "giữ màu chủ thể", "TXT-02": "chữ chạy ngang",
    "KEY-01": "nhãn các phần của tranh", "NUM-01": "con số lớn", "DOC-01": "làm sáng dòng chữ", "SHORT-04": "nhãn vàng", "ID-OPEN-01": "mở đầu vệt sáng", "ID-OPEN-02": "mở đầu tối lại",
    "ID-LABEL-01": "nhãn tác phẩm",
}


def _other(title: str) -> str:
    return "ảnh “%s”" % title if title else "một hình khác"


def _clip_word(title: str, sec: int) -> str:
    return "clip%s%s" % (" “%s”" % title if title else "", ", %d giây" % sec if sec else "")


def _quoted(label: str) -> str:
    return "“%s”" % label


def _and_more(n: int) -> str:
    return "và %d lớp khác" % n


def _more_images(n: int) -> str:
    return "và %d ảnh khác" % n


def _more_places(n: int) -> str:
    return "và %d nơi khác" % n


def _two_of(a: str, b: str) -> str:
    return "%s và %s" % (a, b)


# ---- helpers (the small functions of shotsentence.js)
def is_vietnamese(s: Any) -> bool:
    return bool(VI.search(str(s or "")))


def _text(v: Any) -> str:
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else ""


def _clip(s: Any, n: int = MAX) -> str:
    t = re.sub(r"\s+", " ", str(s)).strip()
    return t[: n - 1].rstrip() + "…" if len(t) > n else t


def _lower_first(s: str) -> str:
    return s[0].lower() + s[1:] if s else s


def _sentence_case(s: str) -> str:
    return s[0] + s[1:].lower() if len(s) > 3 and s == s.upper() and s != s.lower() else s


def _short_title(s: str, n: int = 30) -> str:
    return s[: n - 1].rstrip() + "…" if len(s) > n else s


def _list(v: Any) -> list:
    return v if isinstance(v, list) else []


def _dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _isobj(v: Any) -> bool:
    return isinstance(v, dict)


def _num(v: Any) -> float:
    """`Number(v)` of JavaScript for the values that matter here: a number, a numeric string, else NaN."""
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v) if v.strip() else 0.0
        except ValueError:
            return math.nan
    return math.nan


def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _round(x: float) -> int:
    return int(math.floor(x + 0.5))


def main_asset_key(draft: dict, painting_title: str = "") -> str | None:
    """The asset key of the main painting: the one whose title is the project's painting, else the picture the base slots of the storyboard use most."""
    assets = _dict(_dict(draft).get("assets"))
    want = _text(painting_title).lower()
    if want:
        for k, a in assets.items():
            if _text(_dict(a).get("title")).lower() == want and (_dict(a).get("kind") or "image") == "image":
                return k
    n: dict[str, int] = {}
    for s in _list(_dict(draft).get("shots")):
        for v in _dict(_dict(s).get("slots")).values():
            k = _dict(v).get("asset")
            if k and k in assets and (_dict(assets[k]).get("kind") or "image") == "image":
                n[k] = n.get(k, 0) + 1
    if not n:
        return None
    return sorted(n, key=lambda k: (-n[k], k))[0]


def region_words(asset: dict, key: str) -> str:
    label = _text(_dict(_dict(_dict(asset).get("regions")).get(key)).get("label"))
    if not label or ID_LOOKING.search(label):
        return DETAIL
    return _lower_first(label) if is_vietnamese(label) else _quoted(label)


def camera_focus(shot: dict, asset: dict) -> str | None:
    keys = [k for k in _list(_dict(_dict(shot).get("params")).get("camera")) if isinstance(k, dict) and _finite(k.get("cx")) and _finite(k.get("cy")) and _finite(k.get("zoom"))]
    regions = _dict(asset).get("regions")
    if not keys or not isinstance(regions, dict) or not regions:
        return None
    first, last = keys[0], keys[-1]
    if len(keys) > 1 and last["zoom"] < first["zoom"] * 1.05:
        return None
    best, area = None, math.inf
    for name, r in regions.items():
        r = _dict(r)
        rx = _num(r.get("rx"))
        rx = rx if rx > 0 else None
        ry_raw = _num(r.get("ry"))
        ry = ry_raw if ry_raw > 0 else rx
        if not rx or not ry:
            continue
        rxv, ryv = _num(r.get("x")), _num(r.get("y"))
        if ((last["cx"] - rxv) / rx) ** 2 + ((last["cy"] - ryv) / ry) ** 2 > 1:        # a NaN comparison is false, as in JavaScript
            continue
        if rx * ry < area:
            area, best = rx * ry, name
    return best


def _slot_targets(shot: dict, tech: dict, env: dict) -> list[dict]:
    out = []
    slots = [s for s in _list(_dict(tech).get("slots")) if isinstance(s, dict) and s.get("type") in ("image", "video")]
    assets = _dict(env.get("assets"))
    for s in slots:
        if re.fullmatch(r"mask(_\d+)?", str(s.get("name") or "")):
            continue
        v = _dict(_dict(_dict(shot).get("slots")).get(s.get("name")))
        key = v.get("asset")
        asset = assets.get(key) if key else None
        if not asset or (_dict(asset).get("kind") or "image") == "mask":
            continue
        out.append({"slot": s.get("name"), "key": key, "asset": asset, "region": v.get("region") or None,
                    "video": _dict(asset).get("kind") == "video" or s.get("type") == "video", "main": key == env.get("mainKey")})
    return out


def _phrase_of(t: dict) -> str:
    a = _dict(t["asset"])
    if t["video"]:
        d = _num(a.get("duration"))
        return _clip_word(_short_title(_text(a.get("title"))), _round(d) if math.isfinite(d) and d > 0 else 0)
    if t["region"]:
        return region_words(a, t["region"])
    return WHOLE if t["main"] else _other(_short_title(_text(a.get("title"))))


def _join_phrases(ps: list[str], mx: int = 2) -> str:
    u = list(dict.fromkeys(ps))
    if len(u) <= 1:
        return u[0] if u else ""
    if len(u) == 2:
        return _two_of(u[0], u[1])
    return "%s %s" % (", ".join(u[:mx]), _more_images(len(u) - mx))


def _place_name(p: Any) -> str:
    return _text(_dict(p).get("name"))


def _map_sentence(shot: dict, name: str) -> str:
    P = _dict(shot.get("params"))
    places = _list(P.get("places"))
    by_id = {str(_dict(p).get("id") if _dict(p).get("id") is not None else ""): _place_name(p) for p in places}
    named = [n for n in (_place_name(p) for p in places) if n]
    routes = _list(P.get("route"))
    r = routes[0] if routes and routes[0] else (P.get("route") if _isobj(P.get("route")) else None)
    a = by_id.get(str(_dict(r).get("from") if _dict(r).get("from") is not None else ""), "") if r else ""
    b = by_id.get(str(_dict(r).get("to") if _dict(r).get("to") is not None else ""), "") if r else ""
    if a and b:
        return "%s: %s tới %s" % (name, a, b)
    f, t = _text(P.get("from_label")), _text(P.get("to_label"))
    if f and t:
        return "%s: %s tới %s" % (name, f, t)
    if len(named) == 1:
        return "%s: %s" % (name, named[0])
    if len(named) == 2:
        return "%s: %s" % (name, _two_of(named[0], named[1]))
    if len(named) > 2:
        return "%s: %s %s" % (name, ", ".join(named[:2]), _more_places(len(named) - 2))
    return name


def _explainer(shot: dict, tech: dict, tid: str) -> str | None:
    P = _dict(shot.get("params"))
    name = NAMES.get(tid) or _text(tech.get("label_vi"))
    if tid in ("MAP-01", "STATIC-06"):
        return _map_sentence(shot, name)
    if tid == "TIME-01":
        n = len(_list(P.get("items")))
        return "%s: %d mốc" % (name, n) if n > 0 else name
    if tid == "TREE-01":
        n = len(_list(P.get("nodes")))
        return "%s: %d người" % (name, n) if n > 0 else name
    if tid == "STATE-01":
        a, b = _text(P.get("label_a")), _text(P.get("label_b"))
        return "%s: %s" % (name, _two_of(a, b)) if a and b else name
    return None


def _card_sentence(shot: dict, tid: str) -> str | None:
    base = CARD.get(tid)
    if not base:
        return None
    P = _dict(shot.get("params"))
    t = _text(P.get("title")) or _text(P.get("text"))
    return "%s: %s" % (base, _clip(_sentence_case(t), 40)) if t and not ID_LOOKING.search(t) else base


def _camera_sentence(shot: dict, tech: dict, targets: list[dict]) -> str | None:
    spec = CAMERA.get(tech.get("id"))
    if not spec:
        return None
    t = targets[0] if targets else None
    tail = spec.get("tail", "")
    if spec["use"] == "whole":
        return "%s %s" % (spec["lead"], WHOLE)
    other = (" " + spec["otherwise"]) if spec.get("otherwise") else ""
    if not t:
        return "%s%s %s%s" % (spec["lead"], other, PAINTING, tail)
    if t["video"] or spec["use"] == "target":
        return "%s %s%s" % (spec["lead"], _phrase_of(t), tail)
    region = t["region"] or camera_focus(shot, t["asset"])
    if region:
        prep = (" " + spec["prep"]) if spec.get("prep") else ""
        return "%s%s %s%s" % (spec["lead"], prep, region_words(t["asset"], region), tail)
    return "%s%s %s%s" % (spec["lead"], other, WHOLE if t["main"] else _other(_short_title(_text(_dict(t["asset"]).get("title")))), tail)


def _base_sentence(shot: dict, tech: dict, env: dict) -> str:
    tid, label = tech.get("id"), _text(tech.get("label_vi"))
    targets = _slot_targets(shot, tech, env)
    own = _explainer(shot, tech, tid) or _card_sentence(shot, tid) or _camera_sentence(shot, tech, targets)
    if own:
        return own
    what = _join_phrases([_phrase_of(t) for t in targets])
    if not label:
        return "%s: %s" % (UNKNOWN, what) if what else ""
    return "%s: %s" % (label, what) if what else label


def overlay_phrases(shot: dict, env: dict) -> list[str]:
    tech = env.get("tech")
    order: list[str] = []
    n: dict[str, int] = {}
    for o in _list(_dict(shot).get("overlays")):
        oid = _dict(o).get("technique")
        t = tech(oid) if callable(tech) else None
        phrase = OVERLAY.get(oid) or _lower_first(_text(_dict(t).get("label_vi")))
        if not phrase:
            continue
        if phrase not in n:
            order.append(phrase)
        n[phrase] = n.get(phrase, 0) + 1
    return ["%d %s" % (n[p], p) if n[p] > 1 else p for p in order]


def shot_sentence(shot: Any, env: dict | None = None) -> str:
    """The sentence of a shot. Never empty and never an id. `env`: {tech: id -> registry entry | None, assets: {key: asset}, mainKey: key | None}."""
    env = env or {}
    shot = shot if isinstance(shot, dict) else {}
    tech_fn = env.get("tech")
    tech = (tech_fn(shot.get("technique")) if callable(tech_fn) else None) or None
    base = ""
    if shot.get("id") == OPENING_ID:
        base = OPENING
    elif tech and _text(tech.get("label_vi")):
        try:
            base = _base_sentence(shot, tech, env)
        except Exception:         # noqa: BLE001 - as the page does: the name of the technique stands in
            base = _text(tech.get("label_vi"))
    ov = overlay_phrases(shot, env)
    shown = ov[:3] + [_and_more(len(ov) - 3)] if len(ov) > 3 else ov
    return _clip(JOINER.join([base or UNKNOWN] + shown))


def looks_raw(s: str) -> bool:
    """The words that show that a sentence is not plain: an id of a technique, an underscore name or a raw file name."""
    return bool(LOOKS_RAW.search(str(s)))


def env_of(techniques: Any, assets: dict, main_key: str | None) -> dict:
    """An `env` from a registry (a list of technique entries, a dict id -> entry, or a function id -> entry)."""
    if callable(techniques):
        tech = techniques
    elif isinstance(techniques, dict):
        tech = techniques.get
    else:
        by = {t.get("id"): t for t in techniques or [] if isinstance(t, dict)}
        tech = by.get
    return {"tech": tech, "assets": assets or {}, "mainKey": main_key}
