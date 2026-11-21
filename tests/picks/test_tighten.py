"""End-to-end tests for the second-look tight-bounding-box pipeline and standalone `picks.tighten` (worker tightbox)."""
import copy
import io
import json
import tempfile
import time

import pytest
from auto_fixtures import paid  # noqa: F401
from auto_helpers import CHOICE, PLAN, FakeAgent, fake_book_thumb, fake_thumb, install_agent, install_sources, make_auto_project, plan
from fastapi.testclient import TestClient
from picks_helpers import mount
from PIL import Image

from bti import settings as S
from bti.editor.app import create_app
from bti.longjob import manager
from bti.output import sheets
from bti.picks import doc
from bti.picks.auto import inputs as ainputs, search as asearch, shapes, tighten, tighten_job, workspace
from bti.script import env as env_mod, models as models_mod

BEATS = [{"id": "b%04d" % i, "chapter": "c%02d" % ((i + 1) // 2), "words": 40,
          "text": "The couple hold a pair of pattens and the joined hands beside the convex mirror."}
         for i in range(1, 7)]
IDS = [b["id"] for b in BEATS]


def _pctx(**kw):
    return shapes.PlanCtx(beats=BEATS, targets=list(IDS), existing_regions={}, line_texts={b["id"]: b["text"] for b in BEATS}, **kw)


def _png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------------------------------------------- 1. Plan: thing & MAX_REGIONS
def test_plan_thing_english_word_count_and_x_and_y_rules():
    assert shapes.MAX_REGIONS == 30
    # Valid thing (2..8 English words)
    assert shapes.clean_thing("carved woman standing on a dragon", "r")[0] == "carved woman standing on a dragon"
    # Vietnamese refused
    assert "thing_not_english" in shapes.clean_thing("tượng phụ nữ đứng trên rồng", "r")[1]
    # Word count < 2 or > 8 refused
    assert "thing_words" in shapes.clean_thing("mirror", "r")[1]
    assert "thing_words" in shapes.clean_thing("one two three four five six seven eight nine", "r")[1]
    # "X and Y" refused by default
    assert "thing_two_things" in shapes.clean_thing("mirror and candle", "r")[1]
    # Allowed exceptions: known single unit, colour/material adjectives, narration exact phrase
    assert shapes.clean_thing("cup and saucer", "r")[1] is None
    assert shapes.clean_thing("black and white tiles", "r")[1] is None
    assert shapes.clean_thing("the joined hands", "r")[1] is None
    assert shapes.clean_thing("pair of pattens and clasped hands", "r", line_texts=["the pair of pattens and clasped hands rests near the door"])[1] is None


def test_plan_allows_up_to_30_regions_and_refuses_31():
    beats = [{"id": "b%04d" % i, "chapter": "c%02d" % (i // 5 + 1), "words": 20} for i in range(1, 32)]
    targets = [b["id"] for b in beats]
    pctx = shapes.PlanCtx(beats=beats, targets=targets, existing_regions={})
    regs30 = [{"name": "R%02d" % i, "box": [0.05 + (i % 5) * 0.18, 0.05 + (i // 5) * 0.14, 0.15 + (i % 5) * 0.18, 0.13 + (i // 5) * 0.14],
               "what": "Vùng %d" % i, "thing": "carved detail number %d" % i} for i in range(1, 31)]
    lines30 = [{"beat": beats[i]["id"], "reason": "Chi tiết tranh.", "kinds": ["detail"],
                "show": [{"type": "detail", "region": regs30[min(i, 29)]["name"]}]} for i in range(31)]
    rep30 = shapes.check_plan({"schema": shapes.PLAN_SCHEMA, "regions": regs30, "lines": lines30}, pctx)
    assert rep30.ok, rep30.text()
    regs31 = regs30 + [{"name": "R31", "box": [0.80, 0.80, 0.90, 0.90], "what": "Vùng 31", "thing": "extra carved detail"}]
    lines31 = lines30[:-1] + [{"beat": beats[30]["id"], "reason": "Chi tiết.", "kinds": ["detail"], "show": [{"type": "detail", "region": "R31"}]}]
    rep31 = shapes.check_plan({"schema": shapes.PLAN_SCHEMA, "regions": regs31, "lines": lines31}, pctx)
    assert not rep31.ok and "at most 30" in rep31.text()


# ---------------------------------------------------------------------------------------------------------------- 2. Cutouts, full resolution & scale up/down
def test_cutout_cuts_from_full_resolution_scales_up_and_down_and_clamps_to_content_box(tmp_path):
    # High-res 4000x3000 painting with a black ground outside [200, 100, 3800, 2900] and a single bright 4x4 pixel marker inside a tiny spot
    im = Image.new("RGB", (4000, 3000), (0, 0, 0))
    canvas = Image.new("RGB", (3600, 2800), (60, 50, 45))
    im.paste(canvas, (200, 100))
    for dx in range(2400, 2406):
        for dy in range(1500, 1506):
            im.putpixel((dx, dy), (255, 40, 200))
    src = tmp_path / "full.png"
    im.save(src)

    # Small rough box: 60x60 -> +15% => 78x78, clamped inside surface, scaled UP to 1024x1024
    small_geom = tighten.cutout_geom([2370, 1470, 2430, 1530], (4000, 3000), {"x0": 200, "y0": 100, "x1": 3800, "y1": 2900})
    assert small_geom["cutout_size"] == [1024, 1024] and small_geom["scale"] > 10.0
    out_small = tmp_path / "small.jpg"
    tighten.render_cutout(src, small_geom, out_small, with_grid=False)
    with Image.open(out_small) as cm:
        assert cm.size == (1024, 1024)
        # Bright magenta 6x6 marker preserved at high saturation inside scaled-up full-res cutout
        cx, cy = [int(round(v)) for v in tighten.stored_to_cutout([2403, 1503, 2404, 1504], small_geom)[:2]]
        r, g, b = cm.getpixel((cx, cy))
        assert r > 200 and b > 150 and g < 80

    # Large rough box: 1800x1600 -> scaled DOWN to 1024 long side
    large_geom = tighten.cutout_geom([400, 400, 2200, 2000], (4000, 3000), {"x0": 200, "y0": 100, "x1": 3800, "y1": 2900})
    assert max(large_geom["cutout_size"]) == 1024 and large_geom["scale"] < 1.0

    # Overlap with ground clamped to content_box [200, 100, 3800, 2900]
    edge_geom = tighten.cutout_geom([120, 60, 420, 360], (4000, 3000), {"x0": 200, "y0": 100, "x1": 3800, "y1": 2900})
    assert edge_geom["crop_px"][0] == 200 and edge_geom["crop_px"][1] == 100

    # Verify workspace uses FULL resolution rather than 1568px images/main.jpg
    full_crop = tighten.cutout_to_stored([200, 200, 800, 800], large_geom)
    assert full_crop[2] > full_crop[0] and full_crop[3] > full_crop[1]


# ---------------------------------------------------------------------------------------------------------------- 3. Validation, wider, 6-per-sheet & confirmation
def test_second_look_refusals_wider_and_6_per_sheet_check(tmp_path):
    im = Image.new("RGB", (2000, 2000), (140, 120, 100))
    src = tmp_path / "inputs" / "main_full.jpg"
    src.parent.mkdir(parents=True)
    im.save(src, quality=92)
    cutouts = {}
    for i in range(1, 8):
        name = "R%d" % i
        geom = tighten.cutout_geom([100 * i, 100, 100 * i + 200, 300], (2000, 2000))
        cutouts[name] = {**geom, "name": name, "existing": False, "what": "Chi tiết %d" % i,
                         "thing": "detail item %d" % i, "full_image": "inputs/main_full.jpg"}

    # Out-of-cutout box refused; <8px stored refused; small-rough full-cutout box refused
    r1_cw, r1_ch = cutouts["R1"]["cutout_size"]
    for bad_box, code in (
        ([0, 0, r1_cw + 50, r1_ch], "box_outside_cutout"),
        ([10, 10, 15, 15], "box_too_small"),
        ([0, 0, r1_cw - 2, r1_ch - 2], "box_too_loose"),
    ):
        _, errs, _ = tighten.check_regions_response(
            [{"name": "R1", "action": "tight", "box": bad_box}]
            + [{"name": "R%d" % i, "action": "drop", "reason": "Không thấy chi tiết."} for i in range(2, 8)],
            cutouts, ws_root=tmp_path,
        )
        assert any(code in e for e in errs), (code, errs)

    # Asking wider produces +40% cut-out look/d_R1_wider.jpg, asking wider twice is refused
    _, errs, _ = tighten.check_regions_response(
        [{"name": "R1", "action": "wider", "reason": "Chi tiết bị cắt ở mép khung."}]
        + [{"name": "R%d" % i, "action": "tight", "box": [200, 200, 700, 700]} for i in range(2, 8)],
        cutouts, ws_root=tmp_path,
    )
    assert any("wider_ready" in e for e in errs) and (tmp_path / "look" / "d_R1_wider.jpg").is_file()
    _, errs2, _ = tighten.check_regions_response(
        [{"name": "R1", "action": "wider", "reason": "Thử rộng hơn nữa."}]
        + [{"name": "R%d" % i, "action": "tight", "box": [200, 200, 700, 700]} for i in range(2, 8)],
        cutouts, ws_root=tmp_path,
    )
    assert any("wider_already_used" in e for e in errs2)

    # First valid pass writes 2 check sheets (7 items -> 6 on check_1.jpg, 1 on check_2.jpg) and refuses premature confirmed=True
    pass1 = [{"name": "R1", "action": "tight", "box": [220, 220, 680, 680], "confirmed": True}] + [
        {"name": "R%d" % i, "action": "tight", "box": [200, 200, 700, 700]} for i in range(2, 8)
    ]
    _, errs3, _ = tighten.check_regions_response(pass1, cutouts, ws_root=tmp_path)
    assert any("check_sheet_ready" in e for e in errs3)
    assert (tmp_path / "look" / "check_1.jpg").is_file() and (tmp_path / "look" / "check_2.jpg").is_file()

    # Unconfirmed fail-safe returns confirmed=False when allow_unconfirmed=True
    unconf, errs_u, _ = tighten.check_regions_response(
        [{"name": "R1", "action": "tight", "box": [220, 220, 680, 680], "confirmed": True}]
        + [{"name": "R%d" % i, "action": "tight", "box": [200, 200, 700, 700]} for i in range(2, 8)],
        cutouts, ws_root=tmp_path, allow_unconfirmed=True,
    )
    assert errs_u == [] and unconf["R1"]["confirmed"] is True and all(unconf["R%d" % i]["confirmed"] is False for i in range(2, 8))

    # One-time correction with confirmed=True succeeds; second correction is refused
    corr = [{"name": "R1", "action": "tight", "box": [240, 240, 690, 690], "confirmed": True}] + [
        {"name": "R%d" % i, "action": "tight", "box": [200, 200, 700, 700], "confirmed": True} for i in range(2, 8)
    ]
    res_ok, errs4, _ = tighten.check_regions_response(corr, cutouts, ws_root=tmp_path)
    assert errs4 == [] and res_ok["R1"]["confirmed"] is True and res_ok["R1"]["wider"] is True

    corr2 = [{"name": "R1", "action": "tight", "box": [260, 260, 700, 700], "confirmed": True}] + corr[1:]
    _, errs5, _ = tighten.check_regions_response(corr2, cutouts, ws_root=tmp_path)
    assert any("correction_limit" in e for e in errs5)


def test_unconfirmed_regions_never_store_tight_true(tmp_path):
    from auto_helpers import choice
    root = tmp_path / "projects"
    root.mkdir()
    pdir = make_auto_project(root)
    with pytest.MonkeyPatch.context() as mp:
        install_sources(mp)
        agent = install_agent(mp, FakeAgent(choice=choice(regions=[
            {"name": "MIRROR", "action": "tight", "box": [120, 130, 735, 890], "reason": "Chưa xác nhận."},
            {"name": "HEAD", "action": "tight", "box": [110, 110, 900, 860], "reason": "Chưa xác nhận."},
        ])))
        manager.configure(projects_root=root)
        mp.setattr("tempfile.tempdir", str(tmp_path / "work"))
        (tmp_path / "work").mkdir()
        from bti.picks import auto
        rec = auto.start(pdir.name, pdir, fetch_thumb=fake_thumb, fetch_book_thumb=fake_book_thumb)
        job = manager.wait(rec["id"], 60)
        assert job["state"] == "done" and agent.calls
        regs = doc.load(pdir)["assets"]["A"]["regions"]
        assert set(regs) == {"MIRROR", "HEAD"}
        assert all(not r.get("tight") for r in regs.values())
        assert doc.non_tight_regions(doc.load(pdir)) == ["MIRROR", "HEAD"]


# ---------------------------------------------------------------------------------------------------------------- 4. Legacy, size repair & output sheet
def test_doc_compatibility_size_repair_scaling_rough_and_regions_sheet(tmp_path):
    # Legacy region hashes & saves without adding tight/thing/rough
    legacy = {"schema": doc.SCHEMA, "main_asset": "A",
              "assets": {"A": {"file": "media/a.png", "kind": "image", "title": "A", "artist": "", "year": "", "width": 4000, "height": 2000,
                               "credit": {"source": "commons", "source_url": "u", "author": "x", "licence": "PD", "flag": None},
                               "regions": {"OLD": {"x": 2000, "y": 1000, "rx": 400, "ry": 200, "label": "Cũ"}},
                               "content_box": {"x0": 0, "y0": 0, "x1": 4000, "y1": 2000, "how": "whole"}}},
              "beats": {}, "approval": {"approved": False}}
    norm = doc.normalize(copy.deepcopy(legacy))
    assert norm["assets"]["A"]["regions"]["OLD"] == {"x": 2000, "y": 1000, "rx": 400, "ry": 200, "label": "Cũ"}
    assert doc.non_tight_regions(norm) == ["OLD"]

    # Size repair scales `rough` along with `x, y, rx, ry`
    pdir = tmp_path / "proj_repair"
    (pdir / "media").mkdir(parents=True)
    Image.new("RGB", (400, 200), (100, 90, 80)).save(pdir / "media" / "a.png")
    legacy["assets"]["A"]["regions"]["TIGHT"] = {
        "x": 2000, "y": 1000, "rx": 100, "ry": 50, "label": "Khít",
        "tight": True, "thing": "carved saint", "rough": [1600, 800, 2400, 1200],
    }
    (pdir / "picks.json").write_text(json.dumps(legacy), encoding="utf-8")
    loaded = doc.load(pdir)
    tr = loaded["assets"]["A"]["regions"]["TIGHT"]
    assert tr["x"] == 200 and tr["rx"] == 10 and tr["rough"] == [160, 80, 240, 120] and doc.non_tight_regions(loaded) == ["OLD"]

    # Output regions sheet draws tight + legacy regions cleanly
    out_sheet = tmp_path / "regions_sheet.jpg"
    cnt = sheets.regions_sheet(pdir / "media" / "a.png", loaded["assets"]["A"]["regions"], out_sheet, "Test")
    assert cnt == 2 and out_sheet.is_file()


# ---------------------------------------------------------------------------------------------------------------- 5. Existing non-tight region tightened during picks.auto
def test_picks_auto_tightens_existing_non_tight_region_in_place(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    root.mkdir()
    pdir = make_auto_project(root)
    with doc.Held(pdir):
        pd = doc.load(pdir)
        pd["assets"]["A"]["regions"]["MIRROR"] = {"x": 650, "y": 530, "rx": 180, "ry": 190, "label": "Tấm gương lồi"}
        doc.save(pdir, pd)
    p = plan(regions=[PLAN["regions"][1]])  # MIRROR already exists -> NOT in plan["regions"], used by b0002 -> still tightened in place!
    install_sources(monkeypatch)
    install_agent(monkeypatch, FakeAgent(plan=p))
    manager.configure(projects_root=root)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path / "work"))
    (tmp_path / "work").mkdir()
    from bti.picks import auto
    rec = auto.start(pdir.name, pdir, fetch_thumb=fake_thumb, fetch_book_thumb=fake_book_thumb)
    job = manager.wait(rec["id"], 60)
    assert job["state"] == "done", job.get("error")
    mir = doc.load(pdir)["assets"]["A"]["regions"]["MIRROR"]
    assert mir["tight"] is True and mir["rx"] < 180 and mir["ry"] < 190
    assert doc.non_tight_regions(doc.load(pdir)) == []


# ---------------------------------------------------------------------------------------------------------------- 6. Standalone picks.tighten API & job
@pytest.fixture
def t_api(tmp_path, monkeypatch, paid):
    monkeypatch.setenv("BTI_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setenv("BTI_AGY_BIN", "")
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    (tmp_path / "run").mkdir()
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(tmp_path / "run" / "settings.json"))
    (tmp_path / "agents.json").write_text(json.dumps({r: "mock" for r in S.ROLES}), encoding="utf-8")
    monkeypatch.setenv("BTI_AGENTS_FILE", str(tmp_path / "agents.json"))
    mock = {"default": "gem", "agents": [{"id": "gem", "label": "Gemini giả", "model": "mock"}],
            "steps": {"script": ["script.outline", "script.narration"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"]}}
    (tmp_path / "choices.json").write_text(json.dumps(mock), encoding="utf-8")
    monkeypatch.setenv("BTI_AGENT_CHOICES_FILE", str(tmp_path / "choices.json"))
    models_mod.reset_cache()
    env_mod._cache.clear()
    root = tmp_path / "projects"
    root.mkdir()
    pdir = make_auto_project(root)
    with doc.Held(pdir):
        pd = doc.load(pdir)
        pd["assets"]["A"]["regions"] = {
            "MIRROR": {"x": 650, "y": 530, "rx": 180, "ry": 190, "label": "Tấm gương lồi"},
            "HEAD": {"x": 260, "y": 190, "rx": 170, "ry": 170, "label": "Khuôn mặt", "tight": True, "thing": "man's face", "rough": [90, 20, 430, 360]},
            "UNUSED_DROP": {"x": 900, "y": 900, "rx": 80, "ry": 80, "label": "Vùng thừa"},
        }
        pd["beats"] = {
            "b0001": {"items": [{"asset": "A", "region": None, "role": "main", "note": "Giữ nguyên."}], "status": "picked", "note": "Mở đầu."},
            "b0002": {"items": [{"asset": "A", "region": "MIRROR", "role": "detail", "note": "Gương."}], "status": "picked", "note": "Chi tiết gương."},
        }
        doc.save(pdir, pd)
    nv = json.loads((pdir / "script" / "narration.json").read_text(encoding="utf-8"))
    from bti.picks import context
    nrev = context.narration_view(pdir)["rev"]
    with doc.Held(pdir):
        doc.stamp_approval(pdir, doc.revision(doc.load(pdir)), nrev)

    (tmp_path / "work").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "work"))
    install_sources(monkeypatch)
    agent = install_agent(monkeypatch, FakeAgent(tighten={
        "schema": tighten.TIGHTEN_SCHEMA,
        "regions": [
            {"name": "MIRROR", "action": "tight", "box": [180, 180, 680, 820], "confirmed": True, "thing": "convex mirror on back wall", "reason": "Khung sát gương."},
            {"name": "UNUSED_DROP", "action": "drop", "reason": "Không thấy chi tiết này."},
        ],
    }))
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    mount(app)
    with TestClient(app, raise_server_exceptions=False) as c:
        c.root, c.pdir, c.pid, c.agent = root, pdir, pdir.name, agent
        c.u = "/api/projects/%s/picks/tighten" % pdir.name
        yield c
    assert paid == []


def test_picks_tighten_updates_regions_only_drops_approval_and_is_undoable(t_api):
    ov = t_api.get(t_api.u).json()
    assert ov["non_tight"] == ["MIRROR", "UNUSED_DROP"] and ov["running"] is None

    before_beats = copy.deepcopy(doc.load(t_api.pdir)["beats"])
    r = t_api.post(t_api.u, json={})
    assert r.status_code == 200, r.text
    assert r.json()["regions"] == 2
    jid = r.json()["job_id"]
    end = time.time() + 30
    while time.time() < end:
        j = t_api.get("/api/longjobs/" + jid).json()
        if j["state"] in ("done", "error", "cancelled"):
            break
        time.sleep(0.05)
    assert j["state"] == "done", j.get("error")
    assert j["result"]["tightened"] == ["MIRROR"] and j["result"]["dropped"] == ["UNUSED_DROP"]
    pd = doc.load(t_api.pdir)
    assert pd["beats"] == before_beats                                  # chosen beat pictures & notes untouched
    assert pd["approval"]["approved"] is False                          # approval dropped as by every edit
    assert "UNUSED_DROP" not in pd["assets"]["A"]["regions"]
    assert pd["assets"]["A"]["regions"]["MIRROR"]["tight"] is True and pd["assets"]["A"]["regions"]["MIRROR"]["thing"] == "convex mirror on back wall"
    assert doc.non_tight_regions(pd) == []
    # Now nothing non-tight remains -> HTTP 409 tighten_nothing_to_do
    r2 = t_api.post(t_api.u, json={})
    assert r2.status_code == 409 and r2.json()["code"] == "tighten_nothing_to_do"

    # Undo restores original MIRROR & UNUSED_DROP
    rev = doc.revision(pd)
    batch = j["result"]["batches"][0]
    u = t_api.post("/api/projects/%s/changes/%s/undo" % (t_api.pid, batch), json={"base_rev": rev, "actor": "human"})
    assert u.status_code == 200
    after_undo = doc.load(t_api.pdir)["assets"]["A"]["regions"]
    assert "UNUSED_DROP" in after_undo and "tight" not in after_undo["MIRROR"]


def test_picks_tighten_failure_writes_nothing_and_dropped_in_use_stays(t_api):
    # Used region returned as `drop` stays in place (`dropped_in_use`)
    t_api.agent.tighten = {
        "schema": tighten.TIGHTEN_SCHEMA,
        "regions": [
            {"name": "MIRROR", "action": "drop", "reason": "Không thấy gương."},
            {"name": "UNUSED_DROP", "action": "tight", "box": [180, 180, 680, 820], "confirmed": True, "reason": "Sát chi tiết."},
        ],
    }
    r = t_api.post(t_api.u, json={})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    while True:
        j = t_api.get("/api/longjobs/" + jid).json()
        if j["state"] in ("done", "error", "cancelled"):
            break
        time.sleep(0.05)
    assert j["state"] == "done" and j["result"]["dropped_in_use"] == ["MIRROR"]
    assert "MIRROR" in doc.load(t_api.pdir)["assets"]["A"]["regions"] and "tight" not in doc.load(t_api.pdir)["assets"]["A"]["regions"]["MIRROR"]

    # Agent error leaves MIRROR unchanged
    t_api.agent.status = "error"
    t_api.agent.error_code = "agy_rate_limit"
    r2 = t_api.post(t_api.u, json={"regions": ["MIRROR"]})
    assert r2.status_code == 200
    jid2 = r2.json()["job_id"]
    while True:
        j2 = t_api.get("/api/longjobs/" + jid2).json()
        if j2["state"] in ("done", "error", "cancelled"):
            break
        time.sleep(0.05)
    assert j2["state"] == "error" and "MIRROR" in doc.non_tight_regions(doc.load(t_api.pdir))
