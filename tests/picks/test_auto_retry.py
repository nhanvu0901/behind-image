"""fixes4, point 2: `picks.retry_missing` (bti/picks/auto/retry.py). The pictures the agent chose and the source refused (`missing` with the code `import_limited`) are imported
from the saved files of the last run and their lines are written again the way the write part would have written them. Fake agent, fake sources, no network."""
import json
import shutil

import pytest
from auto_fixtures import env, paid  # noqa: F401
from auto_helpers import Env, make_auto_project

from bti.picks import doc, service
from bti.picks.auto import AutoError, retry, store, texts
from bti.picks.errors import PicksError


# ---------------------------------------------------------------------------------------------------------------- helpers
def refusing(*, fail=("commons",), wait=None):
    """A `fetch_asset` seam that is the real one, except that a source in `fail` answers "too many requests"."""
    calls = []

    def fetch(pdir, source, source_id):
        calls.append((source, source_id))
        if source in fail:
            raise PicksError(503, "the image source limits downloads", "source_rate_limited", retryable=True, retry_after=wait)
        return service.fetch_asset(pdir, source, source_id)
    fetch.calls = calls
    return fetch


def working():
    calls = []

    def fetch(pdir, source, source_id):
        calls.append((source, source_id))
        return service.fetch_asset(pdir, source, source_id)
    fetch.calls = calls
    return fetch


def limited_run(env, **kw):
    """A run of the pictures agent in which Commons refuses every download: both Commons pictures (b0003, the clip of b0004) are listed `import_limited`."""
    job = env.run(fetch_asset=refusing(**kw))
    assert job["state"] == "done", job.get("error")
    return job


def retry_job(env, *, fetch=None, beats=None, actor="cli:test", **seams):
    rec = retry.start(env.pid, env.pdir, beats=beats, actor=actor, manager=env.manager, fetch_asset=fetch or working(), **seams)
    return env.manager.wait(rec["id"], 60)


def shape(pdir):
    """The beats of a picks document in a form two projects can be compared in: the asset of an item by its title."""
    d = doc.load(pdir)
    out = {}
    for bid, b in d["beats"].items():
        out[bid] = {"status": b["status"], "note": b["note"], "kinds": b.get("kinds"), "missing": b.get("missing"),
                    "items": [(i["role"], i["region"], i["note"], d["assets"][i["asset"]]["title"]) for i in b["items"]]}
    return out


# ---------------------------------------------------------------------------------------------------------------- the result is what the write part would have written
def test_a_line_that_was_refused_is_written_again_exactly_as_a_run_that_was_not_refused_would_have_written_it(env):
    limited_run(env)
    before = shape(env.pdir)
    assert before["b0003"]["missing"] == [{"what": "Chân dung họa sĩ", "code": "import_limited"}] and before["b0003"]["items"][0][0] == "main"        # its fallback
    assert "Chưa tìm được" in before["b0003"]["note"] and before["b0004"]["missing"] == [{"what": "Kênh đào", "code": "import_limited"}]
    job = retry_job(env)
    assert job["state"] == "done", job.get("error")
    r = job["result"]
    assert r["lines_total"] == 2 and r["lines_fixed"] == ["b0003", "b0004"] and r["lines_still_limited"] == [] and r["lines_left"] == [] and r["pictures_imported"] == 2
    assert r["sentence"] == "Đã tải lại hình cho 2/2 đoạn." and len(r["batches"]) == 2
    control = Env(env.root, make_auto_project(env.root, "pk2"), env.agent, env.sources, env.manager)
    assert control.run()["state"] == "done"
    assert shape(env.pdir) == shape(control.pdir)                                                                   # the same notes, kinds, items in the same order, nothing missing
    b3 = shape(env.pdir)["b0003"]
    assert b3["items"][0][0] == "context" and b3["items"][0][2] == "Bản chụp chân dung rõ nét." and b3["missing"] is None and "Chưa tìm được" not in b3["note"]
    assert b3["note"] == "Nói về họa sĩ."                                                                           # the plan's reason, without the sentence about what is missing


