"""Who may approve a gate (worker c5cli): `auto.json`, the actor of the four approval routes, who is recorded, and what the state answer marks.

The rule (bti/auto.py, bti/editor/auto_api.py): the page approves as `human` (the default: it sends no actor); an actor that is not `human`
(`agent:...`, `cli:...`) approves a gate only when the project's `auto` is enabled and allows that gate, else 403 `gate_needs_human` and
nothing is written; `paid` spending is never allowed to an agent."""
import json

import pytest

from bti import auto as A
from state_helpers import DEMO_SRC, PID, action, build, make_book_project, make_picks, put_storyboard, wait_job

P = f"/api/projects/{PID}"
GATES = ("outline", "narration", "picks", "storyboard")
BOT = "cli:tester"


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    """Nothing heavy starts (the same stand-ins as tests/state/test_state.py)."""
    import bti.draft.run as draft_run
    import bti.editor.jobs as jobs_mod
    import bti.export.run as export_run
    import bti.voice.run as voice_run
    from bti.picks import service
    monkeypatch.setattr(voice_run, "start", lambda *a, **k: {"id": "fakevoicejob"})
    monkeypatch.setattr(draft_run, "start", lambda *a, **k: {"id": "fakedraftjob", "meta": {}})
    monkeypatch.setattr(export_run, "start", lambda *a, **k: {"id": "fakeexportjob"})
    monkeypatch.setattr(jobs_mod, "render_preview", lambda *a, **k: "/api/projects/x/files/cache/previews/p.mp4")
    monkeypatch.setattr(service, "search", lambda *a, **k: {"items": [], "errors": []})


def set_auto(c, **change):
    rev = c.get(P + "/auto").json()["rev"]
    r = c.put(P + "/auto", json={"base_rev": rev, **change})
    assert r.status_code == 200, r.text
    return r.json()


class Stage:
    """A book project brought, step by step, to just before a gate, with the pieces the routes need to approve it."""

    def __init__(self, c, monkeypatch):
        from bti.draft import run as draft_run
        from bti.library import projects as projects_mod
        self.c = c
        make_book_project(c.root)
        monkeypatch.setattr(projects_mod, "stage_states", self._states(projects_mod.stage_states))
        monkeypatch.setattr(draft_run, "readiness", lambda d: {"voice": {"ok": True}, "picks": {"ok": True}, "ok": True})

    @staticmethod
    def _states(real):
        def stood_in(d):
            out = real(d)
            out["voice"] = {"state": "done", "detail": "Giọng đọc đã xong."}
            return out
        return stood_in

    def outline(self):
        r = self.c.post(P + "/outline/generate", json={})
        assert r.status_code == 200, r.text
        assert wait_job(self.c, r.json()["job_id"])["state"] == "done"
        return self.c.get(P + "/outline").json()["rev"]

    def narration(self):
        rev = self.outline()
        assert self.c.post(P + "/outline/approve", json={"rev": rev}).status_code == 200
        r = self.c.post(P + "/narration/generate", json={})
        assert r.status_code == 200, r.text
        assert wait_job(self.c, r.json()["job_id"])["state"] == "done"
        return self.c.get(P + "/narration").json()["rev"]

    def picks(self):
        from bti.picks import doc
        from picks_helpers import png_bytes
        rev = self.narration()
        assert self.c.post(P + "/narration/approve", json={"rev": rev}).status_code == 200
        d = self.c.root / PID
        (d / "media").mkdir(exist_ok=True)
        (d / "media" / "main.png").write_bytes(png_bytes(120, 160))
        pd = {"schema": doc.SCHEMA, "main_asset": "MAIN", "beats": {}, "approval": {"approved": False},
              "assets": {"MAIN": {"file": "media/main.png", "kind": "image", "title": "The Arnolfini Portrait", "artist": "Jan Van Eyck",
                                  "year": "1434", "width": 120, "height": 160, "regions": {},
                                  "credit": {"source": "commons", "source_url": "u", "author": "x", "licence": "PD", "flag": None}}}}
        doc.save(d, pd)
        return doc.revision(doc.load(d))

    def storyboard(self):
        rev = self.picks()
        assert self.c.post(P + "/picks/approve", json={"rev": rev}).status_code == 200
        put_storyboard(self.c, PID)
        return self.c.get(P).json()["rev"]

    def at(self, gate):
        return getattr(self, gate)()


ROUTE = {"outline": "/outline/approve", "narration": "/narration/approve", "picks": "/picks/approve", "storyboard": "/approve"}


