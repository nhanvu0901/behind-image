"""Technique sweep helpers: drives the 78 registry techniques through an HTTP client, as the editing page would.

`client` is anything with .get/.post/.put returning an object with .status_code, .json(), .content (httpx.Client or
starlette TestClient). `project` is a copy of technique_lab (reference configuration for every technique).
"""
from __future__ import annotations

import copy
import io
import time

import numpy as np
from PIL import Image

PID = "technique_lab"


WARM_LIMIT_MS = 1500        # was 300 (the Mac); the Windows server measured 373 ms. 5 x the old limit: a frame that is not cached takes seconds

def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def decode(content: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(content)).convert("RGB")).astype(np.float32)


def uniform(arr: np.ndarray) -> bool:
    return float(arr.std()) < 2.0


def locate(sb: dict, tech: dict) -> tuple[str, int, int | None]:
    """Where the technique_lab reference of `tech` lives: (kind, shot index, overlay index)."""
    tid, kind = tech["id"], tech["kind"]
    for i, s in enumerate(sb["shots"]):
        if kind in ("base", "card") and s["technique"] == tid:
            return kind, i, None
        if kind == "overlay":
            for j, o in enumerate(s.get("overlays") or []):
                if o["technique"] == tid:
                    return kind, i, j
        if kind == "transition" and (s.get("transition_in") or {}).get("technique") == tid:
            return kind, i, None
    raise LookupError(tid)


def context_for(sb: dict, kind: str, i: int, j: int | None) -> dict:
    shot = sb["shots"][i]
    item = shot["overlays"][j] if kind == "overlay" else shot
    slots = copy.deepcopy(item.get("slots") or shot.get("slots") or {})
    assets = {k: {"width": a.get("width"), "height": a.get("height"), "title": a.get("title"),
                  "artist": a.get("artist"), "year": a.get("year"), "regions": a.get("regions") or {}}
              for k, a in sb["assets"].items()}
    return {"item": "overlay" if kind == "overlay" else "shot", "shot_id": shot["id"], "slots": slots,
            "assets": assets, "canvas": sb.get("canvas")}


def build_draft(sb: dict, tech: dict, params: dict, kind: str, i: int, j: int | None) -> dict:
    d = strip(copy.deepcopy(sb))
    s = d["shots"][i]
    if kind in ("base", "card"):
        s["params"] = params
        s["overlays"] = []
        s["transition_in"] = None
    elif kind == "overlay":
        s["overlays"][j]["params"] = params
    else:
        s["transition_in"]["params"] = params
    return d


def sample_times(rs: dict, kind: str, i: int, j: int | None) -> list[float]:
    s = rs["shots"][i]
    if kind == "overlay":
        o = s["overlays"][j]
        a, b = o["_t0"], o["_t1"]
    elif kind == "transition":
        a, b = s["_t0"], s["_t0"] + max(s["transition_in"].get("dur") or 0, 0.3)
        b = min(b, s["_t1"])
    else:
        a, b = s["_t0"], s["_t1"]
    return [round(a + (b - a) * f, 3) for f in (0.12, 0.5, 0.88)]


