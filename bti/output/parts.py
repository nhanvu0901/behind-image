"""The writers of the parts of an output folder. Each takes the facts and the folder, writes the files of ONE part (atomically, nothing half-written) and returns
`{"rev": ..., "files": [relative paths, "/" separated], ...}`; a part that cannot be written raises, and `publish.py` turns that into a warning and goes on with the others.

    sources  outline  narration  voice  pictures  storyboard  export          (the documents are those of `facts.Facts`)

The revision of a part is the revision of the document it was made from (the one the approval names), so "did the document change after it was published" is one comparison."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable

from . import fsutil, render, shotwords, times, words
from .paths import FINAL_VIDEO, PARTS

log = logging.getLogger("bti.output")
PICTURE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".mov", ".m4v")


def rel(folder: Path, path: Path) -> str:
    return Path(path).relative_to(folder).as_posix()


def sha(*parts: Any) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------ the registry (names of techniques)
_REGISTRY: dict[str, dict] = {}


def registry(style: str = "gae") -> dict[str, dict]:
    """{technique id: entry} of the style (with its patches, like the page); the plain file when the engine's loader is not there."""
    if style in _REGISTRY:
        return _REGISTRY[style]
    techs: list = []
    try:
        from bti.engine import registry as R
        techs = list(R.load_bundle(style).techniques)
    except Exception:       # noqa: BLE001
        try:
            techs = json.loads((Path(__file__).resolve().parents[2] / "style" / style / "techniques.json").read_text(encoding="utf-8")).get("techniques") or []
        except (OSError, ValueError):
            techs = []
    _REGISTRY[style] = {t.get("id"): t for t in techs if isinstance(t, dict)}
    return _REGISTRY[style]


def label_of_factory(style: str = "gae") -> Callable[[str], str | None]:
    reg = registry(style)

    def label_of(tid: str) -> str | None:
        t = reg.get(tid)
        v = (t or {}).get("label_vi")
        return str(v) if v else None
    return label_of


def dossier_details(pdir: Path) -> dict[str, str]:
    try:
        from bti.picks import context
        return {d["id"]: d["label"] for d in context.details(Path(pdir))}
    except Exception:       # noqa: BLE001
        return {}


def action_label(aid: str) -> str:
    try:
        from bti.editor import state_api
        s = state_api.SPEC.get(aid)
        return s.label if s else aid
    except Exception:       # noqa: BLE001
        return aid


# ------------------------------------------------------------------------------------------------ 1_sources
def write_sources(f, folder: Path) -> dict:
    d = folder / PARTS["sources"]
    src = f.pdir / "source"
    files: list[str] = []
    texts: list[dict] = []
    shas: list[str] = []
    names: set[str] = set()
    if src.is_dir():
        for p in sorted(src.iterdir()):
            if not p.is_file() or p.name.startswith(".") or p.suffix.lower() not in (".txt", ".json"):
                continue
            fsutil.put_file(p, d / p.name, link=False)
            names.add(p.name)
            files.append(rel(folder, d / p.name))
            shas.append(p.name + ":" + (sha_of(p) or ""))
            if p.suffix.lower() == ".txt":
                try:
                    texts.append({"name": p.name, "words": words.count_words(p.read_text(encoding="utf-8", errors="replace"))})
                except OSError:
                    pass
    from bti.export import describe
    books = describe.library_titles()
    fsutil.write_text(d / "sources.md", render.sources_md(f, books, texts))
    names.add("sources.md")
    files.append(rel(folder, d / "sources.md"))
    fsutil.keep_only(d, names)
    return {"rev": sha(json.dumps(f.meta.get("sources"), sort_keys=True, ensure_ascii=False), *shas), "files": files}


def sha_of(path: Path) -> str | None:
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


# ------------------------------------------------------------------------------------------------ 2_script
def write_outline(f, folder: Path) -> dict:
    d = folder / PARTS["script"]
    fsutil.write_text(d / "outline.md", render.outline_md(f, dossier_details(f.pdir)))
    fsutil.put_file(f.pdir / "script" / "outline.json", d / "outline.json", link=False)
    return {"rev": f.outline_rev, "files": [rel(folder, d / "outline.md"), rel(folder, d / "outline.json")],
            "counts": {"chapters": len(f.outline.chapters), "facts": len(f.outline.facts)}}


def write_narration(f, folder: Path) -> dict:
    d = folder / PARTS["script"]
    fsutil.write_text(d / "narration.md", render.narration_md(f, dossier_details(f.pdir)))
    fsutil.put_file(f.pdir / "script" / "narration.json", d / "narration.json", link=False)
    n = f.narration
    return {"rev": f.narration_rev, "files": [rel(folder, d / "narration.md"), rel(folder, d / "narration.json")],
            "counts": {"chapters": len(n.chapters), "lines": sum(len(c.beats) for c in n.chapters),
                       "words": sum(words.count_words(b.text) for c in n.chapters for b in c.beats)}}


