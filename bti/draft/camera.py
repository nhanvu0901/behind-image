"""Program-computed camera moves for shots on the main painting (worker boxcam).

The storyboard model names the target region (`slots.image.region`; omitted = whole painting) and optionally where the move starts
(`"from": "previous"` | `"whole"` | `"<REGION>"`); the compiler calls `build_main_camera` to compute every keyframe from `bti.engine.viewchecks.region_frame`.
"""
from __future__ import annotations

import math

from bti.engine import viewchecks as VC
from bti.engine.timing import AnchorError, Timing

OFFERED_CAMERA_TECHNIQUES = ("CAM-01", "CAM-03", "CAM-04", "CAM-05", "STATIC-01")

ARRIVE_BEFORE_WORD_S = 0.30     # arrive at least 0.3 s before the naming overlay's word
ARRIVE_DEFAULT_FRAC = 0.45      # without a naming word, arrive by 45% of the shot
HOLD_MIN_S = 2.0                # end hold requirement (matches VC.ARRIVE_MIN_S)
HOLD_MIN_SHARE = 0.55           # or 55% of the shot (matches VC.ARRIVE_MIN_SHARE)
MIN_TRAVEL_S = 0.60             # shorter than this cannot comfortably ease across a painting
MAX_TRAVEL_SPEED = 0.35         # frame-widths / second (derived from stored Arnolfini storyboard speeds)
ZOOM_RATE_MAX = 1.0             # octaves / second: abs(log2(end_zoom / start_zoom)) / travel_s <= 1.0
HOLD_PUSH_PCT = 0.04            # gentle push after early arrival so the frame stays alive without losing the detail
SAME_REGION_PUSH_PCT = 0.08     # start 8% wider on same-region push / no-race fallback
PULL_START_PCT = 0.18           # default tighter start when CAM-03 has no prior frame
STATIC_DRIFT_PCT = 0.03         # gentle matte drift for STATIC-01


def _key(rel: float, frame: tuple[float, float, float], ease: str = "linear") -> dict:
    return {"at": {"rel": round(float(rel), 4)}, "cx": round(float(frame[0]), 2),
            "cy": round(float(frame[1]), 2), "zoom": round(float(frame[2]), 5), "ease": ease}


def _travel_speed_fw(a: tuple[float, float, float], b: tuple[float, float, float], dur: float) -> float:
    """Travel speed between poses `a` and `b` over `dur` seconds in frame-widths/second (midpoint frame width)."""
    fw_mid = 1920.0 / math.sqrt(max(1e-6, float(a[2]) * float(b[2])))
    return math.hypot(b[0] - a[0], b[1] - a[1]) / fw_mid / max(1e-6, float(dur))


