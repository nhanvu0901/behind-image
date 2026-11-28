from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from bti.scorecard import DEFAULT_TARGETS, compute_metrics, load_targets


def _metric_map(sc: dict) -> dict[str, dict]:
    return {m["key"]: m for m in sc["metrics"]}


def _write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_image(path: Path, w: int, h: int, color=(80, 90, 100)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), color).save(path)


def test_load_targets_reads_gae_quality_block():
    t = load_targets("gae")
    assert t["small_painting_max_share"] == 0.06
    assert t["small_painting_cover_threshold"] == 0.70
    assert t["marks_per_min_max"] == 3.0
    assert t["mark_max_height_pct"] == 0.30
    assert t["identity_fill_min_cover"] == 0.95
    assert t["loudness_target_lufs"] == -15.0
    assert len(t) == len(DEFAULT_TARGETS)


def test_compute_metrics_legacy_storyboard_all_twelve_metrics(tmp_path: Path):
    pdir = tmp_path / "proj"
    # Narrow tall main painting: full shot covers width ~ 600*1080/1600/1920 = 0.21 (< 0.6)
    _make_image(pdir / "assets" / "main.png", 600, 1600)
    _make_image(pdir / "assets" / "ext.png", 1920, 1080)

    _write_json(
        pdir / "picks.json",
        {
            "main_asset": "painting_a",
            "regions": {
                "WOMAN_FACE": {"label": "Gương mặt", "cx": 0.5, "cy": 0.4, "w": 0.2, "h": 0.2},
                "DOG": {"label": "Con chó", "cx": 0.5, "cy": 0.8, "w": 0.15, "h": 0.15},
            },
            "subjects": [
                {"id": "MAN", "name": "Giovanni Arnolfini", "kind": "person", "where": {"region": "WOMAN_FACE"}},
                {"id": "PHILIP", "name": "Philip the Good", "also": ["Duke of Burgundy"], "kind": "person", "where": {"region": "WOMAN_FACE"}},
                {"id": "THING_HAT", "name": "Hat", "kind": "thing", "where": {"region": "DOG"}},
            ],
        },
    )
    _write_json(
        pdir / "timing.json",
        {
            "duration": 60.0,
            "words": [
                {"w": "Welcome", "s": 0.0, "e": 1.0},
                {"w": "Giovanni", "s": 6.0, "e": 7.0},
                {"w": "Arnolfini", "s": 7.0, "e": 8.0},
                {"w": "stood", "s": 8.0, "e": 9.0},
                {"w": "And", "s": 18.0, "e": 19.0},
                {"w": "dog", "s": 22.0, "e": 23.0},
                {"w": "sleeps", "s": 34.0, "e": 35.0},
            ],
        },
    )
    sb = {
        "schema": "bti.storyboard/1",
        "title": "Test",
        "timing": "timing.json",
        "end": {"t": 60.0},
        "assets": {
            "painting_a": {
                "file": "assets/main.png",
                "width": 600,
                "height": 1600,
                "regions": {
                    "WOMAN_FACE": {"cx": 0.5, "cy": 0.4, "w": 0.2, "h": 0.2},
                    "DOG": {"cx": 0.5, "cy": 0.8, "w": 0.15, "h": 0.15},
                },
            },
            "ext_pic": {"file": "assets/ext.png", "width": 1920, "height": 1080},
        },
        "shots": [
            {
                "id": "s01",
                "start": {"t": 0.0},
                "technique": "ID-MARK-01",
                "slots": {"image": {"asset": "painting_a"}},
                "params": {
                    "title": "I. Mở đầu",
                    "camera": [
                        {"at": {"t": 0.0}, "cx": 300, "cy": 800, "zoom": 0.675, "ease": "linear"},
                        {"at": {"t": 6.0}, "cx": 300, "cy": 800, "zoom": 0.675, "ease": "linear"},
                    ],
                },
            },
            {
                "id": "s02",
                "start": {"t": 6.0},
                "technique": "CAM-01",
                "slots": {"image": {"asset": "painting_a"}},
                "params": {
                    "camera": [
                        {"at": {"t": 6.0}, "cx": 300, "cy": 800, "zoom": 0.675, "ease": "linear"},
                        {"at": {"t": 18.0}, "cx": 300, "cy": 800, "zoom": 0.675, "ease": "linear"},
                    ]
                },
                "overlays": [
                    {"technique": "AN-01", "params": {"at": "WOMAN_FACE", "radius": 300}},
                    {"technique": "X-ANN-01", "params": {"text": "Giovanni Arnolfini", "sub": "Giovanni Arnolfini"}},
                ],
            },
            {
                "id": "s03",
                "start": {"t": 18.0},
                "technique": "CAM-05",
                "slots": {"image": {"asset": "painting_a"}},
                "params": {"region": "DOG"},
            },
            {
                "id": "s04",
                "start": {"t": 20.0},
                "technique": "X-LAY-01",
                "slots": {"image": {"asset": "ext_pic"}},
            },
            {
                "id": "s05",
                "start": {"t": 22.0},
                "technique": "CAM-05",
                "slots": {"image": {"asset": "painting_a"}},
                "params": {"region": "DOG"},
                "overlays": [
                    {"technique": "HI-01", "params": {"at": "DOG", "ry": 80}},
                    {"technique": "X-ANN-01", "params": {"text": "Philip the Good", "sub": "Duke of Burgundy"}},
                    {"technique": "X-ANN-01", "params": {"text": "Hat", "sub": "Unknown detail"}},
                ],
            },
            {
                "id": "s06",
                "start": {"t": 34.0},
                "technique": "CAM-05",
                "slots": {"image": {"asset": "painting_a"}},
                "params": {"region": "WOMAN_FACE"},
            },
        ],
    }
    _write_json(pdir / "storyboard.json", sb)

    sc = compute_metrics(
        pdir,
        audio={"loudness": {"lufs": -15.2, "lra": 3.0, "true_peak": -1.5}, "pause_vs_speech": {"diff_db": 12.0}},
        exported=True,
    )
    assert sc["schema"] == "bti.scorecard/1"
    m = _metric_map(sc)
    assert len(m) == 12

    # s02 full tall painting (12 s, cov ~0.21 < 0.6) -> 12/60 = 0.2 > 0.06
    assert m["small_painting_share"]["ok"] is False
    assert m["small_painting_share"]["shot_count"] >= 1

    # 1 ring (AN-01) + 1 spotlight (HI-01) in 60 s = 2.0/min <= 3.0
    assert m["marks_per_minute"]["ok"] is True
    assert m["marks_per_minute"]["rings"] == 1
    assert m["marks_per_minute"]["spotlights"] == 1

    # AN-01 radius=300 * 2 / 1080 = 0.556 > 0.30
    assert m["biggest_mark"]["ok"] is False
    assert m["biggest_mark"]["over_30_count"] >= 1

    # AN-01 on WOMAN_FACE (person) -> marks_on_person == 1
    assert m["marks_on_person"]["ok"] is False
    assert m["marks_on_person"]["value"] == 1

    # X-ANN-01 repeating sub ("Giovanni Arnolfini") + alias ok ("Duke of Burgundy") + thing strip ("Hat")
    assert m["name_strips"]["ok"] is False
    assert m["name_strips"]["value"]["count"] == 3
    assert m["name_strips"]["value"]["sub_repeats"] == 1
    assert m["name_strips"]["value"]["on_thing"] == 1

    # borrowed picture s04 is 2.0 s (< 3.0 s)
    assert m["borrowed_pictures"]["ok"] is False
    assert m["borrowed_pictures"]["value"]["count"] == 1
    assert m["borrowed_pictures"]["value"]["under_3s_count"] == 1

    # s03 is 2.0 s non-program shot (< 2.5 s)
    assert m["short_shots"]["ok"] is False
    assert m["short_shots"]["value"] >= 1

    # unfilled_identity: s01 covs=[0.6, 0.6] < 0.95
    assert m["unfilled_identity"]["ok"] is False
    assert m["unfilled_identity"]["value"] == 1

    # audio metrics evaluated
    assert m["loudness"]["ok"] is True
    assert m["pause_vs_speech"]["ok"] is True


