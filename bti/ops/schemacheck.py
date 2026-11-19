"""A small JSON Schema checker for the operations' own schemas, and the builders those schemas are made with.

Only the part of JSON Schema the registry uses is understood: `type`, `enum`, `const`, `minimum`, `maximum`,
`exclusiveMinimum`, `minLength`, `maxLength`, `pattern` (searched, as JSON Schema says), `minItems`, `maxItems`, `items`,
`required`, `properties`, `additionalProperties` (false), `minProperties` and `anyOf`. The tests check every schema with the
full `jsonschema` library as well, so a schema can never mean one thing here and another thing to a reader.

`validate` answers with `fields` entries, `{path, problem, allowed?}`, the form of the error bodies: the caller gives the path
prefix (`ops[1]`). It collects up to MAX_FIELDS problems so that an agent can fix them in one round.
"""
from __future__ import annotations

import math
import re
from typing import Any

MAX_FIELDS = 25

_TYPE_WORDS = {"string": "a string", "integer": "a whole number", "number": "a number", "boolean": "true or false",
               "object": "an object", "array": "a list", "null": "null"}


# ---------------------------------------------------------------- builders (the schemas are plain dicts)
def _with(d: dict, description: str | None, **more: Any) -> dict:
    if description:
        d["description"] = description
    d.update({k: v for k, v in more.items() if v is not None})
    return d


def string(description: str | None = None, *, pattern: str | None = None, max_length: int | None = None, min_length: int | None = None,
           enum: list | None = None, hint: str | None = None, nullable: bool = False) -> dict:
    return _with({"type": ["string", "null"] if nullable else "string"}, description, pattern=pattern, maxLength=max_length,
                 minLength=min_length, enum=enum, **{"x-hint": hint})


def integer(description: str | None = None, *, minimum: int | None = None, maximum: int | None = None) -> dict:
    return _with({"type": "integer"}, description, minimum=minimum, maximum=maximum)


def number(description: str | None = None, *, minimum: float | None = None, maximum: float | None = None,
           exclusive_minimum: float | None = None, nullable: bool = False) -> dict:
    return _with({"type": ["number", "null"] if nullable else "number"}, description, minimum=minimum, maximum=maximum,
                 exclusiveMinimum=exclusive_minimum)


def boolean(description: str | None = None) -> dict:
    return _with({"type": "boolean"}, description)


def array(items: dict, description: str | None = None, *, min_items: int | None = None, max_items: int | None = None) -> dict:
    return _with({"type": "array", "items": items}, description, minItems=min_items, maxItems=max_items)


def free_object(description: str | None = None, *, min_properties: int | None = None) -> dict:
    """An object whose keys are decided by the registry at apply time (technique parameters, slots)."""
    return _with({"type": "object"}, description, minProperties=min_properties)


def any_of(*alternatives: dict, description: str | None = None, title: str | None = None) -> dict:
    return _with({"anyOf": list(alternatives)}, description, title=title)


def obj(name: str, required: list[str], properties: dict, description: str | None = None) -> dict:
    """The schema of one operation: an object with the fixed `op` name and exactly the listed fields."""
    props = {"op": {"const": name, "description": "The operation name."}}
    props.update(properties)
    return _with({"type": "object", "additionalProperties": False, "required": ["op"] + [r for r in required if r != "op"],
                  "properties": props}, description)


def plain_object(properties: dict, required: list[str] | None = None, description: str | None = None, title: str | None = None) -> dict:
    """A nested object with exactly the listed fields."""
    d = {"type": "object", "additionalProperties": False, "properties": properties}
    if required:
        d["required"] = list(required)
    return _with(d, description, title=title)


# ---------------------------------------------------------------- the checker
def _is_type(t: str, v: Any) -> bool:
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "null":
        return v is None
    if t == "integer":
        if isinstance(v, bool):
            return False
        return isinstance(v, int) or (isinstance(v, float) and math.isfinite(v) and v.is_integer())
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and (not isinstance(v, float) or math.isfinite(v))
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    return True


def _type_problem(types: list[str]) -> str:
    return "must be " + " or ".join(_TYPE_WORDS.get(t, t) for t in types)


def _join(path: str, key: str) -> str:
    return "%s.%s" % (path, key) if path else key


def _entry(path: str, problem: str, allowed: list | None = None) -> dict:
    e: dict[str, Any] = {"path": path, "problem": problem}
    if allowed is not None and len(allowed) <= 60:
        e["allowed"] = list(allowed)
    return e


