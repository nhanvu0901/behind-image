"""The export as one long job (design section 4 and 8): subtitles and description first (cheap, so a bad timing fails before
the render), then the render parts (heavy, resumable), the join, the mux, and the checks that publish the files.

    start(project_dir)  -> the long-job record      state(project_dir) -> {"state": none|running|stale|done, "detail": ...}
    plan_for(project_dir)  what will be made and how long it should take
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from bti.editor.common import compute_rev, file_signature, read_json, storyboard_approval
from bti.script import store

from . import check, describe, mux, plan, render, subtitles
from .errors import ExportError, part_error
from .settings import Settings, load_settings
from bti.fsio import atomic_replace

KIND = "export"
SCHEMA = "bti.export/1"
FILE_NAMES = ("video", "subtitles", "description", "chapters")


# ---------------------------------------------------------------------------------------------------------------- paths
def export_dir(project_dir: Path) -> Path:
    return Path(project_dir) / "export"


def cache_dir(project_dir: Path) -> Path:
    return Path(project_dir) / "cache" / "export"


def manifest_path(project_dir: Path) -> Path:
    return export_dir(project_dir) / "export.json"


def file_names(pid: str) -> dict:
    return {"video": pid + ".mp4", "subtitles": pid + ".srt", "description": "description.txt", "chapters": "chapters.txt"}


def read_manifest(project_dir: Path) -> dict | None:
    """The manifest, or None when there is none or it cannot be read (the export is then simply "not made")."""
    try:
        d = store.read_object(manifest_path(project_dir), "export")
    except store.DocumentCorrupt:
        return None
    return d if isinstance(d, dict) and d.get("schema") == SCHEMA else None


# --------------------------------------------------------------------------------------------------------------- inputs
@dataclass
class Inputs:
    storyboard: dict
    rev: str
    timing: dict
    audio: Path
    audio_sig: str
    project_meta: dict


def _inside(project_dir: Path, rel) -> Path | None:
    if not isinstance(rel, str) or not rel or os.path.isabs(rel) or "\\" in rel or ".." in rel.split("/"):
        return None
    p = (Path(project_dir) / rel)
    try:
        if not p.resolve().is_relative_to(Path(project_dir).resolve()):
            return None
    except OSError:
        return None
    return p


def load_inputs(project_dir: Path, *, need_approval: bool = True) -> Inputs:
    """The approved storyboard, the mix and the timing, or an ExportError that says which one is missing."""
    project_dir = Path(project_dir)
    try:
        sb = read_json(project_dir / "storyboard.json")
    except FileNotFoundError:
        raise ExportError("no_storyboard", "there is no storyboard yet", 409)
    except (OSError, ValueError):
        raise ExportError("storyboard_unreadable", "storyboard.json cannot be read", 409)
    if not isinstance(sb, dict):
        raise ExportError("storyboard_unreadable", "storyboard.json cannot be read", 409)
    ap = storyboard_approval(sb)
    if need_approval and ap != "fresh":
        raise ExportError("not_approved" if ap == "none" else "approval_stale",
                          "the storyboard is not approved" if ap == "none" else "the storyboard changed after it was approved", 409)
    audio = _inside(project_dir, sb.get("audio") or "audio/mix.m4a")
    if audio is None or not audio.is_file():
        raise ExportError("no_audio", "the audio mix is missing", 409)
    tpath = _inside(project_dir, sb.get("timing") or "timing.json")
    try:
        timing = read_json(tpath) if tpath is not None and tpath.is_file() else None
    except (OSError, ValueError):
        timing = None
    if not isinstance(timing, dict) or not isinstance(timing.get("words"), list) or not timing["words"]:
        raise ExportError("no_timing", "timing.json is missing or has no words", 409)
    try:
        meta = store.read_object(project_dir / "project.json", "project") or {}
    except store.DocumentCorrupt:
        meta = {}
    return Inputs(sb, compute_rev(sb), timing, audio, file_signature(audio), meta)


_TIMELINES: dict[tuple, tuple] = {}


def engine_timeline(project_dir: Path, rev: str) -> tuple[list[float], float]:
    """(shot start times, end of the video) from the engine, cached per storyboard revision."""
    key = (str(Path(project_dir).resolve()), rev)
    if key not in _TIMELINES:
        from bti.engine.api import open_project
        r = open_project(Path(project_dir)).resolve()
        while len(_TIMELINES) >= 8:
            _TIMELINES.pop(next(iter(_TIMELINES)))
        _TIMELINES[key] = ([float(s["_t0"]) for s in r["shots"]], float(r["end"]["_t"]))
    return _TIMELINES[key]


def get_manager():
    from bti.longjob import manager
    return manager


def _active(manager, pid: str):
    try:
        a = manager.active(pid, kind=KIND)
    except TypeError:
        a = manager.active(pid, KIND)
    if isinstance(a, (list, tuple)):
        a = a[0] if a else None
    return a or None


# ------------------------------------------------------------------------------------------------------------------ plan
def plan_for(project_dir: Path, settings: Settings | None = None, timeline=None, inputs: Inputs | None = None) -> dict:
    """What will be made: length, parts (and how many already exist), estimate in seconds, assets used, flagged assets."""
    settings = settings or load_settings()
    inp = inputs or load_inputs(project_dir)
    starts, end = (timeline or engine_timeline)(project_dir, inp.rev)
    parts = plan.plan_parts(starts, end, settings.fps, settings.part_seconds)
    pdir = cache_dir(project_dir) / "parts"
    have = [p for p in parts if (pdir / plan.part_filename(p, plan.part_key(inp.rev, p, settings.width))).is_file()]
    todo = sum(p.seconds for p in parts if p not in have)
    assets = inp.storyboard.get("assets") or {}
    used = describe.used_assets(inp.storyboard)
    return {"duration": round(end, 3), "frames": plan.total_frames(end, settings.fps), "parts": len(parts), "parts_done": len(have),
            "part_seconds": [round(p.seconds, 1) for p in parts], "estimate_seconds": plan.estimate_seconds(todo, settings.render_speed),
            "assets_used": len(used), "flagged": [k for k in used if isinstance(assets[k].get("credit"), dict) and assets[k]["credit"].get("flag") in describe.FLAGS],
            "storyboard_rev": inp.rev}


# ----------------------------------------------------------------------------------------------------------------- state
def state(project_dir, manager=None) -> dict:
    """Cheap: reads the manifest, the storyboard and the audio's signature; no ffprobe, no engine."""
    project_dir = Path(project_dir)
    pid = project_dir.name
    try:
        mgr = manager or get_manager()
        if _active(mgr, pid):
            return {"state": "running", "detail": "Đang xuất video."}
    except Exception:   # noqa: BLE001 - the long-job runner may not exist yet; the state is then computed from the files
        pass
    m = read_manifest(project_dir)
    if m is None:
        return {"state": "none", "detail": "Chưa xuất video."}
    reason = stale_reason(project_dir, m)
    if reason:
        return {"state": "stale", "detail": {"storyboard": "Cần xuất lại: storyboard đã đổi sau lần xuất trước.",
                                             "audio": "Cần xuất lại: giọng đọc đã đổi sau lần xuất trước.",
                                             "files": "Cần xuất lại: tệp đã xuất không còn đủ."}[reason], "reason": reason}
    return {"state": "done", "detail": "Đã xuất video."}


