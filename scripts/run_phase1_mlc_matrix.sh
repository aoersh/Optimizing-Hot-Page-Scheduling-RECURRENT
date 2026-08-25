#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
run_id=${RUN_ID:-$(date +%Y%m%d-%H%M%S)}
output_dir=${1:-"$root/results/mlc/$run_id"}
mkdir -p "$output_dir/raw" "$output_dir/configs" "$output_dir/parsed"
mlc=${MLC_BIN:-"$root/third_party/intel-mlc/Linux/mlc"}
repeats=${REPEATS:-5}
buffer_kib=${BUFFER_KIB:-65536}
time_seconds=${TIME_SECONDS:-1}
summary="$output_dir/summary.jsonl"
: >"$summary"

scenarios=${SCENARIOS:-"socket0:0:1-15:0:2 socket1:16:17-31:1:3"}
for scenario_spec in $scenarios; do
    IFS=: read -r scenario latency_cpu traffic_cpus dram_node cxl_node <<<"$scenario_spec"
    cpu_list="$latency_cpu,$traffic_cpus"
    for workload in ${WORKLOADS:-W21 W23 W27}; do
        for cxl_percent in ${CXL_PERCENTS:-10 25}; do
            ratio="$((100-cxl_percent)):$cxl_percent"
            config="$output_dir/configs/${scenario}-${workload}-${ratio//:/_}.conf"
            printf '%s %s seq %s dram %s dram %s %s\n' \
                "$traffic_cpus" "$workload" "$buffer_kib" "$dram_node" "$cxl_node" "$cxl_percent" >"$config"
            for repeat in $(seq 1 "$repeats"); do
                stem="${scenario}-${workload}-${ratio//:/_}-r${repeat}"
                raw="$output_dir/raw/$stem.txt"
                parsed="$output_dir/parsed/$stem.jsonl"
                numactl --physcpubind="$cpu_list" "$mlc" --loaded_latency -e -r \
                    -c"$latency_cpu" -j"$dram_node" -o"$config" -t"$time_seconds" >"$raw" 2>&1
                python3 "$root/analysis/parse_mlc_loaded_latency.py" "$raw" --output "$parsed" \
                    --workload "$workload" --ratio "$ratio" --scenario "$scenario" --repeat "$repeat" \
                    | tee -a "$summary"
            done
        done
    done
done
printf 'results=%s\n' "$output_dir"
