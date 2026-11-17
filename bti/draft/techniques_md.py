"""`inputs/techniques.md`: a compact description of every technique of the registry, generated (never hand written) so that it
cannot drift from `style/gae/techniques.json`. It tells the agent WHEN to use a technique, what it needs and what it may change."""
from __future__ import annotations

from bti.engine import registry as R

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


def _p(p: dict) -> str:
    t = p["type"]
    if t == "camera":
        return "camera"
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


def generate(bundle: R.StyleBundle) -> str:
    techs = [t for t in bundle.techniques if t.get("engine", {}).get("available") is True]
    out = ["# Techniques", "",
           "Generated from the registry. `*` = required. `[a..b]` = allowed range. `=x` = default. Parameters you do not write keep their default;",
           "the compiler also fills the camera keys, label texts and region sizes for you. Slots hold pictures: `{\"asset\": \"A\", \"region\": \"MIRROR\"}`.",
           "A camera is a list of keys `{\"at\": {\"rel\": 0..1}, \"cx\": x, \"cy\": y, \"zoom\": z, \"ease\": \"linear\"}` with cx, cy in SOURCE pixels and zoom = screen pixels per source pixel (the frame shows 1920/zoom by 1080/zoom source pixels).",
           "Write `camera` yourself only when the default move is wrong; `at` may also be a spoken word `{\"w\": index, \"off\": 0.0}`.", "",
           "## Choosing by intent (core first)", ""]
    for intent, hint in INTENT_HELP.items():
        ids = sorted((t for t in techs if intent in (t.get("intents") or []) and t.get("channel_usage") != "shorts_only"),
                     key=lambda t: (USAGE_ORDER.get(t.get("channel_usage"), 9), t["id"]))
        out.append("- **%s** (%s): %s" % (intent, hint, ", ".join("%s%s" % (t["id"], "" if t.get("channel_usage") == "core" else " (%s)" % t.get("channel_usage")) for t in ids)))
    out += ["", "## The techniques", ""]
    order = {"base": 0, "card": 1, "overlay": 2, "transition": 3}
    for t in sorted(techs, key=lambda t: (order.get(t["kind"], 9), t.get("category") or "", USAGE_ORDER.get(t.get("channel_usage"), 9), t["id"])):
        out.append("### %s %s  [%s, %s]" % (t["id"], t["name"], t["kind"], USAGE_HELP.get(t.get("channel_usage"), t.get("channel_usage"))))
        out.append("- used as: %s; intents: %s" % (KIND_WHERE.get(t["kind"], t["kind"]), ", ".join(t.get("intents") or [])))
        out.append("- what: %s" % (t.get("description") or ""))
        if t.get("usage_rule"):
            out.append("- when: %s" % t["usage_rule"])
        out.append("- slots: %s" % (", ".join(_slot(s) for s in t.get("slots") or []) or "none"))
        out.append("- params: %s" % (", ".join(_p(p) for p in t.get("params") or []) or "none"))
        tm = t.get("timing") or {}
        if tm.get("default_s"):
            out.append("- length: usually %ss (min %s, max %s)" % (tm["default_s"], tm.get("min_s"), tm.get("max_s")))
        out.append("")
    return "\n".join(out)
