"""Licence allow-list gate (PLAN.md section 5, rule 1).

Allowed: public domain, CC0, CC BY, CC BY-SA (any version).
Rejected: anything NC or ND, "fair use", unknown, missing.

`check_text(text)` and `check_licence(meta)` return `(allowed, licence_name, reason)`.
`licence_name` is canonical when recognised ("PD", "CC0", "CC BY 4.0", "CC BY-SA 3.0"),
otherwise the cleaned input text. `reason` is "" when allowed.
"""
from __future__ import annotations

import html
import re
from typing import Any, Iterable

ALLOWED_NAMES = ("PD", "CC0", "CC BY", "CC BY-SA")

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