def test_compute_metrics_supports_visual_json_contract(tmp_path: Path):
    pdir = tmp_path / "vis_proj"
    _make_image(pdir / "assets" / "portrait.png", 1200, 1080)
    _write_json(
        pdir / "timing.json",
        {
            "duration": 30.0,
            "words": [
                {"w": "Look", "s": 0.0, "e": 1.0},
                {"w": "at", "s": 1.0, "e": 2.0},
                {"w": "him", "s": 2.0, "e": 3.0},
            ],
        },
    )
    _write_json(
        pdir / "visual.json",
        {
            "schema": "bti.visual/1",
            "main_asset": "portrait",
            "cast": [
                {
                    "id": "SAINT",
                    "name": "Saint Eligius",
                    "kind": "person",
                    "shown_by": [{"region": "SAINT_FACE"}],
                },
                {
                    "id": "RING",
                    "name": "Gold ring",
                    "kind": "thing",
                    "strip": True,
                    "shown_by": [{"region": "GOLD_RING"}],
                },
            ],
            "moments": [
                {"id": "m1", "start": {"t": 0.0}, "about": "SAINT", "show": {"region": "BACKGROUND"}},
                {"id": "m2", "start": {"t": 15.0}, "about": "RING", "show": {"region": "GOLD_RING"}},
            ],
        },
    )
    _write_json(
        pdir / "storyboard.json",
        {
            "schema": "bti.storyboard/1",
            "title": "Visual Demo",
            "timing": "timing.json",
            "end": {"t": 30.0},
            "assets": {
                "portrait": {
                    "file": "assets/portrait.png",
                    "width": 1200,
                    "height": 1080,
                    "regions": {
                        "BACKGROUND": {"cx": 0.2, "cy": 0.2, "w": 0.2, "h": 0.2},
                        "SAINT_FACE": {"cx": 0.5, "cy": 0.4, "w": 0.2, "h": 0.2},
                        "GOLD_RING": {"cx": 0.6, "cy": 0.7, "w": 0.15, "h": 0.15},
                    },
                }
            },
            "shots": [
                {
                    "id": "v01",
                    "start": {"t": 0.0},
                    "technique": "CAM-05",
                    "slots": {"image": {"asset": "portrait"}},
                    "params": {"region": "BACKGROUND"},
                    "overlays": [{"technique": "HI-01", "params": {"at": "SAINT_FACE"}}],
                },
                {
                    "id": "v02",
                    "start": {"t": 15.0},
                    "technique": "CAM-05",
                    "slots": {"image": {"asset": "portrait"}},
                    "params": {"region": "GOLD_RING"},
                },
            ],
        },
    )

    sc = compute_metrics(pdir)
    assert sc["source"] == "visual"
    m = _metric_map(sc)
    assert m["marks_on_person"]["value"] == 1
    assert m["marks_on_person"]["ok"] is False
    assert m["subject_not_shown"]["value"] == 1
    assert m["subject_not_shown"]["ok"] is False
    assert m["loudness"]["ok"] is None
    assert m["pause_vs_speech"]["ok"] is None


