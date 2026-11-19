"""The pass criteria of the bench: small functions a program can check on what an agent made.

A criterion is named by its `kind` in a case file, takes the OUTPUTS of the driver of the step (documents read through the app's API: `outline`, `brief`,
`narration`, `storyboard`, `timing`, `before`, `after`, `picks`, `answer`, ...) and parameters from the case, and answers a `Result`:

    passed   True or False
    value    what was measured (a number, a list of the things that failed): the summary shows it, so a reader sees how far off a failure was
    detail   one sentence

A criterion never calls a model and never touches a project: it reads dicts. `needs` names the outputs it cannot do without; when one is missing (the
agent made nothing) the criterion FAILS with "nothing to check". The kinds are listed by `python -m bti.evals list --criteria`; each says its parameters.
"""
from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[2]


@dataclass
class Result:
    passed: bool
    value: Any = None
    detail: str = ""


@dataclass
class Criterion:
    kind: str
    fn: Callable[..., Result]
    needs: tuple[str, ...]
    params: dict[str, dict]            # name -> {type: int|number|str|bool|list, required?: bool, default?: any}
    doc: str


REGISTRY: dict[str, Criterion] = {}


def criterion(kind: str, *, needs: tuple[str, ...] = (), params: dict[str, dict] | None = None):
    def deco(fn: Callable[..., Result]) -> Callable[..., Result]:
        REGISTRY[kind] = Criterion(kind, fn, tuple(needs), params or {}, ((fn.__doc__ or "").strip().split("\n")[0]))
        return fn
    return deco


def P(type_: str, default: Any = None, required: bool = False) -> dict:
    d: dict = {"type": type_, "required": required}
    if default is not None:
        d["default"] = default
    return d


_TYPES = {"int": lambda v: isinstance(v, int) and not isinstance(v, bool), "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
          "str": lambda v: isinstance(v, str), "bool": lambda v: isinstance(v, bool), "list": lambda v: isinstance(v, list), "dict": lambda v: isinstance(v, dict)}


