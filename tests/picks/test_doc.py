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


# ---------------------------------------------------------------- kinds, missing and the outside lines (worker linekinds)
def outside_doc():
    d = good()
    d["assets"]["B"] = asset(file="media/b.jpg", title="Noyon Cathedral")
    d["beats"] = {
        "b0001": {"items": [{"asset": "A", "region": "MIRROR", "role": "detail", "note": ""}], "status": "picked", "note": "", "kinds": ["detail"]},
        "b0002": {"items": [{"asset": "A", "region": None, "role": "main", "note": ""}], "status": "picked", "note": "", "kinds": ["outside"],
                  "missing": [{"what": "Noyon Cathedral", "code": "agent_none"}]},                                   # outside, shows only the painting
        "b0003": {"items": [{"asset": "B", "region": None, "role": "context", "note": ""}], "status": "picked", "note": "", "kinds": ["outside", "figure"]},
        "b0004": {"items": [{"asset": "A", "region": "MIRROR", "role": "detail", "note": ""}], "status": "picked", "note": "", "kinds": ["compare"]},
        "b0005": {"items": [], "status": "skip", "note": "", "kinds": ["outside"]},                                  # the owner settled it: the painting again, on purpose
        "b0006": {"items": [], "status": "todo", "note": "", "kinds": ["outside"]},                                  # nothing at all
        "b0007": {"items": [{"asset": "A", "region": None, "role": "main", "note": ""}], "status": "picked", "note": "", "kinds": ["idea"]},
        "b0008": {"items": [{"asset": "A", "region": None, "role": "main", "note": ""}], "status": "picked", "note": ""}}          # a beat of a document made before
    return d


def test_normalize_keeps_kinds_and_missing_only_when_they_are_there():
    d = doc.normalize(outside_doc())
    assert d["beats"]["b0002"]["kinds"] == ["outside"] and d["beats"]["b0002"]["missing"] == [{"what": "Noyon Cathedral", "code": "agent_none"}]
    assert "kinds" not in d["beats"]["b0008"] and "missing" not in d["beats"]["b0008"] and "missing" not in d["beats"]["b0001"]
    junk = doc.normalize({"assets": {}, "beats": {"b0001": {"items": [], "kinds": ["idea", "idea", "nope", "whole", "detail"], "missing": [
        {"what": " Noyon  Cathedral ", "code": "agent_none"}, {"what": "", "code": "x"}, {"what": "y", "code": "Bad Code"}, {"what": 1, "code": "x"}, "z"]},
        "b0002": {"items": [], "kinds": "outside", "missing": {"what": "x"}}}})
    assert junk["beats"]["b0001"]["kinds"] == ["idea", "whole"] and junk["beats"]["b0001"]["missing"] == [{"what": "Noyon Cathedral", "code": "agent_none"}]
    assert "kinds" not in junk["beats"]["b0002"] and "missing" not in junk["beats"]["b0002"]


def test_a_document_made_before_kinds_existed_has_the_revision_it_had():
    before = good()
    d = doc.normalize(before)
    assert set(d["beats"]["b0001"]) == {"items", "status", "note"}
    assert doc.revision(d) == doc.revision(doc.normalize(json.loads(json.dumps(before))))
    plain = {"items": [{"asset": "A", "region": "MIRROR", "role": "detail", "note": ""}], "status": "picked", "note": ""}
    assert d["beats"]["b0001"] == plain
    assert doc.revision(doc.normalize({**before, "beats": {"b0001": {**plain, "kinds": []}}})) == doc.revision(d)         # an empty list is no field


@pytest.mark.parametrize("mut,frag", [
    (lambda d: d["beats"]["b0001"].update(kinds="outside"), "kinds"),
    (lambda d: d["beats"]["b0001"].update(kinds=["detail", "whole", "idea"]), "kinds"),
    (lambda d: d["beats"]["b0001"].update(kinds=["picture"]), "kinds"),
    (lambda d: d["beats"]["b0001"].update(missing="x"), "missing"),
    (lambda d: d["beats"]["b0001"].update(missing=[{"what": "x"}]), "missing"),
    (lambda d: d["beats"]["b0001"].update(missing=[{"what": "x", "code": "a"}] * 11), "missing"),
])
def test_doc_problem_for_kinds_and_missing(mut, frag):
    d = good()
    d["beats"]["b0001"].update(kinds=["detail"], missing=[{"what": "x", "code": "agent_none"}])
    assert doc.doc_problem(d) is None
    mut(d)
    assert frag in doc.doc_problem(d)


