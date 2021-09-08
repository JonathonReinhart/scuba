#!/bin/sh
set -e

topdir=$(cd $(dirname $0)/.. && pwd)

# Load test constants
eval $(cd $topdir && python3 -m tests.const)

# Pull this image ahead of time, so it's there for the tests
docker pull "$DOCKER_IMAGE"

# Build docker images for local testing
$topdir/test-docker-images/build_all.sh
