CC ?= cc
CFLAGS ?= -O2 -g -Wall -Wextra -Wpedantic
LDLIBS ?= -lnuma

.PHONY: all clean

all: numa_probe memory_bench

numa_probe: numa_probe.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

memory_bench: memory_bench.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	$(RM) numa_probe memory_bench

