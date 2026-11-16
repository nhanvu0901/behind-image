import json,sys
sys.path.insert(0,'scripts')
from beats_src import BEATS
t=0.0;b={}
title=None
for i,(id_,sec,text,*_) in enumerate(BEATS):
    words=text.split(); d=len(words)/142*60
    ws=[{"w":w,"s":round(t+d*k/len(words),3),"e":round(t+d*(k+1)/len(words),3)} for k,w in enumerate(words)]
    b[id_]={"start":round(t,3),"end":round(t+d,3),"words":ws}
    t+=d+(0.28)
    if id_=="B1b": title=[round(t+0.1,2),round(t+2.6,2)]; t+=2.7
    if id_ in("B2d","B3c","B4d"): t+=0.22
json.dump({"beats":b,"title":title,"end":round(t+1.2,2)},open('ref/fake_timing.json','w'),indent=1)
print(title,t)
