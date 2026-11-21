#!/usr/bin/env bash
# tools/deploy/snapshot_rm.sh NAME
# Removes the private snapshot D:\code\behind-the-image\run\snap-NAME and its archives.
# Directory junctions (library, books, projects) are removed with non-recursive rmdir
# before deleting the snapshot folder, never touching the target data.
set -euo pipefail

NAME="${1:-}"
if [[ -z "$NAME" || ! "$NAME" =~ ^[a-z0-9-]{1,24}$ ]]; then
  echo "Usage: $0 NAME (where NAME matches [a-z0-9-]{1,24})" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "$ROOT/tools/deploy/lib.sh"

SNAP_DIR="$RW\\run\\snap-$NAME"

echo "== remove snapshot $NAME on server"
rssh "cmd /c \"(if exist $SNAP_DIR\\library rmdir $SNAP_DIR\\library) & (if exist $SNAP_DIR\\books rmdir $SNAP_DIR\\books) & (if exist $SNAP_DIR\\projects rmdir $SNAP_DIR\\projects) & (if exist $SNAP_DIR rmdir /s /q $SNAP_DIR) & (if exist $RW\\run\\snap-$NAME.tgz del /q $RW\\run\\snap-$NAME.tgz)\""

echo "== remove local archive"
rm -f "$ROOT/.scratch/snap/$NAME.tgz"

echo "snapshot $NAME removed"
