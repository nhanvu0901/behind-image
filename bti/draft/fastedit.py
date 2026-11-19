"""The storyboard side of the prompt box (step 5, the fast path): the scope, the briefing, and one turn.

One call to a model (`bti.script.providers`, no workspace, no tools) that answers with typed operations
(`{"status", "summary", "reason", "ops"}`, see `boxops.py` for the whole turn: dry run inside the owner's selection, one repair, one
batch in the change log). This module builds what the model is given from `skills/storyboard_edit/FAST.template.md`:

  * the operations useful here, rendered from the registry in `bti/ops` (never hand written),
  * the shots in scope (with the narration spoken in each), the shot before and after, the narration words over the range,
  * the pictures those shots use and their regions, the other pictures of the project,
  * the catalogue of techniques reduced to what a small edit needs: the techniques on the scope's shots, the usual overlays, the core base
    techniques, and an explanatory device only when the request is about that kind of point.
"""
from __future__ import annotations

import json
import re
import threading
from typing import Any, Callable

from bti.engine import registry as R
from bti.engine.timing import Timing
from bti.identity import read as read_identity
from bti.ops.timeline import fmt_time
from bti.script.brief import REPO_ROOT

from . import boxops as B
from . import decompile as D
from . import techniques_md as T
from .inputs import DraftInputs, line_assets, resolve_edit_scope

TEMPLATE_PATH = REPO_ROOT / "skills" / "storyboard_edit" / "FAST.template.md"
MAX_WORDS = 500          # the narration words shown at most
SAYS_WORDS = 40          # the narration of one shot, at most this many words

# the explanatory devices and the words of a request that are about them: a device is described only when the sentence asks for its kind of point
DEVICE_WORDS = {
    "MAP-01": r"bản đồ|ban do|\bmap\b|địa điểm|hành trình|vùng đất|lãnh thổ|route|journey|territory",
    "TIME-01": r"mốc|dòng thời gian|trục thời gian|niên đại|timeline|chronolog|\bnăm\b",
    "TREE-01": r"sơ đồ|quan hệ|gia đình|gia phả|dòng họ|family|relation|genealog|\btree\b",
    "KEY-01": r"nhãn|gọi tên|chỉ các phần|đặt tên|\blabels?\b|name the parts",
    "NUM-01": r"con số|số liệu|bao nhiêu|so sánh số|\bfigure|\bnumber|how many|statistic",
    "STATE-01": r"hai trạng thái|trước và sau|phục chế|hồng ngoại|tia x|x-ray|infrared|before and after|restoration",
    "DOC-01": r"dòng chữ|chữ ký|thư từ|trích dẫn|làm sáng|inscription|signature|\bletter\b|quotation|highlight the text",
}


# ------------------------------------------------------------------------------------------------------------ the scope
def storyboard_scope(inp: DraftInputs, doc: dict, payload: dict, bundle=None) -> B.Scope:
    """The owner's selection as a `Scope` (raises `DraftError` for an empty, unknown or fully locked one, as the routes always did). Cards
    (title, chapter marks, text cards) are not part of what the box edits: they stay out of the scope, so the batch cannot touch them."""
    unlocked, _chapters, words = resolve_edit_scope(inp, payload)
    bundle = bundle or R.load_bundle(inp.style)
    shots = [s for s in doc.get("shots") or [] if isinstance(s, dict) and isinstance(s.get("id"), str)]
    order = [s["id"] for s in shots]
    cards = {s["id"] for s in shots if D.is_card(bundle, s)}
    if payload.get("all"):
        kind, ids, chapter = "all", order, None
    elif payload.get("chapter") is not None:
        kind, chapter = "chapter", str(payload["chapter"]).strip()
        tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
        ids = []
        for rc in D.resolved_current(inp, tm):
            s = rc["shot"]
            if isinstance(s.get("id"), str) and D.chapter_of(inp, D._word_of(tm, s.get("start") or {}, rc["t0"])[0]) == chapter:
                ids.append(s["id"])
    else:
        kind, chapter = "shots", None
        want = set(payload.get("shots") or [])
        ids = [i for i in order if i in want]
    ids = [i for i in ids if i not in cards]
    editable = [i for i in ids if i in unlocked]
    return B.Scope(kind, words, ids, editable, {"shots": ids}, chapter=chapter, payload=dict(payload))


