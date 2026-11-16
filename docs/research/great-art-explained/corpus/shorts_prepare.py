import json,pathlib,subprocess,math
from PIL import Image,ImageOps,ImageDraw
root=pathlib.Path('/Users/nhanvu/Documents/code/behind-the-image'); p=root/'docs/research/great-art-explained/corpus'; media=root/'research_media/great-art-explained'; target=media/'analysis-shorts';target.mkdir(exist_ok=True);inv=json.loads((p/'inventory.json').read_text()); state=json.loads((p/'download-state.json').read_text())
for x in inv:
 if x['tab']!='shorts' or state[x['id']]['status']!='downloaded':continue
 id=x['id']; src=media/(id+'.mp4'); d=target/id; frames=d/'frames';frames.mkdir(parents=True,exist_ok=True)
 r=subprocess.run(['/opt/homebrew/bin/ffprobe','-v','error','-show_entries','format=duration:stream=width,height,codec_type','-of','json',str(src)],capture_output=True,text=True);meta=json.loads(r.stdout);duration=float(meta['format']['duration']);(d/'probe.json').write_text(json.dumps(meta,indent=2)+'\n')
 cmd=['/opt/homebrew/bin/ffmpeg','-hide_banner','-loglevel','error','-i',str(src),'-vf','fps=1/5:start_time=0','-q:v','3','-y',str(frames/'frame-%04d.jpg')];r=subprocess.run(cmd,capture_output=True,text=True);(d/'extract.log').write_text(r.stderr)
 files=sorted(frames.glob('frame-*.jpg')); cellw=180;cellh=270;columns=6;rows=math.ceil(len(files)/columns); sheet=Image.new('RGB',(cellw*columns,cellh*rows),'#202020');draw=ImageDraw.Draw(sheet)
 for i,f in enumerate(files):
  im=Image.open(f).convert('RGB');im.thumbnail((cellw-8,cellh-30),Image.Resampling.LANCZOS);x0=(i%columns)*cellw+(cellw-im.width)//2;y0=(i//columns)*cellh+24+(cellh-30-im.height)//2;sheet.paste(im,(x0,y0));draw.text(((i%columns)*cellw+5,(i//columns)*cellh+4),f'~{i*5:03d}s',fill='white')
 sheet.save(d/'contact.jpg',quality=90);(d/'sampling.json').write_text(json.dumps({'id':id,'duration':duration,'spacing_seconds':5,'frames':len(files),'note':'fps sampling approximately at listed seconds; aspect preserved via thumbnail and padding'},indent=2));print(id,'duration',duration,'frames',len(files),flush=True)
