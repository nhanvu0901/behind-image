"""The title document: its states (none, done, stale, a person's title never stale), setting a title, writing a generation, the history, and a damaged file."""
import json

import pytest
from title_helpers import cand, good_choice, make_title_project

from bti.script import store as sstore
from bti.title import store as T
from bti.title.store import TitleError


@pytest.fixture()
def pdir(root):
    return make_title_project(root)


def generated(pdir, by="agent:mock", rev="x"):
    return T.write_generated(pdir, good_choice()["candidates"], by=by, narration_rev_=rev or T.narration_rev(pdir), written={"model": "mock", "at": "2026-11-20T10:00:00+0700"})


def test_a_project_without_the_file_is_none_and_nothing_breaks(pdir):
    assert T.state(pdir) == "none" and T.chosen_text(pdir) is None
    doc, problem = T.read(pdir)
    assert doc == T.empty_doc() and problem is None and T.revision(doc) == T.EMPTY_REV


def test_a_generation_makes_the_first_candidate_the_title_and_is_done(pdir):
    doc = generated(pdir, rev=T.narration_rev(pdir))
    assert doc["chosen"]["text"] == "The Saint Who Was Also an Advertisement" and doc["chosen"]["source"] == "agent" and doc["chosen"]["option"] == 1 and doc["chosen"]["by"] == "agent:mock"
    assert len(doc["candidates"]) == 6 and doc["narration_rev"] == T.narration_rev(pdir)
    assert T.state(pdir) == "done" and T.chosen_text(pdir) == "The Saint Who Was Also an Advertisement"
    on_disk = json.loads((pdir / "title.json").read_text(encoding="utf-8"))
    assert on_disk["schema"] == "bti.title/1" and on_disk["candidates"][1]["why"].startswith("Câu hỏi")


def test_an_agents_title_goes_stale_when_the_narration_changes_and_a_persons_never_does(pdir):
    generated(pdir, rev=T.narration_rev(pdir))
    n = sstore.load_narration(pdir)
    n.chapters[1].beats[0].text += " It is so."
    sstore.save_narration(pdir, n)
    assert T.state(pdir) == "stale" and T.chosen_text(pdir)                  # still in use: only the state says it is old
    doc, _ = T.read(pdir)
    T.set_title(pdir, base_rev=T.revision(doc), actor="human", text="The Saint Who Was Also an Advertisement")
    assert T.state(pdir) == "done"
    n = sstore.load_narration(pdir)
    n.chapters[1].beats[0].text += " Again."
    sstore.save_narration(pdir, n)
    assert T.state(pdir) == "done"                                           # a title set by a person is never stale


def test_approving_the_same_narration_again_does_not_make_the_title_stale(pdir):
    generated(pdir, rev=T.narration_rev(pdir))
    n = sstore.load_narration(pdir)
    sstore.approve(pdir, "narration", n.rev(), "someone")
    assert T.state(pdir) == "done"


def test_setting_a_title_by_text(pdir):
    doc = generated(pdir, rev=T.narration_rev(pdir))
    new = T.set_title(pdir, base_rev=T.revision(doc), actor="cli:operator", text="  The Saint Who Was Also\nan Ad".replace("\n", " "))
    assert new["chosen"]["text"] == "The Saint Who Was Also an Ad" and new["chosen"]["source"] == "person" and new["chosen"]["by"] == "cli:operator" and new["chosen"]["option"] is None
    assert [h["text"] for h in new["history"]] == ["The Saint Who Was Also an Advertisement"] and new["history"][0]["source"] == "agent"
    assert new["candidates"] == doc["candidates"] and new["narration_rev"] == doc["narration_rev"]
    assert T.read(pdir)[0] == new


def test_setting_a_title_by_option_and_a_text_equal_to_a_candidate_remembers_which(pdir):
    doc = generated(pdir, rev=T.narration_rev(pdir))
    new = T.set_title(pdir, base_rev=T.revision(doc), actor="human", option=3)
    assert new["chosen"]["text"] == "The Two Strangers in the Mirror" and new["chosen"]["option"] == 3 and new["chosen"]["source"] == "person"
    again = T.set_title(pdir, base_rev=T.revision(new), actor="human", text="Why Is a Saint Weighing a Ring?")
    assert again["chosen"]["option"] == 2


def test_setting_the_same_title_again_does_not_grow_the_history(pdir):
    first = T.set_title(pdir, base_rev=T.EMPTY_REV, actor="human", text="A Title For Now")
    assert first["history"] == []
    second = T.set_title(pdir, base_rev=T.revision(first), actor="human", text="A Title For Now")
    assert second["history"] == []
    third = T.set_title(pdir, base_rev=T.revision(second), actor="human", text="Another Title")
    assert [h["text"] for h in third["history"]] == ["A Title For Now"]


