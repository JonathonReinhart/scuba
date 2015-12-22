#!/bin/bash

cd $(dirname $0)

# Run ./do_build.sh inside of a container,
# using the image specified in .scuba.yml
../../src/scuba ./do_build.sh "here are args" from user "via scuba invocation"
