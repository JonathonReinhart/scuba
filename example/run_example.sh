#!/bin/bash

cd $(dirname $0)

export PATH="../src:$PATH"


# Run ./do_build.sh inside of a container,
# using the image specified in .scuba.yml
scuba ./do_build.sh "here are args" from user "via scuba invocation"

echo ""

# This invocation runs an alias named 'build'
scuba build "and more args" from "the command-line"

