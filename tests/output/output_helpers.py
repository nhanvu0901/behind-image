"""A fixture project that is made step by step, the way a real one moves: after each method the project stands where the owner would see it after that step.
Real documents (the script store's dataclasses, the picks document, a storyboard with its revision, an export manifest the export code accepts as current); the heavy
stages (the voice, the export) are stood in for by small files, which is what the stage packages' own tests cover. No model, no voice, no render, no network."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image

from bti.editor.common import compute_rev, file_signature
from bti.picks import context, doc as pdoc
from bti.script import store as sstore

REPO = Path(__file__).resolve().parents[2]
PID = "dutch-portrait"
KEY = "vermeer-the-dutch-portrait"
TITLE = "The Dutch Portrait"
STAMP = "2026-11-19T09:00:00-0800"
BOOKS = [{"work_id": "payne_gae/002", "book_id": "payne_gae", "pdf_pages": [23, 35]}, {"work_id": "hodge_aid/003", "book_id": "hodge_aid", "pdf_pages": [22, 25]}]

CHAPTERS = [("c01", "cold_open", "COLD OPEN", ["High on the back wall hangs a mirror. In Latin, it says Vermeer was here.", "Below it stands a woman, a pearl at her ear."]),
            ("c02", "chapter", "THE ROOM", ["The room is small and the light comes from the left.", "A map of the provinces covers the wall behind her.", "Dutch merchants bought such pictures by the yard."]),
            ("c03", "closing", "CLOSING", ["It is only a view, but it is a view worth keeping."])]


def png(path: Path, size=(400, 500), color=(120, 90, 60)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def make_video(path: Path, seconds: float = 6.0) -> None:
    """A real, short H.264 file (ffmpeg's test pattern): what the contact sheets are cut from."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=%s" % seconds, "-pix_fmt", "yuv420p", str(path)], check=True,
                   stdin=subprocess.DEVNULL, timeout=60)


