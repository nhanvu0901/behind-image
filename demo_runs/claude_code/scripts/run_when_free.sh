#!/bin/bash
# usage: run_when_free.sh <jobname> [max_minutes]  -- polls every 60 s; never touches another agent's lock
job=$1; max=${2:-40}
for ((i=0;i<max;i++)); do
  out=$(scripts/ssh.sh "powershell -NoProfile -ExecutionPolicy Bypass -File D:\\bench\\claude_code\\guard.ps1 -Job $job" 2>&1 | tr -d '\r' | tail -2)
  echo "$(date +%H:%M:%S) $out"
  case "$out" in *"GOT launched"*) exit 0;; esac
  sleep 60
done; exit 1
