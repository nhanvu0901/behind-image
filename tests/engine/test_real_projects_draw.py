"""R2B-018: the real projects can be drawn. `draw_check` (the check approval runs) on the finished reference project and on the
technique lab returns no `undrawable` issue; the R2B-017 case (a buffer of two gigapixels) is still refused."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from bti.engine import guard
from bti.engine.api import open_project

REPO = Path(__file__).resolve().parents[2]


def _copy(name, tmp_path):
    src = REPO / "projects" / name
    if not (src / "storyboard.json").exists() or not (src / "media").is_dir():
        pytest.skip("projects/%s is not present with its media folder" % name)
    d = tmp_path / name
    shutil.copytree(src, d, ignore=shutil.ignore_patterns("cache", "history"))
    return open_project(d)


@pytest.mark.parametrize("name", ["arnolfini", "arnolfini_edit", "technique_lab"])
def test_draw_check_of_a_real_project_is_clean(name, tmp_path):
    p = _copy(name, tmp_path)
    assert [i["message"] for i in p.draw_check()] == []


def test_the_real_limit_admits_real_work_and_refuses_the_24gb_case():
    guard.check_pixels(2478, 3721)                    # the source of arnolfini shot s0014 (the case R2B-018 was about)
    guard.check_pixels(1920, 3410)                    # the ambient fill of a 9:16 short
    guard.check_pixels(3924, 3924)                    # the largest request at a registry maximum
    with pytest.raises(guard.BufferTooLarge):
        guard.check_pixels(1920, 1_036_800)           # R2B-017: 2000 MP


def test_draw_check_samples_start_middle_and_end(tiny_project, monkeypatch):
    from bti.engine import scene as S
    seen = []
    orig = S.Scene.frame_at

    def spy(self, t, width=1920):
        seen.append(round(t, 3))
        return orig(self, t, width)
    monkeypatch.setattr(S.Scene, "frame_at", spy)
    tiny_project.draw_check()
    assert len(seen) >= 9 and len(set(seen)) == len(seen)       # three shots, three samples each (plus overlays), none twice
