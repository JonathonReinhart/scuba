#!/bin/bash
what="tests/"
if [[ $# -ge 1 ]]; then
    what="$@"
fi

exec python3 -m pytest -v --cov=scuba --cov=tests $what
