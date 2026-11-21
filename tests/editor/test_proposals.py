import copy
import json

from editor_helpers import PID, editable

P = f"/api/projects/{PID}"


def write_proposal(root, pid_, sb, **kw):
    d = root / PID / "proposals"
    d.mkdir(exist_ok=True)
    (d / f"{pid_}.json").write_text(json.dumps({"id": pid_, "created_at": kw.get("created_at", "2026-01-01T00:00:00"),
                                                "author": "agent:test", "summary": "t", "base_rev": "x",
                                                "storyboard": sb}))


def saved(root):
    return json.loads((root / PID / "storyboard.json").read_text())


def test_list_and_detail(client):
    lst = client.get(f"{P}/proposals").json()["items"]
    assert [p["id"] for p in lst] == ["p_demo_001"]
    assert set(lst[0]) == {"id", "created_at", "author", "summary", "n_changes"} and lst[0]["n_changes"] == 6
    j = client.get(f"{P}/proposals/p_demo_001").json()
    assert j["proposal"]["id"] == "p_demo_001"
    by = {c["id"]: c for c in j["changes"]}
    for c in j["changes"]:
        assert {"id", "op", "path", "before", "after", "blocked_by_lock"} <= set(c)
    assert by["shot.s0011"]["op"] == "add" and by["shot.s0011"]["before"] is None
    assert by["shot.s0008"]["op"] == "remove" and by["shot.s0008"]["after"] is None
    ch = by["shot.s0002"]
    assert ch["op"] == "change" and ch["before"]["params"]["camera"][1]["zoom"] == 1.215 \
        and ch["after"]["params"]["camera"][1]["zoom"] == 1.62
    assert by["overlay.s0002.o3"]["op"] == "add" and by["overlay.s0002.o3"]["path"] == "shots[id=s0002].overlays[id=o3]"
    assert by["shot.s0006"]["blocked_by_lock"] is True
    assert sum(c["blocked_by_lock"] for c in j["changes"]) == 1
    assert client.get(f"{P}/proposals/nope").status_code == 404


