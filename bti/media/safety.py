"""The A7 safety switch for the media package.

With the environment variable `BTI_NO_REAL_MODELS=1` (set by every `conftest.py`, the end-to-end launchers and the snapshot
test runner), nothing in `bti.media` may reach the network or start `yt-dlp`: tests must never touch a real service, and twice
a test rig started a real model run by accident. The same test as the model providers use: the value must be exactly "1".

The check sits at the point where a REAL request or program starts, behind every injection point (a fake `opener`, a fake
`runner`, a fake client), so fixture-based tests are not affected:
  * `bti.media.http.open_url` and `download_file`, when no `opener` is injected (every picture source goes through them);
  * `bti.media.youcom.YouComClient._call`, when no `opener` is injected and the client has a key;
  * `bti.media.clips._run_capture`, the one place that starts `yt-dlp` (the default of the `runner` argument).
"""
from __future__ import annotations

import os

from .errors import RealModelsOff


def refuse_if_real_models_off(what: str = "") -> None:
    if os.environ.get("BTI_NO_REAL_MODELS") == "1":
        raise RealModelsOff(what)
