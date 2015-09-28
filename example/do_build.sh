#!/bin/bash
echo "Hello world from sample build script!"
echo "This is running inside a docker container."

echo ""
echo "Here are the arguments to do_build.sh:"
for i in "$@"; do
    echo "   '$i'"
done

echo ""
cat sample_source.txt
