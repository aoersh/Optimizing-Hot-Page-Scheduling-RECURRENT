#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output="$root/results/migration/$(date +%Y%m%d-%H%M%S).jsonl"
mkdir -p "$(dirname "$output")"
make -C "$root/benchmarks" migration_bench
for pair in "socket0_near_cxl 0 2" "socket1_near_cxl 16 3" "socket0_cross_socket_cxl 0 3" "socket1_cross_socket_cxl 16 2"; do
    read -r name cpu cxl <<<"$pair"
    for dram_percent in 90 75; do
        cxl_percent=$((100 - dram_percent))
        numactl --physcpubind="$cpu" "$root/benchmarks/migration_bench" --source "$cxl" --target "$([[ "$cpu" -lt 16 ]] && echo 0 || echo 1)" --mib "${MIB:-128}" --dram-percent "$dram_percent" --hot-percent "$cxl_percent" --seconds "${SECONDS_PER_TEST:-0.25}" | jq -c --arg scenario "$name" '. + {scenario: $scenario}' | tee -a "$output"
    done
done
printf 'results=%s\n' "$output"