def approve(c, gate, rev, **extra):
    return c.post(P + ROUTE[gate], json={"rev": rev, **extra})


def recorded(c, gate):
    """The `by` stored where the approval is stored."""
    d = c.root / PID
    if gate == "storyboard":
        return json.loads((d / "storyboard.json").read_text(encoding="utf-8"))["approvals"]["storyboard"].get("by")
    f = d / ("picks.json" if gate == "picks" else f"script/{gate}.json")
    return json.loads(f.read_text(encoding="utf-8"))["approval"].get("by")


def approved(c, gate):
    d = c.root / PID
    if gate == "storyboard":
        return bool(json.loads((d / "storyboard.json").read_text(encoding="utf-8"))["approvals"].get("storyboard"))
    f = d / ("picks.json" if gate == "picks" else f"script/{gate}.json")
    return json.loads(f.read_text(encoding="utf-8"))["approval"].get("approved") is True


# ---------------------------------------------------------------------------------------------------------------- the document
def test_the_defaults_enable_nothing(client):
    make_book_project(client.root)
    j = client.get(P + "/auto").json()
    assert j["schema"] == "bti.auto/1" and j["enabled"] is False
    assert j["gates"] == {g: True for g in GATES} and j["spend"] == {"model": True, "machine_time": True, "paid": False}
    assert j["warnings"] == [] and isinstance(j["rev"], str) and j["rev"]
    assert not (client.root / PID / "auto.json").exists()                # reading writes nothing


def test_put_changes_only_what_it_names_and_checks_the_revision(client):
    make_book_project(client.root)
    a = set_auto(client, enabled=True, gates={"picks": False})
    assert a["enabled"] is True and a["gates"] == {"outline": True, "narration": True, "picks": False, "storyboard": True}
    assert a["spend"] == {"model": True, "machine_time": True, "paid": False}
    saved = json.loads((client.root / PID / "auto.json").read_text(encoding="utf-8"))
    assert saved["schema"] == "bti.auto/1" and saved["enabled"] is True and saved["gates"]["picks"] is False
    b = set_auto(client, spend={"machine_time": False})
    assert b["enabled"] is True and b["gates"]["picks"] is False and b["spend"]["machine_time"] is False and b["rev"] != a["rev"]
    r = client.put(P + "/auto", json={"base_rev": a["rev"], "enabled": False})              # an old revision
    assert r.status_code == 409 and r.json()["code"] == "stale" and r.json()["current_rev"] == b["rev"] and r.json()["fix"]
    assert client.get(P + "/auto").json()["enabled"] is True                                    # nothing was written


@pytest.mark.parametrize("body, path", [
    ({"enabled": "yes"}, "enabled"), ({"gates": {"lunch": True}}, "gates.lunch"), ({"gates": {"outline": 1}}, "gates.outline"),
    ({"gates": [True]}, "gates"), ({"spend": {"paid": True}}, "spend.paid"), ({"spend": {"gold": False}}, "spend.gold"),
    ({"colour": "red"}, "colour"), ({"actor": "robot"}, "actor"),
])
def test_a_wrong_change_is_refused_with_the_field(client, body, path):
    make_book_project(client.root)
    rev = client.get(P + "/auto").json()["rev"]
    r = client.put(P + "/auto", json={"base_rev": rev, **body})
    assert r.status_code == 422, r.text
    j = r.json()
    assert j["code"] == "invalid_field" and j["retry"] == "after_fix" and path in [f["path"] for f in j["fields"]], j
    assert not (client.root / PID / "auto.json").exists()


def test_put_needs_base_rev_and_a_known_project(client):
    make_book_project(client.root)
    r = client.put(P + "/auto", json={"enabled": True})
    assert r.status_code == 422 and r.json()["fields"][0]["path"] == "base_rev"
    assert client.get("/api/projects/nope/auto").status_code == 404
    assert client.put("/api/projects/nope/auto", json={"base_rev": "x"}).status_code == 404


def test_only_the_owner_changes_automatic_running(client):
    """An agent that asks to switch automatic running on for itself is refused: the switch is the owner's."""
    make_book_project(client.root)
    rev = client.get(P + "/auto").json()["rev"]
    for actor in (BOT, "agent:gemini-3.8-flash"):
        r = client.put(P + "/auto", json={"base_rev": rev, "enabled": True, "actor": actor})
        assert r.status_code == 403 and r.json()["code"] == "auto_needs_human" and r.json()["fix"], r.text
    assert client.get(P + "/auto").json()["enabled"] is False
    assert client.put(P + "/auto", json={"base_rev": rev, "enabled": True, "actor": "human"}).status_code == 200


