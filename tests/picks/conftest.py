import sys
from pathlib import Path

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


@pytest.fixture
def root(tmp_path):
    return tmp_path / "projects"


@pytest.fixture
def proj(root):
    from picks_helpers import make_project
    root.mkdir()
    return make_project(root)
