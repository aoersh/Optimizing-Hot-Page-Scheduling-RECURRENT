#define _GNU_SOURCE
#include <errno.h>
#include <numaif.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <time.h>

static double now_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

int main(int argc, char **argv)
{
    if (argc < 4 || argc > 6) {
        fprintf(stderr, "usage: %s PID TARGET_NODE ADDRESSES [SOURCE_NODE] [MAX_PAGES]\n", argv[0]);
        return 2;
    }
    pid_t pid = (pid_t)strtol(argv[1], NULL, 10);
    int target = atoi(argv[2]);
    int source = argc >= 5 ? atoi(argv[4]) : -1;
    size_t limit = argc >= 6 ? (size_t)strtoull(argv[5], NULL, 10) : (size_t)-1;
    FILE *input = fopen(argv[3], "r");
    if (pid <= 0 || target < 0 || !input) return 2;
    size_t capacity = 256, count = 0;
    void **pages = malloc(capacity * sizeof(*pages));
    if (!pages) return 1;
    unsigned long address;
    while (fscanf(input, "%lx", &address) == 1) {
        if (count == capacity) {
            capacity *= 2;
            void **grown = realloc(pages, capacity * sizeof(*pages));
            if (!grown) return 1;
            pages = grown;
        }
        pages[count++] = (void *)address;
    }
    fclose(input);
    int *nodes = calloc(count, sizeof(*nodes));
    int *targets = malloc(count * sizeof(*targets));
    if (!nodes || !targets) return 1;
    if (count == 0) {
        printf("{\"pid\":%d,\"target\":%d,\"requested\":0,\"query_rc\":0,"
               "\"migrate_rc\":0,\"migration_errors\":0,\"verify_rc\":0,"
               "\"verified\":0,\"migration_seconds\":0.0,\"errno\":0}\n", pid, target);
        return 0;
    }
    size_t input_count = count;
    int query_rc = move_pages(pid, count, pages, NULL, nodes, 0);
    int before_nodes[4] = {0, 0, 0, 0};
    for (size_t i = 0; i < count; ++i) {
        if (nodes[i] >= 0 && nodes[i] < 4) ++before_nodes[nodes[i]];
    }
    size_t eligible = 0;
    for (size_t i = 0; i < count && eligible < limit; ++i) {
        if (source < 0 || nodes[i] == source) pages[eligible++] = pages[i];
    }
    count = eligible;
    for (size_t i = 0; i < count; ++i) targets[i] = target;
    if (count == 0) {
        printf("{\"pid\":%d,\"target\":%d,\"input_pages\":%zu,\"source_filter\":%d,"
               "\"requested\":0,\"before_nodes\":[%d,%d,%d,%d],\"query_rc\":%d,"
               "\"migrate_rc\":0,\"migration_errors\":0,\"verify_rc\":0,"
               "\"verified\":0,\"migration_seconds\":0.0,\"errno\":0}\n",
               pid, target, input_count, source, before_nodes[0], before_nodes[1],
               before_nodes[2], before_nodes[3], query_rc);
        free(targets); free(nodes); free(pages);
        return query_rc != 0;
    }
    double start = now_seconds();
    int migrate_rc = move_pages(pid, count, pages, targets, nodes, MPOL_MF_MOVE);
    double migration_seconds = now_seconds() - start;
    int errors = 0;
    for (size_t i = 0; i < count; ++i) if (nodes[i] < 0) ++errors;
    int verify_rc = move_pages(pid, count, pages, NULL, nodes, 0);
    int verified = 0;
    for (size_t i = 0; i < count; ++i) if (nodes[i] == target) ++verified;
    printf("{\"pid\":%d,\"target\":%d,\"input_pages\":%zu,\"source_filter\":%d,\"requested\":%zu,"
           "\"before_nodes\":[%d,%d,%d,%d],"
           "\"query_rc\":%d,\"migrate_rc\":%d,\"migration_errors\":%d,"
           "\"verify_rc\":%d,\"verified\":%d,\"migration_seconds\":%.9f,\"errno\":%d}\n",
           pid, target, input_count, source, count, before_nodes[0], before_nodes[1], before_nodes[2], before_nodes[3],
           query_rc, migrate_rc, errors, verify_rc, verified, migration_seconds, errno);
    free(targets); free(nodes); free(pages);
    return query_rc || migrate_rc || verify_rc || errors || verified != (int)count;
}
