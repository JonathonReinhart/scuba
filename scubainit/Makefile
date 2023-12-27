.PHONY: all
all: scubainit-debug   # Build this first to catch compile errors faster
all: scubainit

TARGET=x86_64-unknown-linux-musl

# Force static linking for all builds
export RUSTFLAGS=-C relocation-model=static

.PHONY: scubainit-debug  # always build
scubainit-debug: PROFILE=debug
scubainit-debug: setup
	@/bin/echo -e "\nBuilding scubainit ($(PROFILE)) with RUSTFLAGS=\"$$RUSTFLAGS\""
	cargo build --target $(TARGET)
	cp target/x86_64-unknown-linux-musl/$(PROFILE)/scubainit $@

.PHONY: scubainit  # always build
scubainit: PROFILE=release
scubainit: setup
	@/bin/echo -e "\nBuilding scubainit ($(PROFILE)) with RUSTFLAGS=\"$$RUSTFLAGS\""
	cargo build --target $(TARGET) --release
	cp target/x86_64-unknown-linux-musl/$(PROFILE)/scubainit $@

.PHONY: setup  # always run
setup:
	rustup target add $(TARGET)


.PHONY: clean
clean:
	rm -rf target/ scubainit scubainit-debug
