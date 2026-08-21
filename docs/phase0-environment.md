# Phase 0: Physical CXL environment validation

## Confirmed topology

The server has two CPU-bearing DRAM nodes and two CPU-less CXL nodes:

| CPU placement | DRAM | Near CXL | Cross-socket CXL |
|---|---:|---:|---:|
| socket 0, CPUs 0-15 | Node 0 | Node 2, distance 14 | Node 3, distance 24 |
| socket 1, CPUs 16-31 | Node 1 | Node 3, distance 14 | Node 2, distance 24 |

Node 2 and Node 3 are 64 GiB DAX devices bound to the `kmem` driver. The
authoritative machine-readable mapping is in `configs/server-topology.json`.

## Run the checks

Run the complete non-destructive phase 0 check from the repository root:

```bash
./scripts/run_phase0.sh
```

The script builds the probe, writes timestamped snapshots under
`results/environment/`, then allocates and migrates 16 MiB in its own process
for the two near-CXL node pairs. It does not change sysctls, CPU frequency,
memory online state, or system-wide NUMA policy.

To test one pair directly:

```bash
make -C benchmarks
numactl --physcpubind=0 ./benchmarks/numa_probe --source 0 --target 2 --mib 16
```

Each output line is JSON. A successful run reports all pages on `source_node`
in the `before` phase and all pages on `target_node` in the `after` phase.

## Known gates

- Intel MLC is not currently present in `PATH`.
- `kernel.perf_event_paranoid=4` blocks CXL PMU and PEBS for this user.
- DAMON sysfs is not exposed at `/sys/kernel/mm/damon/admin`.
- The installed ndctl/cxl userspace is older than the kernel interfaces and
  cannot fully parse the memdev objects. Sysfs, PCI, DAX, and NUMA mappings are
  therefore the source of truth for phase 0.

The next privileged step, when approved, is to grant the experiment process
the minimum performance-monitoring capability and retest PMU/DAMON access.