# ------------------------------------------------------------------------------------------------------------ what the model is shown
def _compact(o: Any) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def _anchor(a: Any) -> Any:
    if isinstance(a, dict):
        return {k: a[k] for k in ("t", "w", "off") if a.get(k) is not None and not (k == "off" and a[k] == 0)}
    return a


def _says(words: list[dict], t0: float | None, t1: float | None, cap: int = SAYS_WORDS) -> str:
    if t0 is None:
        return ""
    got = [str(w.get("w", "")) for w in words if float(w.get("s", 0)) >= t0 - 1e-6 and (t1 is None or float(w.get("s", 0)) < t1 - 1e-6)]
    return " ".join(got[:cap]) + (" …" if len(got) > cap else "")


def _overlay_view(o: dict) -> dict:
    v = {"id": o.get("id"), "technique": o.get("technique"), "intent": o.get("intent"), "start": _anchor(o.get("start"))}
    if o.get("end") is not None:
        v["end"] = _anchor(o["end"])
    elif o.get("dur") is not None:
        v["dur"] = o["dur"]
    for k in ("params", "slots", "note"):
        if o.get(k):
            v[k] = o[k]
    if o.get("locked"):
        v["locked"] = True
    return v


def shot_view(shot: dict, n: int, span: tuple, words: list[dict], *, full: bool = True) -> dict:
    t0, t1 = span
    v: dict[str, Any] = {"id": shot.get("id"), "n": n, "at": fmt_time(t0), "len_s": round(t1 - t0, 1) if t0 is not None and t1 is not None else None}
    if full:
        v["start"] = _anchor(shot.get("start"))
    v["technique"] = shot.get("technique")
    if full:
        v["intent"] = shot.get("intent")
    if shot.get("locked"):
        v["locked"] = True
    if full:
        for k in ("slots", "params"):
            if shot.get(k):
                v[k] = shot[k]
        if shot.get("overlays"):
            v["overlays"] = [_overlay_view(o) for o in shot["overlays"] if isinstance(o, dict)]
        if shot.get("transition_in"):
            v["transition_in"] = shot["transition_in"]
        if shot.get("note"):
            v["note"] = shot["note"]
    v["says"] = _says(words, t0, t1, SAYS_WORDS if full else 18)
    return v


def _region_text(r: dict) -> dict:
    out = {"label": r.get("label") or ""}
    for k in ("x", "y", "rx", "ry"):
        if isinstance(r.get(k), (int, float)):
            out[k] = r[k]
    return out


def assets_block(doc: dict, used: set[str], main: str | None, offered: set[str] | None = None) -> str:
    """The pictures of the scope's shots with their regions, then the other pictures of the project; with `offered` (the pictures some line of the
    narration has, `inputs.line_assets`) the others are only those: a picture the owner took out of every line stays in the project but is not offered."""
    assets = doc.get("assets") or {}
    shown, others = {}, {}
    for key, a in assets.items():
        if not isinstance(a, dict):
            continue
        if key not in used and key != main and offered is not None and key not in offered:
            continue
        if key in used or key == main:
            shown[key] = {"title": a.get("title") or key, "kind": a.get("kind", "image"), "size": "%sx%s" % (a.get("width"), a.get("height")),
                          "regions": {n: _region_text(r) for n, r in (a.get("regions") or {}).items() if isinstance(r, dict)}}
        else:
            regs = ", ".join((a.get("regions") or {}))
            others[key] = "%s (%s%s)" % (a.get("title") or key, a.get("kind", "image"), "; regions: " + regs if regs else "")
    text = ["Pictures on the scope's shots (and the main picture %s):" % (main or "-"), _compact(shown) if shown else "{}"]
    if others:
        text += ["Other pictures of the project (usable with `set_slot`):", _compact(others)]
    return "\n".join(text)


def words_block(inp_words: list[dict], t0: float | None, t1: float | None) -> str:
    if t0 is None:
        return "(none)"
    lo = next((i for i, w in enumerate(inp_words) if float(w.get("s", 0)) >= t0 - 1e-6), len(inp_words))
    hi = next((i for i, w in enumerate(inp_words) if t1 is not None and float(w.get("s", 0)) >= t1 - 1e-6), len(inp_words))
    hi = min(hi, lo + MAX_WORDS)
    return " ".join("%d:%s@%.1f" % (i, str(inp_words[i].get("w", "")), float(inp_words[i].get("s", 0.0))) for i in range(lo, hi)) or "(none)"


