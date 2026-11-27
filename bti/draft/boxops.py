"""The prompt box on typed operations (worker c2box): the machinery that step 5 ("Sửa video bằng lời") and step 4 share.

A turn of the box is ONE model call that answers with a short list of typed operations (`bti/ops`, `docs/OPS.md`):

    {"status": "applied" | "cannot" | "escalate", "summary": "...", "reason": "...", "ops": [ ... ]}

The server then (1) checks the shape and the words, (2) dry-runs the operations through `bti.ops` with the owner's selection as the
scope and the actor `agent:<model id>`, (3) when a check refuses, sends the server's own error body back to the model ONCE, (4) applies
the batch for real with the owner's request as its note, retrying once on a new revision when the document moved in between and the
scope did not. Nothing is written until a dry run passed. The batch is in the change log, so the card's "Hoàn tác" is the undo of
that batch.

`fastedit.py` (the storyboard briefing) and `picksedit.py` (the picks briefing) build the prompts; `run.py` runs a turn as a long job
and records it in the thread (`thread.py`). The slow path (an agent working in a folder) writes through the same door:
`apply_deep` turns its compiled result into `replace_range` batches (`bti/draft/merge.py`'s three-way merge still decides what of
the owner's own edits stays).
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from bti.engine import registry as R
from bti.ops import registry
from bti.ops import runner as ops_runner
from bti.ops.adapters import PicksAdapter, StoryboardAdapter
from bti.ops.errors import OpError
from bti.ops.log import ChangeLog
from bti.ops.things import canon

from . import describe

STATUSES = ("applied", "cannot", "escalate")
# What the box never offers: a lock is the owner's own decision; `replace_range` is the slow path's tool; an import needs the network
# (one call cannot search or look), so the box does not import.
EXCLUDED = {"storyboard": ("lock", "unlock", "replace_range"), "picks": ("import",)}
# changes something shared by every line: outside any scope, so only a whole-video box may use them
WHOLE_VIDEO_PICKS = ("set_caption", "set_main", "set_region", "remove_region")
MAX_OPS = 40
SYSTEM = "You edit a video project for its owner. Answer with a single JSON object and nothing else."


# ------------------------------------------------------------------------------------------------------------ the owner's words
_EN_WORDS = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "at", "make", "add", "remove", "zoom", "slower", "faster", "circle", "this",
             "that", "shot", "it", "with", "for", "please", "more", "less", "into", "picture", "line", "change", "put", "show", "from", "is"}
_VI_PLAIN = {"la", "cho", "cai", "cua", "va", "canh", "lam", "them", "bo", "hinh", "nhe", "hon", "khong", "duoc", "nay", "mot", "cac", "toi",
             "ban", "khung", "may", "quay", "cham", "nhanh", "dong", "tranh", "doi", "sang", "vao", "ra"}
_VI_LETTERS = re.compile(r"[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]", re.I)


def owner_language(text: str) -> str:
    """`vi` or `en`: what the owner wrote the request in. Vietnamese unless the request is plain English (no diacritics, English function
    words and no Vietnamese ones): an owner who types Vietnamese without marks still gets Vietnamese."""
    t = str(text or "")
    if _VI_LETTERS.search(t):
        return "vi"
    words = re.findall(r"[a-z]+", t.lower())
    en = sum(w in _EN_WORDS for w in words)
    vi = sum(w in _VI_PLAIN for w in words)
    return "en" if en >= 2 and en > vi else "vi"


_ID = re.compile(r"\b[sbc]\d{3,6}\b|\b(?:[A-Z]{1,6}-)+\d{1,3}\b")


def sentence_problem(text: Any, lang: str) -> str | None:
    """Why a sentence of the model is not fit to show the owner, None when it is."""
    if not isinstance(text, str) or not text.strip():
        return "is missing or empty"
    if lang == "vi":
        if not describe.sentence_ok(text):
            return ("must be one plain sentence in Vietnamese (with its diacritics) that names no shot or line id, technique id or setting name, "
                    "and no number except seconds")
        return None
    if len(text) > 400 or _ID.search(text):
        return "must be one plain sentence of at most 400 characters that names no shot or line id or technique id"
    return None


def extract_json(raw: str) -> tuple[dict | None, str | None]:
    """The first JSON object of the model's answer (tolerates a code fence and text around it)."""
    text = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    candidate = text[start:end + 1] if start != -1 and end > start else text
    try:
        data = json.loads(candidate)
    except Exception as e:      # noqa: BLE001
        return None, "JSON parse error: %s" % e
    if not isinstance(data, dict):
        return None, "JSON root must be an object, got %s" % type(data).__name__
    return data, None


