#define _GNU_SOURCE

#include <errno.h>
#include <getopt.h>
#include <numa.h>
#include <numaif.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

static void usage(const char *program)
{
    fprintf(stderr,
            "Usage: %s [--source NODE] [--target NODE] [--mib SIZE] "
            "[--no-migrate]\n",
            program);
}

static int query_pages(void **pages, int count, int *status)
{
    memset(status, 0, (size_t)count * sizeof(*status));
    return move_pages(0, (unsigned long)count, pages, NULL, status, 0);
}

static void summarize(const char *phase, const int *status, int count,
                      int source, int target)
{
    int source_count = 0;
    int target_count = 0;
    int other_count = 0;
    int error_count = 0;

    for (int i = 0; i < count; ++i) {
        if (status[i] < 0)
            ++error_count;
        else if (status[i] == source)
            ++source_count;
        else if (status[i] == target)
            ++target_count;
        else
            ++other_count;
    }

    printf("{\"phase\":\"%s\",\"source_node\":%d,\"target_node\":%d,"
           "\"pages\":%d,\"on_source\":%d,\"on_target\":%d,"
           "\"on_other\":%d,\"errors\":%d}\n",
           phase, source, target, count, source_count, target_count,
           other_count, error_count);
}

int main(int argc, char **argv)
{
    int source = 0;
    int target = 2;
    int mib = 16;
    int migrate = 1;
    int option;
    const long page_size = sysconf(_SC_PAGESIZE);
    void *mapping = MAP_FAILED;
    void **pages = NULL;
    int *nodes = NULL;
    int *status = NULL;
    int rc = EXIT_FAILURE;

    static const struct option options[] = {
        {"source", required_argument, NULL, 's'},
        {"target", required_argument, NULL, 't'},
        {"mib", required_argument, NULL, 'm'},
        {"no-migrate", no_argument, NULL, 'n'},
        {"help", no_argument, NULL, 'h'},
        {NULL, 0, NULL, 0},
    };

    while ((option = getopt_long(argc, argv, "s:t:m:nh", options, NULL)) != -1) {
        switch (option) {
        case 's': source = atoi(optarg); break;
        case 't': target = atoi(optarg); break;
        case 'm': mib = atoi(optarg); break;
        case 'n': migrate = 0; break;
        case 'h': usage(argv[0]); return EXIT_SUCCESS;
        default: usage(argv[0]); return EXIT_FAILURE;
        }
    }

    if (page_size <= 0 || mib <= 0 || source < 0 || target < 0 ||
        numa_available() < 0 || source > numa_max_node() || target > numa_max_node()) {
        fprintf(stderr, "invalid arguments or NUMA is unavailable\n");
        return EXIT_FAILURE;
    }

    const size_t length = (size_t)mib * 1024 * 1024;
    const int page_count = (int)(length / (size_t)page_size);
    unsigned long nodemask = 1UL << source;

    mapping = mmap(NULL, length, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED) {
        perror("mmap");
        goto out;
    }
    if (mbind(mapping, length, MPOL_BIND, &nodemask, sizeof(nodemask) * 8,
              MPOL_MF_STRICT | MPOL_MF_MOVE) != 0) {
        perror("mbind source");
        goto out;
    }

    pages = calloc((size_t)page_count, sizeof(*pages));
    nodes = calloc((size_t)page_count, sizeof(*nodes));
    status = calloc((size_t)page_count, sizeof(*status));
    if (!pages || !nodes || !status) {
        perror("calloc");
        goto out;
    }

    for (int i = 0; i < page_count; ++i) {
        pages[i] = (char *)mapping + (size_t)i * (size_t)page_size;
        *(volatile uint8_t *)pages[i] = (uint8_t)i;
        nodes[i] = target;
    }

    if (query_pages(pages, page_count, status) != 0) {
        perror("move_pages query before");
        goto out;
    }
    summarize("before", status, page_count, source, target);

    if (migrate) {
        if (move_pages(0, (unsigned long)page_count, pages, nodes, status,
                       MPOL_MF_MOVE) != 0) {
            perror("move_pages migrate");
            summarize("migration_status", status, page_count, source, target);
            goto out;
        }
        if (query_pages(pages, page_count, status) != 0) {
            perror("move_pages query after");
            goto out;
        }
        summarize("after", status, page_count, source, target);
    }

    rc = EXIT_SUCCESS;
out:
    free(status);
    free(nodes);
    free(pages);
    if (mapping != MAP_FAILED)
        munmap(mapping, length);
    return rc;
}

