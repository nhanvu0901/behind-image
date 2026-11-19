"""The HTTP path of the command, once against a real local port (an ephemeral one): urllib, JSON bodies, error answers, a dead port, an answer that
is not the app's, the launcher module. Everything else runs through the transport that talks to the app in the test process."""
import http.server
import json
import os
import subprocess
import sys
import threading

import pytest

from bti.cli.main import REPO, main
from bti.cli.transport import HttpTransport, Reply, Unreachable
from state_helpers import PID, make_book_project

P = f"/api/projects/{PID}"


def bti_url(url, *argv, env=None):
    import io
    out, err = io.StringIO(), io.StringIO()
    code = main(["--url", url, *argv], stdout=out, stderr=err, env=env if env is not None else {}, sleep=lambda s: None)
    return code, out.getvalue(), err.getvalue()


def test_a_whole_session_over_a_real_port(live, root):
    url, stop = live
    make_book_project(root)
    code, out, err = bti_url(url, "status")
    assert code == 0 and "arn" in out and err == ""
    code, out, err = bti_url(url, "status", "arn")
    assert code == 0 and out.splitlines()[0] == "project: arn   stage: selected   current step: script (Kịch bản)"
    assert out.splitlines()[-1] == "next: bti do arn outline.generate --yes-cost --wait   (Lập dàn ý)"
    code, out, err = bti_url(url, "status", "arn", "--json")
    assert code == 0 and json.loads(out)["project"] == "arn" and json.loads(out)["auto"]["enabled"] is False
    code, out, err = bti_url(url, "do", "arn", "outline.generate")                                     # a cost, not confirmed: stopped before the app is asked
    assert code == 3 and err.splitlines()[0] == "a person is needed: cost_not_confirmed"
    code, out, err = bti_url(url, "approve", "arn", "outline")                                         # the gate is not ready, and an agent may not approve it
    assert code == 3 and err.splitlines()[0] == "a person is needed: gate_needs_human"
    code, out, err = bti_url(url, "status", "nope", "--json")
    assert code == 4 and json.loads(out)["code"] == "project_not_found" and json.loads(out)["status"] == 404
    code, out, err = bti_url(url, "schema", "ops", "picks")
    assert code == 0 and "  set_main: " in out
    stop()
    code, out, err = bti_url(url, "status", "arn")
    assert code == 6 and err.splitlines()[0] == "cannot reach the app: unreachable"


def test_the_server_refuses_an_agent_that_the_owner_did_not_allow_over_the_wire(live, root):
    """The rule is the server's: the same refusal comes back over HTTP, whoever asks."""
    url, stop = live
    make_book_project(root)
    t = HttpTransport(url)
    r = t.request("POST", P + "/outline/approve", {"rev": "x", "actor": "cli:bti"})
    assert r.status == 403 and r.data["code"] == "gate_needs_human" and r.data["fix"]
    g = t.request("GET", P + "/auto")
    assert g.ok and g.data["enabled"] is False
    assert t.request("PUT", P + "/auto", {"base_rev": g.data["rev"], "enabled": True, "actor": "cli:bti"}).status == 403
    assert t.request("PUT", P + "/auto", {"base_rev": g.data["rev"], "enabled": True}).ok
    again = t.request("POST", P + "/outline/approve", {"rev": "x", "actor": "cli:bti"})
    assert again.status == 404 and again.data["code"] == "no_outline"                                    # allowed now: the document's own answer


def test_a_closed_port_is_unreachable():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()                                                                                           # nothing listens here now
    code, out, err = bti_url("http://127.0.0.1:%d" % port, "status")
    assert code == 6 and out == "" and "Cannot reach the app" in err
    with pytest.raises(Unreachable):
        HttpTransport("http://127.0.0.1:%d" % port).request("GET", "/api/health", None, 2.0)


def test_a_server_that_is_not_the_app_is_exit_6():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"<html>not the app</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        code, out, err = bti_url("http://127.0.0.1:%d" % srv.server_address[1], "status", "arn")
        assert code == 6 and err.splitlines()[0] == "cannot reach the app: not_the_app (HTTP 200)"
    finally:
        srv.shutdown()
        srv.server_close()


def test_the_address_comes_from_the_option_then_the_environment():
    for bad in ("ftp://x", "localhost:8560", "http://"):
        code, out, err = bti_url(bad, "status")
        assert code == 2 and err.startswith("usage: "), bad
    import io
    out, err = io.StringIO(), io.StringIO()
    code = main(["status"], stdout=out, stderr=err, env={"BTI_URL": "http://127.0.0.1:9"}, sleep=lambda s: None)     # the discard port: refused at once
    assert code == 6 and "Cannot reach the app" in err.getvalue()
    assert HttpTransport(None).base == "http://127.0.0.1:8560" and HttpTransport("http://x:1/").base == "http://x:1"


def test_python_dash_m_runs_the_command(live, root):
    url, stop = live
    make_book_project(root)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1", "BTI_URL": url}
    p = subprocess.run([sys.executable, "-m", "bti.cli", "status", "arn"], cwd=str(REPO), env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert p.returncode == 0 and p.stdout.startswith("project: arn"), p.stderr
    p = subprocess.run([sys.executable, "-m", "bti.cli", "status", "nope", "--json"], cwd=str(REPO), env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert p.returncode == 4 and json.loads(p.stdout)["code"] == "project_not_found"
    p = subprocess.run([sys.executable, "-m", "bti.cli", "frobnicate"], cwd=str(REPO), env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert p.returncode == 2 and p.stderr.startswith("usage: ")
    p = subprocess.run([sys.executable, "-m", "bti.cli", "--help"], cwd=str(REPO), env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert p.returncode == 0 and "exit codes: 0 done; 2 usage; 3 person_needed" in p.stdout


def test_the_launchers_exist_and_call_the_module():
    sh = (REPO / "tools" / "bti").read_text(encoding="utf-8")
    bat = (REPO / "tools" / "bti.bat").read_text(encoding="utf-8")
    assert "-m bti.cli" in sh and ".venv" in sh and "exec " in sh
    assert "-m bti.cli" in bat and ".venv\\Scripts\\python.exe" in bat and "%*" in bat
    assert "pip install" not in sh and "pip install" not in bat                                              # a launcher never installs anything