def check_spec(spec: Any) -> list[str]:
    """The problems of one criterion entry of a case (an empty list when it is fine)."""
    if not isinstance(spec, dict):
        return ["a criterion must be an object"]
    out = []
    if not isinstance(spec.get("id"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", spec.get("id") or ""):
        out.append("`id` must be a short word of letters, digits, - and _")
    c = REGISTRY.get(spec.get("kind"))
    if c is None:
        return out + ["unknown kind %r (python -m bti.evals list --criteria)" % (spec.get("kind"),)]
    for k in spec:
        if k not in ("id", "kind") and k not in c.params:
            out.append("%s: %r is not a parameter of this kind (it takes: %s)" % (spec.get("id"), k, ", ".join(c.params) or "none"))
    for name, p in c.params.items():
        if name not in spec:
            if p.get("required"):
                out.append("%s: parameter %r is required" % (spec.get("id"), name))
        elif not _TYPES[p["type"]](spec[name]):
            out.append("%s: parameter %r must be %s" % (spec.get("id"), name, p["type"]))
    return out


def evaluate(spec: dict, outputs: dict) -> dict:
    """Run one criterion entry on the outputs: {id, kind, passed, value, detail}."""
    c = REGISTRY[spec["kind"]]
    params = {n: p["default"] for n, p in c.params.items() if "default" in p}
    params.update({k: v for k, v in spec.items() if k in c.params})
    head = {"id": spec["id"], "kind": spec["kind"]}
    missing = [n for n in c.needs if outputs.get(n) is None]
    if missing:
        return {**head, "passed": False, "value": None, "detail": "nothing to check: the agent made no %s" % ", ".join(missing)}
    try:
        r = c.fn(outputs, **params)
    except Exception as e:      # noqa: BLE001 - a criterion that cannot read the output is a failed criterion, never a crashed run
        return {**head, "passed": False, "value": None, "detail": "the check could not read the output: %s: %s" % (type(e).__name__, str(e)[:160])}
    return {**head, "passed": bool(r.passed), "value": r.value, "detail": r.detail}


def evaluate_all(specs: list[dict], outputs: dict) -> list[dict]:
    return [evaluate(s, outputs) for s in specs]


def _words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)?", text or "", re.UNICODE)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s.strip()]


def _between(v: float, lo: float | None, hi: float | None) -> bool:
    return (lo is None or v >= lo) and (hi is None or v <= hi)


def _ok(passed: bool, value: Any, yes: str, no: str) -> Result:
    return Result(bool(passed), value, yes if passed else no)


# ================================================================================================================================== the outline
def _outline(o: dict) -> dict:
    return o["outline"]


def _known_paragraphs(brief: dict | None) -> tuple[set[str], set[str]]:
    """(the ids of the paragraphs of the included sources, those of the excluded ones) from `GET .../brief`; empty sets when there is no brief."""
    inc, exc = set(), set()
    for s in (brief or {}).get("sources") or []:
        ids = {p["id"] for p in s.get("paragraphs") or [] if isinstance(p, dict) and p.get("id")}
        (inc if s.get("included") else exc).update(ids)
    return inc, exc


@criterion("outline.chapters_between", needs=("outline",), params={"min": P("int", required=True), "max": P("int", required=True)})
def outline_chapters_between(o, min, max):
    """The outline has between `min` and `max` chapters."""
    n = len(_outline(o).get("chapters") or [])
    return _ok(min <= n <= max, n, "%d chapters" % n, "%d chapters, wanted %d to %d" % (n, min, max))


@criterion("outline.every_chapter_cites_a_source", needs=("outline", "brief"))
def outline_every_chapter_cites_a_source(o):
    """Every chapter uses at least one fact, and every fact it uses cites a paragraph of an included source of the dossier."""
    ol = _outline(o)
    inc, _ = _known_paragraphs(o["brief"])
    facts = {f["id"]: f for f in ol.get("facts") or []}
    bad = []
    for c in ol.get("chapters") or []:
        used = [facts[f] for f in c.get("facts") or [] if f in facts]
        if not used or not all(any(s in inc for s in f.get("sources") or []) for f in used):
            bad.append(c.get("id"))
    return _ok(not bad, bad, "every chapter cites the dossier", "chapters without a source of the dossier: %s" % ", ".join(map(str, bad)))


@criterion("outline.facts_sourced", needs=("outline", "brief"), params={"min_share": P("number", 1.0)})
def outline_facts_sourced(o, min_share):
    """At least `min_share` of the facts cite only paragraphs that exist in the included sources of the dossier (and at least one)."""
    facts = _outline(o).get("facts") or []
    inc, _ = _known_paragraphs(o["brief"])
    good = [f for f in facts if f.get("sources") and all(s in inc for s in f["sources"])]
    share = len(good) / len(facts) if facts else 0.0
    return _ok(share >= min_share, round(share, 3), "%d of %d facts are sourced" % (len(good), len(facts)), "only %d of %d facts are sourced (%.0f%%)" % (len(good), len(facts), share * 100))


@criterion("outline.no_excluded_source", needs=("outline", "brief"))
def outline_no_excluded_source(o):
    """No fact cites a paragraph of a source the owner excluded."""
    _, exc = _known_paragraphs(o["brief"])
    bad = sorted({f["id"] for f in _outline(o).get("facts") or [] if any(s in exc for s in f.get("sources") or [])})
    return _ok(not bad, bad, "no excluded source is cited", "facts that cite an excluded source: %s" % ", ".join(bad))


@criterion("outline.no_error_issues", needs=("outline",))
def outline_no_error_issues(o):
    """The outline's own checks (the "Kiểm tra" list) hold no error."""
    errs = [i for i in o.get("issues") or [] if i.get("level") == "error"]
    return _ok(not errs, [i.get("code") for i in errs], "no error", "errors: %s" % ", ".join(str(i.get("code")) for i in errs))


@criterion("outline.warnings_at_most", needs=("outline",), params={"max": P("int", required=True)})
def outline_warnings_at_most(o, max):
    """The outline's checks hold at most `max` warnings."""
    n = [i.get("code") for i in o.get("issues") or [] if i.get("level") in ("warning", "warn")]
    return _ok(len(n) <= max, n, "%d warnings" % len(n), "%d warnings (%s), at most %d" % (len(n), ", ".join(map(str, n[:6])), max))


@criterion("outline.budget_near_target", needs=("outline",), params={"tolerance": P("number", 0.15)})
def outline_budget_near_target(o, tolerance):
    """The chapter budgets add up to the target of words within `tolerance`."""
    ol = _outline(o)
    total, target = sum(int(c.get("word_budget") or 0) for c in ol.get("chapters") or []), int(ol.get("target_words") or 0)
    ratio = total / target if target else 0.0
    return _ok(target > 0 and abs(ratio - 1) <= tolerance, round(ratio, 3), "budgets %d of target %d" % (total, target), "budgets %d against a target of %d (%.0f%% off)" % (total, target, abs(ratio - 1) * 100))


@criterion("outline.chapter_budget_between", needs=("outline",), params={"min": P("int", required=True), "max": P("int", required=True)})
def outline_chapter_budget_between(o, min, max):
    """Every chapter's word budget is between `min` and `max`."""
    bad = {c.get("id"): c.get("word_budget") for c in _outline(o).get("chapters") or [] if not _between(int(c.get("word_budget") or 0), min, max)}
    return _ok(not bad, bad, "every budget is between %d and %d" % (min, max), "budgets out of range: %s" % json.dumps(bad))


@criterion("outline.thesis_and_hooks", needs=("outline",), params={"hooks": P("int", 3)})
def outline_thesis_and_hooks(o, hooks):
    """The outline has a thesis that is a question, at least `hooks` openings, and one of them is chosen."""
    ol = _outline(o)
    th = (ol.get("thesis") or "").strip()
    opts = ol.get("hook_options") or []
    chosen = ol.get("hook_choice") in {h.get("id") for h in opts}
    ok = bool(th.endswith("?")) and len(opts) >= hooks and chosen
    return _ok(ok, {"thesis_is_question": th.endswith("?"), "hooks": len(opts), "chosen": chosen}, "thesis, %d hooks, one chosen" % len(opts), "thesis a question: %s; hooks: %d (wanted %d); chosen: %s" % (th.endswith("?"), len(opts), hooks, chosen))


@criterion("outline.disputed_facts_have_conflict", needs=("outline",))
def outline_disputed_facts_have_conflict(o):
    """Every fact marked disputed says what the sources disagree about."""
    bad = [f["id"] for f in _outline(o).get("facts") or [] if f.get("certainty") == "disputed" and not (f.get("conflict") or "").strip()]
    return _ok(not bad, bad, "every disputed fact has its conflict", "disputed facts without a conflict: %s" % ", ".join(bad))


@criterion("outline.facts_all_used", needs=("outline",), params={"min_share": P("number", 0.9)})
def outline_facts_all_used(o, min_share):
    """At least `min_share` of the facts are used by a chapter."""
    ol = _outline(o)
    used = {f for c in ol.get("chapters") or [] for f in c.get("facts") or []}
    facts = [f["id"] for f in ol.get("facts") or []]
    share = len([f for f in facts if f in used]) / len(facts) if facts else 0.0
    return _ok(share >= min_share, round(share, 3), "%.0f%% of the facts are used" % (share * 100), "only %.0f%% of the facts are used by a chapter" % (share * 100))


@criterion("outline.roles", needs=("outline",), params={"first": P("str", "cold_open"), "last": P("str", "closing")})
def outline_roles(o, first, last):
    """The first chapter has the role `first` (a cold open) and the last one `last` (a closing)."""
    ch = _outline(o).get("chapters") or []
    got = [ch[0].get("role"), ch[-1].get("role")] if ch else [None, None]
    return _ok(got == [first, last], got, "opens with %s, closes with %s" % (first, last), "roles are %s, wanted %s and %s" % (got, first, last))


# ================================================================================================================================= the narration
def _beats(n: dict) -> list[tuple[str, dict]]:
    return [(c["id"], b) for c in (n["narration"].get("chapters") or []) for b in c.get("beats") or []]


@criterion("narration.words_within_target", needs=("narration", "outline"), params={"tolerance": P("number", 0.15)})
def narration_words_within_target(o, tolerance):
    """The narration has as many words as the outline's target, within `tolerance`."""
    words = sum(len(_words(b.get("text"))) for _, b in _beats(o))
    target = int(_outline(o).get("target_words") or 0)
    ratio = words / target if target else 0.0
    return _ok(target > 0 and abs(ratio - 1) <= tolerance, round(ratio, 3), "%d words for a target of %d" % (words, target), "%d words for a target of %d (%.0f%% off)" % (words, target, abs(ratio - 1) * 100))


@criterion("narration.minutes_at_least", needs=("narration",), params={"minutes": P("number", required=True), "wps": P("number", 2.41)})
def narration_minutes_at_least(o, minutes, wps):
    """Read aloud at `wps` words per second (2.41 is the measured speed of the voice) the narration lasts at least `minutes` minutes."""
    words = sum(len(_words(b.get("text"))) for _, b in _beats(o))
    m = words / wps / 60.0
    return _ok(m >= minutes, round(m, 1), "%d words, %.1f minutes" % (words, m), "%d words are %.1f minutes, wanted at least %s" % (words, m, minutes))


@criterion("narration.max_beat_words", needs=("narration",), params={"max": P("int", 90)})
def narration_max_beat_words(o, max):
    """No line (beat) is longer than `max` words."""
    longest = [(b["id"], len(_words(b.get("text")))) for _, b in _beats(o)]
    bad = [x for x in longest if x[1] > max]
    return _ok(not bad, bad[:8] or (sorted(x[1] for x in longest)[-1] if longest else 0), "no line over %d words" % max, "lines over %d words: %s" % (max, ", ".join("%s (%d)" % x for x in bad[:6])))


@criterion("narration.max_sentence_words", needs=("narration",), params={"max": P("int", 28)})
def narration_max_sentence_words(o, max):
    """No sentence is longer than `max` words."""
    bad = []
    for _, b in _beats(o):
        for s in _sentences(b.get("text")):
            if len(_words(s)) > max:
                bad.append((b["id"], len(_words(s))))
    return _ok(not bad, bad[:8], "no sentence over %d words" % max, ("%d sentences over %d words (first: %s)" % (len(bad), max, bad[0])) if bad else "")


@criterion("narration.median_sentence_words", needs=("narration",), params={"min": P("int", 8), "max": P("int", 22)})
def narration_median_sentence_words(o, min, max):
    """The median sentence has between `min` and `max` words (spoken storytelling is neither clipped nor long-winded)."""
    lens = [len(_words(s)) for _, b in _beats(o) for s in _sentences(b.get("text"))]
    med = statistics.median(lens) if lens else 0
    return _ok(_between(med, min, max), med, "median sentence %s words" % med, "median sentence %s words, wanted %d to %d" % (med, min, max))


@criterion("narration.no_error_issues", needs=("narration",))
def narration_no_error_issues(o):
    """The narration's own checks (the "Kiểm tra" list) hold no error."""
    errs = [i for i in o.get("issues") or [] if i.get("level") == "error"]
    return _ok(not errs, [i.get("code") for i in errs], "no error", "errors: %s" % ", ".join(str(i.get("code")) for i in errs[:8]))


@criterion("narration.chapters_match_outline", needs=("narration", "outline"))
def narration_chapters_match_outline(o):
    """The narration has the outline's chapters, in the outline's order, each with some text."""
    want = [c["id"] for c in _outline(o).get("chapters") or []]
    got = [c["id"] for c in o["narration"].get("chapters") or [] if any((b.get("text") or "").strip() for b in c.get("beats") or [])]
    return _ok(got == want, got, "the %d chapters of the outline" % len(want), "chapters %s, the outline has %s" % (got, want))


@criterion("narration.chapter_budgets", needs=("narration", "outline"), params={"tolerance": P("number", 0.3)})
def narration_chapter_budgets(o, tolerance):
    """Every chapter is as long as its budget, within `tolerance`."""
    budget = {c["id"]: int(c.get("word_budget") or 0) for c in _outline(o).get("chapters") or []}
    bad = {}
    for c in o["narration"].get("chapters") or []:
        w = sum(len(_words(b.get("text"))) for b in c.get("beats") or [])
        if budget.get(c["id"]) and abs(w / budget[c["id"]] - 1) > tolerance:
            bad[c["id"]] = [w, budget[c["id"]]]
    return _ok(not bad, bad, "every chapter is near its budget", "chapters off budget (words, budget): %s" % json.dumps(bad))


@criterion("narration.every_beat_has_show", needs=("narration",))
def narration_every_beat_has_show(o):
    """Every line says what is on screen (the pictures step needs it)."""
    bad = [b["id"] for _, b in _beats(o) if not b.get("show")]
    return _ok(not bad, bad[:10], "every line has a hint of what is shown", "%d lines without a hint: %s" % (len(bad), ", ".join(bad[:6])))


@criterion("narration.facts_in_outline", needs=("narration", "outline"))
def narration_facts_in_outline(o):
    """Every fact a line cites is in the outline's fact table."""
    known = {f["id"] for f in _outline(o).get("facts") or []}
    bad = sorted({f for _, b in _beats(o) for f in b.get("facts") or [] if f not in known})
    return _ok(not bad, bad, "every cited fact exists", "cited facts that are not in the outline: %s" % ", ".join(bad))


_MARKUP = re.compile(r"(\b[A-Z]{3}-\d{2,3}\b|\bf\d{2,}\b|\*\*|__|`|^\s*#|\[[^\]]{1,80}\]|<[^>]{1,40}>|\|)", re.M)


@criterion("narration.spoken_words_only", needs=("narration",))
def narration_spoken_words_only(o):
    """No line holds anything a voice cannot say: source ids, fact ids, markup, brackets, bars."""
    bad = [b["id"] for _, b in _beats(o) if _MARKUP.search(b.get("text") or "")]
    return _ok(not bad, bad[:10], "spoken words only", "lines with source ids or markup: %s" % ", ".join(bad[:8]))


@criterion("narration.copied_runs_at_most", needs=("narration",), params={"max_share": P("number", 0.25)})
def narration_copied_runs_at_most(o, max_share):
    """At most `max_share` of the words sit in runs of eight or more words copied from the sources (the app's own `overlap` information)."""
    info = next((i for i in o.get("issues") or [] if i.get("code") == "overlap"), None)
    if info is None:
        return Result(False, None, "the app gave no `overlap` information (no brief)")
    m = re.search(r"(\d+)%", info.get("message") or "")
    share = int(m.group(1)) / 100 if m else 0.0
    return _ok(share <= max_share, share, "%.0f%% copied" % (share * 100), "%.0f%% of the words are copied runs, at most %.0f%%" % (share * 100, max_share * 100))


# ===================================================================================================================== the storyboard (draft)
_REGISTRY_CACHE: dict[str, dict] = {}


def _technique_usage() -> dict[str, str]:
    if "u" not in _REGISTRY_CACHE:
        reg = json.loads((REPO / "style" / "gae" / "techniques.json").read_text(encoding="utf-8"))["techniques"]
        _REGISTRY_CACHE["u"] = {t["id"]: t.get("channel_usage") or "" for t in reg}
        _REGISTRY_CACHE["k"] = {t["id"]: t.get("kind") or "" for t in reg}
    return _REGISTRY_CACHE["u"]


def _technique_kind() -> dict[str, str]:
    _technique_usage()
    return _REGISTRY_CACHE["k"]


def shots_of(sb: dict | None) -> list[dict]:
    return [s for s in (sb or {}).get("shots") or [] if isinstance(s, dict)]


def shot_spans(sb: dict, timing: dict | None = None) -> list[tuple[dict, float, float]]:
    """[(shot, start s, end s)] of the shots that have times: the resolved storyboard of GET /api/projects/{pid} carries `_t0` and `_t1` on every shot; a storyboard
    that is not resolved is resolved here from the timing's words ({"w": i, "off": s} anchors and {"t": s})."""
    words = (timing or {}).get("words") or []

    def at(a: Any) -> float | None:
        if not isinstance(a, dict):
            return None
        if isinstance(a.get("_t"), (int, float)):
            return float(a["_t"])
        if isinstance(a.get("t"), (int, float)):
            return float(a["t"])
        if isinstance(a.get("w"), int) and 0 <= a["w"] < len(words):
            return float(words[a["w"]]["s"]) + float(a.get("off") or 0.0)
        return None
    shots = shots_of(sb)
    end = at((sb or {}).get("end"))
    out = []
    for i, s in enumerate(shots):
        t0 = s.get("_t0") if isinstance(s.get("_t0"), (int, float)) else at(s.get("start"))
        t1 = s.get("_t1") if isinstance(s.get("_t1"), (int, float)) else (at(shots[i + 1].get("start")) if i + 1 < len(shots) else end)
        if t0 is not None and t1 is not None:
            out.append((s, float(t0), float(t1)))
    return out


def _base_shots(sb: dict) -> list[dict]:
    kinds = _technique_kind()
    return [s for s in shots_of(sb) if kinds.get(s.get("technique"), "base") in ("base", "")]


@criterion("draft.no_error_issues", needs=("storyboard",))
def draft_no_error_issues(o):
    """The storyboard the draft made holds no error-level issue (the engine's own validation)."""
    errs = [i for i in o.get("issues") or [] if i.get("level") == "error"]
    return _ok(not errs, [i.get("code") for i in errs][:10], "no error", "%d errors, first: %s" % (len(errs), errs[0].get("message") if errs else ""))


@criterion("draft.shot_pace", needs=("storyboard",), params={"median_min": P("number", 5.0), "median_max": P("number", 9.0), "shortest": P("number", 1.5),
                                                              "longest": P("number", 30.0), "max_share_under_4": P("number", 0.25)})
def draft_shot_pace(o, median_min, median_max, shortest, longest, max_share_under_4):
    """About one shot every seven seconds: the median shot is between `median_min` and `median_max` seconds, none shorter than `shortest` or longer than `longest`, and few under four."""
    spans = [(t1 - t0) for s, t0, t1 in shot_spans(o["storyboard"], o.get("timing")) if s.get("technique") and not str(s["technique"]).startswith(("X-CARD", "ID-"))]
    if not spans:
        return Result(False, None, "no shot has a time")
    med, under = statistics.median(spans), sum(1 for d in spans if d < 4) / len(spans)
    ok = _between(med, median_min, median_max) and min(spans) >= shortest and max(spans) <= longest and under <= max_share_under_4
    return _ok(ok, {"median": round(med, 2), "shortest": round(min(spans), 2), "longest": round(max(spans), 2), "share_under_4": round(under, 2)},
               "median %.1f s over %d shots" % (med, len(spans)),
               "median %.1f s, shortest %.1f s, longest %.1f s, %.0f%% under 4 s (wanted median %s to %s, none under %s or over %s, at most %.0f%% under 4 s)"
               % (med, min(spans), max(spans), under * 100, median_min, median_max, shortest, longest, max_share_under_4 * 100))


@criterion("draft.distinct_techniques_at_least", needs=("storyboard",), params={"k": P("int", required=True)})
def draft_distinct_techniques_at_least(o, k):
    """The base shots use at least `k` different techniques."""
    used = sorted({s["technique"] for s in _base_shots(o["storyboard"]) if s.get("technique")})
    return _ok(len(used) >= k, used, "%d techniques" % len(used), "%d techniques (%s), wanted %d" % (len(used), ", ".join(used), k))


@criterion("draft.core_techniques", needs=("storyboard",), params={"min_share": P("number", 0.6)})
def draft_core_techniques(o, min_share):
    """At least `min_share` of the base shots use a technique the channel classes as core, and none uses a shorts-only one."""
    usage = _technique_usage()
    shots = _base_shots(o["storyboard"])
    core = [s for s in shots if usage.get(s.get("technique")) == "core"]
    shorts = sorted({s["technique"] for s in shots if usage.get(s.get("technique")) == "shorts_only"})
    share = len(core) / len(shots) if shots else 0.0
    return _ok(share >= min_share and not shorts, {"core_share": round(share, 2), "shorts_only": shorts}, "%.0f%% core shots" % (share * 100),
               "%.0f%% core shots (wanted %.0f%%)%s" % (share * 100, min_share * 100, ("; shorts-only techniques used: " + ", ".join(shorts)) if shorts else ""))


@criterion("draft.covers_the_narration", needs=("storyboard", "timing"), params={"slack": P("number", 0.25)})
def draft_covers_the_narration(o, slack):
    """The shots start at the start of the voice, follow each other with no gap, and the last one runs to the end."""
    spans = shot_spans(o["storyboard"], o["timing"])
    if not spans:
        return Result(False, None, "no shot has a time")
    dur = float(o["timing"].get("duration") or 0.0)
    first, last_end = spans[0][1], spans[-1][2]
    gaps = [round(b[1] - a[2], 2) for a, b in zip(spans, spans[1:]) if abs(b[1] - a[2]) > 0.05]
    ok = first <= slack and not gaps and last_end >= dur - slack
    return _ok(ok, {"first": round(first, 2), "last_end": round(last_end, 2), "duration": dur, "gaps": gaps[:5]}, "covers 0 to %.0f s" % last_end,
               "starts at %.2f s, ends at %.2f of %.2f s, %d gaps" % (first, last_end, dur, len(gaps)))


@criterion("draft.context_lines_avoid_the_main_painting", needs=("storyboard", "picks"))
def draft_context_lines_avoid_the_main_painting(o):
    """A shot whose intent is `context` (a person, a place, another work) does not show the main painting."""
    main = (o["picks"] or {}).get("main_asset")
    bad = [s.get("id") for s in shots_of(o["storyboard"]) if s.get("intent") == "context" and any((v or {}).get("asset") == main for v in (s.get("slots") or {}).values())]
    return _ok(not bad, bad, "no context shot shows the main painting", "context shots that show the main painting: %s" % ", ".join(map(str, bad[:8])))


def _strings(v: Any):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x)


