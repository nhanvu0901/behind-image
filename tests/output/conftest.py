"""Fixtures of the output-folder tests. Every test runs on a temporary data root (`projects/` and `output/` side by side), with private settings files, no model, no network, no
render. The voice's state is stood in for by a flag of the fixture project (the voice stage's own tests cover the real one)."""
import json
import os
import sys
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (REPO, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from bti.output import facts as F  # noqa: E402
from bti.output import hooks  # noqa: E402
from output_helpers import Project  # noqa: E402


@pytest.fixture(autouse=True)
def _isolation(tmp_path, monkeypatch):
    """Private settings and agent files, no real .env, writes at once (no one-second gap between two background writes)."""
    monkeypatch.setenv("BTI_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setenv("BTI_AGY_BIN", "")
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    run = tmp_path / "run"
    run.mkdir()
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(run / "settings.json"))
    monkeypatch.delenv("BTI_OUTPUT_ROOT", raising=False)
    monkeypatch.setattr(hooks, "MIN_GAP", 0.0)
    hooks._ROOTS.clear()
    hooks._ERRORS.clear()
    yield
    hooks.flush(30)
    hooks._ROOTS.clear()
    hooks._ERRORS.clear()


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    p = Project(tmp_path)
    monkeypatch.setattr(F, "voice_done", lambda pdir, pid: p.voice_ok)
    return p


@pytest.fixture()
def set_clean(tmp_path):
    """Switch the cleaning on or off the way the settings route does."""
    def go(flag: bool):
        from bti import settings as S
        S.set_output_clean(flag)
    return go