@pytest.mark.parametrize("kw, code", [({"text": ""}, "title_invalid"), ({"text": "   "}, "title_invalid"), ({"text": 5}, "title_invalid"), ({"text": "a\nb"}, "title_not_one_line"),
                                      ({"text": "x" * 61}, "title_too_long"), ({"option": 1}, "title_option_unknown"), ({"option": 0}, "title_option_unknown"),
                                      ({"option": True}, "title_option_unknown"), ({"option": "1"}, "title_option_unknown"), ({}, "title_choice_needed"),
                                      ({"text": "A", "option": 1}, "title_choice_needed")])
def test_a_refused_setting_writes_nothing(pdir, kw, code):
    with pytest.raises(TitleError) as e:
        T.set_title(pdir, base_rev=T.EMPTY_REV, actor="human", **kw)
    assert e.value.code == code and e.value.status == 422 and not (pdir / "title.json").exists()


def test_an_option_beyond_the_candidates_is_refused(pdir):
    doc = generated(pdir, rev=T.narration_rev(pdir))
    with pytest.raises(TitleError) as e:
        T.set_title(pdir, base_rev=T.revision(doc), actor="human", option=7)
    assert e.value.code == "title_option_unknown" and "there are 6" in e.value.message


def test_a_stale_revision_is_409_with_the_revision_now(pdir):
    doc = generated(pdir, rev=T.narration_rev(pdir))
    with pytest.raises(TitleError) as e:
        T.set_title(pdir, base_rev=T.EMPTY_REV, actor="human", text="Mine")
    assert e.value.status == 409 and e.value.code == "stale_revision" and e.value.extra["rev"] == T.revision(doc)
    with pytest.raises(TitleError) as e2:
        T.set_title(pdir, base_rev="", actor="human", text="Mine")
    assert e2.value.code == "invalid_request"


def test_a_new_generation_replaces_a_persons_title_and_keeps_it_in_the_history(pdir):
    first = T.set_title(pdir, base_rev=T.EMPTY_REV, actor="human", text="My Own Title")
    new = T.write_generated(pdir, good_choice()["candidates"], by="agent:mock", narration_rev_=T.narration_rev(pdir), written={})
    assert new["chosen"]["source"] == "agent" and [h["text"] for h in new["history"]] == ["My Own Title"] and new["history"][0]["source"] == "person"
    assert T.revision(new) != T.revision(first)


def test_the_history_is_bounded(pdir):
    rev = T.EMPTY_REV
    for i in range(T.KEEP + 7):
        doc = T.set_title(pdir, base_rev=rev, actor="human", text="Title %d" % i)
        rev = T.revision(doc)
    assert len(doc["history"]) == T.KEEP and doc["history"][-1]["text"] == "Title %d" % (T.KEEP + 5)


def test_a_damaged_file_counts_as_no_title_and_the_next_write_replaces_it(pdir):
    (pdir / "title.json").write_text("{ not json", encoding="utf-8")
    doc, problem = T.read(pdir)
    assert doc == T.empty_doc() and "title.json is corrupt" in problem
    assert T.state(pdir) == "none" and T.chosen_text(pdir) is None                 # never raises: the compiler and the export call these
    new = T.set_title(pdir, base_rev=T.EMPTY_REV, actor="human", text="A Fresh Start")
    assert new["chosen"]["text"] == "A Fresh Start" and T.read(pdir)[1] is None
    (pdir / "title.json").write_text(json.dumps([1, 2]), encoding="utf-8")
    assert T.state(pdir) == "none"


def test_odd_content_is_cleaned_not_trusted(pdir):
    (pdir / "title.json").write_text(json.dumps({
        "schema": "bti.title/1", "chosen": {"text": "  Odd One  ", "by": 7, "source": "robot", "option": -3},
        "candidates": [{"text": "A", "form": "slogan", "lines": "b0001", "scores": {"curiosity": True, "clear": 4}}, "x", {"text": ""}],
        "narration_rev": 5, "history": "nope"}), encoding="utf-8")
    doc, _ = T.read(pdir)
    assert doc["chosen"] == {"text": "Odd One", "by": None, "at": None, "source": "agent", "option": None}
    assert doc["candidates"] == [{"text": "A", "form": "other", "lines": [], "scores": {"clear": 4}, "why": ""}]
    assert doc["narration_rev"] is None and doc["history"] == []


def test_a_deleted_project_folder_is_not_made_again(root):
    d = make_title_project(root, "gone1")
    import shutil
    shutil.rmtree(d)
    with pytest.raises(Exception):
        T.set_title(d, base_rev=T.EMPTY_REV, actor="human", text="Too Late")
    assert not d.exists()


def test_cand_helper_is_what_the_check_wants():
    c = cand("T", "other", ["b0001"])
    assert set(c) == {"text", "form", "lines", "scores", "why"}
