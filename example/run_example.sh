#!/bin/bash

export PATH="../src:$PATH"

scuba /bin/sh ./do_build.sh "here are args" from user "via scuba invocation"
