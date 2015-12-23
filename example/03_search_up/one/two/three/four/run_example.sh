#!/bin/sh

cd $(dirname $0)

scuba cat ../../../1.txt ../../2.txt ../3.txt 4.txt
