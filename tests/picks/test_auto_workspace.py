"""The agent's work folders (plan and choose), their helper commands (`check`, `crop`), the contact sheets and the briefings."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from auto_helpers import CHOICE, PLAN, FakeAgent, default_sources, fake_thumb, install_sources, make_auto_project, plan

from bti.picks import doc
from bti.picks.auto import images, inputs as ainputs, job, search as asearch, shapes, store, workspace

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def pdir(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    return make_auto_project(root)


def load(pdir, **kw):
    return ainputs.load(pdir, **kw)


def build(pdir, tmp_path, name="ws", **kw):
    inp = load(pdir, **kw)
    return inp, workspace.build_plan(inp, job.PLAN_LIMITS, root=tmp_path / name)


def helper(ws, *args):
    env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONUTF8="1")
    return subprocess.run([sys.executable, "-m", "bti.picks.auto.helper", *args], cwd=str(ws), env=env, capture_output=True, text=True, encoding="utf-8")


# ---------------------------------------------------------------------------------------------------------------- the plan folder
def test_the_plan_folder_has_the_inputs_the_briefing_names_and_copies_only(pdir, tmp_path):
    inp, ws = build(pdir, tmp_path)
    root = ws.root
    for f in ("TASK.md", "inputs/context.json", "inputs/narration.json", "inputs/facts.json", "inputs/dossier.json", "inputs/painting.json",
              "inputs/main_large.jpg", "images/main.jpg"):
        assert (root / f).is_file(), f
    assert (root / "out").is_dir() and (root / "look").is_dir()
    ext = ".cmd" if os.name == "nt" else ""
    for name in ("check", "crop"):
        w = (root / (name + ext)).read_text(encoding="utf-8")
        assert "bti.picks.auto.helper %s" % name in w and "PYTHONPATH" in w
    painting = json.loads((root / "inputs" / "painting.json").read_text(encoding="utf-8"))
    assert painting["source_size"] == [1300, 1250] and painting["image"] == "images/main.jpg" and painting["title"] == "The Test Painting"
    nar = json.loads((root / "inputs" / "narration.json").read_text(encoding="utf-8"))
    lines = [ln for c in nar["chapters"] for ln in c["lines"]]
    assert [ln["id"] for ln in lines] == ["b0001", "b0002", "b0003", "b0004", "b0005", "b0006"] and all(ln["target"] for ln in lines)
    assert [ln["no"] for ln in lines] == [1, 2, 3, 4, 5, 6] and lines[0]["words"] == len(lines[0]["text"].split()) > 40
    assert lines[0]["seconds"] == pytest.approx(lines[0]["words"] / 2.41, abs=0.06)
    assert json.loads((root / "inputs" / "facts.json").read_text(encoding="utf-8"))["f01"] == "The picture is dated 1434."
    ctx = json.loads((root / "inputs" / "context.json").read_text(encoding="utf-8"))
    assert ctx["mode"] == "plan" and ctx["plan"]["targets"] == [ln["id"] for ln in lines] and ctx["plan"]["existing_regions"] == {}
    assert not (root / "media").exists() and not (root / "picks.json").exists()                        # the project is not in it
    assert all(str(pdir) not in p.read_text(encoding="utf-8", errors="ignore") for p in root.rglob("*.json") if "inputs" in p.parts)


def test_lines_that_are_not_the_agents_say_what_they_already_have_and_existing_regions_are_boxes(pdir, tmp_path):
    from bti.ops import runner as ops_runner
    from bti.ops.adapters import PicksAdapter
    from bti.ops.log import ChangeLog
    d, rev = PicksAdapter(pdir).read()
    ops_runner.run_batch(PicksAdapter(pdir), {"base_rev": rev, "actor": "human", "ops": [
        {"op": "set_region", "asset": "A", "region": "HAND", "x": 650, "y": 625, "rx": 130, "ry": 125, "label": "Bàn tay"},
        {"op": "set_picks", "beat": "b0002", "items": [{"asset": "A", "region": "HAND"}]}, {"op": "skip_beat", "beat": "b0006"}]}, ChangeLog(pdir))
    inp, ws = build(pdir, tmp_path, owner_note="  Đoạn 3: thêm chân dung họa sĩ.  ")
    nar = json.loads((ws.root / "inputs" / "narration.json").read_text(encoding="utf-8"))
    lines = {ln["id"]: ln for c in nar["chapters"] for ln in c["lines"]}
    assert lines["b0002"]["target"] is False and lines["b0002"]["already"] == [{"asset": "A", "region": "HAND", "role": "detail"}]
    assert lines["b0006"]["target"] is False and lines["b0006"]["already"] == "needs no picture of its own" and lines["b0001"]["target"] is True
    painting = json.loads((ws.root / "inputs" / "painting.json").read_text(encoding="utf-8"))
    assert painting["regions"]["HAND"]["box"] == [0.4, 0.4, 0.6, 0.6] and painting["regions"]["HAND"]["label"] == "Bàn tay"
    ctx = json.loads((ws.root / "inputs" / "context.json").read_text(encoding="utf-8"))
    assert ctx["plan"]["targets"] == ["b0001", "b0003", "b0004", "b0005"] and ctx["plan"]["existing_regions"] == {"HAND": [0.4, 0.4, 0.6, 0.6]}
    task = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "Đoạn 3: thêm chân dung họa sĩ." in task and "The owner's request for these lines" in task
    assert "b0001, b0003, b0004, b0005" in task


def test_the_briefing_is_filled_in_and_says_what_a_good_choice_is(pdir, tmp_path):
    inp, ws = build(pdir, tmp_path)
    task = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "{{" not in task and "}}" not in task                                                      # every placeholder was filled
    assert "The owner's request" not in task                                                          # no note: the block is gone
    ext = ".cmd" if os.name == "nt" else ""
    check = ".\\check.cmd" if os.name == "nt" else "./check"
    assert check in task and "The Test Painting" in task and "A. Painter" in task and "**120 steps**" in task and "**30 minutes**" in task
    for rule in ("A line about the painting shows the part it speaks of", "A line about something outside the painting shows something other than the main painting",
                 "The same framing does not stay on screen for more than about half a minute", "Ask for the work itself, not for pictures about it",
                 "A map only when the line is about *where*", "Nothing invented", "at most one clip per chapter", "4 to 10 seconds"):
        assert rule in task, rule


def test_the_choose_briefing_says_what_a_good_choice_is(pdir, tmp_path):
    inp = load(pdir)
    search = {"wants": {}, "books": []}
    p = shapes.check_plan(plan(), inp.plan_ctx()).value
    ws, ctx = workspace.build_choose(inp, p, search, job.CHOOSE_LIMITS, books=[], root=tmp_path / "c")
    task = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "{{" not in task
    for rule in ("Does it show the thing itself?", "Prefer a public-domain reproduction of the named work", "over illustrations or pictures about it",
                 "Never pick a picture you are not sure shows what the line says", "Never use the main painting itself", "keep", "adjust", "drop",
                 "A flagged picture"):
        assert rule in task, rule


# ---------------------------------------------------------------------------------------------------------------- the helper commands
def test_check_says_what_is_wrong_in_plain_sentences_and_passes_a_good_plan(pdir, tmp_path):
    inp, ws = build(pdir, tmp_path)
    r = helper(ws.root, "check")
    assert r.returncode == 1 and "ERROR out/plan.json is missing" in r.stdout and "1 error(s)" in r.stdout
    (ws.root / "out" / "plan.json").write_text(json.dumps(plan(regions=[{"name": "MIRROR", "box": [0.4, 0.3, 1.5, 0.6], "what": "Gương"}, PLAN["regions"][1]])), encoding="utf-8")
    r = helper(ws.root, "check")
    assert r.returncode == 1 and "ERROR regions[0] (MIRROR): box [0.4, 0.3, 1.5, 0.6] lies outside the painting" in r.stdout
    (ws.root / "out" / "plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
    r = helper(ws.root, "check")
    assert r.returncode == 0 and r.stdout.strip().endswith("0 error(s), 0 note(s), 1 warning(s)") and "WARNING lines b0005 to b0006" in r.stdout
    # the same function the session uses
    from bti.picks.auto import helper as h
    assert h.run_check(ws.root).ok and h.run_check(ws.root).problems() is None


def test_crop_writes_inside_look_and_says_which_pixels(pdir, tmp_path):
    inp, ws = build(pdir, tmp_path)
    r = helper(ws.root, "crop", "--box", "0.1,0.2,0.4,0.6", "-o", "look/head.jpg")
    assert r.returncode == 0 and "wrote look/head.jpg" in r.stdout and "pixels 130 to 520 by 250 to 750 of the 1300 x 1250 painting" in r.stdout
    im = images.read(ws.root / "look" / "head.jpg")
    assert (im.shape[1], im.shape[0]) == (390, 500)
    r = helper(ws.root, "crop", "--grid", "-o", "look/grid.jpg")
    assert r.returncode == 0 and (ws.root / "look" / "grid.jpg").is_file()
    r = helper(ws.root, "crop", "--box", "0.1 0.2 0.4 0.6", "-o", "look/b.jpg", "--width", "100")
    assert r.returncode == 0 and max(images.read(ws.root / "look" / "b.jpg").shape[:2]) == 100


@pytest.mark.parametrize("args,part", [
    (["--box", "0.1,0.2,0.4,0.6", "-o", "../x.jpg"], "outside the workspace"),
    (["--box", "0.1,0.2,0.4,0.6", "-o", "out/x.jpg"], "inside look/"),
    (["--box", "0.1,0.2,0.4,0.6", "-o", "/tmp/x.jpg"], "outside the workspace"),
    (["--box", "0.1,0.2,1.7,0.6", "-o", "look/x.jpg"], "outside the painting"),
    (["--box", "a,b,c,d", "-o", "look/x.jpg"], "four numbers"),
    (["-o", "look/x.jpg"], "give --box"),
])
def test_crop_refuses_what_it_should(pdir, tmp_path, args, part):
    inp, ws = build(pdir, tmp_path)
    r = helper(ws.root, "crop", *args)
    assert r.returncode == 2 and part in (r.stdout + r.stderr)
    assert not (tmp_path / "x.jpg").exists() and not (ws.root / "look" / "x.jpg").exists()


def test_a_folder_that_is_not_a_work_folder_is_refused(tmp_path):
    r = helper(tmp_path, "check")
    assert r.returncode != 0 and "not a picks work folder" in (r.stdout + r.stderr)


# ---------------------------------------------------------------------------------------------------------------- the choose folder
def search_state(pdir, wants, **by_id):
    st = asearch.new_state()
    for w in wants:
        st["wants"][w["id"]] = asearch._new_want(w)
    for wid, cands in by_id.items():
        wid = wid.replace("_", ".", 1)
        st["wants"][wid]["candidates"] = cands
        st["wants"][wid]["status"] = "found"
    return st


def cand(pdir, n, sid, **kw):
    t = fake_thumb(pdir, {"source": "commons", "source_id": sid})
    return {"n": n, "source": "commons", "source_id": sid, "title": "T " + sid, "author": "Au", "licence": "CC0", "flag": None, "width": 1300, "height": 1250,
            "page_url": "https://x/" + sid, "media": "image", "thumb": t, **kw}


def test_the_choose_folder_has_a_numbered_sheet_per_want_a_crop_per_box_and_the_books(pdir, tmp_path):
    inp = load(pdir)
    p = shapes.check_plan(PLAN, inp.plan_ctx()).value
    wants = shapes.wants_of(p)
    st = search_state(pdir, wants, b0003_1=[cand(pdir, 1, "a"), cand(pdir, 2, "b"), cand(pdir, 3, "c", thumb=None)],
                      b0004_1=[{**cand(pdir, 1, "m"), "thumb": None, "media": "image", "title": "Bản đồ Bruges"}])
    books = [{"n": 1, "label": "Payne, ảnh trang 23", "source_id": "payne_gae/img/850", "thumb": pdir / fake_thumb(pdir, {"source": "book", "source_id": "payne_gae/img/850"})},
             {"n": 2, "label": "Payne, ảnh trang 24", "source_id": "payne_gae/img/851", "thumb": None}]
    ws, cctx = workspace.build_choose(inp, p, st, job.CHOOSE_LIMITS, books=books, root=tmp_path / "c")
    root = ws.root
    assert cctx.wants == {"b0003.1": 3, "b0004.1": 1} and cctx.books == 2 and cctx.regions == ["MIRROR", "HEAD"]
    w = json.loads((root / "inputs" / "wants.json").read_text(encoding="utf-8"))
    by = {x["id"]: x for x in w["wants"]}
    assert set(by) == {"b0003.1", "b0004.1"} and by["b0003.1"]["sheet"] == "images/w_b0003_1.jpg" and by["b0004.1"]["sheet"] is None            # a map has no sheet
    assert [c["n"] for c in by["b0003.1"]["candidates"]] == [1, 2, 3] and by["b0003.1"]["line_text"].startswith("Word") and by["b0003.1"]["what"] == "Chân dung họa sĩ"
    assert by["b0004.1"]["candidates"][0]["title"] == "Bản đồ Bruges"
    assert w["books"]["pictures"] == [{"n": "B1", "label": "Payne, ảnh trang 23"}, {"n": "B2", "label": "Payne, ảnh trang 24"}] and w["books"]["sheets"] == ["images/books_1.jpg"]
    from PIL import Image
    with Image.open(root / "images" / "w_b0003_1.jpg") as sheet:
        assert sheet.size == (3 * 460 + 4 * 8, 340 + 2 * 8)                     # three tiles in one row
    with Image.open(root / "images" / "books_1.jpg") as sheet:
        assert sheet.size == (2 * 460 + 3 * 8, 340 + 2 * 8)
    regs = json.loads((root / "inputs" / "regions.json").read_text(encoding="utf-8"))["regions"]
    assert [r["name"] for r in regs] == ["MIRROR", "HEAD"] and regs[0]["lines"] == ["b0002"] and regs[1]["lines"] == ["b0005"] and regs[0]["crop"] == "images/d_MIRROR.jpg"
    im = images.read(root / "images" / "d_MIRROR.jpg")
    assert (im.shape[1], im.shape[0]) == (260, 313)                              # 0.2 x 0.25 of 1300 x 1250 (the box is exactly what the camera shows)
    task = (root / "TASK.md").read_text(encoding="utf-8")
    assert "{{" not in task and "b0003.1, b0004.1" in task and "**2**" in task
    context = json.loads((root / "inputs" / "context.json").read_text(encoding="utf-8"))
    assert context["mode"] == "choose" and context["choice"] == {"wants": {"b0003.1": 3, "b0004.1": 1}, "books": 2, "regions": ["MIRROR", "HEAD"]}
    # the same check the agent runs
    (root / "out" / "choice.json").write_text(json.dumps(CHOICE), encoding="utf-8")
    r = helper(root, "check")
    assert r.returncode == 1 and "no such wanted picture" in r.stdout                      # CHOICE answers b0004.2, which this folder does not have
    (root / "out" / "choice.json").write_text(json.dumps(FakeAgent.fit(CHOICE, root, "choose")), encoding="utf-8")
    assert helper(root, "check").returncode == 0


def test_a_contact_sheet_survives_a_thumbnail_that_does_not_open(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not a picture")
    images.contact_sheet([("1", None), ("2", bad)], tmp_path / "s.jpg")
    from PIL import Image
    with Image.open(tmp_path / "s.jpg") as sheet:
        assert sheet.size[0] == 2 * 460 + 3 * 8
    with pytest.raises(images.ImageError):
        images.contact_sheet([], tmp_path / "e.jpg")


def test_the_main_painting_must_be_readable(pdir, tmp_path, monkeypatch):
    inp = load(pdir)

    def broken(*a, **k):
        raise images.ImageError("cannot be read")
    monkeypatch.setattr(images, "save_scaled", broken)
    with pytest.raises(workspace.WorkspaceError) as e:
        workspace.build_plan(inp, job.PLAN_LIMITS, root=tmp_path / "ws")
    assert e.value.code == "main_asset_unreadable"
    (pdir / "media" / "main.png").unlink()
    with pytest.raises(ainputs.AutoError) as e:
        load(pdir)
    assert e.value.code == "main_asset_unreadable"


def test_old_work_folders_of_this_job_are_cleaned_and_nothing_else(tmp_path, monkeypatch):
    import tempfile
    import time
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    old, other = tmp_path / (workspace.PREFIX + "old"), tmp_path / "keep-me"
    new = tmp_path / (workspace.PREFIX + "new")
    for d in (old, other, new):
        d.mkdir()
    t = time.time() - 3 * 86400
    os.utime(old, (t, t))
    os.utime(other, (t, t))
    assert workspace.clean_old() == 1 and not old.exists() and other.exists() and new.exists()


# ---------------------------------------------------------------------------------------------------------------- websearch: what the choosing session reads, and its second look
def test_each_candidate_shows_its_page_title_its_site_and_its_snippet_and_the_session_sees_at_most_eight(pdir, tmp_path):
    inp = load(pdir)
    p = shapes.check_plan(PLAN, inp.plan_ctx()).value
    wants = shapes.wants_of(p)
    many = [cand(pdir, n, "w%d" % n, via="wikipedia", page_title="Noyon Cathedral", site="Wikipedia", snippet="Cathedral in France") for n in range(1, 8)]
    many += [cand(pdir, 8, "web8", source="web", page_title="A museum page", site="museum.example.org", snippet="A portrait of the duke", flag="unknown", licence=""),
             cand(pdir, 9, "tooMany"), cand(pdir, 10, "tooMany2")]
    st = search_state(pdir, wants, b0003_1=many)
    st["wants"]["b0003.1"].update({"entity": "Philip the Good", "period": "then"})
    ws, cctx = workspace.build_choose(inp, p, st, job.CHOOSE_LIMITS, books=[], root=tmp_path / "c")
    assert cctx.wants == {"b0003.1": 8}                                                         # the numbers the session may answer are 1..8
    row = json.loads((ws.root / "inputs" / "wants.json").read_text(encoding="utf-8"))["wants"][0]
    assert [c["n"] for c in row["candidates"]] == list(range(1, 9))
    assert row["candidates"][0]["page_title"] == "Noyon Cathedral" and row["candidates"][0]["site"] == "Wikipedia" and row["candidates"][0]["snippet"] == "Cathedral in France"
    assert row["candidates"][7]["site"] == "museum.example.org" and row["candidates"][7]["snippet"] == "A portrait of the duke" and row["candidates"][7]["flag"] == "unknown"
    assert row["entity"] == "Philip the Good" and row["period"] == "then" and "first_look" not in row and isinstance(row.get("kinds", []), list) and not row.get("places")      # the plan's kinds travel with the want
    plain = cand(pdir, 1, "plain")
    st2 = search_state(pdir, wants, b0003_1=[plain])
    ws2, _ = workspace.build_choose(inp, p, st2, job.CHOOSE_LIMITS, books=[], root=tmp_path / "c2")
    r2 = json.loads((ws2.root / "inputs" / "wants.json").read_text(encoding="utf-8"))["wants"][0]
    assert set(r2["candidates"][0]) == {"n", "title", "source", "author", "licence", "flag", "width", "height", "page_url", "media"}          # a candidate without the page's words is shown as before


def test_the_choosing_briefing_has_the_new_rules_and_every_old_one(pdir, tmp_path):
    inp = load(pdir)
    p = shapes.check_plan(plan(), inp.plan_ctx()).value
    ws, _ = workspace.build_choose(inp, p, {"wants": {}, "books": []}, job.CHOOSE_LIMITS, books=[], root=tmp_path / "c")
    task = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "{{" not in task and "second look" not in task
    for rule in ("A line about the past wants a picture made in that period", "a painting, a drawing, a print, a manuscript page, a coin, a seal, an object in a museum",
                 "Prefer it to a modern photograph, a reconstruction, a film still", "A **photograph of today** is right when the want says `\"period\": \"now\"`",
                 "for a building or an object that survives", "or when nothing else shows the thing", "Never a watermarked picture", "Say in the reason what the picture is and from when",
                 "`page_title`", "`snippet`", "`entity`", "at most eight"):
        assert rule in task, rule


def test_the_second_look_folder_holds_only_the_new_candidates_no_boxes_and_what_was_said_before(pdir, tmp_path):
    inp = load(pdir)
    p = shapes.check_plan(PLAN, inp.plan_ctx()).value
    wants = shapes.wants_of(p)
    st = search_state(pdir, wants, b0003_1=[cand(pdir, 1, "new1", source="web", page_title="P", site="s.example.org"), cand(pdir, 2, "new2")])
    st["wants"]["b0003.1"]["earlier"] = "Cả sáu hình đều là người khác."
    ws, cctx = workspace.build_choose(inp, p, st, job.CHOOSE_LIMITS, books=[], root=tmp_path / "c", second=True)
    assert cctx.wants == {"b0003.1": 2} and cctx.regions == [] and cctx.books == 0
    task = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "{{" not in task and "This is a second look" in task and "ONLY the new candidates" in task and "`first_look`" in task
    row = json.loads((ws.root / "inputs" / "wants.json").read_text(encoding="utf-8"))["wants"][0]
    assert row["first_look"] == "Cả sáu hình đều là người khác." and json.loads((ws.root / "inputs" / "regions.json").read_text(encoding="utf-8"))["regions"] == []
    assert not list((ws.root / "images").glob("d_*.jpg")) and not list((ws.root / "images").glob("books_*"))
    # the same check the agent runs: only the wanted pictures, no boxes
    (ws.root / "out" / "choice.json").write_text(json.dumps({"wants": [{"id": "b0003.1", "pick": 2, "reason": "Ảnh chân dung vẽ thời đó."}], "regions": []}), encoding="utf-8")
    assert helper(ws.root, "check").returncode == 0


def test_the_row_of_a_want_carries_what_the_line_does_and_the_places_of_a_journey_when_the_plan_gave_them(pdir, tmp_path):
    inp = load(pdir)
    p = shapes.check_plan(PLAN, inp.plan_ctx()).value
    st = search_state(pdir, shapes.wants_of(p), b0003_1=[cand(pdir, 1, "a")])
    st["wants"]["b0003.1"].update({"kinds": ["outside"], "places": ["Lyon, France", "Lübeck, Germany"]})
    ws, _ = workspace.build_choose(inp, p, st, job.CHOOSE_LIMITS, books=[], root=tmp_path / "c")
    row = json.loads((ws.root / "inputs" / "wants.json").read_text(encoding="utf-8"))["wants"][0]
    assert row["kinds"] == ["outside"] and row["places"] == ["Lyon, France", "Lübeck, Germany"]