class Project:
    """projects/<pid> of a temporary data root, and the output root beside it."""

    def __init__(self, tmp: Path, pid: str = PID, key: str = KEY, created: str = STAMP, title: str = TITLE):
        self.root = tmp / "projects"
        self.out = tmp / "output"
        self.pid, self.key, self.title, self.created = pid, key, title, created
        self.d = self.root / pid
        self.voice_ok = False
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- step 1
    def create(self) -> "Project":
        d = self.d
        (d / "source").mkdir(parents=True)
        (d / "source" / "payne_gae_002.txt").write_text("The Dutch portrait is small. " * 40, encoding="utf-8")
        (d / "source" / "hodge_aid_003.txt").write_text("A woman in a pearl earring. " * 25, encoding="utf-8")
        (d / "source" / "dossier.json").write_text(json.dumps({"identity": {"title": self.title, "artist": "Jan Vermeer", "year": "1665"},
                                                               "details": ["the mirror", "the pearl"]}), encoding="utf-8")
        meta = {"id": self.pid, "title": self.title, "artist": "Jan Vermeer", "year": "1665", "stage": "selected", "created_at": self.created, "sources": BOOKS,
                "artwork_key": self.key, "dossier": "source/dossier.json"}
        (d / "project.json").write_text(json.dumps(meta), encoding="utf-8")
        return self

    # ---- step 2
    def outline(self) -> "Project":
        chapters = [sstore.OChapter(cid, role, title, False, "Purpose of " + title, 150, ["f01", "f02"] if cid == "c01" else ["f03"], ["D1", "D2 the pearl", "the whole room"])
                    for cid, role, title, _ in CHAPTERS]
        facts = [sstore.Fact("f01", "Vermeer signed the picture in 1665.", ["PAY-01"], "established"), sstore.Fact("f02", "The sitter is unknown.", ["HOD-02"], "disputed"),
                 sstore.Fact("f03", "The panel is small.", ["PAY-02"], "likely"), sstore.Fact("f04", "A fact no chapter uses.", [], "likely")]
        o = sstore.Outline(thesis="Who is the woman, and why was she painted?", hook_options=[sstore.Hook("h1", "Look into the mirror."), sstore.Hook("h2", "Count the pearls.")],
                           hook_choice="h1", chapters=chapters, facts=facts, target_words=300)
        sstore.save_outline(self.d, o)
        return self

    def approve_outline(self, by: str = "cli:test") -> "Project":
        sstore.approve(self.d, "outline", sstore.load_outline(self.d).rev(), by=by)
        return self

    def narration(self) -> "Project":
        n = sstore.Narration(project=self.pid, title=self.title, language="en")
        i = 0
        for cid, role, title, lines in CHAPTERS:
            beats = []
            for text in lines:
                i += 1
                beats.append(sstore.Beat("b%04d" % i, text, ["f01"], ["the mirror", "D2"], False, ""))
            n.chapters.append(sstore.NChapter(cid, role, title, False, beats))
        sstore.save_narration(self.d, n)
        return self

    def approve_narration(self, by: str = "cli:test") -> "Project":
        sstore.approve(self.d, "narration", sstore.load_narration(self.d).rev(), by=by)
        return self

    def edit_narration(self) -> "Project":
        n = sstore.load_narration(self.d)
        n.chapters[0].beats[0].text += " (a new sentence)"
        sstore.save_narration(self.d, n)
        return self

    # ---- step 3
    def voice(self) -> "Project":
        """The audio files, timing.json (from the narration) and the voice manifest; the voice counts as done."""
        n = sstore.load_narration(self.d)
        words, beats, chapters, t = [], [], [], 0.35
        for ch in n.chapters:
            c0 = t
            for b in ch.beats:
                b0, w0 = t, len(words)
                for w in b.text.split():
                    words.append({"w": w, "s": round(t, 2), "e": round(t + 0.35, 2)})
                    t += 0.4
                beats.append({"id": b.id, "chapter": ch.id, "text": b.text, "w0": w0, "w1": len(words), "start": round(b0, 2), "end": round(t, 2)})
                t += 0.2
            chapters.append({"id": ch.id, "name": ch.title, "start": round(c0, 2), "end": round(t, 2), "card": False})
        self.duration = round(t, 2)
        (self.d / "timing.json").write_text(json.dumps({"duration": self.duration, "words": words, "beats": beats, "chapters": chapters}), encoding="utf-8")
        (self.d / "audio").mkdir(exist_ok=True)
        (self.d / "audio" / "mix.m4a").write_bytes(b"MIX" * 400)
        (self.d / "audio" / "voice.wav").write_bytes(b"WAV" * 1000)
        (self.d / "voice").mkdir(exist_ok=True)
        (self.d / "voice" / "voice.json").write_text(json.dumps({"schema": "bti.voice/1", "finished_at": "2026-11-19T09:26:04-0800", "duration": self.duration, "chunks": []}), encoding="utf-8")
        self.voice_ok = True
        return self

    # ---- step 4
    def picks(self) -> "Project":
        for name, size, col in (("a.jpg", (400, 500), (120, 90, 60)), ("b.jpg", (300, 200), (30, 60, 120)), ("c.jpg", (200, 200), (90, 160, 90)), ("d.jpg", (250, 250), (200, 20, 20))):
            png(self.d / "media" / name, size, col)
        n = sstore.load_narration(self.d)
        beats = {}
        for ch in n.chapters:
            for k, b in enumerate(ch.beats):
                items = [{"asset": "A", "region": "MIRROR" if k % 2 == 0 else None, "role": "detail", "note": ""}]
                if b.id == "b0003":
                    items.append({"asset": "B", "region": None, "role": "context", "note": ""})
                if b.id == "b0004":
                    items.append({"asset": "D", "region": None, "role": "context", "note": ""})          # picked for a line, but no shot of the storyboard uses it
                beats[b.id] = {"items": items, "status": "picked", "note": ""}
        cred = {"source": "commons", "source_url": "https://commons.example/A", "author": "Jan Vermeer", "licence": "PD", "licence_url": "", "flag": None}
        d = {"schema": pdoc.SCHEMA, "main_asset": "A", "approval": {"approved": False}, "beats": beats, "assets": {
            "A": {"file": "media/a.jpg", "kind": "image", "title": TITLE, "artist": "Jan Vermeer", "year": "1665", "width": 400, "height": 500, "credit": cred,
                  "regions": {"MIRROR": {"x": 200, "y": 120, "rx": 80, "ry": 60, "label": "Tấm gương trên tường"}, "PEARL": {"x": 250, "y": 300, "rx": 30, "ry": 30, "label": "Viên ngọc trai"}}},
            "B": {"file": "media/b.jpg", "kind": "image", "title": "A map of the provinces", "artist": "", "year": "", "width": 300, "height": 200, "credit": {**cred, "source_url": "https://commons.example/B"}, "regions": {}},
            "C": {"file": "media/c.jpg", "kind": "image", "title": "A picture nobody uses", "artist": "", "year": "", "width": 200, "height": 200, "credit": cred, "regions": {}},
            "D": {"file": "media/d.jpg", "kind": "image", "title": "Picked, never on screen", "artist": "", "year": "", "width": 250, "height": 250, "credit": cred, "regions": {}}}}
        with pdoc.Held(self.d):
            pdoc.save(self.d, d)
        return self

    def approve_picks(self, by: str = "cli:test") -> "Project":
        nv = context.narration_view(self.d)
        with pdoc.Held(self.d):
            pdoc.stamp_approval(self.d, pdoc.revision(pdoc.load(self.d)), nv["rev"], by=by)
        return self

    def edit_picks(self) -> "Project":
        d = pdoc.load(self.d)
        d["beats"]["b0001"]["note"] = "look closer"
        with pdoc.Held(self.d):
            pdoc.save(self.d, d)
        return self

    # ---- step 5
    def storyboard(self) -> "Project":
        pk = pdoc.load(self.d)
        assets = {k: {kk: v[kk] for kk in ("file", "kind", "title", "artist", "year", "width", "height", "credit", "regions")} for k, v in pk["assets"].items()}
        T = json.loads((self.d / "timing.json").read_text(encoding="utf-8"))["duration"]
        step = T / 7
        shots = [
            {"id": "s0001", "start": {"t": 0.0}, "technique": "CAM-01", "slots": {"image": {"asset": "A", "region": "MIRROR"}}, "params": {}, "intent": "explore", "overlays": [], "locked": False},
            {"id": "s0002", "start": {"t": round(step, 2)}, "technique": "CAM-03", "slots": {"image": {"asset": "A"}}, "params": {}, "intent": "explore",
             "overlays": [{"id": "o1", "technique": "HI-01", "start": {"t": round(step + 0.5, 2)}, "dur": 1.0, "params": {"at": "MIRROR"}}], "locked": True},
            {"id": "s0003", "start": {"t": round(2 * step, 2)}, "technique": "STATIC-01", "slots": {"image": {"asset": "B"}}, "params": {}, "intent": "context", "overlays": [], "locked": False},
            {"id": "s0004", "start": {"t": round(3 * step, 2)}, "technique": "X-CARD-02", "slots": {}, "params": {"title": "THE ROOM"}, "intent": "context", "overlays": [], "locked": False},
            {"id": "s0005", "start": {"t": round(4 * step, 2)}, "technique": "CAM-05", "slots": {"image": {"asset": "A", "region": "PEARL"}}, "params": {}, "intent": "isolate",
             "overlays": [{"id": "o2", "technique": "X-ANN-01", "start": {"t": round(4 * step + 0.3, 2)}, "dur": 2.0, "params": {"text": "Pearl"}}], "locked": False},
            {"id": "s0006", "start": {"t": round(5 * step, 2)}, "technique": "CAM-03", "slots": {"image": {"asset": "A"}}, "params": {}, "intent": "explore", "overlays": [], "locked": False},
            {"id": "s0007", "start": {"t": round(6 * step, 2)}, "technique": "STATIC-01", "slots": {"image": {"asset": "A"}}, "params": {}, "intent": "context", "overlays": [], "locked": False}]
        sb = {"schema": "bti.storyboard/1", "project": self.pid, "title": self.title, "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
              "audio": "audio/mix.m4a", "assets": assets, "shots": shots, "end": {"t": T}, "approvals": {"storyboard": None}}
        (self.d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
        return self

    def approve_storyboard(self, by: str = "cli:test") -> "Project":
        sb = json.loads((self.d / "storyboard.json").read_text(encoding="utf-8"))
        sb["approvals"] = {"storyboard": {"rev": compute_rev(sb), "approved_at": "2026-11-19T11:36:19-0800", "by": by}}
        (self.d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
        return self

    def edit_storyboard(self) -> "Project":
        sb = json.loads((self.d / "storyboard.json").read_text(encoding="utf-8"))
        sb["shots"][0]["note"] = "edited"
        (self.d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
        return self

    # ---- step 6
    def export(self, video: Path | None = None, status: str = "ok") -> "Project":
        """An export the export code counts as current: the manifest names the storyboard and the audio it was made from."""
        sb = json.loads((self.d / "storyboard.json").read_text(encoding="utf-8"))
        e = self.d / "export"
        e.mkdir(exist_ok=True)
        if video is not None:
            shutil.copyfile(video, e / (self.pid + ".mp4"))
        else:
            (e / (self.pid + ".mp4")).write_bytes(b"VIDEO" * 2000)
        (e / "description.txt").write_text("The Dutch Portrait\n\n00:00 Cold open\n", encoding="utf-8")
        (e / "chapters.txt").write_text("00:00 Cold open\n", encoding="utf-8")
        T = json.loads((self.d / "timing.json").read_text(encoding="utf-8"))["duration"]
        manifest = {"schema": "bti.export/1", "pid": self.pid, "slug": self.pid, "storyboard_rev": compute_rev(sb), "audio_sig": file_signature(self.d / "audio" / "mix.m4a"),
                    "audio_file": "audio/mix.m4a", "duration": T, "frames": int(T * 30), "fps": 30, "width": 1920, "chapters": 3, "chapters_merged": 0, "parts": [],
                    "files": {"video": self.pid + ".mp4", "description": "description.txt", "chapters": "chapters.txt"},
                    "report": [{"key": "video", "status": "ok", "value": "h264", "expected": "h264", "note": ""},
                               {"key": "loudness", "status": status, "value": -15.0, "expected": -15.0, "note": ""},
                               {"key": "size", "status": "ok", "value": 10000, "expected": None, "note": ""}],
                    "report_status": status, "loudness": {"lufs": -15.0, "lra": 3.0, "true_peak": -1.7}, "credits": ["credit line"], "notes": [], "created": "2026-11-19T11:50:03-0800", "seconds": 863.2}
        (e / "export.json").write_text(json.dumps(manifest), encoding="utf-8")
        return self

    # ---- the rest
    def change(self, batch_doc: str = "storyboard", note: str = "Make the CAM-03 shots fill the screen", what: str = "Cảnh 2: dời điểm cắt từ 0:10 sang 0:12") -> "Project":
        from bti.ops.log import ChangeLog
        rec = {"doc": batch_doc, "time": "2026-11-19T10:00:00-0800", "actor": "agent:claude:claude-opus-5-5@high", "note": note, "ops": [{"op": "move_boundary", "shot": "s0002", "to": 12.0}],
               "applied": 1, "changes": [{"target": {"shot": "s0002"}, "time": "0:12", "what": what}], "created": {"shots": [], "overlays": [], "assets": [], "refs": {}},
               "rev_before": "a", "rev_after": "b", "touched": ["shot:s0002"], "undo_of": None, "scope": None}
        ChangeLog(self.d).write(rec, {"x": 1}, {"x": 2})
        return self

    def job(self, jid: str, kind: str, state: str = "done", sub: str = "longjobs", **meta) -> "Project":
        d = self.d / "cache" / sub
        d.mkdir(parents=True, exist_ok=True)
        rec = {"id": jid, "kind": kind, "pid": self.pid, "state": state, "progress": 1.0, "parts": [], "error": None, "error_code": None, "result": {}, "created": 1795104252.0,
               "finished": 1795104252.0 + 120, "meta": meta, "log_tail": []}
        if sub == "jobs":
            rec.update(agent=meta.get("agent"), model=meta.get("model"))
        (d / (jid + ".json")).write_text(json.dumps(rec), encoding="utf-8")
        if sub == "longjobs":                                  # only the long jobs keep a text log beside their record
            (d / (jid + ".log")).write_text("log line\n" * 50, encoding="utf-8")
        return self

    def caches(self) -> "Project":
        """Everything the app keeps under cache/ after a long session: what the cleaning removes and what it must leave."""
        c = self.d / "cache"
        for rel, size in (("export/parts/part_01_x.mp4", 5000), ("export/video_all.mp4", 7000), ("export/chapters.ffmeta", 30), ("frames/f_1_1000_640.jpg", 800), ("thumbs/t.jpg", 300),
                          ("previews/p.mp4", 900), ("uploads/u.tmp", 100), ("picks_auto/plan.json", 200), ("picks_auto/last.json", 150), ("picks_auto/thumbs/x.jpg", 400), ("picks_auto/runs/20261119-083125/plan-events.jsonl", 2000), ("voice/mix_pre.wav", 3000),
                          ("wave_abc_4000.json", 100), ("longjobs/work/voice/align/heard.json", 300),
                          ("draft/thread.json", 120), ("draft/turns/t1/out/c01.json", 50), ("picks/suggestions.json", 90)):
            p = c / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x" * size)
        self.job("1111111111111111", "voice", provider="chatterbox", aligner="whisper")
        self.job("2222222222222222", "draft", agent={"id": "opus", "label": "Opus 5.5 High", "model": "m"}, model="claude:m", mode="edit", instruction="Fill the screen in the CAM-03 shots")
        self.job("3333333333333333", "outline", sub="jobs", agent={"id": "opus", "label": "Opus 5.5 High"}, model="claude:m")
        return self

    # ---- helpers for the tests
    def stage(self, upto: str) -> "Project":
        order = ["create", "outline", "approve_outline", "narration", "approve_narration", "voice", "picks", "approve_picks", "storyboard", "approve_storyboard", "export"]
        for name in order[:order.index(upto) + 1]:
            getattr(self, name)()
        return self

    def tree(self) -> dict[str, int]:
        """{relative path: size} of every file of this project's output folder."""
        base = self.out / self.key
        return {p.relative_to(base).as_posix(): p.stat().st_size for p in sorted(base.rglob("*")) if p.is_file()}

    def state(self) -> dict:
        return json.loads((self.out / self.key / "state.json").read_text(encoding="utf-8"))

    def text(self, rel: str) -> str:
        return (self.out / self.key / rel).read_text(encoding="utf-8")


def export_world(proj, monkeypatch, fail_t0=None, real_timeline=False):
    """The real export job with the fake tools of tests/export, on a fixture project (`.root`, `.d`, `.out`, `.duration`); the app registered its output folder."""
    import sys
    sys.path.insert(0, str(REPO / "tests" / "export"))
    import fakelongjob
    from bti.output import hooks, publish
    from bti.export import render, run
    from bti.export.settings import Settings
    FAKE = str(REPO / "tests" / "export" / "fake_tools.py")
    log = proj.root.parent / "fake.log"
    env = {"FAKE_LOG": str(log)}
    if fail_t0 is not None:
        env["FAKE_FAIL_T0"] = fail_t0
    tools = render.Tools(ffmpeg=[sys.executable, FAKE, "ffmpeg"], ffprobe=[sys.executable, FAKE, "ffprobe"],
                         engine=lambda project_dir, spec, out, settings: [sys.executable, FAKE, "engine", "render", str(project_dir), "--t0", "%.6f" % spec.t0, "--t1", "%.6f" % spec.t1,
                                                                          "--fps", str(spec.fps), "-o", str(out)], cwd=proj.root.parent, env=env)
    mgr = fakelongjob.FakeManager()
    monkeypatch.setattr(run, "get_manager", lambda: mgr)
    monkeypatch.setattr(run, "_part_cls", lambda pc: fakelongjob.Part)
    monkeypatch.setattr(run.render.Tools, "from_settings", classmethod(lambda cls, s: tools))
    sb = lambda: json.loads((proj.d / "storyboard.json").read_text(encoding="utf-8"))          # noqa: E731
    if not real_timeline:               # the fixture's shots start at plain seconds; with real_timeline the engine resolves the word anchors of its project
        monkeypatch.setattr(run, "engine_timeline", lambda d, rev: (sorted(float(s["start"]["t"]) for s in sb()["shots"]), float(sb()["end"]["t"])))
    monkeypatch.setattr(publish, "_ffmpeg", lambda t: (list(tools.ffmpeg), tools.env))
    (proj.d / "audio").mkdir(exist_ok=True)
    (proj.d / "audio" / "mix.m4a").write_text(json.dumps({"kind": "audio", "codec": "aac", "duration": getattr(proj, 'duration', 30.0)}), encoding="utf-8")
    hooks.register(proj.root, proj.out)
    return run, Settings(render_threads=2, part_seconds=60.0, render_speed=2.0), tools
