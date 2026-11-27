"""Exercise failed saved plan on a private snapshot copy; never invoke a model."""
from pathlib import Path
import json
import shutil
from bti.picks import doc
from bti.picks.auto import write
from bti.ops.log import ChangeLog
from bti.script.store import read_object
from bti.visual import regions, validate

source = Path(r'D:\code\behind-the-image\projects\arnolfini-v3')
out = Path(r'C:\Users\ADMIN\AppData\Local\Temp\bti-visual-12zbdfg4\out')
target = Path('.scratch/regionlimit-real/arnolfini-v3')
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(source, target, ignore=shutil.ignore_patterns('cache', 'export', 'audio', 'voice', 'history', 'auto_runs', 'proposals', '.env', '*.env'), dirs_exist_ok=False)
for name in ('regions.json', 'visual.json'):
    shutil.copy2(out / name, target.parent / name)
plan = json.loads((target.parent / 'visual.json').read_text(encoding='utf-8'))
new = json.loads((target.parent / 'regions.json').read_text(encoding='utf-8'))
picks = doc.load_or_new(target)
key = picks['main_asset']
asset = picks['assets'][key]
old = asset['regions']
print('before:', len(old), 'new plan regions:', len(new))
owner = regions.agent_regions(ChangeLog(target), key, old)
remove = regions.cleanup_names(old, plan, read_object(target / 'storyboard.json', 'storyboard') or {}, owner)
print('agent provenance:', len(owner), 'unreferenced candidates:', len(remove))
# Existing picks remain valid during this isolated region-write check.
remove -= set(regions._strings(picks.get('beats', {})))
remove -= set(regions._strings(picks.get('names', [])))
remaining = {n: r for n, r in old.items() if n not in remove}
keep, dropped = write.final_regions({'regions': new}, {'regions': {}})
ops, names, _ = write.region_ops(key, {**asset, 'regions': remaining}, keep, asset['width'], asset['height'])
print('removals:', len(remove), 'additions:', len(ops), 'renamed:', sum(names.get(n) != n for n in new), 'dropped:', len(dropped))
writer = write.Writer(target, 'agent:regionlimit-test', redo=True)
result = writer.send([{'op': 'remove_region', 'asset': key, 'region': n} for n in sorted(remove)] + ops, 'regionlimit real-data check')
after = doc.load_or_new(target)
print('after:', len(after['assets'][key]['regions']), 'batch:', result['batch'])
issues = validate.validate(plan, read_object(target / 'timing.json', 'timing'), after)
errors = [i for i in issues if i.get('level') != 'review']
print('visual validation errors:', len(errors), 'first:', errors[:2])
if not errors:
    from bti.visual import store
    before = store.load(target)
    rev = store.save(target, plan, base_rev=store.revision(before) if before else None, actor='agent:regionlimit-test', compose=False)
    print('visual saved:', bool(rev))
