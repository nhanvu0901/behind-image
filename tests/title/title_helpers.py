"""Helpers of the title tests: a project with an approved narration of real sentences (an Eligius-like story, so that the check's rules about the lines a title cites have
something to look at), the answers a title agent writes (good, and broken in each way the check refuses), and a fake agent that writes them into its work folder the way a real
one would, calls the `check` it was handed and sends a repair turn when the check finds problems. Nothing here calls a model, a program or a network."""
import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO, REPO / "tests" / "script", REPO / "tests" / "picks"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from picks_helpers import make_project  # noqa: E402,F401

from bti.script import store  # noqa: E402
from bti.script.store import Beat, NChapter, Narration  # noqa: E402

LINES = [
    ("c01", "cold_open", "COLD OPEN", [
        "A saint stands at a counter and weighs a ring on a pair of scales. Is this a prayer, or a shop sign?",
        "The panel was painted in 1449 for the goldsmiths of Bruges, and it worked as an advertisement for them."]),
    ("c02", "chapter", "THE SHOP", [
        "The saint is Eligius, the patron saint of goldsmiths, and in the story he was a goldsmith too.",
        "Two strangers watch from a round mirror at the front of the shop, and they are not part of the scene.",
        "Rings, belts and a cup lie on the shelves behind him, as in a real shop of the time."]),
    ("c03", "closing", "CLOSING", [
        "So the picture is both a prayer and an advertisement, and it was meant to be both.",
        "A ring on a pair of scales: that is the whole argument of the painting."]),
]


def make_title_project(root: Path, pid: str = "pk1", *, approved: bool = True) -> Path:
    """A library-style project whose narration is the eight lines above (b0001..b0007) in three chapters, approved by default."""
    d = make_project(root, pid, approved=False)
    n = Narration(pid, "The Test Painting", "en")
    for cid, role, title, texts in LINES:
        ch = NChapter(cid, role, title, False)
        for t in texts:
            ch.beats.append(Beat(n.new_beat_id(), t, ["f01"], ["the mirror"]))
        n.chapters.append(ch)
    store.save_narration(d, n)
    if approved:
        store.approve(d, "narration", n.rev())
    return d


def beat_ids(d: Path) -> list[str]:
    n = store.load_narration(d)
    return [b.id for c in n.chapters for b in c.beats]


def line_texts(d: Path) -> dict:
    n = store.load_narration(d)
    return {b.id: b.text for c in n.chapters for b in c.beats}


def cand(text, form, lines, why="Hai thứ trái ngược mà đều đúng với bức tranh.", scores=(5, 5, 5, 4)):
    return {"text": text, "form": form, "lines": list(lines), "scores": dict(zip(("curiosity", "concrete", "central", "clear"), scores)), "why": why}


def good_choice(ids=None) -> dict:
    """A file that passes every rule, for a project made by `make_title_project` (the ids default to b0001..b0007)."""
    ids = ids or ["b0001", "b0002", "b0003", "b0004", "b0005", "b0006", "b0007"]
    a, b, c, d_, e, f, g = ids
    return {"schema": "bti.title.choice/1", "candidates": [
        cand("The Saint Who Was Also an Advertisement", "contradiction", [a, b, f], "Một vị thánh và một tấm biển quảng cáo: hai thứ trái ngược mà đều đúng.", (5, 5, 5, 4)),
        cand("Why Is a Saint Weighing a Ring?", "question", [a], "Câu hỏi mà người lạ chưa thể trả lời.", (4, 5, 5, 5)),
        cand("The Two Strangers in the Mirror", "hidden", [d_], "Hai người lạ ngay trước mắt mà ít ai để ý.", (4, 5, 4, 5)),
        cand("This Painting Was a Shop Sign", "really_is", [a, b], "Bức tranh thật ra là một tấm biển hàng.", (4, 4, 4, 5)),
        cand("The Ring on the Scales", "object", [a, g], "Một vật nhỏ mang cả lập luận của bức tranh.", (3, 5, 4, 5)),
        cand("A Goldsmith's Prayer for Sale", "other", [a, c], "Lời cầu nguyện mà cũng là hàng để bán.", (3, 4, 4, 4))]}


