"""R2B-017: validate accepted a value that made the engine allocate 24 GB (SHORT-02 `frame_aspect` "0:1": a 2 px wide panel, so a
blurred ambient fill 1 million rows tall). The registry now refuses the value and the engine refuses the buffer."""
from __future__ import annotations

import numpy as np
import pytest

import cv2
from bti.engine import guard
from bti.engine import registry as R
from bti.engine.errors import RenderError
from bti.engine.techniques import _t4_common as C


def test_registry_refuses_extreme_aspects():
    spec = R.load_bundle("gae").spec("SHORT-02")
    for bad in ("0:1", "1:0", "1:1000", "1000:1", "x", "9:16:1", ""):
        issues = R.validate_params(spec, {"frame_aspect": bad}, "p")
        assert any(i["level"] == "error" for i in issues), bad
    for good in ("9:16", "16:9", "1:1", "4:5"):
        assert not R.validate_params(spec, {"frame_aspect": good}, "p"), good


def test_aspect_wh_never_returns_a_degenerate_panel():
    for bad in ("0:1", "1:1000", "1000:1", "nonsense", "1:0"):
        assert C.aspect_wh(bad, 1080) == (608, 1080), bad
    assert C.aspect_wh("16:9", 1080) == (1920, 1080)


def test_guard_is_off_outside_drawing():
    big = cv2.resize(np.zeros((2, 2, 3), np.uint8), (4386, 6000))          # a 26 MP resize is fine for media code and tools
    assert big.shape[:2] == (6000, 4386)


def test_guard_refuses_huge_buffers_before_allocating():
    small = np.zeros((2, 2, 3), np.float32)
    with guard.limited():
        _refuse(small)


def _refuse(small):
    with pytest.raises(guard.BufferTooLarge):
        cv2.resize(small, (1920, 1_000_000), interpolation=cv2.INTER_AREA)
    with pytest.raises(guard.BufferTooLarge):
        cv2.warpAffine(small, np.eye(2, 3, dtype=np.float64), (100_000, 100_000))
    with pytest.raises(guard.BufferTooLarge):
        cv2.warpPerspective(small, np.eye(3), (100_000, 100_000))
    with pytest.raises(guard.BufferTooLarge):
        guard.check_pixels(float("nan"), 10)
    cv2.resize(small, (1920, 1080))                      # a normal canvas is fine
    guard.check_pixels(1920 * 2, 1080 * 2)


def test_guard_error_surfaces_as_render_error(tiny_project):
    """A technique that asks for an absurd buffer fails as RenderError naming the shot and the technique, not as an allocation."""
    cls = R.RENDERERS["CAM-05"][0]
    orig = cls.render

    def boom(self, t):
        cv2.resize(np.zeros((2, 2, 3), np.float32), (1920, 5_000_000))
    cls.render = boom
    try:
        with pytest.raises(RenderError) as e:
            tiny_project.frame_at(1.0, 160)
    finally:
        cls.render = orig
    assert e.value.shot == "s1" and e.value.technique == "CAM-05"
    assert "larger than the engine allows" in e.value.message