def test_apply_all_never_touches_locked(client, root):
    before = saved(root)
    r = client.post(f"{P}/proposals/p_demo_001/apply", json={"accept": "all"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert "shot.s0006" in j["skipped_locked"] and "shot.s0006" not in j["applied"]
    after = saved(root)
    s6_b = next(s for s in before["shots"] if s["id"] == "s0006")
    s6_a = next(s for s in after["shots"] if s["id"] == "s0006")
    assert s6_a == s6_b and s6_a["locked"] is True
    ids = [s["id"] for s in after["shots"]]
    assert "s0008" not in ids and ids.index("s0011") == ids.index("s0006") - 1
    by = {s["id"]: s for s in after["shots"]}
    assert by["s0002"]["source"] == "agent" and by["s0002"]["params"]["camera"][1]["zoom"] == 1.62
    assert by["s0011"]["source"] == "agent" and by["s0004"]["technique"] == "CAM-03"
    o3 = next(o for o in by["s0002"]["overlays"] if o["id"] == "o3")
    assert o3["source"] == "agent"
    assert by["s0001"]["source"] == "import"  # untouched items keep their source
    assert j["rev"] and j["storyboard"]["shots"][0]["_t0"] is not None
    # the diff is now only the blocked change
    left = client.get(f"{P}/proposals/p_demo_001").json()["changes"]
    assert [c["id"] for c in left] == ["shot.s0006"]


def test_apply_explicit_locked_id_is_still_blocked(client, root):
    before = saved(root)
    r = client.post(f"{P}/proposals/p_demo_001/apply", json={"accept": ["shot.s0006"]})
    assert r.status_code == 200 and r.json()["applied"] == [] and r.json()["skipped_locked"] == ["shot.s0006"]
    assert saved(root) == before  # nothing written


def test_apply_subset(client, root):
    r = client.post(f"{P}/proposals/p_demo_001/apply", json={"accept": ["shot.s0002"]})
    assert r.status_code == 200 and r.json()["applied"] == ["shot.s0002"]
    after = saved(root)
    ids = [s["id"] for s in after["shots"]]
    assert "s0008" in ids and "s0011" not in ids
    assert next(s for s in after["shots"] if s["id"] == "s0004")["technique"] == "CAM-01"
    assert not any(o["id"] == "o3" for o in next(s for s in after["shots"] if s["id"] == "s0002")["overlays"])


def test_apply_bad_accept(client):
    assert client.post(f"{P}/proposals/p_demo_001/apply", json={"accept": ["nope"]}).status_code == 422
    assert client.post(f"{P}/proposals/p_demo_001/apply", json={"accept": 3}).status_code == 422
    assert client.post(f"{P}/proposals/p_demo_001/apply", json={}).status_code == 422


def test_locked_overlay_and_locked_shot_children(client, root, state):
    sb = editable(state)
    prop = copy.deepcopy(sb)
    for s in prop["shots"]:
        if s["id"] == "s0006":
            s["overlays"][0]["params"]["text"] = "CHANGED"   # locked overlay inside a locked shot
            s["overlays"].append({"id": "o9", "technique": "STATIC-02", "start": s["start"], "dur": 1,
                                  "params": {"text": "x"}})
    write_proposal(root, "p2", prop)
    ch = {c["id"]: c for c in client.get(f"{P}/proposals/p2").json()["changes"]}
    assert ch["overlay.s0006.o1"]["blocked_by_lock"] and ch["overlay.s0006.o9"]["blocked_by_lock"]
    before = saved(root)
    r = client.post(f"{P}/proposals/p2/apply", json={"accept": "all"})
    assert r.status_code == 200 and r.json()["applied"] == [] and saved(root) == before


def test_locked_overlay_in_unlocked_shot(client, root, state):
    sb = editable(state)
    for s in sb["shots"]:
        if s["id"] == "s0006":
            s["locked"] = False
    (root / PID / "storyboard.json").write_text(json.dumps(__import__("bti.editor.common", fromlist=["x"]).strip_derived(sb)))
    st = client.get(P).json()
    prop = copy.deepcopy(editable(st))
    for s in prop["shots"]:
        if s["id"] == "s0006":
            s["overlays"][0]["dur"] = 1.0
            s["params"]["camera"][1]["zoom"] = 1.1
    write_proposal(root, "p3", prop)
    ch = {c["id"]: c for c in client.get(f"{P}/proposals/p3").json()["changes"]}
    assert ch["overlay.s0006.o1"]["blocked_by_lock"] is True      # overlay itself is locked
    assert ch["shot.s0006"]["blocked_by_lock"] is False           # shot is not
    client.post(f"{P}/proposals/p3/apply", json={"accept": "all"})
    s6 = next(s for s in saved(root)["shots"] if s["id"] == "s0006")
    assert s6["params"]["camera"][1]["zoom"] == 1.1 and s6["overlays"][0]["dur"] == 4.0 and s6["overlays"][0]["source"] == "human"


def test_agent_cannot_unlock_or_self_lock(client, root, state):
    prop = editable(state)
    for s in prop["shots"]:
        if s["id"] == "s0006":
            s["locked"] = False
        if s["id"] == "s0001":
            s["locked"] = True
            s["note"] = "agent note"
    write_proposal(root, "p4", prop)
    r = client.post(f"{P}/proposals/p4/apply", json={"accept": "all"})
    assert r.status_code == 200
    by = {s["id"]: s for s in saved(root)["shots"]}
    assert by["s0006"]["locked"] is True and by["s0001"]["locked"] is False and by["s0001"]["note"] == "agent note"


def test_apply_invalid_result_422_and_unchanged(client, root, state):
    prop = editable(state)
    prop["shots"][1]["technique"] = "NOPE-1"
    write_proposal(root, "p5", prop)
    before = saved(root)
    r = client.post(f"{P}/proposals/p5/apply", json={"accept": "all"})
    assert r.status_code == 422 and r.json()["issues"] and saved(root) == before


def test_new_asset_comes_with_shot(client, root, state):
    prop = editable(state)
    prop["assets"]["Z"] = copy.deepcopy(prop["assets"]["C"])
    prop["shots"][0]["slots"]["image"] = {"asset": "Z"}
    write_proposal(root, "p6", prop)
    ch = {c["id"] for c in client.get(f"{P}/proposals/p6").json()["changes"]}
    assert ch == {"asset.Z", "shot.s0001"}
    assert client.post(f"{P}/proposals/p6/apply", json={"accept": ["shot.s0001"]}).status_code == 422  # asset missing
    assert client.post(f"{P}/proposals/p6/apply", json={"accept": "all"}).status_code == 200
    assert "Z" in saved(root)["assets"]


def test_corrupt_proposal_quarantined(client, root):
    (root / PID / "proposals" / "bad.json").write_text("{not json")
    assert [p["id"] for p in client.get(f"{P}/proposals").json()["items"]] == ["p_demo_001"]
    assert not (root / PID / "proposals" / "bad.json").exists()
    assert list((root / PID / "proposals").glob("bad.json.corrupt-*"))


def test_listing_sorted_newest_first(client, root, state):
    write_proposal(root, "newer", editable(state), created_at="2027-01-01T00:00:00")
    assert [p["id"] for p in client.get(f"{P}/proposals").json()["items"]] == ["newer", "p_demo_001"]


def test_proposal_diff_and_apply_identity_video_title():
    from bti.editor import proposals as PR

    assert PR.shape_problem({"shots": [], "identity": "bad"}) is not None
    assert PR.shape_problem({"shots": [], "identity": {"style": "raking", "video_title": "New"}}) is None

    base = {"schema": "bti.storyboard/1", "style": "gae", "assets": {}, "shots": [],
            "identity": {"style": "raking", "video_title": "Old Title"}}
    prop_new = {**base, "identity": {"style": "raking", "video_title": "Person Title"}}
    changes = PR.diff(base, prop_new)
    assert [(c["id"], c["kind"], c["op"]) for c in changes] == [("identity", "identity", "change")]
    applied, ids, skipped = PR.apply(base, prop_new, "all")
    assert ids == ["identity"] and skipped == []
    assert applied["identity"] == {"style": "raking", "video_title": "Person Title"}

    # Edit mode preserves existing identity, so diff emits no identity change.
    assert PR.diff(base, copy.deepcopy(base)) == []

    # When saved has no identity block yet, apply inserts it right after style.
    no_ident = {"schema": "bti.storyboard/1", "style": "gae", "assets": {}, "shots": []}
    with_ident = {**no_ident, "identity": {"style": "raking", "video_title": "Agent Title"}}
    applied2, _, _ = PR.apply(no_ident, with_ident, "all")
    assert list(applied2.keys())[:2] == ["schema", "style"] and list(applied2.keys())[2] == "identity"
    assert applied2["identity"]["video_title"] == "Agent Title"
