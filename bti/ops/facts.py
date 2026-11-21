"""The project's facts: what an operation may need to know besides the document it changes.

An operation never reads a file. The facts do, once, when a batch starts, and answer questions in plain terms: which narration
lines exist and in what order, what the timing is, which techniques the style has, what the engine's defaults are, what the
validation says. One class per document; the tests build their own when they need a fake.

`PicksFacts` and `StoryboardFacts` are what `bti.ops.runner` hands to `bti.ops.batch.apply_ops`.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bti.engine import registry as R
from bti.engine.timing import Timing

from .errors import OpError, small
from .timeline import Timeline, fmt_time


def _bad_scope(path: str, problem: str, allowed: list | None = None) -> OpError:
    entry: dict[str, Any] = {"path": path, "problem": problem}
    vals = small(allowed) if allowed is not None else None
    if vals is not None:
        entry["allowed"] = vals
    return OpError("invalid_request", "%s %s" % (path, problem), fields=[entry])


def _scope_items(scope: dict) -> tuple[str, list]:
    kind = next(iter(scope))
    return kind, scope[kind]


# ---------------------------------------------------------------- picks
class PicksFacts:
    """Facts for the picks document: the narration lines (their order and, when the timing allows, their start times)."""

    def __init__(self, pdir: Path, *, narration: dict | None = None, beat_times: dict | None = None):
        nv = narration or {}
        self.pdir = Path(pdir)
        self.present = bool(nv.get("present"))
        self.beat_ids: list[str] = list(nv.get("beat_ids") or [])
        self.beat_set = set(self.beat_ids)
        self.chapters: dict[str, list[str]] = {c["id"]: [b["id"] for b in c.get("beats") or []] for c in nv.get("chapters") or []}
        self._times = dict(beat_times or {})

    @classmethod
    def from_project(cls, pdir: Path) -> "PicksFacts":
        from bti.picks import context
        nv = context.narration_view(Path(pdir))
        return cls(pdir, narration=nv, beat_times=_beat_times(Path(pdir), nv))

    def beat_no(self, bid: str):
        """The number the owner sees for a line (its place in the narration, from 1), or the id when the narration is not known."""
        return self.beat_ids.index(bid) + 1 if bid in self.beat_set else bid

    def beat_time(self, bid: str) -> str | None:
        return fmt_time(self._times.get(bid))

    def resolve_scope(self, scope: dict, doc: dict) -> set[str]:
        kind, vals = _scope_items(scope)
        if kind == "shots":
            raise _bad_scope("scope.shots", "does not apply to the picks document: use beats or chapters")
        if kind == "beats":
            if self.present:
                for k, b in enumerate(vals):
                    if b not in self.beat_set:
                        raise _bad_scope("scope.beats[%d]" % k, "is not a beat of the narration", self.beat_ids)
            return set(vals)
        out: set[str] = set()
        for k, c in enumerate(vals):
            if c not in self.chapters:
                raise _bad_scope("scope.chapters[%d]" % k, "is not a chapter of the narration", sorted(self.chapters))
            out.update(self.chapters[c])
        return out

    # -- validation
    def document_problem(self, doc: dict) -> str | None:
        from bti.picks import doc as pdoc
        return pdoc.doc_problem(doc)

    def issues(self, doc: dict) -> list[dict]:
        from bti.picks import doc as pdoc
        return pdoc.issues(doc, self.pdir, self.beat_ids if self.present else None)

    def fingerprint(self, issue: dict, doc: dict) -> tuple:
        return (issue.get("code"), issue.get("beat"), issue.get("asset"), issue.get("region"))

    def issue_keys(self, issue: dict, doc: dict) -> list[str]:
        """The thing keys an issue may come from (to name the operation that changed one of them), most likely first."""
        code, asset, beat = issue.get("code"), issue.get("asset"), issue.get("beat")
        if code == "no_main":
            return ["main"]
        if code == "unknown_region":
            return ["regions:%s" % asset, "beat:%s" % beat]
        if code == "unknown_asset":
            return ["asset:%s" % asset, "beat:%s" % beat]
        if code in ("asset_file_missing", "asset_flag"):
            return ["asset:%s" % asset]
        return ["beat:%s" % beat] if beat else []


def _beat_times(pdir: Path, nv: dict) -> dict:
    """Start time of each narration line, taken from timing.json when it has exactly one beat for every line (the rule the draft uses)."""
    try:
        from bti.script import store as sstore
        timing = sstore.read_object(pdir / "timing.json", "timing") or {}
        beats = [b for b in timing.get("beats") or [] if isinstance(b, dict)]
        ids = nv.get("beat_ids") or []
        if beats and len(beats) == len(ids):
            return {bid: float(b["start"]) for bid, b in zip(ids, beats)
                    if isinstance(b.get("start"), (int, float)) and not isinstance(b.get("start"), bool)}
    except Exception:       # noqa: BLE001  - the times are decoration: a sentence without one is still true
        pass
    return {}


# ---------------------------------------------------------------- storyboard
_SHOT_PATH = re.compile(r"^shots\[(\d+)\](?:\.overlays\[(\d+)\])?(.*)$", re.S)


class StoryboardFacts:
    """Facts for the storyboard document: the style's techniques, the timing, the engine's validation and defaults.
    `project` is an engine `Project` of the app (real or stub); every call into it holds the engine lock."""

    def __init__(self, pdir: Path, project: Any, doc: dict):
        import bti.engine.api  # noqa: F401  - registers the renderers: `bundle.available` is false for a technique without one
        from bti.editor.engine_adapter import ENGINE_LOCK
        self._lock = ENGINE_LOCK
        self.pdir = Path(pdir)
        self.project = project
        style = doc.get("style") if isinstance(doc.get("style"), str) and doc.get("style") else "gae"
        self.bundle = R.load_bundle(style)
        with self._lock:
            self.raw_timing = project.timing()
        self.timing = Timing(self.raw_timing)
        self.timeline = Timeline(self.timing)
        self._norm: dict | None = None

    # -- the engine
    def validate(self, doc: dict) -> list[dict]:
        with self._lock:
            return self.project.validate(doc)

    issues = validate

    def defaults(self, technique: str, context: dict) -> dict:
        """The starting parameters of `technique` for a context, exactly what `POST /api/projects/{pid}/defaults` returns as `params`."""
        from bti.editor.app import engine_context
        with self._lock:
            return self.project.default_params(technique, engine_context(context))

    def document_problem(self, doc: dict) -> str | None:
        return None                 # the engine's validation reports a structure it cannot read (`unreadable_structure`)

    # -- scope
    def _normalized(self) -> dict:
        if self._norm is None:
            from bti.draft.inputs import DraftError, normalize_timing
            from bti.script import store as sstore
            n = sstore.load_narration(self.pdir)
            try:
                self._norm = normalize_timing(self.raw_timing, n.to_dict() if n is not None else None)
            except DraftError as e:
                raise OpError("invalid_request", "the scope cannot be resolved from timing.json: %s" % str(e)[:200],
                              fields=[{"path": "scope", "problem": "needs chapters and beats in timing.json: %s" % str(e)[:200]}])
        return self._norm

    def resolve_scope(self, scope: dict, doc: dict) -> set[str]:
        kind, vals = _scope_items(scope)
        shots = [s for s in doc.get("shots") or [] if isinstance(s, dict)]
        if kind == "shots":
            have = [s.get("id") for s in shots]
            for k, sid in enumerate(vals):
                if sid not in have:
                    raise _bad_scope("scope.shots[%d]" % k, "is not a shot of the storyboard", have)
            return set(vals)
        nt = self._normalized()
        ranges = {x["id"]: (x["start"], x["end"]) for x in nt["chapters" if kind == "chapters" else "beats"]}
        for k, ident in enumerate(vals):
            if ident not in ranges:
                raise _bad_scope("scope.%s[%d]" % (kind, k), "is not a %s of the narration timing" % kind[:-1], sorted(ranges))
        out: set[str] = set()
        spans = self.timeline.spans(doc)
        for s, (t0, _) in zip(doc.get("shots") or [], spans):
            if t0 is None or not isinstance(s, dict):
                continue
            if any(a - 0.05 <= t0 < b - 0.05 for a, b in (ranges[i] for i in vals)):
                out.add(s.get("id"))
        return out

    # -- issues
    @staticmethod
    def _id_path(path: str, doc: dict) -> str:
        m = _SHOT_PATH.match(path or "")
        if not m:
            return path or ""
        shots = doc.get("shots") or []
        i = int(m.group(1))
        sid = shots[i].get("id") if i < len(shots) and isinstance(shots[i], dict) else "#%d" % i
        out = "shot:%s" % sid
        if m.group(2) is not None:
            ovs = (shots[i].get("overlays") or []) if i < len(shots) and isinstance(shots[i], dict) else []
            j = int(m.group(2))
            out += "/ov:%s" % (ovs[j].get("id") if j < len(ovs) and isinstance(ovs[j], dict) else "#%d" % j)
        return out + m.group(3)

    def fingerprint(self, issue: dict, doc: dict) -> tuple:
        """What makes an issue "the same problem" before and after a batch: its code and where it is, by shot and overlay id
        (a split or a merge moves the indexes in a path, never the ids)."""
        return (issue.get("code"), self._id_path(issue.get("path") or "", doc))

    def issue_keys(self, issue: dict, doc: dict) -> list[str]:
        m = _SHOT_PATH.match(issue.get("path") or "")
        if not m:
            return []
        shots = doc.get("shots") or []
        i = int(m.group(1))
        if i < len(shots) and isinstance(shots[i], dict) and isinstance(shots[i].get("id"), str):
            return ["shot:%s" % shots[i]["id"]]
        return []
