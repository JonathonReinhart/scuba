.PHONY: all
all: scuba/scubainit-all

SCUBAINIT_BIN_TARGETS := x86_64-unknown-linux-musl aarch64-unknown-linux-musl

.PHONY: scubainit  # Defer dependency-tracking to Cargo
scubainit:
	make -C $@ test scubainit

# Copy all architecture variants into the scuba python package
scuba/scubainit-all: scubainit
	for target in $(SCUBAINIT_BIN_TARGETS); do \
		cp scubainit/scubainit-$$target scuba/scubainit-$$target; \
	done

.PHONY: clean
clean:
	make -C scubainit clean
	rm -f scuba/scubainit-*
