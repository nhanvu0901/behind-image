"""The two silences a project may set for itself (worker introflow): `lead` before the first word and `title` that holds the channel-name beat.

A project without its own values keeps `silence.lead` and `silence.title` of config/voice.json exactly as before (its voice state, its timing and its
`assemble_sig` do not change); a change of either makes the voice stale with the existing reason `mix_settings_changed`, and a run with scope `changed`
assembles and aligns again without speaking any sentence again. Fake voice, even aligner, in-process long-job manager: no model, no GPU."""
import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bti.editor.common import ApiError
from bti.editor.voice_api import make_router
from bti.longjob.config import ServerConfig
from bti.longjob.fakes import FakeProbes
from bti.longjob.heavy import HeavySlot
from bti.longjob.manager import LongJobManager
from bti.voice import describe, files, run as voice_run
from bti.voice.config import load_voice_config, silence_settings, silenced
from bti.voice.plan import make_plan
from conftest import needs_ffmpeg, write_project


def _plan(project, cfg):
    return make_plan(project, cfg=cfg, provider="fake")


def _gaps(plan):
    return {c.gap_kind: c.gap for c in plan.chunks if c.gap_kind in ("lead", "title")}


def _old_assemble_sig(plan, cfg):
    """The signature as it was computed before a project could choose its silences: only the config's own numbers go in (an independent copy of the formula)."""
    struct = [[c.id, c.beat, c.chapter, round(c.gap, 3), len(c.written)] for c in plan.chunks]
    chapters = [[c.id, c.title, bool(c.card)] for c in plan.narration.chapters]
    doc = {"chunks": struct, "chapters": chapters, "tempo": plan.settings["tempo"], "pad": plan.settings["pad"], "padcfg": cfg["pad"],
           "tail": cfg["silence"]["tail"], "fade": cfg["fade_ms"], "loud": cfg["loudness"], "aac": cfg["aac_bitrate"]}
    return hashlib.sha1(json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------------------- what is in force
def test_the_config_has_the_new_opening_block_and_a_project_without_values_keeps_the_old_silences(cfg):
    assert cfg["intro"] == {"lead": 2.0, "title": 10.2}
    s = silence_settings({}, cfg)
    assert (s["lead"], s["title"], s["own"]) == (0.35, 6.2, {"lead": False, "title": False}) and s["intro"] == {"lead": 2.0, "title": 10.2}
    assert silenced(cfg, {}) is cfg and silenced(cfg, {"tempo": 1.1}) is cfg              # nothing of its own: the very same config
    own = silence_settings({"lead": 2.0, "title": 10.2}, cfg)
    assert (own["lead"], own["title"], own["own"]) == (2.0, 10.2, {"lead": True, "title": True})
    for bad in ({"lead": 0.1}, {"lead": 16}, {"lead": True}, {"lead": "5"}, {"title": 2.9}, {"title": 31}, {"title": float("nan")}):
        assert not any(silence_settings(bad, cfg)["own"].values()), bad                    # a value out of its range is ignored


def test_a_project_without_its_own_silences_has_the_old_gaps_and_the_old_signature(project, cfg):
    plan = _plan(project, cfg)
    assert _gaps(plan) == {"lead": 0.35, "title": 6.2 + 3.2}
    assert plan.assemble_sig == _old_assemble_sig(plan, cfg)               # nothing new went into the signature: a manifest built before is still current


def test_its_own_values_are_the_gaps_and_change_the_signature(project, cfg):
    before = _plan(project, cfg)
    files.write_settings(project, {"lead": 5.0, "title": 10.2})
    plan = _plan(project, cfg)
    assert _gaps(plan) == {"lead": 5.0, "title": 10.2 + 3.2}
    assert plan.assemble_sig != before.assemble_sig
    assert [c.id for c in plan.chunks] == [c.id for c in before.chunks]    # the sentences themselves (their ids) are the same: nothing is spoken again


# ------------------------------------------------------------------------------------------------------------------ the route
@pytest.fixture()
def client(tmp_path, cfg):
    write_project(tmp_path, "vtest")
    mgr = LongJobManager(heavy=HeavySlot(ServerConfig(), probes=FakeProbes()))
    mgr.configure(projects_root=tmp_path)
    app = FastAPI()

    @app.exception_handler(ApiError)
    async def _e(_, e):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": e.detail, **e.extra}, status_code=e.status)

    app.include_router(make_router(tmp_path, cfg=cfg, server={}, provider="fake", manager=mgr))
    c = TestClient(app)
    c.root = tmp_path
    return c


def test_get_shows_the_values_in_force_and_whether_they_are_the_projects_own(client):
    s = client.get("/api/projects/vtest/voice").json()["silence"]
    assert (s["lead"], s["title"], s["own"]) == (0.35, 6.2, {"lead": False, "title": False})
    assert s["default"] == {"lead": 0.35, "title": 6.2} and s["intro"] == {"lead": 2.0, "title": 10.2} and s["range"] == {"lead": [0.2, 15.0], "title": [3.0, 30.0]}
    r = client.put("/api/projects/vtest/voice/settings", json={"lead": 2, "title": 10.2})
    assert r.status_code == 200
    s = r.json()["silence"]
    assert (s["lead"], s["title"], s["own"]) == (2.0, 10.2, {"lead": True, "title": True})
    assert r.json()["settings"] == {"tempo": 1.0, "pad": True}             # tempo and pad are exactly what they were
    assert files.read_settings(client.root / "vtest") == {"lead": 2.0, "title": 10.2}


def test_one_value_alone_and_null_takes_it_away(client):
    client.put("/api/projects/vtest/voice/settings", json={"lead": 5.0, "title": 10.2, "tempo": 1.1})
    s = client.put("/api/projects/vtest/voice/settings", json={"title": None}).json()["silence"]
    assert (s["lead"], s["title"], s["own"]) == (5.0, 6.2, {"lead": True, "title": False})
    s = client.put("/api/projects/vtest/voice/settings", json={"lead": None}).json()["silence"]
    assert (s["lead"], s["title"], s["own"]) == (0.35, 6.2, {"lead": False, "title": False})
    assert files.read_settings(client.root / "vtest") == {"tempo": 1.1}


@pytest.mark.parametrize("body,code", [({"lead": 0.1}, "bad_lead"), ({"lead": 15.5}, "bad_lead"), ({"lead": "5"}, "bad_lead"), ({"lead": True}, "bad_lead"),
                                       ({"title": 2.9}, "bad_title"), ({"title": 30.5}, "bad_title"), ({"title": [10]}, "bad_title")])
def test_values_out_of_their_range_are_refused_and_nothing_is_written(client, body, code):
    r = client.put("/api/projects/vtest/voice/settings", json={**body, "tempo": 1.1})
    assert r.status_code == 422 and r.json()["code"] == code
    assert files.read_settings(client.root / "vtest") == {}


def test_a_project_the_app_creates_gets_the_intro_silences(tmp_path, monkeypatch):
    """`create_project` writes `intro` of config/voice.json into the project's own voice settings."""
    from bti.library import projects as P
    d = tmp_path / "newproj"
    d.mkdir()
    P._write_intro_silences(d)
    assert files.read_settings(d) == {"lead": 2.0, "title": 10.2, "tempo": 1.1}


def test_an_old_project_keeps_its_own_lead_until_changed_through_settings_route(client):
    files.write_settings(client.root / "vtest", {"lead": 5.0, "title": 10.2})
    assert client.get("/api/projects/vtest/voice").json()["silence"]["lead"] == 5.0
    r = client.put("/api/projects/vtest/voice/settings", json={"lead": 2.0})
    assert r.status_code == 200 and r.json()["silence"]["lead"] == 2.0
    assert files.read_settings(client.root / "vtest") == {"lead": 2.0, "title": 10.2}


def test_create_project_itself_writes_them(tmp_path):
    """The real creation (a catalogue entry, a dossier): the folder has its own `lead` and `title`; a project made by hand has none."""
    from bti.library import projects
    try:
        p = projects.create_project(["payne_gae/002"], "intro-test", tmp_path)
    except projects.ProjectError as e:
        pytest.skip("no library data on this machine: %s" % e)
    d = tmp_path / p["id"]
    assert files.read_settings(d) == {"lead": 2.0, "title": 10.2, "tempo": 1.1}
    assert silence_settings(files.read_settings(d), load_voice_config())["own"] == {"lead": True, "title": True}


# ---------------------------------------------------------------------------------------------------- a run with the fake voice
@pytest.fixture()
def mgr(tmp_path):
    m = LongJobManager(heavy=HeavySlot(ServerConfig(), probes=FakeProbes()))
    m.configure(projects_root=tmp_path)
    return m


def go(project, mgr, cfg, **kw):
    job = voice_run.start(project, project.name, cfg=cfg, server={}, provider_name="fake", manager=mgr, **kw)
    return mgr.wait(job, 120)


def _timing(project):
    return json.loads(files.timing_path(project).read_text(encoding="utf-8"))


@needs_ffmpeg
def test_a_change_of_a_silence_is_a_mix_change_and_nothing_is_spoken_again(project, mgr, cfg):
    assert go(project, mgr, cfg)["state"] == "done"
    old = _timing(project)
    assert describe(project, cfg=cfg, server={}, provider_name="fake")["state"] == "done"
    wavs = {p.name: p.stat().st_mtime_ns for p in files.chunks_dir(project).glob("*.wav")}
    # (1) the manifest built before the change is still done for a project with no values of its own (its signature is the old one)
    m = files.read_manifest(project)
    assert m["plan"]["assemble_sig"] == _old_assemble_sig(_plan(project, cfg), cfg)
    # (2) the owner sets the two silences: only the mix and the timing are stale
    files.write_settings(project, {"lead": 5.0, "title": 10.2})
    d = describe(project, cfg=cfg, server={}, provider_name="fake")
    assert d["state"] == "stale" and d["reasons"] == ["mix_settings_changed"] and d["counts"]["changed"] == 0 and d["counts"]["missing"] == 0
    assert d["silence"]["lead"] == 5.0 and d["silence"]["own"] == {"lead": True, "title": True}
    rec = go(project, mgr, cfg)                                           # scope "changed"
    assert rec["state"] == "done", rec
    keys = [p["key"] for p in rec["parts"]]
    assert not [k for k in keys if k.startswith("synth")] and keys[:2] == ["assemble", "align"]          # no sentence is spoken again
    assert {p.name: p.stat().st_mtime_ns for p in files.chunks_dir(project).glob("*.wav")} == wavs          # the audio of every sentence is the very same file
    new = _timing(project)
    assert describe(project, cfg=cfg, server={}, provider_name="fake")["state"] == "done"
    # every word is later: the cold open by the difference of the leads, every later word by that and the difference of the title silences
    d1, d2 = 5.0 - 0.35, (5.0 - 0.35) + (10.2 - 6.2)
    first_chapter = {b["id"] for b in new["beats"] if b["chapter"] == new["chapters"][0]["id"]}
    shifted = []
    for ob, nb in zip(old["beats"], new["beats"]):
        want = d1 if ob["id"] in first_chapter else d2
        for w in range(ob["w0"], ob["w1"]):
            shifted.append((new["words"][w]["s"] - old["words"][w]["s"], want))
    assert shifted and all(abs(got - want) < 0.01 for got, want in shifted)
    c1, c2 = new["chapters"]
    assert abs(c1["lead"]["end"] - 5.0) < 0.01 and c1["lead"]["start"] == 0
    assert abs((c2["lead"]["end"] - c2["lead"]["start"]) - (10.2 + 3.2)) < 0.05
    assert abs((c2["title_end"] - c2["title_start"]) - 10.2) < 1e-6        # the timing file's beat length is the project's own silence
    assert abs(c2["card_end"] - c2["card_start"] - 2.8) < 1e-6
    assert abs(new["duration"] - (old["duration"] + d2)) < 0.01


@needs_ffmpeg
def test_taking_the_values_away_goes_back_to_the_old_timing(project, mgr, cfg):
    go(project, mgr, cfg)
    old = _timing(project)
    files.write_settings(project, {"lead": 5.0, "title": 10.2})
    go(project, mgr, cfg)
    files.write_settings(project, {})
    assert describe(project, cfg=cfg, server={}, provider_name="fake")["reasons"] == ["mix_settings_changed"]
    go(project, mgr, cfg)
    assert _timing(project)["words"] == old["words"]


def test_old_project_without_own_tempo_keeps_fallback(tmp_path):
    from bti.voice.config import project_settings
    assert project_settings(files.read_settings(tmp_path), load_voice_config())["tempo"] == 1.0
