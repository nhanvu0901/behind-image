"""`inputs/techniques.md`: a description of the techniques a model is OFFERED (`offered` of `style/gae/techniques.json`), generated (never hand written) so that it
cannot drift from the registry. For every technique it says in which case to use it (`use_when`), what must exist (`needs`), when never (`never_when`) and one real
sentence (`example`), grouped by the kind of line it serves (the `kinds` of a beat, decided at the pictures step); then its slots and parameters. The hidden techniques
are not listed (using one is the error `technique_not_offered`); the ones the program writes stay in their own short section."""
from __future__ import annotations

import json

from bti.engine import registry as R
from bti.identity import read as read_identity

INTENT_HELP = {
    "establish": "show the whole work or set the scene", "explore": "let the eye travel over the work", "point_at": "name a detail and look at it",
    "isolate": "make one part stand out", "reveal": "uncover something step by step", "compare": "put two or more things side by side",
    "context": "show something around the work (a place, a person, a document)", "quantify": "size, number, measurement",
    "explain_mechanism": "show how something works or was made", "quote": "show a quotation", "structure": "cards, titles, labels",
    "transition": "move from one picture to another",
}
USAGE_ORDER = {"core": 0, "occasional": 1, "rare": 2, "other_series": 3, "shorts_only": 4}
USAGE_HELP = {"core": "core: the channel uses it all the time", "occasional": "occasional: now and then", "rare": "rare: only when the beat clearly calls for it",
              "other_series": "other series: not part of this channel's usual look", "shorts_only": "SHORTS ONLY: do not use in this video"}
KIND_WHERE = {"base": "a shot (the `technique` of a shot)", "card": "a shot (the `technique` of a shot)",
              "overlay": "an overlay (inside the `overlays` of a shot)", "transition": "a shot's `transition_in` (rarely needed)"}


def _field(f: dict) -> str:
    """One field of an `items` param: `name:type`, its bounds or values, `*` when required, `=default` for a plain default."""
    s = "%s:%s" % (f["name"], f["type"])
    if f["type"] in ("number", "at") and f.get("min") is not None:
        s += "[%s..%s]" % (f["min"], f.get("max"))
    if f["type"] == "enum" and f.get("values"):
        s += "{%s}" % "|".join(str(v) for v in f["values"])
    if f.get("required"):
        s += "*"
    d = f.get("default")
    if d is not None and not isinstance(d, (list, dict)) and not f.get("required"):
        s += "=%s" % str(d)[:24]
    return s


def _p(p: dict) -> str:
    t = p["type"]
    if t == "camera":
        return "camera"
    if t == "items":                       # a list of records: say how many and what each one holds
        n = "" if p.get("min_items") is None and p.get("max_items") is None else "(%s..%s)" % (p.get("min_items", 0), p.get("max_items", "n"))
        return "%s:items%s[{%s}]" % (p["name"], n, ", ".join(_field(f) for f in p.get("fields") or []))
    s = "%s:%s" % (p["name"], t)
    if t == "number" and p.get("min") is not None:
        s += "[%s..%s]" % (p["min"], p.get("max"))
    if t == "enum" and p.get("values"):
        s += "{%s}" % "|".join(str(v) for v in p["values"])
    if p.get("required"):
        s += "*"
    d = p.get("default")
    if d is not None and not isinstance(d, (list, dict)):
        s += "=%s" % (str(d)[:24])
    return s


def _slot(s: dict) -> str:
    return "%s%s%s" % (s["name"], "*" if s.get("required") else "", "(region ok)" if s.get("region") else "") + ("[%s]" % s["type"] if s["type"] != "image" else "")


PROGRAM_ONLY = "PROGRAM ONLY: the channel identity, written by the compiler, never by you"
EXPLAINER_FAMILIES = ("MAP-", "KEY-", "TIME-", "NUM-", "TREE-", "STATE-", "DOC-")      # the explanatory devices: each is printed with a filled example


def _example(t: dict) -> str:
    """The filled example of an explanatory device, taken from the registry defaults (so that it cannot drift): every list of items (a field that holds its default
    and is not required is left out, the compiler fills it), plus the lists of lines and the texts that are not empty. Empty for any other technique."""
    if not str(t.get("id", "")).startswith(EXPLAINER_FAMILIES):
        return ""
    ex = {}
    for p in t.get("params") or []:
        d = p.get("default")
        if p["type"] == "items" and isinstance(d, list) and d:
            keep = {f["name"]: f for f in p.get("fields") or []}
            ex[p["name"]] = [{k: v for k, v in it.items() if k in keep and (keep[k].get("required") or v != keep[k].get("default"))} for it in d]
        elif p["type"] in ("lines", "string") and d not in (None, "", []):
            ex[p["name"]] = d
    return json.dumps(ex, ensure_ascii=False, separators=(",", ":")) if ex else ""


