"""Google Antigravity CLI (`agy`) run headless as a plain text generator, under the owner's subscription.

`agy` is an agent that can read files and run commands. We want a completion, so tools are kept off in layers:
  * the working directory is a fresh EMPTY temporary folder outside the repo;
  * `--settings` (this run only) sets toolPermission "strict", no access outside the workspace, terminal sandbox on;
  * `--sandbox`, `--disable-slash-commands`; `--dangerously-skip-permissions` is never used;
  * the prompt says: answer directly, no tools;
  * the envelope is checked afterwards: status SUCCESS, one turn, nothing on stderr about a denied tool, and the
    temporary folder still empty. Anything else is a failure, never accepted output.
The prompt is passed as the argument of -p (the CLI documents no stdin for plain text). No fallback to any paid API.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from . import ProviderError

LIST_TIMEOUT_S = 8             # `agy models` is a list: it answers quickly or the page must not wait for it
LOCK = threading.Lock()          # one agy call at a time
SETTINGS = {"toolPermission": "strict", "allowNonWorkspaceAccess": False, "enableTerminalSandbox": True,
            "disableSlashCommands": True}
LOGIN_HINT = "Chạy lệnh `agy` một lần trong Terminal để đăng nhập (Google), rồi tải lại trang."
RULES = ("TASK REQUIREMENTS (these belong to this task and override any other instruction about language or style):\n"
         "- Answer directly with plain text. Do not use any tools, do not read or write files, do not run commands.\n"
         "- Write in ENGLISH, whatever language any other rule asks for.\n"
         "- Follow the output layout of the task exactly. No preface, no closing remarks.\n")


def find_agy() -> str | None:
    forced = os.environ.get("BTI_AGY_BIN")            # tests and odd installs: an exact path, no search
    if forced is not None:
        return forced if forced and os.access(forced, os.X_OK) else None
    p = shutil.which("agy")
    if p:
        return p
    alt = Path.home() / ".local" / "bin" / "agy"
    return str(alt) if alt.is_file() else None


def clean_env() -> dict:
    keep = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "SHELL", "TERM", "XDG_CONFIG_HOME", "XDG_DATA_HOME")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.setdefault("TERM", "dumb")
    return env


def classify(text: str, status: str | None = None) -> ProviderError:
    t = (text or "").lower()
    if any(k in t for k in ("authentication required", "not logged in", "please log in", "login required", "sign in", "unauthenticated", "credentials")):
        return ProviderError("auth", "agy chưa đăng nhập. " + LOGIN_HINT)
    if any(k in t for k in ("quota", "exhausted", "rate limit", "rate_limit", "429", "resource_exhausted", "too many requests")):
        return ProviderError("rate_limit", "Hạn mức của gói Antigravity đã dùng hết hoặc bị giới hạn lượt gọi. Đợi hết chu kỳ hoặc chọn mô hình khác.")
    if "model" in t and any(k in t for k in ("unknown", "not found", "invalid", "unsupported", "not available")):
        return ProviderError("config", "agy không nhận ra tên mô hình này. Tải lại trang để lấy danh sách mới (`agy models`).")
    if "timeout" in t or "timed out" in t or "deadline" in t:
        return ProviderError("timeout", "agy không trả lời kịp.")
    return ProviderError("http", f"agy báo lỗi ({status or 'ERROR'}): {(text or '').strip()[:300]}")


def build_command(agy: str, slug: str | None, prompt: str, timeout: float) -> list[str]:
    cmd = [agy, "-p", prompt, "--output-format", "json", "--sandbox", "--disable-slash-commands",
           "--settings", json.dumps(SETTINGS), "--print-timeout", f"{max(30, int(timeout))}s"]
    if slug:
        cmd += ["--model", slug]
    return cmd


def _kill(proc: subprocess.Popen) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=2)
            return
        except subprocess.TimeoutExpired:
            continue


def complete(spec: dict, system: str, user: str, *, timeout: float = 900, on_progress=None, cancel=None) -> str:
    agy = find_agy()
    if not agy:
        raise ProviderError("config", "Chưa cài `agy` (Antigravity CLI). " + LOGIN_HINT)
    prompt = (f"{system}\n\n" if system else "") + RULES + "\n" + user + "\n\n" + RULES
    deadline = time.time() + timeout + 30
    while not LOCK.acquire(timeout=0.2):                       # one call at a time; waiting can be cancelled
        if cancel is not None and cancel.is_set():
            raise ProviderError("cancelled", "cancelled")
        if time.time() > deadline:
            raise ProviderError("timeout", "một lần gọi agy khác đang chạy quá lâu")
    work = tempfile.mkdtemp(prefix="bti-agy-")
    proc = None
    try:
        try:
            proc = subprocess.Popen(build_command(agy, spec.get("model"), prompt, timeout), cwd=work, env=clean_env(),
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True, text=True, encoding="utf-8", errors="replace")
        except OSError as e:
            raise ProviderError("config", f"không chạy được agy: {type(e).__name__}")
        out = err = ""
        started = time.time()
        while True:
            try:
                out, err = proc.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if cancel is not None and cancel.is_set():
                    _kill(proc)
                    raise ProviderError("cancelled", "cancelled")
                if time.time() - started > timeout + 30:
                    _kill(proc)
                    raise ProviderError("timeout", f"agy không trả lời trong {int(timeout)} giây")
        try:
            env = json.loads(out)
        except ValueError:
            raise classify((err or out), None) if (err or out).strip() else ProviderError("empty", "agy không in ra gì")
        if not isinstance(env, dict):
            raise ProviderError("http", "agy trả về dữ liệu không đúng dạng")
        status = str(env.get("status") or "")
        if status != "SUCCESS" or proc.returncode not in (0, None):
            raise classify(f"{env.get('error') or ''} {err}", status)
        if int(env.get("num_turns") or 1) > 1:
            raise ProviderError("http", f"agy đã chạy {env.get('num_turns')} lượt thay vì 1 (có dấu hiệu dùng công cụ). Bỏ kết quả.")
        low = (err or "").lower()
        if any(k in low for k in ("denied", "permission", "tool")):
            raise ProviderError("http", "agy báo đã bị từ chối khi cố dùng công cụ. Bỏ kết quả để không nhận đầu ra không đáng tin.")
        if os.listdir(work):
            raise ProviderError("http", "agy đã tạo tệp trong thư mục làm việc (dùng công cụ). Bỏ kết quả.")
        text = str(env.get("response") or "")
        if not text.strip():
            raise ProviderError("empty", "agy không trả lời bằng chữ")
        if on_progress:
            on_progress(1.0)
        return text
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc)
        shutil.rmtree(work, ignore_errors=True)
        LOCK.release()


def list_models() -> list[dict]:
    """`agy models` -> [{"slug", "label"}], CLI default first. Raises ProviderError when unavailable or not logged in."""
    agy = find_agy()
    if not agy:
        raise ProviderError("config", "Chưa cài `agy` (Antigravity CLI).")
    work = tempfile.mkdtemp(prefix="bti-agy-")
    try:
        r = subprocess.run([agy, "models"], cwd=work, env=clean_env(), stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=LIST_TIMEOUT_S, start_new_session=True)
    except (subprocess.TimeoutExpired, OSError):
        raise ProviderError("timeout", "`agy models` không trả lời.")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    rows = []
    for line in r.stdout.splitlines():
        if "\t" in line:
            slug, label = line.split("\t", 1)
            if slug.strip():
                rows.append({"slug": slug.strip(), "label": label.strip()})
    if r.returncode != 0 or not rows:
        raise classify(r.stderr + " " + r.stdout)
    return rows