def test_the_picture_comes_at_the_place_the_plan_gave_and_the_other_items_of_the_line_stay(env):
    limited_run(env)
    retry_job(env)
    d = doc.load(env.pdir)
    assert [i["role"] for i in d["beats"]["b0004"]["items"]] == ["map", "video"]                                   # the map was there; the clip came back after it, as the plan says
    assert "clip khoảng 6 giây" in d["beats"]["b0004"]["items"][1]["note"] and d["assets"][d["beats"]["b0004"]["items"][1]["asset"]]["kind"] == "video"
    assert [(c["actor"], c["note"]) for c in env.changes()[:2]] == [("cli:test", "Tải lại hình đã chọn: đoạn b0004"), ("cli:test", "Tải lại hình đã chọn: đoạn b0003")]   # one batch a line
    assert all(b["undo_of"] is None for b in env.changes()[:2]) and d["approval"]["approved"] is False                # never approves


def test_every_batch_of_the_retry_can_be_undone(env):
    limited_run(env)
    retry_job(env)
    from bti.ops import runner
    from bti.ops.adapters import PicksAdapter
    from bti.ops.log import ChangeLog
    newest = env.changes()[0]["batch"]
    ad = PicksAdapter(env.pdir)
    runner.run_undo({"picks": ad}, newest, {"base_rev": ad.read()[1], "actor": "cli:test", "note": ""}, ChangeLog(env.pdir))
    d = doc.load(env.pdir)                                                                                           # the newest batch was the line b0004: it is as the agent's run left it, b0003 keeps its picture
    assert d["beats"]["b0004"]["missing"] == [{"what": "Kênh đào", "code": "import_limited"}] and "missing" not in d["beats"]["b0003"]


def test_what_was_done_is_kept_so_that_the_run_takes_it_once_and_a_new_run_forgets_it(env):
    limited_run(env)
    f = retry.facts(env.pdir, doc.load(env.pdir))
    assert f == {"lines": ["b0003", "b0004"], "files": True, "untried": ["b0003", "b0004"]}
    retry_job(env, fetch=refusing(wait=75))                                                                         # nothing can be had: the lines stay listed
    f = retry.facts(env.pdir, doc.load(env.pdir))
    assert f["lines"] == ["b0003", "b0004"] and f["untried"] == [] and store.read(env.pdir, "retry.json")["tried"] == ["b0003", "b0004"]
    store.reset(env.pdir)                                                                                           # a new run of picks.auto starts from nothing
    assert not (store.cache_dir(env.pdir) / "retry.json").exists()


# ---------------------------------------------------------------------------------------------------------------- what does not change
def test_a_line_that_is_still_refused_stays_as_it_was_and_is_reported_with_the_wait(env):
    limited_run(env)
    before = shape(env.pdir)
    changes = len(env.changes())
    job = retry_job(env, fetch=refusing(wait=75))
    assert job["state"] == "done"
    r = job["result"]
    assert r["lines_fixed"] == [] and [x["beat"] for x in r["lines_still_limited"]] == ["b0003", "b0004"] and r["pictures_imported"] == 0
    assert all(x["code"] == "import_limited" and "khoảng 2 phút" in x["why"] for x in r["lines_still_limited"])
    assert shape(env.pdir) == before and len(env.changes()) == changes                                            # nothing was written
    assert r["sentence"] == "Đã tải lại hình cho 0/2 đoạn. 2 chỗ vẫn bị giới hạn lượt tải, thử lại sau."


def test_a_source_that_refuses_again_after_the_first_picture_is_not_asked_for_the_second(env):
    limited_run(env)
    fetch = refusing(wait=None)
    job = retry_job(env, fetch=fetch)
    assert [s for s, _ in fetch.calls].count("commons") == 1 and job["result"]["lines_fixed"] == []


