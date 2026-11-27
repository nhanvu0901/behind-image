import json
from pathlib import Path
import pytest
from bti.visual.validate import validate

ROOT = Path(__file__).parent / "fixtures"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("painting", ["landscape", "still_life"])
def test_invented_painting_is_valid(painting):
    base = ROOT / painting
    visual, timing, picks = (read(base / f"{name}.json") for name in ("visual", "timing", "picks"))
    assert 8 <= len(visual["moments"]) <= 12
    assert not [i for i in validate(visual, timing, picks) if i.get("level") != "review"]


@pytest.mark.parametrize("number", range(1, 13))
def test_each_invalid_fixture_exposes_its_rule(number):
    visual = read(ROOT / "invalid" / f"V{number}.json")
    timing = read(ROOT / "landscape" / "timing.json")
    picks = read(ROOT / "landscape" / "picks.json")
    assert f"V{number}" in {issue["rule"] for issue in validate(visual, timing, picks)}


@pytest.mark.parametrize("painting", ["landscape", "still_life"])
def test_fixture_picture_is_present_and_matches_declared_size(painting):
    from PIL import Image
    base = ROOT / painting
    picks = read(base / "picks.json")
    asset = picks["assets"][picks["main_asset"]]
    with Image.open(base / asset["file"]) as image:
        assert image.size == (asset["width"], asset["height"])