# ------------------------------------------------------------------------------------------------------------ the catalogue, reduced
def _kinds_text(t: dict) -> str:
    return "%s, %s" % (t["kind"], T.USAGE_HELP.get(t.get("channel_usage"), t.get("channel_usage") or ""))


def _params_names(t: dict) -> str:
    return ", ".join(p["name"] for p in t.get("params") or []) or "none"


def _sentence(text: str, cap: int = 110) -> str:
    t = " ".join(str(text or "").split())
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    t = m.group(1) if m else t
    return t if len(t) <= cap else t[:cap - 1].rstrip() + "…"


def catalogue(bundle: R.StyleBundle, used: set[str], instruction: str) -> str:
    """The techniques a small edit needs, generated from the registry: those on the scope's shots (full), the core overlays (full), the other
    occasional overlays and the core base techniques (one line each: what, slots, parameter names; the defaults of their parameters apply), and
    the explanatory devices the request is about (full, with the filled example). Identity techniques, rare, other-series and shorts-only ones
    are left out."""
    techs = [t for t in bundle.techniques if t.get("engine", {}).get("available") is True]
    cfg = read_identity(bundle.style)
    ident = (lambda tid: bool(cfg) and cfg.is_identity_technique(tid))
    asked = {tid for tid, pat in DEVICE_WORDS.items() if re.search(pat, instruction or "", re.I)}
    full, brief, devices = [], [], []
    for t in techs:
        tid, usage = t["id"], t.get("channel_usage")
        if ident(tid) or usage in ("shorts_only", "other_series"):
            continue
        if tid.startswith(T.EXPLAINER_FAMILIES):
            if tid in asked:
                devices.append(t)
        elif tid in used or (t["kind"] == "overlay" and usage == "core"):
            full.append(t)
        elif (t["kind"] == "overlay" and usage == "occasional") or (t["kind"] in ("base", "card") and usage == "core"):
            brief.append(t)
    order = {"base": 0, "card": 1, "overlay": 2, "transition": 3}

    def entry(t: dict) -> list[str]:
        lines = ["### %s %s  [%s]" % (t["id"], t["name"], t["kind"]), "- used as: %s" % T.KIND_WHERE.get(t["kind"], t["kind"]),
                 "- what: %s" % (t.get("description") or ""),
                 "- slots: %s" % (", ".join(T._slot(s) for s in t.get("slots") or []) or "none"),
                 "- params: %s" % (", ".join(T._p(p) for p in t.get("params") or []) or "none")]
        if T._example(t):
            lines.append("- example (the defaults; replace ALL of its data): %s" % T._example(t))
        return lines

    out = []
    if full:
        out += ["## Techniques on the scope's shots, and the usual overlays (parameters in full)", ""]
        for t in sorted(full, key=lambda t: (order.get(t["kind"], 9), t["id"])):
            out += entry(t) + [""]
    if brief:
        out += ["## Other treatments (one line each: what, slots, parameter names; a new treatment takes the defaults of its parameters)", ""]
        for t in sorted(brief, key=lambda t: (order.get(t["kind"], 9), t["id"])):
            out.append("- %s %s [%s]: %s | slots: %s | params: %s" % (t["id"], t["name"], t["kind"], _sentence(t.get("description")),
                                                                    ", ".join(T._slot(s) for s in t.get("slots") or []) or "none",
                                                                    ", ".join(p["name"] for p in t.get("params") or []) or "none"))
        out.append("")
    if devices:
        out += ["## Explanatory devices the request is about (use one only for that kind of point)", ""]
        for t in sorted(devices, key=lambda t: t["id"]):
            out += entry(t) + [""]
    return "\n".join(out).strip()


def history_block(turns: list[dict] | None) -> str:
    rows = [t for t in (turns or []) if t.get("instruction") and t.get("doc", "storyboard") == "storyboard"][-3:]
    if not rows:
        return "(no earlier turn)"
    out = []
    for i, t in enumerate(rows, 1):
        said = (t.get("summary") or t.get("reason") or t.get("notes") or "").strip()
        out.append("Turn %d: owner: %s | outcome: %s%s" % (i, t["instruction"].strip(), t.get("status") or "?", (" | " + said) if said else ""))
    return "\n".join(out)