@criterion("draft.no_narration_on_screen", needs=("storyboard", "timing"), params={"run": P("int", 5)})
def draft_no_narration_on_screen(o, run):
    """No parameter holds `run` or more words in a row copied from the narration (no subtitles on screen)."""
    spoken = [re.sub(r"\W+", "", w.get("w", "")).lower() for w in o["timing"].get("words") or []]
    grams = {tuple(spoken[i:i + run]) for i in range(len(spoken) - run + 1)}
    bad = []
    for s in shots_of(o["storyboard"]):
        for txt in list(_strings(s.get("params"))) + [t for ov in s.get("overlays") or [] for t in _strings(ov.get("params"))]:
            w = [re.sub(r"\W+", "", x).lower() for x in txt.split()]
            if any(tuple(w[i:i + run]) in grams for i in range(len(w) - run + 1)):
                bad.append(s.get("id"))
                break
    return _ok(not bad, bad, "no narration on screen", "shots with the narration's words in a parameter: %s" % ", ".join(map(str, bad[:8])))


@criterion("draft.picks_are_used", needs=("storyboard", "picks", "timing"), params={"min_share": P("number", 0.8)})
def draft_picks_are_used(o, min_share):
    """For at least `min_share` of the lines where the owner picked a picture, a shot of that line shows it."""
    spans = shot_spans(o["storyboard"], o["timing"])
    beats = {b["id"]: b for b in o["timing"].get("beats") or []}
    want = used = 0
    for bid, b in ((o["picks"] or {}).get("beats") or {}).items():
        items = [i for i in b.get("items") or [] if i.get("asset")]
        tb = beats.get(bid)
        if not items or tb is None:
            continue
        want += 1
        shown = {(v or {}).get("asset") for s, t0, t1 in spans if t1 > tb["start"] and t0 < tb["end"] for v in (s.get("slots") or {}).values()}
        if any(i["asset"] in shown for i in items):
            used += 1
    share = used / want if want else 1.0
    return _ok(share >= min_share, round(share, 2), "%d of %d picked lines show their picture" % (used, want), "only %d of %d picked lines show their picture" % (used, want))


