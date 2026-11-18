"""python -m tools.clean_text.restore --book grovier_nws [--work N[,M|A-B]] [--model ID] [--out DIR] [--force] [--dry-run]

Exit codes: 0 every selected work is restored (or was already), 1 at least one work failed its checks, 2 bad arguments or
setup, 3 real models are switched off (BTI_NO_REAL_MODELS=1) and the model is a real one."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .run import dry_check_saved, load_report, RestoreError, Settings, build_prompt, page_ids, read_page, restore_book, PROMPT_PATH, resolve_model
from .pages import page_type

REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_works(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m tools.clean_text.restore", description=__doc__.split("\n\n")[0])
    ap.add_argument("--book", required=True, help="book id, for example grovier_nws")
    ap.add_argument("--work", help="work number(s): 5, 5,7 or 5-9 (default: every work of the book)")
    ap.add_argument("--model", help="model id (default: the model of the role library.restore)")
    ap.add_argument("--out", help="folder that receives the pages and report.json (default: library/restored/<book>)")
    ap.add_argument("--clean-dir", help="folder of the cleaned pages (default: library/clean_text/<book>)")
    ap.add_argument("--force", action="store_true", help="restore works again even when they are already done from the same input")
    ap.add_argument("--dry-run", action="store_true", help="list the works, pages and prompt sizes; call no model, write nothing")
    ap.add_argument("--print-prompt", action="store_true", help="with --dry-run: print the full prompt of the first selected work")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        only = parse_works(args.work)
    except ValueError:
        print("--work must look like 5, 5,7 or 5-9", file=sys.stderr)
        return 2
    try:
        from bti.settings import model_for
        model_id = args.model or model_for("library.restore")
        spec = resolve_model(model_id)               # refuses a real model while BTI_NO_REAL_MODELS=1, before anything is read
        from bti.library import catalogue
        works = catalogue.load_works(args.book)
        if not works:
            raise RestoreError("no_works", f"no works for book {args.book!r} (library/books/{args.book}/works.json is missing or empty)")
        books = {b["id"]: b for b in catalogue.load_books()}
        title = (books.get(args.book) or {}).get("title") or args.book
        clean_dir = Path(args.clean_dir) if args.clean_dir else REPO_ROOT / "library" / "clean_text" / args.book
        out_dir = Path(args.out) if args.out else REPO_ROOT / "library" / "restored" / args.book
        if not clean_dir.is_dir():
            raise RestoreError("no_clean_text", f"{clean_dir} does not exist")
        st = Settings(book_id=args.book, book_title=title, works=works, clean_dir=clean_dir, out_dir=out_dir,
                      model_id=model_id, force=args.force, only=only, log=lambda s: print(s, flush=True))
        if args.dry_run:
            return dry_run(st, args.print_prompt)
        print(f"model {model_id}; {len(works)} works in the book; output {out_dir}", flush=True)
        res = restore_book(st)
    except RestoreError as e:
        print(f"{e.code}: {e.message}", file=sys.stderr)
        return 3 if e.code == "real_models_off" else 2
    print(f"done: {len(res['ok'])} restored, {len(res['skipped'])} already done, {len(res['failed'])} failed; report {res['report']}")
    if res["failed"]:
        print("failed works: " + ", ".join(map(str, res["failed"])) + " (see the report; run again to retry them)")
        return 1
    return 0


def dry_run(st: Settings, show: bool) -> int:
    from . import checks
    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt_lines = checks.prompt_lines_of(template + "\nYOUR PREVIOUS ANSWER WAS REJECTED.")
    try:
        rep = load_report(st)                       # read-only: nothing is written
    except RestoreError:
        rep = {"works": {}}
    first = True
    for w in st.works:
        if st.only is not None and w["n"] not in st.only:
            continue
        pages = {}
        for p in page_ids(w):
            t = read_page(st.clean_dir, p)
            if t is not None and page_type(t) == "body":
                pages[f"page_{p:04d}"] = t
        prompt = build_prompt(template, st, w, pages)
        print(f"work {w['n']:>2}  pages {w['pdf_pages'][0]}-{w['pdf_pages'][1]}  body pages {len(pages)}  "
              f"input {sum(len(t) for t in pages.values())} chars  prompt {len(prompt)} chars  {w.get('title')}")
        saved = dry_check_saved(st, w, template, prompt_lines, rep)
        if saved:
            print("  " + saved)
        if show and first:
            print("-" * 70 + "\n" + prompt + "\n" + "-" * 70)
        first = False
    return 0


if __name__ == "__main__":
    sys.exit(main())
