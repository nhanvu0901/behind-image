from pathlib import Path
import subprocess,json
root=Path('/Users/nhanvu/Documents/code/behind-the-image'); media=root/'research_media/great-art-explained'; dest=media/'effect-excerpts'; items=[('83ggxS21mFM',31,'pull-back'),('lAjVuUB9AkI',930,'pan-up'),('TU3dRcqik3I',1011,'zoom-and-shift'),('lHePKNTRmdI',0,'hold-caption')]
manifest=dest/'manifest.json'; data=json.loads(manifest.read_text())
for vid,start,name in items:
 out=dest/f'{vid}-{start}-{name}.mp4'; cmd=['/opt/homebrew/bin/ffmpeg','-hide_banner','-loglevel','error','-ss',str(start),'-i',str(media/(vid+'.mp4')),'-t','10','-map','0:v:0','-an','-c:v','libx264','-crf','18','-preset','fast','-movflags','+faststart','-n',str(out)];r=subprocess.run(cmd,capture_output=True,text=True); (dest/f'{vid}-{start}-{name}.log').write_text(r.stderr); data.append({'id':vid,'start':start,'duration':10,'name':name,'file':str(out),'status':'ok' if r.returncode==0 else 'error','exit':r.returncode});print(name,r.returncode,flush=True)
manifest.write_text(json.dumps(data,indent=2)+'\n')