@criterion("draft.every_shot_has_a_reason", needs=("storyboard",), params={"min_share": P("number", 0.9)})
def draft_every_shot_has_a_reason(o, min_share):
    """At least `min_share` of the shots carry a note (the reason the owner reads next to the shot)."""
    shots = [s for s in shots_of(o["storyboard"]) if not str(s.get("technique") or "").startswith(("X-CARD", "ID-"))]
    n = sum(1 for s in shots if (s.get("note") or "").strip())
    share = n / len(shots) if shots else 0.0
    return _ok(share >= min_share, round(share, 2), "%d of %d shots have a note" % (n, len(shots)), "only %d of %d shots have a note" % (n, len(shots)))


@criterion("draft.locked_shots_unchanged", needs=("storyboard", "before"))
def draft_locked_shots_unchanged(o):
    """A shot the owner locked is exactly as it was before the draft."""
    def core(s):
        return {k: v for k, v in s.items() if not k.startswith("_")}
    after = {s.get("id"): core(s) for s in shots_of(o["storyboard"])}
    bad = [s.get("id") for s in shots_of(o["before"]) if s.get("locked") and after.get(s.get("id")) != core(s)]
    return _ok(not bad, bad, "locked shots are untouched", "locked shots that changed: %s" % ", ".join(map(str, bad[:8])))