def check_shape(data: dict) -> list[str]:
    """The shape of the answer; the words are checked apart (a wrong sentence is not a wrong shape)."""
    st = data.get("status")
    if st not in STATUSES:
        return ["`status` must be one of %s, got %r" % (", ".join('"%s"' % s for s in STATUSES), st)]
    if st in ("cannot", "escalate"):
        return [] if isinstance(data.get("reason"), str) and data["reason"].strip() else ["status %r needs a non-empty `reason`" % st]
    out = []
    ops = data.get("ops")
    if not isinstance(ops, list) or not ops:
        out.append("status \"applied\" needs `ops`: a list of 1 to %d operation objects" % MAX_OPS)
    elif len(ops) > MAX_OPS:
        out.append("`ops` has %d operations: send at most %d (a bigger change is for the slower agent: answer \"escalate\")" % (len(ops), MAX_OPS))
    elif not all(isinstance(o, dict) for o in ops):
        out.append("every entry of `ops` must be an object with an `op` name")
    if not isinstance(data.get("summary"), str) or not data["summary"].strip():
        out.append("status \"applied\" needs `summary`: one sentence for the owner")
    return out


# ------------------------------------------------------------------------------------------------------------ the operations, as text
_TYPE_WORDS = {"string": "text", "integer": "whole number", "number": "number", "boolean": "true or false", "object": "object", "array": "list",
               "null": "null"}


def _first_sentence(text: str, cap: int = 150) -> str:
    t = " ".join(str(text or "").split())
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    t = m.group(1) if m else t
    return t if len(t) <= cap else t[:cap - 1].rstrip() + "…"


def schema_type(s: dict, depth: int = 0) -> str:
    """One compact phrase for a JSON Schema of the registry: `text`, `one of a|b`, `{t?, w?}`, `list of text`."""
    if not isinstance(s, dict):
        return "any"
    if "const" in s:
        return json.dumps(s["const"])
    if s.get("enum"):
        vals = [str(v) for v in s["enum"]]
        return "one of " + "|".join(vals)
    if s.get("anyOf") and not s.get("type"):
        return " or ".join(dict.fromkeys(schema_type(a, depth + 1) for a in s["anyOf"]))
    t = s.get("type")
    types = [t] if isinstance(t, str) else list(t or [])
    base = [x for x in types if x != "null"]
    kind = base[0] if base else "null"
    if kind == "object" and isinstance(s.get("properties"), dict) and depth < 2:
        req = set(s.get("required") or [])
        text = "{" + ", ".join("%s%s" % (k, "" if k in req else "?") for k in s["properties"]) + "}"
    elif kind == "array":
        text = "list of " + schema_type(s.get("items") or {}, depth + 1)
    else:
        text = _TYPE_WORDS.get(kind, kind)
    return text + (" or null" if "null" in types and base else "")


