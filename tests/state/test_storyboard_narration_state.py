"""State chooses a new draft for obsolete narration, but retimes voice-only drift."""
import json

from state_helpers import action, build, make_book_project


def setup_project(client, monkeypatch, old):
    from bti.draft import retime, run
    from bti.picks.context import narration_view
    make_book_project(client.root)
    monkeypatch.setattr(retime, "project_off_voice", lambda *a, **k: [])
    pid = build("storyboard_approved", client, monkeypatch)
    path = client.root / pid / "storyboard.json"
    sb = json.loads(path.read_text(encoding="utf-8"))
    beat = narration_view(client.root / pid)["beat_ids"][0]
    for shot in sb["shots"]:
        shot["beat"] = "old_beat" if old else beat
    path.write_text(json.dumps(sb), encoding="utf-8")
    monkeypatch.setattr(run, "state", lambda d: {"state": "none", "proposal": None})
    monkeypatch.setattr(retime, "project_off_voice", lambda *a, **k: [{"code": "title_off", "repair": True}])
    return client.get(f"/api/projects/{pid}/state").json()


def test_old_beats_need_a_new_draft(client, monkeypatch):
    state = setup_project(client, monkeypatch, True)
    edit = next(s for s in state["steps"] if s["step"] == "edit")
    assert edit["state"] != "done"
    assert "lời dẫn cũ" in edit["detail"]
    assert action(state, "draft.start")["needs"] == []
    assert action(state, "draft.start")["advances"]
    assert not action(state, "storyboard.retime")["advances"]
    assert not any(a["id"] == "export.start" and a["advances"] for a in state["next_actions"])


def test_current_beats_still_retime_voice_drift(client, monkeypatch):
    state = setup_project(client, monkeypatch, False)
    assert action(state, "storyboard.retime")["advances"]
    assert not action(state, "draft.start")["advances"]


def test_new_draft_can_replace_old_storyboard(client, monkeypatch):
    from bti.draft import run
    from bti.picks.context import narration_view
    setup_project(client, monkeypatch, True)
    d = client.root / "arn"
    sb_path = d / "storyboard.json"
    old = json.loads(sb_path.read_text(encoding="utf-8"))
    proposed = json.loads(json.dumps(old))
    beat = narration_view(d)["beat_ids"][0]
    for shot in proposed["shots"]:
        shot["beat"] = beat
    folder = d / "proposals"
    folder.mkdir(exist_ok=True)
    proposal = folder / "draft_new.json"
    proposal.write_text(json.dumps({"id": "draft_new", "storyboard": proposed}), encoding="utf-8")
    import os
    os.utime(proposal, ns=(sb_path.stat().st_mtime_ns + 2_000_000_000,) * 2)
    monkeypatch.setattr(run, "state", lambda d: {"state": "done", "proposal": "draft_new"})
    state = client.get("/api/projects/arn/state").json()
    apply = action(state, "proposal.apply")
    assert apply["advances"] and not action(state, "draft.start")["advances"]
    response = client.post(apply["path"], json=apply["body"])
    assert response.status_code == 200, response.text
    saved = json.loads(sb_path.read_text(encoding="utf-8"))
    assert all(s.get("beat") == beat for s in saved["shots"])
    assert saved["approvals"]["storyboard"] is None


def test_word_anchored_storyboard_uses_older_draft_narration_hash(client, monkeypatch):
    import os
    import time
    setup_project(client, monkeypatch, False)
    d = client.root / "arn"
    sb_path = d / "storyboard.json"
    sb = json.loads(sb_path.read_text(encoding="utf-8"))
    for shot in sb["shots"]:
        shot.pop("beat", None)
    sb_path.write_text(json.dumps(sb), encoding="utf-8")
    folder = d / "proposals"
    folder.mkdir(exist_ok=True)
    proposal = folder / "draft_old.json"
    proposal.write_text(json.dumps({"made_from": {"narration": "older hash"}}), encoding="utf-8")
    now = time.time()
    os.utime(proposal, (now - 30, now - 30))
    os.utime(sb_path, (now - 20, now - 20))
    state = client.get("/api/projects/arn/state").json()
    assert action(state, "draft.start")["advances"]
    assert not action(state, "storyboard.retime")["advances"]
