"""Shot-length stats from the rendered storyboard + camera speeds measured (ECC) on the delivered mp4 vs the reference numbers."""
import json,sys,statistics,subprocess,os
H=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V=sys.argv[1]
shots=json.load(open(f"{H}/v2/shots_final.json"))
d=[s['t1']-s['t0'] for s in shots]
stills=[s['t1']-s['t0'] for s in shots if s['effect'].startswith(('context still','Bruges still','Ghent still','tomb still','Las Meninas'))]
cards=[s['t1']-s['t0'] for s in shots if 'card' in s['effect']]
print(f"shots: {len(shots)}  median {statistics.median(d):.1f}s mean {statistics.mean(d):.1f}s p10 {sorted(d)[int(.1*len(d))]:.1f}s p90 {sorted(d)[int(.9*len(d))]:.1f}s max {max(d):.1f}s min {min(d):.1f}s")
print(f"reference episode: 59 shots, median 7.0 s, mean 15.9 s, p10 4.0, p90 37.6 (hard cuts at thr 0.15)")
print(f"context stills: n={len(stills)} hold median {statistics.median(stills):.1f}s (reference stills in a sequence: 4.0 s each)" if stills else "")
print(f"cards: n={len(cards)} durations {[round(x,1) for x in cards]}")
def find(sub,nth=0): return [s for s in shots if sub in s['effect']][nth]
moves={"opening pull-back (ref 3.0x/17.9 s ease-out)":find("opening pull-back"),"matte to fill-width (ref 1.59x/4.9 s ease-in)":find("matte to fill-width"),"mirror push (ref 3.57x/~11 s ease-in-out)":find("mirror push"),"closing pull-out (ref 5.8x/40 s ease-out)":find("closing")}
for name,s in moves.items():
    t0=s['t0']+ (0.0); dur=min(s['t1']-s['t0'],46)
    if "matte" in name: t0=s['t0']; dur=5.6
    if "mirror push" in name: dur=12
    if "closing" in name: t0=s['t0']+0.5; dur=40
    if "opening" in name: dur=18.5
    out=subprocess.run(["python3",f"{H}/scripts/measure_motion.py",V,str(t0),str(dur),name,"10"],capture_output=True,text=True).stdout.strip().splitlines()
    print("##",name,f"(window {t0:.1f}-{t0+dur:.1f})"); print("\n".join(l for l in out if l.startswith(('TOTAL','  progress'))))
