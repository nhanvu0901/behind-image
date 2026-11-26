from bti.cli.transport import Reply
from run_helpers import Scripted, act, made_state
from test_loop import PID, exported, run_loop


def music_action():
    return act("music.auto", "export", cost={"kind": "model", "about": "x"}, long_job=True)


def export_action():
    return act("export.start", "export", cost={"kind": "machine_time", "about": "x"})


def test_empty_library_does_not_block_export_and_reports_once(tmp_path):
    music = act("music.auto", "export", ready=False, needs=["music_library"])
    export = export_action()
    t = Scripted(PID, [made_state([music, export], current="export"), exported()], posts={export["path"]: Reply(200, {})})
    result, _, _ = run_loop(tmp_path, t)
    assert result["reason"] == "exported"
    assert [w["code"] for w in result["warnings"]] == ["music_none"]
    assert t.paths("POST") == [export["path"]]


def test_failed_music_job_does_not_retry_or_block_export(tmp_path):
    music, export = music_action(), export_action()
    state = made_state([music, export], current="export")
    t = Scripted(PID, [state, state, exported()],
                 posts={music["path"]: Reply(200, {"job_id": "m1"}), export["path"]: Reply(200, {})},
                 jobs={"/api/longjobs/m1": [{"state": "error", "error_code": "model_failed"}]})
    result, _, log = run_loop(tmp_path, t)
    assert result["reason"] == "exported"
    assert [w["code"] for w in result["warnings"]] == ["music_none"]
    assert t.paths("POST") == [music["path"], export["path"]]
    assert log.rec["steps"][0]["job_state"] == "error"


def test_successful_music_job_precedes_export(tmp_path):
    music, export = music_action(), export_action()
    t = Scripted(PID, [made_state([music, export], current="export"), made_state([export], current="export"), exported()],
                 posts={music["path"]: Reply(200, {"job_id": "m1"}), export["path"]: Reply(200, {})},
                 jobs={"/api/longjobs/m1": [{"state": "done"}]})
    result, _, _ = run_loop(tmp_path, t)
    assert result["reason"] == "exported"
    assert not result.get("warnings")
    assert t.paths("POST") == [music["path"], export["path"]]
