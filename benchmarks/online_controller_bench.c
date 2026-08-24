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

static double monotonic_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static int query_nodes(void **pages, size_t count, int *status)
{
    memset(status, 0, count * sizeof(*status));
    return move_pages(0, count, pages, NULL, status, 0);
}

int main(int argc, char **argv)
{
    int dram = 0, cxl = 2, mib = 64, threshold = 20;
    int cycles = 5, max_migrations = 256, interval_ms = 20;
    int option;
    const long page_size = sysconf(_SC_PAGESIZE);
    static const struct option options[] = {
        {"dram-node", required_argument, NULL, 'd'}, {"cxl-node", required_argument, NULL, 'x'},
        {"mib", required_argument, NULL, 'm'}, {"threshold", required_argument, NULL, 't'},
        {"cycles", required_argument, NULL, 'c'}, {"max-migrations", required_argument, NULL, 'l'},
        {"interval-ms", required_argument, NULL, 'i'}, {NULL, 0, NULL, 0}
    };
    while ((option = getopt_long(argc, argv, "d:x:m:t:c:l:i:", options, NULL)) != -1) {
        if (option == 'd') dram = atoi(optarg); else if (option == 'x') cxl = atoi(optarg);
        else if (option == 'm') mib = atoi(optarg); else if (option == 't') threshold = atoi(optarg);
        else if (option == 'c') cycles = atoi(optarg); else if (option == 'l') max_migrations = atoi(optarg);
        else if (option == 'i') interval_ms = atoi(optarg); else return EXIT_FAILURE;
    }
    if (page_size <= 0 || mib <= 0 || threshold < 0 || cycles <= 0 || max_migrations <= 0 ||
        interval_ms < 0 || numa_available() < 0 || dram < 0 || cxl < 0 ||
        dram > numa_max_node() || cxl > numa_max_node()) return EXIT_FAILURE;

    size_t length = (size_t)mib * 1024 * 1024;
    size_t page_count = length / (size_t)page_size;
    uint8_t *mapping = mmap(NULL, length, PROT_READ | PROT_WRITE,
                            MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED) { perror("mmap"); return EXIT_FAILURE; }
    madvise(mapping, length, MADV_NOHUGEPAGE);
    unsigned long mask = 1UL << cxl;
    if (mbind(mapping, length, MPOL_BIND, &mask, sizeof(mask) * 8,
              MPOL_MF_STRICT | MPOL_MF_MOVE) != 0) { perror("mbind"); return EXIT_FAILURE; }
    memset(mapping, 0x3c, length);

    void **all_pages = calloc(page_count, sizeof(*all_pages));
    void **candidates = calloc(page_count, sizeof(*candidates));
    int *nodes = calloc(page_count, sizeof(*nodes));
    int *destinations = calloc(page_count, sizeof(*destinations));
    int *migration_status = calloc(page_count, sizeof(*migration_status));
    if (!all_pages || !candidates || !nodes || !destinations || !migration_status)
        return EXIT_FAILURE;
    for (size_t i = 0; i < page_count; ++i) all_pages[i] = mapping + i * (size_t)page_size;
    if (query_nodes(all_pages, page_count, nodes) != 0) return EXIT_FAILURE;
    for (size_t i = 0; i < page_count; ++i) if (nodes[i] != cxl) return EXIT_FAILURE;

    const size_t hot_count = page_count / 10;
    size_t total_migrated = 0;
    double next_deadline = monotonic_seconds();
    for (int cycle = 0; cycle < cycles; ++cycle) {
        next_deadline += (double)interval_ms / 1000.0;
        double control_start = monotonic_seconds();
        size_t hot_start = ((size_t)cycle * hot_count) % page_count;
        if (query_nodes(all_pages, page_count, nodes) != 0) return EXIT_FAILURE;
        size_t high_delta_pages = 0, eligible = 0;
        uint64_t sum_cpu = 0, sum_cxl = 0;
        uint32_t max_delta = 0;
        for (size_t offset = 0; offset < page_count; ++offset) {
            size_t relative = (offset + page_count - hot_start) % page_count;
            int is_hot = relative < hot_count;
            uint32_t cpu_access = is_hot ? 45 : 10;
            uint32_t cxl_access = 10;
            uint32_t delta = cpu_access - cxl_access;
            sum_cpu += cpu_access; sum_cxl += cxl_access;
            if (delta > max_delta) max_delta = delta;
            if ((int)delta >= threshold) {
                ++high_delta_pages;
                if (nodes[offset] == cxl && eligible < (size_t)max_migrations) {
                    candidates[eligible] = all_pages[offset];
                    destinations[eligible++] = dram;
                }
            }
        }
        double imbalance = (double)(sum_cpu - sum_cxl) / (double)(sum_cpu + sum_cxl);
        double start = monotonic_seconds();
        int migrate_rc = move_pages(0, eligible, candidates, destinations,
                                    migration_status, MPOL_MF_MOVE);
        double migration_seconds = monotonic_seconds() - start;
        int errors = 0;
        for (size_t i = 0; i < eligible; ++i) if (migration_status[i] < 0) ++errors;
        if (query_nodes(candidates, eligible, migration_status) != 0) return EXIT_FAILURE;
        int verified = 0;
        for (size_t i = 0; i < eligible; ++i) if (migration_status[i] == dram) ++verified;
        total_migrated += (size_t)verified;
        double control_seconds = monotonic_seconds() - control_start;
        printf("{\"benchmark\":\"online_controller_bench\",\"cycle\":%d,"
               "\"threshold\":%d,\"max_migrations\":%d,\"interval_ms\":%d,"
               "\"total_pages\":%zu,\"avg_n0\":%.3f,\"avg_n1\":%.3f,"
               "\"max_delta\":%u,\"high_delta_pages\":%zu,"
               "\"imbalance_ratio\":%.6f,\"eligible_pages\":%zu,"
               "\"migrated_pages\":%d,\"migration_errors\":%d,"
               "\"migration_seconds\":%.9f,\"control_seconds\":%.9f,"
               "\"total_migrated_pages\":%zu}\n",
               cycle, threshold, max_migrations, interval_ms, page_count,
               (double)sum_cpu / page_count, (double)sum_cxl / page_count,
               max_delta, high_delta_pages, imbalance, eligible, verified,
               errors, migration_seconds, control_seconds, total_migrated);
        if (migrate_rc != 0 || errors || verified != (int)eligible) return EXIT_FAILURE;
        double remaining = next_deadline - monotonic_seconds();
        if (remaining > 0) usleep((useconds_t)(remaining * 1e6));
    }
    free(migration_status); free(destinations); free(nodes); free(candidates);
    free(all_pages); munmap(mapping, length);
    return EXIT_SUCCESS;
}
