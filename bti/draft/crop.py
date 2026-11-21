"""Draw a source-pixel grid or a ruled crop of the draft's main painting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bti.draft.check import refuse_outside
from bti.engine import viewchecks as VC
from bti.media import contentbox as CB
from bti.picks.auto import images


def main(argv=None):
    import cv2
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--grid', action='store_true')
    group.add_argument('--box', help='x0,y0,x1,y1 in source pixels')
    group.add_argument('--region', help='named region on the main painting')
    p.add_argument('-o', '--out', required=True)
    a = p.parse_args(argv)
    if refuse_outside(a.out, 'the output path') or not a.out.replace('\\', '/').startswith('look/'):
        print('ERROR output must be inside look/')
        return 2
    root = Path.cwd()
    data = json.loads((root / 'inputs/assets.json').read_text(encoding='utf-8'))
    main_key = data['main_asset']
    asset = data['assets'][main_key]
    sw, sh = asset['source_size']
    try:
        im = images.read(root / asset['file'])
    except images.ImageError as exc:
        print('ERROR %s' % exc)
        return 1
    h, w = im.shape[:2]
    reg_obj = None
    try:
        if a.grid:
            x0, y0, x1, y1 = (0, 0, sw, sh)
        elif a.region:
            r = (asset.get('regions') or {}).get(a.region)
            if not isinstance(r, dict):
                print('ERROR no region %r on %s (regions: %s)' % (a.region, main_key, ', '.join(sorted(asset.get('regions') or {})) or 'none'))
                return 2
            b = VC.region_box(r)
            if b is None:
                print('ERROR region %r has no bounding box (x, y, rx, ry)' % a.region)
                return 2
            x0, y0, x1, y1 = max(0, int(round(b[0]))), max(0, int(round(b[1]))), min(sw, int(round(b[2]))), min(sh, int(round(b[3])))
            reg_obj = r
        else:
            x0, y0, x1, y1 = tuple(int(x.strip()) for x in a.box.split(','))
            if not (0 <= x0 < x1 <= sw and 0 <= y0 < y1 <= sh):
                raise ValueError()
            reg_obj = {'x': (x0 + x1) / 2.0, 'y': (y0 + y1) / 2.0, 'rx': (x1 - x0) / 2.0, 'ry': (y1 - y0) / 2.0}
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
    if reg_obj is not None:
        box = None
        if (root / 'picks.json').is_file():
            try:
                pk = json.loads((root / 'picks.json').read_text(encoding='utf-8'))
                box = CB.box_of((pk.get('assets') or {}).get(main_key), root)
            except Exception:       # noqa: BLE001
                box = None
        finfo = VC.region_frame_info(reg_obj, sw, sh, box)
        spot = ' (under 40%% -> use HI-01)' if finfo.get('needs_spotlight') else ''
        print('compiler end frame: centre (%.1f, %.1f) zoom %.4f rect %s; fill %.1f%% W x %.1f%% H%s' % (
            finfo['cx'], finfo['cy'], finfo['zoom'], finfo['rect'],
            100.0 * finfo.get('width_share', 0.0), 100.0 * finfo.get('height_share', 0.0), spot))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
