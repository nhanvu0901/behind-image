"""The `identity` block of `style/<id>/style.json`: which technique plays which role in each style.

The block is written by the engine side (the seven `ID-*` techniques). This module only READS it, so a technique id is never
written down anywhere else in this package, with one exception: the three legacy techniques of the old look (the title card and
the two kinds of chapter card), which the contract names, and the prefixes of the `ID-*` families, used to recognise what an
earlier application left in a storyboard.

Shape of the block (every value may also be wrapped as `{"value": ..., "source": ...}`, the way style.json writes constants):

    "identity": {
      "channel_name": "RAKING LIGHT",
      "default_style": "raking",
      "styles": {
        "raking": {"label_vi": "Vệt sáng quét", "open": "ID-OPEN-01", "label": "ID-LABEL-01", "brand": "ID-BRAND-01", "mark": "ID-MARK-01",
                   "nominal": {"open": {"start_s": 0.0, "dur_s": 9.0}, "label": {"start_s": 6.2, "dur_s": 4.5}}},
        "dim":    {"label_vi": "Tối lại, hiện tên", "open": "ID-OPEN-02", "brand": "ID-BRAND-02", "mark": "ID-MARK-02",
                   "mark_transition": {"technique": "TR-01", "dur": 0.75}}
      }
    }

A style may leave `label` out (the `dim` opening writes the title itself, `label: null`); `mark_transition` is optional (null: a hard
cut). Optional: `nominal: {role: {start_s, dur_s}}` per style (where in the video the opening overlays start, and for how long) and
`min_element_s` (no element is shorter).
"""
from __future__ import annotations

from dataclasses import dataclass, field

LEGACY_TITLE = ("X-CARD-02",)                 # the old title card
LEGACY_MARKS = ("X-CARD-01", "TXT-01")        # the old chapter cards
PREFIX = {"open": "ID-OPEN-", "label": "ID-LABEL-", "brand": "ID-BRAND-", "mark": "ID-MARK-"}
ROLES = ("open", "label", "brand", "mark")

# Only used when the block carries no display name for a style it lists (a name is a word for the owner, not a rule).
FALLBACK_LABELS = {"raking": "Vệt sáng quét", "dim": "Tối lại, hiện tên"}
_TRANSITION_KEYS = ("mark_transition", "mark_transition_in", "transition_in", "entry_transition", "mark_entry")


class IdentityError(ValueError):
    """The style cannot be applied. `code` is stable (the route maps it to a status), `message` is an English sentence."""

    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra


def _plain(v):
    """style.json wraps many constants as {"value": x, "source": "..."}."""
    if isinstance(v, dict) and "value" in v and set(v) <= {"value", "source", "note"}:
        return v["value"]
    return v


@dataclass(frozen=True)
class StyleDef:
    id: str
    label: str
    open: str | None = None
    label_role: str | None = None            # the technique of the two-line label (role `label`)
    brand: str | None = None
    mark: str | None = None
    transition: dict | None = None           # {"technique", "dur"} of the mark's entry, or None (a hard cut)
    start_s: dict = field(default_factory=dict)       # optional per-role nominal start (seconds into the video)
    dur_s: dict = field(default_factory=dict)         # optional per-role nominal length (seconds)

    def technique(self, role: str) -> str | None:
        return self.label_role if role == "label" else getattr(self, role)


@dataclass(frozen=True)
class IdentityConfig:
    channel_name: str
    default_style: str
    styles: dict                              # id -> StyleDef, in the order of the block
    fit_pct: float = 95.5                     # painting height as a percent of the frame (style.json `matte.painting_height_pct`)
    min_element_s: float = 1.5                # an element (channel-name beat, chapter mark) is never shorter than this

    def style(self, style_id: str) -> StyleDef | None:
        return self.styles.get(style_id) if isinstance(style_id, str) else None

    def ids(self) -> list[str]:
        return list(self.styles)

    def options(self) -> list[dict]:
        return [{"id": s.id, "label": s.label} for s in self.styles.values()]

    def techniques(self, role: str) -> set[str]:
        """Every technique that plays `role` in some style (the other style's technique too)."""
        return {t for t in (s.technique(role) for s in self.styles.values()) if t}

    def is_family(self, technique, role: str) -> bool:
        """The technique belongs to the `role` family: named by a style, or carrying the family prefix (`ID-MARK-*`)."""
        return isinstance(technique, str) and (technique in self.techniques(role) or technique.startswith(PREFIX[role]))

    def is_identity_technique(self, technique) -> bool:
        """Any technique of the channel identity: the opening and the label (overlays) and the title slot and chapter marks (cards)."""
        return any(self.is_family(technique, role) for role in ROLES)

    def is_identity_card(self, technique) -> bool:
        """A title slot or a chapter mark of some style (the `brand` and `mark` families): cards in everything but their kind."""
        return self.is_family(technique, "brand") or self.is_family(technique, "mark")

    def old_look(self) -> set[str]:
        return set(LEGACY_TITLE) | set(LEGACY_MARKS)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def _transition(entry: dict) -> dict | None:
    for k in _TRANSITION_KEYS:
        if k in entry:
            v = _plain(entry[k])
            if not isinstance(v, dict):
                return None
            tech = v.get("technique") or v.get("id")
            dur = v.get("dur", v.get("dur_s", v.get("seconds")))
            if isinstance(tech, str) and tech and _num(dur) and dur > 0:
                return {"technique": tech, "dur": float(dur)}
            return None
    return None