def test_a_damaged_file_counts_as_the_defaults_and_is_set_aside_by_the_next_change(client):
    make_book_project(client.root)
    (client.root / PID / "auto.json").write_text("{not json", encoding="utf-8")
    j = client.get(P + "/auto").json()
    assert j["enabled"] is False and [w["code"] for w in j["warnings"]] == ["auto_file_unreadable"]
    set_auto(client, enabled=True)
    assert any(f.name.startswith("auto.json.corrupt-") for f in (client.root / PID).iterdir())
    assert client.get(P + "/auto").json()["warnings"] == []


def test_a_hand_edited_file_never_allows_paid(client):
    make_book_project(client.root)
    (client.root / PID / "auto.json").write_text(json.dumps({"schema": "bti.auto/1", "enabled": True, "spend": {"paid": True, "model": "x"}}), encoding="utf-8")
    j = client.get(P + "/auto").json()
    assert j["spend"] == {"model": True, "machine_time": True, "paid": False} and j["enabled"] is True
    assert [w["code"] for w in j["warnings"]] == ["paid_ignored"]


def test_the_rule_of_the_module():
    d = A.normalize({"enabled": True, "gates": {"picks": False}})
    assert [A.gate_allowed(d, g) for g in GATES] == [True, True, False, True]
    assert not any(A.gate_allowed(A.default_doc(), g) for g in GATES)
    assert A.gate_allowed(d, "nope") is False
    assert A.spend_allowed(d, "model") and A.spend_allowed(d, "machine_time") and not A.spend_allowed(d, "paid") and not A.spend_allowed(d, "gold")
    assert A.gate_refusal(A.default_doc(), "outline") == "auto_off" and A.gate_refusal(d, "picks") == "gate_not_allowed" and A.gate_refusal(d, "outline") is None


# ------------------------------------------------------------------------------------------------------------ the approval routes
@pytest.mark.parametrize("gate", GATES)
def test_the_page_approves_unchanged_and_the_approval_says_human(client, monkeypatch, gate):
    rev = Stage(client, monkeypatch).at(gate)
    r = approve(client, gate, rev)                                   # the page sends no actor
    assert r.status_code == 200, r.text
    assert approved(client, gate) and recorded(client, gate) == "human"
    assert not (client.root / PID / "auto.json").exists()           # the page never needed the document


@pytest.mark.parametrize("gate", GATES)
@pytest.mark.parametrize("actor", [BOT, "agent:gemini-3.8-flash-high"])
def test_an_agent_is_refused_by_default_and_nothing_is_written(client, monkeypatch, gate, actor):
    rev = Stage(client, monkeypatch).at(gate)
    r = approve(client, gate, rev, actor=actor)
    assert r.status_code == 403, r.text
    j = r.json()
    assert j["code"] == "gate_needs_human" and j["gate"] == gate and j["actor"] == actor and j["reason"] == "auto_off" and j["retry"] == "after_fix"
    assert "owner" in j["fix"] and "page" in j["fix"] and "automatic running" in j["fix"] and "/api/projects/%s/auto" % PID in j["fix"]
    assert j["auto"]["enabled"] is False
    assert not approved(client, gate)
    assert approve(client, gate, rev).status_code == 200            # the owner can still approve it on the page


@pytest.mark.parametrize("gate", GATES)
def test_an_agent_is_allowed_after_the_owner_turned_it_on_and_it_is_recorded(client, monkeypatch, gate):
    rev = Stage(client, monkeypatch).at(gate)
    set_auto(client, enabled=True)
    r = approve(client, gate, rev, actor=BOT)
    assert r.status_code == 200, r.text
    assert approved(client, gate) and recorded(client, gate) == BOT


@pytest.mark.parametrize("gate", GATES)
def test_the_owner_allows_the_gates_one_by_one(client, monkeypatch, gate):
    rev = Stage(client, monkeypatch).at(gate)
    set_auto(client, enabled=True, gates={gate: False})
    r = approve(client, gate, rev, actor=BOT)
    assert r.status_code == 403 and r.json()["reason"] == "gate_not_allowed" and r.json()["code"] == "gate_needs_human"
    assert not approved(client, gate)
    set_auto(client, gates={gate: True})
    assert approve(client, gate, rev, actor=BOT).status_code == 200


