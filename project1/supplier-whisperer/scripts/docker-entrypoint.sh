#!/bin/sh
# Hand the Fly volume to the app user, then run the app as that user (never as root).
set -e
if [ "$(id -u)" = "0" ]; then
    mkdir -p /data
    chown whisperer:whisperer /data
    exec setpriv --reuid=whisperer --regid=whisperer --init-groups "$@"
fi
exec "$@"
