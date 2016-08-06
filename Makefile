
# Let scubainit/Makefile deal with dependencies
.PHONY: scuba/scubainit
scuba/scubainit:
	make -C scubainit
	cp scubainit/scubainit $@

.PHONY: clean
clean:
	make -C scubainit clean
	rm scuba/scubainit
