#!/usr/bin/env bash
# tools/deploy/snapshot_py.sh NAME <python arguments>
# Runs `python <arguments>` in the server's .venv with working directory
# D:\code\behind-the-image\run\snap-NAME, UTF-8 streaming output.
# Environment: PYTHONUTF8=1, PYTHONUNBUFFERED=1, PYTHONDONTWRITEBYTECODE=1, BTI_NO_REAL_MODELS=1
set -uo pipefail

NAME="${1:-}"
if [[ -z "$NAME" || ! "$NAME" =~ ^[a-z0-9-]{1,24}$ ]]; then
  echo "Usage: $0 NAME <python arguments> (where NAME matches [a-z0-9-]{1,24})" >&2
  exit 2
fi
shift

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/tools/deploy"
. "$HERE/lib.sh"

SNAP_DIR="$RW\\run\\snap-$NAME"

# Verify snapshot exists
if ! rssh "if not exist $SNAP_DIR exit 1"; then
  echo "Error: snapshot '$NAME' does not exist at $SNAP_DIR. Sync it first with snapshot_test.sh." >&2
  exit 1
fi

ID="$(date +%Y%m%d%H%M%S)-$$"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Generate args.json
python3 - "$TMP/args.json" "$SNAP_DIR" "$@" <<'PY'
import json, sys
json.dump({"cwd": sys.argv[2], "argv": sys.argv[3:]}, open(sys.argv[1], "w", encoding="utf-8"))
PY

# Generate runner script
cat <<'PY' > "$TMP/snap_run.py"
import json
import os
import subprocess
import sys

def main() -> int:
    if len(sys.argv) < 2:
        return 1
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        spec = json.load(f)

    cwd = spec["cwd"]
    argv = spec["argv"]

    env = dict(
        os.environ,
        PYTHONUTF8="1",
        PYTHONUNBUFFERED="1",
        PYTHONDONTWRITEBYTECODE="1",
        BTI_NO_REAL_MODELS="1",
        PYTHONIOENCODING="utf-8",
        PYTHONPATH=cwd,
        HF_HOME=r"D:\code\behind-the-image\cache\hf",
        HF_HUB_DISABLE_TELEMETRY="1",
    )

    py = r"D:\code\behind-the-image\.venv\Scripts\python.exe"
    p = subprocess.Popen(
        [py] + argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

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
PY

rscp "$TMP/args.json" "$HOST:$REMOTE/run/snap-args-$ID.json" || exit 255
rscp "$TMP/snap_run.py" "$HOST:$REMOTE/run/snap-run-$ID.py" || exit 255

ssh -o ConnectTimeout=20 -o BatchMode=yes -o ServerAliveInterval=30 "$HOST" \
  "$RW\\.venv\\Scripts\\python.exe $RW\\run\\snap-run-$ID.py $RW\\run\\snap-args-$ID.json"
rc=$?

rssh "del /q $RW\\run\\snap-args-$ID.json $RW\\run\\snap-run-$ID.py" >/dev/null 2>&1
exit $rc
