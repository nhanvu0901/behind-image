"""The brief: deterministic, no model. Built on demand from projects/<id>/source/ (design section 2.1).

Tolerates two project shapes: the dossier shape (project.json -> source/dossier.json + source/<book>_<nnn>.txt)
and the older shape (project.json `sources` list, or only the .txt files).
Source text files hold body text only: `# ` title, `## ` section headings, `> ` quotes, one paragraph per line.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .store import DocumentCorrupt, now_iso, read_object, read_text_strict, script_dir, write_json_atomic
from .. import textfold

REPO_ROOT = Path(__file__).resolve().parents[2]

SRC_CODES = {"payne_gae": "PAY", "hodge_aid": "HOD", "hagen_wgps": "HAG", "brookehitching_mad": "MAD",
             "dasal_artcurious": "DAS", "grovier_nws": "GRO"}
LOW_NOTE = "low trust (machine translation): not a basis for facts"
DEFAULT_TARGET = 2000
DEFAULT_WPS = 2.41
PARA_ID_RE = re.compile(r"\b([A-Z]{3})-(\d{2,3})\b")
_TAGGED = re.compile(r"^\[(meta|caption|credit|note|page-type|continues)\]", re.I)


def _read_json(p: Path, what: str = "script") -> dict:
    """The JSON object in `p`, {} when the file does not exist. A file that is there but unreadable or not an object raises
    DocumentCorrupt naming it (409 for the page): a damaged input is never replaced by defaults without a word."""
    return read_object(p, what) or {}


def src_code(book_id: str, taken: set[str]) -> str:
    code = SRC_CODES.get(book_id) or (re.sub(r"[^a-z]", "", book_id.lower())[:3].upper().ljust(3, "X"))
    base, i = code, 0
    while code in taken:
        i += 1
        code = base[:2] + chr(ord("A") + (i % 26))
    return code


def parse_source_text(text: str) -> dict:
    """-> {"title", "sections": [..], "paragraphs": [{"n","text","section","kind"}]}"""
    title, section, paras, sections = "", "", [], []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line or _TAGGED.match(line):
            continue
        if line.startswith("## "):
            section = line[3:].strip()
            if section and section not in sections:
                sections.append(section)
        elif line.startswith("# "):
            title = title or line[2:].strip()
        else:
            kind = "body"
            if line.startswith("> "):
                kind, line = "quote", line[2:].strip()
            elif line.startswith("[quote]"):
                kind, line = "quote", line[7:].strip()
            if line:
                paras.append({"n": len(paras) + 1, "text": line, "section": section, "kind": kind})
    return {"title": title, "sections": sections, "paragraphs": paras}


def _book_info(book_id: str, lib: Path) -> dict:
    j = _read_json(lib / "books" / book_id / "book.json", "library")
    return {"title": j.get("title") or book_id, "author": j.get("author") or ""}


def _trust_table(lib: Path) -> dict:
    return _read_json(lib / "overrides" / "books.json", "library")


def _resolve_dossier(pdir: Path, proj: dict) -> tuple[dict | None, Path | None]:
    for cand in (proj.get("dossier"), "source/dossier.json"):
        if cand and not Path(str(cand)).is_absolute():
            p = pdir / str(cand)
            if p.is_file():
                d = _read_json(p, "source")
                _need_shape(d, p.name, "source", [("identity", dict), ("sources", list), ("conflicts", list)],
                            [("sources", dict), ("conflicts", dict)])
                return d, p
    return None, None


def _need_shape(d: dict, name: str, what: str, kinds: list, items: list) -> None:
    """The fields of `d` that the brief reads have the type it expects (a list of objects, not a list of numbers...)."""
    for k, t in kinds:
        if d.get(k) is not None and not isinstance(d[k], t):
            raise DocumentCorrupt(f"{name} is corrupt: {k} must be {'an object' if t is dict else 'a list'}", what)
    for k, t in items:
        if any(not isinstance(x, t) for x in d.get(k) or []):
            raise DocumentCorrupt(f"{name} is corrupt: every entry of {k} must be an object", what)


def load_options(pdir: Path) -> dict:
    return _options_from(_read_json(script_dir(pdir) / "brief_options.json"))


def _options_from(o: dict) -> dict:
    tw = o.get("target_words")
    low = o.get("include_low")
    exc = o.get("exclude")
    return {"include_low": [str(x) for x in low if isinstance(x, (str, int))] if isinstance(low, list) else [],
            "exclude": [str(x) for x in exc if isinstance(x, (str, int))] if isinstance(exc, list) else [],
            "target_words": int(tw) if isinstance(tw, (int, float)) and not isinstance(tw, bool) and math.isfinite(tw) and tw > 0 else DEFAULT_TARGET,
            "notes": str(o.get("notes") or ""),
            "wps": float(o["wps"]) if isinstance(o.get("wps"), (int, float)) and 0.5 <= o["wps"] <= 6 else DEFAULT_WPS}


class OptionsError(ValueError):
    """A brief option is out of range or of the wrong type; the message names the option and the allowed values."""

    def __init__(self, message: str, code: str = "options_error"):
        super().__init__(message)
        self.code = code


def check_options(opts: dict) -> dict:
    """The options of `opts` that are present, validated; raises OptionsError. Nothing is coerced or silently dropped."""
    out: dict = {}
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v   # noqa: E731
    if "include_low" in opts:
        v = opts["include_low"]
        if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
            raise OptionsError("include_low must be a list of strings (book ids, work ids or source codes)")
        out["include_low"] = sorted(set(v))
    if "exclude" in opts:
        v = opts["exclude"]
        if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
            raise OptionsError("exclude must be a list of strings (book ids, work ids or source codes)")
        out["exclude"] = sorted(set(v))
    if "target_words" in opts:
        v = opts["target_words"]
        if not (num(v) and 300 <= v <= 20000):
            raise OptionsError("target_words must be a number from 300 to 20000")
        out["target_words"] = int(v)
    if "notes" in opts:
        v = opts["notes"]
        if not isinstance(v, str):
            raise OptionsError("notes must be a string")
        if len(v) > 4000:
            raise OptionsError("notes may have at most 4000 characters")
        out["notes"] = v
    if "wps" in opts:
        v = opts["wps"]
        if not (num(v) and 0.5 <= v <= 6):
            raise OptionsError("wps (words per second) must be a number from 0.5 to 6")
        out["wps"] = float(v)
    return out


def save_options(pdir: Path, opts: dict, *, library_root: Path | None = None) -> dict:
    new = check_options(opts)           # raises OptionsError before anything is written
    try:
        cur = load_options(pdir)
    except DocumentCorrupt:             # a damaged file is replaced by a whole, valid one: this is how the owner repairs it
        cur = _options_from({})
    cur.update(new)

    pdir = Path(pdir)
    lib = Path(library_root) if library_root else REPO_ROOT / "library"
    proj = _read_json(pdir / "project.json", "project")
    dossier, _ = _resolve_dossier(pdir, proj)
    entries = _source_entries(pdir, proj, dossier)
    if entries:
        ticked = set(cur.get("include_low", []))
        excluded = set(cur.get("exclude", []))
        trust_tbl = _trust_table(lib)
        taken: set[str] = set()
        included_count = 0
        for e in entries:
            code = src_code(e["book_id"], taken)
            taken.add(code)
            trust = e["trust"] or (trust_tbl.get(e["book_id"]) or {}).get("trust") or "normal"
            low = trust == "low"
            is_excluded = e["book_id"] in excluded or e["work_id"] in excluded or code in excluded
            is_low_included = e["book_id"] in ticked or e["work_id"] in ticked or code in ticked
            inc = (not is_excluded) and ((not low) or is_low_included)
            if inc:
                included_count += 1
        if included_count == 0:
            raise OptionsError("at least one source must stay", code="at_least_one_source")

    write_json_atomic(script_dir(pdir) / "brief_options.json", cur)
    return cur


def _source_entries(pdir: Path, proj: dict, dossier: dict | None) -> list[dict]:
    """[{work_id, book_id, file, trust, trust_note, meta, title, artist, year}] in a stable order."""
    src_dir = pdir / "source"
    out: list[dict] = []
    if dossier and dossier.get("sources"):
        for s in dossier["sources"]:
            out.append({"work_id": s.get("work_id") or "", "book_id": s.get("book_id") or "",
                        "file": s.get("file") or "", "trust": s.get("trust"), "trust_note": s.get("trust_note") or "",
                        "meta": list((s.get("outline") or {}).get("meta") or []),
                        "details": list((s.get("outline") or {}).get("details") or []),
                        "words": s.get("words")})
    elif proj.get("sources"):
        for s in proj["sources"]:
            wid = s.get("work_id") or ""
            book = s.get("book_id") or wid.split("/")[0]
            n = wid.split("/")[1] if "/" in wid else ""
            out.append({"work_id": wid, "book_id": book, "file": f"{book}_{n}.txt" if n else "", "trust": None,
                        "trust_note": "", "meta": [], "details": [], "words": None})
    known = {e["file"] for e in out}
    if src_dir.is_dir():
        for f in sorted(src_dir.glob("*.txt")):
            if f.name not in known:
                m = re.match(r"^(.+)_(\d+)\.txt$", f.name)
                book = m.group(1) if m else f.stem
                out.append({"work_id": f"{book}/{m.group(2)}" if m else f.stem, "book_id": book, "file": f.name,
                            "trust": None, "trust_note": "", "meta": [], "details": [], "words": None})
    return [e for e in out if e["file"] and (src_dir / e["file"]).is_file()]


def build_brief(pdir: Path, *, library_root: Path | None = None, include_low: list[str] | None = None,
                exclude: list[str] | None = None) -> dict:
    try:
        return _build_brief(pdir, library_root=library_root, include_low=include_low, exclude=exclude)
    except (AttributeError, TypeError, KeyError, IndexError, ValueError) as e:      # a field of the wrong type deep inside a data file
        if isinstance(e, DocumentCorrupt):
            raise
        raise DocumentCorrupt(f"the data files of project {Path(pdir).name!r} are malformed ({type(e).__name__})", "project")


def _build_brief(pdir: Path, *, library_root: Path | None = None, include_low: list[str] | None = None,
                 exclude: list[str] | None = None) -> dict:
    pdir = Path(pdir)
    lib = Path(library_root) if library_root else REPO_ROOT / "library"
    proj = _read_json(pdir / "project.json", "project")
    _need_shape(proj, "project.json", "project", [("sources", list)], [("sources", dict)])
    dossier, _ = _resolve_dossier(pdir, proj)
    opts = load_options(pdir)
    ticked = set(include_low if include_low is not None else opts["include_low"])
    excluded = set(exclude if exclude is not None else opts.get("exclude", []))
    trust_tbl = _trust_table(lib)

    ident = (dossier or {}).get("identity") or {}
    painting = {"title": ident.get("title") or proj.get("title") or pdir.name,
                "artist": ident.get("artist") or proj.get("artist") or "",
                "year": str(ident.get("year") or proj.get("year") or ""), "meta": {}}

    sources, taken, code_map = [], set(), {}
    for e in _source_entries(pdir, proj, dossier):
        code = src_code(e["book_id"], taken)
        taken.add(code)
        code_map[code] = e["work_id"]
        parsed = parse_source_text(read_text_strict(pdir / "source" / e["file"]))
        trust = e["trust"] or (trust_tbl.get(e["book_id"]) or {}).get("trust") or "normal"
        note = e["trust_note"] or (trust_tbl.get(e["book_id"]) or {}).get("trust_note") or ""
        low = trust == "low"
        is_excluded = e["book_id"] in excluded or e["work_id"] in excluded or code in excluded
        is_low_included = e["book_id"] in ticked or e["work_id"] in ticked or code in ticked
        included = (not is_excluded) and ((not low) or is_low_included)
        width = 3 if len(parsed["paragraphs"]) > 99 else 2
        paras = [{"id": f"{code}-{p['n']:0{width}d}", **p} for p in parsed["paragraphs"]]
        if e["meta"]:
            painting["meta"][code] = e["meta"]
        bi = _book_info(e["book_id"], lib)
        sources.append({"code": code, "work_id": e["work_id"], "book_id": e["book_id"], "book_title": bi["title"],
                        "author": bi["author"], "trust": trust, "trust_note": note or (LOW_NOTE if low else ""),
                        "low_trust": low, "included": included, "excluded": is_excluded, "file": e["file"],
                        "title": parsed["title"], "sections": parsed["sections"], "detail_headings": e["details"],
                        "words": sum(len(p["text"].split()) for p in paras), "paragraphs": paras})

    # named details: Hodge detail headings and the section headings of the other sources
    details: dict[str, dict] = {}
    for s in sources:
        if not s["included"]:
            continue
        heads = s["detail_headings"] if s["book_id"] == "hodge_aid" and s["detail_headings"] else s["sections"]
        for h in heads:
            key = textfold.norm(h)
            if not key:
                continue
            d = details.setdefault(key, {"name": h, "where": []})
            ids = [p["id"] for p in s["paragraphs"] if p["section"] == h]
            d["where"].append({"src": s["code"], "paras": ids})
    det_list = [{"id": f"D{i + 1}", **d} for i, d in enumerate(details.values())]

    conflicts = []
    for c in (dossier or {}).get("conflicts") or []:
        conflicts.append({"field": c.get("field"), "values": [
            {"work_id": v.get("work_id"), "src": next((k for k, w in code_map.items() if w == v.get("work_id")), None),
             "value": v.get("value")} for v in c.get("values") or []]})

    return {"project": proj.get("id") or pdir.name, "built_at": now_iso(),
            "shape": "dossier" if dossier else ("project" if proj.get("sources") else "files"),
            "painting": painting, "sources": sources, "code_map": code_map, "details": det_list,
            "conflicts": conflicts, "options": {**opts, "include_low": sorted(ticked), "exclude": sorted(excluded)},
            "paragraph_ids": sorted(p["id"] for s in sources for p in s["paragraphs"]),
            "totals": {"sources": len(sources), "included": sum(1 for s in sources if s["included"]),
                       "paragraphs": sum(len(s["paragraphs"]) for s in sources),
                       "words": sum(s["words"] for s in sources if s["included"])}}


def render_brief(brief: dict) -> str:
    """The text block put into the prompts."""
    p = brief["painting"]
    L = ["THE PAINTING", f"Title: {p['title']}", f"Artist: {p['artist']}", f"Year: {p['year']}"]
    for code, lines in p["meta"].items():
        L.append(f"Meta ({code}): " + "; ".join(str(x) for x in lines))
    L += ["", "SOURCES (code = source work)"]
    for s in brief["sources"]:
        flag = "" if s["included"] else "  [NOT INCLUDED, text withheld]"
        low = f"  [LOW TRUST: {s['trust_note']}]" if s["low_trust"] else ""
        L.append(f"{s['code']} = {s['work_id']}: {s['book_title']}" + (f", {s['author']}" if s["author"] else "") + low + flag)
    if brief["details"]:
        L += ["", "NAMED DETAILS (candidates for what the camera points at)"]
        for d in brief["details"]:
            where = "; ".join(f"{w['src']}: {', '.join(w['paras']) or 'heading only'}" for w in d["where"])
            L.append(f"{d['id']} {d['name']}  [{where}]")
    if brief["conflicts"]:
        L += ["", "CONFLICTS BETWEEN SOURCES (on identity; do not resolve silently)"]
        for c in brief["conflicts"]:
            L.append(f"{c['field']}: " + " vs ".join(f"{v.get('src') or v.get('work_id')} says {v.get('value')!r}" for v in c["values"]))
    for s in brief["sources"]:
        if not s["included"]:
            continue
        L += ["", f"=== SOURCE {s['code']}: {s['book_title']} ({s['work_id']})" + (" [LOW TRUST]" if s["low_trust"] else "") + " ==="]
        cur = None
        for para in s["paragraphs"]:
            if para["section"] != cur:
                cur = para["section"]
                if cur:
                    L.append(f"-- section: {cur}")
            q = " (quotation)" if para["kind"] == "quote" else ""
            L.append(f"[{para['id']}]{q} {para['text']}")
    return "\n".join(L)
