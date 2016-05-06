
# Let scubainit/Makefile deal with dependencies
.PHONY: scuba/scubainit
scuba/scubainit:
	make -C scubainit
	cp scubainit/scubainit $@
