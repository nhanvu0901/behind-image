"""Worker fixdraft (2026-11-19): a first storyboard draft that does not need twenty corrections.

What the two draft agents are told (the new rules are in both briefings), what they are given (only pictures that a line of the narration uses),
what the owner can add (`draft.start` takes a note), what comes back to the agent (the looks the owner rejects are sent back with the errors), and
the two small repairs (the progress line, the note of a shot that now shows something else). Fake agents only: no model is called."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from bti.draft import fastedit, boxops
from bti.draft import run as R
from bti.draft import workspace as W
from bti.draft.compile import compile_specs
from bti.draft.guard import Guard
from bti.draft.inputs import NOTE_MAX, DraftError, clone_inputs, line_assets, load_inputs
from bti.editor import draft_api
from bti.editor.common import ApiError
from bti.longjob import LongJobManager
from helpers import GOOD, clean_spec
from test_agy import fake  # noqa: F401  (the fake agy fixture)

REPO = Path(__file__).resolve().parents[2]
TASK = (REPO / "skills" / "storyboard_draft" / "TASK.template.md").read_text(encoding="utf-8")
FAST = (REPO / "skills" / "storyboard_edit" / "FAST.template.md").read_text(encoding="utf-8")

# every rule of the new briefings, by a phrase that carries its number or its condition
TASK_RULES = {
    "the frame is full": ["**The frame is full.**", "`zoom = 1920 / W`", "3840 px wide: 0.5", "under 0.6 of that (0.3)", "at most 5% of the running time (30 s in ten minutes)",
                          "the pull back that ends the cold open, ONE chapter opening and the last shot", "`zoom >= 0.6 x 1920 / W`", "`cx = W / 2`",
                          "Neighbouring shots never end and start on the same frame", "channel-name beat and each chapter mark", "start every chapter's first shot, on a filling frame"],
    "highlights": ["**Highlights are rare and stay lit.**", "at most one in two minutes, none in the first minute", "never when the camera already frames it closely",
                   "5% in from every edge", "`floor` / `surround_floor` 0.6 or more"],
    "text on the screen": ["**Text on the screen is true and tidy.**", "comes from the narration", "never a placeholder (\"Unknown author\")", "the word \"narration\"",
                           "the same words twice", "`region_label` `\"\"`", "`region_iso` `[]`", "`sea_names` `false`"],
    "the first half minute": ["**The first half minute is the painting.**", "before second 30", "STATIC-09"],
    "only listed pictures": ["**Only the pictures of `inputs/assets.json`**", "long side is under 1000 px", "`zoom` 2 at most", "twice its size", "default fit", "under 80% of that fit", "sits on the matte"],
    "the catalogue pass": ["**A device is used only on a beat whose `kinds` call for it.**", "we apply all the animation we have", "wrong places most of the time", "`device_wrong_kind`",
                           "`device_too_little`", "**A beat of kind `outside` that has an outside picture shows that picture for most of the beat, not the painting.**",
                           "Don't just show the painting too much", "`outside_on_painting`", "**A beat whose outside picture is `missing` stays on the detail the picks give**",
                           "**The picture under a large figure is the thing counted**", "42 ships were laid over the saint", "`figure_on_wrong_picture`", "`technique_not_offered`",
                           "`outside_picture_small`"],
    "the checks": ["`upright_whole_share`", "`highlight_off_frame`", "`highlight_too_dark`", "`caption_placeholder`", "`caption_repeats`", "`text_not_in_narration`",
                   "`asset_not_in_lines`", "`explainer_early`", "`shot_short`"],
    "the note of an edited shot": ["rewrite its `note` (or leave it empty): never keep the old reason"],
    "the owner's note": ["{{#NOTE}}", "{{OWNER_NOTE}}", "The owner's wish for this draft"],
}
FAST_RULES = {
    "the frame stays full": ["**the frame stays full**", "`zoom = 1920 / W`", "under 0.6 of that", "5% of the video at most", "`cx` = `W / 2`", "does not end where the next begins"],
    "highlights after a camera move": ["**after you move a camera, look at its highlights**", "5% in from every edge", "`remove_overlay` it", "under 0.6"],
    "text on the screen": ["**text on the screen**", "no placeholder", "no word \"narration\"", "`region_label` `\"\"`", "`sea_names` `false`", "Before second 30", "`STATIC-09`"],
    "pictures": ["**pictures**", "each is chosen for some line", "long side is under 1000 px", "`zoom` 2 at most", "default fit", "twice its size"],
    "the catalogue pass": ["`unknown_technique`", "never for one place that is merely mentioned", "never over the painting's face"],
}


@pytest.mark.parametrize("rule", sorted(TASK_RULES))
def test_the_draft_briefing_carries_the_rule(rule):
    for phrase in TASK_RULES[rule]:
        assert phrase in TASK, (rule, phrase)


@pytest.mark.parametrize("rule", sorted(FAST_RULES))
def test_the_fast_briefing_carries_the_rule(rule):
    for phrase in FAST_RULES[rule]:
        assert phrase in FAST, (rule, phrase)


def test_the_briefings_are_not_much_bigger_than_before():
    """Before this worker: 23,600 characters (23,693 bytes) for the draft task and 7,714 (7,868 bytes) for the fast briefing. The rules cost 3,130 and 1,309.
    Worker introflow added what the program writes at the start of the video (the opening shot `s0000`: the model's first shot is never a still view of the whole
    painting): about 450 and 180 more characters."""
    assert len(TASK) < 32_000 and len(TASK) - 23_600 < 8_400          # catalogue pass: the table by kinds and the rules 18 to 21 (+3,950)
    assert len(FAST) < 10_200 and len(FAST) - 7_714 < 2_500


def test_the_rendered_task_has_the_rules_and_no_open_braces(proj, tmp_path):
    ws = W.build(load_inputs(proj), root=tmp_path / "ws")
    t = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "{{" not in t and "{#" not in t and "**The frame is full.**" in t and "wish for this draft" not in t        # (the JSON example has "}}", a template key never has "{{")
    t2 = (W.build(load_inputs(proj), root=tmp_path / "ws2", instruction="x", scope_words="a chapter").root / "TASK.md").read_text(encoding="utf-8")
    assert "{{" not in t2 and "rewrite its `note`" in t2 and "wish for this draft" not in t2


def test_the_fast_briefing_of_a_box_turn_has_the_rules_and_the_main_painting_size(box):
    be = boxops.Backend(box.pdir)
    inp = load_inputs(box.pdir, for_edit=True)
    doc, _ = be.read("storyboard")
    scope = fastedit.storyboard_scope(inp, doc, {"shots": ["s0004"]})
    text = fastedit.build_briefing(inp, doc, be.adapter("storyboard").facts(doc), scope, "làm chậm cú zoom", [])
    assert "**the frame stays full**" in text and "{{" not in text
    main = inp.picks["main_asset"]
    a = doc["assets"][main]
    assert '"size":"%sx%s"' % (a["width"], a["height"]) in text, "the width the rule talks about is in the briefing"


# ----------------------------------------------------------------------------------------------------------------- only pictures that a line uses
def add_picture(proj, key, beat=None, status="picked"):
    """A third picture in the project's picks; with `beat`, a line of the narration has it."""
    pk = json.loads((proj / "picks.json").read_text(encoding="utf-8"))
    pk["assets"][key] = {**pk["assets"]["B"], "title": "Stock photo " + key, "file": "media/%s.jpg" % key}
    (proj / "media" / ("%s.jpg" % key)).write_bytes((proj / "media" / "b.jpg").read_bytes())
    if beat:
        pk["beats"][beat] = {"items": pk["beats"].get(beat, {}).get("items", []) + [{"asset": key, "region": None, "role": "context", "note": ""}], "status": status, "note": ""}
    (proj / "picks.json").write_text(json.dumps(pk), encoding="utf-8")


