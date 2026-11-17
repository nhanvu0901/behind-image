"""What the page and the pipeline need to know about the voice of a project: `describe` (everything) and `state` (the pair of
words the stepper shows)."""
from __future__ import annotations

from pathlib import Path

from bti.script import store

from . import files, planner
from .config import load_server_config, load_voice_config, voice_worker
from .errors import VoiceError
from .plan import make_plan
from .chunks import written_hash
from .providers.chatterbox import wav_seconds


def _active(pid: str, manager=None):
    try:
        if manager is None:
            from bti.longjob import manager as manager
        return manager.active(pid, "voice")
    except Exception:         # the runner missing or broken never breaks the page
        return None


# Why a sentence has to be read again (when the voice settings are the same): its written text changed, only the pronunciation
# table changed its spoken text, or the owner asked for another reading of the same text (a new seed).
CHANGE_REASONS = ("narration_changed", "pronounce_changed", "reread")


def classify_changed(changed: list, prior: list) -> dict[str, int]:
    """{reason: number of sentences}. `prior` is the chunk list of the manifest (id, th and, since the pronunciation split, wh).
    A manifest written before `wh` existed cannot tell the narration from the table: it says narration_changed."""
    prior_th = {p.get("th") for p in prior if isinstance(p, dict)}
    prior_wh = {p.get("wh") for p in prior if isinstance(p, dict) and p.get("wh")}
    out: dict[str, int] = {}
    for c in changed:
        if c.th in prior_th:
            r = "reread"
        elif written_hash(c) in prior_wh:
            r = "pronounce_changed"
        else:
            r = "narration_changed"
        out[r] = out.get(r, 0) + 1
    return out


def change_detail(by_reason: dict[str, int], n: int) -> str:
    """The sentence of the status for the sentences that must be read again: one reason, or the split when they are mixed."""
    kinds = [r for r in CHANGE_REASONS if by_reason.get(r)]
    if len(kinds) == 1:
        return {"narration_changed": "Lời dẫn đã đổi: %d câu cần đọc lại." % n,
                "pronounce_changed": "Bảng phát âm đã đổi: %d câu cần đọc lại." % n,
                "reread": "Bạn đã yêu cầu đọc lại: %d câu cần đọc lại." % n}[kinds[0]]
    part = {"narration_changed": "%d do lời dẫn đổi", "pronounce_changed": "%d do bảng phát âm đổi", "reread": "%d do bạn yêu cầu đọc lại"}
    return "Cần đọc lại %d câu: %s." % (n, ", ".join(part[r] % by_reason[r] for r in kinds))


