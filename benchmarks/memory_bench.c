#define _GNU_SOURCE

#include <errno.h>
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

#define CACHE_LINE 64

static volatile uint64_t sink;

static double now_seconds(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &ts) != 0) {
        perror("clock_gettime");
        exit(EXIT_FAILURE);
    }
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static uint64_t xorshift64(uint64_t *state)
{
    uint64_t x = *state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    *state = x;
    return x;
}

static void usage(const char *program)
{
    fprintf(stderr,
            "Usage: %s --node NODE [--mib SIZE] [--seconds SEC] "
            "[--seed SEED]\n", program);
}

static int verify_placement(void *mapping, size_t length, long page_size,
                            int expected_node, int *matched, int *errors)
{
    const size_t page_count = length / (size_t)page_size;
    void **pages = calloc(page_count, sizeof(*pages));
    int *status = calloc(page_count, sizeof(*status));
    int rc = -1;

    if (!pages || !status) {
        perror("calloc placement");
        goto out;
    }
    for (size_t i = 0; i < page_count; ++i)
        pages[i] = (char *)mapping + i * (size_t)page_size;
    if (move_pages(0, page_count, pages, NULL, status, 0) != 0) {
        perror("move_pages placement");
        goto out;
    }
    *matched = 0;
    *errors = 0;
    for (size_t i = 0; i < page_count; ++i) {
        if (status[i] == expected_node)
            ++*matched;
        else if (status[i] < 0)
            ++*errors;
    }
    rc = (int)page_count;
out:
    free(status);
    free(pages);
    return rc;
}

static void report_bandwidth(const char *operation, int node, size_t length,
                             uint64_t passes, double elapsed)
{
    const double bytes = (double)length * (double)passes;
    printf("{\"benchmark\":\"memory_bench\",\"operation\":\"%s\","
           "\"node\":%d,\"bytes\":%.0f,\"passes\":%" PRIu64 ","
           "\"seconds\":%.9f,\"bandwidth_mib_s\":%.3f}\n",
           operation, node, bytes, passes, elapsed,
           bytes / elapsed / (1024.0 * 1024.0));
}

int main(int argc, char **argv)
{
    int node = -1;
    int mib = 256;
    double duration = 1.0;
    uint64_t seed = 1;
    int option;
    const long page_size = sysconf(_SC_PAGESIZE);
    void *mapping = MAP_FAILED;
    size_t length = 0;
    int rc = EXIT_FAILURE;

    static const struct option options[] = {
        {"node", required_argument, NULL, 'n'},
        {"mib", required_argument, NULL, 'm'},
        {"seconds", required_argument, NULL, 't'},
        {"seed", required_argument, NULL, 's'},
        {"help", no_argument, NULL, 'h'},
        {NULL, 0, NULL, 0},
    };

    while ((option = getopt_long(argc, argv, "n:m:t:s:h", options, NULL)) != -1) {
        switch (option) {
        case 'n': node = atoi(optarg); break;
        case 'm': mib = atoi(optarg); break;
        case 't': duration = atof(optarg); break;
        case 's': seed = strtoull(optarg, NULL, 10); break;
        case 'h': usage(argv[0]); return EXIT_SUCCESS;
        default: usage(argv[0]); return EXIT_FAILURE;
        }
    }

    if (page_size <= 0 || node < 0 || mib <= 0 || duration <= 0.0 ||
        numa_available() < 0 || node > numa_max_node() || node >= 8 * (int)sizeof(unsigned long)) {
        usage(argv[0]);
        return EXIT_FAILURE;
    }

    length = (size_t)mib * 1024 * 1024;
    length -= length % CACHE_LINE;
    unsigned long nodemask = 1UL << node;
    mapping = mmap(NULL, length, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED) {
        perror("mmap");
        goto out;
    }
    if (madvise(mapping, length, MADV_NOHUGEPAGE) != 0) {
        perror("madvise MADV_NOHUGEPAGE");
        goto out;
    }
    if (mbind(mapping, length, MPOL_BIND, &nodemask, sizeof(nodemask) * 8,
              MPOL_MF_STRICT | MPOL_MF_MOVE) != 0) {
        perror("mbind");
        goto out;
    }

    memset(mapping, 0xa5, length);
    int matched = 0;
    int errors = 0;
    int pages = verify_placement(mapping, length, page_size, node, &matched, &errors);
    if (pages < 0)
        goto out;
    printf("{\"benchmark\":\"memory_bench\",\"operation\":\"placement\","
           "\"node\":%d,\"pages\":%d,\"matched\":%d,\"errors\":%d}\n",
           node, pages, matched, errors);
    if (matched != pages) {
        fprintf(stderr, "not all pages are on requested node %d\n", node);
        goto out;
    }

    uint64_t passes = 0;
    uint64_t checksum = 0;
    double start = now_seconds();
    do {
        const uint64_t *data = mapping;
        for (size_t offset = 0; offset < length / sizeof(*data); offset += CACHE_LINE / sizeof(*data))
            checksum += data[offset];
        ++passes;
    } while (now_seconds() - start < duration);
    double elapsed = now_seconds() - start;
    sink = checksum;
    report_bandwidth("sequential_read", node, length, passes, elapsed);

    passes = 0;
    start = now_seconds();
    do {
        uint64_t *data = mapping;
        for (size_t offset = 0; offset < length / sizeof(*data); offset += CACHE_LINE / sizeof(*data))
            data[offset] = passes + offset;
        ++passes;
    } while (now_seconds() - start < duration);
    elapsed = now_seconds() - start;
    report_bandwidth("sequential_write", node, length, passes, elapsed);

    const size_t line_count = length / CACHE_LINE;
    uint64_t *order = malloc(line_count * sizeof(*order));
    if (!order) {
        perror("malloc order");
        goto out;
    }
    for (size_t i = 0; i < line_count; ++i)
        order[i] = i;
    for (size_t i = line_count - 1; i > 0; --i) {
        size_t j = (size_t)(xorshift64(&seed) % (i + 1));
        uint64_t tmp = order[i];
        order[i] = order[j];
        order[j] = tmp;
    }
    for (size_t i = 0; i < line_count; ++i) {
        size_t next = (i + 1 == line_count) ? 0 : i + 1;
        *(uint64_t *)((char *)mapping + order[i] * CACHE_LINE) = order[next];
    }
    uint64_t index = order[0];
    uint64_t accesses = 0;
    start = now_seconds();
    do {
        for (size_t i = 0; i < line_count; ++i) {
            index = *(volatile uint64_t *)((char *)mapping + index * CACHE_LINE);
            ++accesses;
        }
    } while (now_seconds() - start < duration);
    elapsed = now_seconds() - start;
    sink = index;
    printf("{\"benchmark\":\"memory_bench\",\"operation\":\"random_read\","
           "\"node\":%d,\"accesses\":%" PRIu64 ",\"seconds\":%.9f,"
           "\"latency_ns\":%.3f}\n", node, accesses, elapsed,
           elapsed * 1e9 / (double)accesses);
    free(order);
    rc = EXIT_SUCCESS;
out:
    if (mapping != MAP_FAILED)
        munmap(mapping, length);
    return rc;
}

