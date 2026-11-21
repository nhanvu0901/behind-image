"""Which copy of a picture a draft works from: the picks' (the pictures step) or the saved storyboard's (worker regionsrc).

One function for the compiler (`compile._Compiler._merge_assets`), the work folder the model reads (`workspace.build`, `inputs/assets.json` and
`inputs/compile_input.json`), the helpers (`./defaults`, `./still`, `./check`) and the reading of `out/regions.json` (`run.py`), so that all of them
show the same regions.

The rule:
- the facts of the STORED FILE (`FILE_FACTS`: path, kind, pixel size, the source's own size, a video's length) always come from the picks;
- an EDIT (`edit=True`, the ids of the shots it may change are given): everything else comes from the saved copy, as it is (the shots outside the
  scope must come back identical);
- a FULL DRAFT (`edit=False`): the pictures step is where regions are made and measured, so the painted area (`content_box`) and every region the
  PICKS hold come from the picks, each region whole (its box and its fields `tight`, `thing`, `rough`, `label`), replacing the saved region of the
  same name. A region only the saved storyboard has (an earlier draft, or a person, added it there) is kept. Everything else on the saved copy
  (title, artist, year, credit, anything a person or an agent added) is kept.
"""
from __future__ import annotations

import copy

from bti.media.assets import scale_regions

# What describes the STORED FILE of a picture: its path, kind, pixel size, the source's own size kept beside it, a video's length. These are facts of the
# file and always come from the picks (their sizes were corrected to the file by `reconcile_sizes`); a storyboard saved before a correction must not keep the
# old ones (the warning `asset_size_mismatch` would never clear).
FILE_FACTS = ("file", "kind", "width", "height", "original_width", "original_height", "duration")


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def saved_asset(saved: dict, pick, *, edit: bool) -> dict:
    """The saved storyboard's copy of an asset, brought up to date from the picks' record of it (see the module's rule). `pick` is None for a picture only the
    storyboard has: its own record."""
    out = copy.deepcopy(saved)
    if not isinstance(pick, dict):
        return out
    old_w, old_h = out.get("width"), out.get("height")
    for k in FILE_FACTS:
        if k in pick:
            out[k] = copy.deepcopy(pick[k])
        else:
            out.pop(k, None)                             # a fact the picks do not state is not kept from another file
    if "content_box" in pick and not edit:               # panelbox: the painted area is a fact of the picture too: a draft takes the picks' (a person may have set it)
        out["content_box"] = copy.deepcopy(pick["content_box"])
    new_w, new_h = out.get("width"), out.get("height")
    if all(_number(v) for v in (old_w, old_h, new_w, new_h)) and (old_w, old_h) != (new_w, new_h):
        scale_regions(out.get("regions"), new_w / old_w, new_h / old_h)     # the regions were drawn in the old size: the same scaling as `reconcile_sizes`
    if not edit:
        pick_regions = {n: r for n, r in (pick.get("regions") or {}).items() if isinstance(r, dict)} if isinstance(pick.get("regions"), dict) else {}
        if pick_regions:                                 # the picks' regions replace the saved ones of the same name (already in the picks' size); the others stay
            saved_regions = out.get("regions") if isinstance(out.get("regions"), dict) else {}
            merged = {n: copy.deepcopy(r) for n, r in pick_regions.items()}
            merged.update({n: r for n, r in saved_regions.items() if n not in pick_regions})
            out["regions"] = merged
    return out


def merged_assets(picks_assets: dict | None, saved_assets: dict | None, *, edit: bool) -> dict:
    """Every asset a draft works from: the picks' assets, each replaced by `saved_asset` where the saved storyboard also has it, and the pictures only the
    storyboard has. A deep copy: the callers may change it."""
    assets = copy.deepcopy(picks_assets or {})
    for k, a in (saved_assets or {}).items():
        if isinstance(a, dict):
            assets[k] = saved_asset(a, assets.get(k), edit=edit)
    return assets
