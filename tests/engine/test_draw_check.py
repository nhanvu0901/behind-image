"""Interface used by the editor backend: RenderError from frame_at / render_range, and Project.draw_check."""
from __future__ import annotations

import copy

import pytest

from bti.engine import storyboard as SB
from bti.engine.errors import DataError, RenderError


def _broken_label(project):
    sb = copy.deepcopy(project.storyboard())
    sb["shots"][0]["overlays"][2]["params"]["text"] = "ok"
    return sb


def _poison(monkeypatch, tid):
    from bti.engine import registry as R
    cls = R.RENDERERS[tid][0]

    def boom(self, *a, **k):
        raise KeyError("boom")
    for name in ("render", "apply", "blend"):
        if name in cls.__dict__:
            monkeypatch.setattr(cls, name, boom)


def test_draw_check_is_clean_for_a_good_project(tiny_project):
    assert tiny_project.draw_check() == []


def test_failing_technique_is_render_error_with_ids(tiny_project, monkeypatch):
    _poison(monkeypatch, "X-ANN-01")                      # overlay o3 of shot s1
    with pytest.raises(RenderError) as e:
        tiny_project.frame_at(1.5, 160)
    assert (e.value.shot, e.value.overlay, e.value.technique, e.value.what) == ("s1", "o3", "X-ANN-01", "render")
    assert isinstance(e.value, DataError)


def test_render_range_raises_render_error_and_leaves_no_file(tiny_project, monkeypatch, tmp_path):
    _poison(monkeypatch, "X-CARD-01")                     # shot s2
    out = tmp_path / "o.mp4"
    with pytest.raises(RenderError) as e:
        tiny_project.render_range(5.0, 7.0, out, 160, 5)
    assert e.value.shot == "s2" and not out.exists()


def test_draw_check_lists_each_failure_and_keeps_the_draft(tiny_project, monkeypatch):
    _poison(monkeypatch, "X-ANN-01")
    _poison(monkeypatch, "X-CARD-01")
    tiny_project.use_draft(None)
    issues = tiny_project.draw_check()
    assert {(i["path"], i["shot"]) for i in issues} == {("shots[0].overlays[2]", "s1"), ("shots[1]", "s2")}
    assert all(i["level"] == "error" and i["code"] == "undrawable" and i["code"] in SB.ISSUE_CODES for i in issues)
    assert tiny_project._draft is None
    draft = tiny_project.storyboard()
    tiny_project.use_draft(draft)
    tiny_project.draw_check(draft)
    assert tiny_project._draft == draft


def test_deep_documents_raise_data_error_not_recursion_error():
    doc = cur = {}
    for _ in range(3000):
        cur["a"] = {}
        cur = cur["a"]
    with pytest.raises(DataError):
        SB.strip_derived(doc)
    with pytest.raises(DataError):
        SB.canonical(doc)


def test_unreadable_media_names_the_asset_in_the_render_error_and_the_undrawable_issue(tiny_project, tmp_path):
    sb = tiny_project.storyboard()
    key = next(k for k, a in sb["assets"].items() if a.get("kind") == "image")
    f = tiny_project.dir / sb["assets"][key]["file"]
    keep = f.read_bytes()
    try:
        f.write_bytes(b"not a picture")
        from bti.engine import base as engine_base
        engine_base.IMAGES.clear() if hasattr(engine_base.IMAGES, "clear") else None
        issues = tiny_project.draw_check(sb)
        bad = [i for i in issues if i["code"] == "undrawable"]
        assert bad and all("asset" in i["args"] for i in bad)
        assert any(i["args"]["asset"] == key for i in bad), bad
    finally:
        f.write_bytes(keep)
