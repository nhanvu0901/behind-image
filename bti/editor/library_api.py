"""HTTP API of the book library (front door of the pipeline). Mounted from app.py.

Local, private research tool: reads books/ and library/, writes only projects/<slug>/ and library/cache/.
No endpoint exports or publishes book pages beyond rendering them for the local page."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Body, Query
from fastapi.responses import FileResponse

from bti.library import catalogue, config as libcfg, extract
from bti.library import projects as libprojects

from .common import ApiError, read_json, valid_pid

CENTURY_MAX = 21


def _book(book_id: str) -> dict:
    if not libcfg.BOOK_ID_RE.fullmatch(book_id) or book_id not in libcfg.BOOK_BY_ID:
        raise ApiError(404, "book not found")
    f = libcfg.book_dir(book_id) / "book.json"
    if not f.is_file():
        raise ApiError(404, "book not catalogued; run python -m bti.library build")
    return catalogue.read_json(f)


def _work(book_id: str, n: int) -> dict:
    _book(book_id)
    w = catalogue.load_work(book_id, n)
    if w is None:
        raise ApiError(404, "work not found")
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
            try:
                p = read_json(f)
            except Exception:
                continue
            for s in p.get("sources") or []:
                idx.setdefault(s.get("work_id"), []).append(
                    {"id": d.name, "stage": libprojects.infer_stage(d),
                     "has_storyboard": (d / "storyboard.json").is_file()})
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
        return {**{k: w.get(k) for k in ("id", "n", "title", "artist", "year", "headline", "pdf_pages", "words",
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
            raise ApiError(404, "page is not part of this entry")
        return _jpeg(book_id, pdf_page, w)

    @r.get("/works/{book_id}/{n}/image/{xref}.jpg")
    def work_image(book_id: str, n: int, xref: int, w: int = Query(700)):
        wk = _work(book_id, n)
        a, b = wk["pdf_pages"]
        if xref not in {im["xref"] for im in extract.images(book_id, a, b)}:
            raise ApiError(404, "image is not part of this entry")
        if not 64 <= w <= 2400:
            raise ApiError(422, "w must be between 64 and 2400")
        try:
            return FileResponse(extract.render_image(book_id, xref, w), media_type="image/jpeg",
                                headers={"Cache-Control": "private, max-age=86400"})
        except Exception:
            raise ApiError(415, "cannot extract this image")

    @r.get("/artworks/{artwork_key}")
    def artwork(artwork_key: str):
        a = catalogue.load_artworks().get(artwork_key)
        if a is None:
            raise ApiError(404, "artwork not found")
        arts, pidx = catalogue.load_artworks(), project_index()
        ws = []
        for wid in a["works"]:
            bid, n = wid.split("/")
            w = catalogue.load_work(bid, int(n))
            if w:
                ws.append(row(w, arts, pidx))
        return {"artwork_key": artwork_key, **a, "works_detail": ws}

    @r.post("/projects")
    def create(body: dict = Body(...)):
        wids = body.get("work_ids")
        slug = body.get("slug") or None
        if slug is not None and not isinstance(slug, str):
            raise ApiError(422, "slug must be a string")
        try:
            return libprojects.create_project(wids, slug, projects_root)
        except libprojects.ProjectError as e:
            raise ApiError(e.status, str(e))
        except FileNotFoundError as e:
            raise ApiError(404, str(e))

    return r


def _jpeg(book_id: str, pdf_page: int, w: int):
    if not 64 <= w <= 2400:
        raise ApiError(422, "w must be between 64 and 2400")
    try:
        f = extract.render_page(book_id, pdf_page, w)
    except IndexError:
        raise ApiError(404, "page not found")
    except FileNotFoundError:
        raise ApiError(404, "book PDF is missing")
    return FileResponse(f, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


def stage_of(d: Path) -> str:
    return libprojects.infer_stage(d)
