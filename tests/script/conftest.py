import json
import os
import shutil
import sys
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

REAL = REPO / "projects" / "arnolfini-from-books"

from bti.script import env as env_mod, models as models_mod  # noqa: E402
from bti.script.providers import mock as mock_mod, set_transport  # noqa: E402
from script_helpers import make_project  # noqa: E402


@pytest.fixture(autouse=True)
def _isolation(tmp_path, monkeypatch):
    """No real .env, no real keys, no network, default models file."""
    monkeypatch.setenv("BTI_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setenv("BTI_AGY_BIN", "")                      # the real agy is never reached from tests
    models_mod.reset_cache()
    for k in ("GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    env_mod._cache.clear()
    set_transport(None)
    mock_mod.CALLS.clear()
    yield
    set_transport(None)


@pytest.fixture()
def tproj(tmp_path):
    return make_project(tmp_path)


@pytest.fixture()
def real_project(tmp_path):
    if not (REAL / "project.json").is_file():
        pytest.skip("projects/arnolfini-from-books is missing")
    shutil.copytree(REAL, tmp_path / "arn", ignore=shutil.ignore_patterns("script", "cache", "history"))
    return tmp_path / "arn"
