"""The run in production shape: the app on a real local port, nothing swapped in. The run is started over HTTP and calls the same app over HTTP at the address the request
reached the server at (the socket's own address), like `bti` does, and drives it through a fake pipeline to the export."""
import pytest

from run_helpers import P, PID, World, actions_of, finish_run, set_auto, start_run


def test_the_run_calls_the_app_over_http_on_the_port_it_was_reached_at(live, monkeypatch):
    world = World(live, monkeypatch)
    world.build("picks_approved")
    set_auto(live, enabled=True)
    started = start_run(live)
    job, run = finish_run(live, started)
    assert actions_of(run) == ["draft.start", "proposal.apply", "storyboard.review", "storyboard.approve", "export.start"] and run["reason"] == "exported" and run["outcome"] == "done"
    assert job["state"] == "done" and job["meta"]["result"]["reason"] == "exported"
    sb = live.get(P).json()["storyboard"]
    assert sb["approvals"]["storyboard"]["by"] == "agent:auto"                       # the gate was approved over HTTP as the actor of the run


def test_the_address_is_the_one_of_the_socket_not_a_name_the_client_used(live):
    from starlette.requests import Request
    from bti.auto_run.api import local_url
    scope = {"type": "http", "server": ("127.0.0.1", 8123), "headers": [(b"host", b"winbox-cmd:8560")], "method": "POST", "path": "/", "query_string": b""}
    assert local_url(Request(scope)) == "http://127.0.0.1:8123"
    scope["server"] = ("::1", 8123)
    assert local_url(Request(scope)) == "http://[::1]:8123"
    scope["server"] = None
    assert local_url(Request(scope)).startswith("http://")
