from types import SimpleNamespace
import numpy as np
from bti.engine import registry
from bti.engine.techniques import layout


def test_pair_entrance_shows_both_captions_at_start_and_preserves_default(monkeypatch):
    class Cam:
        def at(self, t): return (0, 0, 1)
    class Picture:
        def view(self, *args): return (np.ones((2, 2, 3)),)
    class Caption:
        def __init__(self): self.alpha = []
        def apply(self, frame, alpha): self.alpha.append(alpha)
    positions = []
    monkeypatch.setattr(layout, 'backdrop', lambda w, h: np.zeros((h, w, 3)))
    monkeypatch.setattr(layout, 'compose_matte', lambda *args: np.zeros((2, 2, 3)))
    monkeypatch.setattr(layout, 'put', lambda frame, x, y, image: positions.append(x))
    renderer = layout.TwoPanel.__new__(layout.TwoPanel)
    renderer.ctx = SimpleNamespace(w=10, h=10, image=lambda key: Picture())
    renderer.pw = renderer.ph = 2
    renderer.py, renderer.xl, renderer.xr = 0, 1, 6
    renderer.kl, renderer.kr = 'left', 'right'
    renderer.camL = renderer.camR = Cam()
    renderer.capL, renderer.capR = Caption(), Caption()
    renderer.t0 = 4
    renderer.p = {'entrance': 'together', 'slide_delay_s': 0.1, 'slide_s': 0.85}
    renderer.render(4)
    assert positions == [1, 6]
    assert renderer.capL.alpha[-1] == renderer.capR.alpha[-1] == 1
    positions.clear()
    renderer.p.pop('entrance')
    renderer.render(4)
    assert positions[1] > 10
    assert renderer.capR.alpha[-1] == 0
    assert registry.load_bundle('gae').param_defaults('LAY-01')['entrance'] == 'slide'
