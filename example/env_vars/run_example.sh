#!/bin/bash
cd $(dirname $0)

export EXTERNAL_1="Value 1 taken from external environment"
export EXTERNAL_2="Value 2 taken from external environment"

scuba -e CMDLINE="This comes from the cmdline" example