def sweep_one(client, tech: dict, sb: dict, rs: dict, pid: str = PID, width: int = 640) -> dict:
    """Run every check for one technique and return a record (never raises)."""
    tid = tech["id"]
    rec: dict = {"id": tid, "kind": tech["kind"], "problems": [], "timings_ms": {}}
    try:
        kind, i, j = locate(sb, tech)
    except LookupError:
        rec["problems"].append("no reference in technique_lab")
        return rec
    ctx = context_for(sb, kind, i, j)
    t = time.time()
    r = client.post(f"/api/projects/{pid}/defaults", json={"technique": tid, "context": ctx})
    rec["timings_ms"]["defaults"] = round((time.time() - t) * 1000)
    if r.status_code != 200:
        rec["problems"].append(f"defaults -> {r.status_code} {r.text[:200]}")
        return rec
    params = r.json()["params"]
    rec["defaults"] = params
    # defaults without context must not crash either
    r0 = client.post(f"/api/projects/{pid}/defaults", json={"technique": tid, "context": {}})
    if r0.status_code != 200:
        rec["problems"].append(f"defaults with empty context -> {r0.status_code} {r0.text[:160]}")
    draft = build_draft(sb, tech, params, kind, i, j)
    r = client.post(f"/api/projects/{pid}/validate", json={"storyboard": draft})
    if r.status_code != 200:
        rec["problems"].append(f"validate -> {r.status_code} {r.text[:200]}")
        return rec
    errs = [x for x in r.json()["issues"] if x["level"] == "error"]
    warns = [x for x in r.json()["issues"] if x["level"] == "warn"]
    rec["errors"], rec["warns"] = errs, warns
    if errs:
        rec["problems"].append("defaults fail validation: " + "; ".join(f"{e['path']}: {e['message']}" for e in errs[:3]))
    # the shot's other slots that the registry marks required but the draft has not filled
    spec_slots = tech.get("slots") or []
    item = draft["shots"][i]["overlays"][j] if kind == "overlay" else draft["shots"][i]
    have = set((item.get("slots") or draft["shots"][i].get("slots") or {}).keys())
    miss = [s["name"] for s in spec_slots if s["required"] and s["type"] in ("image", "video") and s["name"] not in have]
    if miss and kind != "transition":
        rec["problems"].append(f"required slots not filled by the reference: {miss}")
    frames = []
    for t_ in sample_times(rs, kind, i, j):
        body = {"t": t_, "width": width, "storyboard": draft}
        t0 = time.time()
        r = client.post(f"/api/projects/{pid}/frame", json=body)
        cold = (time.time() - t0) * 1000
        if r.status_code != 200:
            rec["problems"].append(f"frame t={t_} -> {r.status_code} {r.text[:200]}")
            continue
        t0 = time.time()
        r2 = client.post(f"/api/projects/{pid}/frame", json=body)
        warm = (time.time() - t0) * 1000
        rec["timings_ms"][f"t{t_}"] = [round(cold), round(warm)]
        a = decode(r.content)
        frames.append((t_, a))
        if uniform(a):
            rec["problems"].append(f"uniform/blank frame at t={t_} (std {a.std():.2f})")
        if warm > WARM_LIMIT_MS:
            rec["problems"].append(f"warm still {warm:.0f} ms at t={t_} (width {width})")
        if r2.content != r.content:
            rec["problems"].append(f"non-deterministic frame at t={t_}")
    if kind == "overlay" and frames:
        base = copy.deepcopy(draft)
        base["shots"][i]["overlays"] = []
        diffs = []
        for t_, a in frames:
            r = client.post(f"/api/projects/{pid}/frame", json={"t": t_, "width": width, "storyboard": base})
            if r.status_code == 200:
                diffs.append(float(np.abs(decode(r.content) - a).mean()))
        rec["overlay_diff"] = [round(d, 3) for d in diffs]
        if diffs and max(diffs) < 0.05:
            rec["problems"].append("overlay with default params changes nothing at any of the 3 times")
    return rec


def preview_one(client, tech: dict, sb: dict, rs: dict, rec: dict, pid: str = PID, width: int = 640, fps: int = 15,
                poll_timeout: float = 120.0) -> dict:
    """3 s preview of the technique's own configuration (defaults params); returns {job_s, frames, duration, size}."""
    import json
    import os
    import subprocess
    import tempfile
    kind, i, j = locate(sb, tech)
    draft = build_draft(sb, tech, rec.get("defaults") or {}, kind, i, j)
    t = sample_times(rs, kind, i, j)[0]
    t0 = max(0.0, t - 0.5) if kind != "base" and kind != "card" else rs["shots"][i]["_t0"]
    body = {"t0": t0, "t1": t0 + 3.0, "width": width, "fps": fps, "storyboard": draft}
    start = time.time()
    r = client.post(f"/api/projects/{pid}/preview", json=body)
    if r.status_code != 200:
        return {"error": f"submit {r.status_code} {r.text[:200]}"}
    jid = r.json()["job_id"]
    while time.time() - start < poll_timeout:
        j_ = client.get(f"/api/jobs/{jid}").json()
        if j_["state"] in ("done", "error"):
            break
        time.sleep(0.2)
    else:
        return {"error": "timeout"}
    el = time.time() - start
    if j_["state"] == "error":
        return {"error": j_["error"], "job_s": round(el, 2)}
    f = client.get(j_["result_url"])
    if f.status_code != 200:
        return {"error": f"result {f.status_code}", "job_s": round(el, 2)}
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as fh:
        fh.write(f.content)
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames,duration,width,height", "-of", "json", fh.name], capture_output=True)
        info = json.loads(p.stdout)["streams"][0]
    finally:
        os.unlink(fh.name)
    return {"job_s": round(el, 2), "frames": int(info["nb_read_frames"]), "duration": float(info.get("duration") or 0),
            "size": len(f.content), "w": info["width"], "h": info["height"]}
