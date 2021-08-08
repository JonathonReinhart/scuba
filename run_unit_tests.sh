#!/bin/bash
what="tests/"
if [[ $# -ge 1 ]]; then
    what="$@"
fi

exec python3 -m pytest -v --log-level=DEBUG --cov=scuba --cov=tests $what
