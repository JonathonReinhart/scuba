#!/bin/sh
set -e
cd $(dirname $0)

entrypoint-test/build.sh
hello/build.sh
scratch/build.sh
