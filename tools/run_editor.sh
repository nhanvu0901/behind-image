#!/usr/bin/env bash
# Start the editing page backend on 127.0.0.1:8560 (never 8550, never 0.0.0.0 by default).
# Usage: tools/run_editor.sh [--check]    env: BTI_PROJECTS_ROOT, BTI_EDITOR_PORT
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV="$ROOT/.venv"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet -r requirements.txt
PORT="${BTI_EDITOR_PORT:-8560}"
if [ "$PORT" = "8550" ]; then echo "port 8550 belongs to the comic UI" >&2; exit 1; fi
[ "${1:-}" = "--check" ] && { "$VENV/bin/python" -c "import bti.editor.app"; echo "ok"; exit 0; }
echo "BTI editor on http://127.0.0.1:$PORT"
exec "$VENV/bin/python" -m uvicorn bti.editor.app:create_app --factory --host 127.0.0.1 --port "$PORT"
