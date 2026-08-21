#define _GNU_SOURCE

#include <getopt.h>
#include <inttypes.h>
#include <numa.h>
#include <numaif.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <x86intrin.h>

static double clock_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static void usage(const char *p)
{
    fprintf(stderr, "Usage: %s --source NODE --target NODE [--mib SIZE] [--dram-percent P] [--hot-percent P] [--seconds S]\n", p);
}

static int placement(void **pages, size_t count, int expected, int *matched)
{
    int *status = calloc(count, sizeof(*status));
    if (!status) return -1;
    if (move_pages(0, count, pages, NULL, status, 0) != 0) {
        free(status);
        return -1;
    }
    *matched = 0;
    for (size_t i = 0; i < count; ++i) if (status[i] == expected) ++*matched;
    free(status);
    return 0;
}

static uint64_t random64(uint64_t *state)
{
    uint64_t x = *state;
    x ^= x << 13; x ^= x >> 7; x ^= x << 17;
    return *state = x;
}

static double hot_latency(void **hot_pages, size_t pages, uint64_t first,
                          double seconds, uint64_t *accesses)
{
    uint64_t count = 0;
    double measured = 0.0;
    do {
        for (size_t i = 0; i < pages; ++i)
            _mm_clflush(hot_pages[i]);
        _mm_mfence();
        uint64_t index = first;
        double start = clock_seconds();
        for (size_t i = 0; i < pages; ++i) {
            index = *(volatile uint64_t *)hot_pages[index];
            ++count;
        }
        measured += clock_seconds() - start;
        __asm__ volatile("" : : "r"(index) : "memory");
    } while (measured < seconds);
    *accesses = count;
    return measured * 1e9 / (double)count;
}

