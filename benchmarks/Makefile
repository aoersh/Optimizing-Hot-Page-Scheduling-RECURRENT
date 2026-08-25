CC ?= cc
CFLAGS ?= -O2 -g -Wall -Wextra -Wpedantic
LDLIBS ?= -lnuma

.PHONY: all clean

all: numa_probe memory_bench migration_bench static_controller_bench online_controller_bench shared_heat_bench migrate_pid_pages

numa_probe: numa_probe.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

memory_bench: memory_bench.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

migration_bench: migration_bench.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

static_controller_bench: static_controller_bench.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

online_controller_bench: online_controller_bench.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

shared_heat_bench: shared_heat_bench.c
	$(CC) $(CFLAGS) -pthread -o $@ $< $(LDLIBS)

migrate_pid_pages: migrate_pid_pages.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	$(RM) numa_probe memory_bench migration_bench static_controller_bench online_controller_bench shared_heat_bench migrate_pid_pages
