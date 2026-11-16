"""Longest run of consecutive words shared between script.txt and the extracted chapter text (lowercase, punctuation stripped)."""
import re,sys
def toks(s): return re.findall(r"[a-z0-9]+",s.lower().replace("’","'").replace("'",""))
book=toks(open('assets/chapter2_text.txt',encoding='utf8').read())
scr=toks(open('script.txt',encoding='utf8').read())
N=6
grams={tuple(book[i:i+N]) for i in range(len(book)-N+1)}
hits=[(i,scr[i:i+N]) for i in range(len(scr)-N+1) if tuple(scr[i:i+N]) in grams]
# longest shared run
bi={}
for i,w in enumerate(book): bi.setdefault(w,[]).append(i)
best=(0,0,0)
for i in range(len(scr)):
    for j in bi.get(scr[i],[]):
        k=0
        while i+k<len(scr) and j+k<len(book) and scr[i+k]==book[j+k]: k+=1
        if k>best[0]: best=(k,i,j)
print(f"script words: {len(scr)}; book words: {len(book)}")
print(f"6-gram overlaps: {len(hits)}")
for i,g in hits: print("  HIT:", " ".join(g))
print(f"longest shared run: {best[0]} words -> '{' '.join(scr[best[1]:best[1]+best[0]])}'")
print("RESULT:", "PASS (<=5 consecutive)" if best[0]<=5 else "FAIL")
