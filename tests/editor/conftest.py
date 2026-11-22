import os
import shutil
import sys
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
from editor_helpers import PID, REPO, editable  # noqa: E402,F401

sys.path.insert(0, str(REPO))

from bti.editor.app import create_app  # noqa: E402


@pytest.fixture()
def root(tmp_path):
    shutil.copytree(REPO / "projects" / PID, tmp_path / PID, ignore=shutil.ignore_patterns("cache", "history"))
    return tmp_path


@pytest.fixture()
def client(root):
    app = create_app(projects_root=root, engine_module=None, media_module=None)  # force stubs
    with TestClient(app) as c:
        c.root = root
        yield c


@pytest.fixture()
def state(client):
    return client.get(f"/api/projects/{PID}").json()


@pytest.fixture(autouse=True)
def _no_real_viewer_review(monkeypatch):
    from bti.draft import review
    def forbidden(*args, **kwargs):
        pytest.fail("viewer review must use a fake in tests")
    monkeypatch.setattr(review, "_review_round", forbidden)
