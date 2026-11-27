"""Build isolated visual-planning work folders from current source data."""
from __future__ import annotations

import json
import hashlib
import re
import stat
import sys
import tempfile
from pathlib import Path
from bti.picks.auto import images

REPO = Path(__file__).resolve().parents[2]


def _json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def build_plan(inp, timing: dict, *, root: Path | None = None, instruction: str | None = None) -> Path:
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix='bti-visual-'))
    for part in ('inputs', 'images', 'out', 'look'):
        (root / part).mkdir(parents=True, exist_ok=True)
    p = inp.painting
    sw, sh, cw, ch = images.save_scaled(p.file, root / 'images/main.jpg', images.VIEW_SIDE, 90)
    images.save_scaled(p.file, root / 'inputs/main_large.jpg', images.LARGE_SIDE, 90)
    images.grid(root / 'images/main.jpg', root / 'images/grid.jpg')
    regions = {}
    for index, (name, region) in enumerate(p.regions.items()):
        thumbnail = f'images/region_{index}.jpg'
        images.crop(p.file, region['box'], root / thumbnail, 640)
        regions[name] = {'box': region['box'], 'label': region['label'], 'thumbnail': thumbnail}
    _json(root / 'inputs/painting.json', {'key': p.key, 'title': p.title, 'artist': p.artist, 'year': p.year,
          'source_size': [sw, sh], 'image': 'images/main.jpg', 'image_size': [cw, ch], 'large': 'inputs/main_large.jpg',
          'regions': regions})
    catalogue = []
    subject_names = {s.get('id'): s.get('name') for s in inp.picks.get('subjects', []) if isinstance(s, dict) and s.get('id') and s.get('name')}
    for index, (key, asset) in enumerate(inp.picks['assets'].items()):
        if key == inp.picks.get('main_asset'):
            continue
        thumb = f'images/pool_{index}.jpg'
        try:
            images.save_scaled(inp.pdir / asset['file'], root / thumb, 640, 85)
        except (images.ImageError, KeyError, OSError):
            thumb = None
        catalogue.append({'key': key, 'thumbnail': thumb, 'caption': asset.get('caption', ''),
                          'shows': [subject_names.get(i, i) for i in asset.get('shows', [])], 'period': asset.get('period')})
    _json(root / 'inputs/catalogue.json', catalogue)
    words = timing['words']
    sentences = []
    for beat in timing['beats']:
        start = beat['w0']
        for i in range(beat['w0'], beat['w1']):
            if re.search(r'[.!?][\"\u2019\u201d)]*$', words[i]['w']) or i == beat['w1'] - 1:
                sentences.append({'line': beat['id'], 'w0': start, 'w1': i + 1,
                                  'text': ' '.join(w['w'] for w in words[start:i+1])})
                start = i + 1
    timing_beats = {b['id']: b for b in timing['beats']}
    _json(root / 'inputs/narration.json', {'lines': [{'id': b['id'], 'text': b['text'], 'w0': timing_beats[b['id']]['w0'], 'w1': timing_beats[b['id']]['w1']} for b in inp.beats], 'sentences': sentences})
    _json(root / 'inputs/timing.json', timing)
    _json(root / 'inputs/picks.json', {'main_asset': inp.picks['main_asset'], 'assets': inp.picks['assets']})
    _json(root / 'inputs/facts.json', inp.facts)
    _json(root / 'inputs/dossier.json', {'identity': inp.identity, 'details': inp.details})
    narration_file = inp.pdir / 'script/narration.json'
    if not narration_file.is_file():
        narration_file = inp.pdir / 'narration.json'
    timing_file = inp.pdir / 'timing.json'
    narration_hash = hashlib.sha1(narration_file.read_bytes()).hexdigest() if narration_file.is_file() else inp.narration_rev
    timing_hash = hashlib.sha1(timing_file.read_bytes()).hexdigest() if timing_file.is_file() else hashlib.sha1(json.dumps(timing, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
    from bti.ops.log import ChangeLog
    from bti.script.store import read_object
    from bti.visual.regions import agent_regions
    current_regions = inp.picks['assets'][p.key].get('regions', {})
    storyboard = read_object(inp.pdir / 'storyboard.json', 'storyboard') or {}
    eligible = sorted(agent_regions(ChangeLog(inp.pdir), p.key, current_regions))
    _json(root / 'inputs/context.json', {'mode': 'plan', 'made_from': {'narration': narration_hash, 'timing': timing_hash},
          'agent_regions': eligible, 'storyboard': storyboard,
          'legacy_names': inp.picks.get('names', []), 'old_beats': inp.picks.get('beats', {})})
    windows = sys.platform == 'win32'
    for command in ('check', 'crop'):
        module = 'bti.visual.check' if command == 'check' else 'bti.picks.auto.helper'
        arg = '' if command == 'check' else ' crop'
        f = root / (command + ('.cmd' if windows else ''))
        if windows:
            f.write_text(f'@echo off\r\nset "PYTHONPATH={REPO}"\r\n"{sys.executable}" -m {module}{arg} %*\r\n', encoding='utf-8')
        else:
            f.write_text(f'#!/bin/sh\nPYTHONPATH=\'{REPO}\' exec \'{sys.executable}\' -m {module}{arg} "$@"\n', encoding='utf-8')
            f.chmod(f.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    text = instruction if instruction is not None else (REPO / 'skills/visual_plan/PLAN.template.md').read_text(encoding='utf-8')
    (root / 'TASK.md').write_text(text.replace('{{CHECK_CMD}}', '.\\check.cmd' if windows else './check').replace('{{CROP_CMD}}', '.\\crop.cmd' if windows else './crop'), encoding='utf-8')
    return root


def build_choose(pdir: Path, visual: dict, search: dict, *, root: Path | None = None, main: dict | None = None, regions: dict | None = None, limits=None, region_context: dict | None = None) -> Path:
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix='bti-visual-choose-'))
    for part in ('inputs', 'images', 'out'):
        (root / part).mkdir(parents=True, exist_ok=True)
    rows = []
    for index, want in enumerate(visual['wanted']):
        state = search.get('wants', {}).get(want['id'], {})
        candidates = state.get('candidates') or []
        sheet = None
        if candidates:
            sheet = f'images/want_{index}.jpg'
            images.contact_sheet([(str(c['n']), Path(pdir) / c['thumb'] if c.get('thumb') else None) for c in candidates], root / sheet)
        rows.append({**want, 'sheet': sheet, 'tried': state.get('tried_queries', []),
                     'candidates': [{k: v for k, v in c.items() if k not in ('thumb',)} for c in candidates]})
    _json(root / 'inputs/wants.json', rows)
    _json(root / 'inputs/visual.json', visual)
    _json(root / 'inputs/search.json', search)
    _json(root / 'inputs/context.json', {'mode': 'choose', **(region_context or {})})
    windows = sys.platform == 'win32'
    f = root / ('check.cmd' if windows else 'check')
    if windows:
        f.write_text(f'@echo off\r\nset "PYTHONPATH={REPO}"\r\n"{sys.executable}" -m bti.visual.check %*\r\n', encoding='utf-8')
    else:
        f.write_text(f"#!/bin/sh\nPYTHONPATH='{REPO}' exec '{sys.executable}' -m bti.visual.check \"$@\"\n", encoding='utf-8')
        f.chmod(f.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if regions:
        from bti.picks.auto import workspace as old_workspace, shapes
        entries = []
        for name, region in regions.items():
            raw = shapes.box_to_region(region['box'], main['width'], main['height'])
            entries.append({'name': name, 'raw': raw, 'label': region['what'], 'thing': region.get('thing', ''), 'lines': [], 'line_texts': {}})
        old_workspace.build_tighten(pdir, main, entries, limits, root=root / 'tighten')
        (root / 'tighten/TASK.md').write_text('Follow the region instructions in ../TASK.md; write out/tighten.json relative to the choose folder.\n', encoding='utf-8')
    instruction = (REPO / 'skills/visual_plan/CHOOSE.template.md').read_text(encoding='utf-8')
    instruction = instruction.replace('{{CHECK_CMD}}', '.\\check.cmd' if windows else './check')
    if regions:
        instruction += '\nThe check covers choices and region bounds together.\n'
    (root / 'TASK.md').write_text(instruction, encoding='utf-8')
    return root
