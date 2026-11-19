"""Claude Code (`claude`) run headless as a plain text generator, under the owner's own Claude plan.

Model ids of this family are `claude:<model>@<effort>` (for example `claude:claude-opus-5-5@high`): `--model <model>` and
`--effort <effort>`. This module is the only place that parses such an id (`parse_model_id`), finds the program, builds its
environment, recognises its failures and answers "is it installed and signed in" (`auth_status`) without a model call.

One call, text in and text out. The program is an agent that could read files, run commands and load the signed-in user's own
set-up. We want a completion that is the same on every machine, so all of that is switched off in layers (the exact command is
`build_command`, and tests/script/test_claudecode.py inspects it):
  * `--tools ""`: no built-in tool exists, so there is nothing to approve and nothing to deny;
  * `--safe-mode`: no CLAUDE.md, hooks, skills, plugins, MCP servers, custom commands or agents, output styles, auto memory;
  * `--setting-sources ""`, `--strict-mcp-config`, `--disable-slash-commands`: the settings files of the user, the project and
    the folder load nothing and no MCP server connects;
  * `--no-session-persistence`: nothing is written to the program's session folder;
  * `--permission-mode dontAsk`: anything that would ask is refused (never `--dangerously-skip-permissions`);
  * `--system-prompt`: the `system` text REPLACES the default Claude Code prompt;
  * the working directory is a fresh EMPTY temporary folder outside the repo, deleted afterwards;
  * the environment holds only what the program needs to find its login: no project variable, no API key (a key in the
    environment would turn a plan call into a paid call, so it is never passed on).
The prompt goes in through standard input, never as an argument (a Windows command line stops at about 32,000 characters and our
prompts reach 60,000). The answer is the `result` of `--output-format json`. No fallback to any paid API.
"""
from __future__ import annotations

import datetime
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
from .antigravity import retry_at, wait_words

FAMILY = "claude"
EFFORTS = ("low", "medium", "high", "xhigh", "max")
ID_RE = re.compile(r"claude:([A-Za-z0-9][A-Za-z0-9._-]{0,79})@(low|medium|high|xhigh|max)")
MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
STATUS_TIMEOUT_S = 15                  # `claude auth status` is a local check: it answers quickly or the page must not wait for it
HELP_TIMEOUT_S = 30
LOCK = threading.Lock()                # one Claude Code call at a time
LOGIN_COMMAND = "claude auth login"
LOGIN_HINT = ("Claude Code trên máy chủ chưa đăng nhập. Hãy đăng nhập một lần trên máy chủ bằng lệnh `%s`, rồi thử lại." % LOGIN_COMMAND)
MISSING_HINT = "Chưa cài Claude Code (lệnh `claude`) trên máy này. Cài Claude Code rồi đăng nhập một lần bằng lệnh `%s`." % LOGIN_COMMAND
# Options the isolation below needs. A build of the program without one of them is refused instead of run half-open.
REQUIRED_FLAGS = ("--safe-mode", "--setting-sources", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
                  "--tools", "--permission-mode", "--system-prompt", "--output-format", "--model", "--effort")


def _err(kind: str, message: str, code: str) -> ProviderError:
    """A ProviderError that also carries the owner-facing `code` of this runner (bti/draft/run.py has the sentence of each code)."""
    e = ProviderError(kind, message)
    e.code = code
    return e


# ------------------------------------------------------------------------------------------------ the model id family
def parse_model_id(model_id) -> tuple[str, str] | None:
    """`claude:<model>@<effort>` -> (model, effort); None for any other string. The ONE parser of the family."""
    m = ID_RE.fullmatch(model_id) if isinstance(model_id, str) else None
    return (m.group(1), m.group(2)) if m else None


def make_model_id(model: str, effort: str) -> str:
    return f"{FAMILY}:{model}@{effort}"


def is_claude_id(model_id) -> bool:
    return parse_model_id(model_id) is not None


def label_for(model: str, effort: str) -> str:
    """The label of an id that no tracked entry names."""
    return f"Claude Code: {model} ({effort})"


