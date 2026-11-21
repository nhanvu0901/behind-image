"""`bti status` names `bti do <project> storyboard.retime` as the next command while the storyboard does not fit the voice, and `bti do` calls it with the
body the state gives (worker introflow). What `off_voice` finds is stood in for; the real rules are tested in tests/draft and tests/editor."""
import pytest

from state_helpers import PID, action, build, make_book_project

P = f"/api/projects/{PID}"
PROBLEM = {"code": "card_off", "shot": "s0005", "chapter": "c02", "message": "the chapter card starts at 61.87 s, the voice puts it at 70.52 s", "repair": True, "locked": False}


@pytest.fixture()
def drafted(client, monkeypatch):
    from bti.draft import retime
    make_book_project(client.root)
    monkeypatch.setattr(retime, "project_off_voice", lambda *a, **k: [])
    build("drafted", client, monkeypatch)
    monkeypatch.setattr(retime, "project_off_voice", lambda *a, **k: [PROBLEM])
    return client


def test_status_names_retime_as_the_next_command_and_lists_it_before_the_gate(bti, drafted):
    r = bti("status", "arn")
    lines = r.out.splitlines()
    assert r.code == 0 and lines[-1] == "next: bti do arn storyboard.retime   (Khớp lại với giọng đọc)"
    ids = [l.split()[0] for l in lines[lines.index("can do now:") + 1:] if l.startswith("  ") and l.split()]
    assert ids.index("storyboard.retime") < ids.index("storyboard.approve")
    approve = next(l for l in lines if l.strip().startswith("storyboard.approve"))
    assert approve.endswith("needs: storyboard_fits_voice") and "advances" not in approve                    # the gate waits while the storyboard is off the voice


def test_do_calls_it_with_the_body_the_state_gives(bti, drafted):
    st = drafted.get(P + "/state").json()
    a = action(st, "storyboard.retime")
    assert a["body"]["base_rev"] == drafted.get(P).json()["rev"] and a["body"]["actor"] == "cli:retime"
    r = bti("do", "arn", "storyboard.retime", "--actor", "cli:tester")
    sent = bti.transport.log[-1]
    assert sent[:2] == ("POST", P + "/storyboard/retime") and sent[2]["actor"] == "cli:tester" and sent[2]["base_rev"] == a["body"]["base_rev"]
    assert r.code == 0 and r.out.splitlines()[0] == "ok: storyboard.retime" and '"changed":[]' in r.out        # the demo storyboard has nothing to move: no revision was written


def test_when_it_fits_the_command_says_it_is_not_listed(bti, client, monkeypatch):
    from bti.draft import retime
    make_book_project(client.root)
    monkeypatch.setattr(retime, "project_off_voice", lambda *a, **k: [])
    build("drafted", client, monkeypatch)
    r = bti("do", "arn", "storyboard.retime")
    assert r.code == 4 and "storyboard.retime" in r.err and "storyboard.retime" not in bti("status", "arn").out.split("can do now:")[1]