def _nominal(entry: dict, field_name: str) -> dict:
    """role -> seconds, from `nominal: {role: {start_s, dur_s}}` (a role that is null or has no such number is left out)."""
    nom = _plain(entry.get("nominal"))
    out = {}
    if isinstance(nom, dict):
        for role, d in nom.items():
            d = _plain(d)
            if role in ROLES and isinstance(d, dict) and _num(_plain(d.get(field_name))):
                out[role] = float(_plain(d[field_name]))
    return out


def block_of(style) -> dict | None:
    """The `identity` block of a style.json document (the block itself is accepted too); None when there is none."""
    if not isinstance(style, dict):
        return None
    b = style.get("identity")
    if b is None and ("default_style" in style or "channel_name" in style):
        b = style
    b = _plain(b)
    return b if isinstance(b, dict) else None


def read(style) -> IdentityConfig | None:
    """The configuration, or None when the style has no usable `identity` block."""
    b = block_of(style)
    if not b:
        return None
    raw = _plain(b.get("styles"))
    if not isinstance(raw, dict):            # the styles may also sit directly in the block, next to channel_name
        raw = {k: v for k, v in b.items() if isinstance(_plain(v), dict) and k not in ("channel_name", "default_style")}
    styles = {}
    for sid, entry in raw.items():
        entry = _plain(entry)
        if not isinstance(sid, str) or not isinstance(entry, dict):
            continue
        g = lambda k: (lambda v: v if isinstance(v, str) and v else None)(_plain(entry.get(k)))      # noqa: E731
        label = g("label_vi") or g("name_vi") or g("title_vi") or FALLBACK_LABELS.get(sid) or sid
        # `label` is the role of the two-line label; a style that names a display text there instead is not supported
        styles[sid] = StyleDef(id=sid, label=label, open=g("open"), label_role=g("label"), brand=g("brand"), mark=g("mark"),
                               transition=_transition(entry), start_s=_nominal(entry, "start_s"), dur_s=_nominal(entry, "dur_s"))
    if not styles:
        return None
    name = _plain(b.get("channel_name"))
    default = _plain(b.get("default_style"))
    if default not in styles:
        default = next(iter(styles))
    fit = 95.5
    m = _plain(style.get("matte")) if isinstance(style, dict) else None
    if isinstance(m, dict) and _num(_plain(m.get("painting_height_pct"))):
        fit = float(_plain(m["painting_height_pct"]))
    mn = _plain(b.get("min_element_s"))
    return IdentityConfig(channel_name=name if isinstance(name, str) and name else "", default_style=default, styles=styles, fit_pct=fit,
                          min_element_s=float(mn) if _num(mn) and mn > 0 else 1.5)


def need(style) -> IdentityConfig:
    """Like `read`, but a style without the block is an IdentityError."""
    cfg = read(style)
    if cfg is None:
        raise IdentityError("no_identity_block", "this style has no `identity` block in style.json")
    return cfg


def options(style) -> list[dict]:
    """[{id, label}] of the styles an owner or an agent may choose; [] when the style has no identity block."""
    cfg = read(style)
    return cfg.options() if cfg else []


def is_mismatch(cfg: IdentityConfig, style_id: str, technique) -> bool:
    """True when `technique` is part of the identity (the old title and chapter cards, or any style's title slot or chapter mark)
    but is not the title slot or the chapter mark of `style_id`."""
    sd = cfg.style(style_id)
    if sd is None or not isinstance(technique, str):
        return False
    part = technique in cfg.old_look() or cfg.is_family(technique, "brand") or cfg.is_family(technique, "mark")
    return part and technique not in (sd.brand, sd.mark)
