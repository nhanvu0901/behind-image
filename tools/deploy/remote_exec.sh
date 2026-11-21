#!/usr/bin/env bash
# Internal: remote_exec.sh <venv> <python args...>. Ships the arguments as JSON, runs them through remote_run.py.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/lib.sh"
VENV="$1"; shift
ID="$(date +%Y%m%d%H%M%S)-$$"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
python3 - "$TMP/args.json" "$@" <<'PY'
import json, sys
json.dump({"argv": sys.argv[2:]}, open(sys.argv[1], "w", encoding="utf-8"))
PY
rssh "if not exist $RW\\run mkdir $RW\\run" || exit 255
rscp "$TMP/args.json" "$HOST:$REMOTE/run/args-$ID.json" || exit 255
rscp "$HERE/remote_run.py" "$HOST:$REMOTE/run/remote_run-$ID.py" || exit 255
# the runner is started once; a dropped connection is not retried (it would start the tests twice)
ssh -o ConnectTimeout=20 -o BatchMode=yes -o ServerAliveInterval=30 "$HOST" \
  "$RW\\.venv\\Scripts\\python.exe $RW\\run\\remote_run-$ID.py $RW\\run\\args-$ID.json $VENV"
rc=$?
rssh "del /q $RW\\run\\args-$ID.json $RW\\run\\remote_run-$ID.py" >/dev/null 2>&1
exit $rc
