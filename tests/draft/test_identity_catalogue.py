"""The technique catalogue the draft and edit models read (`inputs/techniques.md`, `{{TECHNIQUES_MD}}`) and the briefings: the identity techniques
are listed (so that a model can recognise an opening overlay on the first shot) but marked as the program's, never offered as a choice."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from bti import identity as ID
from bti.draft import techniques_md
from bti.draft import workspace as W
from bti.draft.inputs import load_inputs
from bti.engine import registry as R

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def bundle():
    b = R.load_bundle("gae")
    if ID.read(b.style) is None:
        pytest.skip("style/gae/style.json has no identity block yet")
    return b


def family(bundle):
    cfg = ID.read(bundle.style)
    return sorted(t["id"] for t in bundle.techniques if cfg.is_identity_technique(t["id"]))


def test_the_family_is_the_seven_techniques_of_the_block(bundle):
    cfg = ID.read(bundle.style)
    named = {t for s in cfg.styles.values() for t in (s.open, s.label_role, s.brand, s.mark) if t}
    assert set(family(bundle)) == named and len(named) == 7


def test_every_identity_technique_is_listed_and_marked_program_only(bundle):
    md = techniques_md.generate(bundle)
    for tid in family(bundle):
        line = next(l for l in md.split("\n") if l.startswith("### %s " % tid))
        assert "PROGRAM ONLY" in line and "never by you" in line, line
    other = [l for l in md.split("\n") if l.startswith("### ") and not any(l.startswith("### %s " % t) for t in family(bundle))]
    assert other and not [l for l in other if "PROGRAM ONLY" in l]


def test_they_are_not_offered_in_the_index_by_intent(bundle):
    md = techniques_md.generate(bundle)
    index = md[md.index("## Choosing by intent"):md.index("## The channel identity")]
    for tid in family(bundle):
        assert tid not in index
    assert "CAM-01" in index and "X-CARD-01" in index                       # the old cards and everything else are still offered


def test_the_identity_section_is_generated_from_the_block(bundle):
    cfg = ID.read(bundle.style)
    md = techniques_md.generate(bundle)
    sec = md[md.index("## The channel identity"):md.index("## The techniques")]
    for sid, sd in cfg.styles.items():
        assert "`%s`" % sid in sec
        for t in (sd.open, sd.label_role, sd.brand, sd.mark):
            if t:
                assert t in sec
    assert "never" in sec and "PROGRAM ONLY" in sec and "overlays" in sec


def test_a_style_without_an_identity_block_gets_no_such_marks(bundle):
    b = R.StyleBundle("gae")
    b.style = {k: v for k, v in b.style.items() if k != "identity"}
    md = techniques_md.generate(b)
    assert "PROGRAM ONLY" not in md and "## The channel identity" not in md
    assert "### ID-MARK-01 " in md                                          # still a technique of the registry


def test_the_workspace_file_and_the_briefings_say_the_same(bundle, proj, tmp_path):
    ws = W.build(load_inputs(proj), root=tmp_path / "ws")
    md = (ws.root / "inputs" / "techniques.md").read_text(encoding="utf-8")
    assert md.count("PROGRAM ONLY") >= 7 and "## The channel identity" in md
    task = (REPO / "skills" / "storyboard_draft" / "TASK.template.md").read_text(encoding="utf-8")
    fast = (REPO / "skills" / "storyboard_edit" / "FAST.template.md").read_text(encoding="utf-8")
    for text in (task, fast):
        assert not re.search(r"\b71 techniques\b|The 71\b", text)
        assert "never" in text and "Kiểu mở đầu và mốc chương" in text
    assert "ID-OPEN-*" in task and "ID-MARK-*" in task and "ID-BRAND-*" in task and "ID-LABEL-*" in task
    assert "`ID-*`" in fast and "the program writes them" in fast               # the fast briefing names the family; the catalogue it is given leaves every ID-* technique out
    assert "`cannot`" in fast                                                  # the model only answers cannot: the owner chooses the style in the box (the route is the page's)
    rendered = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "{{" not in rendered and "PROGRAM ONLY" in rendered
