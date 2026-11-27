"""Exercise the real deploy guard against a local HTTP API on available PowerShells."""
import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "deploy" / "check_running_jobs.ps1"


@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
@pytest.mark.parametrize("running", [False, True])
def test_multiple_projects(shell, running):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is not available")
    paths = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            if self.path == "/api/projects":
                payload = [{"id": "first"}, {"id": "second"}]
            elif self.path in ("/api/projects/first/state", "/api/projects/second/state"):
                jobs = ([{"kind": "draft", "id": "job-7", "state": "running"}]
                        if running and self.path == "/api/projects/second/state" else [])
                payload = {"jobs": jobs, "problems": []}
            else:
                self.send_error(404)
                return
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
                                 "-BaseUrl", f"http://127.0.0.1:{server.server_port}"],
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == (3 if running else 0), result.stdout + result.stderr
        assert paths == ["/api/projects", "/api/projects/first/state", "/api/projects/second/state"]
        if running:
            assert "project second has a running draft job (job-7)" in result.stdout
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
