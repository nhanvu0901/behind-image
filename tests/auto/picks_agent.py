"""The fake pictures agent of tests/picks (`auto_helpers.py` there), loaded under another name: this folder has an `auto_helpers.py` of its own (the fake pipeline of the
automatic run), and two modules of one name cannot both be imported. Nothing here calls a model, a program or a network."""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("picks_auto_helpers", REPO / "tests" / "picks" / "auto_helpers.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["picks_auto_helpers"] = _mod
_spec.loader.exec_module(_mod)

FakeAgent = _mod.FakeAgent
PNG = _mod.PNG
fake_book_thumb = _mod.fake_book_thumb
fake_thumb = _mod.fake_thumb
install_agent = _mod.install_agent
install_sources = _mod.install_sources