def stale_reason(project_dir: Path, m: dict) -> str | None:
    """None when the manifest still describes the project: `storyboard` (another revision), `audio` (another file) or `files`."""
    project_dir = Path(project_dir)
    names = m.get("files") if isinstance(m.get("files"), dict) else {}
    if not all(isinstance(names.get(k), str) and (export_dir(project_dir) / names[k]).is_file() for k in FILE_NAMES):
        return "files"
    try:
        sb = read_json(project_dir / "storyboard.json")
    except (OSError, ValueError):
        return "storyboard"
    if not isinstance(sb, dict) or compute_rev(sb) != m.get("storyboard_rev"):
        return "storyboard"
    audio = _inside(project_dir, sb.get("audio") or "audio/mix.m4a")
    try:
        if audio is None or file_signature(audio) != m.get("audio_sig"):
            return "audio"
    except OSError:
        return "audio"
    return None


# ------------------------------------------------------------------------------------------------------------------ start
def start(project_dir: Path, *, manager=None, tools: render.Tools | None = None, settings: Settings | None = None,
          timeline=None, part_cls=None) -> dict:
    """Checks the inputs, plans the parts and starts the long job. Raises ExportError (409) when the project is not ready or
    already exporting. Starting again after a stop or a restart is the resume: parts with a current file are not redone."""
    project_dir = Path(project_dir)
    pid = project_dir.name
    settings = settings or load_settings()
    tools = tools or render.Tools.from_settings(settings)
    inp = load_inputs(project_dir)
    starts, end = (timeline or engine_timeline)(project_dir, inp.rev)
    specs = plan.plan_parts(starts, end, settings.fps, settings.part_seconds)
    job_parts = build_parts(project_dir, inp, specs, end, tools, settings, part_cls)
    mgr = manager or get_manager()
    try:
        return mgr.start(kind=KIND, pid=pid, project_dir=project_dir, parts=job_parts,
                         meta={"storyboard_rev": inp.rev, "duration": end, "parts": len(specs)})
    except Exception as e:   # noqa: BLE001
        if type(e).__name__ == "Busy":
            raise ExportError("busy", "this project is already being exported", 409)
        raise


