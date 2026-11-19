"""The exit codes of `bti`: the table that maps what the server answered to one of them, and that every code can be produced."""
import pytest

from bti.cli import exitcodes as X


@pytest.mark.parametrize("status, body, expected", [
    (403, {"code": "gate_needs_human", "retry": "after_fix"}, X.PERSON),
    (403, {"code": "forbidden", "retry": "no"}, X.PERSON),
    (401, {"code": "forbidden", "retry": "no"}, X.PERSON),
    (422, {"code": "confirm_required", "retry": "after_fix"}, X.PERSON),
    (409, {"code": "agy_auth", "retry": "after_fix"}, X.PERSON),
    (409, {"code": "claude_auth", "retry": "after_fix"}, X.PERSON),
    (409, {"code": "real_models_off", "retry": "no"}, X.PERSON),
    (409, {"code": "stale_revision", "retry": "after_fix"}, X.BUSY),
    (409, {"code": "stale", "retry": "after_fix"}, X.BUSY),
    (409, {"code": "model_job_busy", "retry": "later"}, X.BUSY),
    (409, {"code": "voice_busy", "retry": "later"}, X.BUSY),
    (503, {"code": "source_unavailable", "retry": "later"}, X.BUSY),
    (429, {"code": "whatever", "retry": "later"}, X.BUSY),
    (422, {"code": "invalid_field", "retry": "after_fix"}, X.REFUSED),
    (404, {"code": "project_not_found", "retry": "no"}, X.REFUSED),
    (409, {"code": "undo_conflict", "retry": "after_fix"}, X.REFUSED),
    (500, {"code": "internal_error", "retry": "no"}, X.REFUSED),
    (400, {"detail": "no code, no retry"}, X.REFUSED),
    (404, None, X.UNREACHABLE),
    (502, None, X.UNREACHABLE),
    (500, "Internal Server Error", X.UNREACHABLE),
])
def test_one_table_maps_the_servers_answer_to_the_exit_code(status, body, expected):
    assert X.exit_for_error(status, body) == expected


def test_the_table_in_the_documents_is_the_table_in_the_code():
    """MAPPING is what the documents print; its rules are the ones `exit_for_error` applies, in the same order."""
    codes = [c for _, c in X.MAPPING]
    assert codes == [X.DONE, X.PERSON, X.BUSY, X.BUSY, X.REFUSED, X.UNREACHABLE]
    assert [n for n, *_ in X.EXIT_CODES] == [0, 2, 3, 4, 5, 6] and set(X.NAME_OF) == {0, 2, 3, 4, 5, 6}
    assert (X.DONE, X.USAGE, X.PERSON, X.REFUSED, X.BUSY, X.UNREACHABLE) == (0, 2, 3, 4, 5, 6)


@pytest.mark.parametrize("job, expected", [
    ({"state": "done"}, X.DONE),
    ({"state": "cancelled"}, X.BUSY),
    ({"state": "interrupted", "error_code": "interrupted"}, X.BUSY),
    ({"state": "error", "error_code": "agy_auth"}, X.PERSON),
    ({"state": "error", "error_code": "claude_auth"}, X.PERSON),
    ({"state": "error", "error_code": "voice_worker_failed"}, X.BUSY),
    ({"state": "error", "error_code": "agy_rate_limit"}, X.BUSY),
    ({"state": "error", "error_code": "invalid_field"}, X.REFUSED),
    ({"state": "error", "error_code": "a_code_nobody_knows"}, X.REFUSED),
    ({"state": "error", "error_kind": "auth"}, X.PERSON),
    ({"state": "error", "error_kind": "timeout"}, X.BUSY),
    ({"state": "error", "error_kind": "rate_limit"}, X.BUSY),
    ({"state": "error", "error_kind": "parse"}, X.REFUSED),
    ({"state": "error", "error_kind": "validation"}, X.REFUSED),
    ({"state": "error"}, X.REFUSED),
])
def test_a_job_that_ended_maps_by_its_error_code_or_kind(job, expected):
    assert X.exit_for_job(job) == expected


def test_every_person_code_is_a_code_of_the_server():
    from bti.editor.hints import HINTS
    assert X.PERSON_CODES <= set(HINTS) and X.STALE_CODES <= set(HINTS)


def test_every_script_job_kind_has_an_exit():
    """The kinds a script job can fail with (bti/script/runner.py JobError) all map."""
    kinds = {"timeout", "rate_limit", "auth", "config", "validation", "parse", "http", "empty", "blocked", "conflict"}
    assert kinds <= set(X.JOB_KIND_EXIT)