def render_op(d, seen: set | None = None) -> str:
    """One operation as the briefing shows it: its name and meaning, its fields (required ones marked `*`) and the registry's own example. A
    description that an earlier operation of the same briefing already gave (the shot id, the technique id, ...) is not repeated."""
    seen = seen if seen is not None else set()
    props = d.schema.get("properties") or {}
    req = set(d.schema.get("required") or [])
    lines = ["### %s: %s" % (d.name, _first_sentence(d.summary, 230))]
    for k, v in props.items():
        if k == "op":
            continue
        desc = _first_sentence(v.get("description") or "", 100)
        if desc in seen:
            desc = ""
        elif desc:
            seen.add(desc)
        lines.append("- `%s`%s (%s)%s" % (k, "*" if k in req else "", schema_type(v), (": " + desc) if desc else ""))
    lines.append("example: " + json.dumps(d.example, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines)


def allowed_ops(kind: str, *, whole_video: bool = False) -> list[str]:
    """The operations the box offers (and accepts) for a document. A scoped picks box does not offer what belongs to the whole video."""
    out = [n for n in registry.names(kind) if n not in EXCLUDED[kind]]
    if kind == "picks" and not whole_video:
        out = [n for n in out if n not in WHOLE_VIDEO_PICKS]
    return out


def render_ops(kind: str, names: list[str]) -> str:
    table = registry.defs(kind)
    seen: set = set()
    return "\n\n".join(render_op(table[n], seen) for n in names)


# ------------------------------------------------------------------------------------------------------------ the project, as the batch routes see it
class Backend:
    """How a turn reads and writes the two documents: the adapters of the batch routes (`bti/ops/adapters.py`), over the same locks and the
    same files, so a turn and a save of the page never interleave. The storyboard adapter is given the project through a fresh engine object
    each time (the engine reloads a file that changed)."""

    def __init__(self, pdir: Path):
        self.pdir = Path(pdir)
        self.pid = self.pdir.name
        self.log = ChangeLog(self.pdir)

    def _project(self, pid: str):
        from bti.engine.api import open_project
        return open_project(self.pdir)

    def _saved(self, pid: str) -> dict:
        from bti.editor.engine_adapter import ENGINE_LOCK
        with ENGINE_LOCK:
            return self._project(pid).storyboard()

    def _lock(self, pid: str):
        from bti.editor.common import save_lock
        return save_lock(self.pdir)

    def adapter(self, kind: str):
        if kind == "picks":
            return PicksAdapter(self.pdir)
        return StoryboardAdapter(self.pid, self.pdir, project=self._project, saved=self._saved, slock=self._lock, forget=lambda pid: None)

    def read(self, kind: str) -> tuple[dict, str]:
        return self.adapter(kind).read()

    def run(self, kind: str, body: dict) -> dict:
        return ops_runner.run_batch(self.adapter(kind), body, self.log)

    def undo(self, kind: str, batch: str, body: dict) -> dict:
        return ops_runner.run_undo({"picks": PicksAdapter(self.pdir), "storyboard": self.adapter("storyboard")}, batch, body, self.log)


# ------------------------------------------------------------------------------------------------------------ the scope
@dataclass
class Scope:
    kind: str                          # shots | chapter | all   (picks: beats | chapter | all)
    words: str                         # the scope in the owner's words
    ids: list[str]                     # storyboard: the shots of the selection (locked ones too); picks: the lines
    editable: list[str]                # the ones that are not locked (picks: all)
    ops: dict | None                   # the `scope` of the batch: {"shots": [...]} / {"beats": [...]} / {"chapters": [...]} / None
    chapter: str | None = None
    payload: dict = field(default_factory=dict)       # what the page sent

    @property
    def whole_video(self) -> bool:
        return self.ops is None


def scope_snapshot(kind: str, doc: dict, scope: Scope) -> str:
    """What a turn compares to tell that "the scope's shots did not change" between two readings of the document."""
    if kind == "storyboard":
        ids = set(scope.ids)
        return canon([s for s in doc.get("shots") or [] if isinstance(s, dict) and s.get("id") in ids])
    if scope.ops is None:
        return canon({k: v for k, v in doc.items() if k != "approval"})
    return canon({b: (doc.get("beats") or {}).get(b) for b in scope.ids})


# ------------------------------------------------------------------------------------------------------------ what the owner reads about a refusal
# One plain sentence for each code a refused batch can carry. `{n}` is the number of the shot or line when the error names one.
REFUSALS = {
    "storyboard": {
        "out_of_scope": "Agent định sửa cả phần bạn chưa chọn nên chưa đổi gì. Chọn thêm cảnh cần sửa, hoặc nói rõ hơn.",
        "locked": "Cảnh {n} đang khóa nên không sửa được. Mở khóa cảnh đó, hoặc bỏ nó khỏi phần đã chọn.",
        "validation_failed": "Cách sửa này làm storyboard có lỗi nên chưa đổi gì. Thử nói lại yêu cầu theo cách khác.",
        "shot_too_short": "Cách sửa này làm một cảnh quá ngắn nên chưa đổi gì. Thử nói lại yêu cầu.",
        "not_consecutive": "Các cảnh cần gộp không nằm kề nhau nên chưa đổi gì. Chọn các cảnh liền nhau.",
        "stale_revision": "Storyboard đã đổi trong lúc agent làm việc nên chưa sửa gì. Gửi lại yêu cầu.",
    },
    "picks": {
        "out_of_scope": "Agent định sửa cả phần bạn chưa chọn nên chưa đổi gì. Chọn thêm dòng cần sửa (hoặc cả video), hoặc nói rõ hơn.",
        "validation_failed": "Cách sửa này làm danh sách hình có lỗi nên chưa đổi gì. Thử nói lại yêu cầu theo cách khác.",
        "stale_revision": "Danh sách hình đã đổi trong lúc agent làm việc nên chưa sửa gì. Gửi lại yêu cầu.",
    },
}
REFUSAL_UNKNOWN = {"storyboard": "Agent nhắc tới một thứ không có trong storyboard nên chưa đổi gì. Nói rõ hơn bạn muốn sửa gì.",
                   "picks": "Agent nhắc tới một thứ không có trong danh sách hình nên chưa đổi gì. Nói rõ hơn bạn muốn sửa gì."}
REFUSAL_OTHER = "Agent trả lời chưa đúng cách, kể cả sau một lần chỉnh lại, nên chưa đổi gì. Thử gửi lại yêu cầu, hoặc nói cụ thể hơn."


def shot_number(doc: dict | None, sid: Any) -> int | str:
    shots = [s.get("id") for s in (doc or {}).get("shots") or [] if isinstance(s, dict)]
    return shots.index(sid) + 1 if sid in shots else "?"


def refusal_words(kind: str, code: str | None, body: dict | None = None, doc: dict | None = None) -> str:
    """The plain Vietnamese sentence for a batch the server refused twice (or a shape the model could not get right)."""
    table = REFUSALS[kind]
    if code in table:
        n = shot_number(doc, (body or {}).get("shot")) if kind == "storyboard" else "?"
        return table[code].format(n=n)
    if code and (code.startswith("unknown_") or code in ("slot_kind_mismatch", "wrong_technique_kind", "technique_unavailable")):
        return REFUSAL_UNKNOWN[kind]
    return REFUSAL_OTHER


def code_summary(changes: list[dict]) -> str:
    """The summary when the model's own sentence is not fit to show: the batch's first sentence and how many more there are."""
    ws = [c.get("what") for c in changes if isinstance(c, dict) and c.get("what")]
    if not ws:
        return "Đã sửa theo yêu cầu."
    return ws[0] if len(ws) == 1 else "%s. Và %d thay đổi khác." % (ws[0].rstrip("."), len(ws) - 1)


# ------------------------------------------------------------------------------------------------------------ a turn
@dataclass
class TurnResult:
    status: str                        # applied | cannot | escalate | no_change | failed
    summary: str = ""
    summary_source: str = "model"      # model | code: who wrote the sentence the owner reads
    reason: str = ""                   # cannot / escalate: what is missing and what to do, in the owner's language
    code: str | None = None            # failed: the code (a code of the operations, `spec_invalid`, `bad_model`, ...)
    words: str = ""                    # failed: the plain Vietnamese sentence
    batch: str | None = None
    changes: list = field(default_factory=list)       # the batch's own `changes` (target, time, what)
    created: dict = field(default_factory=dict)
    rev_before: str | None = None
    rev_after: str | None = None
    repairs: int = 0
    raw: str = ""
    refusal: dict | None = None        # the last error body the server gave the model
    actor: str = ""


class _CancelFlag:
    """What the providers want (`is_set()`) from what a long job has (`cancelled()`)."""

    def __init__(self, fn):
        self._fn = fn

    def is_set(self) -> bool:
        return bool(self._fn())


def _feedback_body(e: OpError) -> dict:
    """The error body the model gets back: the server's own, without the bulk (the issues and the long lists)."""
    b = e.body()
    out = {"code": b.get("code"), "detail": e.detail[:400], "fix": b.get("fix"), "retry": b.get("retry")}
    if b.get("fields"):
        out["fields"] = [{k: (v[:25] if isinstance(v, list) else v) for k, v in f.items()} for f in b["fields"][:6]]
    if b.get("op_index") is not None:
        out["op_index"] = b["op_index"]
    if b.get("issues"):
        out["issues"] = [{"code": i.get("code"), "message": str(i.get("message"))[:200], "op_index": i.get("op_index")} for i in b["issues"][:5]]
    return out


# --- catalogue pass (worker catalogue, 2026-11-20): a technique that is hidden from the models is refused, with what to use instead (`hidden_reason` of the registry)
def hidden_technique_error(kind: str, doc: dict | None, ops: list) -> OpError | None:
    """The `unknown_technique` refusal for the first operation that names a technique the registry hides from models (`offered` false); None when there is none.
    A technique the shot already has (itself or in an overlay) is never refused: the stored storyboards use hidden ones."""
    if kind != "storyboard":
        return None
    try:
        bundle = R.load_bundle(str((doc or {}).get("style") or "gae"))
    except Exception:       # noqa: BLE001 - an unreadable style is the operations' own refusal
        return None
    shots = {s.get("id"): s for s in (doc or {}).get("shots") or [] if isinstance(s, dict)}

    def has(shot_id, tid) -> bool:
        s = shots.get(shot_id) or {}
        return s.get("technique") == tid or any(isinstance(o, dict) and o.get("technique") == tid for o in s.get("overlays") or [])

    def names(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "technique" and isinstance(v, str):
                    yield v
                else:
                    yield from names(v)
        elif isinstance(x, list):
            for v in x:
                yield from names(v)

    for i, o in enumerate(ops):
        for tid in names(o):
            if bundle.spec(tid) is not None and not bundle.offered(tid) and not has(o.get("shot") if isinstance(o, dict) else None, tid):
                return OpError("unknown_technique", bundle.not_offered_text(tid), op_index=i,
                               fields=[{"path": "ops[%d].technique" % i, "problem": "is not one of the techniques you are offered", "allowed": bundle.offered_ids()}])
    return None


def repair_text(feedback: dict) -> str:
    if feedback.get("error"):
        return ("\n\n[REPAIR TURN]\nThe server did not accept your answer. This is the server's own error body:\n"
                + json.dumps(feedback["error"], ensure_ascii=False, indent=1)
                + "\n\nSend the COMPLETE answer again in the same shape, with only that mistake corrected. Nothing was written.")
    return ("\n\n[REPAIR TURN]\nYour previous answer had these problems:\n" + "\n".join("- " + i for i in feedback.get("issues") or [])
            + "\n\nSend the COMPLETE answer again in the same shape, with the problems corrected. Nothing was written.")


def _check_cancel(cancel: Any) -> None:
    if cancel is not None and cancel.is_set():
        from bti.script.providers import ProviderError
        raise ProviderError("cancelled", "cancelled")


def _provider(model_id: str):
    from bti.script import models as models_mod
    from bti.script.providers import get_provider
    spec = models_mod.resolve(model_id)
    if spec is None:
        return None, None
    return spec, get_provider(spec["provider"])


def run_turn(kind: str, backend: Backend, *, instruction: str, scope: Scope, doc0: dict, rev0: str, briefing: str, model_id: str,
             progress: Callable[[float, str], None] | None = None, cancel: Any = None, max_repairs: int = 1, timeout: float = 240.0,
             warm: Callable[[], None] | None = None) -> TurnResult:
    """One turn: the model's answer, the dry run, one repair, the batch. `doc0` and `rev0` are the document the briefing was made from.
    A provider error is raised as `bti.script.providers.ProviderError` (the caller decides what the owner is told); everything the model
    can get wrong ends in a `TurnResult`, never an exception. Nothing is written unless a dry run passed."""
    if callable(cancel):
        cancel = _CancelFlag(cancel)
    note = lambda frac, text: progress(frac, text) if progress else None      # noqa: E731
    spec, provider_fn = _provider(model_id)
    if spec is None:
        return TurnResult("failed", code="bad_model", words="", refusal=None)
    actor = "agent:" + model_id
    lang = owner_language(instruction)
    names = allowed_ops(kind, whole_video=scope.whole_video)
    feedback: dict = {}
    last_error: OpError | None = None
    shape_failed = False
    for attempt in range(max_repairs + 1):
        note(0.1 if attempt == 0 else 0.5, "Đang nghĩ…")
        ask = briefing + (repair_text(feedback) if attempt else "")
        raw = provider_fn(spec, SYSTEM, ask, timeout=timeout, on_progress=None, cancel=cancel)
        if warm is not None and attempt == 0:
            warm()                                              # joins the engine warm-up: nothing is checked while it still runs
        _check_cancel(cancel)
        note(0.7, "Đang kiểm tra…")
        data, err = extract_json(raw)
        problems = [err] if err else check_shape(data)
        if problems:
            feedback, last_error, shape_failed = {"issues": problems}, None, True
            continue
        shape_failed = False
        status = data["status"]
        if status in ("cannot", "escalate"):
            bad = sentence_problem(data["reason"], lang)
            if bad and attempt < max_repairs:
                feedback, last_error = {"issues": ["`reason` " + bad + ": it is what the owner reads when nothing is changed"]}, None
                continue
            return TurnResult(status, reason=data["reason"].strip() if not bad else "", raw=raw, repairs=attempt, actor=actor,
                              refusal={"reason_unfit": data["reason"][:300]} if bad else None)
        # status "applied": every operation must be one the box offers, then the server's own dry run
        ops = data["ops"]
        wrong = [i for i, o in enumerate(ops) if o.get("op") not in names]
        if wrong:
            i = wrong[0]
            e = OpError("unknown_op", "ops[%d].op: %r is not an operation this box offers" % (i, str(ops[i].get("op"))[:40]), op_index=i,
                        fields=[{"path": "ops[%d].op" % i, "problem": "is not an operation this box offers", "allowed": names}])
            feedback, last_error = {"error": _feedback_body(e)}, e
            continue
        hidden = hidden_technique_error(kind, doc0, ops)
        if hidden is not None:                                   # catalogue pass: refused before the dry run, with what to use instead
            feedback, last_error = {"error": _feedback_body(hidden)}, hidden
            continue
        try:
            dry, rev_d, doc_d = _dry_run(kind, backend, scope, doc0, ops, actor, instruction)
        except _Moved as m:
            return TurnResult("failed", code="stale_revision", words=refusal_words(kind, "stale_revision"), raw=raw, repairs=attempt, actor=actor,
                              refusal=m.body)
        except OpError as e:
            feedback, last_error = {"error": _feedback_body(e)}, e
            continue
        summary, source = data["summary"].strip(), "model"
        if sentence_problem(summary, lang):
            summary, source = "", "code"                        # the batch's own sentences say what changed; the summary is made from them
        if not dry["changes"]:
            return TurnResult("no_change", raw=raw, repairs=attempt, actor=actor, rev_before=rev_d, rev_after=rev_d)
        _check_cancel(cancel)                                    # a cancelled turn writes nothing
        note(0.85, "Đang áp dụng thay đổi…")
        try:
            ans = _apply(kind, backend, scope, ops, actor, instruction, rev_d, doc_d)
        except _Moved as m:
            return TurnResult("failed", code="stale_revision", words=refusal_words(kind, "stale_revision"), raw=raw, repairs=attempt, actor=actor,
                              refusal=m.body)
        except OpError as e:                                    # a refusal AFTER a clean dry run: something moved; nothing was written
            return TurnResult("failed", code=e.code, words=refusal_words(kind, e.code, e.extra, doc0), raw=raw, repairs=attempt, actor=actor,
                              refusal=_feedback_body(e))
        if not ans.get("batch") and not ans.get("changes"):
            return TurnResult("no_change", raw=raw, repairs=attempt, actor=actor, rev_before=rev_d, rev_after=ans.get("rev"))
        if not summary:
            summary = code_summary(ans["changes"])
        return TurnResult("applied", summary=summary, summary_source=source, batch=ans.get("batch"), changes=ans["changes"], created=ans["created"],
                          rev_before=rev_d, rev_after=ans["rev"], repairs=attempt, raw=raw, actor=actor)
    # the model could not give a good answer, with one repair
    if shape_failed or last_error is None:
        return TurnResult("failed", code="spec_invalid", words="", raw=raw, repairs=max_repairs, actor=actor,
                          refusal={"issues": feedback.get("issues")})
    return TurnResult("failed", code=last_error.code, words=refusal_words(kind, last_error.code, last_error.extra, doc0), raw=raw,
                      repairs=max_repairs, actor=actor, refusal=feedback.get("error"))


class _Moved(Exception):
    """The scope changed under the turn: the model's answer was made for a document that is gone."""

    def __init__(self, body: dict | None = None):
        super().__init__("the document changed")
        self.body = body


def _batch(scope: Scope, ops: list, actor: str, instruction: str, rev: str, *, dry: bool) -> dict:
    body = {"base_rev": rev, "actor": actor, "ops": ops, "dry_run": dry, "note": instruction.strip()[:2000]}
    if scope.ops is not None:
        body["scope"] = scope.ops
    return body


def _dry_run(kind: str, backend: Backend, scope: Scope, doc0: dict, ops: list, actor: str, instruction: str) -> tuple[dict, str, dict]:
    """The batch as a dry run on the document as it is NOW; returns the answer, the revision it ran on and the document it ran on. The model
    answered for `doc0`: when the scope's part of the document is not what it saw, the answer is stale (`_Moved`) and nothing is tried."""
    doc, rev = backend.read(kind)
    if scope_snapshot(kind, doc, scope) != scope_snapshot(kind, doc0, scope):
        raise _Moved({"reason": "the scope changed while the model answered"})
    try:
        return backend.run(kind, _batch(scope, ops, actor, instruction, rev, dry=True)), rev, doc
    except OpError as e:
        if e.code != "stale_revision":
            raise
    doc2, rev2 = backend.read(kind)                              # it moved between the read and the dry run: once more, if the scope stayed
    if scope_snapshot(kind, doc2, scope) != scope_snapshot(kind, doc0, scope):
        raise _Moved({"reason": "the scope changed during the dry run"})
    return backend.run(kind, _batch(scope, ops, actor, instruction, rev2, dry=True)), rev2, doc2


def _apply(kind: str, backend: Backend, scope: Scope, ops: list, actor: str, instruction: str, rev_dry: str, doc_dry: dict) -> dict:
    """The batch for real, on the revision of the dry run. A stale revision is retried once on the new one when the scope's shots did not
    change since the dry run; else `_Moved` (the turn fails saying the storyboard changed)."""
    try:
        return backend.run(kind, _batch(scope, ops, actor, instruction, rev_dry, dry=False))
    except OpError as e:
        if e.code != "stale_revision":
            raise
    now, rev_now = backend.read(kind)
    if scope_snapshot(kind, now, scope) != scope_snapshot(kind, doc_dry, scope):
        raise _Moved({"reason": "the scope changed between the dry run and the write"})
    return backend.run(kind, _batch(scope, ops, actor, instruction, rev_now, dry=False))


# ------------------------------------------------------------------------------------------------------------ what a turn records about the shots
def shot_rows(before: dict, after: dict, batch_changes: list, timing: dict | None) -> list[dict]:
    """The thread's `changes` of a storyboard batch, in the shape the card already reads (`shot_id`, `number`, `start`, `op`, `what`, `facts`):
    one row per shot that differs between the two copies of the log, and the sentences of the batch itself as its `facts` (these are what
    the card shows). `before_id` and `after_id` name the shot in each copy (they differ only for a shot the slow path replaced)."""
    from . import merge as M
    lines: dict[str, list[str]] = {}
    for c in batch_changes or []:
        sid = (c.get("target") or {}).get("shot") if isinstance(c, dict) else None
        if sid and c.get("what"):
            lines.setdefault(sid, []).append(c["what"])
    out = []
    for r in M.compute_changes(before, after, None, timing):
        r = dict(r)
        sid = r["shot_id"]
        if sid in lines:
            r["facts"], r["what"], r["what_source"] = lines[sid], lines[sid][0], "batch"
        r["before_id"] = None if r["op"] == "added" else sid
        r["after_id"] = None if r["op"] == "removed" else sid
        out.append(r)
    return out


def applied_fields(kind: str, backend: Backend, res: TurnResult, timing: dict | None) -> dict:
    """What `update_turn` stores for an applied turn: the batch, its sentences and (storyboard) the rows with the shots to show."""
    out = {"status": "applied", "doc": kind, "batch": res.batch, "batch_changes": res.changes, "summary": res.summary,
           "summary_source": res.summary_source, "before_rev": res.rev_before, "after_rev": res.rev_after, "repairs": res.repairs}
    out["changes"] = []
    if kind == "storyboard" and res.batch:
        both = backend.log.copies(res.batch)
        if both is not None:
            out["changes"] = shot_rows(both[0], both[1], res.changes, timing)
    return out


# ------------------------------------------------------------------------------------------------------------ the slow path writes through the same door
class DeepPlanError(Exception):
    """The agent's result cannot be put on the saved storyboard as operations (its shots do not tile the time they replace)."""


EPS = 1e-6


def _anchor(a: Any) -> dict | None:
    if not isinstance(a, dict):
        return None
    out = {k: a[k] for k in ("t", "w", "off", "text") if a.get(k) is not None}
    return out or None


def _clean_slots(slots: dict) -> dict:
    """Keep only `asset` / `text` per slot when emitting typed ops (`bti/ops/sb_ops.py` forbids `region` in slots)."""
    out = {}
    for k, v in slots.items():
        if isinstance(v, dict) and "asset" in v:
            out[k] = {"asset": v["asset"]}
        else:
            out[k] = copy.deepcopy(v)
    return out


def _overlay_spec(o: dict) -> dict:
    d: dict[str, Any] = {"technique": o["technique"]}
    st = _anchor(o.get("start"))
    if st:
        d["start"] = st
    if _anchor(o.get("end")):
        d["end"] = _anchor(o["end"])
    elif isinstance(o.get("dur"), (int, float)) and o["dur"] > 0:
        d["dur"] = o["dur"]
    if o.get("params"):
        d["params"] = copy.deepcopy(o["params"])
    if o.get("slots"):
        d["slots"] = _clean_slots(o["slots"])
    if o.get("intent"):
        d["intent"] = o["intent"]
    if o.get("note"):
        d["note"] = str(o["note"])[:400]
    return d


def _shot_spec(ns: dict, first: bool) -> dict:
    d: dict[str, Any] = {"technique": ns["technique"]}
    if not first:
        st = _anchor(ns.get("start"))
        if not st:
            raise DeepPlanError("a new shot has no start")
        d["start"] = st
    if ns.get("intent"):
        d["intent"] = ns["intent"]
    if ns.get("note"):
        d["note"] = str(ns["note"])[:400]
    if ns.get("slots"):
        d["slots"] = _clean_slots(ns["slots"])
    if ns.get("params"):
        d["params"] = copy.deepcopy(ns["params"])
    ovs = [_overlay_spec(o) for o in ns.get("overlays") or [] if isinstance(o, dict) and o.get("technique")]
    if ovs:
        d["overlays"] = ovs
    return d


def replace_ops(cur: dict, merged: dict, tl) -> tuple[list[dict], list[tuple[list[dict], list[dict]]]]:
    """The `replace_range` operations that turn the saved storyboard `cur` into `merged` (the agent's result merged with what the owner
    changed meanwhile): one per maximal run of consecutive shots that differ (the shot itself, or the time it covers), replaced by the shots
    `merged` has over that time. Shots that did not change keep their ids. Returns `(ops, runs)`; a run is `(old shots, new shots)`."""
    cs = [s for s in cur.get("shots") or [] if isinstance(s, dict)]
    ms = [s for s in merged.get("shots") or [] if isinstance(s, dict)]
    cspan, mspan = tl.spans(cur), tl.spans(merged)
    m_by = {s.get("id"): (s, mspan[i]) for i, s in enumerate(ms)}

    def close(a, b):
        return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= EPS)

    dirty = []
    for i, s in enumerate(cs):
        hit = m_by.get(s.get("id"))
        if hit is None or canon(s) != canon(hit[0]) or not (close(cspan[i][0], hit[1][0]) and close(cspan[i][1], hit[1][1])):
            dirty.append(i)
    runs_idx: list[list[int]] = []
    for i in dirty:
        if runs_idx and runs_idx[-1][-1] == i - 1:
            runs_idx[-1].append(i)
        else:
            runs_idx.append([i])
    ops, runs = [], []
    for idx in runs_idx:
        old = [cs[i] for i in idx]
        t0, t1 = cspan[idx[0]][0], cspan[idx[-1]][1]
        if t0 is None:
            raise DeepPlanError("a shot has no start time")
        new = [s for i, s in enumerate(ms) if mspan[i][0] is not None and t0 - EPS <= mspan[i][0] and (t1 is None or mspan[i][0] < t1 - EPS)]
        if not new:
            raise DeepPlanError("the result has no shot over the time of %s" % old[0].get("id"))
        n0 = mspan[ms.index(new[0])][0]
        if abs(n0 - t0) > 1e-3:
            raise DeepPlanError("the first new shot starts at %.2f s, not at %.2f s" % (n0, t0))
        ops.append({"op": "replace_range", "from_shot": old[0]["id"], "to_shot": old[-1]["id"],
                    "shots": [_shot_spec(ns, k == 0) for k, ns in enumerate(new)]})
        runs.append((old, new))
    return ops, runs


def new_regions(cur: dict, merged: dict) -> dict[str, dict]:
    """Regions the agent's result has on an asset that the saved storyboard lacks: `{asset: {name: region}}`."""
    out: dict[str, dict] = {}
    for key, a in (merged.get("assets") or {}).items():
        have = ((cur.get("assets") or {}).get(key) or {}).get("regions") or {}
        add = {n: copy.deepcopy(r) for n, r in ((a or {}).get("regions") or {}).items() if n not in have}
        if add and key in (cur.get("assets") or {}):
            out[key] = add
    return out


def apply_deep(backend: Backend, *, base_sb: dict, result_sb: dict, scope_ids: set[str] | None, timing: dict, instruction: str, actor: str,
               model_changes: list | None = None, overwrite: bool = False, retries: int = 1) -> dict:
    """Put the slow path's result on the saved storyboard as ONE batch of `replace_range` operations (change log, actor, note, undo), after
    the three-way merge of `bti.draft.merge` that keeps whatever the owner saved meanwhile. Returns like `merge.apply_direct_edit`
    (`status` applied | no_change | needs_choice | failed, `changes`, `conflicts`, `after_rev`) plus `batch` and `batch_changes`.
    The one thing outside the batch: regions the agent added to a picture are written first, under the storyboard lock (the operations have
    no storyboard region operation); an undo of the batch leaves them, which is harmless (a region nobody uses)."""
    from . import merge as M
    adapter = backend.adapter("storyboard")
    regions_done = False
    for attempt in range(retries + 1):
        cur, rev = adapter.read()
        mres = M.merge_storyboard(base_sb, result_sb, cur, scope_shot_ids=scope_ids, timing=timing, overwrite=overwrite)
        if mres.status == "needs_choice":
            return {"status": "needs_choice", "storyboard": None, "conflicts": mres.conflicts, "after_rev": None, "batch": None,
                    "changes": M.compute_changes(base_sb, result_sb, model_changes, timing)}
        merged = mres.storyboard
        add = new_regions(cur, merged)
        if add and not regions_done:
            def make(current):
                doc = copy.deepcopy(current)
                for key, regs in add.items():
                    doc["assets"][key].setdefault("regions", {}).update(copy.deepcopy(regs))
                return doc, None
            M.locked_update(backend.pdir, make)
            regions_done = True
            cur, rev = adapter.read()
            mres = M.merge_storyboard(base_sb, result_sb, cur, scope_shot_ids=scope_ids, timing=timing, overwrite=overwrite)
            if mres.status == "needs_choice":
                return {"status": "needs_choice", "storyboard": None, "conflicts": mres.conflicts, "after_rev": None, "batch": None,
                        "changes": M.compute_changes(base_sb, result_sb, model_changes, timing)}
            merged = mres.storyboard
        try:
            ops, runs = replace_ops(cur, merged, adapter.facts(cur).timeline)
        except DeepPlanError as e:
            return {"status": "failed", "code": "compile_error", "detail": str(e), "changes": [], "conflicts": [], "after_rev": None, "batch": None}
        if not ops:
            return {"status": "no_change", "storyboard": cur, "changes": [], "conflicts": [], "after_rev": rev, "batch": None,
                    "touched_ids": sorted(mres.touched_ids)}
        scope_list = sorted(scope_ids) if scope_ids else [s.get("id") for s in cur.get("shots") or [] if isinstance(s, dict)]     # no named shots: any shot may be in a run
        body = {"base_rev": rev, "actor": actor, "ops": ops, "note": instruction.strip()[:2000], "scope": {"shots": scope_list}}
        try:
            ans = backend.run("storyboard", body)
        except OpError as e:
            if e.code == "stale_revision" and attempt < retries:
                continue                                         # the owner saved in between: read, merge and try once more
            raise
        break
    rows = M.turn_changes(base_sb, merged, mres.touched_ids, model_changes=model_changes, timing=timing)
    created, mapping, k = list(ans["created"].get("shots") or []), {}, 0
    for _old, new in runs:
        for s in new:
            if k < len(created):
                mapping[s.get("id")] = created[k]
            k += 1
    both = backend.log.copies(ans["batch"]) if ans.get("batch") else None
    order = [s.get("id") for s in (both[1].get("shots") if both else None) or []]
    for r in rows:
        sid = r["shot_id"]
        r["before_id"] = None if r["op"] == "added" else sid
        r["after_id"] = None if r["op"] == "removed" else mapping.get(sid, sid)
        r["shot_id"] = r["after_id"] or sid
        if r["after_id"] in order:
            r["number"] = order.index(r["after_id"]) + 1
    status = "applied" if ans.get("batch") or ans.get("changes") else "no_change"
    return {"status": status, "after_rev": ans["rev"], "changes": rows if status == "applied" else [], "conflicts": [], "batch": ans.get("batch"),
            "batch_changes": ans.get("changes") or [], "touched_ids": sorted(mres.touched_ids), "storyboard": None}
