#!/bin/bash
set -e

MUSL_VERSION="1.1.14"
MUSL_RELEASE="musl-${MUSL_VERSION}"

# Is it already installed?
ver=$(/usr/local/musl/lib/libc.so 2>&1 | grep Version | awk '{ print $2 }')
if [[ $ver == "$MUSL_VERSION" ]]; then
    echo "$MUSL_RELEASE already installed!"
    exit 0
fi


# Install it
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
