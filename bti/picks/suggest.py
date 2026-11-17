""""Gợi ý thêm": visual suggestions for chosen beats, from You.com (paid) through a provider.

The only way a paid call can happen is the owner clicking the button in the running app: `POST /picks/suggest` with
`confirm_paid: true`. Nothing else starts it, and the real provider refuses unless the config allows it (`live_allowed`) and
`bti.media.research` agrees (`live=True` and the key). Tests use `FakeProvider`, which never touches the network.

The job runs in the shared long-job runner (`bti.longjob`, written by CORE; interface in the design doc, section 4): one
part per beat, so a cancel or a failure keeps the beats that are done, and starting the same job again resumes (a beat
that already has suggestions is skipped unless `refresh`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from bti.script import store as sstore

from . import context, doc
from .errors import PicksError

KIND = "picks"
MAX_BEATS = 40
SUGGESTIONS = "cache/picks/suggestions.json"
SCHEMA = "bti.picks.suggestions/1"
PART_ERRORS = {"suggest_off": "Gợi ý hình đang tắt trong cấu hình.", "suggest_no_key": "Chưa có khóa You.com trên máy chủ.",
               "suggest_failed": "You.com không trả lời được. Thử lại sau.",
               "suggest_key_refused": "You.com từ chối khóa của máy chủ. Cần kiểm tra khóa.",
               "suggest_quota": "Tài khoản You.com hết hạn mức hoặc cần thanh toán.",
               "suggest_timeout": "You.com trả lời quá chậm (hết thời gian chờ). Thử lại sau.",
               "suggest_bad_answer": "You.com từ chối yêu cầu hoặc trả lời sai dạng."}
_KIND_CODE = {"key_refused": "suggest_key_refused", "quota": "suggest_quota", "timeout": "suggest_timeout",
              "bad_answer": "suggest_bad_answer", "failed": "suggest_failed"}
_longjob = None          # tests put a fake module here; None means `bti.longjob`
REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- settings
def settings() -> dict:
    """`config/picks.json` (optional): `{"suggest": "youcom" | "off"}`. Default "youcom": the button works, and it still asks
    the owner to confirm the cost every time."""
    try:
        d = json.loads((REPO_ROOT / "config" / "picks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    mode = d.get("suggest") if isinstance(d, dict) else None
    return {"suggest": mode if mode in ("youcom", "off") else "youcom"}


def live_allowed() -> bool:
    return settings()["suggest"] == "youcom"


# ---------------------------------------------------------------- providers
class Provider(Protocol):
    name: str
    live: bool           # True: a call costs money

    def suggest(self, beat: dict, ctx: dict) -> list[dict]:
        """`beat`: {id, text, show}. `ctx`: the painting (title, artist, year, motifs). Returns
        [{what, kind, why, search_terms, source_urls, candidates: [media candidates]}]."""


class FakeProvider:
    """Canned answers for tests and for a dry run: no network, no cost."""
    name, live = "fake", False

    def __init__(self, by_beat: dict | None = None, default: list | None = None, fail: Exception | None = None):
        self.by_beat, self.default, self.fail, self.calls = by_beat or {}, default or [], fail, []

    def suggest(self, beat: dict, ctx: dict) -> list[dict]:
        self.calls.append(beat["id"])
        if self.fail is not None:
            raise self.fail
        return json.loads(json.dumps(self.by_beat.get(beat["id"], self.default)))


class YouComProvider:
    """The real one: `bti.media.research.visual_research` (a paid You.com call), then Commons and Met for each suggestion
    (free). Refuses unless the config allows live calls."""
    name, live = "youcom", True

    def __init__(self, limit_suggestions: int = 6, limit_candidates: int = 8):
        self.limit_suggestions, self.limit_candidates = limit_suggestions, limit_candidates

    def suggest(self, beat: dict, ctx: dict) -> list[dict]:
        if not live_allowed():
            raise PicksError(409, "suggestions are switched off in config/picks.json", "suggest_off")
        from bti.media import research
        from bti.media.youcom import YouComClient
        from bti.script import env as script_env
        client = YouComClient(api_key=script_env.get_key("YDC_API_KEY") or "")      # LR-001: the key may live only in the project's .env
        try:
            found = research.visual_research(beat["text"], ctx, client=client, live=True)
        except research.LiveCallDisabled as e:
            raise PicksError(409, str(e)[:200], "suggest_no_key")
        except research.ResearchError as e:
            key = client.api_key
            raw = f"{e} | status={e.status} | {e.detail}".replace(key, "***") if key else f"{e} | status={e.status} | {e.detail}"
            raise PicksError(502, raw[:500], _KIND_CODE.get(e.kind, "suggest_failed"))
        out = []
        for s in found[: self.limit_suggestions]:
            cands = research.resolve_suggestion(s)[: self.limit_candidates]
            out.append({**s, "candidates": cands})
        return out


def provider_info(override=None) -> dict:
    """What the page needs to know before it shows the button."""
    if override is not None:
        return {"available": True, "paid": bool(getattr(override, "live", False)), "provider": getattr(override, "name", "custom")}
    on = live_allowed()
    return {"available": on, "paid": True, "provider": "youcom" if on else "off"}


def pick_provider(override=None):
    if override is not None:
        return override
    if not live_allowed():
        raise PicksError(409, "suggestions are switched off in config/picks.json", "suggest_off")
    return YouComProvider()


# ---------------------------------------------------------------- stored suggestions
def _path(pdir: Path) -> Path:
    return Path(pdir) / SUGGESTIONS


def load_suggestions(pdir: Path) -> dict:
    d = sstore.read_object(_path(pdir), "picks") or {}
    beats = d.get("beats") if isinstance(d.get("beats"), dict) else {}
    return {"schema": SCHEMA, "beats": beats}


def _store(pdir: Path, bid: str, provider_name: str, items: list[dict]) -> None:
    with doc.Held(pdir):
        d = load_suggestions(pdir)
        d["beats"][bid] = {"created_at": sstore.now_iso(), "provider": provider_name, "items": items}
        sstore.write_json_atomic(_path(pdir), d, levels=2)


# ---------------------------------------------------------------- the job
def _lj():
    if _longjob is not None:
        return _longjob
    try:
        import bti.longjob as lj
    except ImportError:
        raise PicksError(503, "the long-job runner is not available yet", "longjob_missing")
    return lj


def _beats_of(pdir: Path, ids: list[str]) -> list[dict]:
    nv = context.narration_view(pdir)
    by = {b["id"]: b for c in nv["chapters"] for b in c["beats"]}
    out = []
    for i in ids:
        if i not in by:
            raise PicksError(404, f"beat {str(i)[:20]} not found", "not_found")
        out.append(by[i])
    return out


def start(pdir: Path, pid: str, beat_ids, *, confirm_paid, refresh: bool = False, override=None) -> dict:
    """Start the suggestion job for `beat_ids`. `confirm_paid` must be True: the owner has read that it costs money."""
    if confirm_paid is not True:
        raise PicksError(422, "confirm_paid must be true: this call costs money", "confirm_required")
    if not isinstance(beat_ids, list) or not beat_ids or not all(isinstance(i, str) for i in beat_ids):
        raise PicksError(422, "beats (a list of beat ids) is required", "invalid")
    ids = list(dict.fromkeys(beat_ids))
    if len(ids) > MAX_BEATS:
        raise PicksError(422, f"at most {MAX_BEATS} beats at a time", "too_many")
    beats = _beats_of(pdir, ids)
    provider = pick_provider(override)
    lj = _lj()
    ident = context.identity(pdir)
    ctx = {**ident, "motifs": [d["label"] for d in context.details(pdir)][:3]}

    def make(b: dict):
        def run(c):
            if c.cancelled():
                return None
            have = load_suggestions(pdir)["beats"].get(b["id"])
            if have and not refresh:
                c.progress(1.0, "đã có gợi ý")
                return {"beat": b["id"], "skipped": True}
            c.progress(0.1, "đang hỏi You.com")
            try:
                items = provider.suggest({"id": b["id"], "text": b["text"], "show": b["show"]}, ctx)
            except PicksError as e:
                c.log(f"{e.code}: {str(e)[:400]}")          # LR-002: the reason was thrown away; the owner/engineer saw only a generic sentence
                raise lj.PartError(e.code or "suggest_failed", PART_ERRORS.get(e.code, "Không lấy được gợi ý hình từ You.com."))
            _store(pdir, b["id"], getattr(provider, "name", "custom"), items)
            c.progress(1.0, f"{len(items)} gợi ý")
            return {"beat": b["id"], "n": len(items)}
        return run

    parts = [lj.Part(key=f"beat-{b['id']}", title=f"Gợi ý cho {b['id']}", run=make(b), heavy=False, est_seconds=60) for b in beats]
    try:
        job = lj.manager.start(kind=KIND, pid=pid, project_dir=pdir, parts=parts,
                               meta={"beats": ids, "provider": getattr(provider, "name", "custom"), "refresh": bool(refresh)})
    except getattr(lj, "Busy", ()) as e:       # noqa: PIE786
        raise PicksError(409, "a suggestion job is already running for this project", "busy", job_id=(getattr(e, "job", None) or {}).get("id"))
    jid = job if isinstance(job, str) else (job.get("id") if isinstance(job, dict) else getattr(job, "id", None))
    return {"job_id": jid}


def running(pid: str) -> bool:
    """Is a suggestion job running for this project? False when the runner does not exist (yet)."""
    try:
        lj = _lj()
        act = lj.manager.active(pid, kind=KIND)
    except Exception:       # noqa: BLE001
        return False
    return bool(act)