# ------------------------------------------------------------------------------------------------ the program
def find_claude() -> str | None:
    forced = os.environ.get("BTI_CLAUDE_BIN")          # tests and odd installs: an exact path, no search
    if forced is not None:
        return forced if forced and os.access(forced, os.X_OK) else None
    p = shutil.which("claude")                          # honours PATHEXT on Windows (claude.exe, claude.cmd)
    if p:
        return p
    names = ("claude.exe", "claude.cmd") if IS_WINDOWS else ("claude",)
    home = Path.home()
    spots = [home / ".local" / "bin", home / ".claude" / "local"]
    if IS_WINDOWS:
        for var, sub in (("APPDATA", "npm"), ("LOCALAPPDATA", "Programs/claude"), ("LOCALAPPDATA", "Claude/bin")):
            if os.environ.get(var):
                spots.append(Path(os.environ[var]) / sub)
    else:
        spots += [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    for d in spots:
        for n in names:
            if (d / n).is_file():
                return str(d / n)
    return None


_ENV_KEEP = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "SHELL", "TERM", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TMPDIR",
             # where the program keeps its login, and the owner's own long-lived plan token when they use one
             "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN",
             # the network set-up of the machine (a proxy, a company certificate)
             "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "ALL_PROXY", "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE")
_ENV_KEEP_WINDOWS = ("PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "USERNAME", "USERPROFILE", "USERDOMAIN",
                     "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES",
                     "PROGRAMFILES(X86)", "COMMONPROGRAMFILES", "ALLUSERSPROFILE", "TEMP", "TMP", "COMPUTERNAME", "OS",
                     "CLAUDE_CODE_GIT_BASH_PATH")


def clean_env() -> dict:
    """Only what the program needs to find its login and run. Never ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN or a base URL: any of
    them would send the call to a paid API or another provider instead of the owner's plan."""
    keep = _ENV_KEEP + (_ENV_KEEP_WINDOWS if IS_WINDOWS else ())
    env = {k: v for k, v in os.environ.items() if k.upper() in keep}      # Windows variable names are case-insensitive
    env.setdefault("TERM", "dumb")
    return env


_HELP_OK: dict[tuple, str | None] = {}


def check_cli(claude: str, env: dict | None = None, needed: tuple = REQUIRED_FLAGS) -> None:
    """Refuse a build of the program that lacks an option the isolation needs. Cached per executable and option list."""
    key = (claude, needed)
    if key in _HELP_OK:
        err = _HELP_OK[key]
    else:
        err = None
        work = tempfile.mkdtemp(prefix="bti-claude-")
        try:
            r = subprocess.run([claude, "--help"], cwd=work, env=env or clean_env(), stdin=subprocess.DEVNULL, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=HELP_TIMEOUT_S, **group_kwargs())
            text = (r.stdout or "") + (r.stderr or "")
            missing = [f for f in needed if f not in text]
            if missing:
                err = ("Claude Code trên máy này quá cũ (thiếu " + ", ".join(missing) + "). Chạy `claude update` để cập nhật, vì không có "
                       "các tùy chọn này thì không thể khóa công cụ và tách khỏi cài đặt riêng của người dùng.")
        except (subprocess.TimeoutExpired, OSError):
            err = "`claude --help` không trả lời; không kiểm tra được phiên bản Claude Code."
        finally:
            shutil.rmtree(work, ignore_errors=True)
        _HELP_OK[key] = err
    if err:
        raise _err("config", err, "claude_config")


# A `.cmd` or `.bat` file (the npm shim of Windows) is run through cmd.exe, which re-reads the command line: these characters would
# be taken for syntax. Nothing of ours contains them, except possibly the system text: then that text moves to the standard input.
_CMD_UNSAFE = re.compile(r'["%^&|<>!\r\n]')


def is_shim(exe: str) -> bool:
    return IS_WINDOWS and str(exe).lower().endswith((".cmd", ".bat"))


def arg_ok_for(exe: str, arg: str) -> bool:
    return not (is_shim(exe) and (_CMD_UNSAFE.search(arg) or len(arg) > 4000))


# ------------------------------------------------------------------------------------------------ the command
def isolation_args() -> list[str]:
    """What keeps the signed-in user's own Claude Code set-up out (shared with the agent in a folder)."""
    return ["--safe-mode", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"]


def build_command(claude: str, model: str, effort: str, system: str | None = None) -> list[str]:
    """No prompt here: it goes in through standard input (see `complete`). `system` replaces the default system prompt."""
    cmd = [claude, "-p", "--model", model, "--effort", effort, "--output-format", "json", "--tools", ""]
    cmd += isolation_args()
    cmd += ["--permission-mode", "dontAsk"]
    if system:
        cmd += ["--system-prompt", system]
    return cmd


# ------------------------------------------------------------------------------------------------ when the plan is used up
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
_UNIT_S = {"d": 86400, "h": 3600, "m": 60, "s": 1}
_IN_RE = re.compile(r"\bresets?\s+(?:in\s+)?((?:\d+\s*(?:days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b[\s,]*(?:and\s+)?)+)", re.I)
_AT_RE = re.compile(r"\bresets?\s+(?:at\s+)?(?:(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?,?\s*(?:at\s+)?)?"
                    r"(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>am|pm)?(?:\s*\((?P<tz>[A-Za-z][A-Za-z0-9_/+-]*)\))?", re.I)
_EPOCH_RE = re.compile(r"limit reached\s*\|\s*(\d{9,11})\b", re.I)


def _zone(name: str | None):
    if name:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name)
        except Exception:      # noqa: BLE001 - no tz database on this machine (Windows without tzdata): the local clock it is
            pass
    return None


def parse_reset_seconds(text: str, now: float | None = None) -> int | None:
    """Seconds until the plan's limit opens again, from what Claude Code prints: `You've hit your session limit · resets 7pm`,
    `resets 1:50am (Asia/Tokyo)`, `resets Nov 25 at 3pm (Europe/Paris)`, `resets in 4 hr 30 min`, or the older
    `Claude AI usage limit reached|1760000000` (an epoch). None when the text names no time."""
    text = text or ""
    now = time.time() if now is None else now
    m = _EPOCH_RE.search(text)
    if m:
        wait = int(m.group(1)) - int(now)
        return wait if wait > 0 else None
    m = _IN_RE.search(text)
    if m:
        total = 0
        for n, u in re.findall(r"(\d+)\s*(days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b", m.group(1), re.I):
            total += int(n) * _UNIT_S[u[0].lower()]
        return total or None
    m = _AT_RE.search(text)
    if not m:
        return None
    ap, hh, mm = (m.group("ap") or "").lower(), int(m.group("h")), m.group("m")
    if not ap and mm is None:                            # "resets 7" is not a time
        return None
    if ap:
        if not 1 <= hh <= 12:
            return None
        hh = hh % 12 + (12 if ap == "pm" else 0)
    elif hh > 23:
        return None
    tz = _zone(m.group("tz"))
    t0 = datetime.datetime.fromtimestamp(now, tz)
    try:
        if m.group("mon"):
            when = t0.replace(month=_MONTHS[m.group("mon").lower()[:3]], day=int(m.group("day")), hour=hh, minute=int(mm or 0), second=0, microsecond=0)
            if when <= t0:
                when = when.replace(year=t0.year + 1)
        else:
            when = t0.replace(hour=hh, minute=int(mm or 0), second=0, microsecond=0)
            if when <= t0:
                when += datetime.timedelta(days=1)
    except ValueError:
        return None
    wait = int(when.timestamp() - now)
    return wait if wait > 0 else None


def reset_from_events(events: list[dict]) -> int | None:
    """The stream-json `rate_limit_event` of a refused request carries the reset as an epoch (`resetsAt`): exact, so it wins over the text."""
    for ev in reversed(events or []):
        info = ev.get("rate_limit_info") if isinstance(ev, dict) and ev.get("type") == "rate_limit_event" else None
        if isinstance(info, dict) and str(info.get("status") or "").lower().startswith("rejected"):
            try:
                wait = int(float(info.get("resetsAt")) - time.time())
            except (TypeError, ValueError):
                continue
            if wait > 0:
                return wait
    return None


def quota_message(wait: int | None) -> str:
    msg = "Hạn mức của gói Claude Code đã dùng hết hoặc bị giới hạn lượt gọi. "
    return msg + (("Thử lại sau %s (khoảng %s)." % (wait_words(wait), retry_at(wait))) if wait else "Đợi hết chu kỳ rồi thử lại.")


_AUTH_RE = re.compile(r"not logged in|please run /login|run /login|login required|login expired|invalid api key|oauth token|authentication[_ ]failed|"
                      r"authentication_error|invalid authentication credentials|failed to authenticate|unauthenticated|\b401\b|sign in", re.I)
_LIMIT_RE = re.compile(r"hit your[^.\n]{0,30}limit|usage limit|limit reached|rate[ _-]?limit|too many requests|\b429\b|quota|"
                       r"temporarily limiting|resource_exhausted|exceeded your", re.I)
_MODEL_RE = re.compile(r"selected model|not a recognized model|model[^.\n]{0,120}(?:not found|does not exist|doesn't exist|may not exist|invalid|unknown|unsupported|not available)|"
                       r"not_found_error|invalid model|model_not_found", re.I)
_TIME_RE = re.compile(r"timed out|timeout|deadline", re.I)
# The installed Claude Code is too old for the model asked: `Claude Code 2.1.233 does not support this model; version 2.1.280 or newer is
# required. Run 'claude update'` (answer of a real call on the server, 2026-11-18). Not a quota, not an unknown model: the advice is to update.
_OUTDATED_NEEDED_RE = re.compile(r"\b(?:version|v)\s*(\d+(?:\.\d+)+)\s+or\s+(?:newer|later|higher|above)\b|"
                                r"\brequires?\s+(?:claude code\s+)?(?:version\s+|v)?(\d+(?:\.\d+)+)\s+or\s+(?:newer|later|higher|above)\b", re.I)
_OUTDATED_NOW_RE = re.compile(r"\bclaude code\s+v?(\d+(?:\.\d+)+)", re.I)
_OUTDATED_NOSUPPORT_RE = re.compile(r"does not support (?:this|the selected|the requested) model", re.I)
OUTDATED_HEAD = "Claude Code trên máy chủ quá cũ cho mô hình này"


def outdated_versions(text: str) -> tuple[str | None, str | None] | None:
    """(needed, current) version texts of a "Claude Code is too old for this model" answer, each None when the answer does not state it;
    None when the text is not such an answer. The answer must name Claude and either say which version it needs or say the model is not
    supported together with a version of Claude Code or the `claude update` command (a bare "does not support this model" is not enough)."""
    text = text or ""
    if "claude" not in text.lower():
        return None
    m = _OUTDATED_NEEDED_RE.search(text)
    needed = (m.group(1) or m.group(2)) if m else None
    current = next((m.group(1) for m in _OUTDATED_NOW_RE.finditer(text)       # "Claude Code 2.1.233 does not ...", not "requires Claude Code 2.1.280 or newer"
                    if not re.search(r"requires?\s+$", text[:m.start()], re.I) and not re.match(r"\s+or\s+(?:newer|later|higher|above)\b", text[m.end():], re.I)), None)
    if needed or (_OUTDATED_NOSUPPORT_RE.search(text) and (current or re.search(r"claude\s+update", text, re.I))):
        return needed, current
    return None


def outdated_message(needed: str | None = None, current: str | None = None) -> str:
    """The owner's sentence for the code `claude_outdated`; a version the answer did not state is left out."""
    facts = [x for x in ((f"cần bản {needed} trở lên" if needed else ""), (f"đang là {current}" if current else "")) if x]
    return OUTDATED_HEAD + (f" ({', '.join(facts)})" if facts else "") + ". Chạy `claude update` trên máy chủ rồi thử lại."


def classify(text: str, events: list[dict] | None = None, api_status=None) -> ProviderError:
    """One failure text of the program -> the ProviderError kind the rest of the app already knows."""
    text = (text or "").strip()
    old = outdated_versions(text)
    if old is not None:               # first: it must not be taken for an unknown model (status 404) or a limit, the advice is `claude update`
        err = _err("config", outdated_message(*old), "claude_outdated")
        err.versions = old
        return err
    limited = bool(_LIMIT_RE.search(text)) or api_status == 429
    if not limited and (api_status in (401, 403) or _AUTH_RE.search(text)):
        return _err("auth", LOGIN_HINT, "claude_auth")
    if limited:
        wait = reset_from_events(events or []) or parse_reset_seconds(text)
        err = _err("rate_limit", quota_message(wait), "claude_rate_limit")
        err.retry_after_seconds = wait          # None when the program printed no time; a rate limit is never retried inside the same job
        return err
    if api_status == 404 or _MODEL_RE.search(text):
        return _err("config", "Claude Code không nhận ra tên mô hình này. Chọn mô hình khác trong danh sách.", "claude_model")
    if _TIME_RE.search(text):
        return _err("timeout", "Claude Code không trả lời kịp.", "claude_timeout")
    return _err("http", f"Claude Code báo lỗi: {text[:300] or 'không rõ nguyên nhân'}", "claude_error")


# ------------------------------------------------------------------------------------------------ is it installed and signed in
def auth_status(claude: str | None = None) -> bool:
    """True when `claude auth status` says signed in. No model call. Raises ProviderError: `config` (not installed, or it cannot be
    asked), `auth` (not signed in), `timeout`. Only the `loggedIn` flag is read: the rest of the answer (the account's e-mail
    among it) is never kept, returned or logged."""
    claude = claude or find_claude()
    if not claude:
        raise _err("config", MISSING_HINT, "claude_missing")
    work = tempfile.mkdtemp(prefix="bti-claude-")
    proc = None
    try:
        proc = subprocess.Popen([claude, "auth", "status"], cwd=work, env=clean_env(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, **group_kwargs())
        try:
            raw_out, _raw_err = proc.communicate(timeout=STATUS_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            raise ProviderError("timeout", "`claude auth status` không trả lời.")
    except OSError:
        raise ProviderError("config", "Không chạy được lệnh `claude` trên máy này.")
    finally:
        if proc is not None and proc.poll() is None:
            kill_tree(proc)
        shutil.rmtree(work, ignore_errors=True)
    flag = None
    try:
        data = json.loads(raw_out.decode("utf-8", "replace"))
        if isinstance(data, dict) and isinstance(data.get("loggedIn"), bool):
            flag = data["loggedIn"]
    except ValueError:
        pass
    if flag is None:
        raise ProviderError("config", "`claude auth status` cho kết quả không đọc được. Cập nhật Claude Code (`claude update`).")
    if not flag:
        raise ProviderError("auth", LOGIN_HINT)
    return True


def availability() -> dict:
    """{"ok": bool, "kind": None | "config" | "auth" | "timeout", "message": str | None, "reason": "not_installed" | "not_signed_in" | ...}.
    Never raises. `BTI_NO_REAL_MODELS=1` answers without starting the program (tests, safe mode of the build)."""
    if os.environ.get("BTI_NO_REAL_MODELS") == "1":
        return {"ok": False, "kind": "config", "reason": "real_models_off",
                "message": "Đang tắt việc gọi mô hình thật (chế độ thử), nên chưa kiểm tra Claude Code."}
    claude = find_claude()
    if not claude:
        return {"ok": False, "kind": "config", "reason": "not_installed", "message": MISSING_HINT}
    try:
        auth_status(claude)
        return {"ok": True, "kind": None, "reason": None, "message": None}
    except ProviderError as e:
        reason = {"auth": "not_signed_in", "timeout": "timeout"}.get(e.kind, "unreadable" if "không đọc được" in e.message else "not_installed")
        return {"ok": False, "kind": e.kind, "reason": reason, "message": e.message}
    except Exception:      # noqa: BLE001 - the list can never break a request
        return {"ok": False, "kind": "http", "reason": "unreadable", "message": "Không kiểm tra được Claude Code."}


# ------------------------------------------------------------------------------------------------ one call
def parse_result(out: str) -> dict | None:
    """stdout of `--output-format json` -> the result object (the program prints one object; some builds print the whole event list)."""
    out = (out or "").strip()
    if not out:
        return None
    try:
        data = json.loads(out)
    except ValueError:
        for line in reversed(out.splitlines()):          # a warning line before the object, or a stream of lines
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    break
                except ValueError:
                    continue
        else:
            return None
    if isinstance(data, list):
        data = next((e for e in reversed(data) if isinstance(e, dict) and e.get("type") == "result"), None)
    return data if isinstance(data, dict) and data.get("type", "result") == "result" else None


def _kill(proc: subprocess.Popen) -> None:
    kill_tree(proc)


def complete(spec: dict, system: str, user: str, *, timeout: float = 900, on_progress=None, cancel=None) -> str:
    if os.environ.get("BTI_NO_REAL_MODELS") == "1":
        raise ProviderError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1)")
    model, effort = spec.get("model"), spec.get("effort")
    if not (isinstance(model, str) and MODEL_RE.fullmatch(model) and effort in EFFORTS):
        raise _err("config", "Tên mô hình hoặc mức nỗ lực của Claude Code không hợp lệ.", "claude_model")
    claude = find_claude()
    if not claude:
        raise _err("config", MISSING_HINT, "claude_missing")
    env0 = clean_env()
    check_cli(claude, env0)
    prompt = user
    sys_text = (system or "").strip() or None
    if sys_text and not arg_ok_for(claude, sys_text):      # cmd.exe would re-read it: it goes in with the task instead
        prompt, sys_text = f"{sys_text}\n\n{user}", None
    deadline = time.time() + timeout + 30
    while not LOCK.acquire(timeout=0.2):                       # one call at a time; waiting can be cancelled
        if cancel is not None and cancel.is_set():
            raise ProviderError("cancelled", "cancelled")
        if time.time() > deadline:
            raise ProviderError("timeout", "một lần gọi Claude Code khác đang chạy quá lâu")
    work = tempfile.mkdtemp(prefix="bti-claude-")
    proc = None
    feed_path = None
    feed_file = None
    try:
        # The prompt goes to the program through a FILE used as its standard input, never through a pipe fed by communicate() (which on
        # macOS and Linux writes only as much as the pipe holds while the program has not started reading, and a polling loop passes
        # no input again). A file has no such limit and the program sees the end of its input at once. It is outside the work folder
        # (so "the folder is still empty" stays meaningful) and is deleted in every outcome: it holds the owner's text.
        fd, feed_path = tempfile.mkstemp(prefix="bti-claude-in-", suffix=".txt")
        with os.fdopen(fd, "wb") as fh:
            fh.write(prompt.encode("utf-8"))
        feed_file = open(feed_path, "rb")
        try:
            proc = subprocess.Popen(build_command(claude, model, effort, sys_text), cwd=work, env=env0, stdin=feed_file,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                    **group_kwargs())
        except OSError as e:
            raise _err("config", f"không chạy được Claude Code: {type(e).__name__}", "claude_config")
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
                if time.time() - started > timeout:
                    _kill(proc)
                    raise _err("timeout", f"Claude Code không trả lời trong {int(timeout)} giây", "claude_timeout")
        res = parse_result(out)
        if res is None:
            raise classify(err or out) if (err or out).strip() else _err("empty", "Claude Code không in ra gì", "claude_no_result")
        text = str(res.get("result") or "")
        if res.get("is_error") or (proc.returncode not in (0, None)):
            raise classify(f"{text} {err}", None, res.get("api_error_status"))
        if str(res.get("subtype") or "success") != "success":
            raise classify(f"{res.get('subtype')} {text} {err}", None, res.get("api_error_status"))
        if res.get("permission_denials"):
            raise _err("http", "Claude Code báo đã bị từ chối khi cố dùng công cụ. Bỏ kết quả để không nhận đầu ra không đáng tin.", "claude_error")
        if int(res.get("num_turns") or 1) > 1:
            raise _err("http", f"Claude Code đã chạy {res.get('num_turns')} lượt thay vì 1 (có dấu hiệu dùng công cụ). Bỏ kết quả.", "claude_error")
        if os.listdir(work):
            raise _err("http", "Claude Code đã tạo tệp trong thư mục làm việc (dùng công cụ). Bỏ kết quả.", "claude_error")
        if not text.strip():
            raise _err("empty", "Claude Code không trả lời bằng chữ", "claude_no_result")
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
