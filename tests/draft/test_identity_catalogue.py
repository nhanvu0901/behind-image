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


def test_the_family_is_the_seven_techniques_of_the_block_and_the_earlier_form_of_the_beat(bundle):
    cfg = ID.read(bundle.style)
    named = {t for s in cfg.styles.values() for t in (s.open, s.label_role, s.brand, s.mark) if t}
    assert len(named) == 7
    earlier = {t for s in cfg.styles.values() for ids in s.earlier.values() for t in ids}       # ID-BRAND-01 & ID-BRAND-03: earlier forms of raking before ID-BRAND-04
    assert earlier == {"ID-BRAND-01", "ID-BRAND-03"} and set(family(bundle)) == named | earlier


def test_every_identity_technique_is_listed_and_marked_program_only(bundle):
    """Catalogue pass: they are in the short section `Written by the program`, after the offered techniques, each marked PROGRAM ONLY."""
    md = techniques_md.generate(bundle)
    body, program = md.split("## Written by the program")
    for tid in family(bundle):
        line = next(l for l in program.split("\n") if l.startswith("### %s " % tid))
        assert "PROGRAM ONLY" in line and "never by you" in line, line
        assert "### %s " % tid not in body
    other = [l for l in body.split("\n") if l.startswith("### ")]
    assert other and not [l for l in other if "PROGRAM ONLY" in l], "an offered technique is never marked as the program's"


def test_they_are_not_offered_in_the_index_by_kind(bundle):
    md = techniques_md.generate(bundle)
    index = md[md.index("## Choosing by the kind of line"):md.index("## The channel identity")]
    for tid in family(bundle) + ["X-CARD-01", "X-CARD-02", "TXT-01"]:
        assert tid not in index, tid                                        # the old cards are the program's too
    assert "CAM-01" in index and "MAP-01" in index


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
    assert "## The channel identity" not in md
    assert "PROGRAM ONLY: the channel identity" not in md                   # no identity block: nothing is the identity's
    assert "### ID-MARK-01 " in md                                          # still a technique of the registry, listed among the ones the program writes


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
