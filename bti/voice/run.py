"""The voice run as a long job (`bti.longjob`): synthesis parts (heavy), assembly (light), alignment (heavy when the real
aligner is used), then timing.json and the manifest.

Resume = start the same job again: every part decides for itself (`is_done` for heavy ones) whether its output is current."""
from __future__ import annotations

import time
from pathlib import Path

from bti.script import store

from . import align as align_mod
from . import files, planner
from .assemble import assemble
from .config import aligner_config, load_server_config, load_voice_config
from .errors import VoiceError
from .plan import Plan, make_plan
from .providers import resolve
from .timingfile import build_timing

VI = {   # what the owner reads when a part fails (the page may translate by code as well)
    "voice_chunks_failed": "Có câu máy chưa đọc được. Bấm đọc lại để thử tiếp.",
    "voice_chunks_missing": "Lời dẫn đã đổi trong lúc đọc. Hãy chạy lại để đọc phần mới.",
    "voice_worker_failed": "Máy đọc giọng bị dừng giữa chừng. Chạy lại để đọc tiếp, các câu đã đọc được giữ lại.",
    "voice_assemble_failed": "Không ghép được tệp âm thanh (ffmpeg lỗi).",
    "voice_align_failed": "Không đo được thời điểm từng từ.",
    "voice_not_configured": "Máy này chưa cài giọng đọc.",
}


def _partfail(e: VoiceError):
    from bti.longjob import PartError
    return PartError(e.code, VI.get(e.code, "Bước giọng đọc thất bại."))


def _guard(fn):
    def run(ctx):
        try:
            return fn(ctx)
        except VoiceError as e:
            if e.code == "cancelled":
                return None
            raise _partfail(e)
    return run


def reseed(pdir: Path, plan: Plan, ids: list[str]) -> list[str]:
    """Give the sentences with these chunk ids another seed (kept in the manifest, keyed by the text hash). Returns the ids that
    were changed."""
    from .chunks import next_seed
    by = plan.by_id()
    ths = {by[i].th: by[i].seed for i in ids if i in by}
    if not ths:
        return []

    def go(doc):
        seeds = doc.setdefault("seeds", {})
        for th, seed in ths.items():
            seeds[th] = next_seed(seed)
    files.update_manifest(pdir, go)
    return list(ths)