def offered(ws):
    return json.loads((ws.root / "inputs" / "assets.json").read_text(encoding="utf-8"))["assets"]


def test_the_catalogue_leaves_out_a_picture_that_no_line_uses_and_keeps_it_in_the_project(proj, tmp_path):
    add_picture(proj, "C")
    inp = load_inputs(proj)
    assert set(inp.picks["assets"]) == {"A", "B", "C"} and line_assets(inp) == {"A", "B"}
    ws = W.build(inp, root=tmp_path / "ws")
    assert set(offered(ws)) == {"A", "B"}
    assert not (ws.root / "images" / "C.jpg").exists() and (ws.root / "images" / "B.jpg").is_file()
    compiled = json.loads((ws.root / "inputs" / "compile_input.json").read_text(encoding="utf-8"))
    assert set(compiled["picks"]["assets"]) == {"A", "B"}
    assert "C" in json.loads((proj / "picks.json").read_text(encoding="utf-8"))["assets"], "the project's own picks are not touched"


def test_a_picture_that_a_line_has_is_offered_and_one_of_a_skipped_line_is_not(proj, tmp_path):
    add_picture(proj, "C", beat="b0005")
    assert set(offered(W.build(load_inputs(proj), root=tmp_path / "ws"))) == {"A", "B", "C"}
    pk = json.loads((proj / "picks.json").read_text(encoding="utf-8"))
    pk["beats"]["b0005"]["status"] = "skip"
    (proj / "picks.json").write_text(json.dumps(pk), encoding="utf-8")
    assert set(offered(W.build(load_inputs(proj), root=tmp_path / "ws2"))) == {"A", "B"}


