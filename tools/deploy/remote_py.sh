#!/usr/bin/env bash
# tools/deploy/remote_py.sh [--venv NAME] <python arguments>   (no sync; run deploy_windows.sh first if needed)
# Runs `python <arguments>` in the server's .venv (or .venv-NAME, e.g. --venv align), cwd D:\code\behind-the-image,
# UTF-8. For one-off checks only: nothing heavy (renders, sweeps, voice, model runs) without the lock protocol.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV=main
if [ "${1:-}" = "--venv" ]; then VENV="$2"; shift 2; fi
exec "$HERE/remote_exec.sh" "$VENV" "$@"