@pytest.mark.parametrize("gate", GATES)
def test_the_gates_are_independent(client, monkeypatch, gate):
    """Forbidding one gate leaves the others as they were."""
    rev = Stage(client, monkeypatch).at(gate)
    others = [g for g in GATES if g != gate]
    set_auto(client, enabled=True, gates={o: False for o in others})
    assert approve(client, gate, rev, actor=BOT).status_code == 200


def test_enabled_false_wins_over_the_gates(client, monkeypatch):
    rev = Stage(client, monkeypatch).at("outline")
    set_auto(client, enabled=False, gates={g: True for g in GATES})
    assert approve(client, "outline", rev, actor=BOT).status_code == 403


def test_a_human_actor_needs_no_permission_and_a_bad_actor_is_refused(client, monkeypatch):
    rev = Stage(client, monkeypatch).at("outline")
    r = approve(client, "outline", rev, actor="robot")
    assert r.status_code == 422 and r.json()["code"] == "invalid_field" and r.json()["fields"][0]["path"] == "actor"
    assert r.json()["fields"][0]["allowed"] == ["human", "agent:<model id>", "cli:<name>"]
    assert approve(client, "outline", rev, actor=7).status_code == 422
    assert not approved(client, "outline")
    assert approve(client, "outline", rev, actor="human").status_code == 200 and recorded(client, "outline") == "human"


def test_the_refusal_comes_before_any_other_check(client, monkeypatch):
    """A refused agent is told about the rule, not about a stale revision or a missing document."""
    make_book_project(client.root)
    r = client.post(P + "/outline/approve", json={"rev": "stale", "actor": BOT})
    assert r.status_code == 403 and r.json()["code"] == "gate_needs_human"
    assert client.post(P + "/outline/approve", json={"rev": "stale"}).status_code == 404         # the human gets the document's own refusal (no outline yet)
    assert client.post("/api/projects/nope/outline/approve", json={"rev": "x", "actor": BOT}).status_code == 404


def test_the_approval_by_survives_a_save_that_changes_nothing_and_goes_with_a_change(client, monkeypatch):
    s = Stage(client, monkeypatch)
    rev = s.outline()
    set_auto(client, enabled=True)
    assert approve(client, "outline", rev, actor=BOT).status_code == 200
    j = client.get(P + "/outline").json()
    assert j["outline"]["approval"]["by"] == BOT and j["approved"] is True
    o = j["outline"]
    o["thesis"] = o.get("thesis", "") + " (edited)"
    assert client.put(P + "/outline", json={"outline": o, "base_rev": j["rev"]}).status_code == 200
    assert "by" not in client.get(P + "/outline").json()["outline"]["approval"]                # a changed document loses its approval and its `by`


# ---------------------------------------------------------------------------------------------------------------------- paid
def test_the_paid_call_is_never_started_by_an_agent(client, monkeypatch):
    Stage(client, monkeypatch).picks()
    set_auto(client, enabled=True)
    for actor in (BOT, "agent:x"):
        r = client.post(P + "/picks/suggest", json={"beats": ["b0001"], "confirm_paid": True, "actor": actor})
        assert r.status_code == 403 and r.json()["code"] == "spend_needs_human" and r.json()["kind"] == "paid", r.text
    r = client.post(P + "/picks/suggest", json={"beats": ["b0001"]})                          # the page: the route's own answer, unchanged
    assert r.status_code == 422 and r.json()["code"] == "confirm_required"


def test_paid_stays_out_of_reach_even_with_a_forged_file(client, monkeypatch):
    Stage(client, monkeypatch).picks()
    (client.root / PID / "auto.json").write_text(json.dumps({"enabled": True, "spend": {"paid": True}}), encoding="utf-8")
    r = client.post(P + "/picks/suggest", json={"beats": ["b0001"], "confirm_paid": True, "actor": BOT})
    assert r.status_code == 403 and r.json()["code"] == "spend_needs_human"
    st = client.get(P + "/state").json()
    assert st["auto"]["spend"]["paid"] is False and action(st, "picks.suggest")["auto_ok"] is False


# ------------------------------------------------------------------------------------------------------ what the state answer says
def gate_marks(st):
    return {a["id"].split(".")[0]: a["auto_ok"] for a in st["next_actions"] if a["gate"]}