def test_the_main_painting_is_always_offered(proj, tmp_path):
    pk = json.loads((proj / "picks.json").read_text(encoding="utf-8"))
    pk["beats"] = {"b0004": pk["beats"]["b0004"]}                         # no line has A any more
    (proj / "picks.json").write_text(json.dumps(pk), encoding="utf-8")
    assert set(offered(W.build(load_inputs(proj), root=tmp_path / "ws"))) == {"A", "B"}


def test_a_picture_the_saved_storyboard_still_shows_is_offered_marked_do_not_use(proj, tmp_path):
    add_picture(proj, "C")
    inp = load_inputs(proj)
    cur = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False).storyboard
    cur["assets"]["C"] = {**cur["assets"]["B"], "title": "Stock photo C", "file": "media/C.jpg"}
    cur["shots"][0]["slots"] = {"image": {"asset": "C"}}
    (proj / "storyboard.json").write_text(json.dumps(cur), encoding="utf-8")
    ws = W.build(clone_inputs(load_inputs(proj), edit_shots={cur["shots"][0]["id"]}), root=tmp_path / "ws", instruction="x")
    got = offered(ws)
    assert set(got) == {"A", "B", "C"} and "no line of the narration has it" in got["C"]["note"] and "never use it in a new shot" in got["C"]["note"]
    assert "note" not in got["A"] or "no line" not in got["A"]["note"]


def test_when_the_picks_say_nothing_about_lines_nothing_is_hidden(proj, tmp_path):
    pk = json.loads((proj / "picks.json").read_text(encoding="utf-8"))
    pk["beats"] = {b: {"items": [], "status": "picked"} for b in pk["beats"]}          # the picks made from a saved storyboard's own assets
    (proj / "picks.json").write_text(json.dumps(pk), encoding="utf-8")
    inp = load_inputs(proj)
    assert line_assets(inp) is None
    assert set(offered(W.build(inp, root=tmp_path / "ws"))) == {"A", "B"}


def test_the_fast_briefing_lists_as_other_pictures_only_those_a_line_has(box):
    """The fixture project: lines b0001 and b0003 have pictures A (the main one) and B; C and D belong to no line."""
    be = boxops.Backend(box.pdir)
    inp = load_inputs(box.pdir, for_edit=True)
    doc, _ = be.read("storyboard")
    assert line_assets(inp) == {"A", "B"}
    block = fastedit.assets_block(doc, {"A"}, "A", line_assets(inp))
    assert "Other pictures of the project" in block and "B" in block.split("Other pictures of the project")[1] and "Test detail" not in block and "Test other work" not in block
    everything = fastedit.assets_block(doc, {"A"}, "A", None)
    assert "Test detail" in everything and "Test other work" in everything
    assert "Test other work" in fastedit.assets_block(doc, {"A", "D"}, "A", line_assets(inp)), "a picture on the scope's shots is shown, it is what the shot has"


