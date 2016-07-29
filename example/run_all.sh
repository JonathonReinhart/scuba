#!/bin/sh
cd $(dirname $0)

./01_basic/run_example.sh
./02_with_alias/run_example.sh
./03_search_up/one/two/three/four/run_example.sh
./external_yaml_simple/run_example.sh
./external_yaml_nested/run_example.sh
./scubainit_hooks/run_example.sh
./alias_multiline/run_example.sh
./per_alias_image/run_example.sh
