"""Licence allow-list gate (PLAN.md section 5, rule 1).

Allowed: public domain, CC0, CC BY, CC BY-SA (any version), and the licences of the free picture services: the Pexels
License, the Pixabay Content License and ODbL (OpenStreetMap map tiles).
Rejected: anything NC or ND, "fair use", unknown, missing.

`check_text(text)` and `check_licence(meta)` return `(allowed, licence_name, reason)`.
`licence_name` is canonical when recognised ("PD", "CC0", "CC BY 4.0", "CC BY-SA 3.0"),
otherwise the cleaned input text. `reason` is "" when allowed.
"""
from __future__ import annotations

import html
import re
from typing import Any, Iterable

ALLOWED_NAMES = ("PD", "CC0", "CC BY", "CC BY-SA", "Pexels License", "Pixabay Content License", "ODbL")

PEXELS_LICENCE = "Pexels License"
PIXABAY_LICENCE = "Pixabay Content License"
ODBL = "ODbL"
# Canonical name -> its page, for the names this table recognises (the Creative Commons ones carry their link in the record).
LICENCE_URLS = {
    PEXELS_LICENCE: "https://www.pexels.com/license/",
    PIXABAY_LICENCE: "https://pixabay.com/service/license-summary/",
    ODBL: "https://www.openstreetmap.org/copyright",
}

# Keys searched in a metadata dict, in priority order. Covers our own normalised
# candidates, Wikimedia extmetadata (flattened or nested), Met records and yt-dlp info.
_TEXT_KEYS = ("licence", "license", "licence_name", "LicenseShortName", "License",
              "UsageTerms", "licenseShortName", "usage_terms")
_TAG = re.compile(r"<[^>]+>")
_TOKEN = re.compile(r"[a-z0-9]+")
_VERSION = re.compile(r"(?<![\d.])([1-4]\.\d)(?!\d)")
_NC = re.compile(r"non[\s\-_]?commercial|\bnc\b")
_ND = re.compile(r"no[\s\-_]?deriv|\bnd\b")
_BAD_PHRASES = ("fair use", "all rights reserved", "standard youtube", "copyrighted",
                "not public domain", "non-free", "nonfree", "permission", "unknown",
                "no license", "no licence", "proprietary")


def _clean(text: Any) -> str:
    s = html.unescape(_TAG.sub(" ", str(text or "")))
    return " ".join(s.split())


def licence_url(name: Any) -> str:
    """The page of a licence this table knows by name ("ODbL 1.0" counts as "ODbL"), else ""."""
    base = _VERSION.sub("", _clean(name)).strip()
    return LICENCE_URLS.get(base, "")


def _service_licence(low: str, toks: list[str]) -> str | None:
    """The canonical name when the text is one of the free picture services' licences, else None. The service's own word is
    needed (or the full name of ODbL): "Pexels" alone or a bare "Content License" with other words does not count."""
    licensed = "license" in toks or "licence" in toks
    if "pexels" in toks and licensed:
        return PEXELS_LICENCE
    if "pixabay" in toks and licensed:
        return PIXABAY_LICENCE
    if toks in (["content", "license"], ["content", "licence"]):          # how Pixabay names it on its pages
        return PIXABAY_LICENCE
    if "odbl" in toks or "open database license" in low or "open database licence" in low:
        m = _VERSION.search(low)
        return ODBL + (" " + m.group(1) if m else "")
    return None


