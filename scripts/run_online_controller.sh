#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
make -C "$root/benchmarks" online_controller_bench >&2

numactl --physcpubind=0 "$root/benchmarks/online_controller_bench" \
    --dram-node 0 --cxl-node 2 --mib "${MIB:-64}" \
    --threshold "${THRESHOLD:-20}" --cycles "${CYCLES:-5}" \
    --max-migrations "${MAX_MIGRATIONS:-256}" --interval-ms "${INTERVAL_MS:-20}"
