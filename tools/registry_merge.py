#!/usr/bin/env python3
"""Fold style/gae/patches/*.json into style/gae/techniques.json.

    python tools/registry_merge.py [--style gae] [--apply]

Without --apply: merge in memory, validate against techniques.schema.json, print a summary (exit 1 on any problem).
With --apply: also write techniques.json and move the applied patch files into patches/applied/.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from bti.engine.registry import PatchError, apply_patches  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="gae")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    d = REPO / "style" / a.style
    reg = json.loads((d / "techniques.json").read_text(encoding="utf-8"))
    files = sorted((d / "patches").glob("*.json")) if (d / "patches").is_dir() else []
    try:
        merged = apply_patches(reg["techniques"], d / "patches") if files else reg["techniques"]
    except PatchError as e:
        print("PATCH ERROR:", e)
        return 1
    reg["techniques"] = merged
    import jsonschema
    try:
        jsonschema.validate(reg, json.loads((d / "techniques.schema.json").read_text(encoding="utf-8")))
    except jsonschema.ValidationError as e:
        print("SCHEMA ERROR at %s: %s" % (list(e.absolute_path), e.message))
        return 1
    n_av = sum(1 for t in merged if t["engine"].get("available"))
    print("%d patch file(s) merged; %d techniques, %d available; schema OK" % (len(files), len(merged), n_av))
    if a.apply and files:
        (d / "techniques.json").write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (d / "patches" / "applied").mkdir(exist_ok=True)
        for f in files:
            shutil.move(str(f), str(d / "patches" / "applied" / f.name))
        print("applied: techniques.json rewritten, patches moved to patches/applied/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
