#!/usr/bin/env bash
# tools/deploy/snapshot_test.sh NAME [--no-sync] [--refdata] -- <pytest arguments>
# Packs and copies the working tree to D:\code\behind-the-image\run\snap-NAME\ on the Windows server,
# sets up directory junctions (library, books, projects), and runs pytest inside the snapshot copy.
# Output is streamed back in UTF-8; exits with pytest's exit code.
# Refuses `-m slow` and `-m server` unless BTI_ALLOW_HEAVY=1.
set -uo pipefail

NAME="${1:-}"
if [[ -z "$NAME" || ! "$NAME" =~ ^[a-z0-9-]{1,24}$ ]]; then
  echo "Usage: $0 NAME [--no-sync] [--refdata] -- <pytest arguments> (where NAME matches [a-z0-9-]{1,24})" >&2
  exit 2
fi
shift

SYNC=1
REFDATA=0
while [ $# -gt 0 ]; do
  case "$1" in
    --no-sync) SYNC=0; shift;;
    --refdata) REFDATA=1; shift;;
    --) shift; break;;
    *) break;;
  esac
done

if [ "${BTI_ALLOW_HEAVY:-0}" != 1 ]; then
  prev=""
  for a in "$@"; do
    combo="$prev$a"
    case "$combo" in
      *-m*slow*|*-mslow*)
        case "$combo" in
          *"not slow"*) ;;
          *) echo "refused: slow tests are heavy jobs (lock protocol). See docs/WINDOWS.md" >&2; exit 64;;
        esac
        ;;
      *-m*server*|*-mserver*)
        case "$combo" in
          *"not server"*) ;;
          *) echo "refused: server tests are heavy jobs. See docs/WINDOWS.md" >&2; exit 64;;
        esac
        ;;
    esac
    prev="$a "
  done
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/tools/deploy"
. "$HERE/lib.sh"

SNAP_DIR="$RW\\run\\snap-$NAME"

# Check if reference data is needed (--refdata or run\refdata\projects missing)
NEED_REFDATA=$REFDATA
if [ $NEED_REFDATA -eq 0 ]; then
  if ! rssh "if not exist $RW\\run\\refdata\\projects exit 1"; then
    NEED_REFDATA=1
  fi
fi

if [ $NEED_REFDATA -eq 1 ]; then
  echo "== sync reference projects to run/refdata/projects"
  REF_ID="$(date +%Y%m%d%H%M%S)-$$"
  TMP_REF="$(mktemp -d)"; trap 'rm -rf "$TMP_REF"' EXIT
  export COPYFILE_DISABLE=1
  tar -czf "$TMP_REF/refdata.tgz" \
    --exclude=cache --exclude=history --exclude='._*' --exclude=.DS_Store \
    --no-xattrs --no-mac-metadata \
    -C "$ROOT/projects" \
    arnolfini arnolfini_edit arnolfini-from-books technique_lab demo_stub lab_annot lab_diagrams lab_layouts lab_text \
    2>/dev/null \
    || tar -czf "$TMP_REF/refdata.tgz" \
    --exclude=cache --exclude=history --exclude='._*' --exclude=.DS_Store \
    -C "$ROOT/projects" \
    arnolfini arnolfini_edit arnolfini-from-books technique_lab demo_stub lab_annot lab_diagrams lab_layouts lab_text
  
  rssh "if not exist $RW\\run\\refdata\\projects mkdir $RW\\run\\refdata\\projects" || exit 255
  rscp "$TMP_REF/refdata.tgz" "$HOST:$REMOTE/run/refdata-$REF_ID.tgz" || exit 255
  rm -rf "$TMP_REF"
  trap - EXIT
  rssh "tar -xzf $RW\\run\\refdata-$REF_ID.tgz -C $RW\\run\\refdata\\projects && del /q $RW\\run\\refdata-$REF_ID.tgz" || exit 255
fi

if [ $SYNC -eq 1 ]; then
  echo "== pack snapshot $NAME"
  SNAP_LOCAL="$ROOT/.scratch/snap"
  mkdir -p "$SNAP_LOCAL"
  LOCAL_ARCHIVE="$SNAP_LOCAL/$NAME.tgz"
  FILE_LIST="$SNAP_LOCAL/files-$NAME-$$.txt"
  export COPYFILE_DISABLE=1
  cd "$ROOT"
  {
    git ls-files -z -c -o --exclude-standard
    git ls-files -z -o -i --exclude-standard style
  } | while IFS= read -r -d '' f; do
      [ -e "$f" ] && printf '%s\n' "$f"
    done \
    | grep -vE '^(books|library|projects|demo_runs|research_media|\.scratch|\.venv[^\/]*|\.git)/|(^|/)\._|(^|/)\.DS_Store$|(^|/)\.env' \
    | grep -v '^$' > "$FILE_LIST"

  tar -czf "$LOCAL_ARCHIVE" --no-xattrs --no-mac-metadata -T "$FILE_LIST" 2>/dev/null \
    || tar -czf "$LOCAL_ARCHIVE" -T "$FILE_LIST"
  rm -f "$FILE_LIST"

  echo "== copy snapshot $NAME to server"
  rssh "if not exist $RW\\run mkdir $RW\\run" || exit 255
  rscp "$LOCAL_ARCHIVE" "$HOST:$REMOTE/run/snap-$NAME.tgz" || exit 255

  echo "== unpack snapshot $NAME and setup junctions"
  rssh "cmd /c \"(if exist $SNAP_DIR\\library rmdir $SNAP_DIR\\library) & (if exist $SNAP_DIR\\books rmdir $SNAP_DIR\\books) & (if exist $SNAP_DIR\\projects rmdir $SNAP_DIR\\projects) & (if exist $SNAP_DIR rmdir /s /q $SNAP_DIR) & mkdir $SNAP_DIR & tar -xzf $RW\\run\\snap-$NAME.tgz -C $SNAP_DIR & mklink /J $SNAP_DIR\\library $RW\\library & mklink /J $SNAP_DIR\\books $RW\\books & mklink /J $SNAP_DIR\\projects $RW\\run\\refdata\\projects\"" || exit 255
fi

exec "$HERE/snapshot_py.sh" "$NAME" -m pytest "$@" -p no:cacheprovider
