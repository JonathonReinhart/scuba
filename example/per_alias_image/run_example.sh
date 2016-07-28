#!/bin/bash
cd $(dirname $0)

echo -e "\nRunning 'scuba default'"
scuba default

echo -e "\nRunning 'scuba different'"
scuba different 

echo ""