def _dist_fw(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    fw_mid = 1920.0 / math.sqrt(max(1e-6, float(a[2]) * float(b[2])))
    return math.hypot(b[0] - a[0], b[1] - a[1]) / fw_mid


def _zoom_rate(a: tuple[float, float, float], b: tuple[float, float, float], dur: float) -> float:
    """Zoom rate between poses `a` and `b` over `dur` seconds in octaves/second."""
    z0 = max(1e-6, float(a[2]))
    z1 = max(1e-6, float(b[2]))
    return abs(math.log2(z1 / z0)) / max(1e-6, float(dur))


def _arrive_time(dur: float, t0: float, naming_t: float | None) -> float:
    """Latest arrival offset (seconds into the shot) satisfying early arrival and >= min(2.0s, 55%*dur) hold."""
    hold_need = min(HOLD_MIN_S, HOLD_MIN_SHARE * dur)
    t_hold_cap = max(0.0, dur - hold_need)
    t_name_cap = ((naming_t - t0) - ARRIVE_BEFORE_WORD_S) if naming_t is not None else (ARRIVE_DEFAULT_FRAC * dur)
    return max(0.0, min(t_name_cap, t_hold_cap))


def naming_overlay_time(overlays: list | None, region_name: str | None, tm: Timing, t0: float, t1: float) -> float | None:
    """Earliest start time (in video seconds) of a spotlight or label targeting `region_name` inside `[t0, t1]`."""
    if not region_name or not overlays or tm is None:
        return None
    hits: list[float] = []
    for ov in overlays:
        if not isinstance(ov, dict):
            continue
        tid = ov.get("technique")
        p = ov.get("params") if isinstance(ov.get("params"), dict) else {}
        matched = False
        if tid in ("HI-01", "X-HI-01", "AN-01") and p.get("at") == region_name:
            matched = True
        elif tid in ("X-ANN-01", "X-ANN-02", "X-ANN-03"):
            matched = True
        elif tid == "KEY-01":
            for it in p.get("labels") or []:
                if isinstance(it, dict) and it.get("ref") == region_name and isinstance(it.get("at"), dict):
                    try:
                        kt = tm.resolve(it["at"])
                        hits.append(max(t0, min(t1, kt)))
                    except (AnchorError, KeyError, TypeError):
                        pass
        if matched and isinstance(ov.get("start"), dict):
            try:
                ot = tm.resolve(ov["start"])
                hits.append(max(t0, min(t1, ot)))
            except (AnchorError, KeyError, TypeError):
                pass
    return min(hits) if hits else None


def _build_main_camera(tid: str, region_name: str | None, from_ref: str | None, asset: dict, box,
                       prev_frame: tuple[float, float, float] | None, t0: float, t1: float,
                       overlays: list | None = None, tm: Timing | None = None, *,
                       fit_pct: float = VC.WHOLE_FIT_PCT, frame_fill: float | None = None,
                       sharp_zoom: float | None = None) -> list[dict]:
    """Compute `[key, ...]` camera keys for an offered main-painting camera shot (`CAM-01/03/04/05`, `STATIC-01`)."""
    w = float(asset.get("width") or 1920.0)
    h = float(asset.get("height") or 1080.0)
    pbox = box if (isinstance(box, (list, tuple)) and len(box) == 4 and box[2] > box[0] and box[3] > box[1]) else (0.0, 0.0, w, h)
    regs = asset.get("regions") or {}
    reg = regs.get(region_name) if isinstance(region_name, str) else None
    rbox = VC.region_point_box(reg)

    whole = VC.whole_painting_frame(w, h, pbox, fit_pct=fit_pct)
    z_cap = VC.sharp_limit(w, h, sharp_zoom=sharp_zoom)
    z_cov = VC.cover_zoom(w, h, pbox)
    can_fill = z_cov <= z_cap + 1e-9
    z_floor = max(whole[2], z_cov) if (reg is not None and can_fill) else whole[2]
    dur = max(0.2, float(t1) - float(t0))

    travel = (
        VC.region_travel_frames(
            reg, w, h, pbox, fit_pct=fit_pct, frame_fill=frame_fill, sharp_zoom=sharp_zoom,
            regions=regs, region_name=region_name, dur=dur, max_speed=MAX_TRAVEL_SPEED,
        )
        if reg is not None else None
    )
    end = (
        travel["head"]
        if travel is not None
        else VC.region_frame(reg, w, h, pbox, fit_pct=fit_pct, frame_fill=frame_fill,
                             sharp_zoom=sharp_zoom, regions=regs, region_name=region_name)
    )
    t_name = naming_overlay_time(overlays, region_name, tm, t0, t1) if (region_name and tm is not None) else None
    t_arr = _arrive_time(dur, t0, t_name)

    def clamp(cx: float, cy: float, z: float) -> tuple[float, float, float]:
        z_eff = max(z_floor, float(z)) if reg is not None else float(z)
        return VC.fit_frame_to_box(cx, cy, z_eff, w, h, pbox, fit_pct=fit_pct, z_cap=z_cap)

    def filling_default() -> tuple[float, float, float]:
        if reg is not None and can_fill:
            return VC.fit_frame_to_box(end[0], end[1], z_cov, w, h, pbox, fit_pct=fit_pct, z_cap=z_cap)
        return whole

    def resolve_from(ref: str | None) -> tuple[float, float, float]:
        if ref == "whole":
            return whole
        if ref in (None, "previous"):
            return prev_frame if prev_frame is not None else filling_default()
        target_reg = regs.get(ref) if isinstance(ref, str) else None
        if target_reg is not None:
            return VC.region_frame(target_reg, w, h, pbox, fit_pct=fit_pct, frame_fill=frame_fill,
                                   sharp_zoom=sharp_zoom, regions=regs, region_name=ref)
        return prev_frame if prev_frame is not None else filling_default()

    def ensure_rbox(frame: tuple[float, float, float], target_end: tuple[float, float, float]) -> tuple[float, float, float]:
        """If clamping pushed `frame` so high in zoom that `rbox` is no longer inside it, fall back safely toward `target_end`."""
        if rbox is not None and not VC.box_inside_frame(rbox, *frame)[0]:
            return target_end
        return frame

    def push_on_end(pct: float = SAME_REGION_PUSH_PCT, ease: str = "inout_sine") -> list[dict]:
        if reg is None:
            # Whole painting: keep whole painting fit at start and gently drift in without clipping.
            end_drift = clamp(whole[0], whole[1], min(z_cap, whole[2] * (1.0 + min(pct, 0.035))))
            return [_key(0.0, whole, ease), _key(1.0, end_drift, "linear")]
        z0 = max(z_floor, end[2] / (1.0 + pct))
        start = ensure_rbox(clamp(end[0], end[1], z0), end)
        # If zoom was already near whole/cover floor so z0 == end[2], try a tiny inward push without exceeding sharp limit.
        if abs(end[2] - start[2]) < 1e-4 and end[2] * (1.0 + 0.03) <= z_cap + 1e-6:
            end_pushed = ensure_rbox(clamp(end[0], end[1], min(z_cap, end[2] * 1.03)), end)
            return [_key(0.0, start, ease), _key(1.0, end_pushed, "linear")]
        return [_key(0.0, start, ease), _key(1.0, end, "linear")]

    def travel_to_end(start: tuple[float, float, float], travel_ease: str = "inout_cubic",
                      fallback_pct: float = SAME_REGION_PUSH_PCT, fallback_ease: str = "inout_sine") -> list[dict]:
        dist = _dist_fw(start, end)
        z_ratio = abs(end[2] / max(1e-6, start[2]) - 1.0)
        if dist < 0.05 and z_ratio < 0.08:
            return push_on_end(fallback_pct, fallback_ease)
        if t_arr < MIN_TRAVEL_S:
            return push_on_end(fallback_pct, fallback_ease)
        speed = dist / t_arr
        if speed > MAX_TRAVEL_SPEED + 1e-9 or _zoom_rate(start, end, t_arr) > ZOOM_RATE_MAX + 1e-9:
            return push_on_end(fallback_pct, fallback_ease)
        arrive_rel = max(0.05, min(0.90, t_arr / dur))
        z_arr = max(z_floor, end[2] / (1.0 + HOLD_PUSH_PCT))
        arr = ensure_rbox(clamp(end[0], end[1], z_arr), end)
        return [_key(0.0, start, travel_ease), _key(arrive_rel, arr, "linear"), _key(1.0, end, "linear")]

    # Oversized tall/wide regions: stay at filling zoom and travel from head end to tail end, or hold head end when short.
    if travel is not None:
        head_pose = travel["head"]
        tail_pose = travel["tail"]
        head_box = travel["head_box"]

        def ensure_head(frame: tuple[float, float, float], target_pose: tuple[float, float, float]) -> tuple[float, float, float]:
            if head_box is not None and not VC.box_inside_frame(head_box, *frame)[0]:
                return target_pose
            return frame

        def hold_head(pose: tuple[float, float, float], pct: float = SAME_REGION_PUSH_PCT,
                      ease: str = "inout_sine") -> list[dict]:
            z0 = max(z_floor, pose[2] / (1.0 + pct))
            start = ensure_head(clamp(pose[0], pose[1], z0), pose)
            if abs(pose[2] - start[2]) < 1e-4 and pose[2] * 1.03 <= z_cap + 1e-6:
                end_pushed = ensure_head(clamp(pose[0], pose[1], min(z_cap, pose[2] * 1.03)), pose)
                return [_key(0.0, start, ease), _key(1.0, end_pushed, "linear")]
            return [_key(0.0, start, ease), _key(1.0, pose, "linear")]

        def direct_travel() -> list[dict]:
            dist_ht = _dist_fw(head_pose, tail_pose)
            if dur < MIN_TRAVEL_S or dist_ht < 0.05 or dist_ht / dur > MAX_TRAVEL_SPEED + 1e-9:
                return hold_head(head_pose, SAME_REGION_PUSH_PCT, "inout_sine")
            if t_name is not None and head_box is not None and t_name > t0 + 1e-6:
                pose_at_name = VC.camera_at([(t0, *head_pose, "inout_sine"), (t1, *tail_pose, "linear")], t_name)
                if not VC.box_inside_frame(head_box, *pose_at_name)[0]:
                    hold_s = min(dur - MIN_TRAVEL_S, max(0.0, t_name - t0))
                    rem = dur - hold_s
                    if rem >= MIN_TRAVEL_S:
                        t_rem = VC.region_travel_frames(
                            reg, w, h, pbox, fit_pct=fit_pct, frame_fill=frame_fill, sharp_zoom=sharp_zoom,
                            regions=regs, region_name=region_name, dur=rem, max_speed=MAX_TRAVEL_SPEED,
                        )
                        if t_rem is not None:
                            d_rem = _dist_fw(t_rem["head"], t_rem["tail"])
                            if d_rem >= 0.05 and d_rem / rem <= MAX_TRAVEL_SPEED + 1e-9:
                                hold_rel = max(0.05, min(0.90, hold_s / dur))
                                t_hold = t0 + hold_rel * dur
                                keys_chk = [(t0, *t_rem["head"], "linear"), (t_hold, *t_rem["head"], "inout_sine"), (t1, *t_rem["tail"], "linear")]
                                if VC.box_inside_frame(head_box, *VC.camera_at(keys_chk, t_name))[0]:
                                    return [_key(0.0, t_rem["head"], "linear"),
                                            _key(hold_rel, t_rem["head"], "inout_sine"),
                                            _key(1.0, t_rem["tail"], "linear")]
                    return hold_head(head_pose, HOLD_PUSH_PCT, "inout_sine")
            return [_key(0.0, head_pose, "inout_sine"), _key(1.0, tail_pose, "linear")]

        if tid == "STATIC-01":
            return hold_head(head_pose, STATIC_DRIFT_PCT, "linear")

        prior_start: tuple[float, float, float] | None = None
        prior_ease = "inout_cubic"
        if tid == "CAM-01":
            prior_ease = "inout_sine"
            if from_ref is not None:
                prior_start = resolve_from(from_ref)
            elif prev_frame is not None and prev_frame[2] <= head_pose[2] * 1.02 and (not can_fill or prev_frame[2] >= z_cov - 1e-5):
                prior_start = prev_frame
        elif tid == "CAM-03":
            prior_ease = "inout_cubic"
            if from_ref is not None:
                prior_start = resolve_from(from_ref)
            elif prev_frame is not None and prev_frame[2] > head_pose[2] * 1.04:
                prior_start = prev_frame
        elif tid == "CAM-04":
            prior_ease = "inout_sine"
            if from_ref is not None:
                prior_start = resolve_from(from_ref)
        else:
            prior_ease = "inout_cubic"
            prior_start = resolve_from(from_ref) if from_ref is not None else prev_frame

        if prior_start is not None:
            dist_p = _dist_fw(prior_start, head_pose)
            z_ratio_p = abs(head_pose[2] / max(1e-6, prior_start[2]) - 1.0)
            if (dist_p >= 0.05 or z_ratio_p >= 0.08) and t_arr >= MIN_TRAVEL_S:
                if dist_p / t_arr <= MAX_TRAVEL_SPEED + 1e-9 and _zoom_rate(prior_start, head_pose, t_arr) <= ZOOM_RATE_MAX + 1e-9:
                    arrive_rel = max(0.05, min(0.90, t_arr / dur))
                    rem_dur = dur * (1.0 - arrive_rel)
                    t_rem = (
                        VC.region_travel_frames(
                            reg, w, h, pbox, fit_pct=fit_pct, frame_fill=frame_fill, sharp_zoom=sharp_zoom,
                            regions=regs, region_name=region_name, dur=rem_dur, max_speed=MAX_TRAVEL_SPEED,
                        )
                        if rem_dur >= MIN_TRAVEL_S else None
                    )
                    if t_rem is not None:
                        d_rem = _dist_fw(t_rem["head"], t_rem["tail"])
                        d_to_head = _dist_fw(prior_start, t_rem["head"])
                        if (d_rem >= 0.05 and d_rem / rem_dur <= MAX_TRAVEL_SPEED + 1e-9
                                and d_to_head / t_arr <= MAX_TRAVEL_SPEED + 1e-9
                                and _zoom_rate(prior_start, t_rem["head"], t_arr) <= ZOOM_RATE_MAX + 1e-9):
                            return [_key(0.0, prior_start, prior_ease),
                                    _key(arrive_rel, t_rem["head"], "inout_sine"),
                                    _key(1.0, t_rem["tail"], "linear")]
                    z_arr = max(z_floor, head_pose[2] / (1.0 + HOLD_PUSH_PCT))
                    arr = ensure_head(clamp(head_pose[0], head_pose[1], z_arr), head_pose)
                    return [_key(0.0, prior_start, prior_ease), _key(arrive_rel, arr, "linear"), _key(1.0, head_pose, "linear")]
        return direct_travel()

    if tid == "STATIC-01":
        return push_on_end(STATIC_DRIFT_PCT, "linear")

    if tid == "CAM-01":
        if from_ref is not None:
            return travel_to_end(resolve_from(from_ref), "inout_sine")
        if prev_frame is not None and rbox is not None and VC.box_inside_frame(rbox, *prev_frame)[0] and prev_frame[2] <= end[2] * 1.02:
            return travel_to_end(prev_frame, "inout_sine")
        return push_on_end(SAME_REGION_PUSH_PCT, "inout_sine")

    if tid == "CAM-03":
        if from_ref is not None:
            start = resolve_from(from_ref)
        elif prev_frame is not None and prev_frame[2] > end[2] * 1.04:
            start = prev_frame
        else:
            start = clamp(end[0], end[1], min(z_cap, end[2] * (1.0 + PULL_START_PCT)))
        if reg is None:
            # Pulling back to the whole painting: smooth pull-back across the shot, guarding against excessive speed and zoom rate.
            octaves = min(ZOOM_RATE_MAX * dur, 30.0)         # 2 ** 30 is far past any zoom cap; a long shot must not overflow the power
            z_pull_max = max(whole[2], min(z_cap, math.floor(end[2] * (2.0 ** octaves) * 1e5) / 1e5))
            if _zoom_rate(start, end, dur) > ZOOM_RATE_MAX + 1e-9:
                z_target = z_pull_max if start[2] >= end[2] else max(whole[2], end[2])
                start = VC.fit_frame_to_box(start[0], start[1], z_target, w, h, pbox, fit_pct=fit_pct, z_cap=z_pull_max)
            if _travel_speed_fw(start, end, dur) > MAX_TRAVEL_SPEED + 1e-9:
                start = VC.fit_frame_to_box(whole[0], whole[1], min(z_pull_max, whole[2] * 1.35), w, h, pbox, fit_pct=fit_pct, z_cap=z_pull_max)
            if abs(start[2] - end[2]) < 1e-3 and _dist_fw(start, end) < 0.02:
                start = VC.fit_frame_to_box(whole[0], whole[1], min(z_pull_max, whole[2] * (1.0 + PULL_START_PCT)), w, h, pbox, fit_pct=fit_pct, z_cap=z_pull_max)
            return [_key(0.0, start, "inout_cubic"), _key(1.0, end, "linear")]
        # Pulling back to a wider band/region: arrive early at the filling region frame so the named region sits cleanly in frame.
        dist = _dist_fw(start, end)
        if (dist >= 0.05 or start[2] > end[2] * 1.08) and t_arr >= MIN_TRAVEL_S and (dist / t_arr) <= MAX_TRAVEL_SPEED + 1e-9 and _zoom_rate(start, end, t_arr) <= ZOOM_RATE_MAX + 1e-9:
            arrive_rel = max(0.05, min(0.90, t_arr / dur))
            z_arr = min(z_cap, end[2] * (1.0 + min(0.02, HOLD_PUSH_PCT)))
            arr = clamp(end[0], end[1], z_arr)
            if rbox is not None and not VC.box_inside_frame(rbox, *arr)[0]:
                arr = end
            return [_key(0.0, start, "inout_cubic"), _key(arrive_rel, arr, "linear"), _key(1.0, end, "linear")]
        gentle_start = clamp(end[0], end[1], min(z_cap, end[2] * 1.08))
        if rbox is not None and VC.box_inside_frame(rbox, *gentle_start)[0]:
            return [_key(0.0, gentle_start, "inout_sine"), _key(1.0, end, "linear")]
        return push_on_end(HOLD_PUSH_PCT, "inout_sine")

    if tid == "CAM-04":
        if from_ref is not None:
            return travel_to_end(resolve_from(from_ref), "inout_sine")
        if reg is None:
            bw, bh = pbox[2] - pbox[0], pbox[3] - pbox[1]
            z = max(whole[2], min(z_cap, z_cov))
            hw = 1920.0 / (2.0 * z)
            hh = 1080.0 / (2.0 * z)
            if bh > 2.0 * hh + 40.0:
                y_bot = min(pbox[3] - hh, pbox[1] + bh * 0.72)
                y_top = max(pbox[1] + hh, pbox[1] + bh * 0.28)
                max_dy = MAX_TRAVEL_SPEED * dur * (1920.0 / z)
                if y_bot - y_top > max_dy:
                    mid = 0.5 * (y_bot + y_top)
                    y_bot, y_top = mid + 0.5 * max_dy, mid - 0.5 * max_dy
                cx_mid = 0.5 * (pbox[0] + pbox[2])
                return [_key(0.0, clamp(cx_mid, y_bot, z), "inout_sine"),
                        _key(1.0, clamp(cx_mid, y_top, z), "linear")]
            if bw > 2.0 * hw + 40.0:
                x_left = max(pbox[0] + hw, pbox[0] + bw * 0.28)
                x_right = min(pbox[2] - hw, pbox[0] + bw * 0.72)
                max_dx = MAX_TRAVEL_SPEED * dur * (1920.0 / z)
                if x_right - x_left > max_dx:
                    mid = 0.5 * (x_left + x_right)
                    x_left, x_right = mid - 0.5 * max_dx, mid + 0.5 * max_dx
                cy_mid = 0.5 * (pbox[1] + pbox[3])
                return [_key(0.0, clamp(x_left, cy_mid, z), "inout_sine"),
                        _key(1.0, clamp(x_right, cy_mid, z), "linear")]
            return push_on_end(SAME_REGION_PUSH_PCT, "inout_sine")
        # Vertical upward glide along a detail region, arriving on `end` by `t_arr` and holding with gentle push.
        rh = (rbox[3] - rbox[1]) if rbox is not None else 0.0
        dy = min(0.25 * rh, 0.30 * (1080.0 / end[2]))
        if dy >= 20.0 and t_arr >= MIN_TRAVEL_S:
            start = clamp(end[0], end[1] + dy, max(z_floor, end[2] / (1.0 + HOLD_PUSH_PCT)))
            if _dist_fw(start, end) / t_arr <= MAX_TRAVEL_SPEED + 1e-9 and _zoom_rate(start, end, t_arr) <= ZOOM_RATE_MAX + 1e-9:
                arrive_rel = max(0.05, min(0.90, t_arr / dur))
                z_arr = max(z_floor, end[2] / (1.0 + HOLD_PUSH_PCT))
                arr = ensure_rbox(clamp(end[0], end[1], z_arr), end)
                return [_key(0.0, start, "inout_sine"), _key(arrive_rel, arr, "linear"), _key(1.0, end, "linear")]
        return push_on_end(SAME_REGION_PUSH_PCT, "inout_sine")

    # Default (`CAM-05` Zoom and shift): travel from `from_ref` (default "previous", else filling default) -> `end`.
    eff_from = from_ref or "previous"
    return travel_to_end(resolve_from(eff_from), "inout_cubic")


_UNSET_REGION = object()


def build_main_camera(tid: str, region_name: str | None, from_ref: str | None, asset: dict, box,
                      prev_frame: tuple[float, float, float] | None, t0: float, t1: float,
                      overlays: list | None = None, tm: Timing | None = None, *,
                      fit_pct: float = VC.WHOLE_FIT_PCT, frame_fill: float | None = None,
                      sharp_zoom: float | None = None, prev_region=_UNSET_REGION) -> list[dict]:
    keys = _build_main_camera(tid, region_name, from_ref, asset, box, prev_frame, t0, t1,
                              overlays, tm, fit_pct=fit_pct, frame_fill=frame_fill, sharp_zoom=sharp_zoom)
    if prev_frame is None or not keys:
        return keys

    w = float(asset.get("width") or 1920.0)
    h = float(asset.get("height") or 1080.0)
    pbox = box if (isinstance(box, (list, tuple)) and len(box) == 4 and box[2] > box[0] and box[3] > box[1]) else (0.0, 0.0, w, h)
    regs = asset.get("regions") or {}
    reg = regs.get(region_name) if isinstance(region_name, str) else None
    z_cov = VC.cover_zoom(w, h, pbox)
    z_cap = VC.sharp_limit(w, h, sharp_zoom=sharp_zoom)
    can_fill = z_cov <= z_cap + 1e-9
    is_oversized = bool(reg is not None and VC.region_oversized_axis(reg, w, h, pbox, sharp_zoom=sharp_zoom) is not None)

    def frame(key):
        return (key["cx"], key["cy"], key["zoom"])

    def close(a, b, limit):
        return _dist_fw(a, b) <= limit and abs(b[2] / max(1e-6, a[2]) - 1.0) <= limit

    if prev_region is not _UNSET_REGION and prev_region == region_name:
        return [_key(0.0, prev_frame), _key(1.0, prev_frame)]
    if close(prev_frame, frame(keys[-1]), 0.03) and not (is_oversized and any(not close(frame(k), frame(keys[-1]), 0.05) for k in keys)):
        return [_key(0.0, prev_frame), _key(1.0, prev_frame)]
    if close(prev_frame, frame(keys[0]), 0.12) and (reg is None or not can_fill or prev_frame[2] >= z_cov - 1e-5):
        keys[0].update(cx=prev_frame[0], cy=prev_frame[1], zoom=prev_frame[2])
    return keys
