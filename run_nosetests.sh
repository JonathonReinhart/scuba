#!/bin/bash
nosetests -v \
    --with-coverage \
    --cover-inclusive \
    --cover-package=scuba \
    --processes=-1 \
    --detailed-errors \
    $@