# ----------------------------------------------------------------------------------------------------------------- the owner's note
def test_the_note_is_in_the_task_file_as_the_owners_wish(proj, tmp_path):
    ws = W.build(load_inputs(proj), root=tmp_path / "ws", note="  Fewer close-ups,\nmore of the room.  ")
    t = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "- The owner's wish for this draft, in their own words (follow it wherever it does not break a rule of section 1): Fewer close-ups, more of the room.\n" in t
    assert "{{" not in t and "{#NOTE}" not in t


def test_no_note_no_line(proj, tmp_path):
    for note in (None, "", "   \n "):
        t = (W.build(load_inputs(proj), root=tmp_path / ("ws%s" % abs(hash(str(note)))), note=note).root / "TASK.md").read_text(encoding="utf-8")
        assert "wish for this draft" not in t and "{{" not in t


def test_what_the_note_says_is_never_read_as_a_template_key(proj, tmp_path):
    ws = W.build(load_inputs(proj), root=tmp_path / "ws", note="count {{N_WORDS}} and {{#DRAFT}}x{{/DRAFT}} {{OWNER_NOTE}}")
    t = (ws.root / "TASK.md").read_text(encoding="utf-8")
    line = next(x for x in t.splitlines() if x.startswith("- The owner's wish"))
    assert "{ {N_WORDS} }" in line and "{ {#DRAFT} }x{ {/DRAFT} }" in line and "{ {OWNER_NOTE} }" in line


def test_the_note_is_cut_at_its_bound_in_the_task_file(proj, tmp_path):
    ws = W.build(load_inputs(proj), root=tmp_path / "ws", note="x" * (NOTE_MAX + 50))
    line = next(x for x in (ws.root / "TASK.md").read_text(encoding="utf-8").splitlines() if x.startswith("- The owner's wish"))
    assert line.endswith("x" * NOTE_MAX) and not line.endswith("x" * (NOTE_MAX + 1))


def test_check_note():
    assert R.check_note(None) is None and R.check_note("   ") is None and R.check_note("  ít cận cảnh hơn  ") == "ít cận cảnh hơn"
    assert R.check_note("x" * NOTE_MAX) == "x" * NOTE_MAX
    with pytest.raises(DraftError) as e:
        R.check_note("x" * (NOTE_MAX + 1))
    assert e.value.code == "draft_note_too_long" and str(NOTE_MAX) in e.value.message
    for bad in (5, ["a"], {"a": 1}, True):
        with pytest.raises(DraftError) as e:
            R.check_note(bad)
        assert e.value.code == "draft_note_invalid"


@pytest.fixture()
def mgr(proj):
    return LongJobManager(projects_root=proj.parent)


def gf(d):
    return Guard(d, extra=lambda: None, repo_root=d.parent)


def finish(mgr, rec, timeout=180):
    j = mgr.wait(rec, timeout=timeout)
    assert j is not None and j["state"] not in ("queued", "running", "waiting"), j
    return j


def spy_on_build(monkeypatch):
    seen = []
    real = W.build

    def build(inp, **kw):
        ws = real(inp, **kw)
        seen.append({"note": kw.get("note"), "task": (ws.root / "TASK.md").read_text(encoding="utf-8")})
        return ws
    monkeypatch.setattr(W, "build", build)
    return seen


def test_a_draft_started_with_a_note_gives_it_to_the_agent_and_keeps_it_in_the_job(proj, mgr, fake, monkeypatch):
    seen = spy_on_build(monkeypatch)
    rec = R.start(proj.name, proj, provider="agy", note="  Show the room more than the faces. ", manager=mgr, guard_factory=gf, python="python")
    assert rec["meta"]["note"] == "Show the room more than the faces."
    j = finish(mgr, rec)
    assert j["state"] == "done", (j["error"], j["log_tail"])
    assert seen[-1]["note"] == "Show the room more than the faces." and "Show the room more than the faces." in seen[-1]["task"]
    assert "TASK.md" in fake.prompts()[0], "the agent is told to read the task file, which holds the note"


