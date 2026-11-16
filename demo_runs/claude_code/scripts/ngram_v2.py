"""n-gram overlap of v2/script.txt against the book chapter text and the saved reference pages (lowercase, punctuation stripped).
Reports 6-gram hits per sentence and longest shared run per source."""
import re,sys,json
def tok(s): return re.findall(r"[a-z0-9]+",s.lower().replace("’","'").replace("'",""))
srcs={"book chapter":"assets/chapter2_text.txt","Wikipedia: Arnolfini Portrait":"v2/refpages/wikipedia_arnolfini_portrait.txt","National Gallery page":"v2/refpages/national_gallery_arnolfini.txt"}
script=open("v2/script.txt",encoding="utf8").read()
sents=[s.strip() for s in re.split(r'(?<=[.!?])\s+',re.sub(r'\[[^\]]+\]','',script).replace("\n"," ")) if s.strip()]
out=[];fail=False
for name,p in srcs.items():
    b=tok(open(p,encoding="utf8").read()); grams={tuple(b[i:i+6]) for i in range(len(b)-5)}
    bi={}
    for i,w in enumerate(b): bi.setdefault(w,[]).append(i)
    full=tok(" ".join(sents)); best=0;bs=0
    for i in range(len(full)):
        for j in bi.get(full[i],[]):
            k=0
            while i+k<len(full) and j+k<len(b) and full[i+k]==b[j+k]: k+=1
            if k>best: best,bs=k,i
    nhits=sum(1 for i in range(len(full)-5) if tuple(full[i:i+6]) in grams)
    out.append(f"{name}: source words {len(b)}; 6-gram hits {nhits}; longest shared run {best} words" + (f" -> '{' '.join(full[bs:bs+best])}'" if best>5 else ""))
    if best>5: fail=True
    if "-v" in sys.argv:
        for s in sents:
            t=tok(s)
            if any(tuple(t[i:i+6]) in grams for i in range(len(t)-5)): print("  HIT[",name,"]:",s[:140])
print("\n".join(out)); print("RESULT:","FAIL" if fail else "PASS (<=5 consecutive words with every source)")
