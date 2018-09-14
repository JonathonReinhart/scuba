#!/bin/sh
set -e
image="scuba/hello"
cd $(dirname $0)
docker build -t $image .
echo "Built $image"
