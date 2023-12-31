.PHONY: help
help:
	@echo "Targets:"
	@echo "  all      Build everything and run tests (no checks)"
	@echo "  clean    Clean all built files"
	@echo "  check    Run all checks (test, lint, fmt)"
	@echo "  fmt      Check code formatting"
	@echo "  help     Display this help"
	@echo "  lint     Lint code (using clippy)"
	@echo "  test     Run unit + integration tests"
	@echo ""
	@echo "  scubainit        Release build"
	@echo "  scubainit-debug  Debug build"
	@echo ""
	@false

.PHONY: all
all: test  # Build this first to catch compile errors faster
all: scubainit-debug
all: scubainit

TARGET=x86_64-unknown-linux-musl

# Enable static linking
STATIC_RUSTFLAGS=-C relocation-model=static

export RUSTFLAGS

check: test lint fmt

.PHONY: test  # always run
test:
	cargo test

.PHONY: lint
lint:
	cargo clippy --no-deps

.PHONY: fmt
fmt:
	cargo fmt --check


.PHONY: scubainit-debug  # always build
scubainit-debug: PROFILE=debug
scubainit-debug: RUSTFLAGS=$(STATIC_RUSTFLAGS)
scubainit-debug: setup
	@/bin/echo -e "\nBuilding scubainit ($(PROFILE)) with RUSTFLAGS=\"$$RUSTFLAGS\""
	cargo build --target $(TARGET)
	cp target/x86_64-unknown-linux-musl/$(PROFILE)/scubainit $@

.PHONY: scubainit  # always build
scubainit: PROFILE=release
scubainit: RUSTFLAGS=$(STATIC_RUSTFLAGS)
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
