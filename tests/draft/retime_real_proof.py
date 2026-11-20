from pathlib import Path
import json, shutil
from bti.draft import retime
from bti.engine import registry, storyboard, techniques
from bti.engine.timing import Timing
from bti.picks.auto.images import save_scaled
from bti.draft.crop import main

src = Path(r'D:\code\behind-the-image\projects\eligius')
dst = Path('.scratch/retimefix')
dst.mkdir(parents=True, exist_ok=True)
for name in ('storyboard.json', 'timing.json'):
    shutil.copyfile(src/name, dst/name)
sb = json.loads((dst/'storyboard.json').read_text(encoding='utf-8'))
t = json.loads((dst/'timing.json').read_text(encoding='utf-8'))
b = registry.load_bundle(sb.get('style') or 'gae')
new, report = retime.retime(sb, t, b.style, defaults=b.param_defaults)
print('RETIME REPORT', json.dumps(report, ensure_ascii=False))
nt = retime.normalized(t)
issues = storyboard.validate(new, Timing({'duration': nt['duration'], 'words': nt['words']}), b, src)
print('VALIDATOR ERRORS', json.dumps([x for x in issues if x.get('level') == 'error'], ensure_ascii=False))
again, rep2 = retime.retime(new, t, b.style, defaults=b.param_defaults)
print('SECOND IDENTICAL', again == new, 'OVERLAYS', json.dumps(rep2['overlays']))
work = dst/'cropwork'
(work/'inputs').mkdir(parents=True, exist_ok=True)
(work/'images').mkdir(exist_ok=True)
(work/'look').mkdir(exist_ok=True)
sw, sh, cw, ch = save_scaled(src/'media/goldsmith_his_shop_3bc1.jpg', work/'images/main.jpg', 1568)
(work/'inputs/assets.json').write_text(json.dumps({'main_asset':'A', 'assets':{'A':{'file':'images/main.jpg','source_size':[sw, sh]}}}), encoding='utf-8')
import os
os.chdir(work)
main(['--grid','-o','look/grid.jpg'])
