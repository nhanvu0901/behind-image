"""The pictures side of the prompt box (step 4, "Chọn hình"): the same turn as step 5 on the picks document.

The model is given the narration lines in scope (their text, their pictures), the project's pictures with their titles, regions and where
each is used, and the picks operations WITHOUT `import` (one call cannot search or look). It can rearrange, add and remove the pictures
and regions the project already has. A request that needs a new picture, or someone to look at a picture, is answered `escalate` with the
reason. The briefing is `skills/picks_edit/FAST.template.md`; the turn itself (dry run inside the scope, one repair, one batch, undo) is
`boxops.py`.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from bti.script.brief import REPO_ROOT

from . import boxops as B
from .inputs import DraftError

TEMPLATE_PATH = REPO_ROOT / "skills" / "picks_edit" / "FAST.template.md"
USED_LIST_MAX = 8          # how many lines `used_in` names before it only counts them


def picks_scope(facts: Any, doc: dict, payload: dict, nv: dict | None = None) -> B.Scope:
    """The owner's selection of narration lines as a `Scope`: `{"beats": [ids]}`, `{"chapter": id}` or `{"all": true}`. Raises `DraftError`
    (`edit_bad_scope`) for one that is empty, unknown, or has no narration to select from."""
    if not isinstance(payload, dict):
        raise DraftError("edit_bad_scope", "scope must be an object")
    if not facts.present or not facts.beat_ids:
        raise DraftError("edit_bad_scope", "the project has no narration lines yet")
    given = [k for k in ("beats", "chapter", "all") if payload.get(k) is not None and payload.get(k) is not False]
    if len(given) != 1:
        raise DraftError("edit_bad_scope", "scope must specify exactly one of beats, chapter or all")
    if payload.get("all"):
        return B.Scope("all", "Cả video", list(facts.beat_ids), list(facts.beat_ids), None, payload=dict(payload))
    if payload.get("chapter") is not None:
        cid = payload["chapter"]
        if not isinstance(cid, str) or cid not in facts.chapters:
            raise DraftError("edit_bad_scope", "no such chapter: %s" % str(cid)[:40])
        title = next((c.get("title") for c in (nv or {}).get("chapters") or [] if c.get("id") == cid), None)
        ids = list(facts.chapters[cid])
        return B.Scope("chapter", "Chương: %s" % (title or cid), ids, ids, {"chapters": [cid]}, chapter=cid, payload=dict(payload))
    beats = payload["beats"]
    if not isinstance(beats, list) or not beats or not all(isinstance(b, str) for b in beats):
        raise DraftError("edit_bad_scope", "beats must be a non-empty list of line ids")
    unknown = [b for b in beats if b not in facts.beat_set]
    if unknown:
        raise DraftError("edit_bad_scope", "unknown lines: %s" % ", ".join(unknown[:5]))
    ids = [b for b in facts.beat_ids if b in set(beats)]
    nums = [facts.beat_no(b) for b in ids]
    words = "Dòng %s đang chọn" % nums[0] if len(ids) == 1 else "%d dòng đang chọn (%s)" % (len(ids), ", ".join(str(n) for n in nums[:6]) + ("…" if len(nums) > 6 else ""))
    return B.Scope("beats", words, ids, ids, {"beats": ids}, payload=dict(payload))


def _compact(o: Any) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def _line_view(facts: Any, nv_beats: dict, doc: dict, bid: str, *, full: bool = True) -> dict:
    rec = (doc.get("beats") or {}).get(bid) or {}
    b = nv_beats.get(bid) or {}
    v: dict[str, Any] = {"id": bid, "n": facts.beat_no(bid), "text": (b.get("text") or "") if full else (b.get("text") or "")[:160]}
    if full:
        if b.get("show"):
            v["show"] = b["show"]
        v["status"] = rec.get("status") or "todo"
        v["items"] = [{k: it.get(k) for k in ("asset", "region", "role", "note") if it.get(k)} for it in rec.get("items") or [] if isinstance(it, dict)]
        if rec.get("note"):
            v["note"] = rec["note"]
    return v


def assets_block(doc: dict) -> str:
    users: dict[str, list[str]] = {}
    for bid, rec in (doc.get("beats") or {}).items():
        for it in (rec or {}).get("items") or []:
            if isinstance(it, dict) and it.get("asset") and bid not in users.setdefault(it["asset"], []):
                users[it["asset"]].append(bid)
    out = {}
    for key, a in (doc.get("assets") or {}).items():
        if not isinstance(a, dict):
            continue
        used = users.get(key, [])
        out[key] = {"title": a.get("title") or key, "artist": a.get("artist") or "", "kind": a.get("kind", "image"),
                    "size": "%sx%s" % (a.get("width"), a.get("height")),
                    "regions": {n: (r or {}).get("label") or "" for n, r in (a.get("regions") or {}).items()},
                    "used_in": used if len(used) <= USED_LIST_MAX else "%d lines" % len(used)}
    return _compact(out) if out else "{}"


def history_block(turns: list[dict] | None) -> str:
    rows = [t for t in (turns or []) if t.get("instruction") and t.get("doc") == "picks"][-3:]
    if not rows:
        return "(no earlier turn)"
    out = []
    for i, t in enumerate(rows, 1):
        said = (t.get("summary") or t.get("reason") or "").strip()
        out.append("Turn %d: owner: %s | outcome: %s%s" % (i, t["instruction"].strip(), t.get("status") or "?", (" | " + said) if said else ""))
    return "\n".join(out)


def build_briefing(facts: Any, nv: dict, doc: dict, scope: B.Scope, instruction: str, thread_turns: list[dict] | None = None) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    nv_beats = {b["id"]: b for c in nv.get("chapters") or [] for b in c.get("beats") or []}
    order = list(facts.beat_ids)
    mine = [order.index(i) for i in scope.ids if i in order]
    first, last = (min(mine), max(mine)) if mine else (0, -1)
    neighbours = []
    for tag, i in (("before", first - 1), ("after", last + 1)):
        neighbours.append("%s: %s" % (tag, _compact(_line_view(facts, nv_beats, doc, order[i], full=False)) if 0 <= i < len(order) else "(none)"))
    main = doc.get("main_asset")
    names = B.allowed_ops("picks", whole_video=scope.whole_video)
    note = ("" if scope.whole_video else
            "\n(`set_main`, `set_region` and `remove_region` are not offered: they belong to the whole video and the owner did not select it.)")
    lang = "English" if B.owner_language(instruction) == "en" else "Vietnamese"
    out = template
    for key, value in {"LANG": lang, "INSTRUCTION": instruction.strip(), "THREAD_HISTORY": history_block(thread_turns),
                       "OPS": B.render_ops("picks", names), "WHOLE_NOTE": note, "SCOPE_WORDS": scope.words,
                       "LINES": "\n".join(_compact(_line_view(facts, nv_beats, doc, i)) for i in scope.ids) or "(none)",
                       "NEIGHBOURS": "\n".join(neighbours), "MAIN": "%s (%s)" % (main, ((doc.get("assets") or {}).get(main) or {}).get("title") or "-") if main else "none chosen",
                       "ASSETS": assets_block(doc), "MAXOPS": str(B.MAX_OPS)}.items():
        out = out.replace("{{%s}}" % key, value)
    return out


def picks_edit(backend: B.Backend, payload: dict, instruction: str, *, model: str, thread_turns: list[dict] | None = None,
               progress: Callable | None = None, cancel: Any = None, max_repairs: int = 1, timeout: float = 240.0) -> tuple[B.TurnResult, B.Scope]:
    """One picks turn. Raises `DraftError` for a scope that cannot be used and `bti.script.providers.ProviderError` for a model that could
    not answer; everything else is in the returned `TurnResult`."""
    from bti.picks import context
    doc, rev = backend.read("picks")
    facts = backend.adapter("picks").facts(doc)
    nv = context.narration_view(backend.pdir)
    scope = picks_scope(facts, doc, payload, nv)
    prompt = build_briefing(facts, nv, doc, scope, instruction, thread_turns)
    res = B.run_turn("picks", backend, instruction=instruction, scope=scope, doc0=doc, rev0=rev, briefing=prompt, model_id=model,
                     progress=progress, cancel=cancel, max_repairs=max_repairs, timeout=timeout)
    return res, scope