int main(int argc, char **argv)
{
    int source = 2, target = 0, mib = 128, hot_percent = 10, dram_percent = 0;
    double seconds = 0.5;
    int opt;
    const long page_size = sysconf(_SC_PAGESIZE);
    static const struct option opts[] = {
        {"source", required_argument, NULL, 's'}, {"target", required_argument, NULL, 't'},
        {"mib", required_argument, NULL, 'm'}, {"hot-percent", required_argument, NULL, 'p'},
        {"dram-percent", required_argument, NULL, 'r'},
        {"seconds", required_argument, NULL, 'd'}, {"help", no_argument, NULL, 'h'}, {NULL, 0, NULL, 0}
    };
    while ((opt = getopt_long(argc, argv, "s:t:m:p:r:d:h", opts, NULL)) != -1) {
        if (opt == 's') source = atoi(optarg); else if (opt == 't') target = atoi(optarg);
        else if (opt == 'm') mib = atoi(optarg); else if (opt == 'p') hot_percent = atoi(optarg);
        else if (opt == 'r') dram_percent = atoi(optarg);
        else if (opt == 'd') seconds = atof(optarg); else { usage(argv[0]); return opt == 'h' ? 0 : 1; }
    }
    if (page_size <= 0 || mib <= 0 || hot_percent <= 0 || hot_percent > 100 || dram_percent < 0 || dram_percent >= 100 || seconds <= 0 ||
        source < 0 || target < 0 || source > numa_max_node() || target > numa_max_node()) return 1;
    size_t length = (size_t)mib * 1024 * 1024;
    size_t pages_count = length / (size_t)page_size;
    uint8_t *mapping = mmap(NULL, length, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED) { perror("mmap"); return 1; }
    madvise(mapping, length, MADV_NOHUGEPAGE);
    size_t target_initial_count = pages_count * (size_t)dram_percent / 100;
    size_t source_count = pages_count - target_initial_count;
    unsigned long target_mask = 1UL << target;
    unsigned long source_mask = 1UL << source;
    if (target_initial_count && mbind(mapping, target_initial_count * (size_t)page_size, MPOL_BIND, &target_mask, sizeof(target_mask) * 8, MPOL_MF_STRICT | MPOL_MF_MOVE) != 0) { perror("mbind target"); return 1; }
    if (mbind(mapping + target_initial_count * (size_t)page_size, source_count * (size_t)page_size, MPOL_BIND, &source_mask, sizeof(source_mask) * 8, MPOL_MF_STRICT | MPOL_MF_MOVE) != 0) { perror("mbind source"); return 1; }
    memset(mapping, 0x5a, length);
    void **all_pages = calloc(pages_count, sizeof(*all_pages));
    void **hot_pages = calloc(pages_count, sizeof(*hot_pages));
    int *targets = calloc(pages_count, sizeof(*targets));
    int *migration_status = calloc(pages_count, sizeof(*migration_status));
    if (!all_pages || !hot_pages || !targets || !migration_status) return 1;
    size_t hot_count = pages_count * (size_t)hot_percent / 100;
    if (hot_count > source_count) { fprintf(stderr, "hot set exceeds CXL-resident pages\n"); return 1; }
    for (size_t i = 0; i < pages_count; ++i) all_pages[i] = mapping + i * (size_t)page_size;
    for (size_t i = 0; i < hot_count; ++i) { hot_pages[i] = all_pages[target_initial_count + i]; targets[i] = target; }
    uint64_t *order = malloc(hot_count * sizeof(*order));
    if (!order) return 1;
    for (size_t i = 0; i < hot_count; ++i) order[i] = i;
    uint64_t seed = 1;
    for (size_t i = hot_count - 1; i > 0; --i) {
        size_t j = random64(&seed) % (i + 1);
        uint64_t tmp = order[i]; order[i] = order[j]; order[j] = tmp;
    }
    for (size_t i = 0; i < hot_count; ++i) {
        size_t next = (i + 1 == hot_count) ? 0 : i + 1;
        *(uint64_t *)hot_pages[order[i]] = order[next];
    }
    int matched = 0;
    if (placement(all_pages + target_initial_count, source_count, source, &matched) != 0) { perror("placement source"); return 1; }
    int initial_target_matched = 0;
    if (target_initial_count && placement(all_pages, target_initial_count, target, &initial_target_matched) != 0) { perror("placement target"); return 1; }
    uint64_t accesses_before = 0, accesses_after = 0;
    double before = hot_latency(hot_pages, hot_count, order[0], seconds, &accesses_before);
    double migrate_start = clock_seconds();
    int migrate_rc = move_pages(0, hot_count, hot_pages, targets, migration_status, MPOL_MF_MOVE);
    double migrate_seconds = clock_seconds() - migrate_start;
    if (migrate_rc != 0) perror("move_pages migrate");
    int hot_matched = 0;
    placement(hot_pages, hot_count, target, &hot_matched);
    double after = hot_latency(hot_pages, hot_count, order[0], seconds, &accesses_after);
    int migration_errors = 0;
    for (size_t i = 0; i < hot_count; ++i) if (migration_status[i] < 0) ++migration_errors;
    printf("{\"benchmark\":\"migration_bench\",\"source\":%d,\"target\":%d,\"mib\":%d,\"dram_percent\":%d,\"pages\":%zu,\"hot_pages\":%zu,\"initial_source_pages\":%d,\"initial_target_pages\":%d,\"migrated_target_pages\":%d,\"migration_errors\":%d,\"migration_seconds\":%.9f,\"latency_before_ns\":%.3f,\"latency_after_ns\":%.3f,\"accesses_before\":%" PRIu64 ",\"accesses_after\":%" PRIu64 "}\n", source, target, mib, dram_percent, pages_count, hot_count, matched, initial_target_matched, hot_matched, migration_errors, migrate_seconds, before, after, accesses_before, accesses_after);
    free(migration_status); free(order); free(targets); free(hot_pages); free(all_pages); munmap(mapping, length);
    return (migrate_rc == 0 && matched == (int)source_count && initial_target_matched == (int)target_initial_count && hot_matched == (int)hot_count) ? 0 : 1;
}
