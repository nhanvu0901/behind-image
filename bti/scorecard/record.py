"""Render record (`record.json` and `record.md`) built from project jobs and scorecard counts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bti.output import facts as F

RECORD_SCHEMA = "bti.record/1"
REPO_ROOT = Path(__file__).resolve().parents[2]
STEP_ORDER = ("outline", "narration", "title", "voice", "picks", "draft", "review", "edit", "music", "export")


def code_version(repo_root: Path | None = None) -> str:
    """Read current git commit hash from `.git/HEAD` without invoking git."""
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    git_entry = root / ".git"
    git_dir = git_entry
    if git_entry.is_file():
        try:
            txt = git_entry.read_text(encoding="utf-8").strip()
            if txt.startswith("gitdir:"):
                raw = Path(txt.split(":", 1)[1].strip())
                git_dir = raw if raw.is_absolute() else (root / raw).resolve()
        except OSError:
            return "unknown"
    head = git_dir / "HEAD"
    try:
        val = head.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    if val.startswith("ref:"):
        ref_rel = val.split(":", 1)[1].strip()
        ref_path = git_dir / ref_rel
        try:
            return ref_path.read_text(encoding="utf-8").strip()[:12] or "unknown"
        except OSError:
            packed = git_dir / "packed-refs"
            if packed.is_file():
                for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
                    if not line.startswith("#") and not line.startswith("^"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] == ref_rel:
                            return parts[0][:12]
            return "unknown"
    return val[:12] or "unknown"


def _step_kind(job: dict) -> str:
    kind = str(job.get("kind") or "")
    if kind == "draft" and "review" in str(job.get("detail") or "").lower():
        return "review"
    return kind


def _job_rows_with_mode(pdir: Path, f: F.Facts) -> list[dict]:
    """Read jobs from `Facts` and detect `draft` mode `review` from longjob files when present."""
    lj_dir = Path(pdir) / "cache" / "longjobs"
    modes: dict[str, str] = {}
    if lj_dir.is_dir():
        for p in lj_dir.glob("*.json"):
            doc = F._read_json(p)
            if isinstance(doc, dict) and isinstance(doc.get("id"), str):
                mode = (doc.get("meta") or {}).get("mode") if isinstance(doc.get("meta"), dict) else None
                if isinstance(mode, str):
                    modes[doc["id"]] = mode
    out = []
    for j in f.jobs:
        row = dict(j)
        if row.get("kind") == "draft" and modes.get(row.get("id")) == "review":
            row["kind"] = "review"
        out.append(row)
    return out


def _summarize_steps(jobs: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for j in jobs:
        k = _step_kind(j)
        if k:
            grouped.setdefault(k, []).append(j)
    order = list(STEP_ORDER) + sorted(k for k in grouped if k not in STEP_ORDER)
    steps: list[dict] = []
    for kind in order:
        rows = grouped.get(kind)
        if not rows:
            continue
        done_rows = [r for r in rows if r.get("state") == "done"]
        latest = done_rows[-1] if done_rows else rows[-1]
        durs = [
            max(0.0, float(r["finished"]) - float(r["created"]))
            for r in rows
            if isinstance(r.get("created"), (int, float)) and isinstance(r.get("finished"), (int, float)) and r["finished"] >= r["created"]
        ]
        latest_dur = (
            round(max(0.0, float(latest["finished"]) - float(latest["created"])), 1)
            if isinstance(latest.get("created"), (int, float)) and isinstance(latest.get("finished"), (int, float)) and latest["finished"] >= latest["created"]
            else None
        )
        steps.append({
            "step": kind,
            "agent": latest.get("agent"),
            "model": latest.get("model"),
            "duration_s": latest_dur,
            "total_seconds": round(sum(durs), 1) if durs else None,
            "runs": len(rows),
            "state": latest.get("state"),
            "finished": latest.get("finished"),
            "job_id": latest.get("id"),
        })
    return steps


def _counts_from_scorecard(sc: dict) -> dict[str, Any]:
    by_key = {m["key"]: m for m in (sc.get("metrics") or []) if isinstance(m, dict) and "key" in m}
    sp = by_key.get("small_painting_share") or {}
    mk = by_key.get("marks_per_minute") or {}
    bm = by_key.get("biggest_mark") or {}
    mp = by_key.get("marks_on_person") or {}
    ns = (by_key.get("name_strips") or {}).get("value") or {}
    bp = (by_key.get("borrowed_pictures") or {}).get("value") or {}
    ss = by_key.get("short_shots") or {}
    sn = by_key.get("subject_not_shown") or {}
    ui = by_key.get("unfilled_identity") or {}
    ld = (by_key.get("loudness") or {}).get("value") or {}
    pv = (by_key.get("pause_vs_speech") or {}).get("value") or {}
    return {
        "shots": sc.get("shots"),
        "duration_s": sc.get("duration_s"),
        "small_painting_s": sp.get("seconds"),
        "small_painting_share": sp.get("value"),
        "marks_total": mk.get("total"),
        "rings": mk.get("rings"),
        "spotlights": mk.get("spotlights"),
        "marks_per_min": mk.get("value"),
        "biggest_mark_pct": bm.get("value"),
        "marks_over_30_pct": bm.get("over_30_count"),
        "marks_on_person": mp.get("value"),
        "name_strips": ns.get("count"),
        "strip_sub_repeats": ns.get("sub_repeats"),
        "strip_on_thing": ns.get("on_thing"),
        "borrowed_count": bp.get("count"),
        "borrowed_seconds": bp.get("seconds"),
        "borrowed_share": bp.get("share"),
        "borrowed_longest_gap_s": bp.get("longest_gap_s"),
        "borrowed_under_3s": bp.get("under_3s_count"),
        "short_shots": ss.get("value"),
        "subject_not_shown": sn.get("value"),
        "unfilled_identity": ui.get("value"),
        "loudness_lufs": ld.get("lufs"),
        "pause_vs_speech_db": pv.get("diff_db"),
    }


def build_record(project_dir: Path, scorecard: dict, *, facts: F.Facts | None = None, repo_root: Path | None = None) -> dict:
    """Build deterministic render record JSON from project facts and `scorecard`."""
    pdir = Path(project_dir)
    f = facts if facts is not None else F.collect(pdir)
    jobs = _job_rows_with_mode(pdir, f)
    date = (f.export_manifest or {}).get("created") or F.last_event(f) or f.created or ""
    return {
        "schema": RECORD_SCHEMA,
        "date": date,
        "project": f.pid,
        "artwork": {"key": f.key, "title": f.title, "artist": f.artist, "year": f.year},
        "video_title": (F.title_public(f) or {}).get("text"),
        "code_version": code_version(repo_root),
        "storyboard_rev": scorecard.get("storyboard_rev"),
        "export_rev": scorecard.get("export_rev"),
        "steps": _summarize_steps(jobs),
        "counts": _counts_from_scorecard(scorecard),
        "owner_comments": {"good": [], "not_good": [], "wants": [], "notes": ""},
    }
