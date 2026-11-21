"""Helpers of the tests of the automatic picks job (bti/picks/auto): a project with an approved narration and a main painting, fake picture
sources (no network), a fake agent that writes prepared output files into its work folder the way a real one would, and a runner that
starts the job and waits for it. Nothing here calls a model, a program or a network."""
import copy
import json
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO, REPO / "tests" / "script", REPO / "tests" / "media"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from picks_helpers import beat_ids, make_project, png_bytes  # noqa: E402

PNG = png_bytes(1300, 1250)
SMALL_PNG = png_bytes(64, 48)

PLAN = {
    "schema": "bti.picks.plan/1", "names": [],
    "regions": [
        {"name": "MIRROR", "box": [0.40, 0.30, 0.60, 0.55], "what": "Tấm gương lồi", "thing": "convex mirror on back wall"},
        {"name": "HEAD", "box": [0.10, 0.05, 0.30, 0.25], "what": "Khuôn mặt", "thing": "man's face"}],
    "lines": [
        {"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "kinds": ["whole"], "show": [{"type": "whole"}]},
        {"beat": "b0002", "reason": "Nói về tấm gương.", "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
        {"beat": "b0003", "reason": "Nói về họa sĩ.", "kinds": ["outside"],
         "show": [{"type": "context", "search": "Jan van Eyck portrait", "alt": ["van Eyck self portrait"], "kind": "portrait", "entity": "Jan van Eyck",
                   "period": "then", "what": "Chân dung họa sĩ"}],
         "fallback": {"type": "whole"}},
        {"beat": "b0004", "reason": "Nói về nơi vẽ.", "kinds": ["outside", "journey"],
         "show": [{"type": "map", "places": ["Bruges, Belgium", "Antwerp, Belgium"], "what": "Bản đồ Bruges và Antwerp"},
                  {"type": "clip", "search": "canal boat", "what": "Kênh đào", "seconds": 6}],
         "fallback": {"type": "whole"}},
        {"beat": "b0005", "reason": "Khuôn mặt người đàn ông.", "kinds": ["detail", "whole"],
         "show": [{"type": "detail", "region": "HEAD"}, {"type": "whole"}]},
        {"beat": "b0006", "reason": "Vẫn cùng ý.", "kinds": ["idea"], "show": []}]}

CHOICE = {
    "schema": "bti.picks.choice/1",
    "wants": [
        {"id": "b0003.1", "pick": 1, "reason": "Bản chụp chân dung rõ nét."},
        {"id": "b0004.1", "pick": 1, "reason": "Đúng thành phố Bruges."},
        {"id": "b0004.2", "pick": 1, "reason": "Cảnh kênh đào đúng ý."}],
    "regions": [
        {"name": "MIRROR", "action": "tight", "box": [120, 130, 735, 890], "confirmed": True, "reason": "Khung ôm sát tấm gương lồi."},
        {"name": "HEAD", "action": "tight", "box": [110, 110, 900, 860], "confirmed": True, "reason": "Khung ôm vừa khuôn mặt."}]}


def infer_kinds(line):
    """What a plan written before `kinds` existed would say: `kinds` and, for a line about something outside the painting, the `fallback` that the check wants.
    `FakeAgent.fit` applies it to a line whose `kinds` the prepared plan leaves out, so that the plans of the older tests stay valid."""
    line = dict(line)
    types = [i.get("type") for i in line.get("show") or [] if isinstance(i, dict)]
    kinds = []
    for t, k in (("detail", "detail"), ("whole", "whole")):
        if t in types:
            kinds.append(k)
    if "context" in types or "clip" in types:
        kinds = ["outside"]
        line.setdefault("fallback", {"type": "whole"})
    if "map" in types:
        kinds = (["outside"] if "outside" in kinds else []) + ["journey"]
        line["show"] = [dict(i, places=list(i.get("places") or [i["place"], "Antwerp, Belgium"])) if isinstance(i, dict) and i.get("type") == "map" else i
                        for i in line["show"]]
    line["kinds"] = kinds[:2] or ["idea"]
    return line


def plan(**changes):
    """A copy of PLAN; `changes` replaces top-level keys."""
    d = copy.deepcopy(PLAN)
    d.update(changes)
    return d


def choice(**changes):
    d = copy.deepcopy(CHOICE)
    d.update(changes)
    return d


# ---------------------------------------------------------------------------------------------------------------- the project
def make_auto_project(root: Path, pid: str = "pk1", *, approved: bool = True) -> Path:
    """A project whose narration (six lines b0001..b0006 in three chapters) is approved and whose picks hold only the main painting `A`."""
    from bti.picks import doc
    d = make_project(root, pid, approved=approved)
    (d / "media").mkdir(exist_ok=True)
    (d / "media" / "main.png").write_bytes(PNG)
    picks = doc.empty()
    picks["main_asset"] = "A"
    picks["assets"]["A"] = {"file": "media/main.png", "kind": "image", "title": "The Test Painting", "artist": "A. Painter", "year": "1434",
                            "width": 1300, "height": 1250, "credit": {"source": "upload", "flag": None}, "regions": {}}
    with doc.Held(d):
        doc.save(d, picks)
    return d


# ---------------------------------------------------------------------------------------------------------------- picture sources
class FakeSource:
    """A picture source with canned answers. `items`: metas, each with `_q` (a lower-case phrase the query must contain) and `kind`."""

    def __init__(self, name, items=None, fail=None):
        self.name, self.items, self.fail = name, list(items or []), fail
        self.searches, self.downloads = [], []

    def search(self, query, kind="image", limit=24):
        self.searches.append((query, kind, limit))
        if self.fail is not None:
            raise self.fail
        out = []
        for m in self.items:
            if m.get("_q", "") in query.lower() and m.get("kind", "image") == kind:
                out.append({k: v for k, v in m.items() if k != "_q"})
        return out[:limit]

    def fetch_meta(self, source_id):
        m = next(m for m in self.items if m["source_id"] == source_id)
        return {k: v for k, v in m.items() if k != "_q"}

    def licence(self, meta):
        return True, "CC0", ""

    def credit(self, meta):
        return {"source": self.name, "source_url": meta.get("page_url", ""), "author": meta.get("author", ""), "licence": meta.get("licence", ""),
                "licence_url": ""}

    def download(self, meta, dest, **kw):
        self.downloads.append(meta["source_id"])
        Path(dest).write_bytes(PNG)
        return Path(dest)


def meta(source, sid, title, q, kind="image", **kw):
    ext, mime = (".mp4", "video/mp4") if kind == "video" else (".png", "image/png")
    return {"source": source, "source_id": sid, "title": title, "thumb_url": "https://example.invalid/t/%s.jpg" % sid.replace(":", "_"),
            "page_url": "https://example.invalid/p/%s" % sid.replace(":", "_"), "width": 1300, "height": 1250, "mime": mime, "kind": kind,
            "author": "An Author", "licence": "CC0", "url": "https://example.invalid/f/%s%s" % (sid.replace(":", "_"), ext), "_q": q, **kw}


def default_sources():
    commons = FakeSource("commons", [
        meta("commons", "File:Portrait A.jpg", "Portrait A", "portrait"),
        meta("commons", "File:Portrait B.jpg", "Portrait B", "portrait"),
        meta("commons", "File:Canal boat.mp4", "Canal boat", "canal boat", kind="video")])
    met = FakeSource("met", [meta("met", "436535", "Portrait of a man", "portrait")])
    osm = FakeSource("osm", [meta("osm", "1:12:51.2090:3.2247:Bruges", "Bản đồ Bruges", "bruges")])
    return {"commons": commons, "met": met, "osm": osm}


def install_sources(monkeypatch, sources=None, keys=()):
    """Put fake sources where the media facade looks for them; `keys`: the names of the keyed sources that have a key."""
    from bti.media import api as media_api
    from bti.script import env
    sources = sources if sources is not None else default_sources()
    for name, src in sources.items():
        monkeypatch.setitem(media_api._SOURCES, name, src)
    names = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}
    monkeypatch.setattr(env, "has_key", lambda n: n in {names[k] for k in keys})
    monkeypatch.setattr("bti.media.clips.normalize", lambda src, dest, **kw: Path(dest).write_bytes(Path(src).read_bytes()))
    monkeypatch.setattr("bti.media.api._probe_upload_video", lambda p: {"width": 1920, "height": 1080, "duration": 7.5})
    return sources


def fake_thumb(pdir, cand, limited=None, clock=None):
    """The `fetch_thumb` seam: a small picture in the project's cache; none for a candidate whose id says `nothumb`."""
    from bti.picks.auto import store
    if "nothumb" in cand["source_id"]:
        return None
    dest = store.thumb_path(pdir, cand["source"], cand["source_id"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    import cv2
    import numpy as np
    cv2.imwrite(str(dest), np.full((48, 64, 3), 120, dtype=np.uint8))
    return dest.relative_to(pdir).as_posix()


def fake_book_thumb(pdir, item):
    return fake_thumb(pdir, {"source": "book", "source_id": item["source_id"]})


# ---------------------------------------------------------------------------------------------------------------- the fake agent
class FakeAgent:
    """Stands for the module of a runner (`agy` or `claudecode`). For each session it writes `out/plan.json` or `out/choice.json` (what it was
    given for that turn), calls the `check` it was handed the way the real runner does, and sends a repair turn when the check finds problems,
    up to `max_repairs`. `plan` / `choice`: a dict, a text (written as it is), a callable `f(ws_root, turn) -> dict | str`, or a list of these
    (turn 1, turn 2 ...). `hook(mode, ws_root, kw)` runs first (to cancel, to block, to raise)."""
    SUPPORTS_ALLOW = True

    def __init__(self, plan=PLAN, choice=CHOICE, hook=None, status="ok", error_code=None, tighten=None):
        self.plan, self.choice, self.hook, self.status, self.error_code = plan, choice, hook, status, error_code
        self.tighten = choice if tighten is None else tighten
        self.calls = []

    def _content(self, what, ws_root, turn, mode):
        seq = what if isinstance(what, list) else [what]
        item = seq[min(turn, len(seq)) - 1]
        item = item(ws_root, turn) if callable(item) else item
        return self.fit(item, ws_root, mode) if isinstance(item, dict) else item

    @staticmethod
    def fit(content, ws_root, mode):
        """What a real agent does by reading its inputs: a prepared plan keeps only the lines it must cover (and says what each does, `kinds`, when the
        prepared plan did not) and leaves out the regions the painting already has; a prepared choice/tighten answers every wanted picture and region it was shown."""
        ctx = json.loads((Path(ws_root) / "inputs" / "context.json").read_text(encoding="utf-8"))
        c = copy.deepcopy(content)
        if mode == "plan":
            c.setdefault("names", [])
            p = ctx["plan"]
            c["lines"] = [ln if ln.get("kinds") else infer_kinds(ln) for ln in c.get("lines", []) if ln.get("beat") in p["targets"]]
            c["regions"] = [r for r in c.get("regions", []) if r.get("name") not in p["existing_regions"]]
            have = {ln["beat"] for ln in c["lines"]}
            c["lines"] += [{"beat": b, "reason": "Giữ như đoạn trước.", "kinds": ["idea"], "show": []} for b in p["targets"] if b not in have]
        else:
            q = ctx["choice"] if mode == "choose" else ctx["tighten"]
            if mode == "choose":
                c["wants"] = [w for w in c.get("wants", []) if w.get("id") in q["wants"]]
                have = {w["id"] for w in c["wants"]}
                c["wants"] += [{"id": w, "pick": None, "reason": "Không chắc."} for w in q["wants"] if w not in have]
            c["regions"] = [r for r in c.get("regions", []) if r.get("name") in q["regions"]]
            haver = {r["name"] for r in c["regions"]}
            cutouts = q.get("cutouts") or {}
            for n in q["regions"]:
                if n in haver:
                    continue
                if n in cutouts:
                    cw, ch = cutouts[n]["cutout_size"]
                    c["regions"].append({
                        "name": n, "action": "tight",
                        "box": [max(0, cw // 5), max(0, ch // 5), max(2, (cw * 4) // 5), max(2, (ch * 4) // 5)],
                        "confirmed": True, "reason": "Khung ôm sát chi tiết.",
                    })
                else:
                    c["regions"].append({"name": n, "action": "keep", "reason": ""})
        return c

    def run(self, ws_root, *, model=None, timeout=1800.0, max_repairs=2, check=None, cancel=None, on_progress=None, transcript_path=None,
            guard=None, prompt=None, python=None, runner=None, allow=None, **kw):
        from bti.draft.providers.agy import AgyResult
        ws = Path(ws_root)
        mode = json.loads((ws / "inputs" / "context.json").read_text(encoding="utf-8"))["mode"]
        rec = {"mode": mode, "model": model, "timeout": timeout, "max_repairs": max_repairs, "allow": allow, "problems": [], "files": sorted(
            str(p.relative_to(ws)).replace("\\", "/") for p in ws.rglob("*") if p.is_file())}
        self.calls.append(rec)
        if self.hook is not None:
            r = self.hook(mode, ws, {"cancel": cancel, "on_progress": on_progress, "runner": runner, "rec": rec})
            if r is not None:
                return r
        res = AgyResult(status=self.status, error_code=self.error_code, elapsed=1.0)
        if self.status == "error":
            res.error_message = "boom"
            return res
        turn = 1
        src_val = {"plan": self.plan, "choose": self.choice, "tighten": self.tighten}[mode]
        out_name = {"plan": "plan.json", "choose": "choice.json", "tighten": "tighten.json"}[mode]
        while True:
            content = self._content(src_val, ws, turn, mode)
            (ws / "out").mkdir(exist_ok=True)
            (ws / "out" / out_name).write_text(
                content if isinstance(content, str) else json.dumps(content, ensure_ascii=False), encoding="utf-8")
            res.turns, res.steps = turn, 5 * turn
            if on_progress:
                on_progress({"steps": 5 * turn, "last_action": "write_to_file", "turn": turn, "out_files": 1, "elapsed": 1.0})
            problems = check(turn) if check else None
            rec["problems"].append(problems)
            if problems and turn <= max_repairs:
                turn += 1
                res.repairs += 1
                continue
            break
        res.status = "ok"
        return res


def install_agent(monkeypatch, agent):
    from bti.picks.auto import session
    monkeypatch.setattr(session, "agent_module", lambda model_id: agent)
    monkeypatch.setattr(session, "check_installed", lambda model_id: None)
    return agent


# ---------------------------------------------------------------------------------------------------------------- the job
class Env:
    """A project, the long-job manager pointed at it, the fake agent and the fake sources, and `start` / `run` for the job."""

    def __init__(self, root, pdir, agent, sources, manager):
        self.root, self.pdir, self.pid, self.agent, self.sources, self.manager = root, pdir, pdir.name, agent, sources, manager

    def start(self, **kw):
        from bti.draft.guard import Guard
        from bti.picks import auto
        seams = {"fetch_thumb": fake_thumb, "fetch_book_thumb": fake_book_thumb,
                 "guard_factory": lambda d: Guard(d, extra=lambda: None, repo_root=d.parent), "python": sys.executable}
        seams.update(kw)
        return auto.start(self.pid, self.pdir, manager=self.manager, **seams)

    def run(self, timeout=60, **kw):
        rec = self.start(**kw)
        return self.manager.wait(rec["id"], timeout)

    def picks(self):
        from bti.picks import doc
        return doc.load_or_new(self.pdir)

    def changes(self):
        from bti.ops.log import ChangeLog
        return ChangeLog(self.pdir).list("picks", 200)
