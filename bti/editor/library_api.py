"""HTTP API of the book library (front door of the pipeline). Mounted from app.py.

Local, private research tool: reads books/ and library/, writes only projects/<slug>/ and library/cache/.
No endpoint exports or publishes book pages beyond rendering them for the local page."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Body, Query
from fastapi.responses import FileResponse

from bti.library import catalogue, config as libcfg, dossiers, extract
from bti.library import projects as libprojects

from .common import ApiError, read_json, segment_ok, storyboard_approval, string_list, valid_pid

CENTURY_MAX = 21


def _book(book_id: str) -> dict:
    if not libcfg.BOOK_ID_RE.fullmatch(book_id) or book_id not in libcfg.BOOK_BY_ID:
        raise ApiError(404, "book not found", code="book_not_found")
    f = libcfg.book_dir(book_id) / "book.json"
    if not f.is_file():
        raise ApiError(404, "book not catalogued; run python -m bti.library build", code="book_not_catalogued")
    return catalogue.read_json(f)


def _work(book_id: str, n: int) -> dict:
    _book(book_id)
    w = catalogue.load_work(book_id, n)
    if w is None:
        raise ApiError(404, "work not found", code="work_not_found")
    return w


def century(w: dict) -> int | None:
    y = w.get("year_num")
    if y is None:
        return None
    return (y - 1) // 100 + 1 if y > 0 else 0


def make_router(projects_root: Path) -> APIRouter:
    r = APIRouter(prefix="/api/library")

    def project_index() -> dict[str, list[dict]]:
        """work_id -> projects that use it."""
        idx: dict[str, list[dict]] = {}
        if not projects_root.is_dir():
            return idx
        for d in sorted(projects_root.iterdir()):
            f = d / "project.json"
            if not (valid_pid(d.name) and f.is_file()):
                continue
            try:                    # a damaged project is left out of the index; it never breaks the list for the others
                p = read_json(f)
                if not isinstance(p, dict):
                    continue
                srcs = [s for s in (p.get("sources") if isinstance(p.get("sources"), list) else []) if isinstance(s, dict)]
                entry = {"id": d.name, "stage": libprojects.infer_stage(d), "has_storyboard": (d / "storyboard.json").is_file()}
            except Exception:       # noqa: BLE001
                continue
            for s in srcs:
                wid = s.get("work_id")
                if isinstance(wid, str):
                    idx.setdefault(wid, []).append(dict(entry))
        return idx

    def others(w: dict, arts: dict) -> list[dict]:
        a = arts.get(w.get("artwork_key") or "") or {}
        out = []
        for wid in a.get("works", []):
            if wid == w["id"]:
                continue
            bid, n = wid.split("/")
            ow = catalogue.load_work(bid, int(n))
            out.append({"work_id": wid, "book_id": bid, "n": int(n), "title": ow["title"] if ow else None,
                        "pdf_pages": ow["pdf_pages"] if ow else None})
        return out

    def row(w: dict, arts: dict, pidx: dict) -> dict:
        bid = w["id"].split("/")[0]
        return {**{k: w.get(k) for k in ("id", "n", "title", "artist", "year", "year_raw", "headline", "pdf_pages", "words",
                                         "n_images", "artwork_key", "rights")},
                "book_id": bid, "century": century(w), "also_in": others(w, arts),
                "projects": pidx.get(w["id"], []),
                "thumb_url": f"/api/library/works/{bid}/{w['n']}/page/{w['pdf_pages'][0]}.jpg?w=240"}

    @r.get("/books")
    def books():
        pidx = project_index()
        out = []
        for b in catalogue.load_books():
            ws = catalogue.load_works(b["id"])
            out.append({**b, "n_with_project": sum(1 for w in ws if pidx.get(w["id"])),
                        "cover_url": f"/api/library/books/{b['id']}/cover.jpg?w=300"})
        return out

    @r.get("/books/{book_id}/cover.jpg")
    def cover(book_id: str, w: int = Query(300)):
        _book(book_id)
        return _jpeg(book_id, 1, w)

    @r.get("/books/{book_id}/works")
    def works(book_id: str, q: str = "", century_: int | None = Query(None, alias="century"),
              rights: str = "", multi: bool = False):
        _book(book_id)
        arts, pidx = catalogue.load_artworks(), project_index()
        ql = catalogue.norm(q)
        out = []
        for w in catalogue.load_works(book_id):
            rw = row(w, arts, pidx)
            if ql:
                hay = catalogue.norm(" ".join(str(x or "") for x in (w["title"], w.get("artist"), w.get("year"),
                                                                       w.get("headline"))))
                if ql not in hay:
                    continue
            if century_ is not None and rw["century"] != century_:
                continue
            if rights and (w.get("rights") or {}).get("status") != rights:
                continue
            if multi and not rw["also_in"]:
                continue
            out.append(rw)
        return out

    @r.get("/works/{book_id}/{n}")
    def work_detail(book_id: str, n: int):
        w = _work(book_id, n)
        arts, pidx = catalogue.load_artworks(), project_index()
        t = extract.work_text(w)
        a, b = w["pdf_pages"]
        imgs = [{**im, "url": f"/api/library/works/{book_id}/{n}/image/{im['xref']}.jpg?w=700"}
                for im in extract.images(book_id, a, b)]
        return {**row(w, arts, pidx), "headings": w.get("headings", []), "text": t["text"], "ocr": t["ocr"],
                "text_source": t["text_source"],
                "pages": [{"page": p, "url": f"/api/library/works/{book_id}/{n}/page/{p}.jpg?w=900"}
                          for p in range(a, b + 1)],
                "images": imgs, "rights_note": catalogue.RIGHTS_NOTE}

    @r.get("/works/{book_id}/{n}/page/{pdf_page}.jpg")
    def work_page(book_id: str, n: int, pdf_page: int, w: int = Query(800)):
        wk = _work(book_id, n)
        a, b = wk["pdf_pages"]
        if not a <= pdf_page <= b:
            raise ApiError(404, "page is not part of this entry", code="page_not_in_work")
        return _jpeg(book_id, pdf_page, w)

    @r.get("/works/{book_id}/{n}/image/{xref}.jpg")
    def work_image(book_id: str, n: int, xref: int, w: int = Query(700)):
        wk = _work(book_id, n)
        a, b = wk["pdf_pages"]
        if xref not in {im["xref"] for im in extract.images(book_id, a, b)}:
            raise ApiError(404, "image is not part of this entry", code="image_not_in_work")
        if not 64 <= w <= 2400:
            raise ApiError(422, "w must be between 64 and 2400", code="field_invalid", field="w")
        try:
            return FileResponse(extract.render_image(book_id, xref, w), media_type="image/jpeg",
                                headers={"Cache-Control": "private, max-age=86400"})
        except Exception:
            raise ApiError(415, "cannot extract this image", code="image_extract_failed")

    def art_row(key: str, a: dict, arts_pidx: dict) -> dict:
        bad = None
        try:
            d = dossiers.load(key) or {}
        except ValueError as e:     # this artwork's dossier is damaged: its row falls back to the catalogue, the list still works
            d, bad = {}, str(e)[:200]
        ids = a["works"]
        books_ = []
        yn = None
        status = "unknown"
        projs = []
        for wid in ids:
            bid, n = wid.split("/")
            books_.append(bid)
            w = catalogue.load_work(bid, int(n))
            if w and yn is None and w.get("year_num") is not None:
                yn = w["year_num"]
            for p in arts_pidx.get(wid, []):
                if p["id"] not in [x["id"] for x in projs]:
                    projs.append(p)
        rt = d.get("rights") or {"status": "unknown", "basis": ""}
        return {"artwork_key": key, "title": d.get("identity", {}).get("title") or a["title"],
                "artist": d.get("identity", {}).get("artist") or a.get("artist"),
                "year": d.get("identity", {}).get("year") or a.get("year"), "year_raw": a.get("year_raw"), "kind": d.get("kind", "artwork"),
                "century": None if yn is None else ((yn - 1) // 100 + 1 if yn > 0 else 0),
                "books": books_, "n_sources": len(ids), "words": (d.get("totals") or {}).get("words", 0),
                "words_normal": (d.get("totals") or {}).get("words_normal", 0),
                "words_low": (d.get("totals") or {}).get("words_low", 0),
                "only_low_trust": bool(d.get("only_low_trust")),
                "low_trust_books": [b for b in books_ if catalogue.book_trust(b)["trust"] == "low"],
                "text_source": d.get("text_source"), "n_conflicts": len(d.get("conflicts") or []),
                "rights": rt, "projects": projs,
                "thumb_url": _thumb_for(ids[0]), **({"data_error": bad} if bad else {})}

    def _thumb_for(wid: str) -> str:
        bid, n = wid.split("/")
        w = catalogue.load_work(bid, int(n))
        pg = w["pdf_pages"][0] if w else 1
        return f"/api/library/works/{bid}/{n}/page/{pg}.jpg?w=240"

    @r.get("/artworks")
    def artworks_list(q: str = "", century_: int | None = Query(None, alias="century"), has_project: bool | None = None,
                      min_sources: int = 1, kind: str = "artwork", rights: str = "", sort: str = "sources"):
        arts, pidx = catalogue.load_artworks(), project_index()
        ql = catalogue.norm(q)
        out = []
        for k, a in arts.items():
            row_ = art_row(k, a, pidx)
            if kind and row_["kind"] != kind:
                continue
            if ql and ql not in catalogue.norm(f"{row_['title']} {row_['artist'] or ''} {row_['year'] or ''} {k}"):
                continue
            if century_ is not None and row_["century"] != century_:
                continue
            if has_project is not None and bool(row_["projects"]) != has_project:
                continue
            if row_["n_sources"] < min_sources:
                continue
            if rights and row_["rights"]["status"] != rights:
                continue
            out.append(row_)
        keyf = {"sources": lambda x: (-x["n_sources"], -x["words"], x["title"] or ""),
                "words": lambda x: (-x["words"], x["title"] or ""),
                "title": lambda x: (catalogue.norm(x["title"]),),
                "year": lambda x: (x["century"] is None, x["century"] or 0, catalogue.norm(x["title"]))}.get(sort)
        if keyf is None:
            raise ApiError(422, "sort must be sources, words, title or year", code="field_invalid", field="sort")
        out.sort(key=keyf)
        return out

    @r.get("/artworks/{artwork_key}")
    def artwork(artwork_key: str):
        arts = catalogue.load_artworks()
        cur = arts.resolve(artwork_key) if segment_ok(artwork_key) else None   # an old key (alias) opens the current artwork
        a = arts.get(cur) if cur else None
        if a is None:
            raise ApiError(404, "artwork not found", code="artwork_not_found")
        artwork_key, pidx = cur, project_index()
        ws = []
        for wid in a["works"]:
            bid, n = wid.split("/")
            w = catalogue.load_work(bid, int(n))
            if w:
                ws.append(row(w, arts, pidx))
        d = dossiers.load(artwork_key)
        if d is not None:
            for s in d["sources"]:
                s.update(catalogue.book_trust(s["book_id"]))  # live, so a change in overrides/books.json shows at once
                s["text_url"] = f"/api/library/artworks/{artwork_key}/source/{Path(s['file']).stem}"
                s["pages"] = [{"page": p, "url": f"/api/library/works/{s['book_id']}/{s['n']}/page/{p}.jpg?w=900"}
                              for p in range(s["pdf_pages"][0], s["pdf_pages"][1] + 1)]
            for im in d["images"]:
                bid, n = im["work_id"].split("/")
                im["url"] = f"/api/library/works/{bid}/{int(n)}/image/{im['xref']}.jpg?w=700"
        return {"artwork_key": artwork_key, **a, "works_detail": ws, "dossier": d,
                "projects": art_row(artwork_key, a, pidx)["projects"], "rights_note": catalogue.RIGHTS_NOTE}

    @r.get("/artworks/{artwork_key}/source/{name}")
    def artwork_source(artwork_key: str, name: str):
        if not (segment_ok(artwork_key) and segment_ok(name)):
            raise ApiError(404, "dossier not found", code="dossier_not_found")
        artwork_key = catalogue.resolve_key(artwork_key) or artwork_key
        d = dossiers.load(artwork_key)
        if d is None:
            raise ApiError(404, "dossier not found", code="dossier_not_found")
        s = next((x for x in d["sources"] if Path(x["file"]).stem == name), None)
        if s is None:
            raise ApiError(404, "source not found", code="source_not_found")
        f = dossiers.dossier_path(artwork_key).parent / s["file"]
        try:
            if not f.is_file():
                raise ApiError(404, "source text missing", code="source_text_missing")
            return {"work_id": s["work_id"], "text": f.read_text(encoding="utf-8")}
        except UnicodeDecodeError:
            raise ApiError(409, f"{f.name} is not UTF-8 text", data_error="library", code="library_file_unreadable")
        except PermissionError:
            raise ApiError(409, f"{f.name} cannot be read (permission denied)", data_error="library", code="library_file_unreadable")
        except OSError:
            raise ApiError(404, "source text missing", code="source_text_missing")

    @r.post("/artworks/merge")
    def merge(body: dict = Body(...)):
        a, b = body.get("key"), body.get("with")
        if not isinstance(a, str) or not isinstance(b, str):
            raise ApiError(422, "key and with (artwork keys) are required", code="field_required", field="key" if not isinstance(a, str) else "with")
        try:
            return {"artwork_key": dossiers.merge_artworks(a, b)}
        except KeyError:
            raise ApiError(404, "artwork not found", code="artwork_not_found")
        except ValueError as e:
            raise ApiError(422, str(e), code="merge_refused")

    @r.post("/artworks/split")
    def split(body: dict = Body(...)):
        wid = body.get("work_id")
        if not isinstance(wid, str) or not libcfg.WORK_ID_RE.fullmatch(wid):
            raise ApiError(422, "work_id is required", code="field_required", field="work_id")
        try:
            return {"artwork_key": dossiers.split_work(wid)}
        except KeyError:
            raise ApiError(404, "work not found", code="work_not_found")
        except ValueError as e:
            raise ApiError(422, str(e), code="split_refused")

    @r.post("/projects")
    def create(body: dict = Body(...)):
        wids = string_list(body.get("work_ids"), "work_ids", max_items=50, max_len=100)
        slug = body.get("slug") or None
        key = body.get("artwork_key")
        excl = string_list(body.get("exclude"), "exclude", max_items=50, max_len=100)
        if slug is not None and not isinstance(slug, str):
            raise ApiError(422, "slug must be a string", code="field_invalid", field="slug")
        if key is not None and not isinstance(key, str):
            raise ApiError(422, "artwork_key must be a string", code="field_invalid", field="artwork_key")
        try:
            return libprojects.create_project(wids, slug, projects_root, artwork_key=key, exclude=excl)
        except libprojects.ProjectError as e:
            raise ApiError(e.status, str(e), code="project_create_refused")
        except FileNotFoundError as e:
            raise ApiError(404, str(e), code="project_source_missing")

    return r


def _jpeg(book_id: str, pdf_page: int, w: int):
    if not 64 <= w <= 2400:
        raise ApiError(422, "w must be between 64 and 2400", code="field_invalid", field="w")
    try:
        f = extract.render_page(book_id, pdf_page, w)
    except IndexError:
        raise ApiError(404, "page not found", code="page_not_found")
    except FileNotFoundError:
        raise ApiError(404, "book PDF is missing", code="book_pdf_missing")
    return FileResponse(f, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


def stage_of(d: Path, states: dict | None = None) -> str:
    from bti.script.stage import bump_stage   # adds `outlined` / `script` from the approved script files
    return bump_stage(libprojects.infer_stage(d, states), d)
