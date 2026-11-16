from pathlib import Path
import json,subprocess,re,csv,collections,datetime
root=Path('/Users/nhanvu/Documents/code/behind-the-image');p=root/'docs/research/great-art-explained/corpus'; m=root/'research_media/great-art-explained'; inv=json.loads((p/'inventory.json').read_text());state=json.loads((p/'download-state.json').read_text());ledgers={g:(p/f'visual-{g}'/('ledger.md' if g=='a' else 'coverage.md')).read_text() for g in ('a','b')};short_report=(p/'visual-shorts/coverage.md').read_text(); data=[]
for x in inv:
 id=x['id']; status=state[id]['status']; path=m/(id+'.mp4'); measured=None
 if path.exists() and status=='downloaded':
  r=subprocess.run(['/opt/homebrew/bin/ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_type,width,height','-of','json',str(path)],capture_output=True,text=True,timeout=30)
  try:
   d=json.loads(r.stdout);v=next(z for z in d['streams'] if z['codec_type']=='video'); measured={'duration_seconds':float(d['format']['duration']),'width':v['width'],'height':v['height'],'bytes':int(d['format']['size']),'audio_present':any(z['codec_type']=='audio' for z in d['streams']),'ffprobe_ok':r.returncode==0}
  except Exception as e: measured={'ffprobe_ok':False,'error':str(e)}
 upload=None; info=None
 for candidate in (m/(id+'.info.json'),m/(id+'.json')):
  if candidate.exists():
   try: doc=json.loads(candidate.read_text());upload=doc.get('upload_date');info=str(candidate.relative_to(root));break
   except (ValueError,OSError):pass
 reviewed=False;source=None
 if x['tab']=='shorts': reviewed=('`'+id+'` |') in short_report; source='visual-shorts/coverage.md' if reviewed else None
 else:
  for g,txt in ledgers.items():
   lines=[line for line in txt.splitlines() if re.search(r'(?<![\w-])'+re.escape(id)+r'(?![\w-])',line)]
   if any(('xem tay' in line.lower() or 'candidate' in line.lower() or 'đã xem mẫu' in line.lower()) and 'chờ' not in line.lower() for line in lines): reviewed=True;source=f'visual-{g}/'+('ledger.md' if g=='a' else 'coverage.md');break
 data.append({**x,'download_status':status,'download_detail':state[id].get('detail',''),'media':measured,'upload_date':upload,'upload_date_source':info,'visual_reviewed_sampled':reviewed,'visual_review_source':source})
(p/'manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n'); fields=['id','title','tab','download_status','metadata_duration_seconds','measured_duration_seconds','width','height','bytes','upload_date','visual_reviewed_sampled','visual_review_source']
with (p/'manifest.tsv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields,delimiter='\t');w.writeheader()
 for x in data:
  md=x['media'] or {};w.writerow({'id':x['id'],'title':x['title'],'tab':x['tab'],'download_status':x['download_status'],'metadata_duration_seconds':x['duration'],'measured_duration_seconds':md.get('duration_seconds'),'width':md.get('width'),'height':md.get('height'),'bytes':md.get('bytes'),'upload_date':x['upload_date'],'visual_reviewed_sampled':x['visual_reviewed_sampled'],'visual_review_source':x['visual_review_source']})
print('total',len(data),'statuses',dict(collections.Counter(x['download_status'] for x in data)),'reviewed',sum(x['visual_reviewed_sampled'] for x in data),'reviewed_by_tab',dict(collections.Counter(x['tab'] for x in data if x['visual_reviewed_sampled'])),'ffprobe_bad',[x['id'] for x in data if x['download_status']=='downloaded' and (not x['media'] or not x['media'].get('ffprobe_ok') or not x['media'].get('audio_present'))],flush=True)
