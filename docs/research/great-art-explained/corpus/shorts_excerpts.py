from pathlib import Path
import subprocess,json
m=Path('/Users/nhanvu/Documents/code/behind-the-image/research_media/great-art-explained');p=m/'effect-excerpts';manifest=p/'manifest.json';data=json.loads(manifest.read_text()); jobs=[('44LZPWLDYOQ',21,'short-skull-view'),('UKjrMZSIhvg',42,'short-three-strips'),('EFxxmc0EZTI',0,'short-type-changes')]
for id,start,name in jobs:
 out=p/f'{id}-{start}-{name}.mp4';r=subprocess.run(['/opt/homebrew/bin/ffmpeg','-hide_banner','-loglevel','error','-ss',str(start),'-i',str(m/(id+'.mp4')),'-t','10','-map','0:v:0','-an','-c:v','libx264','-crf','18','-preset','fast','-movflags','+faststart','-n',str(out)],capture_output=True,text=True);(p/f'{id}-{start}-{name}.log').write_text(r.stderr);data.append({'id':id,'start':start,'duration':10,'name':name,'file':str(out),'status':'ok' if r.returncode==0 else 'error','exit':r.returncode});print(name,r.returncode,flush=True)
manifest.write_text(json.dumps(data,indent=2)+'\n')
