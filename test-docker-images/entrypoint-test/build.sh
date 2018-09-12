#!/bin/sh
set -e
image="scuba/entrypoint-test"
cd $(dirname $0)
docker build -t $image .
echo "Built $image"
