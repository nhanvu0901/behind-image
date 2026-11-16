#!/bin/bash
cd /Users/nhanvu/Documents/code/behind-the-image/demo_runs/claude_code
for j in v2r1 v2r2 v2r3 v2fin; do
  m=18; [ $j = v2fin ] && m=10
  scripts/run_when_free2.sh $j $m 60
  until scripts/ssh.sh "type D:\\bench\\claude_code\\$j.log" 2>&1 | tr -d '\r' | grep -q LOCK_RELEASED; do sleep 15; done
  echo "$j released $(date +%T)"
  scripts/ssh.sh "type D:\\bench\\claude_code\\$j.log" 2>&1 | tr -d '\r' | grep -E "RENDER_DONE|EXIT|AUDIO" 
done
echo CHAIN_DONE
