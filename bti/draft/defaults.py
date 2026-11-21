"""`python -m bti.draft.defaults <technique> [--asset A --region R] [workspace]`

Prints what a technique needs (slots, parameters with type, bounds and default) and, with `--asset`, the parameters the compiler would
start from for that picture (and region): camera keys included. Use it before you write `params` by hand."""
from __future__ import annotations

import argparse
import json
import sys



def overlay_default_window(tid, start, shot_start, shot_end, params, texts, default_duration):
    """Default overlay window, keeping room for its fade and readable text."""
    from bti.engine.techniques.explain_over import min_read_seconds
    if tid == "HI-01":
        end = max(shot_start, shot_end - float(params.get("ramp_out", 0.5)))
        return max(shot_start, min(start, end - 2.5)), end
    if tid == "KEY-01":
        return start, shot_end
    end = min(shot_end, start + float(default_duration or shot_end - start))
    if texts and end >= shot_end - 1e-6:
        fade_in = float(params.get("pop_in_s", params.get("fade_in_s", 0)) or 0)
        fade_out = float(params.get("fade_out_s", params.get("leave_s", 0)) or 0)
        if tid == "STATIC-04":
            fade_in += float(params.get("delay_s", 0) or 0)
        elif tid == "AN-05":
            fade_in = float(params.get("pop_s",0) or 0)
        elif tid == "AN-04":
            fade_in = float(params.get("label_delay_s",0) or 0) + max(0,len(texts)-1)*float(params.get("label_stagger_s",0) or 0) + float(params.get("label_fade_s",0) or 0)
            fade_out = float(params.get("fade_s",0) or 0)
        elif tid == "X-ANN-05":
            fade_in = sum(float(params.get(k,0) or 0) for k in ("start_delay_s","label_delay_s","label_fade_s")) + max(0,len(texts)-1)*float(params.get("stagger_s",0) or 0)
            fade_out = float(params.get("fade_s",0) or 0)
        elif tid == "SHORT-04":
            fade_in = float(params.get("text_delay_s",0) or 0) + float(params.get("pop_s",0) or 0)
        elif tid == "TXT-02":
            fade_in = max(0,len(texts)-1)*float(params.get("row_delay_s",0) or 0)
        elif tid == "ID-OPEN-02":
            fade_in = max(0.0, float(params.get("ramp_in_s",0) or 0) - float(params.get("title_fade_in_s",0) or 0))
            fade_in += max(float(params.get("title_fade_in_s",0) or 0), float(params.get("sub_delay_s",0) or 0) + float(params.get("sub_fade_in_s",0) or 0))
            fade_out = float(params.get("ramp_out_s",0) or 0)
        elif tid == "DOC-01":
            read_at = params.get("reading_at", 2.4)
            fade_in = (float(read_at) if isinstance(read_at, (int,float)) else 0) + .8
        elif tid == "NUM-01":
            rows = [r for r in params.get("rows",[]) if isinstance(r,dict)]
            ats = [float(r.get("at") or 0) if isinstance(r.get("at"), (int,float)) else 0 for r in rows]
            fade_in = max([1.25] + [at + .75 for at in ats])
        need = max(min_read_seconds(t) for t in texts if t.strip()) + fade_in + fade_out if any(t.strip() for t in texts) else 0
        start = max(shot_start, min(start, shot_end - need))
    return start, end

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="defaults", description=__doc__.split("\n")[0])
    ap.add_argument("technique")
    ap.add_argument("--asset")
    ap.add_argument("--region")
    ap.add_argument("--from", dest="from_ref", default=None, help="previous | whole | <REGION>")
    ap.add_argument("--dur", type=float, default=6.0, help="sample shot duration in seconds (default 6.0)")
    ap.add_argument("--workspace", default=".")
    a = ap.parse_args(argv)
    from .check import refuse_outside
    bad = refuse_outside(a.workspace, "--workspace")
    if bad:
        return bad
    from bti.engine import registry as R
    from bti.engine import viewchecks as VC
    from bti.media import contentbox as CB
    from . import camera as CAM
    from .techniques_md import _p, _slot
    bundle = R.load_bundle("gae")
    t = bundle.spec(a.technique)
    if t is None:
        print("ERROR unknown technique %r. Known ids: %s" % (a.technique, ", ".join(sorted(bundle.by_id))))
        return 2
    print("%s %s [%s, %s]" % (t["id"], t["name"], t["kind"], t.get("channel_usage")))
    print("intents: %s" % ", ".join(t.get("intents") or []))
    print("slots:   %s" % (", ".join(_slot(s) for s in t.get("slots") or []) or "none"))
    print("params:  %s" % (", ".join(_p(p) for p in t.get("params") or []) or "none"))
    if not a.asset:
        return 0
    from .engine import DraftProject
    from .workspace import load_workspace
    try:
        inp, _ = load_workspace(a.workspace)
    except Exception as e:      # noqa: BLE001
        print("ERROR %s" % getattr(e, "message", e))
        return 2
    from .assetmerge import merged_assets
    assets = merged_assets(inp.picks["assets"], (inp.current or {}).get("assets"), edit=inp.edit_shots is not None)       # the regions the compiler will use
    rec = assets.get(a.asset)
    if rec is None:
        print("ERROR no asset %r (assets: %s)" % (a.asset, ", ".join(sorted(assets))))
        return 2
    main_key = inp.picks.get("main_asset")
    if a.region and a.region not in (rec.get("regions") or {}):
        print("ERROR no region %r on %s (regions: %s)" % (a.region, a.asset, ", ".join(sorted(rec.get("regions") or {})) or "none"))
        return 2
    if a.from_ref and a.from_ref not in ("previous", "whole") and a.from_ref not in (rec.get("regions") or {}):
        print("ERROR no --from region %r on %s" % (a.from_ref, a.asset))
        return 2
    eng = DraftProject(inp.project_dir, {"schema": "bti.storyboard/1", "assets": assets, "shots": [], "end": {"t": 1.0}}, inp.timing)
    try:
        info = {"key": a.asset, "w": rec.get("width"), "h": rec.get("height"), "title": rec.get("title"), "artist": rec.get("artist"),
                "year": rec.get("year"), "regions": rec.get("regions") or {}}
        ctx = {"asset": info}
        if a.region:
            ctx.update(region=a.region, focus=a.region, text=info["regions"][a.region].get("label") or a.region)
        params = eng.default_params(a.technique, ctx)
    finally:
        eng.close()
    is_main_cam = (a.asset == main_key and a.technique in CAM.OFFERED_CAMERA_TECHNIQUES)
    if is_main_cam:
        box = CB.box_of(rec, inp.project_dir)
        params["camera"] = CAM.build_main_camera(
            a.technique, a.region, a.from_ref, rec, box, None, 0.0, max(1.0, float(a.dur)),
        )
    print("default params for asset %s%s:" % (a.asset, (" region " + a.region) if a.region else ""))
    print(json.dumps(params, indent=1, ensure_ascii=False))
    if is_main_cam and rec.get("width") and rec.get("height"):
        box = CB.box_of(rec, inp.project_dir)
        reg = (rec.get("regions") or {}).get(a.region) if a.region else None
        finfo = VC.region_frame_info(reg, float(rec["width"]), float(rec["height"]), box)
        share_str = ""
        if "width_share" in finfo:
            share_str = "; region takes %.1f%% W x %.1f%% H%s" % (
                100.0 * finfo["width_share"], 100.0 * finfo["height_share"],
                " (under 40%% -> use HI-01)" if finfo.get("needs_spotlight") else "",
            )
        print("compiler end frame: centre (%.1f, %.1f) zoom %.4f rect %s%s" % (finfo["cx"], finfo["cy"], finfo["zoom"], finfo["rect"], share_str))
        print("note: for main painting shots write slots.image.region (and optional \"from\") in out/<chapter>.json, never params.camera")
    return 0


if __name__ == "__main__":
    sys.exit(main())
