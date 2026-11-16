from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,math
p=Path('/Users/nhanvu/Documents/code/behind-the-image/research_media/great-art-explained'); jobs=[('44LZPWLDYOQ',8,24),('EFxxmc0EZTI',0,15),('UKjrMZSIhvg',38,18)]
for id,start,length in jobs:
 d=p/'analysis-shorts'/id/('dense-'+str(start));d.mkdir(parents=True,exist_ok=True);subprocess.run(['/opt/homebrew/bin/ffmpeg','-hide_banner','-loglevel','error','-ss',str(start),'-i',str(p/(id+'.mp4')),'-t',str(length),'-vf','fps=1','-q:v','3','-y',str(d/'%03d.jpg')],check=True); files=sorted(d.glob('*.jpg'));cw=160;ch=250;cols=6;sheet=Image.new('RGB',(cw*cols,ch*math.ceil(len(files)/cols)),'#222');draw=ImageDraw.Draw(sheet)
 for i,f in enumerate(files):
  im=Image.open(f).convert('RGB');im.thumbnail((cw-8,ch-30));x=(i%cols)*cw+(cw-im.width)//2;y=(i//cols)*ch+22+(ch-30-im.height)//2;sheet.paste(im,(x,y));draw.text(((i%cols)*cw+4,(i//cols)*ch+3),f'~{start+i}s',fill='white')
 sheet.save(d/'contact.jpg',quality=92);print(id,start,flush=True)
