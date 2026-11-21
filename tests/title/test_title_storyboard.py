"""A title reaches the storyboard: a PUT while a storyboard exists applies the channel identity again with the new title in the same request (the revision changes, the approval
stops standing, the answer says so), a same title changes nothing, a refusal of the engine never undoes the title, the function the job calls does the same, and a full draft compile
writes `identity.video_title` from the document. Real engine, a copy of the demo project (the pattern of tests/editor/test_identity_route.py)."""
import json
import shutil

import pytest

pytest.importorskip("cv2")
engine_api = pytest.importorskip("bti.engine.api")

from bti import identity as ID  # noqa: E402
from bti.editor.common import compute_rev, storyboard_approval  # noqa: E402
from bti.title import apply as tapply, store as T  # noqa: E402
from editor_helpers import PID, REPO  # noqa: E402

P = "/api/projects/%s" % PID
STYLE = json.loads((REPO / "style" / "gae" / "style.json").read_text(encoding="utf-8"))
TITLE = "The Saint Who Was Also an Advertisement"


def put_title_card(root):
    """The demo project has a chapter card but no title card: give it one (the pattern of the identity route's tests)."""
    f = root / PID / "storyboard.json"
    sb = json.loads(f.read_text(encoding="utf-8"))
    card = {"id": "s0099", "start": {"t": 5.0}, "technique": "X-CARD-02", "slots": {"background": {"asset": "A"}},
            "params": {"title": "DEMO PORTRAIT", "artist": "GENERATED", "year": "2026"}, "intent": "structure", "transition_in": None,
            "overlays": [], "locked": False, "source": "agent", "note": "title card"}
    sb["shots"].insert(1, card)
    f.write_text(json.dumps(sb, indent=1), encoding="utf-8")


@pytest.fixture()
def rc(make_client, root):
    if not STYLE.get("identity"):
        pytest.skip("style/gae/style.json has no identity block")
    shutil.copytree(REPO / "projects" / PID, root / PID, ignore=shutil.ignore_patterns("cache", "history"))
    put_title_card(root)
    return make_client(engine_module=engine_api)


def saved(c):
    return json.loads((c.root / PID / "storyboard.json").read_text(encoding="utf-8"))


def choose(c, style="raking"):
    r = c.put(P + "/identity", json={"style": style, "base_rev": c.get(P).json()["rev"]})
    assert r.status_code == 200, r.text
    return r.json()


def approve_as_stored(c):
    """The storyboard's approval as the approve route records it (by hand, like the identity route's tests: the demo project is not a real one)."""
    raw = saved(c)
    rev = compute_rev(raw)
    raw["approvals"] = {"storyboard": {"rev": rev, "approved_at": "2026-11-20T00:00:00+0000"}}
    (c.root / PID / "storyboard.json").write_text(json.dumps(raw, indent=1), encoding="utf-8")
    assert storyboard_approval(saved(c)) == "fresh"
    return rev


def put(c, **body):
    rev = c.get(P + "/title").json()["rev"]
    return c.put(P + "/title", json={"base_rev": rev, **body})


def beat(sb):
    return next(s for s in sb["shots"] if s["technique"].startswith("ID-BRAND"))


def test_a_title_set_while_a_storyboard_exists_is_applied_in_the_same_request_and_the_approval_stops_standing(rc):
    choose(rc)
    before_rev = approve_as_stored(rc)
    r = put(rc, text=TITLE, actor="cli:operator")
    assert r.status_code == 200, r.text
    b = r.json()
    sb = saved(rc)
    assert b["storyboard"]["rev"] == compute_rev(sb) != before_rev and "s0099" in b["storyboard"]["changed"] and b["storyboard"]["approval_was_fresh"] is True
    assert b["storyboard"]["sentence"].startswith("Đã cập nhật tựa video trên storyboard (") and b["storyboard"]["sentence"].endswith("Storyboard đã đổi nên cần được duyệt lại.")
    assert sb["identity"] == {"style": "raking", "video_title": TITLE}
    assert beat(sb)["params"]["title"] == TITLE and beat(sb)["params"]["text"] == STYLE["identity"]["channel_name"]
    assert storyboard_approval(sb) == "stale"                                                    # the existing rule: the approved bytes are not the saved ones any more
    g = rc.get(P + "/title").json()
    assert g["storyboard"] == {"exists": True, "title": TITLE, "same": True, "off_voice": False}
    assert rc.get(P + "/identity").json()["video_title"] == TITLE


