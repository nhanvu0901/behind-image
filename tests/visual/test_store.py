import pytest
from bti.visual import store
from bti.script.store import StaleRevision


def test_save_is_revision_checked_and_keeps_history(tmp_path):
    one = {"schema": "bti.visual/1", "cast": [], "wanted": [], "moments": []}
    rev = store.save(tmp_path, one, base_rev=None)
    assert store.load(tmp_path) == one
    two = {**one, "cast": [{"id": "x"}]}
    with pytest.raises(StaleRevision):
        store.save(tmp_path, two, base_rev="wrong")
    assert store.load(tmp_path) == one
    store.save(tmp_path, two, base_rev=rev)
    assert store.load(tmp_path) == two
    assert len(list((tmp_path / "history").glob("visual_*.json"))) == 1


def test_save_does_not_recreate_a_project_removed_during_write(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    def removed(_):
        project.rmdir()
        return None
    monkeypatch.setattr(store, "load", removed)
    with pytest.raises(store.common.ProjectGone):
        store.save(project, {"schema": "bti.visual/1"}, base_rev=None)
    assert not project.exists()