def test_a_draft_without_a_note_says_nothing_about_one(proj, mgr, fake, monkeypatch):
    seen = spy_on_build(monkeypatch)
    rec = R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python")
    assert "note" not in rec["meta"]
    finish(mgr, rec)
    assert "wish for this draft" not in seen[-1]["task"]


def test_a_note_that_is_too_long_is_refused_before_anything_starts(proj, mgr):
    with pytest.raises(DraftError) as e:
        R.start(proj.name, proj, provider="agy", note="y" * (NOTE_MAX + 1), manager=mgr)
    assert e.value.code == "draft_note_too_long"
    assert mgr.list(pid=proj.name) == [] if hasattr(mgr, "list") else True


@pytest.fixture()
def client(proj):
    app = FastAPI()
    app.state.projects_root = proj.parent

    @app.exception_handler(ApiError)
    async def _e(_, e):
        return JSONResponse({"detail": e.detail, **e.extra}, status_code=e.status)
    app.include_router(draft_api.router)
    return TestClient(app, raise_server_exceptions=False)


def test_the_route_refuses_a_note_that_is_too_long_or_not_text(client, proj):
    u = "/api/projects/%s/draft/start" % proj.name
    r = client.post(u, json={"provider": "auto", "note": "z" * (NOTE_MAX + 1)})
    assert r.status_code == 422 and r.json()["code"] == "draft_note_too_long"
    r = client.post(u, json={"provider": "auto", "note": 7})
    assert r.status_code == 422 and r.json()["code"] == "draft_note_invalid"


def test_the_route_takes_a_note_null_or_text(client, proj):
    u = "/api/projects/%s/draft/start" % proj.name
    r = client.post(u, json={"provider": "auto", "note": None})
    assert r.status_code == 200, r.text
    from bti.longjob import manager
    assert manager.wait(r.json()["job_id"], timeout=120)["state"] == "done"


def test_the_two_new_error_codes_have_a_hint_and_a_sentence():
    from bti.editor import hints
    for code in ("draft_note_too_long", "draft_note_invalid"):
        h = hints.HINTS[code]
        assert h["retry"] == "after_fix" and "note" in h["fix"]
        assert R.vi(code) != code and "ghi chú" in R.vi(code).lower()


def test_the_state_answer_offers_the_note(tmp_path):
    from bti.editor import state_api
    src = (REPO / "bti" / "editor" / "state_api.py").read_text(encoding="utf-8")
    assert '{"provider": "agy", "note": None}' in src
    spec = next(s for s in state_api.SPECS if s.id == "draft.start")
    assert "`note`" in spec.when and "600 characters" in spec.when


