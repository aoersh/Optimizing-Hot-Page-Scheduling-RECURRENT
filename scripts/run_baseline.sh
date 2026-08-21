#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mib=${MIB:-256}
seconds=${SECONDS_PER_TEST:-1}
repeats=${REPEATS:-3}
timestamp=$(date +%Y%m%d-%H%M%S)
output="$repo_root/results/baseline/$timestamp.jsonl"

mkdir -p "$(dirname "$output")"
make -C "$repo_root/benchmarks" memory_bench

run_case() {
    local name=$1 cpu=$2 node=$3 repeat=$4
    printf '{"record":"run","scenario":"%s","cpu":%d,"memory_node":%d,"repeat":%d,"mib":%d,"seconds_per_test":%s}\n' \
        "$name" "$cpu" "$node" "$repeat" "$mib" "$seconds" | tee -a "$output"
    numactl --physcpubind="$cpu" "$repo_root/benchmarks/memory_bench" \
        --node "$node" --mib "$mib" --seconds "$seconds" --seed "$repeat" | \
        jq -c --arg scenario "$name" --argjson cpu "$cpu" --argjson repeat "$repeat" \
        '. + {scenario: $scenario, cpu: $cpu, repeat: $repeat}' | tee -a "$output"
}

for repeat in $(seq 1 "$repeats"); do
    run_case socket0_local_dram 0 0 "$repeat"
    run_case socket0_near_cxl 0 2 "$repeat"
    run_case socket0_cross_socket_cxl 0 3 "$repeat"
    run_case socket1_local_dram 16 1 "$repeat"
    run_case socket1_near_cxl 16 3 "$repeat"
    run_case socket1_cross_socket_cxl 16 2 "$repeat"
done

printf 'results=%s\n' "$output"