def test_only_the_line_that_could_be_had_is_written_when_the_other_source_still_refuses(env):
    limited_run(env)
    order = []

    def fetch(pdir, source, source_id):
        order.append(source_id)
        if "Canal" in source_id:
            raise PicksError(503, "limits", "source_rate_limited", retryable=True, retry_after=30)
        return service.fetch_asset(pdir, source, source_id)
    job = retry_job(env, fetch=fetch)
    r = job["result"]
    assert r["lines_fixed"] == ["b0003"] and [x["beat"] for x in r["lines_still_limited"]] == ["b0004"]
    d = doc.load(env.pdir)
    assert d["beats"]["b0003"].get("missing") is None and d["beats"]["b0004"]["missing"] == [{"what": "Kênh đào", "code": "import_limited"}]
    assert retry.facts(env.pdir, d)["lines"] == ["b0004"]


def test_a_line_that_was_changed_after_the_agent_wrote_it_is_left_alone(env):
    from bti.ops import runner
    from bti.ops.adapters import PicksAdapter
    from bti.ops.log import ChangeLog
    limited_run(env)
    ad = PicksAdapter(env.pdir)
    runner.run_batch(ad, {"base_rev": ad.read()[1], "actor": "human", "note": "by hand",
                          "ops": [{"op": "set_picks", "beat": "b0003", "items": [{"asset": "A", "region": "MIRROR", "role": "detail"}], "reason": "Tôi tự chọn."}]}, ChangeLog(env.pdir))
    mine = shape(env.pdir)["b0003"]
    assert mine["missing"] == [{"what": "Chân dung họa sĩ", "code": "import_limited"}]                              # the page keeps what the agent knew
    fetch = working()
    job = retry_job(env, fetch=fetch)
    r = job["result"]
    assert r["lines_fixed"] == ["b0004"] and [(x["beat"], x["code"]) for x in r["lines_left"]] == [("b0003", "line_changed")]
    assert "đã được sửa sau lần chạy của agent" in r["lines_left"][0]["why"] and shape(env.pdir)["b0003"] == mine
    assert not any("Portrait" in sid for _, sid in fetch.calls)                                                    # and its picture was not even downloaded
    assert r["sentence"] == "Đã tải lại hình cho 1/2 đoạn. 1 đoạn giữ nguyên."


def test_a_web_budget_is_not_retried_here_and_the_other_pictures_of_a_line_stay_missing(env):
    limited_run(env)
    d = doc.load(env.pdir)
    from bti.ops import runner
    from bti.ops.adapters import PicksAdapter
    from bti.ops.log import ChangeLog
    ad = PicksAdapter(env.pdir)
    runner.run_batch(ad, {"base_rev": ad.read()[1], "actor": "cli:test", "note": "x",
                          "ops": [{"op": "set_picks", "beat": "b0003", "items": d["beats"]["b0003"]["items"], "reason": d["beats"]["b0003"]["note"],
                                   "missing": [{"what": "Chân dung họa sĩ", "code": "web_budget"}]}]}, ChangeLog(env.pdir))
    assert retry.lines_with_limit(doc.load(env.pdir)) == ["b0004"]                                                  # b0003 says web_budget: not this action's
    job = retry_job(env)
    assert job["result"]["lines_fixed"] == ["b0004"] and shape(env.pdir)["b0003"]["missing"] == [{"what": "Chân dung họa sĩ", "code": "web_budget"}]


def test_the_refusals_before_a_job_starts(env):
    with pytest.raises(AutoError) as e:
        retry.start(env.pid, env.pdir, manager=env.manager)                                                         # no line says import_limited
    assert e.value.code == "retry_nothing_to_do" and e.value.status == 409
    limited_run(env)
    with pytest.raises(AutoError) as e:
        retry.start(env.pid, env.pdir, beats=["b0001"], manager=env.manager)                                        # a line that does not say it
    assert e.value.code == "retry_nothing_to_do"
    with pytest.raises(AutoError) as e:
        retry.start(env.pid, env.pdir, beats="b0003", manager=env.manager)
    assert e.value.code == "invalid" and e.value.status == 422
    cache = store.cache_dir(env.pdir)
    saved = {n: (cache / n).read_bytes() for n in retry.FILES}
    (cache / "choice.json").unlink()
    with pytest.raises(AutoError) as e:
        retry.start(env.pid, env.pdir, manager=env.manager)                                                         # the saved files are not all there
    assert e.value.code == "retry_no_files" and not retry.files_ready(env.pdir)
    (cache / "choice.json").write_bytes(saved["choice.json"])
    other = json.loads(saved["choice.json"])
    other["key"] = "another-run"
    (cache / "choice.json").write_text(json.dumps(other), encoding="utf-8")
    job = retry_job(env)                                                                                            # files of two different runs: the job refuses with its sentence
    assert job["state"] == "error" and job["error_code"] == "retry_no_files"
    for n, b in saved.items():
        (cache / n).write_bytes(b)


