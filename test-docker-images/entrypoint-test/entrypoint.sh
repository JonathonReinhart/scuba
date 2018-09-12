#!/bin/sh
export ENTRYPOINT_WORKS=success
echo 'success' > entrypoint_works.txt
exec "$@"
