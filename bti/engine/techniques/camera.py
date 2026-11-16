"""Camera family over the designed matte: CAM-01, 03, 04, 05, STATIC-01 (matte hold) and X-LAY-01 (context still).

All of them are one renderer: a keyframed virtual camera (param `camera`) looking at the shot's image on the
backdrop with a soft shadow.  The ids differ in their *default camera* (see `default_params`) and in intent.
Lifted from build_v2.py `painting_shot` / `still_shot` and vfx.Cam / compose_matte.
"""
from __future__ import annotations

from ..base import BaseRenderer, View
from ..registry import technique
from ..vfx import Cam, compose_matte

CANVAS_W, CANVAS_H = 1920, 1080


def camera_keys(shot: dict, ctx, name="camera"):
    """[(t, cx, cy, zoom, ease)] in absolute seconds from the shot's camera param (anchors already resolved)."""
    keys = (shot.get("params") or {}).get(name)
    if not keys:
        return None
    out = []
    for k in keys:
        out.append((ctx.t(k["at"], shot), float(k["cx"]), float(k["cy"]), float(k["zoom"]), k.get("ease", "linear")))
    return out


def fit_zoom(h: float, pct: float = 95.5, canvas_h: int = CANVAS_H) -> float:
    """Zoom at which the whole asset height is `pct` % of the frame (STATIC-01 painting_height_pct)."""
    return pct / 100.0 * canvas_h / h


def _focus_point(context: dict, asset: dict):
    f = context.get("focus")
    if isinstance(f, str):
        r = (asset.get("regions") or {}).get(f)
        if r:
            return float(r["x"]), float(r["y"])
    elif isinstance(f, (list, tuple)) and len(f) == 2:
        return float(f[0]), float(f[1])
    return asset["w"] / 2.0, asset["h"] / 2.0


def _key(rel, cx, cy, z, ease="linear"):
    return {"at": {"rel": rel}, "cx": round(cx, 2), "cy": round(cy, 2), "zoom": round(z, 5), "ease": ease}


@technique("STATIC-01", "base")
@technique("CAM-01", "base")
@technique("CAM-03", "base")
@technique("CAM-04", "base")
@technique("CAM-05", "base")
@technique("X-LAY-01", "base")
class MatteShot(BaseRenderer):
    """Image on the matte with a keyframed camera. params: camera (list of keys), shadow (bool)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.key = self.slot_asset("image")
        keys = camera_keys(shot, ctx)
        if keys is None:                               # no camera given: static, whole image fitted
            w, h = ctx.asset_size(self.key)
            keys = [(self.t0, w / 2.0, h / 2.0, fit_zoom(h), "linear")]
        self.cam = Cam(keys)

    def view(self, t):
        cx, cy, z = self.cam.at(t)
        return View(cx, cy, z, self.ctx.image(self.key), self.key)

    def render(self, t):
        v = self.view(t)
        return compose_matte(v.img, v.cx, v.cy, v.z, self.ctx.w, self.ctx.h, shadow=bool(self.p["shadow"]))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        asset = context.get("asset") or {}
        if not asset.get("w") or not asset.get("h"):
            return {p["name"]: p["default"] for p in spec["params"]}
        w, h = float(asset["w"]), float(asset["h"])
        pct = 95.5
        for p in (bundle.by_id.get("STATIC-01") or {}).get("params", []):
            if p["name"] == "painting_height_pct":
                pct = p["default"]
        fit = fit_zoom(h, pct)
        cx0, cy0 = _focus_point(context, asset)
        cur = context.get("camera") or {}
        z_now = cur.get("zoom")
        pre = lambda name, field, d: ((bundle.sv("camera_presets", name) or {}).get(field, d))
        if tid == "X-LAY-01":                          # context still: whole image at 94 % height, slow push
            z = 0.94 * CANVAS_H / h
            keys = [_key(0.0, w / 2, h / 2, z), _key(1.0, w / 2, h / 2, z * 1.06)]
        elif tid == "CAM-01":                          # push in
            z0 = z_now or fit
            keys = [_key(0.0, cx0, cy0, z0), _key(1.0, cx0, cy0, z0 * pre("excerpt_push_in", "zoom_in_ratio", 1.142))]
        elif tid == "CAM-03":                          # pull back
            r = pre("excerpt_pull_back", "zoom_out_ratio", 1.312)
            keys = [_key(0.0, cx0, cy0, (z_now or fit * r), "in_quad"), _key(1.0, w / 2, h / 2, fit)]
        elif tid == "CAM-04":                          # pan up
            z = max(fit, 1920.0 / w)
            ext = pre("excerpt_pan_up", "extent_pct_height", 16.6) / 100.0 * CANVAS_H / z
            keys = [_key(0.0, cx0, cy0 + ext / 2, z), _key(1.0, cx0, cy0 - ext / 2, z)]
        elif tid == "CAM-05":              # zoom and shift
            z0 = z_now or fit
            r = pre("excerpt_zoom_shift", "zoom_in_ratio", 1.51)
            z1 = z0 * r
            if context.get("focus") is not None:
                ex, ey = cx0, cy0
            else:
                ex = w / 2 + pre("excerpt_zoom_shift", "shift_pct_width", 15) / 100.0 * CANVAS_W / z1
                ey = h / 2 + pre("excerpt_zoom_shift", "shift_pct_height", 14) / 100.0 * CANVAS_H / z1
            keys = [_key(0.0, w / 2, h / 2, z0), _key(1.0, ex, ey, z1)]
        else:                                          # STATIC-01: matte hold with a slow drift
            keys = [_key(0.0, w / 2, h / 2, fit * 0.97), _key(1.0, w / 2, h / 2, fit * 1.04)]
        return {"camera": keys, "shadow": True}
