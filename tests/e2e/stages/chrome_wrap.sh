#!/bin/sh
# Real Chrome, but every host except 127.0.0.1 does not resolve: the browser cannot reach the outside network.
exec "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --host-resolver-rules="MAP * ~NOTFOUND, EXCLUDE 127.0.0.1" "$@"
