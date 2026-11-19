"""Errors say how to fix them: every error body has `code`, `fix` and `retry`; the table has a hint for every code in the source."""
import ast
import json
import re
import shutil
from pathlib import Path

import pytest

from bti.editor import hints
from state_helpers import DEMO_SRC, make_book_project

REPO = Path(__file__).resolve().parents[2]
EDITOR = REPO / "bti" / "editor"
# the classes whose first positional argument (or, for PicksError, the third) is the code
POSITIONAL = {"VoiceError": 0, "ExportError": 0, "DraftError": 0, "AgentError": 0, "SettingsError": 0, "PicksError": 2}
# editor files this build may not change: their raises carry no code, the handlers give them one by status (see test below)
NOT_EDITED = {"common.py", "frames.py", "audio.py", "media_adapter.py", "engine_stub.py", "engine_adapter.py"}
ERROR_KEYS = {"detail", "code", "fix", "retry"}


def _source_files():
    return [f for f in sorted((REPO / "bti").rglob("*.py")) if "static" not in f.parts]


def _call_name(n: ast.Call):
    return n.func.id if isinstance(n.func, ast.Name) else n.func.attr if isinstance(n.func, ast.Attribute) else None


def code_literals() -> dict[str, str]:
    """Every code the source names as a literal: `code="x"`, and the code argument of the error classes of the stage packages."""
    found: dict[str, str] = {}
    for f in _source_files():
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            for kw in n.keywords:
                if kw.arg == "code" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    found.setdefault(kw.value.value, f"{f.relative_to(REPO)}:{n.lineno}")
            i = POSITIONAL.get(_call_name(n))
            if i is not None and len(n.args) > i and isinstance(n.args[i], ast.Constant) and isinstance(n.args[i].value, str):
                found.setdefault(n.args[i].value, f"{f.relative_to(REPO)}:{n.lineno}")
            if _call_name(n) == "_err" and len(n.args) == 3 and isinstance(n.args[2], ast.Constant):      # bti/longjob/api.py
                found.setdefault(n.args[2].value, f"{f.relative_to(REPO)}:{n.lineno}")
    return found


# --------------------------------------------------------------------------------------------------- the scan
def test_every_code_in_the_source_has_a_hint():
    found = code_literals()
    assert len(found) > 100
    missing = {c: where for c, where in found.items() if c not in hints.HINTS}
    assert not missing, "codes without a hint in bti/editor/hints.py: %s" % missing


def test_the_codes_made_at_run_time_have_a_hint():
    from bti.draft import run as draft_run
    from bti.export import errors as export_errors
    from bti.picks import suggest
    from bti.voice import errors as voice_errors
    made = set(draft_run.VI) | set(export_errors.VI) | set(voice_errors.CODES) | set(suggest._KIND_CODE.values()) | set(hints.EXTRA_CODES)
    made |= {hints.data_error_code(w) for w in ("storyboard", "timing", "style", "data", None)}
    made |= {hints.fallback_code(s) for s in (400, 401, 403, 404, 405, 409, 410, 413, 415, 416, 422, 500, 502, 503, 504, 418, 599)}
    made |= {w + "_missing" for w in ("timing", "picks", "storyboard")} | {w + "_corrupt" for w in ("timing", "picks", "storyboard")}
    made |= {"outline_missing", "outline_not_approved", "outline_stale", "image_empty", "image_truncated", "image_unreadable",
             "not_approved", "approval_stale", "longjob_not_found", "project_not_found", "longjob_bad_kind", "options_error",
             "picks_error", "request_invalid", "route_not_found", "document_corrupt", "library_data_corrupt", "bad_text_character",
             "internal_error", "storyboard_corrupt"}
    assert not (made - set(hints.HINTS)), sorted(made - set(hints.HINTS))


