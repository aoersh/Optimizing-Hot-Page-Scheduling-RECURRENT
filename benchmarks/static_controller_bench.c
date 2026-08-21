#define _GNU_SOURCE

#include <getopt.h>
#include <numa.h>
#include <numaif.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

static double now_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static int count_pages_on_node(void **pages, size_t count, int node)
{
    int *status = calloc(count, sizeof(*status));
    if (!status || move_pages(0, count, pages, NULL, status, 0) != 0) {
        free(status);
        return -1;
    }
    int matched = 0;
    for (size_t i = 0; i < count; ++i)
        if (status[i] == node) ++matched;
    free(status);
    return matched;
}

int main(int argc, char **argv)
{
    int cpu_node = 0, cxl_node = 2, mib = 64, threshold = 20;
    int option;
    const long page_size = sysconf(_SC_PAGESIZE);
    static const struct option options[] = {
        {"cpu-node", required_argument, NULL, 'c'},
        {"cxl-node", required_argument, NULL, 'x'},
        {"mib", required_argument, NULL, 'm'},
        {"threshold", required_argument, NULL, 't'},
        {NULL, 0, NULL, 0}
    };
    while ((option = getopt_long(argc, argv, "c:x:m:t:", options, NULL)) != -1) {
        if (option == 'c') cpu_node = atoi(optarg);
        else if (option == 'x') cxl_node = atoi(optarg);
        else if (option == 'm') mib = atoi(optarg);
        else if (option == 't') threshold = atoi(optarg);
        else return EXIT_FAILURE;
    }
    if (page_size <= 0 || mib <= 0 || threshold < 0 || numa_available() < 0 ||
        cpu_node < 0 || cxl_node < 0 || cpu_node > numa_max_node() || cxl_node > numa_max_node())
        return EXIT_FAILURE;

    size_t length = (size_t)mib * 1024 * 1024;
    size_t page_count = length / (size_t)page_size;
    uint8_t *mapping = mmap(NULL, length, PROT_READ | PROT_WRITE,
                            MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED) { perror("mmap"); return EXIT_FAILURE; }
    madvise(mapping, length, MADV_NOHUGEPAGE);
    unsigned long mask = 1UL << cxl_node;
    if (mbind(mapping, length, MPOL_BIND, &mask, sizeof(mask) * 8,
              MPOL_MF_STRICT | MPOL_MF_MOVE) != 0) {
        perror("mbind"); return EXIT_FAILURE;
    }
    memset(mapping, 0x7f, length);

    void **all_pages = calloc(page_count, sizeof(*all_pages));
    void **candidates = calloc(page_count, sizeof(*candidates));
    int *destinations = calloc(page_count, sizeof(*destinations));
    int *migration_status = calloc(page_count, sizeof(*migration_status));
    uint32_t *n0 = calloc(page_count, sizeof(*n0));
    uint32_t *n1 = calloc(page_count, sizeof(*n1));
    if (!all_pages || !candidates || !destinations || !migration_status || !n0 || !n1)
        return EXIT_FAILURE;
    for (size_t i = 0; i < page_count; ++i)
        all_pages[i] = mapping + i * (size_t)page_size;
    if (count_pages_on_node(all_pages, page_count, cxl_node) != (int)page_count)
        return EXIT_FAILURE;

    size_t known_hot = page_count / 10;
    uint64_t sum_n0 = 0, sum_n1 = 0;
    uint32_t max_delta = 0, high_delta_pages = 0;
    size_t candidate_count = 0;
    for (size_t i = 0; i < page_count; ++i) {
        if (i < known_hot) {
            size_t band = (i * 3) / known_hot;
            n0[i] = (uint32_t)(25 + band * 10); /* delta bands: 15, 25, 35 */
            n1[i] = 10;
        } else {
            n0[i] = 10;
            n1[i] = 10;
        }
        sum_n0 += n0[i]; sum_n1 += n1[i];
        uint32_t delta = n0[i] > n1[i] ? n0[i] - n1[i] : n1[i] - n0[i];
        if (delta > max_delta) max_delta = delta;
        if ((int)delta >= threshold) {
            ++high_delta_pages;
            candidates[candidate_count] = all_pages[i];
            destinations[candidate_count++] = cpu_node;
        }
    }
    double imbalance = (sum_n0 + sum_n1) ?
        (double)(sum_n0 > sum_n1 ? sum_n0 - sum_n1 : sum_n1 - sum_n0) /
        (double)(sum_n0 + sum_n1) : 0.0;
    double start = now_seconds();
    int migrate_rc = move_pages(0, candidate_count, candidates, destinations,
                                migration_status, MPOL_MF_MOVE);
    double migration_seconds = now_seconds() - start;
    int migration_errors = 0;
    for (size_t i = 0; i < candidate_count; ++i)
        if (migration_status[i] < 0) ++migration_errors;
    int migrated = candidate_count ? count_pages_on_node(candidates, candidate_count, cpu_node) : 0;
    printf("{\"benchmark\":\"static_controller_bench\",\"cpu_node\":%d,"
           "\"cxl_node\":%d,\"threshold\":%d,\"total_pages\":%zu,"
           "\"avg_n0\":%.3f,\"avg_n1\":%.3f,\"max_delta\":%u,"
           "\"high_delta_pages\":%u,\"imbalance_ratio\":%.6f,"
           "\"known_hot_pages\":%zu,\"candidates\":%zu,"
           "\"migrated_to_dram\":%d,\"migration_errors\":%d,"
           "\"migration_seconds\":%.9f}\n",
           cpu_node, cxl_node, threshold, page_count,
           (double)sum_n0 / page_count, (double)sum_n1 / page_count,
           max_delta, high_delta_pages, imbalance, known_hot, candidate_count,
           migrated, migration_errors, migration_seconds);
    free(n1); free(n0); free(migration_status); free(destinations);
    free(candidates); free(all_pages); munmap(mapping, length);
    return migrate_rc == 0 && migration_errors == 0 && migrated == (int)candidate_count ?
        EXIT_SUCCESS : EXIT_FAILURE;
}
