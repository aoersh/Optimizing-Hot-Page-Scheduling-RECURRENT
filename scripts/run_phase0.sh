#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
probe="$repo_root/benchmarks/numa_probe"

make -C "$repo_root/benchmarks"
"$repo_root/scripts/discover_hardware.sh"

printf '\n# Self-process allocation and migration probes\n'
numactl --physcpubind=0 "$probe" --source 0 --target 2 --mib 16
numactl --physcpubind=16 "$probe" --source 1 --target 3 --mib 16

printf '\n# Read-only capability checks\n'
if perf stat -e cxl_pmu_mem0.0/clock_ticks/ -- true >/dev/null 2>&1; then
    printf 'cxl_pmu=available\n'
else
    printf 'cxl_pmu=permission_denied_or_unavailable\n'
fi

if [[ -d /sys/kernel/mm/damon/admin ]]; then
    printf 'damon_sysfs=available\n'
else
    printf 'damon_sysfs=unavailable\n'
fi

