"""Dossiers: one per artwork, merged across the books that cover it. No LLM.

library/dossiers/<artwork_key>/dossier.json + sources/<book_id>_<nnn>.txt (body text only).
Re-runnable at any time: picks up new clean-text pages."""
from __future__ import annotations

import shutil
from pathlib import Path

from . import catalogue, clean, config, extract

PRIORITY = ["payne_gae", "hodge_aid", "brookehitching_mad", "hagen_wgps", "grovier_nws", "dasal_artcurious"]
YEAR_TOLERANCE = 5


def dossiers_dir() -> Path:
    return config.LIB_DIR / "dossiers"


def dossier_path(key: str) -> Path:
    return dossiers_dir() / key / "dossier.json"


def _prio(w: dict) -> int:
    b = w["id"].split("/")[0]
    return PRIORITY.index(b) if b in PRIORITY else 99


def _identity(works: list[dict]) -> dict:
    ws = sorted(works, key=_prio)
    pick = lambda f: next((w[f] for w in ws if w.get(f)), None)
    ident = {"title": pick("title"), "artist": pick("artist"), "year": pick("year")}
    variants, conflicts = {}, []
    for f in ("title", "artist", "year"):
        vals: dict[str, list[str]] = {}
        for w in ws:
            if w.get(f):
                vals.setdefault(str(w[f]), []).append(w["id"])
        variants[f] = [{"value": v, "works": ids} for v, ids in vals.items()]
    # title conflict: different normalised titles
    tn: dict[str, list] = {}
    for w in ws:
        tn.setdefault(catalogue.title_norm(w["title"]), []).append(w)
    if len(tn) > 1:
        conflicts.append({"field": "title", "values": [{"work_id": w["id"], "value": w["title"]} for w in ws]})
    with_artist = [w for w in ws if w.get("artist")]
    if len(with_artist) > 1 and any(not catalogue.artists_match(with_artist[0]["artist"], w["artist"])
                                    for w in with_artist[1:]):
        conflicts.append({"field": "artist", "values": [{"work_id": w["id"], "value": w["artist"]} for w in with_artist]})
    yrs = [w for w in ws if w.get("year_num") is not None and w.get("year") and not w.get("year_from_group")]
    if len(yrs) > 1 and max(w["year_num"] for w in yrs) - min(w["year_num"] for w in yrs) > YEAR_TOLERANCE:
        conflicts.append({"field": "year", "values": [{"work_id": w["id"], "value": w["year"]} for w in yrs]})
    return {"identity": ident, "variants": variants, "conflicts": conflicts}


def build_one(key: str, art: dict, out_dir: Path | None = None) -> dict:
    """Write the dossier of `art` (`{"works": [ids]}`) into `out_dir` (default library/dossiers/<key>)."""
    d = out_dir or (dossiers_dir() / key)
    works = []
    for wid in art["works"]:
        bid, n = wid.split("/")
        w = catalogue.load_work(bid, int(n))
        if w:
            works.append(w)
    works.sort(key=_prio)
    src_dir = d / "sources"
    if src_dir.exists():
        shutil.rmtree(src_dir)
    src_dir.mkdir(parents=True, exist_ok=True)
    sources, images = [], []
    for w in works:
        bid = w["id"].split("/")[0]
        e = clean.entry(w)
        base = f"{bid}_{w['n']:03d}"
        (src_dir / f"{base}.txt").write_text(e["body"] + "\n", encoding="utf-8")
        s = {"work_id": w["id"], "book_id": bid, "n": w["n"], "pdf_pages": w["pdf_pages"], "words": e["words"],
             "text_source": e["text_source"], "ocr": e["ocr"], "title": w["title"], "artist": w.get("artist"),
             "year": w.get("year"), "file": f"sources/{base}.txt", **catalogue.book_trust(bid), "outline": e["outline"],
             "pages_clean": sum(1 for p in e["pages"] if p["source"] == "clean"), "pages_total": len(e["pages"])}
        if w.get("headline"):
            s["headline"] = w["headline"]
        sources.append(s)
        for im in extract.images(bid, *w["pdf_pages"]):
            images.append({"work_id": w["id"], **im})
    ident = _identity(works)
    srcs = {s["text_source"] for s in sources}
    doc = {"artwork_key": key, "kind": "theme" if key.startswith("theme-") else "artwork", **ident, "sources": sources,
           "totals": {"books": len({s["book_id"] for s in sources}), "sources": len(sources),
                      "words": sum(s["words"] for s in sources),
                      "words_normal": sum(s["words"] for s in sources if s["trust"] == "normal"),
                      "words_low": sum(s["words"] for s in sources if s["trust"] == "low"),
                      "pages_clean": sum(s["pages_clean"] for s in sources),
                      "pages_total": sum(s["pages_total"] for s in sources)},
           "only_low_trust": bool(sources) and all(s["trust"] == "low" for s in sources),
           "images": images,
           "details": next((s["outline"]["details"] for s in sources if s["outline"].get("details")), []),
           "rights": min((w.get("rights") or {"status": "unknown"} for w in works),
                         key=lambda r: ["copyright_likely", "unknown", "pd_likely"].index(r["status"]),
                         default={"status": "unknown", "basis": ""}),
           "text_source": "clean" if srcs == {"clean"} else "layer" if srcs == {"layer"} else "mixed"}
    catalogue.write_json(d / "dossier.json", doc)
    return doc


