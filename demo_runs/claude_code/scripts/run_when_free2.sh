#!/bin/bash
# usage: run_when_free2.sh <job> <expected_minutes> [max_polls]; polls every 60 s; never touches another agent's lock
job=$1; mins=$2; max=${3:-60}
for ((i=0;i<max;i++)); do
  out=$(scripts/ssh.sh "powershell -NoProfile -ExecutionPolicy Bypass -File D:\\bench\\claude_code\\guard2.ps1 -Job $job -Minutes $mins" 2>&1 | tr -d '\r' | tail -1)
  echo "$(date +%H:%M:%S) $out"
  case "$out" in *"GOT launched"*) exit 0;; esac
  sleep 60
done; exit 1
