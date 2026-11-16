#!/bin/bash
for i in 1 2 3 4 5; do scp -q -o ConnectTimeout=20 "$@" && exit 0; sleep $((i*5)); done; exit 1
