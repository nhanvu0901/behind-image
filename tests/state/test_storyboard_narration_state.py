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


def _setup_visual_project(client, monkeypatch):
    from pathlib import Path
    from shutil import copyfile
    from bti.scorecard import build as scorecard_build

    orig_make = scorecard_build.make_for_project
    monkeypatch.setattr(scorecard_build, "make_for_project", lambda p, **kw: orig_make(p, **{**kw, "sheets": False}))

    make_book_project(client.root)
    pid = build("voiced", client, monkeypatch)
    d = client.root / pid
    st = client.get(f"/api/projects/{pid}/state").json()
    r = client.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]})
    assert r.status_code == 200, r.text

    fixture = Path(__file__).resolve().parents[1] / "visual" / "fixtures" / "landscape"
    (d / "media").mkdir(exist_ok=True)
    for name in ("visual.json", "timing.json", "picks.json"):
        copyfile(fixture / name, d / name)
    copyfile(fixture / "media" / "painting.png", d / "media" / "painting.png")
    (d / "audio").mkdir(exist_ok=True)
    (d / "audio" / "mix.m4a").write_bytes(b"x" * 64)

    picks = client.get(f"/api/projects/{pid}/picks").json()
    r = client.post(f"/api/projects/{pid}/picks/approve", json={"rev": picks["rev"]})
    assert r.status_code == 200, r.text
    assert (d / "storyboard.json").is_file()
    return d, pid


def test_composed_visual_sequence_offers_approve_and_export(client, monkeypatch):
    import os
    import time
    from bti.compose.api import compose_project
    from bti.draft import review as draft_review
    from bti.editor.common import compute_rev
    from bti.music import library
    from bti.picks import doc as pdoc
    from bti.visual import store as vstore

    d, pid = _setup_visual_project(client, monkeypatch)
    # Legacy draft proposal from an earlier narration must never taint a composed storyboard.
    proposals = d / "proposals"
    proposals.mkdir(exist_ok=True)
    legacy_prop = proposals / "draft_20261126-182138.json"
    legacy_prop.write_text(json.dumps({"made_from": {"narration": "older hash"}}), encoding="utf-8")

    compose_act = action(client.get(f"/api/projects/{pid}/state").json(), "storyboard.compose")
    r = client.post(compose_act["path"], json=compose_act["body"])
    assert r.status_code == 200, r.text

    # Simulate a viewer review that edits visual.json & picks.json, recomposes, and saves its report.
    visual = vstore.load(d)
    base_rev = vstore.revision(visual)
    visual["moments"][0]["why"] = "Cận cảnh ngôi làng bên sông."
    vstore.save(d, visual, base_rev=base_rev, actor="agent:review", compose=False)
    pd = pdoc.load(d)
    pd["assets"]["A"]["title"] = "Landscape"
    pdoc.save(d, pd)
    compose_project(d)

    sb = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
    sb_rev = compute_rev(sb)
    draft_review.save_report(d, {
        "revision": sb_rev,
        "inputs": draft_review._input_signature(d),
        "rounds": 1,
        "warnings": [],
        "history": [{}],
    })
    now = time.time()
    os.utime(legacy_prop, (now - 30, now - 30))
    os.utime(d / "storyboard.json", (now - 20, now - 20))

    # Approve picks again after review, then choose music.
    picks = client.get(f"/api/projects/{pid}/picks").json()
    r = client.post(f"/api/projects/{pid}/picks/approve", json={"rev": picks["rev"]})
    assert r.status_code == 200, r.text

    monkeypatch.setattr(library, "index", lambda: {"rec1": {"duration": 120.0, "title": "Air", "composer": "Bach"}})
    music_rev = client.get(f"/api/projects/{pid}/music").json()["rev"]
    r = client.put(f"/api/projects/{pid}/music", json={
        "base_rev": music_rev,
        "music": {"cues": [{"recording": "rec1", "start": {"t": 0.0}, "end": {"t": 5.0},
                            "offset": 0.0, "level": "normal", "fade_in": 0.5, "fade_out": 0.5,
                            "role": "bed", "why": "Quiet opening"}]},
    })
    assert r.status_code == 200, r.text

    st = client.get(f"/api/projects/{pid}/state").json()
    edit = next(s for s in st["steps"] if s["step"] == "edit")
    assert "lời dẫn cũ" not in edit["detail"]
    approve = action(st, "storyboard.approve")
    assert approve["ready"] and approve["advances"]
    assert not action(st, "storyboard.compose")["advances"]
    assert not action(st, "storyboard.review")["advances"]

    r = client.post(approve["path"], json=approve["body"])
    assert r.status_code == 200, r.text
    st2 = client.get(f"/api/projects/{pid}/state").json()
    export_act = action(st2, "export.start")
    assert export_act["ready"] and export_act["advances"]


