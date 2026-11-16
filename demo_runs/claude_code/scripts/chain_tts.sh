#!/bin/bash
cd /Users/nhanvu/Documents/code/behind-the-image/demo_runs/claude_code
until scripts/ssh.sh "type D:\\bench\\claude_code\\tts2.log" 2>&1 | tr -d '\r' | grep -q LOCK_RELEASED; do sleep 15; done
echo "tts2 released $(date +%T)"
scripts/run_when_free2.sh tts3 23 30
scripts/scp.sh winbox-cmd:D:/bench/claude_code/voice_J2.wav winbox-cmd:D:/bench/claude_code/voice_J2_words.json winbox-cmd:D:/bench/claude_code/tts2.log winbox-cmd:D:/bench/claude_code/git_after_tts2.txt winbox-cmd:D:/bench/claude_code/git_before_tts2.txt v2/voice/
echo "J2 fetched $(date +%T)"
until scripts/ssh.sh "type D:\\bench\\claude_code\\tts3.log" 2>&1 | tr -d '\r' | grep -q LOCK_RELEASED; do sleep 15; done
scripts/scp.sh winbox-cmd:D:/bench/claude_code/voice_J3.wav winbox-cmd:D:/bench/claude_code/voice_J3_words.json winbox-cmd:D:/bench/claude_code/tts3.log winbox-cmd:D:/bench/claude_code/git_after_tts3.txt winbox-cmd:D:/bench/claude_code/git_before_tts3.txt v2/voice/
echo "J3 fetched $(date +%T)"
