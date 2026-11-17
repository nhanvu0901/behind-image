r"""Runs ON the server. Usage: remote_run.py <args.json> [venv-name]
args.json holds {"argv": [...], "cwd": "..."}: argv is run WITHOUT a shell (so spaces and quotes survive), the first item
being a python argument list: the interpreter is the project's .venv (or .venv-<venv-name>). Output (stdout+stderr, UTF-8)
is passed through unchanged; the exit code is the child's."""
import json
import os
import subprocess
import sys

def _home() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    while not os.path.exists(os.path.join(d, "requirements.txt")) and os.path.dirname(d) != d:
        d = os.path.dirname(d)
    return d


HOME = _home()


def main() -> int:
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    venv = ".venv" if len(sys.argv) < 3 or sys.argv[2] in ("", "main") else ".venv-" + sys.argv[2]
    py = os.path.join(HOME, venv, "Scripts", "python.exe")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               HF_HOME=os.path.join(HOME, "cache", "hf"), HF_HUB_DISABLE_TELEMETRY="1", PYTHONPATH=HOME)
    cwd = spec.get("cwd") or HOME
    p = subprocess.Popen([py] + spec["argv"], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = sys.stdout.buffer
    while True:
        chunk = p.stdout.read1(65536)
        if not chunk:
            break
        out.write(chunk)
        out.flush()
    return p.wait()


if __name__ == "__main__":
    sys.exit(main())
