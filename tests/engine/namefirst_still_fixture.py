"""Prepare local fixtures for the two name-strip stills; never touches a project."""
import json
from pathlib import Path
from PIL import Image

root = Path('.scratch/namefirst/stills')
source = Path('tests/engine/fixtures/viewer')
original = json.loads((source / 'final.json').read_text(encoding='utf-8'))
for folder, sub in (('one', ''), ('two', 'most often named as the wife')):
    dest = root / folder
    (dest / 'media').mkdir(parents=True, exist_ok=True)
    document = json.loads(json.dumps(original))
    document['shots'][0]['overlays'] = [{
        'id': 'name', 'technique': 'X-ANN-01', 'start': {'t': 0}, 'dur': 8,
        'params': {'text': 'COSTANZA TRENTA' if sub else 'SETTLE', 'sub': sub}, 'slots': {},
    }]
    (dest / 'storyboard.json').write_text(json.dumps(document), encoding='utf-8')
    (dest / 'timing.json').write_bytes((source / 'timing.json').read_bytes())
    with Image.open(source / 'painting.jpg') as image:
        image.resize((3840, 5253)).save(dest / 'media/van_eyck_arnolfini.jpg', quality=90)