def _part_cls(part_cls):
    if part_cls is not None:
        return part_cls
    from bti.longjob import Part
    return Part


def build_parts(project_dir: Path, inp: Inputs, specs, end: float, tools: render.Tools, settings: Settings, part_cls=None) -> list:
    """The parts of the job. They share `st`, a dict of what the earlier parts made."""
    Part = _part_cls(part_cls)
    pid = Path(project_dir).name
    cdir, pdir = cache_dir(project_dir), cache_dir(project_dir) / "parts"
    names = file_names(pid)
    frames = plan.total_frames(end, settings.fps)
    st: dict = {"rendered": [], "t0": time.time()}
    n = len(specs)

    def prepare(ctx):
        ctx.progress(0.1)
        cues = subtitles.cues_from_timing(inp.timing)
        if not cues:
            raise ExportError("no_subtitles", "no subtitle cue could be made from the timing", 409)
        st["cues"] = cues
        st["srt"] = subtitles.to_srt(cues)
        st["problems"] = subtitles.check_cues(cues)
        d = describe.build_description(inp.storyboard, inp.timing, inp.project_meta, duration=end, titles=describe.library_titles())
        st["desc"] = d
        st["marks"] = mux.chapter_marks(inp.timing.get("chapters"), end)      # the marks inside the file stay as they are
        st["merged"] = d["merged_chapters"]
        ctx.log("%d subtitle cues, %d chapters, %d credit lines" % (len(cues), len(st["marks"]), len(d["credits"])))
        ctx.progress(1.0)
        return {"cues": len(cues), "cue_problems": len(st["problems"])}

    def make_render(spec):
        def run(ctx):
            if ctx.cancelled():
                return None
            key = plan.part_key(inp.rev, spec, settings.width)
            r = render.render_part(ctx, tools, settings, project_dir, spec, key, pdir)
            if r.get("cancelled"):
                return None
            st["rendered"].append({"index": spec.index + 1, "f0": spec.f0, "f1": spec.f1, "key": key, "file": r["file"], "skipped": r["skipped"]})
            return r
        return run

    def join(ctx):
        if ctx.cancelled():
            return None
        files = [pdir / plan.part_filename(s, plan.part_key(inp.rev, s, settings.width)) for s in specs]
        for f in files:
            if not f.is_file():
                raise ExportError("part_missing", "a render part is missing: " + f.name, 500)
        out = cdir / "video_all.mp4"
        r = render.join_parts(ctx, tools, files, out, frames, cdir)
        if r.get("cancelled"):
            return None
        keep = {f.name for f in files}
        for old in pdir.glob("part_*.mp4"):
            if old.name not in keep and ".partial" not in old.name:
                old.unlink(missing_ok=True)
        st["video"] = out
        return r

    def do_mux(ctx):
        if ctx.cancelled():
            return None
        video = st["video"]
        store.write_text_atomic(cdir / "subtitles.srt", st["srt"], 2)
        store.write_text_atomic(cdir / "chapters.ffmeta", mux.ffmetadata(st["marks"], str(inp.storyboard.get("title") or "")), 2)
        try:
            ainfo = check.probe(tools.ffprobe, inp.audio)
            codec = (ainfo.get("audio") or {}).get("codec")
            st["audio_duration"] = ainfo.get("duration")
        except check.ToolError:
            codec = None
        tmp = cdir / "final.partial.mp4"
        tmp.unlink(missing_ok=True)
        cmd = mux.mux_command(tools.ffmpeg, video, inp.audio, cdir / "subtitles.srt", cdir / "chapters.ffmeta", tmp, end,
                              audio_copy=(codec == "aac"), language=settings.language)
        tail: list[str] = []
        rc = ctx.run_process(cmd, cwd=str(cdir), env=tools.env, on_line=lambda ln: tail.append(ln.strip()[:200]) if ln.strip() else None)
        if ctx.cancelled():
            tmp.unlink(missing_ok=True)
            return None
        if rc != 0:
            tmp.unlink(missing_ok=True)
            raise ExportError("mux_failed", "the final mux failed: " + " | ".join(tail[-3:])[-250:], 500)
        st["final"] = tmp
        ctx.progress(1.0)
        return {"file": tmp.name}

    def finish(ctx):
        if ctx.cancelled():
            return None
        final = st["final"]
        info = check.probe(tools.ffprobe, final)
        ctx.progress(0.3, "Đo độ lớn tiếng")
        try:
            loud = check.measure_loudness(tools.ffmpeg, final)
        except check.ToolError as e:
            ctx.log("loudness not measured: %s" % e)
            loud = None
        card = check.report_card(info, loud, expected_frames=frames, expected_duration=end, cues=len(st["cues"]), fps=settings.fps,
                                  audio_duration=st.get("audio_duration"), merged_chapters=st.get("merged", 0))
        ctx.progress(0.7, "Lưu tệp")
        d = st["desc"]
        manifest = {"schema": SCHEMA, "pid": pid, "slug": pid, "storyboard_rev": inp.rev, "audio_sig": inp.audio_sig,
                    "audio_file": inp.storyboard.get("audio") or "audio/mix.m4a", "duration": round(end, 3), "frames": frames, "fps": settings.fps,
                    "width": settings.width, "cues": len(st["cues"]), "cue_problems": st["problems"], "chapters": len(st["marks"]), "chapters_merged": st.get("merged", 0),
                    "parts": st["rendered"], "files": names, "report": card, "report_status": check.worst(card), "loudness": loud,
                    "credits": d["credits"], "notes": d["notes"], "created": store.now_iso(), "seconds": round(time.time() - st["t0"], 1)}
        edir = export_dir(project_dir)
        with store.script_lock(project_dir):
            if not Path(project_dir).is_dir():
                raise ExportError("project_gone", "the project was removed", 404)
            store.make_parent(edir / "x", 1)
            manifest_path(project_dir).unlink(missing_ok=True)        # while the files change the export is "not made", never half
            atomic_replace(final, edir / names["video"])
            store.write_text_atomic(edir / names["subtitles"], st["srt"], 1)
            store.write_text_atomic(edir / names["description"], d["description"], 1)
            store.write_text_atomic(edir / names["chapters"], d["chapters"], 1)
            store.write_json_atomic(manifest_path(project_dir), manifest, 1)
        ctx.progress(1.0)
        return {"report_status": manifest["report_status"], "frames": frames, "duration": manifest["duration"]}

    def guard(fn):
        def wrapped(ctx):
            try:
                return fn(ctx)
            except ExportError as e:
                raise part_error(e) from e
        return wrapped

    def render_done(spec):
        def is_done(ctx):             # asked before the heavy slot is taken: a current file means no waiting for the machine
            f = pdir / plan.part_filename(spec, plan.part_key(inp.rev, spec, settings.width))
            return f.is_file() and f.stat().st_size > 0
        return is_done

    est = lambda s: max(1, int(plan.estimate_seconds(s.seconds, settings.render_speed)))   # noqa: E731
    parts = [Part(key="prepare", title="Làm phụ đề và mô tả", run=guard(prepare), heavy=False, est_seconds=5)]
    parts += [Part(key="render-%d" % (s.index + 1), title="Dựng đoạn %d/%d" % (s.index + 1, n), run=guard(make_render(s)), heavy=True, est_seconds=est(s), is_done=render_done(s)) for s in specs]
    parts += [Part(key="join", title="Ghép các đoạn", run=guard(join), heavy=False, est_seconds=30),
              Part(key="mux", title="Ghép tiếng, phụ đề và mục lục", run=guard(do_mux), heavy=False, est_seconds=60),
              Part(key="finish", title="Kiểm tra và lưu tệp", run=guard(finish), heavy=False, est_seconds=60)]
    return parts
