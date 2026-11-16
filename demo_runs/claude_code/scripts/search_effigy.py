import json,time,urllib.parse,urllib.request,re,sys
UA={"User-Agent":"Mozilla/5.0 (compatible; ArtResearchBot/1.0)"}
def get(u):
    for k in range(6):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA)))
        except Exception as e: time.sleep(20*(k+1))
    return None
qs=["effigy dog at her feet alabaster","tomb lady effigy dog feet church","medieval tomb effigy woman dog","alabaster tomb effigy lady dog","funerary effigy countess dog at feet"]
seen={}
for q in qs:
    d=get("https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch="+urllib.parse.quote(q+" filetype:bitmap")+"&gsrnamespace=6&gsrlimit=10&prop=imageinfo&iiprop=extmetadata|size|url&format=json")
    time.sleep(8)
    if not d: continue
    for p in d.get("query",{}).get("pages",{}).values():
        ii=(p.get("imageinfo") or [{}])[0]; m=ii.get("extmetadata",{})
        lic=re.sub("<[^>]+>","",m.get("LicenseShortName",{}).get("value",""))
        if lic in ("Public domain","CC0") or lic.startswith("CC BY"):
            seen[p["title"]]=(ii.get("width"),ii.get("height"),lic,ii.get("url"),re.sub("<[^>]+>","",m.get("Artist",{}).get("value",""))[:70])
for k,v in seen.items(): print(k,"|",v[0],v[1],"|",v[2],"|",v[4])
json.dump(seen,open("v2/effigy_candidates.json","w"),indent=1)