def validate(schema: dict, value: Any, path: str = "") -> list[dict]:
    """`fields` entries for every way `value` does not fit `schema` (empty list: it fits)."""
    out: list[dict] = []
    _walk(schema, value, path, out)
    return out[:MAX_FIELDS]


def _walk(s: dict, v: Any, path: str, out: list[dict]) -> None:
    if len(out) >= MAX_FIELDS:
        return
    if "anyOf" in s:
        for alt in s["anyOf"]:
            scratch: list[dict] = []
            _walk(alt, v, path, scratch)
            if not scratch:
                break
        else:
            titles = [a.get("title") or a.get("description") or "a valid value" for a in s["anyOf"]]
            out.append(_entry(path, "must be " + (s.get("title") or " or ".join(titles))))
            return
    if "const" in s:
        if v != s["const"] or type(v) is not type(s["const"]):
            out.append(_entry(path, "must be %r" % (s["const"],), [s["const"]]))
        return
    types = s.get("type")
    if types is not None:
        tl = types if isinstance(types, list) else [types]
        if not any(_is_type(t, v) for t in tl):
            out.append(_entry(path, _type_problem(tl)))
            return
    if "enum" in s and v not in s["enum"]:
        out.append(_entry(path, "must be one of: %s" % ", ".join(str(x) for x in s["enum"]), s["enum"]))
        return
    if isinstance(v, str):
        if "minLength" in s and len(v) < s["minLength"]:
            out.append(_entry(path, "must have at least %d character%s" % (s["minLength"], "" if s["minLength"] == 1 else "s")))
        if "maxLength" in s and len(v) > s["maxLength"]:
            out.append(_entry(path, "must have at most %d characters" % s["maxLength"]))
        if "pattern" in s and re.search(s["pattern"], v) is None:
            out.append(_entry(path, "does not have the required form: %s" % (s.get("x-hint") or s["pattern"])))
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in s and v < s["minimum"]:
            out.append(_entry(path, "must be at least %s" % s["minimum"]))
        if "maximum" in s and v > s["maximum"]:
            out.append(_entry(path, "must be at most %s" % s["maximum"]))
        if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
            out.append(_entry(path, "must be greater than %s" % s["exclusiveMinimum"]))
    elif isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]:
            out.append(_entry(path, "must have at least %d item%s" % (s["minItems"], "" if s["minItems"] == 1 else "s")))
        if "maxItems" in s and len(v) > s["maxItems"]:
            out.append(_entry(path, "must have at most %d items" % s["maxItems"]))
        if "items" in s:
            for i, item in enumerate(v):
                _walk(s["items"], item, "%s[%d]" % (path, i), out)
                if len(out) >= MAX_FIELDS:
                    return
    elif isinstance(v, dict):
        props = s.get("properties") or {}
        for key in s.get("required") or []:
            if key not in v:
                out.append(_entry(_join(path, key), "is required"))
        if "minProperties" in s and len(v) < s["minProperties"]:
            out.append(_entry(path, "must have at least %d field%s" % (s["minProperties"], "" if s["minProperties"] == 1 else "s")))
        if s.get("additionalProperties") is False:
            for key in v:
                if key not in props:
                    out.append(_entry(_join(path, str(key)), "is not a field of this object", sorted(props)))
        for key, sub in props.items():
            if key in v:
                _walk(sub, v[key], _join(path, key), out)
                if len(out) >= MAX_FIELDS:
                    return


def describe_type(s: dict) -> str:
    """A short phrase for the type of a schema, for the generated documentation."""
    if "anyOf" in s:
        return " or ".join(describe_type(a) for a in s["anyOf"])
    if "const" in s:
        return "`%s`" % (s["const"],)
    if "enum" in s:
        return "one of " + ", ".join("`%s`" % x for x in s["enum"])
    t = s.get("type")
    tl = t if isinstance(t, list) else [t]
    words = []
    for x in tl:
        if x == "array":
            words.append("list of " + (describe_type(s["items"]) if "items" in s else "values"))
        elif x == "object" and s.get("title"):
            words.append(s["title"])
        else:
            words.append({"string": "text", "integer": "whole number", "number": "number", "boolean": "true or false",
                          "object": "object", "null": "null"}.get(x, str(x)))
    return " or ".join(words)