def _identity_section(cfg) -> list:
    """The channel identity as the style's `identity` block names it (so that it cannot drift): what the family is and what a model may do."""
    roles = {"open": "opening overlay", "label": "artwork label overlay", "brand": "channel-name beat (a card)", "mark": "chapter mark (a card)"}
    out = ["## The channel identity (written by the program, never by you)", "",
           "The opening, the channel-name beat and the chapter marks of a video are made by the compiler in one of the styles the owner chose. "
           "Their techniques are listed below, each marked PROGRAM ONLY: you are never offered them as a choice, and you never write a title card or a "
           "chapter card. The opening overlay and the label sit on the first shot of the video (you may see them in its `overlays`); the channel-name "
           "beat and the chapter marks are cards that the program keeps (you are not shown them). The program also writes the opening SHOT: when the voice "
           "starts late it shows the whole painting from 0 until 0.35 s before the first word (the shot `s0000`, with the opening overlay and the label on it); "
           "your first shot starts on the first word and is never a still view of the whole painting."]
    for sid, sd in cfg.styles.items():
        out.append("- style `%s` (%s): %s" % (sid, sd.label, "; ".join("%s = %s" % (roles[r], sd.technique(r)) for r in roles if sd.technique(r))))
    out.append("")
    return out


# --- catalogue pass (worker catalogue, 2026-11-20): the techniques a model is offered, grouped by the kind of line they serve
KIND_ORDER = ("detail", "whole", "idea", "outside", "compare", "journey", "dates", "figure", "inscription", "construction", "relations")
# kind -> (what the line does, the `intent` to write on its shots)
KIND_HELP = {
    "detail": ("it points at a thing that IS in the painting: names it, describes it, looks at it", "point_at"),
    "whole": ("it speaks of the painting as one object (its date, size, where it hangs, who owned it, its fate), sums up, or recalls details in the closing", "establish"),
    "idea": ("it gives a reading or an opinion that no picture can show: stay on the thing it is about", "explore"),
    "outside": ("it is about a person, place, object, event or custom that is NOT in the painting: show a picture of that thing", "context"),
    "compare": ("it sets the painting or one detail beside another work, or beside another state of the same picture", "compare"),
    "journey": ("it is about a movement or a tie between two or more places", "context"),
    "dates": ("it gives three or more dated events of one story, or turns on one year", "quantify"),
    "figure": ("a quantity is its point (a count, a price, a size)", "quantify"),
    "inscription": ("it reads words that are written in the picture", "quote"),
    "construction": ("it explains how the picture is built (perspective, a shape, a visible technique)", "explain_mechanism"),
    "relations": ("it ties three or more people together (a family, patrons)", "context"),
}
PROGRAM_OTHER = "PROGRAM ONLY: written by the compiler, never by you"


def listed(bundle: R.StyleBundle) -> list:
    """The techniques a model is offered: the engine can draw them and the catalogue offers them (`offered`)."""
    return [t for t in bundle.techniques if t.get("engine", {}).get("available") is True and bundle.offered(t["id"])]


def use_lines(t: dict, which=("use_when", "needs", "never_when", "example")) -> list:
    """The four texts of an offered technique as the lines of its entry (nothing for a technique that has none)."""
    label = {"use_when": "use when", "needs": "needs", "never_when": "never when", "example": "real sentence"}
    return ["- %s: %s" % (label[k], " ".join(str(t[k]).split())) for k in which if t.get(k)]


def _plain_first(t: dict) -> tuple:
    """Order inside a group: the shots before the overlays (camera moves first), then by id."""
    return ({"base": 0, "card": 1, "overlay": 2, "transition": 3}.get(t.get("kind"), 9), t["id"])


def _primary_kind(t: dict) -> str:
    serves = [k for k in t.get("serves") or [] if k in KIND_ORDER]
    return serves[0] if serves else KIND_ORDER[0]


