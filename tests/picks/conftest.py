import os
import sys
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture(autouse=True)
def _never_live(monkeypatch):
    """No test can reach the paid provider: the config switch is off for every test, unless a test builds its own fake."""
    from bti.picks import suggest
    monkeypatch.setattr(suggest, "live_allowed", lambda: False)
    monkeypatch.setattr(suggest, "_longjob", None)
    yield


@pytest.fixture(autouse=True)
def _no_cooldown_between_tests():
    """A source's "wait N seconds" is remembered per host for the life of the process: no test may inherit another's."""
    from bti.media import http
    http.reset_cooldowns()
    yield
    http.reset_cooldowns()


@pytest.fixture
def root(tmp_path):
    return tmp_path / "projects"


@pytest.fixture
def proj(root):
    from picks_helpers import make_project
    root.mkdir()
    return make_project(root)
