#!/usr/bin/env bash
# Deploy the working tree (uncommitted and untracked-but-not-ignored files included) to the Windows server.
# Usage: tools/deploy/deploy_windows.sh [--data] [--restart] [--pack-only]
#   (default)   code only; the server's books/, library/, projects/ are NOT touched.
#   --data      also send books/, library/ (without cache/ and history/) and projects/ (same). Overwrites same-named
#               files, deletes nothing. DANGER once the server holds the only real data.
#   --restart   stop and start OUR app (127.0.0.1:8560) around the unpack. Default: leave it running.
#   --pack-only build the archives in .scratch/deploy/out and stop.
#   --root DIR  pack the files of DIR instead of the working tree (a snapshot, for example `git archive HEAD` plus a few
#               overlaid files); every file under DIR is sent except the never-sent names below.
# env: BTI_SSH_HOST (default winbox-lan), BTI_REMOTE (default D:/code/behind-the-image)
# Also sent: ignored files under style/ (the technique preview clips, 5 MB; tests need them).
# Never sent: .env*, books/ library/ projects/ demo_runs/ research_media/ (except books/library/projects with --data).
# On the server: one deploy at a time (run\deploy.lock, waits up to 20 min, a lock older than 30 min is taken over).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "$ROOT/tools/deploy/lib.sh"
DATA=0; RESTART=0; PACK_ONLY=0; PACK_ROOT=""
while [ $# -gt 0 ]; do a="$1"; shift; case "$a" in
  --root) PACK_ROOT="$1"; shift;;
  --data) DATA=1;; --restart) RESTART=1;; --pack-only) PACK_ONLY=1;;
  *) echo "unknown option $a" >&2; exit 1;; esac; done
cd "$ROOT"
ID="$(date +%Y%m%d%H%M%S)-$$"
OUT="$ROOT/.scratch/deploy/out"
mkdir -p "$OUT"
export COPYFILE_DISABLE=1                                  # no ._ AppleDouble files in the archives

echo "== pack code"
if [ -n "$PACK_ROOT" ]; then
  cd "$PACK_ROOT"; PACK_DIR="$PACK_ROOT"
  LISTER() { find . -type f | sed 's|^\./||' | tr '\n' '\0'; }
else
  PACK_DIR="$ROOT"
  LISTER() { git ls-files -z -c -o --exclude-standard; git ls-files -z -o -i --exclude-standard style; }
fi
LISTER \
  | while IFS= read -r -d '' f; do [ -e "$f" ] && printf '%s\n' "$f"; done \
  | grep -vE '^(books|library|projects|demo_runs|research_media|\.scratch|\.git)/|(^|/)\._|(^|/)\.DS_Store$|(^|/)\.env($|\.)' \
  | grep -v '^$' > "$OUT/code_files.txt"
tar -czf "$OUT/code-$ID.tgz" --no-xattrs --no-mac-metadata -T "$OUT/code_files.txt" 2>/dev/null \
  || tar -czf "$OUT/code-$ID.tgz" -T "$OUT/code_files.txt"
cd "$ROOT"
echo "$(wc -l < "$OUT/code_files.txt" | tr -d ' ') files, $(ls -l "$OUT/code-$ID.tgz" | awk '{print $5}') bytes"
if [ $DATA -eq 1 ]; then
  echo "== pack data"
  TAR_X=(--exclude=cache --exclude=history --exclude='._*' --exclude=.DS_Store --exclude='.env*')
  tar -czf "$OUT/data-$ID.tgz" "${TAR_X[@]}" --no-xattrs --no-mac-metadata books library projects 2>/dev/null \
    || tar -czf "$OUT/data-$ID.tgz" "${TAR_X[@]}" books library projects
  echo "$(ls -l "$OUT/data-$ID.tgz" | awk '{print $5}') bytes"
fi
[ $PACK_ONLY -eq 1 ] && { echo "packed in $OUT (id $ID)"; exit 0; }
trap 'rm -f "$OUT/code-$ID.tgz" "$OUT/data-$ID.tgz"' EXIT

echo "== copy"
rssh "if not exist $RW\\_deploy mkdir $RW\\_deploy"
rscp "$OUT/code-$ID.tgz" "$HOST:$REMOTE/_deploy/code-$ID.tgz"
[ $DATA -eq 1 ] && rscp "$OUT/data-$ID.tgz" "$HOST:$REMOTE/_deploy/data-$ID.tgz"
rscp "$ROOT/tools/deploy/remote_update.ps1" "$HOST:$REMOTE/_deploy/remote_update-$ID.ps1"

echo "== unpack (waits for the deploy lock)"
ARGS=""; [ $DATA -eq 1 ] && ARGS="$ARGS -Data"; [ $RESTART -eq 1 ] && ARGS="$ARGS -Restart"
rssh "powershell -NoProfile -ExecutionPolicy Bypass -File $RW\\_deploy\\remote_update-$ID.ps1 -Id $ID$ARGS"