def test_composed_storyboard_with_old_timing_hash_is_reported_old(client, monkeypatch):
    d, pid = _setup_visual_project(client, monkeypatch)

    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    timing["words"][0]["e"] = round(float(timing["words"][0]["e"]) + 0.01, 3)
    (d / "timing.json").write_text(json.dumps(timing), encoding="utf-8")

    st = client.get(f"/api/projects/{pid}/state").json()
    edit = next(s for s in st["steps"] if s["step"] == "edit")
    assert edit["state"] != "done"
    assert "lời dẫn cũ" in edit["detail"]
    assert not any(a["id"] == "storyboard.approve" for a in st["next_actions"])
    assert not any(a["id"] == "export.start" and a["advances"] for a in st["next_actions"])
    assert next(s for s in st["steps"] if s["step"] == "export")["blocked_by"] == "edit"
    compose = action(st, "storyboard.compose")
    assert compose["ready"] and compose["advances"]


def test_composed_storyboard_with_changed_visual_is_not_old_narration(client, monkeypatch):
    from bti.visual import store as vstore

    d, pid = _setup_visual_project(client, monkeypatch)
    proposals = d / "proposals"
    proposals.mkdir(exist_ok=True)
    (proposals / "draft_old.json").write_text(json.dumps({"made_from": {"narration": "older hash"}}), encoding="utf-8")

    visual = vstore.load(d)
    base_rev = vstore.revision(visual)
    visual["moments"][0]["why"] = "Đổi mô tả để cần dựng lại."
    vstore.save(d, visual, base_rev=base_rev, actor="cli:test", compose=False)

    st = client.get(f"/api/projects/{pid}/state").json()
    edit = next(s for s in st["steps"] if s["step"] == "edit")
    assert "lời dẫn cũ" not in edit["detail"]
    compose = action(st, "storyboard.compose")
    assert compose["ready"] and compose["advances"]
    approve = action(st, "storyboard.approve")
    assert not approve["ready"] and "visual_composed" in approve["needs"]


def test_picks_reapproval_after_review_recomposes_when_script_or_timing_changed(client, monkeypatch):
    from bti.draft import review as draft_review
    from bti.draft.inputs import canon_hash
    from bti.editor.common import compute_rev
    from bti.picks import doc as pdoc
    from bti.visual import store as vstore

    d, pid = _setup_visual_project(client, monkeypatch)

    sb = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
    draft_review.save_report(d, {
        "revision": compute_rev(sb),
        "inputs": draft_review._input_signature(d),
        "rounds": 1,
        "warnings": [],
        "history": [{}],
    })
    # Drop picks approval after review, then change visual.json while unapproved.
    pd = pdoc.load(d)
    pd["assets"]["A"]["title"] = "Landscape"
    pdoc.save(d, pd)

    visual = vstore.load(d)
    base_rev = vstore.revision(visual)
    visual["moments"][0]["why"] = "Sửa sau khi xem lại."
    vstore.save(d, visual, base_rev=base_rev, actor="agent:review", compose=True)
    sb_before = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
    assert sb_before["made_from"]["visual"] != canon_hash(visual)

    picks = client.get(f"/api/projects/{pid}/picks").json()
    r = client.post(f"/api/projects/{pid}/picks/approve", json={"rev": picks["rev"]})
    assert r.status_code == 200, r.text
    sb_after_visual = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
    assert sb_after_visual["made_from"]["visual"] == canon_hash(visual)
    st = client.get(f"/api/projects/{pid}/state").json()
    assert action(st, "storyboard.approve")["ready"] and action(st, "storyboard.approve")["advances"]

    # Also recompose on picks re-approval when timing changed since the storyboard.
    pd = pdoc.load(d)
    pd["assets"]["A"]["title"] = "Landscape 2"
    pdoc.save(d, pd)
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    timing["words"][0]["e"] = round(float(timing["words"][0]["e"]) + 0.01, 3)
    (d / "timing.json").write_text(json.dumps(timing), encoding="utf-8")

    picks = client.get(f"/api/projects/{pid}/picks").json()
    r = client.post(f"/api/projects/{pid}/picks/approve", json={"rev": picks["rev"]})
    assert r.status_code == 200, r.text
    sb_after_timing = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
    assert sb_after_timing["made_from"]["timing"] == canon_hash(timing)
    st2 = client.get(f"/api/projects/{pid}/state").json()
    assert action(st2, "storyboard.approve")["ready"] and action(st2, "storyboard.approve")["advances"]
