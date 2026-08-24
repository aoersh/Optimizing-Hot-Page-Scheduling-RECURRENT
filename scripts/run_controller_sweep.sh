#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output="$root/results/migration/controller-sweep-$(date +%Y%m%d-%H%M%S).jsonl"
mkdir -p "$(dirname "$output")"
make -C "$root/benchmarks" online_controller_bench >&2

for threshold in 10 20 30; do
    for max_migrations in 128 256 512; do
        numactl --physcpubind=0 "$root/benchmarks/online_controller_bench" \
            --dram-node 0 --cxl-node 2 --mib "${MIB:-64}" \
            --threshold "$threshold" --cycles "${CYCLES:-3}" \
            --max-migrations "$max_migrations" --interval-ms "${INTERVAL_MS:-20}" |
            jq -c --argjson threshold "$threshold" --argjson max_migrations "$max_migrations" \
                '. + {sweep_threshold: $threshold, sweep_max_migrations: $max_migrations}' | tee -a "$output"
    done
done
printf 'results=%s\n' "$output" >&2
