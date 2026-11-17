import json

import pytest

from bti.picks import doc
from bti.script.store import DocumentCorrupt, ProjectGone, StaleRevision


def asset(**kw):
    a = {"file": "media/a.jpg", "kind": "image", "title": "A", "artist": "", "year": "", "width": 2000, "height": 3000,
         "credit": {"source": "commons", "source_url": "u", "author": "x", "licence": "PD", "flag": None}, "regions": {}}
    a.update(kw)
    return a


def good():
    return {"schema": doc.SCHEMA, "main_asset": "A", "assets": {"A": asset(regions={"MIRROR": {"x": 10, "y": 20, "rx": 5, "ry": 5, "label": "Gương"}})},
            "beats": {"b0001": {"items": [{"asset": "A", "region": "MIRROR", "role": "detail", "note": ""}], "status": "picked", "note": ""}},
            "approval": {"approved": False}}


def test_normalize_is_forgiving():
    d = doc.normalize({"main_asset": "ZZ", "assets": {"A": {"file": "m/a.jpg", "credit": {"flag": "bogus"}}, "B": "junk"},
                       "beats": {"b0001": {"items": [{"asset": "A", "role": "nope"}, {"x": 1}], "status": "weird"}, "x": 5}})
    assert d["main_asset"] is None and list(d["assets"]) == ["A"]
    assert d["assets"]["A"]["credit"]["flag"] is None
    b = d["beats"]["b0001"]
    assert len(b["items"]) == 1 and b["items"][0]["role"] == "detail" and b["status"] == "picked"
    assert doc.normalize(None)["beats"] == {}


@pytest.mark.parametrize("mut,frag", [
    (lambda d: d.update(main_asset=3), "main_asset"),
    (lambda d: d["beats"].update({"bad": {}}), "beat id"),
    (lambda d: d["beats"]["b0001"]["items"][0].update(role="x"), "role"),
    (lambda d: d["beats"]["b0001"].update(status="x"), "status"),
    (lambda d: d["assets"]["A"]["regions"].update({"R": {"y": 1}}), "numeric"),
    (lambda d: d["assets"].update({"bad key!": {}}), "asset key"),
    (lambda d: d["beats"]["b0001"].update(items="no"), "items"),
])
def test_doc_problem(mut, frag):
    d = good()
    assert doc.doc_problem(d) is None
    mut(d)
    assert frag in doc.doc_problem(d)
    assert "required" in doc.doc_problem([])


def test_revision_ignores_approval_and_save_drops_stale_approval(tmp_path):
    d = doc.normalize(good())            # the revision is always of the normalised document
    r1 = doc.revision(d)
    d["approval"] = {"approved": True, "sha1": r1}
    assert doc.revision(d) == r1
    with doc.Held(tmp_path):
        assert doc.save(tmp_path, d) == r1
        assert doc.load(tmp_path)["approval"]["approved"] is True        # same content: approval stays
        d2 = doc.load(tmp_path)
        d2["beats"]["b0002"] = {"items": [], "status": "skip", "note": ""}
        r2 = doc.save(tmp_path, d2)
    assert r2 != r1 and doc.load(tmp_path)["approval"]["approved"] is False
    assert (tmp_path / "picks.prev.json").is_file()


def test_base_rev_mismatch_is_stale(tmp_path):
    with doc.Held(tmp_path):
        doc.save(tmp_path, good())
        with pytest.raises(StaleRevision):
            doc.save(tmp_path, good(), base_rev="old")
        doc.save(tmp_path, good(), base_rev=doc.disk_rev(tmp_path))


def test_held_on_deleted_project_raises_and_writes_nothing(tmp_path):
    gone = tmp_path / "gone"
    with pytest.raises(ProjectGone):
        with doc.Held(gone):
            doc.save(gone, good())
    assert not gone.exists()


def test_corrupt_file_is_data_error(tmp_path):
    (tmp_path / "picks.json").write_text("{nope")
    with pytest.raises(DocumentCorrupt) as e:
        doc.load(tmp_path)
    assert e.value.what == "picks"


def test_approval_state_reasons():
    d = good()
    assert doc.approval_state(d, "n1", True) == {"approved": False, "reason": None}
    d["approval"] = {"approved": True, "sha1": doc.revision(d), "narration_sha1": "n1"}
    assert doc.approval_state(d, "n1", True)["approved"]
    assert doc.approval_state(d, "n2", True)["reason"] == "narration_changed"
    assert doc.approval_state(d, "n1", False)["reason"] == "narration_not_approved"
    d["main_asset"] = None
    assert doc.approval_state(d, "n1", True)["reason"] == "picks_edited"


def codes(iss, level=None):
    return sorted(i["code"] for i in iss if level in (None, i["level"]))


def test_issues(tmp_path):
    assert codes(doc.issues(None), "error") == ["no_main"]
    d = good()
    (tmp_path / "media").mkdir()
    (tmp_path / "media/a.jpg").write_bytes(b"x")
    assert doc.issues(d, tmp_path, ["b0001"]) == []
    d["beats"]["b0001"]["items"][0]["region"] = "GONE"
    d["beats"]["b0002"] = {"items": [{"asset": "Q", "region": None, "role": "detail", "note": ""}], "status": "picked", "note": ""}
    iss = doc.issues(d, tmp_path, ["b0001", "b0002"])
    assert codes(iss, "error") == ["unknown_asset", "unknown_region"]
    d2 = good()
    d2["assets"]["A"]["credit"]["flag"] = "small"
    iss = doc.issues(d2, tmp_path, ["b0001", "b0002", "b0003"])
    assert codes(iss, "warning") == ["asset_flag", "beat_no_pick", "beat_no_pick"]
    d2["beats"]["b0002"] = {"items": [], "status": "skip", "note": ""}
    assert codes(doc.issues(d2, tmp_path, ["b0001", "b0002"]), "warning") == ["asset_flag"]        # skip is not missing
    assert "beat_unknown" in codes(doc.issues(good(), tmp_path, ["b0099"]))
    assert doc.issues(good(), None, None) == []
    assert codes(doc.issues(good(), tmp_path / "nofiles", None), "error") == ["asset_file_missing"]