def test_the_warning_outside_no_picture_names_each_line_about_something_outside_that_shows_only_the_painting():
    d = doc.normalize(outside_doc())
    ids = ["b%04d" % i for i in range(1, 9)]
    got = [i for i in doc.issues(d, None, ids) if i["code"] == "outside_no_picture"]
    assert [i["beat"] for i in got] == ["b0002", "b0004", "b0006"] and all(i["level"] == "warning" for i in got)
    assert "looked for: Noyon Cathedral" in got[0]["message"] and "outside the painting" in got[0]["message"]
    assert [i["beat"] for i in doc.issues(d, None, ids) if i["code"] == "beat_no_pick"] == ["b0006"]                     # the old warning is as it was
    assert doc.blocking(doc.issues(d, None, ids)) == []                                                                   # never an error
    only = [i["beat"] for i in doc.issues(d, None, None) if i["code"] == "outside_no_picture"]
    assert only == ["b0002", "b0004", "b0006"]                                                                            # also when the narration is not known


def test_a_line_that_is_not_in_the_narration_raises_only_beat_unknown():
    d = doc.normalize(outside_doc())
    codes = [(i["code"], i["beat"]) for i in doc.issues(d, None, ["b0001", "b0003"]) if i.get("beat") in ("b0002", "b0004")]
    assert codes == [("beat_unknown", "b0002"), ("beat_unknown", "b0004")]


def test_the_summary_counts_the_lines_about_something_outside_and_those_without_the_picture():
    d = doc.normalize(outside_doc())
    ids = ["b%04d" % i for i in range(1, 9)]
    assert doc.outside_summary(d, ids) == {"lines": 4, "with_picture": 1, "without": ["b0002", "b0004", "b0006"]}      # b0005 is skip: the owner settled it, it is not counted
    assert doc.outside_summary(d, ids[:3]) == {"lines": 2, "with_picture": 1, "without": ["b0002"]}                   # only the lines of the narration
    assert doc.outside_summary(d) == doc.outside_summary(d, ids)
    assert doc.outside_summary(None, ids) == {"lines": 0, "with_picture": 0, "without": []}


def test_a_document_without_kinds_raises_nothing_new_and_says_zero_outside_lines():
    d = doc.normalize(good())
    d["beats"]["b0002"] = {"items": [{"asset": "A", "region": None, "role": "main", "note": ""}], "status": "picked", "note": ""}
    assert {i["code"] for i in doc.issues(d, None, ["b0001", "b0002", "b0003"])} == {"beat_no_pick"}
    assert doc.outside_summary(d, ["b0001", "b0002", "b0003"]) == {"lines": 0, "with_picture": 0, "without": []}


def test_cast_names_survive_normalization_and_affect_revision():
    from bti.picks import doc
    raw = {'main_asset': 'A', 'assets': {'A': {'file': 'media/a.jpg'}}, 'beats': {},
           'names': [{'name': 'Costanza Trenta', 'also': ['Costanza'], 'line': 'b0001',
                      'where': {'region': 'HEAD'}, 'sure': False, 'words': 'most often named'}]}
    saved = doc.normalize(raw)
    assert saved['names'] == raw['names']
    assert doc.revision(saved) != doc.revision(doc.normalize({k: v for k, v in raw.items() if k != 'names'}))
    assert 'names' not in doc.normalize({})


def test_cast_document_refuses_duplicate_aliases_and_empty_picture():
    d = good()
    one = {'name': 'Costanza Trenta', 'also': ['Costanza'], 'line': 'b0001', 'where': {'region': 'MIRROR'}, 'sure': False, 'words': 'most often named'}
    d['names'] = [one, {**one, 'name': 'costanza', 'also': [], 'line': 'b0002'}]
    assert 'repeats' in doc.doc_problem(d)
    d['names'] = [{**one, 'where': {'asset': ''}}]
    assert 'picks.names' in doc.doc_problem(d)