def build_briefing(inp: DraftInputs, doc: dict, facts: Any, scope: B.Scope, instruction: str, thread_turns: list[dict] | None = None) -> str:
    """The briefing, from the template: nothing in it is about shots outside the scope except the two neighbours."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    shots = [s for s in doc.get("shots") or [] if isinstance(s, dict)]
    spans = facts.timeline.spans(doc)
    words = inp.timing["words"]
    idx = {s.get("id"): i for i, s in enumerate(shots)}
    mine = sorted(idx[i] for i in scope.ids if i in idx)
    lang = "English" if B.owner_language(instruction) == "en" else "Vietnamese"
    shot_lines = [_compact(shot_view(shots[i], i + 1, spans[i], words)) for i in mine]
    prev_i = mine[0] - 1 if mine else -1
    next_i = mine[-1] + 1 if mine else len(shots)
    neighbours = []
    for tag, i in (("before", prev_i), ("after", next_i)):
        neighbours.append("%s: %s" % (tag, _compact(shot_view(shots[i], i + 1, spans[i], words, full=False)) if 0 <= i < len(shots) else "(none)"))
    used: set[str] = set()
    techs: set[str] = set()
    for i in mine:
        s = shots[i]
        techs.add(s.get("technique"))
        for slot in (s.get("slots") or {}).values():
            if isinstance(slot, dict) and slot.get("asset"):
                used.add(slot["asset"])
        for o in s.get("overlays") or []:
            techs.add(o.get("technique"))
            for slot in (o.get("slots") or {}).values():
                if isinstance(slot, dict) and slot.get("asset"):
                    used.add(slot["asset"])
    t_lo = spans[mine[0]][0] if mine else None
    t_hi = spans[mine[-1]][1] if mine else None
    bundle = facts.bundle
    names = B.allowed_ops("storyboard")
    out = template
    for key, value in {"LANG": lang, "INSTRUCTION": instruction.strip(), "THREAD_HISTORY": history_block(thread_turns),
                       "OPS": B.render_ops("storyboard", names), "SCOPE_WORDS": scope.words, "SHOTS": "\n".join(shot_lines) or "(none)",
                       "NEIGHBOURS": "\n".join(neighbours), "WORDS": words_block(words, t_lo, t_hi),
                       "ASSETS": assets_block(doc, used, inp.picks.get("main_asset"), line_assets(inp)),
                       "CATALOGUE": catalogue(bundle, techs, instruction), "MAXOPS": str(B.MAX_OPS)}.items():
        out = out.replace("{{%s}}" % key, value)
    return out


# ------------------------------------------------------------------------------------------------------------ one turn
def _warm(inp: DraftInputs) -> threading.Thread:
    """Best effort, never raises: the first use of the engine in a process (style registry, picture decoding, the scene) takes seconds. It
    runs while the model thinks, so the checks after the answer find everything warm."""
    def go():
        try:
            from bti.draft.engine import DraftProject
            cur = inp.current
            eng = DraftProject(inp.project_dir, cur, inp.timing)
            try:
                eng.validate(cur)
            finally:
                eng.close()
        except Exception:       # noqa: BLE001
            pass
    t = threading.Thread(target=go, daemon=True, name="fastedit-warm")
    t.start()
    return t


def fast_edit(backend: B.Backend, inp: DraftInputs, payload: dict, instruction: str, *, model: str, thread_turns: list[dict] | None = None,
              progress: Callable | None = None, cancel: Any = None, max_repairs: int = 1, timeout: float = 240.0) -> tuple[B.TurnResult, B.Scope]:
    """One storyboard turn. Raises `DraftError` for a scope that cannot be used and `bti.script.providers.ProviderError` for a model that
    could not answer; everything else is in the returned `TurnResult`."""
    doc, rev = backend.read("storyboard")
    scope = storyboard_scope(inp, doc, payload)
    facts = backend.adapter("storyboard").facts(doc)
    warm = _warm(inp)
    prompt = build_briefing(inp, doc, facts, scope, instruction, thread_turns)
    res = B.run_turn("storyboard", backend, instruction=instruction, scope=scope, doc0=doc, rev0=rev, briefing=prompt, model_id=model,
                     progress=progress, cancel=cancel, max_repairs=max_repairs, timeout=timeout, warm=lambda: warm.join(30))
    return res, scope
