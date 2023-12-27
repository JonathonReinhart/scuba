.PHONY: all
all: scuba/scubainit

.PHONY: scubainit  # Defer dependency-tracking to Cargo
scubainit:
	make -C $@

# Copy the binary into the scuba python package
scuba/scubainit: scubainit
	cp $</scubainit $@

.PHONY: clean
clean:
	make -C scubainit clean
	rm -f scuba/scubainit
