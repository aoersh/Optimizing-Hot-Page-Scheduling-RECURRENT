#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_dir=${1:-/tmp/hotpage-perf-check/shared-heat}
mkdir -p "$output_dir"
data="$output_dir/shared-heat.data"
run_log="$output_dir/run.jsonl"
heat="$output_dir/page-heat.jsonl"
features="$output_dir/features.json"
validation="$output_dir/validation.json"
mib=${MIB:-64}
pages=$((mib * 256))

make -C "$root/benchmarks" shared_heat_bench >/dev/null
perf record -c "${SAMPLE_PERIOD:-1000}" -d --sample-cpu \
    -e 'cpu/mem-loads,ldlat=30/P' -o "$data" -- \
    "$root/benchmarks/shared_heat_bench" "$mib" "${DURATION:-5}" >"$run_log"
pid=$(awk -F'[:,]' '/"benchmark":"shared_heat_bench"/ {print $4; exit}' "$run_log")
start=$(sed -n 's/.*"start":"\([^"]*\)".*/\1/p' "$run_log" | head -n 1)
end=$(sed -n 's/.*"end":"\([^"]*\)".*/\1/p' "$run_log" | head -n 1)
if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
    printf 'could not identify benchmark PID\n' >&2
    exit 1
fi
if [[ ! "$start" =~ ^0x[0-9a-f]+$ || ! "$end" =~ ^0x[0-9a-f]+$ ]]; then
    printf 'could not identify workload address range\n' >&2
    exit 1
fi
python3 "$root/analysis/parse_perf_mem.py" "$data" --pid "$pid" --jsonl "$heat" \
    --range "$start" "$end"
python3 "$root/analysis/summarize_page_heat.py" "$heat" --threshold "${THRESHOLD:-10}" \
    --workset-pages "$pages" --output "$features"
python3 "$root/analysis/evaluate_shared_heat.py" "$heat" --start "$start" --pages "$pages" \
    --output "$validation"
printf 'data=%s\nheat=%s\nfeatures=%s\nvalidation=%s\npid=%s\n' \
    "$data" "$heat" "$features" "$validation" "$pid"