# ----------------------------------------------------------------------------------------------------------------- the looks the owner rejects go back to the agent
def test_a_placeholder_caption_makes_the_agent_repair_it_and_the_prompt_says_which_warning(proj, mgr, fake, monkeypatch):
    bad = json.loads(json.dumps(GOOD))
    bad["c02"]["shots"].insert(1, {"beat": "b0004", "start_word": 34, "technique": "LAY-01", "intent": "compare", "slots": {"left": {"asset": "A"}, "right": {"asset": "B"}},
                                   "params": {"caption_left": "Main", "caption_left_sub": "UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950", "caption_right": "Street", "caption_right_sub": ""},
                                   "overlays": [], "note": "two pictures"})
    (fake.dir / "cfg.json").write_text(json.dumps({"specs": bad, "victim": str(proj / "timing.json")}), encoding="utf-8")
    j = finish(mgr, R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python"))
    prompts = [str(p) for p in fake.prompts()]
    assert len(prompts) == 3, "the first turn and the two repair turns (the fake writes the same files again)"
    assert "caption_placeholder" in prompts[1] and "looks the owner rejects" in prompts[1] and "caption_repeats" not in prompts[1].split("looks the owner rejects")[0][-300:]
    assert j["state"] == "done"


def test_a_clean_draft_is_not_sent_back_and_a_default_spotlight_is(proj, mgr, fake):
    """The fake's draft has a spotlight on the mirror with the default floor (0.2 from style.json): on the fixture's picture that is almost black, so the first
    draft is sent back twice; with a floor of 0.7 nothing is raised and the agent is asked once."""
    finish(mgr, R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python"))
    sent = [str(p) for p in fake.prompts()]
    assert len(sent) == 3 and "highlight_too_dark" in sent[1] and "looks the owner rejects" in sent[1]
    fixed = json.loads(json.dumps(GOOD))
    fixed["c01"]["shots"][1]["overlays"][0]["params"]["floor"] = 0.7
    (fake.dir / "cfg.json").write_text(json.dumps({"specs": fixed, "victim": str(proj / "timing.json")}), encoding="utf-8")
    (fake.dir / "prompts.jsonl").unlink()
    finish(mgr, R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python"))
    assert len(fake.prompts()) == 1


# ----------------------------------------------------------------------------------------------------------------- "9/8 chapters"
def test_the_progress_line_never_counts_more_chapters_than_there_are(proj, tmp_path):
    ws = W.build(load_inputs(proj), root=tmp_path / "ws")
    r = R._Run(proj, "agy", None, None)
    r.ws, r.inputs = ws, load_inputs(proj)
    assert R._chapters_written(r, 0, 2) == 0
    out = ws.root / "out"
    (out / "regions.json").write_text("{}", encoding="utf-8")
    assert R._chapters_written(r, 1, 2) == 0, "regions.json is not a chapter"
    (out / "c01.json").write_text("{}", encoding="utf-8")
    (out / "c02.json").write_text("{}", encoding="utf-8")
    (out / "notes.json").write_text("{}", encoding="utf-8")
    assert len(list(out.glob("*.json"))) == 4 and R._chapters_written(r, 4, 2) == 2
    (out / "c09.json").write_text("{}", encoding="utf-8")
    assert R._chapters_written(r, 5, 2) == 2, "a file that is not a chapter of the scope is not counted"
    assert R._chapters_written(R._Run(proj, "agy", None, None), 5, 2) == 2, "without a workspace the count is still clamped"


def test_the_progress_line_of_a_running_draft_is_clamped(proj, mgr, fake):
    lines = []
    rec = R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python")
    j = finish(mgr, rec)
    for ln in (j.get("log_tail") or []):
        lines.append(str(ln))
    import re
    for m in re.finditer(r"(\d+)/(\d+) chương", json.dumps(j, ensure_ascii=False)):
        assert int(m.group(1)) <= int(m.group(2)), m.group(0)


def test_the_check_command_shows_a_viewer_warning_in_the_agents_terms_with_its_hint(proj, tmp_path):
    ws = W.build(load_inputs(proj), root=tmp_path / "ws")
    bad = json.loads(json.dumps(GOOD))
    bad["c02"]["shots"].insert(1, {"beat": "b0004", "start_word": 34, "technique": "LAY-01", "intent": "compare", "slots": {"left": {"asset": "A"}, "right": {"asset": "B"}},
                                   "params": {"caption_left": "Main", "caption_left_sub": "UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950", "caption_right": "Street", "caption_right_sub": ""},
                                   "overlays": [], "note": "two pictures"})
    for cid, sp in bad.items():
        (ws.root / "out" / (cid + ".json")).write_text(json.dumps(sp), encoding="utf-8")
    res, _ = W.workspace_compile(ws.root, draw=False)
    assert not res.errors, res.errors
    got = [i for i in res.warnings if i["code"] == "caption_placeholder"]
    assert len(got) == 1 and got[0]["chapter"] == "c02" and got[0]["shot"] == 2 and got[0]["hint"].startswith("Write a caption that comes from the narration")
    from bti.draft.compile import summary_text
    text = summary_text(res)
    assert "warning caption_placeholder: chapter c02, shot 2 (LAY-01)" in text and got[0]["hint"] in text
