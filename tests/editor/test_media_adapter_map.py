"""mediafix3: the older import path of the storyboard's picture tab (`bti.editor.media_adapter`) answers a map that has no known place
with 422 and the code `map_place_unknown` (the page's sentence is in errmsg.js), not a map of somewhere else. Fakes only."""
from __future__ import annotations

import types

import pytest
from fastapi.testclient import TestClient

from bti.editor.app import create_app
from bti.editor.common import ApiError
from bti.editor.media_adapter import _translate
from bti.media.errors import MapPlaceUnknown
from editor_helpers import PID

P = f"/api/projects/{PID}"


def test_a_map_without_a_place_is_a_422_with_its_code():
    e = _translate(MapPlaceUnknown("source id '297322:12' has no coordinates"))
    assert isinstance(e, ApiError) and e.status == 422
    assert e.extra["code"] == "map_place_unknown"


@pytest.fixture()
def client(root):
    def imp(d, s, i, **kw):
        raise MapPlaceUnknown("source id %r has no coordinates" % i)
    mod = types.SimpleNamespace(search=lambda *a, **k: [], import_candidate=imp, add_upload=lambda *a, **k: None)
    with TestClient(create_app(root, engine_module=None, media_module=mod)) as c:
        yield c


def test_the_import_route_answers_422_with_the_code(client):
    r = client.post(f"{P}/assets/import", json={"source": "osm", "source_id": "297322:12"})
    assert r.status_code == 422 and r.json()["code"] == "map_place_unknown"
