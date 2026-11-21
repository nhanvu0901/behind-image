"""Mapping check against the six real Arnolfini and Eligius reference boxes from the tightbox task brief (`data/grid.py`, `data/vlmcheck.py`, `data/vlm_boxes.json`)."""
from bti.picks.auto import tighten

ARNOLFINI_SIZE = (3840, 5253)
ELIGIUS_SIZE = (3469, 4000)
ELIGIUS_CB = {"x0": 100, "y0": 106, "x1": 3363, "y1": 3900, "how": "found"}

CASES = [
    ("T01_carved_woman", ARNOLFINI_SIZE, None, [2227, 893, 2765, 1629], [298, 162, 398, 392], (2147, 783), (748, 1024), [2425, 934, 2519, 1149]),
    ("T02_gargoyle", ARNOLFINI_SIZE, None, [1728, 1891, 2496, 2627], [595, 172, 692, 328], (1613, 1781), (1024, 981), [2193, 1949, 2287, 2101]),
    ("T04_lit_candle", ARNOLFINI_SIZE, None, [1382, 0, 2534, 1050], [262, 176, 304, 300], (1210, 0), (1024, 826), [1593, 257, 1654, 438]),
    ("T16_shark_teeth", ELIGIUS_SIZE, ELIGIUS_CB, [2671, 1240, 3053, 1720], [338, 372, 458, 634], (2614, 1168), (814, 1024), [2820, 1395, 2893, 1554]),
    ("T13_coins", ELIGIUS_SIZE, ELIGIUS_CB, [2637, 3040, 3053, 3480], [258, 226, 784, 842], (2575, 2974), (967, 1024), [2719, 3100, 3013, 3444]),
    ("T18_buckle", ELIGIUS_SIZE, ELIGIUS_CB, [2428, 920, 2810, 1240], [280, 158, 744, 762], (2371, 872), (1024, 859), [2507, 949, 2731, 1241]),
]


def test_six_real_reference_boxes_map_within_two_pixels():
    for tid, size, cb, rough, vlm_box, exp_xy, exp_cutout, exp_stored in CASES:
        geom = tighten.cutout_geom(rough, size, cb, margin=tighten.MARGIN_INITIAL, long_side=tighten.CUTOUT_LONG_SIDE)
        assert tuple(geom["crop_px"][:2]) == exp_xy, (tid, geom)
        assert tuple(geom["cutout_size"]) == exp_cutout, (tid, geom)
        got = tighten.cutout_to_stored(vlm_box, geom)
        deltas = [abs(a - b) for a, b in zip(got, exp_stored)]
        assert max(deltas) <= 2, (tid, got, exp_stored, deltas)
        back = tighten.stored_to_cutout(got, geom)
        for a, b in zip(back, vlm_box):
            assert abs(a - b) <= 3.0, (tid, back, vlm_box)


def test_eligius_edge_cutout_clamps_to_content_box():
    geom = tighten.cutout_geom([20, 30, 500, 500], ELIGIUS_SIZE, ELIGIUS_CB, margin=tighten.MARGIN_INITIAL)
    assert geom["crop_px"][0] >= ELIGIUS_CB["x0"] and geom["crop_px"][1] >= ELIGIUS_CB["y0"]
    assert geom["crop_px"][2] <= ELIGIUS_CB["x1"] and geom["crop_px"][3] <= ELIGIUS_CB["y1"]