def test_the_same_title_again_changes_nothing_and_the_approval_keeps_standing(rc):
    choose(rc)
    put(rc, text=TITLE)
    rev = approve_as_stored(rc)
    r = put(rc, text=TITLE, actor="cli:other")
    assert r.status_code == 200 and r.json()["storyboard"] == {"rev": rev, "changed": [], "approval_was_fresh": False,
                                                              "sentence": "Storyboard đã có đúng tựa video này."}
    assert compute_rev(saved(rc)) == rev and storyboard_approval(saved(rc)) == "fresh"


def test_a_new_title_replaces_the_old_one_on_the_beat(rc):
    choose(rc)
    put(rc, text=TITLE)
    r = put(rc, text="Why Is a Saint Weighing a Ring?")
    assert r.status_code == 200 and beat(saved(rc))["params"]["title"] == "Why Is a Saint Weighing a Ring?" and saved(rc)["identity"]["video_title"] == "Why Is a Saint Weighing a Ring?"


def test_a_storyboard_that_has_no_style_yet_gets_the_default_one_with_the_title(rc):
    assert "identity" not in saved(rc)
    r = put(rc, text=TITLE)
    assert r.status_code == 200 and saved(rc)["identity"] == {"style": STYLE["identity"]["default_style"], "video_title": TITLE}


def test_a_refusal_of_the_engine_never_undoes_the_title(rc, monkeypatch):
    choose(rc)
    raw = saved(rc)

    def refuse(*a, **k):
        raise ID.IdentityError("identity_style_unknown", "the engine refused it")
    monkeypatch.setattr(ID, "apply_identity", refuse)
    r = put(rc, text=TITLE)
    assert r.status_code == 200
    sb = r.json()["storyboard"]
    assert sb["changed"] == [] and sb["rev"] is None and "the engine refused it" in sb["error"] and sb["sentence"].startswith("Chưa cập nhật được tựa video trên storyboard")
    assert saved(rc) == raw and T.chosen_text(rc.root / PID) == TITLE                           # the title is written; the storyboard takes it at the next draft or the next call
    assert rc.get(P + "/title").json()["storyboard"]["same"] is False


def test_a_storyboard_that_cannot_be_read_never_breaks_the_title(rc):
    (rc.root / PID / "storyboard.json").write_text("{ not json", encoding="utf-8")
    r = put(rc, text=TITLE)
    assert r.status_code == 200 and "error" in r.json()["storyboard"] and T.chosen_text(rc.root / PID) == TITLE


def test_the_function_the_job_calls_does_the_same_through_the_registered_hook(rc):
    choose(rc)
    approve_as_stored(rc)
    out = tapply.apply_to_storyboard(rc.root / PID, "A Title From The Job")
    assert out["changed"] and out["approval_was_fresh"] is True and saved(rc)["identity"]["video_title"] == "A Title From The Job"
    assert tapply.apply_to_storyboard(rc.root / "elsewhere" / PID, "x") is None                  # a project of another projects folder: no function registered for it


def test_a_project_without_a_storyboard_answers_none(client, root):
    from title_helpers import make_title_project
    make_title_project(root, "pk1")
    r = client.put("/api/projects/pk1/title", json={"base_rev": T.EMPTY_REV, "text": TITLE})
    assert r.status_code == 200 and r.json()["storyboard"] is None
