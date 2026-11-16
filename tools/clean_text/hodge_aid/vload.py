import json
def load(path='/Users/nhanvu/Documents/code/behind-the-image/.scratch/clean_hodge/vision.jsonl'):
    V={}
    for l in open(path):
        try: j=json.loads(l)
        except Exception: continue
        V[int(j['image'][-8:-4])]=j['lines']
    return V
