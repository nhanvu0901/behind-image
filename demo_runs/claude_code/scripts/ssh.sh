#!/bin/bash
# retry wrapper: ssh.sh "<cmd>" ; scp.sh in same file via first arg
for i in 1 2 3 4 5; do ssh -o ConnectTimeout=20 winbox-cmd "$@" && exit 0; sleep $((i*5)); done; exit 1