# ============================================================================================================================ an edit by words
def _scope_ids(o: dict) -> set[str]:
    """The ids of the shots the request was about: the shots it names, the shots of the chapter (by time), or every shot."""
    sc = o.get("scope") or {}
    before = o["before"]
    if sc.get("all"):
        return {s.get("id") for s in shots_of(before)}
    if sc.get("shots"):
        return set(sc["shots"])
    if sc.get("chapter"):
        ch = next((c for c in (o.get("timing") or {}).get("chapters") or [] if c.get("id") == sc["chapter"]), None)
        if ch:
            return {s.get("id") for s, t0, t1 in shot_spans(before, o.get("timing")) if t0 >= float(ch["start"]) - 0.01 and t0 < float(ch["end"]) + 0.01}
    return set()


def _plain(s: dict) -> dict:
    return {k: v for k, v in s.items() if not k.startswith("_")}


@criterion("edit.only_scope_changed", needs=("before", "after"))
def edit_only_scope_changed(o):
    """Nothing outside the scope of the request changed: no other shot is different, added or removed, and a locked shot is untouched."""
    scope = _scope_ids(o)
    b = {s.get("id"): _plain(s) for s in shots_of(o["before"])}
    a = {s.get("id"): _plain(s) for s in shots_of(o["after"])}
    touched = sorted(i for i in set(a) | set(b) if a.get(i) != b.get(i) and i not in scope)
    locked = sorted(i for i, s in b.items() if s.get("locked") and a.get(i) != s)
    return _ok(not touched and not locked, {"outside": touched[:10], "locked": locked[:10]}, "only the shots in scope changed", "changed outside the scope: %s; locked shots changed: %s" % (touched[:8], locked[:8]))


