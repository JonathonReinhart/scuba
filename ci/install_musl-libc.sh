#!/bin/bash
set -e

MUSL_RELEASE=musl-1.1.14

cd /tmp

echo "Downloading ${MUSL_RELEASE}..."
wget https://www.musl-libc.org/releases/${MUSL_RELEASE}.tar.gz
tar xf ${MUSL_RELEASE}.tar.gz
cd ${MUSL_RELEASE}

echo "Building ${MUSL_RELEASE}..."
./configure
make

echo "Installing ${MUSL_RELEASE}..."
sudo make install


echo "${MUSL_RELEASE} installed!"
ls -l /usr/local/musl/bin/musl-gcc
