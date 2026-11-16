import time,json,sys,urllib.parse,urllib.request,re
UA={"User-Agent":"Mozilla/5.0 (compatible; ArtResearchBot/1.0)"}
def info(titles):
    out={}
    for i in range(0,len(titles),20):
        u="https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=url|size|extmetadata&format=json&titles="+urllib.parse.quote("|".join(titles[i:i+20]))
        d=None
        for k in range(6):
            try:
                d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA))); break
            except Exception as e:
                time.sleep(15*(k+1))
        import time as _t
        _t.sleep(2)
        for p in d["query"]["pages"].values():
            ii=(p.get("imageinfo") or [{}])[0]; m=ii.get("extmetadata",{})
            f=lambda k:re.sub("<[^>]+>","",m.get(k,{}).get("value","")).strip()
            out[p["title"]]=dict(w=ii.get("width"),h=ii.get("height"),url=ii.get("url"),lic=f("LicenseShortName"),artist=f("Artist")[:90],credit=f("Credit")[:60],date=f("DateTimeOriginal")[:30])
    return out
if __name__=="__main__":
    t=[x if x.startswith("File:") else "File:"+x for x in sys.argv[1:]]
    for k,v in info(t).items(): print(k,"|",v["w"],"x",v["h"],"|",v["lic"],"|",v["artist"])
