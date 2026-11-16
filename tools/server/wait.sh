#!/bin/bash
# usage: wait.sh logname  -> exits when LOCK_RELEASED appears in D:\bench\bti\<log>
until ssh -o ConnectTimeout=20 winbox-lan "findstr LOCK_RELEASED D:\\bench\\bti\\$1" >/dev/null 2>&1; do sleep 20; done
ssh winbox-lan "powershell -NoProfile -Command \"Get-Content D:\\bench\\bti\\$1 -Tail 5\""
