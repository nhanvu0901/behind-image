"""Server-side measurement (scratch, not a product change): draw the samples of the draw check serially and with a thread pool,
compare every frame byte for byte with the serial result, report the times.  Usage: probe_parallel.py [project]"""
import concurrent.futures as cf, hashlib, os, sys, time
import cv2
from bti.engine.api import open_project

name = sys.argv[1] if len(sys.argv) > 1 else "arnolfini"
p = open_project("projects/" + name)
scene = p._scene()
frame = 1 / 15.0
jobs = []
for i, c in enumerate(scene.shots):
    t0, t1 = c.t0, c.t1
    if t0 is None or t1 is None:
        continue
    eps = min(0.05, (t1 - t0) / 10)
    times = [t0 + eps, (t0 + t1) / 2, t1 - eps]
    tr = c.shot.get("transition_in")
    if c.transition is not None and i > 0 and isinstance(tr, dict) and c.transition.dur > 0:
        times.append(t0 + c.transition.dur / 2)
    for o in c.shot.get("overlays") or []:
        if o.get("_t0") is not None and o.get("_t1") is not None:
            times.append((o["_t0"] + o["_t1"]) / 2)
    drawn = []
    for t in times:
        if any(abs(t - d) < frame for d in drawn):
            continue
        drawn.append(t)
        jobs.append(t)
print("samples", len(jobs), "shots", len(scene.shots), "cv2 threads", cv2.getNumThreads(), flush=True)


def draw(t):
    return hashlib.sha1(scene.frame_at(t, 320).tobytes()).hexdigest()


t = time.perf_counter(); c0 = time.process_time()
ref = [draw(t_) for t_ in jobs]
print("serial   wall %.1f s  cpu %.1f s" % (time.perf_counter() - t, time.process_time() - c0), flush=True)
for n in (4, 8):
    t = time.perf_counter(); c0 = time.process_time()
    errs = []
    with cf.ThreadPoolExecutor(n) as ex:
        out = list(ex.map(lambda x: (lambda: draw(x))() if True else None, jobs))
    same = sum(1 for a, b in zip(out, ref) if a == b)
    print("threads=%d wall %.1f s  cpu %.1f s  identical frames %d/%d" % (n, time.perf_counter() - t, time.process_time() - c0, same, len(jobs)), flush=True)
# the same with cv2 threads 1 inside the pool (avoids oversubscription)
cv2.setNumThreads(1)
for n in (1, 4, 8, 16):
    t = time.perf_counter(); c0 = time.process_time()
    with cf.ThreadPoolExecutor(n) as ex:
        out = list(ex.map(draw, jobs))
    same = sum(1 for a, b in zip(out, ref) if a == b)
    print("cv2=1 threads=%d wall %.1f s  cpu %.1f s  identical %d/%d" % (n, time.perf_counter() - t, time.process_time() - c0, same, len(jobs)), flush=True)
