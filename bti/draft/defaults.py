"""`python -m bti.draft.defaults <technique> [--asset A --region R] [workspace]`

Prints what a technique needs (slots, parameters with type, bounds and default) and, with `--asset`, the parameters the compiler would
start from for that picture (and region): camera keys included. Use it before you write `params` by hand."""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="defaults", description=__doc__.split("\n")[0])
    ap.add_argument("technique")
    ap.add_argument("--asset")
    ap.add_argument("--region")
    ap.add_argument("--workspace", default=".")
    a = ap.parse_args(argv)
    from bti.engine import registry as R
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
    from .compile import _Compiler
    try:
        inp, _ = load_workspace(a.workspace)
    except Exception as e:      # noqa: BLE001
        print("ERROR %s" % getattr(e, "message", e))
        return 2
    assets = dict(inp.picks["assets"])
    assets.update((inp.current or {}).get("assets") or {})
    rec = assets.get(a.asset)
    if rec is None:
        print("ERROR no asset %r (assets: %s)" % (a.asset, ", ".join(sorted(assets))))
        return 2
    eng = DraftProject(inp.project_dir, {"schema": "bti.storyboard/1", "assets": assets, "shots": [], "end": {"t": 1.0}}, inp.timing)
    try:
        info = {"key": a.asset, "w": rec.get("width"), "h": rec.get("height"), "title": rec.get("title"), "artist": rec.get("artist"),
                "year": rec.get("year"), "regions": rec.get("regions") or {}}
        ctx = {"asset": info}
        if a.region:
            if a.region not in info["regions"]:
                print("ERROR no region %r on %s (regions: %s)" % (a.region, a.asset, ", ".join(sorted(info["regions"])) or "none"))
                return 2
            ctx.update(region=a.region, focus=a.region, text=info["regions"][a.region].get("label") or a.region)
        params = eng.default_params(a.technique, ctx)
    finally:
        eng.close()
    print("default params for asset %s%s:" % (a.asset, (" region " + a.region) if a.region else ""))
    print(json.dumps(params, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