@criterion("edit.changed_something_in_scope", needs=("before", "after"))
def edit_changed_something_in_scope(o):
    """At least one shot of the scope is different after the request."""
    scope = _scope_ids(o)
    b = {s.get("id"): _plain(s) for s in shots_of(o["before"])}
    a = {s.get("id"): _plain(s) for s in shots_of(o["after"])}
    changed = sorted(i for i in scope if a.get(i) != b.get(i))
    return _ok(bool(changed), changed[:10], "%d shots changed" % len(changed), "nothing in the scope changed")


def _zoom_rate(shot: dict, span: tuple[float, float]) -> float | None:
    cams = [v for v in (shot.get("params") or {}).values() if isinstance(v, list) and v and isinstance(v[0], dict) and "zoom" in v[0]]
    if not cams or span[1] <= span[0]:
        return None
    keys = cams[0]
    return abs(float(keys[-1]["zoom"]) - float(keys[0]["zoom"])) / (span[1] - span[0])


def _metric(sb: dict, timing: dict | None, shot_id: str, metric: str) -> float | None:
    spans = {s.get("id"): (s, t0, t1) for s, t0, t1 in shot_spans(sb, timing)}
    if shot_id not in spans:
        return None
    s, t0, t1 = spans[shot_id]
    if metric == "zoom_rate":
        return _zoom_rate(s, (t0, t1))
    if metric == "duration":
        return t1 - t0
    if metric == "overlay_count":
        return float(len(s.get("overlays") or []))
    if metric.startswith("param:"):
        v = (s.get("params") or {}).get(metric[6:])
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    raise ValueError("unknown metric %r" % metric)


