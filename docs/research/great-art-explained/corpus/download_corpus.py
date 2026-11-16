import json, pathlib, subprocess, time, re, shutil, threading, queue, os, datetime
P=pathlib.Path(__file__).resolve().parent; ROOT=pathlib.Path('/Users/nhanvu/Documents/code/behind-the-image'); MEDIA=ROOT/'research_media/great-art-explained'; MEDIA.mkdir(parents=True,exist_ok=True)
xs=json.loads((P/'inventory.json').read_text()); group={x['id']:g for g in ('a','b') for x in json.loads((P/f'partition-{g}.json').read_text())}; archive=P/'download-archive.txt'; state=P/'download-state.json'; logs=P/'download-logs'; logs.mkdir(exist_ok=True)
statuses={x['id']:{'status':'pending'} for x in xs}; statuses.update(json.loads(state.read_text()) if state.exists() else {}); block_re=re.compile(r'HTTP Error 429|too many requests|confirm you.re not a bot|confirm you are not a bot|unusual traffic|captcha',re.I)
def send(target,msg):
 try: subprocess.run(['/Users/nhanvu/.local/bin/hc','send',target,msg],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
 except Exception: pass
def valid(x):
 f=MEDIA/(x['id']+'.mp4')
 if not f.exists(): return False
 try:
  r=subprocess.run(['/opt/homebrew/bin/ffprobe','-v','error','-show_entries','format=duration:stream=codec_type','-of','json',str(f)],capture_output=True,text=True,timeout=30)
  d=json.loads(r.stdout); kinds={s['codec_type'] for s in d.get('streams',[])}; duration=float(d['format']['duration']); expected=x.get('duration')
  return r.returncode==0 and {'audio','video'}<=kinds and duration>0 and (not expected or duration>=expected*.95)
 except Exception: return False
def save():
 state.write_text(json.dumps(statuses,ensure_ascii=False,indent=2)+'\n'); counts={s:sum(v['status']==s for v in statuses.values()) for s in ('downloaded','unavailable','restricted_age','error','blocked','deferred','pending')}; total=sum((MEDIA/(x['id']+'.mp4')).stat().st_size for x in xs if (MEDIA/(x['id']+'.mp4')).exists()); lines=['# Corpus coverage','',f"Cập nhật: {datetime.datetime.now().astimezone().isoformat()}",f'Public listed: {len(xs)} (inventory tab công khai; không đảm bảo từng video vẫn khả dụng).',f"Downloaded và ffprobe hợp lệ: {counts['downloaded']}",f"Unavailable riêng: {counts['unavailable']}",f"Restricted age (yêu cầu xác nhận tuổi): {counts['restricted_age']}",f"Blocked trực tiếp: {counts['blocked']}",f"Hoãn chưa thử do dừng requests: {counts['deferred']}",f"Lỗi khác: {counts['error']}",f"Chưa thử / pending: {counts['pending']}",f'Tổng bytes MP4 theo inventory (kể cả tệp chưa xác minh): {total}',f'Trạng thái chi tiết: download-state.json; lỗi từng ID: download-logs/.', '', '| ID | Status | Chi tiết |','|---|---|---|']
 for x in xs:
  s=statuses[x['id']]; lines.append('| '+x['id']+' | '+s['status']+' | '+str(s.get('detail','')).replace('|','/').replace('\n',' ')[:400]+' |')
 (P/'coverage.md').write_text('\n'.join(lines)+'\n')
def archive_sync():
 archive.write_text(''.join('youtube '+i+'\n' for i,s in statuses.items() if s['status']=='downloaded'))
for x in xs:
 if valid(x): statuses[x['id']]={'status':'downloaded','detail':'MP4 hiện có được ffprobe xác minh'}
archive_sync();save()
for g,t in [('a','t2m'),('b','t2n')]:
 ids=[i for i,s in statuses.items() if s['status']=='downloaded' and group[i]==g]
 if ids: send(t,'Media MP4 đã ffprobe hợp lệ và sẵn sàng: '+', '.join(ids))
ordered=sorted(xs,key=lambda x:(0 if (x['duration'] or 0)>1800 and x['id'] not in ('cgTvoB6XHdA','tEEq5DTRXr0') else 1 if (x['duration'] or 0)>1800 else 3 if x['tab']=='shorts' else 2,-(x['duration'] or 0),x['id']))
downloaded=0; blocked=None
for idx,x in enumerate(ordered):
 id=x['id']
 if statuses[id]['status']!='pending': continue
 if shutil.disk_usage(MEDIA).free<30*1024**3:
  blocked='Dung lượng trống dưới 30 GiB'; break
 cmd=['/Users/nhanvu/.local/bin/yt-dlp','--ignore-config','--no-cookies','--no-playlist','--retries','0','--fragment-retries','0','--extractor-retries','0','--sleep-requests','2','--sleep-interval','3','--max-sleep-interval','6','--continue','--no-overwrites','--download-archive',str(archive),'--write-info-json','--write-description','--ffmpeg-location','/opt/homebrew/bin','-f','bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/bv*[height<=720]+ba/b[height<=720]','--merge-output-format','mp4','-o',str(MEDIA/'%(id)s.%(ext)s'),x['url']]
 print('START',id,x['title'],flush=True)
 proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1); q=queue.Queue()
 def reader():
  for line in proc.stdout: q.put(line)
  q.put(None)
 threading.Thread(target=reader,daemon=True).start(); lines=[]; ended=False; reason=None
 with (logs/(id+'.log')).open('a') as f:
  f.write('\n--- Lượt thử tiếp ---\n')
  while not ended:
   try: line=q.get(timeout=1)
   except queue.Empty: line=''
   if line is None: ended=True; continue
   if line:
    f.write(line); f.flush(); lines.append(line)
    if block_re.search(line): reason='YouTube 429 hoặc bot challenge: '+line.strip(); proc.terminate(); break
   if shutil.disk_usage(MEDIA).free<30*1024**3: reason='Dung lượng trống dưới 30 GiB'; proc.terminate(); break
  if reason:
   try: proc.wait(timeout=10)
   except subprocess.TimeoutExpired: proc.kill(); proc.wait()
  else: proc.wait()
 output=''.join(lines)
 if reason: statuses[id]={'status':'blocked','detail':reason};blocked=reason
 elif proc.returncode==0 and valid(x):
  statuses[id]={'status':'downloaded','detail':'retry_success: Đã tải tiếp và ffprobe xác minh' if statuses[id].get('previous',{}).get('status') in ('error','blocked') else 'Đã tải và ffprobe xác minh','previous':statuses[id].get('previous')}; downloaded+=1; send('t2m' if group[id]=='a' else 't2n',f'Media hoàn chỉnh và ffprobe hợp lệ: {id}.mp4')
 elif re.search(r'private video|video unavailable|has been removed|not available|members.only|premieres in|confirm your age|age.restricted',output,re.I): statuses[id]={'status':'unavailable','detail':output[-500:].strip()}
 else: statuses[id]={'status':'error','detail':f'yt-dlp exit {proc.returncode}; '+output[-400:].strip()}
 archive_sync();save();print('RESULT',id,statuses[id]['status'],flush=True)
 if downloaded and downloaded%10==0 and statuses[id]['status']=='downloaded': send('t1z',f'Corpus: đã tải thêm {downloaded}; tổng verified {sum(s["status"]=="downloaded" for s in statuses.values())}/{len(xs)}. Xem {state}.')
 if blocked: break
 time.sleep(3)
if blocked:
 for s in statuses.values():
  if s['status']=='pending': s.update(status='deferred',detail='Chưa thử trong lượt này do dừng toàn bộ requests: '+blocked)
 save();send('t1z','BLOCKER corpus: '+blocked+'. Đã dừng toàn bộ YouTube requests; xem coverage.md và download-state.json.')
else: send('t1z',f'Corpus kết thúc: {sum(s["status"]=="downloaded" for s in statuses.values())}/{len(xs)} verified; xem coverage.md và download-state.json để biết mọi trạng thái và bytes.')
print('FINISHED',blocked or 'all attempted',flush=True)
