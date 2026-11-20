"""The export is refused while the storyboard does not fit the voice (worker introflow): `storyboard_off_voice`, before any part is planned or rendered.
The reference projects (arnolfini and the lab projects: a timing the voice code did not write) are not judged, so they export as before."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "draft"))

from bti.draft import retime  # noqa: E402
from bti.export import run  # noqa: E402
from bti.export.errors import ExportError  # noqa: E402
from bti.editor.common import compute_rev  # noqa: E402
from intro_helpers import brand03  # noqa: E402,F401  (a fixture)


def approve(d: Path) -> str:
    sb = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
    sb["approvals"] = {"storyboard": {"rev": compute_rev(sb), "at": "2026-11-16T12:00:00"}}
    (d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    return sb["approvals"]["storyboard"]["rev"]


def test_a_reference_project_with_an_old_timing_is_not_judged_and_still_exports(patch_run, project, settings, fake_tools):
    assert retime.project_off_voice(project) == []
    job = run.start(project, settings=settings)
    assert job["state"] == "done"


def test_the_export_is_refused_with_the_problems_and_nothing_starts(patch_run, project, settings, fake_tools, manager, monkeypatch):
    problem = {"code": "end_off", "shot": None, "chapter": None, "message": "the video ends at 86.00 s, the voice lasts 820.83 s", "repair": True, "locked": False}
    monkeypatch.setattr(retime, "project_off_voice", lambda *a, **k: [problem])
    with pytest.raises(ExportError) as e:
        run.start(project, settings=settings)
    assert e.value.code == "storyboard_off_voice" and e.value.status == 409 and e.value.extra["problems"] == [problem]
    assert "does not fit the voice" in e.value.message
    assert fake_tools.calls() == [] and not manager.running
    monkeypatch.setattr(retime, "project_off_voice", lambda *a, **k: [])
    assert run.start(project, settings=settings)["state"] == "done"                 # after the fit the same call goes on


def test_a_real_storyboard_made_for_another_voice_is_refused_until_it_is_retimed(tmp_path, patch_run, settings, fake_tools, brand03):
    pytest.importorskip("cv2")
    from intro_helpers import compiled, intro_timing, make_project, style_doc
    d = make_project(tmp_path, intro_timing(5.0, 10.2), "intro")
    (d / "storyboard.json").write_text(json.dumps(compiled(d).storyboard), encoding="utf-8")
    (d / "audio").mkdir()
    (d / "audio" / "mix.m4a").write_text("{}")
    approve(d)
    (d / "timing.json").write_text(json.dumps(intro_timing(7.0, 12.0)), encoding="utf-8")          # the voice was made again
    with pytest.raises(ExportError) as e:
        run.start(d, settings=settings)
    assert e.value.code == "storyboard_off_voice" and {p["code"] for p in e.value.extra["problems"]} >= {"title_off", "card_off", "end_off"}
    new, report = retime.retime(json.loads((d / "storyboard.json").read_text(encoding="utf-8")), intro_timing(7.0, 12.0), style_doc(), {"main_asset": "A"}, brand03.param_defaults)
    (d / "storyboard.json").write_text(json.dumps(new), encoding="utf-8")
    approve(d)
    assert retime.project_off_voice(d) == []