def make_parts(pdir: Path, pid: str, plan: Plan, *, provider, aligner, force_ids: set[str] | None, since: float,
               cfg: dict, worker: dict | None = None) -> list:
    from bti.longjob import Part
    todo = planner.missing(pdir, plan.chunks, force_ids, since)
    groups = planner.group_parts(todo, int(cfg["part_chars"]))
    state = {"failed": {}, "tries": {}}       # chunk id -> error ; chunk id -> attempts
    by = plan.by_id()
    parts = []

    def synth_run(ids: list[str], last: bool):
        def run(ctx):
            mine = [by[i] for i in ids]
            retry = [by[i] for i in list(state["failed"]) if i in by and i not in ids and state["tries"].get(i, 0) < 2]
            batch = [c for c in mine + retry if not planner.is_cached(pdir, c, since if (force_ids and c.id in force_ids) else None)]
            if not batch:
                return None
            for c in batch:
                state["tries"][c.id] = state["tries"].get(c.id, 0) + 1
            res = provider.synth(batch, files.chunks_dir(pdir), ctx, ctx.workdir)
            for c in batch:
                r = res.get(c.id)
                if r and r.get("ok"):
                    state["failed"].pop(c.id, None)
                elif not ctx.cancelled():
                    state["failed"][c.id] = (r or {}).get("error", "not spoken")
            if last and state["failed"] and not ctx.cancelled():
                bad = [by[i].spoken[:120] for i in state["failed"] if i in by]
                from bti.longjob import PartError
                ctx.log("failed sentences: " + "; ".join(bad))
                raise PartError("voice_chunks_failed", "Có %d câu máy chưa đọc được: %s" % (len(bad), " | ".join(bad[:3])))
            return {"spoken": len(batch) - len(state["failed"])}
        return _guard(run)

    def synth_done(ids: list[str]):
        return lambda ctx: all(planner.is_cached(pdir, by[i], since if (force_ids and i in force_ids) else None) for i in ids) \
            and not state["failed"]

    n = len(groups)
    for k, g in enumerate(groups):
        ids = [c.id for c in g]
        chars = sum(len(c.spoken) for c in g)
        parts.append(Part(key=f"synth-{k + 1}", title=f"Đọc phần {k + 1}/{n}", run=synth_run(ids, False), heavy=True,
                          est_seconds=planner.estimate_seconds(chars, cfg), is_done=synth_done(ids)))
    if n:
        # the last chance for sentences that failed in the last part
        parts.append(Part(key="synth-retry", title="Đọc lại các câu bị lỗi", run=synth_run([], True), heavy=True,
                          est_seconds=120, is_done=lambda ctx: not state["failed"]))

    def assemble_current() -> dict | None:
        cur = make_plan(pdir, cfg=cfg, provider=plan.provider, worker=worker)
        m = files.read_manifest(pdir) or {}
        a = m.get("assembled")
        if a and a.get("sig") == cur.assemble_sig and files.mix_path(pdir).is_file() and files.dry_path(pdir).is_file():
            return a
        return None

    def assemble_run(ctx):
        cur = make_plan(pdir, cfg=cfg, provider=plan.provider, worker=worker)
        if assemble_current():
            return None
        res = assemble(pdir, cur.chunks, cur.settings, cfg, ctx.workdir, ctx)
        info = {"sig": cur.assemble_sig, "duration": res["duration"], "loudness": res["loudness"], "spans": res["spans"],
                "mix_bytes": res["mix_bytes"], "at": store.now_iso()}

        def go(doc):
            doc["assembled"] = info
            doc.pop("timing", None)               # the timing belongs to the old assembly
        files.update_manifest(pdir, go)
        files.timing_path(pdir).unlink() if files.timing_path(pdir).is_file() else None
        return None

    parts.append(Part(key="assemble", title="Ghép thành một tệp âm thanh", run=_guard(assemble_run), est_seconds=120,
                      is_done=lambda ctx: _safe(lambda: assemble_current() is not None)))

    def timing_current() -> bool:
        cur = make_plan(pdir, cfg=cfg, provider=plan.provider, worker=worker)
        m = files.read_manifest(pdir) or {}
        t = m.get("timing")
        return bool(t and t.get("sig") == cur.assemble_sig and files.timing_path(pdir).is_file()
                    and (t.get("quality") == "aligned" or aligner.name == "even"))

    def align_run(ctx):
        cur = make_plan(pdir, cfg=cfg, provider=plan.provider, worker=worker)
        m = files.read_manifest(pdir) or {}
        a = m.get("assembled")
        if not a or a.get("sig") != cur.assemble_sig:
            raise VoiceError("voice_chunks_missing", "the mix is not current")
        spans = a["spans"]
        heard = aligner.heard(cur.chunks, spans, files.dry_path(pdir), ctx, ctx.workdir)
        if ctx.cancelled():
            return None
        words, st = align_mod.build_words(cur.chunks, spans, heard)
        timing = build_timing(cur, spans, words, st["ranges"], a["duration"], cfg)
        files.write_timing(pdir, timing)
        rate = round(st["matched"] / st["total"], 4) if st["total"] else 0.0
        quality = aligner.quality

        def go(doc):
            doc["timing"] = {"sig": cur.assemble_sig, "quality": quality, "match_rate": rate if quality == "aligned" else None,
                             "words": len(words), "aligner": aligner.name, "at": store.now_iso()}
            doc["timing_quality"] = quality
            doc["plan"] = {"assemble_sig": cur.assemble_sig, "text_hash": cur.text_hash, "chunk_ids": [c.id for c in cur.chunks],
                           "provider": cur.provider, "settings": cur.settings, "settings_sig": cur.settings_sig}
            doc["narration_rev"] = cur.narration.rev()
            doc["chunks"] = [{"id": c.id, "th": c.th, "beat": c.beat, "chapter": c.chapter, "spoken": c.spoken,
                              "start": s["start"], "end": s["end"]} for c, s in zip(cur.chunks, spans)]
            doc["duration"] = a["duration"]
            doc["loudness"] = a["loudness"]
            doc["finished_at"] = store.now_iso()
        files.update_manifest(pdir, go)
        floor = float(cfg["aligner"]["match_floor"])
        return {"timing_quality": quality, "match_rate": rate, "low_match": bool(quality == "aligned" and rate < floor)}

    ac = int(sum(len(c.spoken) for c in plan.chunks))
    est_align = int(planner.estimate_audio_seconds(ac, cfg) * 0.4 + 60) if aligner.name == "whisper" else 10
    parts.append(Part(key="align", title="Đo thời điểm từng từ", run=_guard(align_run), heavy=(aligner.name == "whisper"),
                      est_seconds=est_align, is_done=lambda ctx: _safe(timing_current)))
    return parts


def _safe(fn) -> bool:
    try:
        return bool(fn())
    except Exception:
        return False


def start(pdir: Path, pid: str, *, scope="changed", reseed_ids: list[str] | None = None, cfg: dict | None = None,
          server: dict | None = None, provider_name: str | None = None, aligner_force: str | None = None,
          manager=None) -> dict:
    """Start (or resume) the voice job; returns the job record. Raises VoiceError (and longjob.Busy)."""
    from bti.longjob import manager as real_manager
    manager = manager or real_manager
    cfg = cfg or load_voice_config()
    server = load_server_config() if server is None else server
    name = provider_name or cfg["provider"]
    provider = resolve(name, server)
    worker = getattr(provider, "w", None)
    plan = make_plan(pdir, cfg=cfg, provider=name, worker=worker)
    if reseed_ids:
        if reseed(pdir, plan, reseed_ids):
            plan = make_plan(pdir, cfg=cfg, provider=name, worker=worker)
    force: set[str] | None = None
    if isinstance(scope, list):
        force = {str(i) for i in scope}
    elif scope == "all":
        force = {c.id for c in plan.chunks}
    since = time.time()
    al = align_mod.choose(cfg, aligner_config(server), getattr(plan.narration, "language", "en"), aligner_force)
    parts = make_parts(pdir, pid, plan, provider=provider, aligner=al, force_ids=force, since=since, cfg=cfg, worker=worker)
    return manager.start(kind="voice", pid=pid, project_dir=pdir, parts=parts,
                         meta={"scope": scope if isinstance(scope, str) else "chunks", "provider": name, "aligner": al.name,
                               "chunks": len(plan.chunks)})
