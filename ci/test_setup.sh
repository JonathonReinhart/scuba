#!/bin/sh
set -e

topdir=$(cd $(dirname $0)/.. && pwd)

# Pull this image ahead of time, so it's there for the unit tests
docker pull debian:8.2

# Build docker images for local testing
$topdir/test-docker-images/build_all.sh
