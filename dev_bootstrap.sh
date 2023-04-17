#!/bin/bash
if [ "${BASH_SOURCE[0]}" -ef "$0" ]
then
    echo "Usage: source ${BASH_SOURCE[0]}"
    exit 1
fi

python3 -m virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
