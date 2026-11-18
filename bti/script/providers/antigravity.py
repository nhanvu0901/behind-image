"""Google Antigravity CLI (`agy`) run headless as a plain text generator, under the owner's subscription.

`agy` is an agent that can read files and run commands. We want a completion, so tools are kept off in layers:
  * the working directory is a fresh EMPTY temporary folder outside the repo;
  * `--settings` (this run only) sets toolPermission "strict", no access outside the workspace, terminal sandbox on;
  * `--sandbox`, `--disable-slash-commands`; `--dangerously-skip-permissions` is never used;
  * the prompt says: answer directly, no tools;
  * the envelope is checked afterwards: status SUCCESS, one turn, nothing on stderr about a denied tool, and the
    temporary folder still empty. Anything else is a failure, never accepted output.
The prompt goes in through stdin, as one `{"event":"user","message":{"content":...}}` line of `--input-format stream-json`
(with `--output-format stream-json`), never as a command-line argument: a Windows command line stops at about 32,000
characters and our prompts reach 60,000. The answer is the `result` event on stdout. The CLI must support `--settings`
(older builds do not, and are refused: strict tool permission could not be set). No fallback to any paid API.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from ...proc import IS_WINDOWS, group_kwargs, kill_tree
from . import ProviderError

LIST_TIMEOUT_S = 8             # `agy models` is a list: it answers quickly or the page must not wait for it
LOCK = threading.Lock()          # one agy call at a time
SETTINGS = {"toolPermission": "strict", "allowNonWorkspaceAccess": False, "enableTerminalSandbox": True,
            "disableSlashCommands": True}
TOOL_STEPS = frozenset({"tool_call", "run_command", "view_file", "write_to_file", "list_dir", "grep_search", "search_web"})
LOGIN_HINT = "Chạy lệnh `agy` một lần trong Terminal để đăng nhập (Google), rồi tải lại trang."
RULES = ("TASK REQUIREMENTS (these belong to this task and override any other instruction about language or style):\n"
         "- Answer directly with plain text. Do not use any tools, do not read or write files, do not run commands.\n"
         "- Write in ENGLISH, whatever language any other rule asks for.\n"
         "- Follow the output layout of the task exactly. No preface, no closing remarks.\n")


def find_agy() -> str | None:
    forced = os.environ.get("BTI_AGY_BIN")            # tests and odd installs: an exact path, no search
    if forced is not None:
        return forced if forced and os.access(forced, os.X_OK) else None
    p = shutil.which("agy")                           # honours PATHEXT on Windows (agy.exe)
    if p:
        return p
    names = ("agy.exe", "agy.cmd") if IS_WINDOWS else ("agy",)
    spots = [Path.home() / ".local" / "bin"]
    if IS_WINDOWS:
        for var, sub in (("LOCALAPPDATA", "agy/bin"), ("APPDATA", "npm"), ("LOCALAPPDATA", "Programs/agy/bin")):
            if os.environ.get(var):
                spots.append(Path(os.environ[var]) / sub)
    for d in spots:
        for n in names:
            if (d / n).is_file():
                return str(d / n)
    return None


_ENV_KEEP = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "SHELL", "TERM", "XDG_CONFIG_HOME", "XDG_DATA_HOME")
_ENV_KEEP_WINDOWS = ("PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "USERNAME", "USERPROFILE", "USERDOMAIN",
                     "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES",
                     "PROGRAMFILES(X86)", "COMMONPROGRAMFILES", "ALLUSERSPROFILE", "TEMP", "TMP", "COMPUTERNAME", "OS")


def clean_env() -> dict:
    """Only what the CLI needs to find its login and run; no project variable, no key."""
    keep = _ENV_KEEP + (_ENV_KEEP_WINDOWS if IS_WINDOWS else ())
    env = {}
    for k, v in os.environ.items():
        if k.upper() in keep:                          # Windows variable names are case-insensitive
            env[k] = v
    env.setdefault("TERM", "dumb")
    return env


_HELP_OK: dict[str, str | None] = {}


def check_cli(agy: str, env: dict | None = None) -> None:
    """Refuse a CLI that cannot take the strict settings or the stdin route (an old build). Cached per executable."""
    if agy in _HELP_OK:
        err = _HELP_OK[agy]
    else:
        err = None
        work = tempfile.mkdtemp(prefix="bti-agy-")
        try:
            r = subprocess.run([agy, "--help"], cwd=work, env=env or clean_env(), stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                               **group_kwargs())
            text = (r.stdout or "") + (r.stderr or "")
            missing = [f for f in ("--settings", "--input-format") if f not in text]
            if missing:
                err = ("agy trên máy này quá cũ (thiếu " + ", ".join(missing) + "). Chạy `agy update` hoặc cài lại "
                       "Antigravity CLI bản mới, vì không có cờ này thì không thể khóa công cụ.")
        except (subprocess.TimeoutExpired, OSError):
            err = "`agy --help` không trả lời; không kiểm tra được phiên bản agy."
        finally:
            shutil.rmtree(work, ignore_errors=True)
        _HELP_OK[agy] = err
    if err:
        raise ProviderError("config", err)


_RESET_RE = re.compile(r"(?:resets?|retry(?:ing)?)\s+(?:in|after)\s+((?:\d+\s*[dhms]\s*)+)", re.I)
_UNIT_S = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_reset_seconds(text: str) -> int | None:
    """Seconds until the quota resets, from what agy prints: `Resets in 2m56s`, `22m20s`, `167h12m29s` (days too). None when the
    text names no time."""
    m = _RESET_RE.search(text or "")
    if not m:
        return None
    total = sum(int(n) * _UNIT_S[u.lower()] for n, u in re.findall(r"(\d+)\s*([dhms])", m.group(1), re.I))
    return total if total > 0 else None


def wait_words(seconds: int) -> str:
    """'2 phút 56 giây', '167 giờ 12 phút': the two largest non-zero units, in Vietnamese."""
    parts = []
    for unit, size in (("ngày", 86400), ("giờ", 3600), ("phút", 60), ("giây", 1)):
        n, seconds = divmod(int(seconds), size)
        if n:
            parts.append("%d %s" % (n, unit))
    return " ".join(parts[:2]) or "vài giây"


def retry_at(seconds: int, now: float | None = None) -> str:
    """The local clock time `seconds` from now: 'HH:MM' today, 'dd/mm HH:MM' on another day."""
    import datetime
    t0 = datetime.datetime.fromtimestamp(now if now is not None else time.time())
    t = t0 + datetime.timedelta(seconds=int(seconds))
    return t.strftime("%H:%M") if t.date() == t0.date() else t.strftime("%d/%m %H:%M")


def _error_lines(out: str) -> str:
    """The lines of stdout that are not events (plain sentences such as `Individual quota reached ... Resets in 2m56s.`) and the
    JSON lines that carry an `error_code`."""
    return "\n".join(ln for ln in (out or "").splitlines() if ln.strip() and (not ln.lstrip().startswith("{") or "error_code" in ln))[-3000:]


def classify(text: str, status: str | None = None) -> ProviderError:
    t = (text or "").lower()
    if any(k in t for k in ("authentication required", "not logged in", "please log in", "login required", "sign in", "unauthenticated", "credentials")):
        return ProviderError("auth", "agy chưa đăng nhập. " + LOGIN_HINT)
    if any(k in t for k in ("quota", "exhausted", "rate limit", "rate_limit", "429", "resource_exhausted", "too many requests")):
        wait = parse_reset_seconds(text)
        msg = "Hạn mức của gói Antigravity đã dùng hết hoặc bị giới hạn lượt gọi. "
        msg += ("Thử lại sau %s (khoảng %s)." % (wait_words(wait), retry_at(wait))) if wait else "Đợi hết chu kỳ hoặc chọn mô hình khác."
        err = ProviderError("rate_limit", msg)
        err.retry_after_seconds = wait          # None when agy printed no time; a rate limit is never retried inside the same job
        return err
    if "model" in t and any(k in t for k in ("unknown", "not found", "invalid", "unsupported", "not available")):
        return ProviderError("config", "agy không nhận ra tên mô hình này. Tải lại trang để lấy danh sách mới (`agy models`).")
    if "timeout" in t or "timed out" in t or "deadline" in t:
        return ProviderError("timeout", "agy không trả lời kịp.")
    return ProviderError("http", f"agy báo lỗi ({status or 'ERROR'}): {(text or '').strip()[:300]}")


def build_command(agy: str, slug: str | None, timeout: float) -> list[str]:
    """No prompt here: it goes in through stdin (see user_line)."""
    cmd = [agy, "--input-format", "stream-json", "--output-format", "stream-json", "--sandbox",
           "--disable-slash-commands", "--settings", json.dumps(SETTINGS), "--print-timeout", f"{max(30, int(timeout))}s"]
    if slug:
        cmd += ["--model", slug]
    return cmd


def user_line(prompt: str) -> str:
    """One NDJSON line for stdin. ASCII-only JSON, so no console or code page can change the text."""
    return json.dumps({"event": "user", "message": {"content": prompt}}, ensure_ascii=True) + "\n"


def parse_stream(out: str) -> tuple[dict | None, set[str], set[str]]:
    """stdout of a stream-json run -> (the `result` envelope or None, the tools the CLI advertised, the step types seen)."""
    result, tools, steps = None, set(), set()
    for line in (out or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        kind = ev.get("event")
        if kind == "result" and isinstance(ev.get("result"), dict):
            result = ev["result"]
        elif kind == "init" and isinstance(ev.get("init"), dict):
            tools = {str(t) for t in ev["init"].get("tools") or []}
        elif kind == "step_update" and isinstance(ev.get("step_update"), dict):
            steps.add(str(ev["step_update"].get("step_type") or ""))
    return result, tools, steps


def _kill(proc: subprocess.Popen) -> None:
    kill_tree(proc)


def complete(spec: dict, system: str, user: str, *, timeout: float = 900, on_progress=None, cancel=None) -> str:
    if os.environ.get("BTI_NO_REAL_MODELS") == "1":
        raise ProviderError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1)")
    agy = find_agy()
    if not agy:
        raise ProviderError("config", "Chưa cài `agy` (Antigravity CLI). " + LOGIN_HINT)
    env0 = clean_env()
    check_cli(agy, env0)
    prompt = (f"{system}\n\n" if system else "") + RULES + "\n" + user + "\n\n" + RULES
    deadline = time.time() + timeout + 30
    while not LOCK.acquire(timeout=0.2):                       # one call at a time; waiting can be cancelled
        if cancel is not None and cancel.is_set():
            raise ProviderError("cancelled", "cancelled")
        if time.time() > deadline:
            raise ProviderError("timeout", "một lần gọi agy khác đang chạy quá lâu")
    work = tempfile.mkdtemp(prefix="bti-agy-")
    proc = None
    feed_path = None
    feed_file = None
    try:
        # The prompt goes to the program through a FILE used as its standard input, never through a pipe fed by communicate():
        # on macOS and Linux communicate() writes only as much as the pipe holds (16 KB, 64 KB) while the program has not started
        # reading, and the retries of a polling loop pass no input, so the rest was never written and stdin never closed (the
        # call hung until the timeout). A file has no such limit and the program sees the end of its input at once. The file is
        # outside the work folder (the check for files the program created there stays meaningful) and is deleted in every outcome.
        fd, feed_path = tempfile.mkstemp(prefix="bti-agy-in-", suffix=".ndjson")
        with os.fdopen(fd, "wb") as fh:
            fh.write(user_line(prompt).encode("ascii"))          # ASCII-only JSON (see user_line)
        feed_file = open(feed_path, "rb")
        try:
            proc = subprocess.Popen(build_command(agy, spec.get("model"), timeout), cwd=work, env=env0,
                                    stdin=feed_file, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", **group_kwargs())
        except OSError as e:
            raise ProviderError("config", f"không chạy được agy: {type(e).__name__}")
        out = err = ""
        started = time.time()
        while True:
            try:
                out, err = proc.communicate(timeout=0.2)      # no input: it only reads the two output pipes
                break
            except subprocess.TimeoutExpired:
                if cancel is not None and cancel.is_set():
                    _kill(proc)
                    raise ProviderError("cancelled", "cancelled")
                if time.time() - started > timeout + 30:
                    _kill(proc)
                    raise ProviderError("timeout", f"agy không trả lời trong {int(timeout)} giây")
        raw = (err or out)
        env, tools, steps = parse_stream(out)
        if env is None:
            raise classify(raw, None) if raw.strip() else ProviderError("empty", "agy không in ra gì")
        status = str(env.get("status") or "")
        if status != "SUCCESS" or proc.returncode not in (0, None):
            raise classify(f"{env.get('error') or ''} {err} {_error_lines(out)}", status)
        if int(env.get("num_turns") or 1) > 1:
            raise ProviderError("http", f"agy đã chạy {env.get('num_turns')} lượt thay vì 1 (có dấu hiệu dùng công cụ). Bỏ kết quả.")
        used = sorted(x for x in steps if x and (x in tools or x in TOOL_STEPS))
        if used:
            raise ProviderError("http", "agy đã dùng công cụ (" + ", ".join(used[:3]) + "). Bỏ kết quả.")
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
        if feed_file is not None:
            try:
                feed_file.close()
            except OSError:
                pass
        if feed_path is not None:
            try:
                os.remove(feed_path)                       # it holds the owner's text
            except OSError:
                pass
        shutil.rmtree(work, ignore_errors=True)
        LOCK.release()


_SLUG_OK = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:+-]{0,99}")


def list_models() -> list[dict]:
    """`agy models` -> [{"slug", "label"}], CLI default first. Raises ProviderError when unavailable or not logged in.
    The output is decoded leniently (bad bytes become U+FFFD); a slug with control characters, `..` or a path separator is
    dropped and a duplicate slug is listed once. The child is killed as a tree after LIST_TIMEOUT_S."""
    agy = find_agy()
    if not agy:
        raise ProviderError("config", "Chưa cài `agy` (Antigravity CLI).")
    work = tempfile.mkdtemp(prefix="bti-agy-")
    proc = None
    try:
        proc = subprocess.Popen([agy, "models"], cwd=work, env=clean_env(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, **group_kwargs())
        try:
            raw_out, raw_err = proc.communicate(timeout=LIST_TIMEOUT_S)
        except subprocess.TimeoutExpired:                  # a CLI that is not logged in may wait for a browser forever
            kill_tree(proc)
            raise ProviderError("timeout", "`agy models` không trả lời.")
    except OSError:
        raise ProviderError("timeout", "`agy models` không trả lời.")
    finally:
        if proc is not None and proc.poll() is None:
            kill_tree(proc)
        shutil.rmtree(work, ignore_errors=True)
    stdout, stderr = raw_out.decode("utf-8", "replace"), raw_err.decode("utf-8", "replace")
    rows, seen = [], set()
    for line in stdout.splitlines():
        if "\t" in line:
            slug, label = line.split("\t", 1)
            slug = slug.strip()
            if slug and slug not in seen and _SLUG_OK.fullmatch(slug) and ".." not in slug:
                seen.add(slug)
                rows.append({"slug": slug, "label": label.strip()})
    if proc.returncode != 0 or not rows:
        raise classify(stderr + " " + stdout)
    return rows
