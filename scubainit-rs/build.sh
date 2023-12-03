#!/bin/bash

# Setup:
# rustup target add x86_64-unknown-linux-musl

set -e
export RUSTFLAGS='-C relocation-model=static -C strip=symbols'
cargo build --target x86_64-unknown-linux-musl
cargo build --target x86_64-unknown-linux-musl --release