@criterion("edit.metric_moved", needs=("before", "after"), params={"metric": P("str", required=True), "direction": P("str", required=True), "min_shots": P("int", 1),
                                                                   "shots": P("list")})
def edit_metric_moved(o, metric, direction, min_shots, shots=None):
    """In the shots of the scope that have it, a measure got larger or smaller (`direction` increase | decrease): `zoom_rate` (zoom change per second of a camera shot: a slower zoom is a smaller rate), `duration`, `overlay_count` or `param:<name>`."""
    ids = [i for i in (shots or sorted(_scope_ids(o))) if i]
    moved, wrong = [], []
    for i in ids:
        x, y = _metric(o["before"], o.get("timing"), i, metric), _metric(o["after"], o.get("timing"), i, metric)
        if x is None or y is None:
            continue
        (moved if (y > x + 1e-9 if direction == "increase" else y < x - 1e-9) else wrong).append((i, round(x, 4), round(y, 4)))
    return _ok(len(moved) >= min_shots and not [w for w in wrong if w[1] != w[2]], {"moved": moved[:8], "not_moved": wrong[:8]},
               "%s went %s in %d shots" % (metric, "up" if direction == "increase" else "down", len(moved)),
               "%s did not go %s: moved %d shots, wanted %d; other: %s" % (metric, "up" if direction == "increase" else "down", len(moved), min_shots, wrong[:4]))


@criterion("edit.no_error_issues", needs=("after",))
def edit_no_error_issues(o):
    """The storyboard after the request holds no error-level issue."""
    errs = [i for i in o.get("issues") or [] if i.get("level") == "error"]
    return _ok(not errs, [i.get("code") for i in errs][:10], "no error", "%d errors after the edit" % len(errs))


def _same_document(before: Any, after: Any) -> bool:
    """Nothing in the document changed: the shots of a storyboard, or (the picks have no shots) the picks document itself without its approval."""
    if before is None or after is None:
        return True
    if isinstance(before, dict) and isinstance(after, dict) and "shots" not in before and "shots" not in after:
        return {k: v for k, v in before.items() if k != "approval"} == {k: v for k, v in after.items() if k != "approval"}
    return [_plain(s) for s in shots_of(before)] == [_plain(s) for s in shots_of(after)]


@criterion("edit.answered_cannot", needs=("answer",), params={"codes": P("list")})
def edit_answered_cannot(o, codes=None):
    """A request the project cannot do is answered as `cannot` (or one of `codes`) with a sentence that says why, and nothing changed. The prompt boxes answer
    through typed operations: a request they cannot do ends the turn as `no_change` (the model said `cannot`, nothing was written) or `escalate` (it needs a picture
    the project does not have); the default `codes` are those and the older `cannot` / `edit_no_change`."""
    a = o["answer"]
    codes = codes or ["cannot", "no_change", "edit_no_change", "escalate"]
    code = a.get("code") or a.get("status")
    reason = str(a.get("error") or a.get("reason") or a.get("summary") or "").strip()
    unchanged = _same_document(o.get("before"), o.get("after"))
    return _ok(code in codes and bool(reason) and unchanged, {"code": code, "reason": reason[:120], "unchanged": unchanged}, "answered %s: %s" % (code, reason[:80]),
               "answered %r (wanted one of %s), reason given: %s, nothing changed: %s" % (code, codes, bool(reason), unchanged))


