"""Read-only real-project probe; writes copies only under the snapshot."""
import json
import os
import shutil
from pathlib import Path

from bti.draft.run import _agent_module
from bti.draft.providers import claudecode as runner
from bti.script.providers import claudecode

os.environ['ANTHROPIC_API_KEY'] = 'fake-ignored-value'
fake_config = Path.cwd() / 'run' / 'apikey-real-probe-config'
fake_config.parent.mkdir(parents=True, exist_ok=True)
fake_config.write_text('ANTHROPIC_API_KEY=fake-apikey-test-value\n', encoding='utf-8')
os.environ['BTI_ENV_FILE'] = str(fake_config)
root = Path(r'D:\code\behind-the-image\projects')
out = Path.cwd() / 'run' / 'apikey-real-probe'
out.mkdir(parents=True, exist_ok=True)
for name in ('arnolfini-v3', 'eligius'):
    source, dest = root / name, out / name
    dest.mkdir(exist_ok=True)
    for rel in ('project.json', 'agent.json', 'picks.json', 'visual.json', 'script/narration.json'):
        f = source / rel
        if f.is_file():
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
    counts = {}
    for rel in ('picks.json', 'visual.json', 'script/narration.json'):
        p = dest / rel
        if p.is_file():
            doc = json.loads(p.read_text(encoding='utf-8'))
            if isinstance(doc, dict):
                for field in ('assets', 'moments', 'chapters', 'beats'):
                    if isinstance(doc.get(field), (list, dict)):
                        counts[rel + ':' + field] = len(doc[field])
    sheets = []
    for folder, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if d not in ('history', 'node_modules')]
        for f in files:
            if any(word in f.lower() for word in ('contact', 'sheet', 'frame')) and Path(f).suffix.lower() in ('.jpg', '.jpeg', '.png'):
                sheets.append(Path(folder) / f)
        if sheets:
            break
    if sheets:
        shutil.copy2(sheets[0], dest / ('contact' + sheets[0].suffix.lower()))
    for model in ('claudeapi:claude-opus-5-5@high', 'claudeapi:claude-opus-5-5@medium'):
        assert _agent_module(model) is runner
        assert claudecode.session_env(model)['ANTHROPIC_API_KEY'] == 'fake-apikey-test-value'
    assert 'ANTHROPIC_API_KEY' not in claudecode.session_env('claude:claude-opus-5-5@high')
    print(name, 'project_copy=', (dest / 'project.json').is_file(), 'counts=', counts, 'image_candidates_found=', len(sheets), 'copied_suffix=', sheets[0].suffix.lower() if sheets else None)
