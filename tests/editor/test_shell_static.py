"""The app shell is served at /, and the old pages are small stubs that forward into the app."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti.editor.app import create_app  # noqa: E402


def client(tmp_path):
    return TestClient(create_app(projects_root=tmp_path, engine_module=None, media_module=None))


def test_root_is_the_single_page_app(tmp_path):
    with client(tmp_path) as c:
        t = c.get("/").text
        assert 'id="stepper"' in t and 'id="view"' in t and 'id="project-pick"' in t and "js/app.js" in t
        assert c.get("/js/app.js").status_code == 200 and c.get("/css/theme.css").status_code == 200
        for gone in ("/css/app.css", "/js/main.js", "/js/script.js", "/js/library.js"):
            assert c.get(gone).status_code == 404       # the duplicated copies are removed


def test_old_addresses_forward_into_the_app(tmp_path):
    with client(tmp_path) as c:
        for page in ("/library.html", "/script.html"):
            t = c.get(page).text
            assert "legacyTarget" in t and "location.replace" in t and 'id="view"' not in t


def test_every_view_module_is_served(tmp_path):
    with client(tmp_path) as c:
        for m in ("home", "library", "artwork", "script", "placeholder", "storyboard"):
            assert c.get(f"/js/views/{m}.js").status_code == 200
