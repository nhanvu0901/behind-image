#!/usr/bin/env bash
# tools/deploy/fetch_video.sh <artwork key>
# Copies ONE file from the server to the Mac: output/<artwork key>/final.mp4  ->  ~/Desktop/Claude Render/<artwork key>.mp4 . Nothing else is ever copied from the output folder.
# The file is copied to a temporary name and renamed when whole, so a broken connection never leaves a half-written video under the final name.
# Environment: BTI_SSH_HOST (see lib.sh), BTI_REMOTE (the app's folder on the server), BTI_REMOTE_OUTPUT (the output folder on the server, default $BTI_REMOTE/output),
#              BTI_FETCH_DIR (where to put it, default ~/Desktop/Claude Render).
set -uo pipefail

KEY="${1:-}"
if [[ $# -ne 1 || ! "$KEY" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$ || "$KEY" == *..* ]]; then
  echo "Usage: $0 <artwork key>      (the name of a folder of output/ on the server, e.g. eyck-the-arnolfini-portrait)" >&2
  exit 2
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/lib.sh"

REMOTE_OUTPUT="${BTI_REMOTE_OUTPUT:-$REMOTE/output}"
DEST_DIR="${BTI_FETCH_DIR:-$HOME/Desktop/Claude Render}"
SRC="$HOST:$REMOTE_OUTPUT/$KEY/final.mp4"
DEST="$DEST_DIR/$KEY.mp4"
TMP="$DEST_DIR/.$KEY.mp4.part"

if ! mkdir -p "$DEST_DIR"; then
  echo "cannot make $DEST_DIR (the Mac may refuse a folder for a while: wait a few minutes and run this again)" >&2
  exit 1
fi

echo "== fetch $KEY: $SRC -> $DEST"
if _retry scp -o ConnectTimeout=20 -o BatchMode=yes "$SRC" "$TMP"; then
  if mv -f "$TMP" "$DEST"; then
    echo "done: $DEST ($(du -h "$DEST" | cut -f1))"
    exit 0
  fi
  echo "the video arrived but could not be moved to $DEST" >&2
else
  echo "scp failed: is there a video yet? (the server's folder output/$KEY/ holds final.mp4 once the export is done; \`bti output <project>\` fills it from a finished project)" >&2
fi
rm -f "$TMP"
exit 1
