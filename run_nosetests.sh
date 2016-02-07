#!/bin/bash
rm -f .coverage
nosetests -v \
    --with-coverage \
    --cover-inclusive \
    --cover-package=scuba \
    --processes=-1 \
    --detailed-errors \
    --process-timeout=60 \
    $@
