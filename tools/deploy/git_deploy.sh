#!/usr/bin/env bash
# Deploy by git: push the current branch, then fast-forward the server's checkout to it.
# Usage: tools/deploy/git_deploy.sh [--restart] [--check]
#   (default)   `git push` of the current branch to its upstream (never forced, no tags, no other branches), then
#               tools/deploy/git_update.ps1 on the server: git fetch, refuse if anything is off, `git merge --ff-only`,
#               refresh .venv when requirements.txt changed. The running app is left alone.
#   --restart   stop and start OUR app (127.0.0.1:8560) around the merge. Without it the page files change at once but
#               the running app keeps the old Python code until it is restarted.
#   --check     push nothing, change nothing anywhere: only report what a deploy would do (what is incoming, whether the
#               server checkout is clean and on the branch, whether the history can fast-forward).
# Refuses (non-zero exit, nothing pushed) when tracked files have uncommitted changes, the branch has no upstream, or HEAD is
# detached. Untracked files are only mentioned. Exit code = the server script's exit code (see git_update.ps1).
# The server's .env and the data folders (books, library, projects) never go through git.
# The old tar deploy (deploy_windows.sh) refuses on a git checkout.
# env: BTI_SSH_HOST (default winbox-lan), BTI_REMOTE (default D:/code/behind-the-image)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "$ROOT/tools/deploy/lib.sh"
RESTART=0; CHECK=0
while [ $# -gt 0 ]; do a="$1"; shift; case "$a" in
  --restart) RESTART=1;; --check) CHECK=1;;
  *) echo "unknown option $a" >&2; exit 1;; esac; done
cd "$ROOT"

BRANCH="$(git symbolic-ref --short -q HEAD || true)"
[ -n "$BRANCH" ] || { echo "REFUSED: HEAD is detached; check out a branch first." >&2; exit 2; }
case "$BRANCH" in *[!A-Za-z0-9._/-]*) echo "REFUSED: branch name '$BRANCH' has characters this script does not pass to the server." >&2; exit 2;; esac
DIRTY="$(git status --porcelain --untracked-files=no)"
if [ -n "$DIRTY" ]; then
  echo "REFUSED: tracked files have uncommitted changes (commit them first):" >&2
  echo "$DIRTY" | head -20 >&2
  exit 2
fi
UNTRACKED="$(git status --porcelain --untracked-files=normal | grep -c '^??' || true)"
[ "$UNTRACKED" -gt 0 ] && echo "note: $UNTRACKED untracked path(s) exist here; git does not send them"
UP_REMOTE="$(git config --get "branch.$BRANCH.remote" || true)"
UP_MERGE="$(git config --get "branch.$BRANCH.merge" || true)"
if [ -z "$UP_REMOTE" ] || [ -z "$UP_MERGE" ]; then
  echo "REFUSED: branch $BRANCH has no upstream (git push -u origin $BRANCH sets one)." >&2
  exit 2
fi
if [ "$UP_MERGE" != "refs/heads/$BRANCH" ]; then
  echo "REFUSED: the upstream of $BRANCH is $UP_REMOTE/${UP_MERGE#refs/heads/}, a different name; the server follows the same name as the local branch." >&2
  exit 2
fi
SHA="$(git rev-parse HEAD)"

if [ $CHECK -eq 1 ]; then
  echo "== check (nothing is pushed or changed)"
  AHEAD="$(git rev-list --count "$UP_REMOTE/$BRANCH..HEAD" 2>/dev/null || echo '?')"
  echo "branch $BRANCH at ${SHA:0:7}; commits not yet pushed (by the last fetched $UP_REMOTE/$BRANCH): $AHEAD"
else
  echo "== push $BRANCH to $UP_REMOTE"
  git push "$UP_REMOTE" "refs/heads/$BRANCH:refs/heads/$BRANCH"
fi

ID="$(date +%Y%m%d%H%M%S)-$$"
echo "== copy"
rssh "if not exist $RW\\_deploy mkdir $RW\\_deploy"
rscp "$ROOT/tools/deploy/git_update.ps1" "$HOST:$REMOTE/_deploy/git_update-$ID.ps1"

echo "== update on the server (waits for the deploy lock)"
ARGS=""; [ $RESTART -eq 1 ] && ARGS="$ARGS -Restart"; [ $CHECK -eq 1 ] && ARGS="$ARGS -Check"
rc=0
rssh "powershell -NoProfile -ExecutionPolicy Bypass -File $RW\\_deploy\\git_update-$ID.ps1 -Root $RW -Branch $BRANCH -Commit $SHA$ARGS" || rc=$?
exit $rc