def check_text(text: Any) -> tuple[bool, str, str]:
    """Gate one licence string."""
    raw = _clean(text)
    if not raw:
        return False, "", "licence is missing"
    low = raw.lower()
    toks = _TOKEN.findall(low)

    if any(p in low for p in _BAD_PHRASES):
        return False, raw, f"licence '{raw}' is not on the allow-list (restricted or unclear terms)"
    if _NC.search(low):
        return False, raw, f"licence '{raw}' is non-commercial (NC), which is not allowed"
    if _ND.search(low):
        return False, raw, f"licence '{raw}' is no-derivatives (ND), which is not allowed"

    # the free picture services (Pexels, Pixabay, OpenStreetMap): recorded as allowed; the gate is advisory anyway
    service = _service_licence(low, toks)
    if service:
        return True, service, ""

    # CC0 and public domain
    if "cc0" in toks or ("cc" in toks and "zero" in toks) or "pdm" in toks:
        return True, "CC0" if "pdm" not in toks else "PD", ""
    if "public domain" in low or "publicdomain" in toks or toks[0] == "pd":
        return True, "PD", ""

    # CC BY / CC BY-SA
    is_cc = "cc" in toks or "creative commons" in low
    if is_cc and ("by" in toks or "attribution" in toks):
        sa = "sa" in toks or "sharealike" in toks or "share alike" in low
        name = "CC BY-SA" if sa else "CC BY"
        m = _VERSION.search(low)
        if m:
            name += " " + m.group(1)
        return True, name, ""
    return False, raw, f"licence '{raw}' is not on the allow-list (unknown)"


def _collect_texts(meta: dict) -> list[str]:
    texts: list[str] = []
    for k in _TEXT_KEYS:
        v = meta.get(k)
        if isinstance(v, dict):
            v = v.get("value")
        if v:
            texts.append(str(v))
    ext = meta.get("extmetadata")
    if isinstance(ext, dict):
        for k in ("LicenseShortName", "License", "UsageTerms"):
            v = ext.get(k)
            v = v.get("value") if isinstance(v, dict) else v
            if v:
                texts.append(str(v))
    return texts


def check_texts(texts: Iterable[str]) -> tuple[bool, str, str]:
    """Conservative: any rejecting spelling rejects; otherwise the first accepting one wins."""
    accepted = None
    for t in texts:
        ok, name, reason = check_text(t)
        if not ok and name:           # a recognised bad licence beats everything
            return False, name, reason
        if ok and accepted is None:
            accepted = (ok, name, reason)
    return accepted or (False, "", "licence is missing")


def check_licence(meta: dict) -> tuple[bool, str, str]:
    """Gate a metadata dict (candidate, Commons, Met or yt-dlp shaped)."""
    if not isinstance(meta, dict):
        return False, "", "licence is missing"
    if "isPublicDomain" in meta:                      # Met Open Access record
        if meta.get("isPublicDomain"):
            return True, "CC0", ""
        return False, "", "object is not public domain (Met isPublicDomain is false)"
    return check_texts(_collect_texts(meta))


# ---------------------------------------------------------------------------- advisory flag
# The licence gate is advisory (owner decision, 2026-11-16): an import is never refused for its licence. The result of
# the gate is recorded as `credit.flag`, and the page shows it.
FLAGS = ("rejected", "unknown", "small")
_RESTRICTED = ("fair use", "all rights reserved", "non-commercial", "noncommercial", "no-deriv", "no deriv", "non-free", "nonfree", "copyrighted")


def flag_of(allowed: bool, name: str, reason: str) -> str | None:
    """The licence part of the flag, from a `(allowed, name, reason)` answer of the gate:
    None when the licence is on the allow-list; "unknown" when it is missing or unclear; "rejected" when it is
    recognisably restricted (NC, ND, fair use, not public domain)."""
    if allowed:
        return None
    if not name:
        # an empty name is "missing", except for a Met record that says it is not public domain
        return "rejected" if "not public domain" in (reason or "") else "unknown"
    low = (name + " " + (reason or "")).lower()
    if any(p in low for p in _RESTRICTED) or _NC.search(low) or _ND.search(low):
        return "rejected"
    return "unknown"


def flag_for_text(text: Any) -> str | None:
    return flag_of(*check_text(text))


def flag_for_meta(meta: dict) -> str | None:
    return flag_of(*check_licence(meta))


def with_size_flag(flag: str | None, width: int, height: int, floor: int) -> str | None:
    """`flag`, or "small" when the licence is fine but the picture is under `floor` px on its short side.
    A size of 0 means "not known", which is not small."""
    if flag:
        return flag
    if width and height and floor and min(width, height) < floor:
        return "small"
    return None