def _program_section(bundle: R.StyleBundle, cfg) -> list:
    """The techniques the program writes (`hidden_reason.code` program), one short entry each: a model recognises them on the first shot and never writes one."""
    out = ["## Written by the program (never by you)", "",
           "The registry also holds the techniques below. The compiler writes them (the opening, the channel-name beat, the chapter marks, the cuts); "
           "you never write one, and a shot or an overlay of yours that names one is dropped or refused.", ""]
    for t in bundle.techniques:
        hr = t.get("hidden_reason") or {}
        if hr.get("code") != "program" or t.get("engine", {}).get("available") is not True:
            continue
        mark = PROGRAM_ONLY if (cfg and cfg.is_identity_technique(t["id"])) else PROGRAM_OTHER
        out.append("### %s %s  [%s, %s]" % (t["id"], t["name"], t["kind"], mark))
        out.append("- what: %s" % (t.get("description") or ""))
        out.append("- %s" % hr.get("note", ""))
        out.append("")
    return out


def generate(bundle: R.StyleBundle) -> str:
    techs = listed(bundle)
    cfg = read_identity(bundle.style)
    by_kind: dict = {k: [] for k in KIND_ORDER}
    for t in techs:
        by_kind[_primary_kind(t)].append(t)
    out = ["# Techniques", "",
           "Generated from the registry. `*` = required. `[a..b]` = allowed range. `=x` = default. Parameters you do not write keep their default;",
           "the compiler also fills the camera keys, label texts and region sizes for you. Slots hold pictures: `{\"asset\": \"A\", \"region\": \"MIRROR\"}`.",
           "A camera is a list of keys `{\"at\": {\"rel\": 0..1}, \"cx\": x, \"cy\": y, \"zoom\": z, \"ease\": \"linear\"}` with cx, cy in SOURCE pixels and zoom = screen pixels per source pixel (the frame shows 1920/zoom by 1080/zoom source pixels).",
           "Write `camera` yourself only when the default move is wrong; `at` may also be a spoken word `{\"w\": index, \"off\": 0.0}`.", "",
           "## How to choose", "",
           "Every beat of `inputs/beats.json` has `kinds`: one or two words that say what its sentence does. The pictures step decided them: read them, do not guess them "
           "(for a beat without `kinds`, decide the kind yourself with the table of TASK.md). Take the techniques of the kinds of the beat from the list below. "
           "Each technique says when to use it, what it needs and when never: use one only where its text fits the sentence, never as decoration. "
           "The right number of devices in a video is the number of sentences that call for one, and none is fine; a camera move serves most sentences. "
           "These are all the techniques you are offered: the registry holds more, hidden from you, and writing one is the error `technique_not_offered` "
           "(its message says what to use instead).", "",
           "## Choosing by the kind of line", ""]
    for kind in KIND_ORDER:
        ids = [t for t in techs if kind in (t.get("serves") or [])]
        ids.sort(key=lambda t: (0 if _primary_kind(t) == kind else 1,) + _plain_first(t))
        what, intent = KIND_HELP[kind]
        out.append("- **%s** (%s; write intent `%s`): %s" % (kind, what, intent, ", ".join(t["id"] for t in ids) or "(no technique of its own: the camera techniques of `detail` and `whole` serve it)"))
    out.append("")
    if cfg:
        out += _identity_section(cfg)
    for kind in KIND_ORDER:
        group = sorted(by_kind[kind], key=_plain_first)
        if not group:
            continue
        out += ["## The techniques for lines of kind `%s`" % kind, "", "A line where %s." % KIND_HELP[kind][0], ""]
        for t in group:
            out.append("### %s %s  [%s]" % (t["id"], t["name"], t["kind"]))
            out.append("- used as: %s; intents: %s" % (KIND_WHERE.get(t["kind"], t["kind"]), ", ".join(t.get("intents") or [])))
            out.append("- serves: %s" % ", ".join(t.get("serves") or [kind]))
            out += use_lines(t)
            out.append("- what: %s" % (t.get("description") or ""))
            out.append("- slots: %s" % (", ".join(_slot(s) for s in t.get("slots") or []) or "none"))
            out.append("- params: %s" % (", ".join(_p(p) for p in t.get("params") or []) or "none"))
            if _example(t):
                out.append("- example (the defaults; replace ALL of its data): %s" % _example(t))
            tm = t.get("timing") or {}
            if tm.get("default_s"):
                out.append("- length: usually %ss (min %s, max %s)" % (tm["default_s"], tm.get("min_s"), tm.get("max_s")))
            out.append("")
    out += _program_section(bundle, cfg)
    return "\n".join(out)
