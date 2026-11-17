# Shared helpers for the deploy scripts (sourced). Every ssh and scp is tried three times, but only when the connection
# itself fails (exit code 255); a command that ran and failed is never run again.
HOST="${BTI_SSH_HOST:-winbox-lan}"
REMOTE="${BTI_REMOTE:-D:/code/behind-the-image}"
RW="$(echo "$REMOTE" | tr / '\\')"
_retry() { local n=0 rc; while true; do "$@"; rc=$?; [ $rc -ne 255 ] && return $rc; n=$((n+1)); [ $n -ge 3 ] && return 255; sleep $((n*4)); done; }
rssh() { _retry ssh -o ConnectTimeout=20 -o BatchMode=yes -o ServerAliveInterval=30 "$HOST" "$@"; }
rscp() { _retry scp -q -o ConnectTimeout=20 -o BatchMode=yes "$@"; }