def describe(pdir: Path, pid: str | None = None, *, cfg: dict | None = None, server: dict | None = None,
             provider_name: str | None = None, manager=None, full: bool = True) -> dict:
    pdir = Path(pdir)
    pid = pid or pdir.name
    cfg = cfg or load_voice_config()
    server = load_server_config() if server is None else server
    prov = provider_name or cfg["provider"]
    worker = voice_worker(server) if prov == "chatterbox" else None
    out: dict = {"state": "none", "detail": "", "reasons": [], "provider": prov, "configured": prov != "chatterbox" or worker is not None,
                 "approved": False, "settings": None, "pronounce": {}, "chunks": [], "chapters": [], "counts": None,
                 "estimate": None, "mix": None, "timing": None, "job": None, "defaults": {"tempo_range": cfg["tempo_range"]}}
    n = store.load_narration(pdir)
    if n is None:
        out["detail"] = "Chưa có lời dẫn."
        return out
    o = store.load_outline(pdir)
    out["approved"] = bool(store.narration_approval(n, o)["approved"])
    manifest = files.read_manifest(pdir)
    if not out["approved"] and not manifest:
        out["detail"] = "Cần duyệt lời dẫn trước."
        return out
    try:
        plan = make_plan(pdir, cfg=cfg, provider=prov, worker=worker, narration=n)
    except VoiceError as e:
        out["detail"] = "Lời dẫn chưa có câu nào để đọc." if e.code == "nothing_to_say" else e.message
        return out
    m = manifest or {}
    known = set((m.get("plan") or {}).get("chunk_ids") or [])
    cached = {c.id: wav_seconds(files.chunk_path(pdir, c.id)) for c in plan.chunks}
    todo = [c for c in plan.chunks if cached[c.id] is None]
    changed = [c for c in plan.chunks if c.id not in known]
    mix_ok = files.mix_path(pdir).is_file()
    timing_ok = files.timing_path(pdir).is_file()
    sig_ok = (m.get("plan") or {}).get("assemble_sig") == plan.assemble_sig
    reasons = []
    by_reason: dict[str, int] = {}
    if not manifest or not (m.get("plan")):
        reasons.append("never_built")
    else:
        if (m.get("plan") or {}).get("settings_sig") == plan.settings_sig:
            by_reason = classify_changed(changed, m.get("chunks") or [])
            reasons += [r for r in CHANGE_REASONS if by_reason.get(r)]
        else:
            reasons.append("voice_changed")
        if not sig_ok and not changed:
            reasons.append("mix_settings_changed")
        if not mix_ok or not timing_ok:
            reasons.append("files_missing")
    job = _active(pid, manager)
    if job:
        out["state"], out["detail"] = "running", "Đang tạo giọng đọc."
        out["job"] = job.get("id") if isinstance(job, dict) else None
    elif "never_built" in reasons:
        out["state"], out["detail"] = "none", "Chưa tạo giọng đọc." + (" Đã đọc sẵn %d/%d câu." % (len(plan.chunks) - len(todo), len(plan.chunks)) if len(todo) < len(plan.chunks) else "")
    elif reasons:
        out["state"] = "stale"
        out["detail"] = {"narration_changed": change_detail(by_reason, len(changed)),
                         "pronounce_changed": change_detail(by_reason, len(changed)),
                         "reread": change_detail(by_reason, len(changed)),
                         "voice_changed": "Cài đặt giọng đã đổi: cần đọc lại.",
                         "mix_settings_changed": "Tốc độ hoặc nhạc nền đã đổi: cần ghép lại.",
                         "files_missing": "Thiếu tệp âm thanh hoặc thời gian: cần tạo lại."}[reasons[0]]
    else:
        out["state"], out["detail"] = "done", "Giọng đọc đã xong."
    out["reasons"] = reasons
    out["settings"] = plan.settings
    out["counts"] = {"total": len(plan.chunks), "cached": len(plan.chunks) - len(todo), "missing": len(todo), "changed": len(changed),
                     "by_reason": by_reason}
    chars = sum(len(c.spoken) for c in todo)
    out["estimate"] = {"chars": chars, "seconds": planner.estimate_seconds(chars, cfg) if todo else 0,
                       "parts": len(planner.group_parts(todo, int(cfg["part_chars"])))}
    if m.get("assembled") or mix_ok:
        out["mix"] = {"exists": mix_ok, "duration": m.get("duration") or (m.get("assembled") or {}).get("duration"),
                      "loudness": m.get("loudness"), "bytes": files.mix_path(pdir).stat().st_size if mix_ok else 0}
    if m.get("timing"):
        out["timing"] = {k: m["timing"].get(k) for k in ("quality", "match_rate", "words", "aligner")}
    if full:
        out["pronounce"] = plan.table
        spans = {c["id"]: c for c in m.get("chunks") or []}
        out["chunks"] = [{"id": c.id, "index": c.index, "beat": c.beat, "chapter": c.chapter, "text": " ".join(c.written),
                          "spoken": c.spoken, "cached": cached[c.id] is not None, "sec": cached[c.id],
                          "start": (spans.get(c.id) or {}).get("start"), "end": (spans.get(c.id) or {}).get("end"),
                          "new": c.id not in known, "seed": c.seed} for c in plan.chunks]
        out["chapters"] = [{"id": ch.id, "title": ch.title, "card": ch.card, "role": ch.role} for ch in plan.narration.chapters]
    return out


def state(project_dir) -> dict:
    """`{"state": "none|running|stale|done", "detail": str}` plus counts. Never raises."""
    try:
        d = describe(Path(project_dir), full=False)
        return {"state": d["state"], "detail": d["detail"], "reasons": d["reasons"], "counts": d["counts"]}
    except Exception:
        return {"state": "none", "detail": "Không đọc được dữ liệu giọng đọc.", "reasons": ["error"], "counts": None}
