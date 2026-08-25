#define _GNU_SOURCE
#include <pthread.h>
#include <numa.h>
#include <numaif.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

struct worker {
    volatile uint64_t *base;
    size_t pages;
    int cpu;
    int prefer_first;
    double seconds;
    uint64_t result;
};

static void *run(void *arg)
{
    struct worker *w = arg;
    cpu_set_t set;
    CPU_ZERO(&set); CPU_SET(w->cpu, &set);
    if (pthread_setaffinity_np(pthread_self(), sizeof(set), &set) != 0) return NULL;
    uint64_t state = (uint64_t)(w->cpu + 1), count = 0;
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC_RAW, &now);
    double start = (double)now.tv_sec + (double)now.tv_nsec / 1e9;
    double elapsed;
    do {
        size_t half = w->pages / 2;
        for (size_t i = 0; i < w->pages; ++i) {
            size_t page = (i % 10 < 8) == w->prefer_first ? i % half : half + i % half;
            state ^= state << 13; state ^= state >> 7; state ^= state << 17;
            w->result += w->base[page * 512] + state;
            ++count;
        }
        clock_gettime(CLOCK_MONOTONIC_RAW, &now);
        elapsed = (double)now.tv_sec + (double)now.tv_nsec / 1e9 - start;
    } while (elapsed < w->seconds);
    printf("{\"cpu\":%d,\"accesses\":%llu}\n", w->cpu, (unsigned long long)count);
    return NULL;
}

int main(int argc, char **argv)
{
    int mib = argc > 1 ? atoi(argv[1]) : 64;
    double seconds = argc > 2 ? atof(argv[2]) : 5.0;
    int memory_node = argc > 3 ? atoi(argv[3]) : 2;
    size_t pages = (size_t)mib * 256;
    volatile uint64_t *mapping = mmap(NULL, pages * 4096, PROT_READ | PROT_WRITE,
                                      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED || pages < 2) return 1;
    madvise((void *)mapping, pages * 4096, MADV_NOHUGEPAGE);
    unsigned long mask = 1UL << memory_node;
    if (numa_available() < 0 || memory_node < 0 || memory_node > numa_max_node() ||
        mbind((void *)mapping, pages * 4096, MPOL_BIND, &mask, sizeof(mask) * 8,
              MPOL_MF_STRICT | MPOL_MF_MOVE) != 0) {
        perror("mbind workload");
        return 1;
    }
    memset((void *)mapping, 1, pages * 4096);
    printf("{\"benchmark\":\"shared_heat_bench\",\"pid\":%d,\"pages\":%zu,"
           "\"start\":\"%p\",\"end\":\"%p\",\"memory_node\":%d}\n",
           getpid(), pages, (void *)mapping, (void *)(mapping + pages * 512), memory_node);
    fflush(stdout);
    pthread_t threads[2];
    struct worker workers[2] = {
        {mapping, pages, 0, 1, seconds, 0},
        {mapping, pages, 16, 0, seconds, 0},
    };
    if (pthread_create(&threads[0], NULL, run, &workers[0]) || pthread_create(&threads[1], NULL, run, &workers[1])) return 1;
    pthread_join(threads[0], NULL); pthread_join(threads[1], NULL);
    munmap((void *)mapping, pages * 4096);
    return workers[0].result == 0 || workers[1].result == 0;
}
