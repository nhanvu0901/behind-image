"""Fixtures for the voice tests. Nothing here needs a model, a GPU or the network; the tests marked `server` run only on the
Windows server, under the heavy slot, and speak two real sentences."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti.script import store  # noqa: E402
from bti.voice.config import load_voice_config  # noqa: E402

FFMPEG = shutil.which("ffmpeg") is not None


def pytest_configure(config):
    config.addinivalue_line("markers", "server: runs only on the Windows server (real voice, real aligner), under the heavy slot")


def pytest_collection_modifyitems(config, items):
    expr = (getattr(config.option, "markexpr", "") or "").replace(" ", "")
    wanted = "server" in expr and "notserver" not in expr
    if wanted:
        return
    skip = pytest.mark.skip(reason="server-marked test: run it with -m server on the Windows server")
    for it in items:
        if "server" in it.keywords:
            it.add_marker(skip)


needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg is not installed")

TEXTS = {
    "c1": [("b0001", "In 1434, Jan van Eyck painted a portrait. It is on show in London."),
           ("b0002", "A mirror hangs behind the couple, and it shows two more people in the room.")],
    "c2": [("b0003", "Henry VIII never saw it. Nobody wrote down who owned it before 1600, which is odd."),
           ("b0004", "Look at the chandelier.")],
}


def make_narration(texts=None, card_second=True, role_first="cold_open") -> store.Narration:
    texts = texts or TEXTS
    chs = []
    for i, (cid, beats) in enumerate(texts.items()):
        chs.append(store.NChapter(cid, role_first if i == 0 else "chapter", f"Chapter {cid}", card_second and i == 1,
                                  [store.Beat(bid, t) for bid, t in beats]))
    n = store.Narration(project="p", title="T", chapters=chs)
    n.counters = {"beat": 10}
    return n


def write_project(root: Path, pid: str = "vtest", texts=None, approve: bool = True) -> Path:
    d = root / pid
    (d / "script").mkdir(parents=True)
    (d / "project.json").write_text('{"title": "t"}', encoding="utf-8")
    o = store.Outline(thesis="x")
    orev = store.save_outline(d, o)
    n = make_narration(texts)
    rev = store.save_narration(d, n)
    if approve:
        store.approve(d, "outline", orev)
        store.approve(d, "narration", rev)
    return d


@pytest.fixture()
def cfg():
    c = load_voice_config(override={"provider": "fake", "aligner": {"provider": "even"}, "part_chars": 120})
    return c


@pytest.fixture()
def proot(tmp_path):
    return tmp_path


@pytest.fixture()
def project(tmp_path):
    return write_project(tmp_path)


class FakeCtx:
    """The part of the long-job context a voice part uses, with scripted `run_process` results."""

    def __init__(self, workdir: Path, cancel_after: int | None = None):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.progress_log: list = []
        self.logs: list[str] = []
        self.processes: list[list[str]] = []
        self.on_process = None
        self._cancel = False

    def progress(self, f, note=""):
        self.progress_log.append((f, note))

    def log(self, t):
        self.logs.append(t)

    def cancelled(self):
        return self._cancel

    def cancel(self):
        self._cancel = True

    def run_process(self, cmd, cwd=None, env=None, on_line=None):
        self.processes.append(list(cmd))
        if self.on_process:
            return self.on_process(cmd, on_line)
        return 0
