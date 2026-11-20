"""`inputs/techniques.md`: a compact description of every technique of the registry, generated (never hand written) so that it
cannot drift from `style/gae/techniques.json`. It tells the agent WHEN to use a technique, what it needs and what it may change."""
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


def generate(bundle: R.StyleBundle) -> str:
    techs = [t for t in bundle.techniques if t.get("engine", {}).get("available") is True]
    cfg = read_identity(bundle.style)
    mine = (lambda tid: bool(cfg) and cfg.is_identity_technique(tid))            # a technique of the channel identity: listed, but not a choice
    out = ["# Techniques", "",
           "Generated from the registry. `*` = required. `[a..b]` = allowed range. `=x` = default. Parameters you do not write keep their default;",
           "the compiler also fills the camera keys, label texts and region sizes for you. Slots hold pictures: `{\"asset\": \"A\", \"region\": \"MIRROR\"}`.",
           "A camera is a list of keys `{\"at\": {\"rel\": 0..1}, \"cx\": x, \"cy\": y, \"zoom\": z, \"ease\": \"linear\"}` with cx, cy in SOURCE pixels and zoom = screen pixels per source pixel (the frame shows 1920/zoom by 1080/zoom source pixels).",
           "Write `camera` yourself only when the default move is wrong; `at` may also be a spoken word `{\"w\": index, \"off\": 0.0}`.", "",
           "## Choosing by intent (core first)", ""]
    for intent, hint in INTENT_HELP.items():
        ids = sorted((t for t in techs if intent in (t.get("intents") or []) and t.get("channel_usage") != "shorts_only" and not mine(t["id"])),
                     key=lambda t: (USAGE_ORDER.get(t.get("channel_usage"), 9), t["id"]))
        out.append("- **%s** (%s): %s" % (intent, hint, ", ".join("%s%s" % (t["id"], "" if t.get("channel_usage") == "core" else " (%s)" % t.get("channel_usage")) for t in ids)))
    out.append("")
    if cfg:
        out += _identity_section(cfg)
    out += ["## The techniques", ""]
    order = {"base": 0, "card": 1, "overlay": 2, "transition": 3}
    for t in sorted(techs, key=lambda t: (order.get(t["kind"], 9), t.get("category") or "", USAGE_ORDER.get(t.get("channel_usage"), 9), t["id"])):
        out.append("### %s %s  [%s, %s]" % (t["id"], t["name"], t["kind"], PROGRAM_ONLY if mine(t["id"]) else USAGE_HELP.get(t.get("channel_usage"), t.get("channel_usage"))))
        out.append("- used as: %s; intents: %s" % (KIND_WHERE.get(t["kind"], t["kind"]), ", ".join(t.get("intents") or [])))
        out.append("- what: %s" % (t.get("description") or ""))
        if t.get("usage_rule"):
            out.append("- when: %s" % t["usage_rule"])
        out.append("- slots: %s" % (", ".join(_slot(s) for s in t.get("slots") or []) or "none"))
        out.append("- params: %s" % (", ".join(_p(p) for p in t.get("params") or []) or "none"))
        if _example(t):
            out.append("- example (the defaults; replace ALL of its data): %s" % _example(t))
        tm = t.get("timing") or {}
        if tm.get("default_s"):
            out.append("- length: usually %ss (min %s, max %s)" % (tm["default_s"], tm.get("min_s"), tm.get("max_s")))
        out.append("")
    return "\n".join(out)