def test_no_editor_raise_of_ApiError_is_without_a_code():
    """Every `ApiError(` of the files this build edits has a code (a `**` expansion may carry it); the raises of the helper modules
    it may not edit are the only ones left, and the handlers give those a code by status."""
    bare, helpers = [], 0
    for f in sorted(EDITOR.glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and _call_name(n) == "ApiError":
                if any(k.arg == "code" or k.arg is None for k in n.keywords):
                    continue
                if f.name in NOT_EDITED:
                    helpers += 1
                else:
                    bare.append(f"{f.name}:{n.lineno}")
    assert not bare, "ApiError without code=: %s" % bare
    assert helpers > 0


def test_every_hint_is_one_imperative_english_sentence_with_a_retry_word():
    for code, h in hints.HINTS.items():
        assert re.fullmatch(r"[a-z][a-z0-9_]*", code), code
        assert h["retry"] in ("no", "after_fix", "later"), code
        fix = h["fix"]
        assert fix[0].isupper() and fix.endswith(".") and "\n" not in fix and 15 <= len(fix) <= 330, (code, fix)
        assert not re.search(r"[À-ỹ]", fix), code            # English: the owner's Vietnamese lives in errmsg.js


def test_the_routes_a_fix_names_exist():
    from bti.editor.app import create_app
    from state_helpers import route_ok
    import tempfile
    app = create_app(projects_root=tempfile.mkdtemp(), engine_module=None, media_module=None)
    bad, named = [], 0
    for code, h in hints.HINTS.items():
        for m in re.finditer(r"\b(GET|POST|PUT|DELETE) (/api/[A-Za-z0-9_/{}.-]+)", h["fix"]):
            path = re.sub(r"\{[^}]*\}", "x", m.group(2).rstrip(".,"))
            named += 1
            if not route_ok(app, m.group(1), path):
                bad.append((code, m.group(1), m.group(2)))
    assert named > 60 and not bad, bad


def test_complete_keeps_what_is_there_and_adds_what_is_missing():
    own = hints.complete({"detail": "x", "code": "stale", "fix": "Do it my way.", "retry": "later", "rev": "abc"}, 409)
    assert own["fix"] == "Do it my way." and own["retry"] == "later" and own["current_rev"] == "abc" and own["rev"] == "abc"
    plain = hints.complete({"detail": "boom"}, 404)
    assert plain["code"] == "not_found" and plain["retry"] == "no" and plain["fix"] and plain["detail"] == "boom"
    unknown = hints.complete({"detail": "x", "code": "a_code_nobody_knows"}, 503)
    assert unknown["retry"] == "later" and unknown["code"] == "a_code_nobody_knows"
    assert hints.complete({"detail": "x", "code": "a_code_nobody_knows"}, 422)["retry"] == "after_fix"
    assert hints.complete({"detail": "width must be an integer"}, 422)["field"] == "width"
    assert hints.complete({"detail": "base_rev (string) is required"}, 422)["field"] == "base_rev"
    assert "field" not in hints.complete({"detail": "the storyboard is wrong"}, 422)
    assert hints.complete({"detail": "x", "code": "stale_revision", "rev": "r1"}, 409)["current_rev"] == "r1"
    pid = hints.complete({"detail": "x", "code": "storyboard_corrupt"}, 409, pid="demo")
    assert "/api/projects/demo/storyboard/restore" in pid["fix"] and "{pid}" not in pid["fix"]
    assert "{pid}" in hints.complete({"detail": "x", "code": "storyboard_corrupt"}, 409)["fix"]


# ------------------------------------------------------------------------------------- one refused call per router
@pytest.fixture()
def imp(client, root):
    shutil.copytree(DEMO_SRC, root / "imp", ignore=shutil.ignore_patterns("cache", "history"))
    return client


def refused(r, status, code, retry=None):
    assert r.status_code == status, (r.status_code, r.text[:300])
    b = r.json()
    assert ERROR_KEYS <= set(b), b
    assert b["code"] == code, b
    assert isinstance(b["fix"], str) and b["fix"].endswith(".") and b["retry"] in ("no", "after_fix", "later"), b
    if retry:
        assert b["retry"] == retry
    return b


def test_app_a_stale_storyboard_revision_carries_the_current_one(imp):
    cur = imp.get("/api/projects/imp").json()
    sb = cur["storyboard"]
    b = refused(imp.put("/api/projects/imp/storyboard", json={"storyboard": sb, "base_rev": "0" * 64}), 409, "stale_revision", "after_fix")
    assert b["current_rev"] == cur["rev"] == b["rev"] and b["detail"] == "base_rev does not match the saved revision"
    assert "base_rev" in b["fix"]
    b = refused(imp.post("/api/projects/imp/approve", json={"rev": "nope"}), 409, "stale_revision")
    assert b["current_rev"] == cur["rev"]


def test_app_a_field_that_is_wrong_is_named(imp):
    b = refused(imp.put("/api/projects/imp/storyboard", json={"storyboard": {}}), 422, "base_rev_required")
    assert b["field"] == "base_rev" and b["detail"] == "base_rev (string) is required"
    b = refused(imp.post("/api/projects/imp/preview", json={"t0": 5, "t1": 1}), 422, "field_invalid")
    assert b["field"] == "t1"
    b = refused(imp.post("/api/projects/imp/assets/import", json={"source": "commons"}), 422, "field_required")
    assert b["field"] == "source_id"


def test_app_a_corrupt_storyboard_keeps_its_old_keys_and_names_the_restore_call(imp, root):
    d = root / "imp"
    (d / "history").mkdir()
    shutil.copy(d / "storyboard.json", d / "history" / "20261118-100000.json")
    (d / "storyboard.json").write_text("{ nope", encoding="utf-8")
    b = refused(imp.get("/api/projects/imp"), 409, "storyboard_corrupt", "after_fix")
    assert b["corrupt"] is True and b["restore_from"] == "20261118-100000.json" and "storyboard.json is corrupt" in b["detail"]
    assert "POST /api/projects/imp/storyboard/restore" in b["fix"]
    shutil.rmtree(d / "history")
    b = refused(imp.get("/api/projects/imp"), 409, "storyboard_corrupt")
    assert b["restore_from"] is None and "draft/start" in b["fix"] and "storyboard/restore" not in b["fix"]      # an error that carries its own fix keeps it


def test_app_unknown_project_and_unknown_route(imp):
    refused(imp.get("/api/projects/nope"), 404, "project_not_found", "no")
    refused(imp.get("/api/no/such/route"), 404, "route_not_found", "no")
    refused(imp.post("/api/no/such/route", json={}), 405, "method_not_allowed")        # a path the static catch-all answers for GET
    r = imp.delete("/api/health")
    refused(r, 405, "method_not_allowed")
    assert "allow" in {k.lower() for k in r.headers}


def test_app_a_request_the_framework_refuses_lists_its_fields(imp):
    r = imp.put("/api/projects/imp/storyboard", json=[1, 2])
    b = refused(r, 422, "request_invalid", "after_fix")
    assert isinstance(b["detail"], list) and b["detail"][0]["type"] and b["fields"][0]["path"].startswith("body")


def test_app_a_value_the_helpers_refuse_gets_a_code_and_a_field_by_status(imp):
    b = refused(imp.post("/api/projects/imp/frame", json={"t": "abc", "storyboard": {}}), 422, "field_invalid", "after_fix")
    assert b["field"] == "t" and b["detail"] == "t must be a number"


def test_script_stale_outline_and_a_missing_outline(client, root):
    make_book_project(root)
    P = "/api/projects/arn"
    refused(client.post(P + "/outline/approve", json={"rev": "x"}), 404, "no_outline", "after_fix")
    client.post(P + "/outline/import", json={"text": "nope"})                       # refused: nothing to compare with yet
    r = client.put(P + "/outline", json={"outline": {"schema": "x"}, "base_rev": "x"})
    assert r.status_code == 422 and r.json()["code"] == "document_invalid"
    refused(client.get(P + "/prompt?phase=zzz"), 422, "field_invalid")


def test_script_a_stale_narration_revision_carries_the_current_one(client, root, monkeypatch):
    from state_helpers import build
    make_book_project(root)
    build("narration_approved", client, monkeypatch)
    P = "/api/projects/arn"
    n = client.get(P + "/narration").json()
    b = refused(client.put(P + "/narration", json={"narration": n["narration"], "base_rev": "old"}), 409, "stale_revision")
    assert b["current_rev"] == n["rev"] and b["rev"] == n["rev"]
    b = refused(client.post(P + "/narration/ops", json={"base_rev": "old", "ops": []}), 409, "stale_revision")
    assert b["current_rev"] == n["rev"]
    refused(client.post(P + "/narration/ops", json={"base_rev": n["rev"], "ops": []}), 422, "field_invalid")


def test_script_narration_before_an_approved_outline(client, root):
    make_book_project(root)
    P = "/api/projects/arn"
    refused(client.post(P + "/narration/generate", json={}), 409, "outline_missing", "after_fix")


def test_picks_a_field_a_missing_picks_file_and_a_stale_revision(client, root, monkeypatch):
    from state_helpers import build
    make_book_project(root)
    build("narration_approved", client, monkeypatch)
    P = "/api/projects/arn"
    b = refused(client.post(P + "/picks/search", json={"query": 5}), 422, "field_invalid")
    assert b["field"] == "query"
    refused(client.post(P + "/picks/approve", json={"rev": "x"}), 404, "no_picks")
    from state_helpers import make_picks
    make_picks(client)
    cur = client.get(P + "/picks").json()["rev"]
    b = refused(client.put(P + "/picks", json={"picks": client.get(P + "/picks").json()["picks"], "base_rev": "old"}), 409, "stale")
    assert b["current_rev"] == cur and b["rev"] == cur


def test_voice_draft_and_export_refusals(client, root, monkeypatch):
    from state_helpers import build
    make_book_project(root)
    build("drafted", client, monkeypatch)
    P = "/api/projects/arn"
    refused(client.post(P + "/voice/generate", json={"scope": "nope"}), 422, "bad_scope")
    refused(client.put(P + "/voice/settings", json={"tempo": "fast"}), 422, "bad_tempo")
    refused(client.post(P + "/draft/start", json={"provider": "x"}), 422, "bad_provider")
    refused(client.post(P + "/draft/edit", json={"instruction": " ", "scope": {"all": True}}), 422, "edit_empty_instruction")
    refused(client.post(P + "/draft/edit/nope/resolve", json={"action": "overwrite"}), 404, "turn_not_found", "no")
    refused(client.post(P + "/export/start"), 409, "not_approved", "after_fix")
    refused(client.get(P + "/export/files/none.mp4"), 404, "export_file_not_found")
    refused(client.get(P + "/voice/mix"), 404, "no_voice")


def test_draft_a_stale_edit_carries_the_current_revision(client, root, monkeypatch):
    from bti.draft.inputs import DraftError
    import bti.draft.run as draft_run
    from state_helpers import build
    make_book_project(root)
    build("drafted", client, monkeypatch)

    def stale(*a, **k):
        raise DraftError("stale_revision", "storyboard has changed since edit was requested")
    monkeypatch.setattr(draft_run, "start", stale)
    cur = client.get("/api/projects/arn").json()["rev"]
    b = refused(client.post("/api/projects/arn/draft/edit", json={"instruction": "zoom", "scope": {"all": True}, "base_rev": "old"}),
                409, "stale_revision")
    assert b["current_rev"] == cur


def test_identity_agent_settings_and_pipeline_refusals(client, root):
    make_book_project(root)
    shutil.copytree(DEMO_SRC, root / "imp", ignore=shutil.ignore_patterns("cache", "history"))
    b = refused(client.put("/api/projects/imp/identity", json={"style": "x"}), 422, "base_rev_required")
    assert b["field"] == "base_rev"
    cur = client.get("/api/projects/imp").json()["rev"]
    refused(client.put("/api/projects/imp/identity", json={"style": "no_such", "base_rev": cur}), 422, "identity_style_unknown")
    a = client.get("/api/projects/arn/agent").json()
    b = refused(client.put("/api/projects/arn/agent", json={"agent": "nobody", "base_rev": a["rev"]}), 422, "unknown_agent")
    assert b["allowed"] == ["gem"]
    b = refused(client.put("/api/projects/arn/agent", json={"agent": None, "base_rev": "old"}), 409, "stale", "after_fix")
    assert b["current_rev"] == a["rev"] == b["rev"]
    refused(client.put("/api/settings/agent", json={}), 422, "invalid_payload")
    b = refused(client.delete("/api/projects/arn?confirm=wrong"), 422, "delete_not_confirmed")
    assert b["field"] == "confirm" and "confirm=arn" in b["fix"]


def test_a_proposal_made_from_an_old_revision_carries_the_current_one(imp):
    cur = imp.get("/api/projects/imp").json()["rev"]
    b = refused(imp.post("/api/projects/imp/proposals/p_demo_001/apply", json={"accept": "all", "base_rev": "old"}), 409, "stale", "after_fix")
    assert b["current_rev"] == cur and b["detail"] == "a storyboard was saved in the meantime; open the proposal again"


def test_proposals_and_library_refusals(imp):
    b = refused(imp.post("/api/projects/imp/proposals/p_demo_001/apply", json={"accept": ["zz"]}), 422, "unknown_change_ids")
    assert b["field"] == "accept"
    refused(imp.post("/api/projects/imp/proposals/p_demo_001/apply", json={"accept": 3}), 422, "accept_invalid")
    refused(imp.get("/api/projects/imp/proposals/zzz"), 404, "proposal_not_found", "no")
    refused(imp.get("/api/library/books/zzz/works"), 404, "book_not_found", "no")
    refused(imp.get("/api/library/artworks?sort=zzz"), 422, "field_invalid")
    refused(imp.post("/api/library/projects", json={"work_ids": 3}), 422, "field_invalid")


def test_longjob_routes_and_the_body_limits_are_completed_by_the_net(imp):
    b = refused(imp.get("/api/longjobs/0123456789abcdef"), 404, "longjob_not_found", "no")
    assert b["detail"] == "Không tìm thấy việc này."                             # the existing keys are not touched
    refused(imp.get("/api/projects/imp/longjobs?kind=BAD KIND"), 422, "longjob_bad_kind")
    deep = '{"a":' * 60 + "1" + "}" * 60
    refused(imp.post("/api/projects/imp/validate", content=deep, headers={"content-type": "application/json"}), 422, "too_deep")
    big = b'{"a":"' + b"x" * (9 * 1024 * 1024) + b'"}'
    refused(imp.post("/api/projects/imp/validate", content=big, headers={"content-type": "application/json"}), 413, "too_large")


def test_every_kind_of_handled_error_has_code_fix_and_retry_and_keeps_its_status(imp):
    from bti.engine.errors import DataError, RenderError
    from bti.library.catalogue import LibraryDataError
    from bti.script.store import DocumentCorrupt, ProjectGone

    def raiser(exc):
        async def go():
            raise exc
        return go
    cases = {
        "data": (DataError("timing.json is missing", what="timing"), 409, "timing_unusable"),
        "data_other": (DataError("something is missing"), 409, "data_unusable"),
        "render": (RenderError("it cannot draw", shot="s1", technique="ZM-01"), 422, "render_failed"),
        "corrupt": (DocumentCorrupt("project.json is corrupt: x", "project"), 409, "document_corrupt"),
        "library": (LibraryDataError("artworks.json is corrupt: x"), 409, "library_data_corrupt"),
        "gone": (ProjectGone("gone"), 404, "project_not_found"),
        "surrogate": (UnicodeEncodeError("utf-8", "\ud800", 0, 1, "surrogates not allowed"), 422, "bad_text_character"),
        "bug": (RuntimeError("secret detail"), 500, "internal_error"),
        "missing_folder": (FileNotFoundError("x"), 404, "project_not_found"),
    }
    for name, (exc, status, code) in cases.items():
        path = f"/api/projects/{'nofolder' if name == 'missing_folder' else 'imp'}/probe_{name}"
        imp.app.add_api_route(path, raiser(exc), methods=["POST"])                   # a GET route added now would sit behind the static catch-all
        b = refused(imp.post(path), status, code)
        assert "secret detail" not in b["detail"]
    r = imp.post("/api/projects/imp/probe_data").json()
    assert r["data_error"] == "timing" and r["detail"] == "timing.json is missing"
    r = imp.post("/api/projects/imp/probe_render").json()
    assert r["shot"] == "s1" and r["technique"] == "ZM-01" and {"overlay", "asset"} <= set(r)
    assert imp.post("/api/projects/imp/probe_corrupt").json()["data_error"] == "project"
    assert imp.post("/api/projects/imp/probe_library").json()["data_error"] == "library"
    assert imp.post("/api/projects/imp/probe_bug").json()["retry"] == "no"


def test_a_good_answer_is_not_touched(imp):
    r = imp.get("/api/health")
    assert r.status_code == 200 and "code" not in r.json() and "fix" not in r.json()
    assert imp.get("/api/projects/imp/pipeline").json()["project"] == "imp"
