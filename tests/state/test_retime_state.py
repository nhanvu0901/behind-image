"""The action `storyboard.retime` of the state answer, the need `storyboard_fits_voice` on the approval and the export, and what `bti status` names next
(worker introflow). What `off_voice` finds is tested on real documents in tests/draft/test_intro_flow.py and through the routes in
tests/editor/test_retime_route.py; here it is stood in for (`bti.draft.retime.project_off_voice`), so that the answer's own rules are what is checked:
listed only while the storyboard does not fit, ready when the voice is done, advancing only when something can be moved, before the gate."""
import pytest

from bti.cli import render
from state_helpers import action, build, ids, make_book_project

PROBLEM = {"code": "title_off", "shot": "s0003", "chapter": "c02", "message": "the channel-name beat ends at 61.87 s, the voice puts its end at 70.52 s", "repair": True,
           "locked": False}
STUCK = {"code": "card_count", "shot": None, "chapter": None, "message": "the storyboard has 5 chapter card(s), the voice has 6 chapter(s) with a card: nothing was moved",
         "repair": False, "locked": False}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    import bti.draft.run as draft_run
    import bti.export.run as export_run
    import bti.voice.run as voice_run
    monkeypatch.setattr(voice_run, "start", lambda *a, **k: {"id": "fakevoicejob"})
    monkeypatch.setattr(draft_run, "start", lambda *a, **k: {"id": "fakedraftjob", "meta": {}})
    monkeypatch.setattr(export_run, "start", lambda *a, **k: {"id": "fakeexportjob"})


def at(client, monkeypatch, stage, problems, pid="arn"):
    from bti.draft import retime
    make_book_project(client.root, pid)
    monkeypatch.setattr(retime, "project_off_voice", lambda *a, **k: [])           # the project is built (and approved) as one that fits
    pid = build(stage, client, monkeypatch, pid)
    monkeypatch.setattr(retime, "project_off_voice", lambda *a, **k: list(problems))
    st = client.get(f"/api/projects/{pid}/state").json()
    return pid, st


def test_it_is_not_listed_while_the_storyboard_fits_the_voice(client, monkeypatch):
    pid, st = at(client, monkeypatch, "drafted", [])
    assert "storyboard.retime" not in ids(st)
    assert action(st, "storyboard.approve")["needs"] == [] and action(st, "storyboard.approve")["ready"]


def test_it_is_listed_ready_and_advancing_before_the_gate_while_something_does_not_fit(client, monkeypatch):
    pid, st = at(client, monkeypatch, "drafted", [PROBLEM])
    a = action(st, "storyboard.retime")
    rev = client.get(f"/api/projects/{pid}").json()["rev"]
    assert (a["step"], a["label"], a["method"], a["path"]) == ("edit", "Khớp lại với giọng đọc", "POST", f"/api/projects/{pid}/storyboard/retime")
    assert a["body"] == {"base_rev": rev, "actor": "cli:retime"} and a["ready"] and a["needs"] == [] and a["advances"]
    assert not a["gate"] and a["cost"] is None and not a["long_job"] and not a["uses_model"] and a["auto_ok"] is True        # no model, no cost: an agent may take it
    assert ids(st)[0] == "storyboard.retime"                                                       # the first advancing action: before the gate
    gate = action(st, "storyboard.approve")
    assert gate["needs"] == ["storyboard_fits_voice"] and not gate["ready"] and not gate["advances"]
    # what an automatic run takes first (the loop's own rule: the first action that is ready and advances)
    assert [x["id"] for x in st["next_actions"] if x["ready"] and x["advances"]][0] == "storyboard.retime"


def test_bti_status_names_it_as_the_next_command(client, monkeypatch):
    pid, st = at(client, monkeypatch, "drafted", [PROBLEM])
    line = render.next_line(st)
    assert line == "next: bti do %s storyboard.retime   (Khớp lại với giọng đọc)" % pid
    assert render.command_for(pid, action(st, "storyboard.retime")) == "bti do %s storyboard.retime" % pid


def test_what_retime_cannot_repair_is_listed_but_does_not_advance_and_still_blocks_the_gate(client, monkeypatch):
    pid, st = at(client, monkeypatch, "drafted", [STUCK])
    a = action(st, "storyboard.retime")
    assert a["ready"] and not a["advances"]
    assert action(st, "storyboard.approve")["needs"] == ["storyboard_fits_voice"]
    assert render.next_line(st) != "next: bti do %s storyboard.retime   (Khớp lại với giọng đọc)" % pid


def test_it_needs_the_voice_to_be_done(client, monkeypatch):
    import bti.draft.run as draft_run
    from bti.draft import retime
    make_book_project(client.root)
    pid = build("drafted", client, monkeypatch)
    monkeypatch.setattr(retime, "project_off_voice", lambda *a, **k: [PROBLEM])
    real = draft_run.readiness
    monkeypatch.setattr(draft_run, "readiness", lambda d: {**real(d), "voice": {"ok": False}, "ok": False})
    a = action(client.get(f"/api/projects/{pid}/state").json(), "storyboard.retime")
    assert a["needs"] == ["voice_done"] and not a["ready"] and not a["advances"]


def test_the_export_of_an_approved_storyboard_waits_for_the_fit_too(client, monkeypatch):
    pid, st = at(client, monkeypatch, "storyboard_approved", [PROBLEM])
    assert action(st, "export.start")["needs"] == ["storyboard_fits_voice"]
    assert action(st, "storyboard.retime")["ready"]
    pid2, st2 = at(client, monkeypatch, "storyboard_approved", [], "arn2")
    assert action(st2, "export.start")["needs"] == [] and "storyboard.retime" not in ids(st2)


def test_the_need_has_its_words_and_the_documents_name_the_action():
    from bti.auto_run import reasons
    from bti.editor import state_api
    assert "storyboard_fits_voice" in state_api.NEEDS and "storyboard_fits_voice" in reasons.NEED_VI and "Khớp lại" in reasons.NEED_VI["storyboard_fits_voice"]
    assert state_api.SPEC["storyboard.retime"].step == "edit" and state_api.SPEC["storyboard.retime"].label == "Khớp lại với giọng đọc"
    order = [s.id for s in state_api.SPECS]
    assert order.index("storyboard.retime") < order.index("storyboard.approve")                       # the catalogue order decides who comes first among the advancing calls
