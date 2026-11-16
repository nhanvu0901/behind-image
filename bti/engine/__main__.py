"""Command line:  python -m bti.engine still|render|validate <project_dir> ..."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bti.engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("still", help="write one frame as PNG/JPG")
    s.add_argument("project_dir"); s.add_argument("t", type=float)
    s.add_argument("--width", type=int, default=960); s.add_argument("-o", "--out", required=True)
    r = sub.add_parser("render", help="render a time range to silent H.264")
    r.add_argument("project_dir"); r.add_argument("--t0", type=float, default=0.0); r.add_argument("--t1", type=float, default=None)
    r.add_argument("-o", "--out", required=True); r.add_argument("--width", type=int, default=None); r.add_argument("--fps", type=int, default=None)
    r.add_argument("--quality", choices=("preview", "final"), default="preview"); r.add_argument("--threads", type=int, default=None)
    v = sub.add_parser("validate", help="print validation issues; exit 1 when there are errors")
    v.add_argument("project_dir")
    a = ap.parse_args(argv)

    from .api import open_project
    p = open_project(Path(a.project_dir))
    if a.cmd == "still":
        import cv2
        t0 = time.time()
        fr = p.frame_at(a.t, a.width)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(a.out, fr)
        print("wrote %s (%dx%d) in %.2fs" % (a.out, fr.shape[1], fr.shape[0], time.time() - t0))
    elif a.cmd == "render":
        t1 = a.t1 if a.t1 is not None else p.resolve()["end"]["_t"]
        t0 = time.time()
        fin = a.quality == "final"
        last = [-1]

        def prog(x):
            k = int(x * 20)
            if k != last[0]:
                last[0] = k
                print("progress %d%%" % (k * 5), flush=True)
        p.render_range(a.t0, t1, Path(a.out), a.width or (1920 if fin else 640), a.fps or (30 if fin else 15), on_progress=prog, quality=a.quality, threads=a.threads)
        print("\nwrote %s in %.1fs" % (a.out, time.time() - t0))
    else:
        issues = p.validate()
        for i in issues:
            print("%-5s %s: %s" % (i["level"].upper(), i["path"], i["message"]))
        ne = sum(1 for i in issues if i["level"] == "error")
        print("%d error(s), %d warning(s)" % (ne, len(issues) - ne))
        return 1 if ne else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
