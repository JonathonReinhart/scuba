.PHONY: all
all: scuba/scubainit

.PHONY: scubainit-rs  # Defer dependency-tracking to Cargo
scubainit-rs:
	make -C $@

# Copy the binary into the scuba python package
scuba/scubainit: scubainit-rs
	cp $</scubainit $@

.PHONY: clean
clean:
	make -C scubainit-rs clean
	rm -f scuba/scubainit
