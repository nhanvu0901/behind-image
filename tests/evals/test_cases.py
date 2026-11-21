"""The case files of the bench: the format, every case in `evals/cases`, and that the criteria of a case can be checked on what the driver of its step gives."""
import json
from pathlib import Path

import pytest

from bti.evals import cases, criteria, samples

REPO = Path(__file__).resolve().parents[2]
# what the driver of each step hands to its criteria (bti/evals/driver.py)
OUTPUTS = {"outline": {"outline", "issues", "brief", "approved", "job", "error"}, "narration": {"narration", "outline", "brief", "issues", "stats", "job", "error"},
           "draft": {"before", "storyboard", "timing", "issues", "picks", "proposal", "job", "error"},
           "edit_storyboard": {"before", "after", "storyboard", "timing", "issues", "scope", "answer", "job", "error"},
           "edit_picks": {"before", "after", "picks", "issues", "beat_ids", "scope", "answer", "job", "error"}, "picks_agent": {"picks", "issues", "beat_ids", "job", "error"}}
WANT = {"outline": 10, "narration": 11, "draft": 10, "edit_storyboard": 3, "edit_picks": 3, "picks_agent": 3}


def good_case(**over):
    c = {"schema": "bti.eval.case/1", "name": "outline-x", "step": "outline", "title": "A title", "why": "A reason", "sample": {"project": "arnolfini-from-books", "start": "book"},
         "request": {}, "criteria": [{"id": "n", "kind": "outline.chapters_between", "min": 1, "max": 9}]}
    c.update(over)
    return c


def test_there_are_about_ten_cases_for_the_first_three_steps_and_three_for_the_others():
    got = {}
    for c in cases.load_cases():
        got[c.step] = got.get(c.step, 0) + 1
    assert got == WANT


def test_every_case_file_is_valid_and_named_by_its_file():
    seen = set()
    for f in sorted((REPO / "evals" / "cases").glob("*/*.json")):
        c = cases.load_case(f)
        assert c.name == f.stem and c.step == f.parent.name and c.name not in seen
        seen.add(c.name)
        assert c.title.strip() and c.why.strip() and len(c.criteria) >= 1
        assert c.sample["start"] in samples.STARTS, c.name
        assert (REPO / "projects" / c.sample["project"]).is_dir(), "%s: the sample %s is not in projects/" % (c.name, c.sample["project"])
        assert len({x["id"] for x in c.criteria}) == len(c.criteria)


def test_the_criteria_of_every_case_can_be_checked_on_what_its_driver_gives():
    for c in cases.load_cases():
        for spec in c.criteria:
            need = set(criteria.REGISTRY[spec["kind"]].needs)
            assert need <= OUTPUTS[c.step], "%s: %s needs %s, the %s driver gives %s" % (c.name, spec["kind"], sorted(need), c.step, sorted(OUTPUTS[c.step]))
            assert spec["kind"].split(".")[0] in {"outline": ("outline",), "narration": ("narration",), "draft": ("draft",), "edit_storyboard": ("edit",),
                                                  "edit_picks": ("edit", "picks"), "picks_agent": ("picks",)}[c.step], (c.name, spec["kind"])


def test_a_case_is_refused_with_a_sentence_that_names_the_file(tmp_path):
    def attempt(doc, name="outline-x"):
        d = tmp_path / "outline"
        d.mkdir(exist_ok=True)
        f = d / (name + ".json")
        f.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(cases.CaseError) as e:
            cases.load_case(f)
        return str(e.value)
    assert "outline-x.json" in attempt(good_case(schema="x"))
    assert "name must be" in attempt(good_case(name="Outline X"), "Outline X")
    assert "step must be one of" in attempt(good_case(step="lunch"))
    assert "sample must be" in attempt(good_case(sample={"project": "p"}))
    assert "criteria must be a list" in attempt(good_case(criteria=[]))
    assert "unknown kind" in attempt(good_case(criteria=[{"id": "a", "kind": "outline.nope"}]))
    assert "unique" in attempt(good_case(criteria=[{"id": "a", "kind": "outline.no_error_issues"}, {"id": "a", "kind": "outline.no_error_issues"}]))
    assert "unknown keys: extra" in attempt(good_case(extra=1))
    assert "not a key of a outline request" in attempt(good_case(request={"instruction": "x"}))
    assert "request.instruction" in attempt(good_case(name="edit-x", step="edit_storyboard", request={"scope": {"all": True}}, criteria=[{"id": "a", "kind": "edit.no_error_issues"}]), "edit-x")
    assert "request.scope must be exactly one of" in attempt(good_case(name="edit-y", step="edit_storyboard", request={"instruction": "x", "scope": {"all": True, "chapter": "c1"}},
                                                                      criteria=[{"id": "a", "kind": "edit.no_error_issues"}]), "edit-y")
    assert "must be the file name" in attempt(good_case(name="other-name"))
    bad = tmp_path / "outline" / "broken.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(cases.CaseError, match="broken.json: cannot be read as JSON"):
        cases.load_case(bad)


def test_load_cases_filters_and_refuses_an_unknown_name(tmp_path):
    assert [c.step for c in cases.load_cases("picks_agent")] == ["picks_agent"] * 3
    one = cases.load_cases("outline", ["outline-chapter-count"])
    assert [c.name for c in one] == ["outline-chapter-count"]
    with pytest.raises(cases.CaseError, match="no such case in step outline: nope"):
        cases.load_cases("outline", ["nope"])
    wrong = tmp_path / "draft"
    wrong.mkdir()
    (wrong / "outline-x.json").write_text(json.dumps(good_case()), encoding="utf-8")
    with pytest.raises(cases.CaseError, match="sits in the folder draft"):
        cases.load_cases(root=tmp_path)


def test_the_cases_the_brief_names_are_there():
    names = {c.name for c in cases.load_cases()}
    assert {"outline-chapter-count", "outline-every-chapter-cites-the-dossier", "narration-length-within-target", "narration-no-long-lines", "draft-pace-seven-seconds",
            "draft-technique-variety", "draft-context-lines-leave-the-main-painting", "edit-zoom-slower", "edit-asks-for-a-picture-the-project-lacks"} <= names
