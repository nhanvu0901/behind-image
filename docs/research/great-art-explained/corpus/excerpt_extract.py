import pathlib,subprocess,json
root=pathlib.Path('/Users/nhanvu/Documents/code/behind-the-image'); media=root/'research_media/great-art-explained'; dest=media/'effect-excerpts'; entries=[('crCPVoPsTtk',815,10,'push-in'),('crCPVoPsTtk',695,10,'dissolve'),('cuHgxPe3J7I',1892,10,'slide-in-out'),('cuHgxPe3J7I',1095,10,'scroll-text'),('M4IUt7QZh6U',775,10,'circle-draw'),('eKyYPSpiC9g',1194,12,'figure-reveal'),('9x0tsuS4dk0',1352,12,'spotlight'),('vBG621XEegk',733,12,'panel-opening'),('ceKSyMJjniU',1255,11,'projection-rays'),('ceKSyMJjniU',1314,10,'skull-view'),('ElWG0_kjy_Y',498,12,'diagram-light')]
result=[]
for vid,start,duration,name in entries:
 src=media/(vid+'.mp4'); out=dest/f'{vid}-{start}-{name}.mp4'; log=dest/f'{vid}-{start}-{name}.log'
 if not src.exists(): result.append({'id':vid,'name':name,'status':'missing'});continue
 cmd=['/opt/homebrew/bin/ffmpeg','-hide_banner','-loglevel','error','-ss',str(start),'-i',str(src),'-t',str(duration),'-map','0:v:0','-an','-c:v','libx264','-crf','18','-preset','fast','-movflags','+faststart','-n',str(out)]
 with log.open('w') as f: r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 result.append({'id':vid,'start':start,'duration':duration,'name':name,'file':str(out),'status':'ok' if r.returncode==0 else 'error','exit':r.returncode}); print(name,result[-1]['status'],flush=True)
(dest/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
