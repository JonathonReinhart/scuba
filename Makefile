.PHONY: all
all: scuba/scubainit

ifneq ($(USE_SCUBAINIT_RUST),)
.PHONY: scubainit-rs  # Defer dependency-tracking to Cargo
scubainit-rs:
	make -C $@
scuba/scubainit: scubainit-rs
else  # USE_RUST
.PHONY: scubainit
scubainit:
	make -C $@
scuba/scubainit: scubainit
endif  # USE_RUST

# Copy the desired binary into the scuba python package
scuba/scubainit:
	cp $</scubainit $@

.PHONY: clean
clean:
	make -C scubainit clean
	make -C scubainit-rs clean
	rm -f scuba/scubainit
