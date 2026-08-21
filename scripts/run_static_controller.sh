#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
make -C "$root/benchmarks" static_controller_bench >&2

for threshold in 10 20 30; do
    for pair in "0 2" "1 3"; do
        read -r cpu_node cxl_node <<<"$pair"
        if [[ "$cpu_node" -eq 0 ]]; then cpu=0; else cpu=16; fi
        numactl --physcpubind="$cpu" "$root/benchmarks/static_controller_bench" \
            --cpu-node "$cpu_node" --cxl-node "$cxl_node" \
            --threshold "$threshold" --mib "${MIB:-64}"
    done
done
