"""Draw a source-pixel grid or a ruled crop of the draft's main painting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bti.draft.check import refuse_outside
from bti.picks.auto import images


def main(argv=None):
    import cv2
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--grid', action='store_true')
    group.add_argument('--box', help='x0,y0,x1,y1 in source pixels')
    p.add_argument('-o', '--out', required=True)
    a = p.parse_args(argv)
    if refuse_outside(a.out, 'the output path') or not a.out.replace('\\', '/').startswith('look/'):
        print('ERROR output must be inside look/')
        return 2
    root = Path.cwd()
    data = json.loads((root / 'inputs/assets.json').read_text(encoding='utf-8'))
    asset = data['assets'][data['main_asset']]
    sw, sh = asset['source_size']
    try:
        im = images.read(root / asset['file'])
    except images.ImageError as exc:
        print('ERROR %s' % exc)
        return 1
    h, w = im.shape[:2]
    try:
        x0, y0, x1, y1 = (0, 0, sw, sh) if a.grid else tuple(int(x.strip()) for x in a.box.split(','))
        if not (0 <= x0 < x1 <= sw and 0 <= y0 < y1 <= sh):
            raise ValueError()
    except ValueError:
        print('ERROR --box needs x0,y0,x1,y1 in source pixels inside the painting')
        return 2
    piece = im[round(y0*h/sh):round(y1*h/sh), round(x0*w/sw):round(x1*w/sw)].copy()
    ph, pw = piece.shape[:2]
    for i in range(1, 10):
        x, y = round(i*pw/10), round(i*ph/10)
        if a.grid:
            cv2.line(piece, (x, 0), (x, ph-1), (0, 255, 255), 1)
            cv2.line(piece, (0, y), (pw-1, y), (0, 255, 255), 1)
        for label, pos in ((str(round(x0+(x1-x0)*i/10)), (x+2, 17)), (str(round(y0+(y1-y0)*i/10)), (2, max(17, y-3)))):
            cv2.putText(piece, label, pos, cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(piece, label, pos, cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1, cv2.LINE_AA)
        if not a.grid:
            cv2.line(piece, (x, 0), (x, min(10, ph-1)), (0, 255, 255), 1)
            cv2.line(piece, (0, y), (min(10, pw-1), y), (0, 255, 255), 1)
            cv2.line(piece, (x, ph-1), (x, max(0, ph-11)), (0, 255, 255), 1)
            cv2.line(piece, (pw-1, y), (max(0, pw-11), y), (0, 255, 255), 1)
    dest = root / a.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        images.write_jpeg(piece, dest)
    except images.ImageError as exc:
        print('ERROR %s' % exc)
        return 1
    print('wrote %s; source pixels (%d,%d) to (%d,%d)' % (a.out, x0, y0, x1, y1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