# ============================================================================================================================== the picks
def _picks_doc(o: dict) -> dict:
    return o["picks"] if isinstance(o.get("picks"), dict) else {}


@criterion("picks.every_beat_decided", needs=("picks", "beat_ids"), params={"min_share": P("number", 1.0)})
def picks_every_beat_decided(o, min_share):
    """At least `min_share` of the lines of the narration have a picture or are marked skip."""
    beats = _picks_doc(o).get("beats") or {}
    ids = o["beat_ids"]
    done = [i for i in ids if (beats.get(i) or {}).get("items") or (beats.get(i) or {}).get("status") == "skip"]
    share = len(done) / len(ids) if ids else 0.0
    return _ok(share >= min_share, round(share, 3), "%d of %d lines decided" % (len(done), len(ids)), "%d of %d lines have a picture or a skip" % (len(done), len(ids)))


@criterion("picks.main_painting_chosen", needs=("picks",))
def picks_main_painting_chosen(o):
    """The picks name a main painting that exists in the list of pictures."""
    d = _picks_doc(o)
    return _ok(bool(d.get("main_asset")) and d.get("main_asset") in (d.get("assets") or {}), d.get("main_asset"), "main painting %s" % d.get("main_asset"), "no main painting")


@criterion("picks.no_error_issues", needs=("picks",))
def picks_no_error_issues(o):
    """The picks' own checks hold no error (a missing file, an unknown picture or region)."""
    errs = [i for i in o.get("issues") or [] if i.get("level") == "error"]
    return _ok(not errs, [i.get("code") for i in errs][:10], "no error", "%d errors" % len(errs))


@criterion("picks.credited", needs=("picks",))
def picks_credited(o):
    """Every picture that came from outside the book says where it came from (source and licence)."""
    bad = [k for k, a in (_picks_doc(o).get("assets") or {}).items() if a.get("kind") != "mask" and not ((a.get("credit") or {}).get("source") and (a.get("credit") or {}).get("licence"))]
    return _ok(not bad, bad[:10], "every picture is credited", "pictures without a source and licence: %s" % ", ".join(bad[:8]))


@criterion("picks.variety_at_least", needs=("picks",), params={"k": P("int", required=True)})
def picks_variety_at_least(o, k):
    """The picks use at least `k` different pictures across the lines."""
    used = {i["asset"] for b in (_picks_doc(o).get("beats") or {}).values() for i in b.get("items") or [] if i.get("asset")}
    return _ok(len(used) >= k, sorted(used), "%d different pictures" % len(used), "%d different pictures, wanted %d" % (len(used), k))


@criterion("picks.no_flagged_picture", needs=("picks",))
def picks_no_flagged_picture(o):
    """No picture is flagged (small, licence, and so on)."""
    bad = [i.get("asset") for i in o.get("issues") or [] if i.get("code") == "asset_flag"]
    return _ok(not bad, bad, "no flagged picture", "flagged pictures: %s" % ", ".join(map(str, bad[:8])))


@criterion("picks.only_scope_changed", needs=("before", "after"), params={"beats": P("list", required=True)})
def picks_only_scope_changed(o, beats):
    """Only the lines named in `beats` have different picks after the request (the main painting and the other lines are untouched)."""
    b, a = _picks_doc({"picks": o["before"]}), _picks_doc({"picks": o["after"]})
    bb, ab = b.get("beats") or {}, a.get("beats") or {}
    changed = sorted(i for i in set(bb) | set(ab) if bb.get(i) != ab.get(i) and i not in set(beats))
    main = b.get("main_asset") == a.get("main_asset")
    return _ok(not changed and main, {"outside": changed[:10], "main_unchanged": main}, "only the named lines changed", "changed outside the scope: %s; main painting kept: %s" % (changed[:8], main))


@criterion("picks.changed_in_scope", needs=("before", "after"), params={"beats": P("list", required=True)})
def picks_changed_in_scope(o, beats):
    """At least one of the lines named in `beats` has different picks after the request."""
    bb, ab = _picks_doc({"picks": o["before"]}).get("beats") or {}, _picks_doc({"picks": o["after"]}).get("beats") or {}
    changed = [i for i in beats if bb.get(i) != ab.get(i)]
    return _ok(bool(changed), changed, "%d lines changed" % len(changed), "nothing changed in the named lines")


def describe() -> list[dict]:
    """Every kind with its parameters and what it needs (`python -m bti.evals list --criteria`)."""
    return [{"kind": c.kind, "needs": list(c.needs), "params": {n: {k: v for k, v in p.items() if k != "required" or v} for n, p in c.params.items()}, "doc": c.doc} for c in REGISTRY.values()]