def broken(change) -> dict:
    """`good_choice()` after `change(doc)` has been applied to it."""
    doc = copy.deepcopy(good_choice())
    change(doc)
    return doc


# ---------------------------------------------------------------------------------------------------------------- the fake agent
class FakeTitleAgent:
    """Stands for the module of a runner (`agy` or `claudecode`). For each session it writes `out/title.json` (what it was given for that turn), calls the `check` it was
    handed the way the real runner does, and sends a repair turn when the check finds problems, up to `max_repairs`. `answer`: a dict, a text (written as it is), a callable
    `f(ws_root, turn) -> dict | str`, or a list of these (turn 1, turn 2 ...). `hook(ws_root, kw)` runs first (to cancel, to block, to raise, to look at the folder)."""
    SUPPORTS_ALLOW = True

    def __init__(self, answer=None, hook=None, status="ok", error_code=None):
        self.answer, self.hook, self.status, self.error_code = answer, hook, status, error_code
        self.calls = []

    def run(self, ws_root, *, model=None, timeout=1800.0, max_repairs=2, check=None, cancel=None, on_progress=None, transcript_path=None, guard=None, prompt=None, python=None,
            runner=None, allow=None, **kw):
        from bti.draft.providers.agy import AgyResult
        ws = Path(ws_root)
        rec = {"model": model, "timeout": timeout, "max_repairs": max_repairs, "allow": allow, "problems": [], "turns": 0,
               "files": sorted(str(p.relative_to(ws)).replace("\\", "/") for p in ws.rglob("*") if p.is_file()),
               "task": (ws / "TASK.md").read_text(encoding="utf-8") if (ws / "TASK.md").is_file() else None}
        self.calls.append(rec)
        if self.hook is not None:
            r = self.hook(ws, {"cancel": cancel, "on_progress": on_progress, "runner": runner, "rec": rec})
            if r is not None:
                return r
        res = AgyResult(status=self.status, error_code=self.error_code, elapsed=1.0)
        if self.status == "error":
            res.error_message = "boom"
            return res
        ids = line_texts_of(ws)
        answer = self.answer if self.answer is not None else good_choice((ids * 7)[:7])          # a narration of any length: the first seven ids, or the ids again
        seq = answer if isinstance(answer, list) else [answer]
        turn = 1
        while True:
            item = seq[min(turn, len(seq)) - 1]
            item = item(ws, turn) if callable(item) else item
            (ws / "out").mkdir(exist_ok=True)
            (ws / "out" / "title.json").write_text(item if isinstance(item, str) else json.dumps(item, ensure_ascii=False), encoding="utf-8")
            res.turns, res.steps = turn, 4 * turn
            rec["turns"] = turn
            if on_progress:
                on_progress({"steps": 4 * turn, "last_action": "write_to_file", "turn": turn, "out_files": 1, "elapsed": 1.0})
            problems = check(turn) if check else None
            rec["problems"].append(problems)
            if problems and turn <= max_repairs:
                turn += 1
                res.repairs += 1
                continue
            break
        res.status = "ok"
        return res


def line_texts_of(ws: Path) -> list[str]:
    """The ids of the narration lines in a work folder (what a real agent reads from inputs/narration.json)."""
    d = json.loads((Path(ws) / "inputs" / "narration.json").read_text(encoding="utf-8"))
    return [ln["id"] for c in d["chapters"] for ln in c["lines"]]


def install_agent(monkeypatch, agent):
    """Put the fake where the session looks for a runner; the program counts as installed."""
    from bti.picks.auto import session
    monkeypatch.setattr(session, "agent_module", lambda model_id: agent)
    monkeypatch.setattr(session, "check_installed", lambda model_id: None)
    return agent
