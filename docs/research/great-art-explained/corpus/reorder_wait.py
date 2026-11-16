import os,time,json,signal,subprocess,pathlib
p=pathlib.Path('docs/research/great-art-explained/corpus/download-state.json'); pid=89099
while True:
 try: os.kill(pid,0)
 except ProcessLookupError: print('Downloader đã dừng; không tự khởi động lại',flush=True); break
 s=json.loads(p.read_text())
 if s['cgTvoB6XHdA']['status'] != 'pending':
  if s['cgTvoB6XHdA']['status']=='blocked': print('Đã gặp blocker; không khởi động lại',flush=True);break
  os.kill(pid,signal.SIGTERM);time.sleep(1)
  print('Tiếp tục với documentary ưu tiên',flush=True)
  raise SystemExit(subprocess.call(['/usr/bin/python3','-u','docs/research/great-art-explained/corpus/download_corpus.py']))
 time.sleep(.1)
