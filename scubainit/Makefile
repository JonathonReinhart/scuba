.PHONY: help
help:
	@echo "Targets:"
	@echo "  all      Build everything and run tests (no checks)"
	@echo "  clean    Clean all built files"
	@echo "  check    Run all checks (test, lint, fmt)"
	@echo "  fmt      Check code formatting"
	@echo "  help     Display this help"
	@echo "  lint     Lint code (using clippy)"
	@echo "  setup    Install Rust toolchain support for all targets"
	@echo "  test     Run unit + integration tests"
	@echo ""
	@echo "  scubainit        Release build for all supported targets"
	@echo "  scubainit-debug  Debug build for all supported targets"
	@echo ""
	@false

.PHONY: all
all: test  # Build this first to catch compile errors faster
all: scubainit-debug
all: scubainit

SUPPORTED_TARGETS := x86_64-unknown-linux-musl aarch64-unknown-linux-musl
TARGETS ?= $(SUPPORTED_TARGETS)

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
scubainit-debug: $(patsubst %,scubainit-debug-%,$(TARGETS))

.PHONY: scubainit-debug-%  # always build
scubainit-debug-%: PROFILE=debug
scubainit-debug-%: RUSTFLAGS=$(STATIC_RUSTFLAGS)
scubainit-debug-%:
	@/bin/echo -e "\nBuilding scubainit ($(PROFILE)) for $* with RUSTFLAGS=\"$$RUSTFLAGS\""
	cargo build --target $*
	cp target/$*/$(PROFILE)/scubainit $@

.PHONY: scubainit  # always build
scubainit: PROFILE=release
scubainit: RUSTFLAGS=$(STATIC_RUSTFLAGS)
scubainit: setup
scubainit: $(patsubst %,scubainit-%,$(TARGETS))

.PHONY: scubainit-%  # always build
scubainit-%: PROFILE=release
scubainit-%: RUSTFLAGS=$(STATIC_RUSTFLAGS)
scubainit-%:
	@/bin/echo -e "\nBuilding scubainit ($(PROFILE)) for $* with RUSTFLAGS=\"$$RUSTFLAGS\""
	cargo build --target $* --release
	cp target/$*/$(PROFILE)/scubainit $@

.PHONY: setup  # always run
setup:
	rustup target add $(TARGETS)


.PHONY: clean
clean:
	rm -rf target/ scubainit-* scubainit-debug-*
