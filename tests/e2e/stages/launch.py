"""Runs ON the Windows server (test code only). Starts a second, throw-away instance of the app:
  - own port (default 8562, 127.0.0.1), temp COPIES of a few projects and of the library, in a new temp folder;
  - fakes: voice provider `fake` + aligner `even`, script model `mock` (models file with the mock only), draft provider `auto`
    is chosen by the page (the `agy` program is hidden from PATH, and `agy models` is never called), picks suggestions through
    `suggest.FakeProvider`, Commons and Met through the tests/media fixtures (no network), the export's engine/ffmpeg/ffprobe
    through tests/e2e/stages/fake_tools_wrap.py (a real render, even of five frames, was not chosen: the engine is ~4x slower on
    the server and the point here is the page, not the pixels), the heavy slot in-process only (never D:\\bench\\_heavy.lock).
  - stops by itself when stdin closes (the temp folder is removed), on the stdin line `stop-keep` (temp folder kept, for a
    restart with `--tmp`), or after 90 minutes.
Usage: launch.py [--port 8562] [--tmp EXISTING_TEMP_FOLDER]"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# launch.py is copied next to the repo by remote.mjs (a deploy by another agent mirrors the repo folders and would delete it)
REPO = HERE.parents[2] if (HERE.parents[2] / "bti").is_dir() else Path(os.environ.get("BTI_REPO", r"D:\code\behind-the-image"))
os.environ["BTI_REPO"] = str(REPO)
DATA = Path(r"D:\code\behind-the-image")      # the server's own folder: projects, library and books are read from it, never written
os.chdir(REPO)
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests" / "media"))

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8562)
ap.add_argument("--tmp", default=None)
ap.add_argument("--minutes", type=float, default=90)
A = ap.parse_args()
if A.port in (8550, 8560):
    raise SystemExit("port is not ours")


def say(*a):
    print(*a, flush=True)


reuse = A.tmp is not None
tmp = Path(A.tmp) if reuse else Path(tempfile.mkdtemp(prefix="bti-stages-"))
projects, lib = tmp / "projects", tmp / "library"
IGN = shutil.ignore_patterns("cache", "history")
if not reuse:
    projects.mkdir()
    for n in ("arnolfini", "arnolfini-from-books", "demo_stub"):
        if (DATA / "projects" / n).is_dir():
            shutil.copytree(DATA / "projects" / n, projects / n, ignore=IGN)
    shutil.copytree(DATA / "library", lib, ignore=IGN)
    cfg = json.loads((REPO / "config" / "voice.json").read_text(encoding="utf-8"))
    cfg["provider"] = "fake"
    cfg["aligner"] = {**cfg.get("aligner", {}), "provider": "even"}
    (tmp / "voice.json").write_text(json.dumps(cfg), encoding="utf-8")
    (tmp / "models.json").write_text(json.dumps([{"id": "mock", "label": "Mock (thử, không gọi mạng)", "provider": "mock", "model": "mock",
                                                   "key_env": None, "default": True}]), encoding="utf-8")
say("TMP=%s" % tmp)
say("PID=%d" % os.getpid())

# the environment: no keys, no .env, no agy on PATH
os.environ["BTI_NO_REAL_MODELS"] = "1"
os.environ["BTI_PROJECTS_ROOT"] = str(projects)
os.environ["BTI_ENV_FILE"] = str(tmp / "no.env")
os.environ["BTI_MODELS_FILE"] = str(tmp / "models.json")
os.environ["PYTHONUTF8"] = "1"
for k in list(os.environ):
    if k.upper() in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "YDC_API_KEY", "YOU_API_KEY"):
        del os.environ[k]
keep = []
for d in os.environ.get("PATH", "").split(os.pathsep):
    try:
        if d and any((Path(d) / (n + e)).exists() for n in ("agy",) for e in ("", ".exe", ".cmd", ".bat", ".ps1")):
            continue
    except OSError:
        pass
    keep.append(d)
os.environ["PATH"] = os.pathsep.join(keep)

from bti.library import config as libconfig  # noqa: E402
libconfig.LIB_DIR = lib
libconfig.PROJECTS_DIR = projects
libconfig.BOOKS_DIR = DATA / "books"

from bti.voice import config as vconfig  # noqa: E402
vconfig.VOICE_CONFIG = tmp / "voice.json"

from bti.script import models as script_models  # noqa: E402
script_models.agy_models = lambda refresh=False: (None, "`agy` chưa dùng được trên máy này (bản thử).")

from bti.longjob import manager, HeavySlot  # noqa: E402
from bti.longjob.config import ServerConfig  # noqa: E402
manager.configure(projects_root=projects, heavy=HeavySlot(ServerConfig(), own_markers=(str(REPO),)))

# media: Commons and Met through fixtures
from conftest import FakeNet, load, png_bytes  # noqa: E402  (tests/media/conftest.py: plain helpers)
from bti.media import api as media_api  # noqa: E402
from bti.media.sources.commons import CommonsSource  # noqa: E402
from bti.media.sources.met import MetSource  # noqa: E402
from urllib.parse import unquote_plus, urlparse, parse_qs  # noqa: E402

PNG = png_bytes(1400, 1300)


def commons_route():
    pages = load("commons_search.json")["query"]["pages"]
    full = load("commons_search.json")

    def route_for(req_url):
        q = parse_qs(urlparse(req_url).query)
        titles = q.get("titles")
        if titles:
            t = unquote_plus(titles[0])
            hit = [p for p in pages if p["title"] == t]
            return {"query": {"pages": [dict(hit[0])] if hit else []}}
        return full
    return route_for


class Net(FakeNet):
    def __call__(self, req, timeout=None):
        url = req.full_url
        if "commons.wikimedia.org/w/" in url or "commons.wikimedia.org/api" in url:
            self.urls.append(url)
            from conftest import FakeResp
            return FakeResp(json.dumps(commons_route()(url)).encode())
        return super().__call__(req, timeout)


net = Net([("upload.wikimedia.org", PNG), ("images.metmuseum.org", PNG), ("/search", {"total": 1, "objectIDs": [436535]}),
           ("/objects/", load("met_object.json"))])
media_api._SOURCES["commons"] = CommonsSource(opener=net, sleep=lambda s: None)
media_api._SOURCES["met"] = MetSource(opener=net, sleep=lambda s: None)

# slow the fake voice a little (0.35 s per sentence, cancel-aware) so that progress, cancel and a second tab can be tried
from bti.voice.providers import fake as _fakevoice  # noqa: E402
_orig_synth = _fakevoice.FakeProvider.synth


def _slow_synth(self, chunks, dest_dir, ctx, workdir=None):
    class _Ctx:
        def __getattr__(s_, n):
            return getattr(ctx, n)

        def progress(s_, f, note=""):
            end = time.time() + float(os.environ.get("BTI_FAKE_VOICE_DELAY", "0.35"))
            while time.time() < end and not ctx.cancelled():
                time.sleep(0.05)
            ctx.progress(f, note)
    return _orig_synth(self, chunks, dest_dir, _Ctx(), workdir)


_fakevoice.FakeProvider.synth = _slow_synth

# export: fake engine, ffmpeg, ffprobe
from bti.export import render  # noqa: E402
WRAP = str(HERE / "fake_tools_wrap.py")


def fake_tools(cls, settings):
    return render.Tools(ffmpeg=[sys.executable, WRAP, "ffmpeg"], ffprobe=[sys.executable, WRAP, "ffprobe"],
                        engine=lambda project_dir, spec, out, st: [sys.executable, WRAP, "engine", "render", str(project_dir), "--t0", "%.6f" % spec.t0,
                                                                   "--t1", "%.6f" % spec.t1, "--fps", str(spec.fps), "-o", str(out)],
                        cwd=tmp, env=dict(os.environ, FAKE_LOG=str(tmp / "fake_tools.log"), FAKE_ENGINE_DELAY="0.6"))


render.Tools.from_settings = classmethod(fake_tools)

from bti.editor.app import create_app  # noqa: E402
from bti.picks import suggest  # noqa: E402

CAND = {"source": "commons", "source_id": "File:Arnolfini small.png", "title": "Arnolfini small", "thumb_url": "https://upload.wikimedia.org/thumb/s.png/320px-s.png",
        "page_url": "", "width": 2000, "height": 2000, "mime": "image/png", "author": "someone", "licence": "PD", "licence_ok": True, "licence_reason": "", "flag": None}
SUG = [{"what": "A mirror in another painting", "kind": "artwork", "why": "the same trick of a mirror", "search_terms": ["mirror", "painting"],
        "source_urls": ["https://en.wikipedia.org/wiki/Mirror"], "candidates": [CAND]}]

app = create_app(projects_root=projects)
app.state.picks_provider = suggest.FakeProvider(default=SUG)

import uvicorn  # noqa: E402
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=A.port, log_level="warning", timeout_graceful_shutdown=3))
keep_tmp = [False]


def watch_stdin():
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            if line.strip() == "stop-keep":
                keep_tmp[0] = True
                break
    except Exception:  # noqa: BLE001
        pass
    server.should_exit = True


def timeout():
    time.sleep(A.minutes * 60)
    server.should_exit = True


threading.Thread(target=watch_stdin, daemon=True).start()
threading.Thread(target=timeout, daemon=True).start()
threading.Thread(target=lambda: (time.sleep(2), say("READY port=%d" % A.port)), daemon=True).start()
try:
    server.run()
finally:
    try:
        manager.shutdown() if hasattr(manager, "shutdown") else None
    except Exception:  # noqa: BLE001
        pass
    if not keep_tmp[0]:
        for i in range(10):
            try:
                shutil.rmtree(tmp)
                break
            except OSError:
                time.sleep(1)
    say("BYE kept=%s" % keep_tmp[0])
    os._exit(0)