def test_beats_names_the_lines_to_look_at(env):
    limited_run(env)
    fetch = working()
    job = retry_job(env, fetch=fetch, beats=["b0003"])
    assert job["result"]["lines_fixed"] == ["b0003"] and not any("Canal" in sid for _, sid in fetch.calls)
    assert retry.lines_with_limit(doc.load(env.pdir)) == ["b0004"]


def test_the_job_is_a_picks_job_and_a_second_one_is_refused_while_it_runs(env):
    import threading
    limited_run(env)
    started, release = threading.Event(), threading.Event()

    def slow(pdir, source, source_id):
        started.set()
        release.wait(20)
        return service.fetch_asset(pdir, source, source_id)
    rec = retry.start(env.pid, env.pdir, manager=env.manager, fetch_asset=slow)
    try:
        assert started.wait(20)
        assert env.manager.active(env.pid, kind="picks")["meta"]["action"] == "retry"
        with pytest.raises(AutoError) as e:
            retry.start(env.pid, env.pdir, manager=env.manager, fetch_asset=working())
        assert e.value.code == "busy"
    finally:
        release.set()
        env.manager.wait(rec["id"], 60)


# ---------------------------------------------------------------------------------------------------------------- the second choice (the web round) is read as the write part read it
def build_saved(pdir, *, c1, c2=None, round2=None, key="k1"):
    """Hand-made saved files for a plan of two lines: b0003 wants a portrait (commons candidates 1..3 from round one, 4..6 from round two)."""
    cands = [{"n": n, "source": "commons", "source_id": "File:P%d.jpg" % n, "title": "P%d" % n, "round": 2 if n > 3 else 1} for n in range(1, 7)]
    plan = {"regions": {}, "lines": [
        {"beat": "b0003", "reason": "Nói về họa sĩ.", "kinds": ["outside"], "fallback": {"type": "whole"},
         "show": [{"type": "context", "search": "painter", "alt": [], "kind": "portrait", "what": "Chân dung họa sĩ", "period": "then", "entity": "Jan van Eyck"}]}]}
    search = {"schema": store.SCHEMA, "key": key, "wants": {"b0003.1": {"id": "b0003.1", "beat": "b0003", "n": 1, "type": "context", "status": "found", "candidates": cands}},
              "limited": {}, "books": [], "round2": round2 or {"searched": True, "wants": [], "map": {}, "budget": []}}
    store.write(pdir, "plan.json", {"schema": store.SCHEMA, "key": key, "plan": plan})
    store.write(pdir, "search.json", search)
    store.write(pdir, "choice.json", {"schema": store.SCHEMA, "key": key, "choice": {"wants": {"b0003.1": c1}, "regions": {}}, "shown": ["b0003.1"], "regions": []})
    if c2 is not None:
        store.write(pdir, "choice2.json", {"schema": store.SCHEMA, "key": key, "choice": {"wants": {"b0003.1": c2}, "regions": {}}, "shown": ["b0003.1"]})


def written_as_limited(pdir):
    """The line b0003 as the write part leaves it when the only picture was refused: the fallback and `missing`."""
    from bti.ops import runner
    from bti.ops.adapters import PicksAdapter
    from bti.ops.log import ChangeLog
    ad = PicksAdapter(pdir)
    runner.run_batch(ad, {"base_rev": ad.read()[1], "actor": "agent:mock", "note": "run",
                          "ops": [{"op": "set_picks", "beat": "b0003", "items": [{"asset": "A", "region": None, "role": "main"}], "reason": "Nói về họa sĩ. Chưa tìm được: Chân dung họa sĩ.",
                                   "kinds": ["outside"], "missing": [{"what": "Chân dung họa sĩ", "code": "import_limited"}]}]}, ChangeLog(pdir))


