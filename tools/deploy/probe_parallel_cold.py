"""Scratch: cold-start timing of a thread pool (first thing the process does), then the serial reference. Usage: [project] [threads]"""
import concurrent.futures as cf, hashlib, sys, time
NTHREADS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
sys.argv = sys.argv[:1] + sys.argv[1:2]
name = sys.argv[1] if len(sys.argv) > 1 else "arnolfini"
import runpy, io
src = open("tools/deploy/probe_parallel.py").read().split("def draw(t):")[0]
exec(src)
def draw(t):
    return hashlib.sha1(scene.frame_at(t, 320).tobytes()).hexdigest()
import os
n = NTHREADS
t = time.perf_counter()
with cf.ThreadPoolExecutor(n) as ex:
    out = list(ex.map(draw, jobs))
print("COLD threads=%d wall %.1f s" % (n, time.perf_counter() - t), flush=True)
t = time.perf_counter()
ref = [draw(x) for x in jobs]
print("then serial (warm) wall %.1f s, identical %d/%d" % (time.perf_counter() - t, sum(a == b for a, b in zip(out, ref)), len(jobs)), flush=True)
