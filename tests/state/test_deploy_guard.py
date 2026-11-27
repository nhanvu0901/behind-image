"""Deploy preflight reads live job state and fails closed without changing the app."""
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "deploy" / "check_running_jobs.ps1"


def test_guard_names_running_job_and_force_allows_it():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = ([{"id": "sample"}] if self.path == "/api/projects" else
                       {"jobs": [{"kind": "draft", "id": "j1", "state": "running"}]})
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        args = ["powershell", "-NoProfile", "-File", str(SCRIPT), "-BaseUrl", "http://127.0.0.1:%s" % server.server_port]
        blocked = subprocess.run(args, capture_output=True, text=True)
        assert blocked.returncode != 0
        assert "draft" in blocked.stdout + blocked.stderr and "sample" in blocked.stdout + blocked.stderr
        allowed = subprocess.run(args + ["-ForceWhileRunning"], capture_output=True, text=True)
        assert allowed.returncode == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_guard_refuses_when_app_cannot_be_checked():
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = server.server_port
    server.server_close()
    r = subprocess.run(["powershell", "-NoProfile", "-File", str(SCRIPT), "-BaseUrl", f"http://127.0.0.1:{port}"], capture_output=True, text=True)
    assert r.returncode != 0
    assert "cannot verify" in r.stdout


def test_job_registries_do_not_start_work_while_deploy_lock_exists(tmp_path, monkeypatch):
    import pytest
    from bti import deploy_guard
    from bti.longjob import LongJobManager, Part
    from bti.script.runner import ScriptJobs
    from bti.editor.jobs import JobManager
    monkeypatch.setattr(deploy_guard, "active", lambda: True)
    project = tmp_path / "p1"
    project.mkdir()
    calls = []
    longjobs = LongJobManager()
    with pytest.raises(deploy_guard.DeployBusy):
        longjobs.start("draft", "p1", project, [Part("fake", "Fake", lambda ctx: calls.append("long"))])
    scripts = ScriptJobs(projects_root=tmp_path)
    with pytest.raises(deploy_guard.DeployBusy):
        scripts.start("outline", "p1", "fake", lambda job: calls.append("script"))
    previews = JobManager(projects_root=tmp_path)
    with pytest.raises(deploy_guard.DeployBusy):
        previews.submit("p1", lambda progress: calls.append("preview"))
    assert not calls
    assert not longjobs.active("p1") and not scripts.running("p1") and not previews.active("p1")


def test_guard_refuses_if_project_state_cannot_report_jobs():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = ([{"id": "broken"}] if self.path == "/api/projects" else
                       {"project": "broken", "stage": None, "jobs": [], "problems": [{"code": "project_file_damaged"}]})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-File", str(SCRIPT), "-BaseUrl", f"http://127.0.0.1:{server.server_port}"], capture_output=True, text=True)
        assert r.returncode != 0
        assert "broken" in r.stdout
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_guard_allows_a_readable_project_without_jobs():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = [{"id": "idle"}] if self.path == "/api/projects" else {"project": "idle", "jobs": [], "problems": []}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-File", str(SCRIPT), "-BaseUrl", f"http://127.0.0.1:{server.server_port}"], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
