"""Runs ON the Windows server (test code only): tests/e2e/stages/launch.py (the second, throw-away instance of the app: fakes, mock model,
BTI_NO_REAL_MODELS=1, its own port and temp copies of the data) with TWO MOCK AGENTS that carry the names of the real two:
  - a private agent file (BTI_AGENT_CHOICES_FILE): "Gemini 3.8 Flash" runs the mock model `mock`, "Opus 5.5 High" the mock model `mock-opus`;
    the steps are the real ones. No `agy` and no `claude` is ever started.
  - `mock-opus` answers like `mock`, except that a request whose text holds `[mock:quota]` gets a usage-limit answer that opens again in
    4 hours 30 minutes (what Claude Code answers when the plan's limit is reached), for the script jobs and the fast edit alike;
  - the agent in a folder (the draft) is a fake runner: `mock-opus` answers the usage limit, `mock` writes the automatic draft into out/;
  - `PUT /api/_e2e/opus {down: true|false}` makes `mock-opus` "not signed in" (a model that cannot run, with the owner's sentence).
Usage (through remote.mjs): BTI_STAGES_LAUNCH=tests\\e2e\\agent\\launch_agent.py; the arguments are those of launch.py."""
import json
import os
import runpy
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
os.environ["BTI_REPO"] = str(REPO)

STEPS = {"script": ["script.outline", "script.narration"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"]}
CHOICES = {"default": "gemini", "steps": STEPS,
           "agents": [{"id": "gemini", "label": "Gemini 3.8 Flash", "model": "mock"}, {"id": "opus", "label": "Opus 5.5 High", "model": "mock-opus"}]}
choices = Path(tempfile.gettempdir()) / "bti-agentpick-choices.json"
choices.write_text(json.dumps(CHOICES), encoding="utf-8")
os.environ["BTI_AGENT_CHOICES_FILE"] = str(choices)

SIGNED_OUT = "Claude Code trên máy chủ chưa đăng nhập. Hãy đăng nhập một lần trên máy chủ bằng lệnh `claude auth login`, rồi thử lại."
STATE = {"opus_down": False}

# ---- the second mock model, and "not signed in"
from bti.script import models as M  # noqa: E402

_load_raw = M.load_raw
_resolve = M.resolve


def load_raw(path=None):
    rows = list(_load_raw(path))
    if not any(r.get("id") == "mock-opus" for r in rows):
        rows.append({"id": "mock-opus", "label": "Mock (Opus giả)", "provider": "mock", "model": "mock", "key_env": None})
    return rows


def resolve(model_id, path=None):
    spec = _resolve(model_id, path)
    if spec and spec.get("id") == "mock-opus" and STATE["opus_down"]:
        return {**spec, "unavailable": SIGNED_OUT, "unavailable_kind": "auth", "unavailable_reason": "not_signed_in"}
    return spec


M.load_raw = load_raw
M.resolve = resolve

# ---- the usage-limit answer of `mock-opus`
import bti.script.providers as P  # noqa: E402
import re  # noqa: E402

_get_provider = P.get_provider
_HELPER_FIELDS = ("in_scope", "locked", "start_s", "end_s", "beat_text", "duration_s")


def _edit_answer(user):
    """A good answer to the fast edit of the CURRENT contract (only the shots the model changes, whole, id kept, helper fields not sent back):
    every shot of the scope kept, with its note changed. (The canned answer of launch.py looks for the heading of an older template, so it never fires: the mock then answers "mock response", refused as `spec_invalid`.)"""
    m = re.search(r"do not send them back\.\n(\[.*?\n\])\n\n### The words", user, re.S)
    shots = json.loads(m.group(1)) if m else []
    out, changes = [], []
    for sh in shots:
        sh = {k: v for k, v in sh.items() if k not in _HELPER_FIELDS}
        sh["note"] = "Làm chậm chuyển động (bản thử)"
        out.append(sh)
        changes.append({"shot": sh.get("id"), "what": "Làm chậm chuyển động của cảnh này"})
    return json.dumps({"result": "edit", "summary": "Đã làm chậm chuyển động ở %d cảnh." % len(out), "shots": out, "remove": [], "changes": changes}, ensure_ascii=False)


def get_provider(name):
    fn = _get_provider(name)
    if name != "mock":
        return fn

    def complete(spec, system, user, **kw):
        if spec.get("id") == "mock-opus" and "[mock:quota]" in user:
            e = P.ProviderError("rate_limit", "Hạn mức của gói Claude Code đã hết. Thử lại sau 4 giờ 30 phút.")
            e.retry_after_seconds = 16200
            raise e
        if "change a few shots of a video's storyboard" in user and "[mock:slow]" not in user:        # the heading of skills/storyboard_edit/FAST.template.md
            return _edit_answer(user)
        return fn(spec, system, user, **kw)
    return complete


P.get_provider = get_provider          # generate.py imports it below, after this line, so it gets this one

# ---- the agent in a folder (the draft): a fake runner
from bti.draft import run as R  # noqa: E402
from bti.draft.providers import agy as _agy, auto as _auto  # noqa: E402


class FakeRunner:
    @staticmethod
    def run(ws_root, *, model=None, cancel=None, **kw):
        if model == "mock-opus":
            return _agy.AgyResult(status="error", error_code="claude_rate_limit", error_message="usage limit", retry_after_seconds=16200, elapsed=0.1)
        from bti.draft import workspace as W
        inp, _ = W.load_workspace(ws_root)
        for cid, spec in _auto.draft(inp).items():
            (Path(ws_root) / "out" / (cid + ".json")).write_text(json.dumps(spec), encoding="utf-8")
        (Path(ws_root) / "out" / "notes.md").write_text("Bản nháp thử của agent giả.", encoding="utf-8")
        time.sleep(1.0)
        return _agy.AgyResult(status="ok", turns=1, steps=3, elapsed=1.0)


R._check_agent_installed = lambda model_id: None
R._agent_module = lambda model_id: FakeRunner

# ---- a switch for "not signed in"
import bti.editor.app as A  # noqa: E402

_create_app = A.create_app


def create_app(*a, **k):
    app = _create_app(*a, **k)

    def opus(body: dict):
        STATE["opus_down"] = bool(body.get("down"))
        return {"down": STATE["opus_down"]}
    app.add_api_route("/api/_e2e/opus", opus, methods=["PUT"])
    return app


A.create_app = create_app

runpy.run_path(str(HERE.parent / "stages" / "launch.py"), run_name="__main__")