def test_the_state_marks_every_gate_by_the_rule(client, monkeypatch):
    make_book_project(client.root)
    st = client.get(P + "/state").json()
    assert st["auto"] == {"enabled": False, "gates": {g: True for g in GATES}, "spend": {"model": True, "machine_time": True, "paid": False}}
    assert set(gate_marks(st)) == {"outline", "narration"} and not any(gate_marks(st).values())
    set_auto(client, enabled=True)
    st = client.get(P + "/state").json()
    assert st["auto"]["enabled"] is True and all(gate_marks(st).values())
    set_auto(client, gates={"outline": False, "narration": False})
    marks = gate_marks(client.get(P + "/state").json())
    assert marks == {"outline": False, "narration": False}
    set_auto(client, gates={"outline": True})
    assert gate_marks(client.get(P + "/state").json()) == {"outline": True, "narration": False}
    set_auto(client, enabled=False)
    assert not any(gate_marks(client.get(P + "/state").json()).values())


def test_the_state_marks_the_costly_calls_by_the_spend(client, monkeypatch):
    make_book_project(client.root)
    build("picks_approved", client, monkeypatch)
    st = client.get(P + "/state").json()
    assert action(st, "draft.start")["auto_ok"] is True and action(st, "voice.generate")["auto_ok"] is True            # the defaults allow model and machine time
    assert action(st, "picks.suggest")["auto_ok"] is False and action(st, "outline.generate")["auto_ok"] is True
    assert action(st, "picks.search")["auto_ok"] is True and action(st, "picks.import")["auto_ok"] is True                 # no cost: free for an agent
    set_auto(client, spend={"model": False})
    st = client.get(P + "/state").json()
    assert action(st, "draft.start")["auto_ok"] is False and action(st, "outline.generate")["auto_ok"] is False
    assert action(st, "voice.generate")["auto_ok"] is True
    set_auto(client, spend={"machine_time": False, "model": True})
    st = client.get(P + "/state").json()
    assert action(st, "voice.generate")["auto_ok"] is False and action(st, "draft.start")["auto_ok"] is True and st["auto"]["spend"]["machine_time"] is False


def test_the_state_says_who_approved(client, monkeypatch):
    s = Stage(client, monkeypatch)
    st = client.get(P + "/state").json()
    assert st["approvals"] == {g: None for g in GATES}
    rev = s.outline()
    set_auto(client, enabled=True)
    assert approve(client, "outline", rev, actor=BOT).status_code == 200
    st = client.get(P + "/state").json()
    o = st["approvals"]["outline"]
    assert o["by"] == BOT and o["stands"] is True and o["at"] and st["approvals"]["narration"] is None
    assert approve(client, "outline", client.get(P + "/outline").json()["rev"]).status_code == 200      # the owner approves it again: the record follows
    assert client.get(P + "/state").json()["approvals"]["outline"]["by"] == "human"


def test_the_state_says_who_approved_the_storyboard_and_the_picks(client, monkeypatch):
    s = Stage(client, monkeypatch)
    pk = s.picks()
    set_auto(client, enabled=True)
    assert approve(client, "picks", pk, actor="agent:gem").status_code == 200
    put_storyboard(client, PID)
    sb = client.get(P).json()["rev"]
    assert approve(client, "storyboard", sb).status_code == 200
    ap = client.get(P + "/state").json()["approvals"]
    assert ap["picks"]["by"] == "agent:gem" and ap["picks"]["stands"] is True
    assert ap["storyboard"]["by"] == "human" and ap["storyboard"]["stands"] is True
    assert ap["outline"]["by"] == "human" and ap["outline"]["stands"] is True and ap["narration"]["by"] == "human"
    set_auto(client, gates={"storyboard": False})
    assert client.get(P + "/state").json()["approvals"]["storyboard"]["by"] == "human"      # the record is not the rule: it says what happened


def test_an_approval_made_before_who_was_recorded_says_so(client, monkeypatch):
    s = Stage(client, monkeypatch)
    rev = s.outline()
    assert approve(client, "outline", rev).status_code == 200
    f = client.root / PID / "script" / "outline.json"
    raw = json.loads(f.read_text(encoding="utf-8"))
    del raw["approval"]["by"]                                       # what an old file looks like
    f.write_text(json.dumps(raw), encoding="utf-8")
    o = client.get(P + "/state").json()["approvals"]["outline"]
    assert o == {"by": None, "at": raw["approval"]["approved_at"], "stands": True}


def test_an_approval_that_no_longer_stands_is_said_so(client, monkeypatch):
    s = Stage(client, monkeypatch)
    s.picks()
    rev = client.get(P + "/outline").json()["rev"]
    o = client.get(P + "/outline").json()
    o["outline"]["thesis"] = "changed after the approval"
    assert client.put(P + "/outline", json={"outline": o["outline"], "base_rev": rev}).status_code == 200
    ap = client.get(P + "/state").json()["approvals"]
    assert ap["outline"] is None and ap["narration"]["stands"] is False