def test_scorecard_ignores_old_narration_names_and_stale_moments(tmp_path: Path):
    from bti.scorecard.visual import moments_subject_not_shown
    pdir = tmp_path / "proj_stale"
    _make_image(pdir / "assets" / "main.png", 1200, 1080)
    _write_json(pdir / "picks.json", {
        "main_asset": "main",
        "assets": {"main": {"file": "assets/main.png", "width": 1200, "height": 1080,
                            "regions": {"STALE_NAME_FACE": {"x": 500, "y": 400, "rx": 50, "ry": 50},
                                        "CUR_THING": {"x": 200, "y": 200, "rx": 40, "ry": 40}}}},
        "names": [{"name": "Old Person", "line": "b0130", "where": {"region": "STALE_NAME_FACE"}, "sure": True, "words": ""}],
    })
    timing = {"duration": 10.0, "words": [{"w": "hello", "s": 0.0, "e": 1.0}],
              "beats": [{"id": "b0264", "w0": 0, "w1": 1, "start": 0.0, "end": 10.0}]}
    _write_json(pdir / "timing.json", timing)
    visual = {
        "schema": "bti.visual/1",
        "cast": [{"id": "old", "kind": "person", "name": "Old", "shown_by": [{"region": "OLD_FACE"}]}],
        "wanted": [],
        "moments": [
            {"id": "m_old", "line": "b0130", "w0": 0, "w1": 1, "about": "old", "show": {"region": "CUR_THING"}},
            {"id": "m_cur", "line": "b0264", "w0": 0, "w1": 1, "about": None, "show": {"region": "CUR_THING"}},
        ],
    }
    _write_json(pdir / "visual.json", visual)
    _write_json(pdir / "storyboard.json", {
        "schema": "bti.storyboard/1", "title": "T", "timing": "timing.json", "end": {"t": 10.0},
        "assets": {"main": {"file": "assets/main.png", "width": 1200, "height": 1080}},
        "shots": [{"id": "s1", "moment": "m_cur", "start": {"t": 0.0}, "technique": "STATIC-01",
                   "slots": {"image": {"asset": "main"}}, "params": {},
                   "overlays": [{"technique": "AN-01", "params": {"at": "STALE_NAME_FACE", "radius": 20}}]}],
    })
    assert moments_subject_not_shown(visual, timing) == []
    sc = compute_metrics(pdir)
    m = _metric_map(sc)
    assert m["marks_on_person"]["value"] == 0
    assert m["subject_not_shown"]["value"] == 0
