#!/bin/sh
cd $(dirname $0)
export PATH="$(realpath ../src):$PATH"

./01_basic/run_example.sh
./02_with_alias/run_example.sh
./03_search_up/one/two/three/four/run_example.sh
