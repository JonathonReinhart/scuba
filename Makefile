
.PHONY: all
all: scuba/scubainit scubainit-rs

.PHONY: scubainit-rs
scubainit-rs:
	cd scubainit-rs && ./build.sh

# Let scubainit/Makefile deal with dependencies
.PHONY: scuba/scubainit
scuba/scubainit:
	make -C scubainit
	cp scubainit/scubainit $@

.PHONY: clean
clean:
	make -C scubainit clean
	rm -f scuba/scubainit
	rm -rf scubainit-rs/target
