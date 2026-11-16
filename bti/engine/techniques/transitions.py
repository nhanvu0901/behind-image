"""Transitions between two shots (kind `transition`), used through a shot's `transition_in`.

  X-TR-01 / TR-04   hard cut (dur 0; the channel default, normally written as `transition_in: null`)
  TR-01             cross dissolve over dur
  TR-02             the incoming shot slides in over the outgoing one from an edge (ease: out_cubic by default)
During the overlap the Scene renders both shots; `blend(f_out, f_in, p)` combines them, p = 0..1.
"""
from __future__ import annotations

from ..base import TransitionRenderer
from ..registry import technique
from ..vfx import EASE, blend, ease


@technique("X-TR-01", "transition")
@technique("TR-04", "transition")
class HardCut(TransitionRenderer):
    def blend(self, f_out, f_in, p):
        return f_in


@technique("TR-01", "transition")
class Dissolve(TransitionRenderer):
    def blend(self, f_out, f_in, p):
        return blend(f_out, f_in, min(max(p, 0.0), 1.0))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return {}


@technique("TR-02", "transition")
class SlideIn(TransitionRenderer):
    def blend(self, f_out, f_in, p):
        h, w = f_in.shape[:2]
        e = ease(self.p["easing"], p)
        out = f_out.copy()
        edge = self.p["from_edge"]
        if edge == "right":
            x = int(round(w * (1 - e)))
            out[:, x:] = f_in[:, :w - x]
        elif edge == "left":
            x = int(round(w * (1 - e)))
            out[:, :w - x] = f_in[:, x:]
        elif edge == "bottom":
            y = int(round(h * (1 - e)))
            out[y:, :] = f_in[:h - y, :]
        else:
            y = int(round(h * (1 - e)))
            out[:h - y, :] = f_in[y:, :]
        return out
