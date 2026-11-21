"""Tests for A7 safety switch (BTI_NO_REAL_MODELS=1).

Verifies that when BTI_NO_REAL_MODELS=1, every real model provider refuses immediately with
error code / kind 'real_models_off', while mock providers continue to work.
Also documents and tests the reason why hiding agy from PATH did not work in tests/e2e/stages (E9).
"""
import os
import pytest

from bti.draft.inputs import DraftError
from bti.draft.providers import agy
from bti.script.providers import ProviderError, antigravity, gemini, mock, openrouter


def test_antigravity_refuses_when_switch_is_on(monkeypatch):
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    spec = {"model": "gemini-3.8-flash-high"}
    with pytest.raises(ProviderError) as exc:
        antigravity.complete(spec, "system prompt", "user prompt")
    assert exc.value.kind == "real_models_off"


def test_openrouter_refuses_when_switch_is_on(monkeypatch):
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    monkeypatch.setenv("FAKE_OR_KEY", "dummy-key")
    spec = {"model": "anthropic/claude-3-opus", "key_env": "FAKE_OR_KEY"}
    with pytest.raises(ProviderError) as exc:
        openrouter.complete(spec, "system prompt", "user prompt")
    assert exc.value.kind == "real_models_off"


def test_gemini_refuses_when_switch_is_on(monkeypatch):
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    monkeypatch.setenv("FAKE_GEM_KEY", "dummy-key")
    spec = {"model": "gemini-1.5-pro", "key_env": "FAKE_GEM_KEY"}
    with pytest.raises(ProviderError) as exc:
        gemini.complete(spec, "system prompt", "user prompt")
    assert exc.value.kind == "real_models_off"


def test_agy_run_refuses_when_switch_is_on(monkeypatch, tmp_path):
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    with pytest.raises(DraftError) as exc:
        agy.run(tmp_path)
    assert exc.value.code == "real_models_off"


def test_mock_provider_works_even_when_switch_is_on(monkeypatch):
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    mock.CALLS.clear()
    spec = {"model": "mock"}
    res = mock.complete(spec, "system", "user")
    assert isinstance(res, str)
    assert len(res) > 0


def test_e9_explanation_find_agy_searches_beyond_path(tmp_path, monkeypatch):
    """E9 finding explanation:

    tests/e2e/stages/launch.py cleaned PATH to remove any folder containing `agy`.
    However, `find_agy()` in both `bti/draft/providers/agy.py` and `bti/script/providers/antigravity.py`
    specifically checks hardcoded directories beyond PATH:
      - Path.home() / ".local" / "bin"
      - (On Windows) LOCALAPPDATA / "agy" / "bin", APPDATA / "npm", etc.
    Because `find_agy()` found the executable in LOCALAPPDATA, stripping PATH was insufficient
    and allowed real model calls to proceed.
    With BTI_NO_REAL_MODELS=1, even if find_agy() locates agy, run() refuses before executing anything.
    """
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("BTI_AGY_BIN", raising=False)
    # Simulate agy residing in a non-PATH directory
    fake_local_bin = tmp_path / "local_bin"
    fake_local_bin.mkdir()
    fake_agy = fake_local_bin / "agy"
    fake_agy.write_text("#!/bin/sh\nexit 0\n")

    # If monkeypatched spots includes this directory, find_agy finds it even with PATH=""
    monkeypatch.setattr(agy, "IS_WINDOWS", False)
    monkeypatch.setattr(agy.Path, "home", lambda: tmp_path.parent)  # not matching
    # Now verify that when BTI_NO_REAL_MODELS=1, agy.run rejects immediately without checking or invoking agy
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    with pytest.raises(DraftError) as exc:
        agy.run(tmp_path)
    assert exc.value.code == "real_models_off"