def test_the_first_choice_names_a_candidate_of_the_want_by_its_number(env):
    build_saved(env.pdir, c1={"pick": ["c", 2], "reason": "Hình hai."})
    written_as_limited(env.pdir)
    fetch = working()
    env.sources["commons"].items = [{"source": "commons", "source_id": "File:P%d.jpg" % n, "title": "P%d" % n, "thumb_url": "", "page_url": "", "width": 1300, "height": 1250,
                                     "mime": "image/png", "kind": "image", "author": "A", "licence": "CC0", "url": "https://example.invalid/%d.png" % n, "_q": "x"} for n in range(1, 7)]
    job = retry_job(env, fetch=fetch)
    assert job["state"] == "done", job.get("error")
    assert fetch.calls == [("commons", "File:P2.jpg")]
    d = doc.load(env.pdir)
    assert d["assets"][d["beats"]["b0003"]["items"][0]["asset"]]["title"] == "P2" and d["beats"]["b0003"]["items"][0]["note"] == "Hình hai."


def test_the_second_choice_counts_inside_the_second_rounds_map_of_the_want(env):
    # the second session saw only the NEW candidates, numbered 1..3 on its own sheet: its pick 2 is the want's candidate 5 (`round2.map` says 4, 5, 6)
    build_saved(env.pdir, c1={"pick": None, "reason": "Không hình nào."}, c2={"pick": ["c", 2], "reason": "Hình mới thứ hai."},
                round2={"searched": True, "wants": ["b0003.1"], "map": {"b0003.1": [4, 5, 6]}, "budget": []})
    written_as_limited(env.pdir)
    env.sources["commons"].items = [{"source": "commons", "source_id": "File:P%d.jpg" % n, "title": "P%d" % n, "thumb_url": "", "page_url": "", "width": 1300, "height": 1250,
                                     "mime": "image/png", "kind": "image", "author": "A", "licence": "CC0", "url": "https://example.invalid/%d.png" % n, "_q": "x"} for n in range(1, 7)]
    fetch = working()
    job = retry_job(env, fetch=fetch)
    assert job["state"] == "done", job.get("error")
    assert fetch.calls == [("commons", "File:P5.jpg")]
    d = doc.load(env.pdir)
    assert d["assets"][d["beats"]["b0003"]["items"][0]["asset"]]["title"] == "P5" and d["beats"]["b0003"]["items"][0]["note"] == "Hình mới thứ hai."


def test_a_choice_of_a_picture_of_the_books_is_read_too(env):
    from bti.picks.auto import write as awrite
    plan = {"regions": {}, "lines": [{"beat": "b0003", "reason": "r", "kinds": ["outside"], "fallback": {"type": "whole"},
                                      "show": [{"type": "context", "search": "x", "alt": [], "kind": "document", "what": "Trang sách", "period": "then"}]}]}
    search = {"wants": {"b0003.1": {"id": "b0003.1", "candidates": [], "status": "found"}}, "books": [{"n": 1, "label": "p1", "source_id": "book:p1"}]}
    rows = awrite.resolve_picks(plan, search, {"wants": {"b0003.1": {"pick": ["b", 1], "reason": "Trang sách."}}, "regions": {}}, search["books"])
    assert rows["b0003.1"]["pick"] == {"source": "book", "source_id": "book:p1", "media": "image"}


def test_the_texts_of_the_action_are_there():
    for code in ("retry_nothing_to_do", "retry_no_files"):
        assert texts.vi(code) != code
    assert texts.retry_sentence(5, 6, 1, 0) == "Đã tải lại hình cho 5/6 đoạn. 1 chỗ vẫn bị giới hạn lượt tải, thử lại sau."
    assert texts.retry_sentence(6, 6, 0, 0) == "Đã tải lại hình cho 6/6 đoạn."
