"""Parser of the clean-text page format (docs/design/2026-11-16-clean-text-format.md) and assembly of one
catalogue entry into body text plus an outline (headings, captions, meta, details).

A page uses its clean file when it exists, otherwise the PDF text layer (`text_source`: clean / mixed / layer)."""
from __future__ import annotations

import re

from . import extract, restored as restored_text

TAG = re.compile(r"^\[([A-Za-z][\w-]*)\]\s?(.*)$")
NON_BODY_TYPES = {"front", "contents", "notes", "credits", "index", "back", "blank"}
DETAIL_BOOKS = {"hodge_aid"}  # `##` headings of Hodge are the named details of the painting


def parse_page(text: str) -> dict:
    """-> {type, blocks:[{kind,text}], continues}. kinds: h1 h2 h3 meta caption credit note quote sic p"""
    lines = text.replace("\r", "").split("\n")
    ptype, blocks, continues = "body", [], False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        m = TAG.match(s)
        if m:
            tag, rest = m.group(1).lower(), m.group(2).strip()
            if tag == "page-type":
                ptype = rest.lower() or "body"
            elif tag == "continues":
                continues = True
            elif tag in ("meta", "caption", "credit", "note", "quote"):
                blocks.append({"kind": tag, "text": rest})
            else:
                blocks.append({"kind": "p", "text": s})
            continue
        h = re.match(r"^(#{1,3})\s+(.*)$", s)
        if h:
            blocks.append({"kind": f"h{len(h.group(1))}", "text": h.group(2).strip()})
        else:
            blocks.append({"kind": "p", "text": s})
    return {"type": ptype, "blocks": blocks, "continues": continues}


def layer_page(text: str) -> dict:
    t = extract.repair(text).strip()
    return {"type": "body", "blocks": [{"kind": "p", "text": t}] if t else [], "continues": False}


def entry(work: dict, restored: bool = False) -> dict:
    """Assemble the pages of one entry. Returns {body, words, text_source, outline, pages:[{page,source,type}]}.

    restored=True builds the text of a work at trust level `restored` (see restored.py) from the RESTORED pages and nothing else:
    every [[? ... ?]] passage becomes the mark […]; plate pages are left out; no caption is kept (the review found the captions still
    machine text, so outline["captions"] is empty); headings and the [meta] line stay; the words are the words that remain."""
    book_id = work["id"].split("/")[0]
    a, b = work["pdf_pages"]
    body_blocks, headings, captions, meta, pages, srcs = [], [], [], [], [], []
    prev_cont = False
    for p in range(a, b + 1):
        if restored:
            text, src = restored_text.mark_unclear(restored_text.page_text(book_id, p)), "restored"
        else:
            text, src = extract.page_text(book_id, p)
        pg = parse_page(text) if src in ("clean", "restored") else layer_page(text)
        srcs.append(src)
        pages.append({"page": p, "source": src, "type": pg["type"]})
        if pg["type"] in NON_BODY_TYPES or (restored and pg["type"] == "plate"):
            prev_cont = False
            continue
        first = True
        for blk in pg["blocks"]:
            k = blk["kind"]
            if k in ("h1", "h2", "h3"):
                headings.append({"level": int(k[1]), "text": blk["text"], "page": p})
                body_blocks.append(blk)
            elif k == "meta":
                meta.append(blk["text"])
            elif k == "caption":
                if not restored:
                    captions.append({"page": p, "text": blk["text"]})
            elif k in ("credit", "note", "sic"):
                pass
            else:  # p, quote
                if (first and prev_cont and k == "p" and body_blocks and body_blocks[-1]["kind"] == "p"):
                    body_blocks[-1] = {"kind": "p", "text": body_blocks[-1]["text"] + " " + blk["text"]}
                else:
                    body_blocks.append(blk)
            first = False
        prev_cont = pg["continues"]
    lines = []
    for blk in body_blocks:
        k = blk["kind"]
        lines.append({"h1": "# ", "h2": "## ", "h3": "### ", "quote": "> "}.get(k, "") + blk["text"])
    body = "\n\n".join(lines)
    count = restored_text.count_words if restored else (lambda t: len(t.split()))
    words = sum(count(blk["text"]) for blk in body_blocks if blk["kind"] in ("p", "quote"))
    kinds = set(srcs)
    source = next(iter(kinds)) if len(kinds) == 1 else "mixed"          # clean, layer or restored; any mix is "mixed"
    if source == "layer" and work.get("headings"):  # digital layer text has no markup: use font-size headings
        headings = [{"level": 2, "text": h, "page": None} for h in work["headings"]]
    outline = {"headings": headings, "captions": captions, "meta": meta}
    if book_id in DETAIL_BOOKS:
        outline["details"] = [h["text"] for h in headings if h["level"] == 2]
    return {"body": body, "words": words, "text_source": source, "outline": outline, "pages": pages,
            "ocr": book_id in ("hodge_aid", "hagen_wgps")}
