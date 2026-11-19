"""After the cleaning the project still opens, previews, edits and exports again: on the operations' fixture project, with the real engine and the real routes; the export itself is the
real export job with the fake tools of tests/export (nothing is rendered)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
for p in ("ops", "picks", "script"):
    sys.path.insert(0, str(REPO / "tests" / p))

engine_api = pytest.importorskip("bti.engine.api")

from bti.editor.app import create_app  # noqa: E402
from bti.ops import registry  # noqa: E402
from bti.output import facts as F, hooks  # noqa: E402
from ops_helpers import PID as OPS, make_project  # noqa: E402
from output_helpers import export_world  # noqa: E402


def test_after_cleaning_the_project_opens_previews_edits_and_exports_again(tmp_path, monkeypatch):
    root, out = tmp_path / "projects", tmp_path / "output"
    root.mkdir()
    d = make_project(root)
    monkeypatch.setattr(F, "voice_done", lambda pdir, pid: True)
    holder = SimpleNamespace(root=root, d=d, out=out, duration=90.0)
    app = create_app(projects_root=root, output_root=out, engine_module=engine_api, media_module=None)
    P = "/api/projects/" + OPS
    with TestClient(app) as c:
        run, settings, _ = export_world(holder, monkeypatch, real_timeline=True)
        assert c.post(P + "/approve", json={"rev": c.get(P).json()["rev"]}).status_code == 200
        job = run.start(d, settings=settings)
        assert job["state"] == "done", job.get("error")
        st = json.loads((out / OPS / "state.json").read_text(encoding="utf-8"))
        assert st["clean"]["done"] and st["clean"]["freed_bytes"] > 0 and (out / OPS / "final.mp4").exists()
        assert not (d / "cache" / "export").exists()

        # it opens
        assert c.get(P).status_code == 200 and c.get(P + "/state").status_code == 200 and c.get(P + "/export").status_code == 200
        assert c.get(P + "/changes").status_code == 200 and c.get(P + "/longjobs").status_code == 200
        # it previews: the frame is drawn again and the cache is made again
        r = c.get(P + "/frame?t=3&width=320")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"
        assert any((d / "cache" / "frames").glob("*.jpg"))
        # it edits: a typed operation, one batch in the change log; the approval is dropped, so the export asks for a new one
        first = next(iter(registry.defs("storyboard").values()))
        rev = c.get(P).json()["rev"]
        r = c.post(P + "/storyboard/ops", json={"base_rev": rev, "actor": "agent:test-model", "ops": [first.example]})
        assert r.status_code == 200, r.text
        assert hooks.flush(30)
        parts = json.loads((out / OPS / "state.json").read_text(encoding="utf-8"))["parts"]
        assert parts["storyboard"]["out_of_date"] and parts["export"]["out_of_date"], "the edit marks the published parts as old"
        from bti.export.errors import ExportError
        with pytest.raises(ExportError) as e:
            run.start(d, settings=settings)
        assert e.value.code == "approval_stale"
        # it exports again
        assert c.post(P + "/approve", json={"rev": c.get(P).json()["rev"]}).status_code == 200
        job = run.start(d, settings=settings)
        assert job["state"] == "done", job.get("error")
        st = json.loads((out / OPS / "state.json").read_text(encoding="utf-8"))
        assert not any(v["out_of_date"] for v in st["parts"].values()) and st["clean"]["done"]
        from bti.editor.common import compute_rev
        assert st["parts"]["storyboard"]["rev"] == compute_rev(json.loads((d / "storyboard.json").read_text(encoding="utf-8")))
        assert (out / OPS / "final.mp4").read_bytes() == (d / "export" / (OPS + ".mp4")).read_bytes()
