CC ?= gcc
CFLAGS = -Wall -Wextra -Werror -static -s

scubainit: scubainit.c
	$(CC) $(CFLAGS) -o $@ $^

.PHONY: clean
clean:
	rm scubainit
