"""Server-side probe: time open_project(...).draw_check() with stack dumps every 15 s (faulthandler)."""
import faulthandler, sys, time
faulthandler.dump_traceback_later(15, repeat=True, file=sys.stderr)
from bti.engine.api import open_project
name = sys.argv[1] if len(sys.argv) > 1 else "arnolfini"
t = time.perf_counter()
p = open_project("projects/" + name)
print("open", round(time.perf_counter() - t, 2), flush=True)
t = time.perf_counter()
iss = p.draw_check()
print("draw_check", round(time.perf_counter() - t, 2), "issues", len(iss), flush=True)
