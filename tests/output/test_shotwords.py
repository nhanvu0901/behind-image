"""The Python twin of the page's sentence of a shot says what the page says: the shared cases (tests/output/fixtures/shot_cases.json, made by the JavaScript function; its own test is
shotsentence_parity.test.mjs) all give the same sentence here, and no sentence shows an id."""
import json
from pathlib import Path

import pytest

from bti.output import shotwords as W

REPO = Path(__file__).resolve().parents[2]
CASES = json.loads((Path(__file__).parent / "fixtures" / "shot_cases.json").read_text(encoding="utf-8"))
REG = json.loads((REPO / "style" / "gae" / "techniques.json").read_text(encoding="utf-8"))["techniques"]


def test_every_shared_case_gives_the_sentence_the_page_gives():
    assert len(CASES["cases"]) > 60
    bad = []
    for c in CASES["cases"]:
        got = W.shot_sentence(c["shot"], W.env_of(REG, c["assets"], c["mainKey"]))
        if got != c["expected"]:
            bad.append((c["name"], got, c["expected"]))
    assert not bad, bad[:5]


def test_every_technique_as_a_base_and_as_an_overlay_gives_the_page_sentence_and_no_id():
    env = W.env_of(REG, {}, None)
    assert len(REG) >= 85 and set(CASES["techniques"]) == {t["id"] for t in REG}
    for t in REG:
        base = W.shot_sentence({"technique": t["id"], "slots": {}, "params": {}, "overlays": []}, env)
        over = W.shot_sentence({"technique": "CAM-01", "slots": {}, "params": {}, "overlays": [{"technique": t["id"]}]}, env)
        assert (base, over) == (CASES["techniques"][t["id"]]["base"], CASES["techniques"][t["id"]]["overlay"]), t["id"]
        assert not W.looks_raw(base) and not W.looks_raw(over) and t["id"] not in base and t["id"] not in over


def test_the_program_opening_shot_reads_the_same_in_both_twins():
    """fixes3: the page's twin (shotsentence.js) now says it too: the shot with the reserved id s0000 is "Mở đầu: cả bức tranh", whatever its technique says; the shared file
    holds two such cases (`opening/CAM-01`, `opening/CAM-03`) and this side gives their sentence."""
    named = {c["name"]: c for c in CASES["cases"] if c["name"].startswith("opening/")}
    assert set(named) == {"opening/CAM-01", "opening/CAM-03"}
    for name, c in named.items():
        assert c["shot"]["id"] == "s0000" and c["expected"] == "Mở đầu: cả bức tranh · mở đầu vệt sáng · nhãn tác phẩm", name
        assert W.shot_sentence(c["shot"], W.env_of(REG, c["assets"], c["mainKey"])) == c["expected"], name
    env = W.env_of(REG, {}, None)
    assert W.shot_sentence({"id": "s0000", "technique": "ZZ-99", "overlays": []}, env) == "Mở đầu: cả bức tranh"
    assert W.shot_sentence({"id": "s0001", "technique": "CAM-01", "slots": {}}, env) == "Zoom vào bức tranh"


@pytest.mark.parametrize("shot,expected", [
    ({"technique": "ZZ-99", "overlays": []}, "Một cảnh"), ({}, "Một cảnh"), (None, "Một cảnh"),
    ({"technique": "ZZ-99", "overlays": [{"technique": "HI-01"}]}, "Một cảnh · vòng sáng"),
    ({"technique": "CAM-01", "slots": {"image": {"asset": "gone"}}}, "Zoom vào bức tranh"),
    ({"technique": "CAM-05", "slots": {}}, "Zoom kèm dịch trên bức tranh")])
def test_what_is_not_known_is_a_plain_sentence_never_an_id(shot, expected):
    assert W.shot_sentence(shot, W.env_of(REG, {}, None)) == expected