# ------------------------------------------------------------------------------------------------ 3_voice
def voice_rev(f) -> str | None:
    from .facts import sig_file
    if f.timing is None:
        return None
    return sha(f.timing_sha, sig_file(f.pdir / "audio" / "mix.m4a"), sig_file(f.pdir / "audio" / "voice.wav"))


def write_voice(f, folder: Path) -> dict:
    d = folder / PARTS["voice"]
    files = []
    for srcname, dst in (("audio/voice.wav", "narration.wav"), ("audio/mix.m4a", "mix.m4a")):
        p = f.pdir / srcname
        if p.is_file():
            fsutil.put_file(p, d / dst, link=True)
            files.append(rel(folder, d / dst))
    fsutil.put_file(f.pdir / "timing.json", d / "timing.json", link=False)
    files.append(rel(folder, d / "timing.json"))
    vm = f.voice_manifest or {}
    return {"rev": voice_rev(f), "files": files, "duration": vm.get("duration") or (f.timing or {}).get("duration"),
            "words": len((f.timing or {}).get("words") or [])}


# ------------------------------------------------------------------------------------------------ 4_pictures
def on_screen(f, basis_storyboard: bool) -> tuple[list[str], str]:
    """(keys of the pictures on screen, basis): with an approved storyboard the pictures its shots use; before that the main painting and the pictures the picks give to lines."""
    picks = f.picks or {}
    assets = dict(picks.get("assets") or {})
    if basis_storyboard and f.sb:
        from bti.export import describe
        keys = describe.used_assets(f.sb)
        sb_assets = f.sb.get("assets") or {}
        main = picks.get("main_asset")
        if main and main in sb_assets and main not in keys:
            keys = [main] + keys
        return [k for k in keys if k in sb_assets or k in assets], "storyboard"
    keys: list[str] = []
    main = picks.get("main_asset")
    if main in assets:
        keys.append(main)
    for b in (picks.get("beats") or {}).values():
        for it in b.get("items") or []:
            if it.get("asset") in assets and it["asset"] not in keys:
                keys.append(it["asset"])
    return keys, "picks"


def write_pictures(f, folder: Path, *, basis_storyboard: bool = False) -> dict:
    d = folder / PARTS["pictures"]
    picks = f.picks or {}
    sb_assets = (f.sb or {}).get("assets") or {}
    use_sb = basis_storyboard and bool(f.sb)
    assets = {**(picks.get("assets") or {}), **({k: v for k, v in sb_assets.items()} if use_sb else {})}
    keys, basis = on_screen(f, use_sb)
    main = picks.get("main_asset")
    files: list[str] = []
    names: set[str] = set()
    missing: list[str] = []
    for k in keys:
        a = assets.get(k) or {}
        src = f.pdir / str(a.get("file") or "")
        if not a.get("file") or not src.is_file():
            missing.append(k)
            continue
        name = ("main" if k == main else k) + src.suffix.lower()
        fsutil.put_file(src, d / name, link=True)
        names.add(name)
        files.append(rel(folder, d / name))
    fsutil.keep_only(d, names | {"picks.json", "regions.jpg", "credits.txt"}, suffixes=PICTURE_SUFFIXES)
    fsutil.put_file(f.pdir / "picks.json", d / "picks.json", link=False)
    files.append(rel(folder, d / "picks.json"))
    from bti.export import describe
    fsutil.write_text(d / "credits.txt", render.credits_txt(assets, keys, describe.credit_line, describe.flag_note))
    files.append(rel(folder, d / "credits.txt"))
    regions_n = 0
    main_asset = assets.get(main) if main else None
    if main_asset and main not in missing:
        regions = (sb_assets.get(main) or {}).get("regions") if use_sb and (sb_assets.get(main) or {}).get("regions") else main_asset.get("regions")
        if regions:
            from . import sheets
            regions_n = sheets.regions_sheet(f.pdir / str(main_asset["file"]), regions, d / "regions.jpg", f.title or f.pid)
            files.append(rel(folder, d / "regions.jpg"))
        else:
            fsutil.remove(d / "regions.jpg")
    out = {"rev": f.picks_rev, "files": files, "basis": basis, "count": len(names), "regions": regions_n, "unused_left_out": max(0, len(assets) - len(keys))}
    if missing:
        out["missing"] = missing
    return out


# ------------------------------------------------------------------------------------------------ 5_storyboard
def shot_rows(f) -> list[dict]:
    sb = f.sb or {}
    shots = [s for s in (sb.get("shots") or []) if isinstance(s, dict)]
    assets = sb.get("assets") or {}
    main = shotwords.main_asset_key(sb, f.title)
    env = shotwords.env_of(lambda tid: registry(str(sb.get("style") or "gae")).get(tid), assets, main)
    tm = times.shot_times(f.pdir, sb, f.timing)
    tw = (f.timing or {}).get("words") if isinstance((f.timing or {}).get("words"), list) else []
    rows = []
    for i, (s, (t0, t1)) in enumerate(zip(shots, tm), 1):
        spoken = ""
        if t0 is not None and t1 is not None and tw:
            ws = [w.get("w") for w in tw if isinstance(w, dict) and isinstance(w.get("s"), (int, float)) and t0 - 1e-6 <= w["s"] < t1 - 1e-6 and w.get("w")]
            spoken = " ".join(str(w) for w in ws[:12]) + (" …" if len(ws) > 12 else "")
        rows.append({"n": i, "id": str(s.get("id") or ""), "t0": t0, "t1": t1, "sentence": shotwords.shot_sentence(s, env), "spoken": spoken, "locked": bool(s.get("locked"))})
    return rows


