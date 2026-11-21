import copy
import os
import sys
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
REPO = Path(__file__).resolve().parents[2]
for _p in (REPO, REPO / "tests" / "picks", REPO / "tests" / "script"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ops_helpers import PD_ID, PID, make_project  # noqa: E402,F401
from picks_helpers import FakeNet, load_fix, png_bytes  # noqa: E402

engine_api = pytest.importorskip("bti.engine.api")

from bti.editor.app import create_app  # noqa: E402
from bti.media import api as media_api  # noqa: E402
from bti.media.sources.bookpage import BookPageSource  # noqa: E402
from bti.media.sources.commons import CommonsSource  # noqa: E402
from bti.media.sources.met import MetSource  # noqa: E402
from bti.media.sources.osm import OsmSource  # noqa: E402
from bti.script import env  # noqa: E402

PAGES = {p["pageid"]: p for p in load_fix("commons_search.json")["query"]["pages"]}


@pytest.fixture(autouse=True)
def _never_live(monkeypatch):
    """No test can reach the paid provider, and no source's "wait N seconds" is inherited from another test."""
    from bti.picks import suggest
    from bti.media import http
    monkeypatch.setattr(suggest, "live_allowed", lambda: False)
    monkeypatch.setattr(suggest, "_longjob", None)
    http.reset_cooldowns()
    yield
    http.reset_cooldowns()


@pytest.fixture
def sources(monkeypatch):
    """Fake picture sources (the fakes of the picks tests): nothing here reaches a network."""
    one = lambda n: {"query": {"pages": [copy.deepcopy(PAGES[n])]}}                                      # noqa: E731
    net = FakeNet([("Google+Art+Project", one(2)), ("Arnolfini+nc.jpg", one(3)), ("Arnolfini+small.png", one(1)),
                   ("Arnolfini+nolicence", one(5)),
                   # CHANGED (join, as mediafix3 did in tests/picks): the 4386 x 6000 Arnolfini is downloaded as the rendition its API answer names
                   ("wikipedia/commons/a/a0", png_bytes(1300, 1250)), ("upload.wikimedia.org/thumb/a.jpg", png_bytes(1300, 1250)),
                   ("wikipedia/commons/s/s0", png_bytes(800, 600)),
                   ("x/nc.jpg", png_bytes(1300, 1250)), ("x/nl.jpg", png_bytes(1300, 1250)),
                   ("commons.wikimedia.org", load_fix("commons_search.json"))])
    monkeypatch.setitem(media_api._SOURCES, "commons", CommonsSource(opener=net, sleep=lambda s: None))
    met = FakeNet([("/search", {"total": 1, "objectIDs": [436535]}), ("/objects/436535", load_fix("met_object.json")),
                   ("images.metmuseum.org", png_bytes(1500, 1300))])
    monkeypatch.setitem(media_api._SOURCES, "met", MetSource(opener=met, sleep=lambda s: None))
    monkeypatch.setitem(media_api._SOURCES, "osm", OsmSource(opener=FakeNet([("nominatim", [])]), sleep=lambda s: None))
    monkeypatch.setattr(env, "has_key", lambda name: False)
    monkeypatch.setitem(media_api._SOURCES, "book", BookPageSource(renderer=lambda b, k, r, dest: dest.write_bytes(png_bytes(1358, 1600))))
    return net, met


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "projects"
    r.mkdir()
    return r


@pytest.fixture
def proj(root):
    return make_project(root)


@pytest.fixture
def client(root, proj, sources):
    """The app with the REAL engine (the batches use its validation and its defaults), on the fixture project."""
    app = create_app(projects_root=root, engine_module=engine_api, media_module=None)
    with TestClient(app) as c:
        c.pid, c.pdir, c.root = PID, proj, root
        c.sb = f"/api/projects/{PID}/storyboard/ops"
        c.pk = f"/api/projects/{PID}/picks/ops"
        yield c
