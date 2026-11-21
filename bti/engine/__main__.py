"""Command line:  python -m bti.engine still|render|validate <project_dir> ...

Exit codes: 0 success; 1 run-time failure (missing project, unreadable storyboard, cannot write the output, ffmpeg failed, a
technique cannot draw, `validate` found errors); 2 usage error (an argument is out of range).  A failure prints one line on
stderr; the Python traceback appears only with `--debug`.  No output file is left behind after a failure.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
import traceback
from pathlib import Path

from . import limits as L


class UsageError(Exception):
    """An argument that is out of range (exit code 2)."""


def _finite(name: str, v: float, lo: float = 0.0) -> float:
    if not math.isfinite(v) or v < lo:
        raise UsageError("%s must be a finite number >= %g (got %s)" % (name, lo, v))
    return v


def _int_in(name: str, v: int, lo: int, hi: int) -> int:
    if not lo <= v <= hi:
        raise UsageError("%s must be between %d and %d (got %d)" % (name, lo, hi, v))
    return v


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m bti.engine")
    common = argparse.ArgumentParser(add_help=False)          # `--debug` is accepted before or after the sub-command
    common.add_argument("--debug", action="store_true", default=argparse.SUPPRESS, help="show the Python traceback of a failure")
    ap.add_argument("--debug", action="store_true", default=argparse.SUPPRESS, help="show the Python traceback of a failure")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("still", help="write one frame as PNG/JPG", parents=[common])
    s.add_argument("project_dir"); s.add_argument("t", type=float, help="seconds, finite and >= 0")
    s.add_argument("--width", type=int, default=960, help="%d..%d" % (L.FRAME_WIDTH_MIN, L.FRAME_WIDTH_MAX)); s.add_argument("-o", "--out", required=True)
    r = sub.add_parser("render", help="render a time range to silent H.264", parents=[common])
    r.add_argument("project_dir"); r.add_argument("--t0", type=float, default=0.0); r.add_argument("--t1", type=float, default=None, help="default: the end of the storyboard")
    r.add_argument("-o", "--out", required=True)
    r.add_argument("--width", type=int, default=None, help="%d..%d (default 640; 1920 for --quality final)" % (L.FRAME_WIDTH_MIN, L.FRAME_WIDTH_MAX))
    r.add_argument("--fps", type=int, default=None, help="%d..%d (default 15; 30 for --quality final)" % (L.FPS_MIN, L.FPS_MAX))
    r.add_argument("--quality", choices=("preview", "final"), default="preview")
    r.add_argument("--threads", type=int, default=None, help="0 = automatic (the default), else 1..%d" % L.THREADS_MAX)
    v = sub.add_parser("validate", help="print validation issues; exit 1 when there are errors", parents=[common])
    v.add_argument("project_dir")
    return ap


def _check_still(a):
    _finite("t", a.t)
    _int_in("--width", a.width, L.FRAME_WIDTH_MIN, L.FRAME_WIDTH_MAX)


def _check_render(a):
    _finite("--t0", a.t0)
    if a.t1 is not None:
        _finite("--t1", a.t1)
        if not a.t1 > a.t0:
            raise UsageError("--t1 (%g) must be greater than --t0 (%g)" % (a.t1, a.t0))
    fin = a.quality == "final"
    if a.width is None:
        a.width = 1920 if fin else 640
    if a.fps is None:
        a.fps = 30 if fin else 15
    if a.threads is None:
        a.threads = 0
    _int_in("--width", a.width, L.FRAME_WIDTH_MIN, L.FRAME_WIDTH_MAX)
    _int_in("--fps", a.fps, L.FPS_MIN, L.FPS_MAX)
    _int_in("--threads", a.threads, 0, L.THREADS_MAX)


def _run(a) -> int:
    from .api import open_project
    if not (Path(a.project_dir) / "storyboard.json").is_file():
        raise FileNotFoundError("no storyboard.json in %s" % a.project_dir)
    p = open_project(Path(a.project_dir))
    if a.cmd == "still":
        import cv2
        t0 = time.time()
        end = p.resolve()["end"]["_t"]
        if a.t >= end:
            raise UsageError("t (%g) is at or past the end of the storyboard (%.3f s)" % (a.t, end))
        fr = p.frame_at(a.t, a.width)
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        ok = False
        try:
            ok = bool(cv2.imwrite(str(out), fr))
        except cv2.error as e:
            raise OSError("cannot write %s as a picture (%s)" % (out, str(e).strip().splitlines()[-1][:100]))
        if not ok:
            out.unlink(missing_ok=True)
            raise OSError("cannot write %s (unknown picture type or unwritable folder)" % out)
        print("wrote %s (%dx%d) in %.2fs" % (a.out, fr.shape[1], fr.shape[0], time.time() - t0))
    elif a.cmd == "render":
        end = p.resolve()["end"]["_t"]
        if a.t0 >= end:
            raise UsageError("--t0 (%g) is at or past the end of the storyboard (%.3f s)" % (a.t0, end))
        t1 = a.t1 if a.t1 is not None else end
        if not t1 > a.t0:
            raise UsageError("nothing to render: --t1 (%g) must be greater than --t0 (%g)" % (t1, a.t0))
        t0 = time.time()
        last = [-1]

        def prog(x):
            k = int(x * 20)
            if k != last[0]:
                last[0] = k
                print("progress %d%%" % (k * 5), flush=True)
        p.render_range(a.t0, t1, Path(a.out), a.width, a.fps, on_progress=prog, quality=a.quality, threads=a.threads or None)
        print("\nwrote %s in %.1fs" % (a.out, time.time() - t0))
    else:
        issues = p.validate()
        for i in issues:
            print("%-5s %s: %s" % (i["level"].upper(), i["path"], i["message"]))
        ne = sum(1 for i in issues if i["level"] == "error")
        print("%d error(s), %d warning(s)" % (ne, len(issues) - ne))
        return 1 if ne else 0
    return 0


def main(argv=None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    try:
        if a.cmd == "still":
            _check_still(a)
        elif a.cmd == "render":
            _check_render(a)
        return _run(a)
    except UsageError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 1
    except Exception as e:      # noqa: BLE001
        if getattr(a, "debug", False):
            traceback.print_exc()
        msg = (getattr(e, "message", None) or str(e) or type(e).__name__).strip().splitlines()[0][:300]
        if isinstance(e, FileNotFoundError) and not str(e):
            msg = "file not found"
        print("error: %s" % msg, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
