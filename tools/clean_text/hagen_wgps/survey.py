import sys,collections; sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/hagen_wgps')
import layout as Lo
res={}
for n in range(12,492):
    it,o,L=Lo.assemble(n); res[n]=(it,o)
import pickle; pickle.dump(res,open('/Users/nhanvu/Documents/code/behind-the-image/.scratch/clean_hagen/assembled.pkl','wb'))
# anomalies
for n,(it,o) in res.items():
    words=sum(len(x['text'].split()) for x in it)
    low=[x['text'][:40] for i,x in enumerate(it) if x['kind']=='para' and x['text'][:1].islower() and i>0 and it[i-1]['kind']=='h2']
    nh=sum(x['kind']=='h2' for x in it)
    flags=[]
    if low: flags.append('lowercase-after-h2 %d'%len(low))
    if nh>2: flags.append('h2=%d'%nh)
    if words<30: flags.append('words=%d'%words)
    if o['junk']>3: flags.append('junk=%d'%o['junk'])
    if flags: print(n,words,flags)
