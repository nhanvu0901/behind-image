import sys,collections; sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/hagen_wgps')
import layout as Lo, accents as A
Lo.LINEFIX=lambda n,t,b,W,H: A.collect(n,t,b,W,H,Lo.valid) or t
for n in range(12,492): Lo.assemble(n)
A.build_map(Lo.valid)
print(len(A.CAND),len(A.MAP))
for k,v in sorted(A.MAP.items(),key=lambda kv:-sum(A.CAND[kv[0]].values()) if kv[0] in A.CAND else 0): print(k,'->',v,sum(A.CAND[k].values()) if k in A.CAND else sum(A.WORDFIX[k].values()),A.SEEN[k])