def build_all(keys: list[str] | None = None, log=print) -> dict:
    arts = catalogue.load_artworks()
    todo = keys if keys is not None else list(arts)
    done = {}
    for k in todo:
        if k in arts:
            done[k] = build_one(k, arts[k])
    if keys is None:  # drop dossiers of artworks that no longer exist (after a merge or split)
        root = dossiers_dir()
        if root.is_dir():
            for d in root.iterdir():
                if d.is_dir() and d.name not in arts:
                    shutil.rmtree(d)
    else:
        for k in keys:
            if k not in arts and (dossiers_dir() / k).is_dir():
                shutil.rmtree(dossiers_dir() / k)
    return done


def load(key: str) -> dict | None:
    """The dossier of an artwork; None when there is none (or the key cannot be a folder name). A file that is there but
    damaged raises catalogue.LibraryDataError (a ValueError that names the file); a dossier that is not an object too."""
    if not isinstance(key, str) or not key or "\x00" in key or "/" in key or len(key.encode("utf-8", "ignore")) > 200:
        return None
    f = dossier_path(key)
    try:
        if not f.is_file():
            return None
    except OSError:
        return None
    d = catalogue.read_json(f)
    if not isinstance(d, dict):
        raise catalogue.LibraryDataError("dossier.json of %s is corrupt: the top level must be an object" % key[:60])
    return d


def summary(done: dict) -> dict:
    multi = [d for d in done.values() if d["totals"]["sources"] >= 2]
    srcs = [s["text_source"] for d in done.values() for s in d["sources"]]
    pc = sum(d["totals"]["pages_clean"] for d in done.values())
    pt = sum(d["totals"]["pages_total"] for d in done.values())
    top = sorted(done.values(), key=lambda d: -d["totals"]["words"])[:5]
    return {"artworks": len(done), "with_2plus_sources": len(multi),
            "largest": [(d["artwork_key"], d["totals"]["words"], d["totals"]["sources"]) for d in top],
            "conflicts": sum(len(d["conflicts"]) for d in done.values()),
            "artworks_with_conflicts": sum(1 for d in done.values() if d["conflicts"]),
            "sources_by_text": {k: srcs.count(k) for k in ("clean", "mixed", "layer")},
            "pages_clean": pc, "pages_total": pt}


# ------------------------------------------------------------------ manual merge / split
def _refresh(before: dict) -> dict:
    """After a regroup: rebuild dossiers of artworks that are new or changed, drop vanished ones."""
    after = catalogue.load_artworks()
    old = {k: tuple(a["works"]) for k, a in before.items()}
    changed = [k for k, a in after.items() if old.get(k) != tuple(a["works"])]
    for k in before:
        if k not in after and (dossiers_dir() / k).is_dir():
            shutil.rmtree(dossiers_dir() / k)
    build_all(changed)
    return after


def merge_artworks(key_a: str, key_b: str) -> str:
    """Force the entries of two artworks into one (written to library/overrides/artworks.json). Returns the key."""
    arts = catalogue.load_artworks()
    if key_a not in arts or key_b not in arts:
        raise KeyError("artwork not found")
    if key_a == key_b:
        raise ValueError("cannot merge an artwork with itself")
    ids = arts[key_a]["works"] + arts[key_b]["works"]
    ovr = catalogue.load_artwork_overrides()
    ovr["split"] = [x for x in ovr["split"] if x not in ids]
    keep, fused = [], set(ids)
    for g in ovr["merge"]:
        if fused & set(g):
            fused |= set(g)
        else:
            keep.append(g)
    ovr["merge"] = keep + [sorted(fused)]
    catalogue.save_artwork_overrides(ovr)
    catalogue.regroup()
    after = _refresh(arts)
    return next(k for k, a in after.items() if ids[0] in a["works"])


def split_work(work_id: str) -> str:
    """Take one entry out of its artwork: it becomes its own artwork and is never auto-merged again."""
    arts = catalogue.load_artworks()
    key = next((k for k, a in arts.items() if work_id in a["works"]), None)
    if key is None:
        raise KeyError("work not found")
    if len(arts[key]["works"]) < 2:
        raise ValueError("the artwork has only one source")
    ovr = catalogue.load_artwork_overrides()
    ovr["merge"] = [g for g in ([x for x in g if x != work_id] for g in ovr["merge"]) if len(g) >= 2]
    if work_id not in ovr["split"]:
        ovr["split"].append(work_id)
    catalogue.save_artwork_overrides(ovr)
    catalogue.regroup()
    after = _refresh(arts)
    return next(k for k, a in after.items() if work_id in a["works"])
