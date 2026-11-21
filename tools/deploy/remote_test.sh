#!/usr/bin/env bash
# tools/deploy/remote_test.sh [--no-sync] [--venv NAME] <pytest arguments>
# Deploys the code (unless --no-sync), then runs `python -m pytest <arguments> -p no:cacheprovider` in the server's
# .venv (or .venv-NAME), working directory D:\code\behind-the-image, UTF-8 output streamed back; exits with pytest's code.
# Arguments reach pytest untouched (spaces and quotes survive: they travel as a JSON file, no shell is involved).
# Refuses `-m ...slow...` without "not slow" (heavy); see docs/WINDOWS.md "Heavy jobs". BTI_ALLOW_HEAVY=1 overrides.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC=1; VENV=main
while [ $# -gt 0 ]; do case "$1" in
  --no-sync) SYNC=0; shift;; --venv) VENV="$2"; shift 2;; *) break;; esac; done
if [ "${BTI_ALLOW_HEAVY:-0}" != 1 ]; then
  prev=""; for a in "$@"; do
    case "$prev$a" in *-m*slow*|*-mslow*) case "$prev$a" in *"not slow"*) ;; *) echo "refused: slow tests are heavy jobs (lock protocol). See docs/WINDOWS.md" >&2; exit 64;; esac;; esac
    prev="$a "; done
fi
if [ $SYNC -eq 1 ]; then "$HERE/deploy_windows.sh" || exit $?; fi
exec "$HERE/remote_exec.sh" "$VENV" -m pytest "$@" -p no:cacheprovider