def chapter_spans(f) -> list[dict]:
    names = {c.id: c.title for c in f.narration.chapters} if f.narration is not None else {}
    out = []
    for c in (f.timing or {}).get("chapters") or []:
        if isinstance(c, dict) and isinstance(c.get("start"), (int, float)) and isinstance(c.get("end"), (int, float)):
            out.append({"id": c.get("id"), "title": names.get(c.get("id")) or str(c.get("name") or c.get("id") or "").title(), "t0": float(c["start"]), "t1": float(c["end"])})
    return out


def write_storyboard(f, folder: Path) -> dict:
    d = folder / PARTS["storyboard"]
    rows = shot_rows(f)
    fsutil.write_text(d / "shots.md", render.shots_md(f, rows, chapter_spans(f)))
    fsutil.put_file(f.pdir / "storyboard.json", d / "storyboard.json", link=False)
    return {"rev": f.sb_rev, "files": [rel(folder, d / "shots.md"), rel(folder, d / "storyboard.json")], "counts": {"shots": len(rows)}}


# ------------------------------------------------------------------------------------------------ the video, 6_export and the contact sheets
def export_rev(f) -> str | None:
    m = f.export_manifest
    return sha(m.get("storyboard_rev"), m.get("audio_sig"), m.get("created")) if m else None


def video_facts(m: dict, size_bytes: int | None) -> dict:
    width = int(m.get("width") or 1920)
    return {"file": FINAL_VIDEO, "seconds": m.get("duration"), "size_bytes": size_bytes, "width": width, "height": int(round(width * 9 / 16)), "fps": m.get("fps"),
            "frames": m.get("frames"), "chapters": m.get("chapters"), "loudness": m.get("loudness"), "report_status": m.get("report_status"),
            "checks": [{"key": c.get("key"), "status": c.get("status"), "value": c.get("value"), "expected": c.get("expected"), "note": c.get("note")}
                       for c in (m.get("report") or []) if isinstance(c, dict)], "created": m.get("created"), "render_seconds": m.get("seconds")}


def write_export(f, folder: Path) -> dict:
    m = f.export_manifest or {}
    names = m.get("files") if isinstance(m.get("files"), dict) else {}
    edir = f.pdir / "export"
    video = edir / str(names.get("video") or (f.pid + ".mp4"))
    if not video.is_file():
        raise FileNotFoundError("the exported video is not there: " + video.name)
    fsutil.put_file(video, folder / FINAL_VIDEO, link=True)
    d = folder / PARTS["export"]
    files = [FINAL_VIDEO]
    for key in ("description", "chapters"):
        p = edir / str(names.get(key) or (key + ".txt"))
        if p.is_file():
            fsutil.put_file(p, d / (key + ".txt"), link=False)
            files.append(rel(folder, d / (key + ".txt")))
    report = {k: m.get(k) for k in ("schema", "pid", "storyboard_rev", "duration", "frames", "fps", "width", "chapters", "chapters_merged", "report_status", "report", "loudness",
                                    "credits", "notes", "created", "seconds")}
    fsutil.write_json(d / "report.json", report)
    files.append(rel(folder, d / "report.json"))
    try:
        size = (folder / FINAL_VIDEO).stat().st_size
    except OSError:
        size = None
    return {"rev": export_rev(f), "files": files, "video": video_facts(m, size)}


def write_contact_sheets(f, folder: Path, ffmpeg: list[str], env: dict | None = None, progress=None) -> list[str]:
    """One labelled frame per shot of the finished video, in `5_storyboard/`. The times are those of the storyboard that was exported."""
    from . import sheets
    rows = shot_rows(f)
    total = float((f.export_manifest or {}).get("duration") or 0) or max([r["t1"] for r in rows if r.get("t1") is not None] or [0])
    items = []
    for r in rows:
        if r["t0"] is None:
            continue
        t1 = r["t1"] if r["t1"] is not None else total
        t = r["t0"] + 0.4 * max(0.0, t1 - r["t0"])
        if total:
            t = min(t, max(0.0, total - 0.1))
        items.append({"n": r["n"], "t": t, "label": sheets.label_for(r["n"], r["t0"], r["sentence"])})
    d = folder / PARTS["storyboard"]
    names = sheets.contact_sheets(folder / FINAL_VIDEO, items, d, ffmpeg, title=f.title or f.pid, env=env, progress=progress, tmp_root=folder)
    return [rel(folder, d / n) for n in names]
