r"""Runs ON the server: one heavy pytest run under the heavy slot (bti/longjob/heavy.py, the real lock folder from
config/server.json: production-process check, free-memory check, atomic mkdir of D:\bench\_heavy.lock, owner.txt, release
in `finally`). Usage: heavy_run.py <what> <max-minutes> -- <pytest arguments>
Output goes to stdout (the launcher redirects it to logs\heavy_run.log). Start it only through launch_heavy.ps1, which
detaches it with Win32_Process Create so that it survives the ssh session."""
import os
import subprocess
import sys
import time

HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HOME)
from bti.longjob.config import load            # noqa: E402
from bti.longjob.heavy import HeavySlot        # noqa: E402
from bti.proc import group_kwargs, kill_tree   # noqa: E402

what, minutes = sys.argv[1], float(sys.argv[2])
args = sys.argv[sys.argv.index("--") + 1:]
cfg = load()
print("config lock_dir=%s floor_kb=%s patterns=%s" % (cfg.lock_dir, cfg.memory_floor_kb, cfg.production_patterns), flush=True)
slot = HeavySlot(cfg, own_markers=("behind-the-image",))
rc = 1
try:
    with slot.hold(what, on_wait=lambda n: print("WAIT", n, flush=True), expected_seconds=minutes * 60):
        print("LOCK TAKEN", time.strftime("%H:%M:%S"), flush=True)
        env = dict(os.environ, PYTHONUTF8="1", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=HOME)
        p = subprocess.Popen([sys.executable, "-m", "pytest", *args, "-p", "no:cacheprovider"], cwd=HOME, env=env,
                             stdin=subprocess.DEVNULL, **group_kwargs())
        try:
            rc = p.wait(timeout=minutes * 60)
        except subprocess.TimeoutExpired:
            print("TIME LIMIT: killing the run", flush=True)
            kill_tree(p)
            rc = 124
finally:
    print("LOCK RELEASED", time.strftime("%H:%M:%S"), flush=True)
    print("EXIT=%s" % rc, flush=True)
