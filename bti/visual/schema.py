"""The strict JSON shape of a visual script."""
from jsonschema import Draft202012Validator

STR = {"type": "string", "minLength": 1}
INDEX = {"type": "integer", "minimum": 0}

def obj(properties, required=None):
    return {"type": "object", "properties": properties, "required": required if required is not None else list(properties), "additionalProperties": False}

def array(item, minimum=0):
    return {"type": "array", "items": item, "minItems": minimum}

REGION = obj({"region": STR})
PICTURE = obj({"picture": STR})
WHOLE = obj({"whole": {"const": True}})
FALLBACK = {"oneOf": [REGION, WHOLE]}
SHOW = {"oneOf": [REGION, PICTURE, WHOLE, obj({"want": STR, "else": FALLBACK}),
                  obj({"pair": {"type": "array", "items": PICTURE, "minItems": 2, "maxItems": 2}}),
                  obj({"map": obj({"places": array(STR, 1)})})]}
POINT = obj({"region": STR, "word": INDEX})
LABEL = obj({"region": STR, "text": STR})
INTENT = {"oneOf": [obj({"intro": STR, "word": INDEX}), obj({"point": array(POINT, 1)}),
                    obj({"read": LABEL}), obj({"labels": array(LABEL, 3)}),
                    obj({"number": obj({"text": STR, "of": STR})})]}
CAST = obj({"id": STR, "kind": {"enum": ["person", "place", "work", "thing", "idea", "text"]},
            "name": STR, "also": array(STR), "strip": {"type": "boolean"},
            "sub": {"type": "string"}, "shown_by": array({"oneOf": [REGION, PICTURE]})})
WANTED = obj({"id": STR, "subject": STR, "kind": {"enum": ["portrait", "work", "place", "object", "document"]},
              "search": STR, "alt": array(STR), "period": {"enum": ["then", "later", "today", None]},
              "status": {"enum": ["open", "found", "none"]}, "picture": {"type": ["string", "null"]}, "tried": array(STR)})
MOMENT = obj({"id": STR, "line": STR, "w0": INDEX, "w1": INDEX, "about": {"type": ["string", "null"]},
              "show": SHOW, "move": {"enum": ["hold", "push", "travel", "pull"]}, "from": STR,
              "say": array(INTENT), "why": STR, "about_not_shown": STR},
             ["id", "line", "w0", "w1", "about", "show", "move", "from", "say", "why"])
SCHEMA = obj({"schema": {"const": "bti.visual/1"}, "made_from": obj({"narration": STR, "timing": STR}),
              "cast": array(CAST), "wanted": array(WANTED), "moments": array(MOMENT)})
VALIDATOR = Draft202012Validator(SCHEMA)
