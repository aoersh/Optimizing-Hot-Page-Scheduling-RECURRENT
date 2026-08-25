#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_dir=${1:-/tmp/hotpage-perf-check/real-heat-migration}
mkdir -p "$output_dir"
run_log="$output_dir/run.jsonl"
data="$output_dir/pebs.data"
heat="$output_dir/page-heat.jsonl"
features="$output_dir/features.json"
node0_pages="$output_dir/node0.pages"
node1_pages="$output_dir/node1.pages"
result="$output_dir/migration.json"
mib=${MIB:-8}
duration=${DURATION:-15}
pages=$((mib * 256))

make -C "$root/benchmarks" shared_heat_bench migrate_pid_pages >/dev/null
"$root/benchmarks/shared_heat_bench" "$mib" "$duration" 2 >"$run_log" &
workload_pid=$!
for _ in $(seq 1 50); do
    grep -q '"benchmark":"shared_heat_bench"' "$run_log" && break
    sleep 0.1
done
pid=$(sed -n 's/.*"pid":\([0-9][0-9]*\).*/\1/p' "$run_log" | head -n 1)
start=$(sed -n 's/.*"start":"\([^"]*\)".*/\1/p' "$run_log" | head -n 1)
end=$(sed -n 's/.*"end":"\([^"]*\)".*/\1/p' "$run_log" | head -n 1)
if [[ ! "$pid" =~ ^[0-9]+$ || ! "$start" =~ ^0x[0-9a-f]+$ || ! "$end" =~ ^0x[0-9a-f]+$ ]]; then
    kill "$workload_pid" 2>/dev/null || true
    exit 1
fi
perf record -p "$pid" -c "${SAMPLE_PERIOD:-1000}" -d --sample-cpu \
    -e 'cpu/mem-loads,ldlat=30/P' -o "$data" -- sleep "${SAMPLE_SECONDS:-5}" &
perf_pid=$!
wait "$perf_pid"
python3 "$root/analysis/parse_perf_mem.py" "$data" --pid "$pid" --jsonl "$heat" --range "$start" "$end"
python3 "$root/analysis/summarize_page_heat.py" "$heat" --threshold "${THRESHOLD:-2}" \
    --workset-pages "$pages" --output "$features"
python3 "$root/analysis/select_heat_pages.py" "$heat" --min-delta "${MIN_DELTA:-2}" \
    --max-pages "${MAX_MIGRATIONS:-128}" --node0-output "$node0_pages" --node1-output "$node1_pages"
set +e
node0_result=$("$root/benchmarks/migrate_pid_pages" "$pid" 0 "$node0_pages")
node0_status=$?
node1_result=$("$root/benchmarks/migrate_pid_pages" "$pid" 1 "$node1_pages")
node1_status=$?
set -e
python3 -c 'import json,sys; json.dump({"pid":int(sys.argv[1]),"node0":json.loads(sys.argv[2]),"node1":json.loads(sys.argv[3]),"status":[int(sys.argv[4]),int(sys.argv[5])]},open(sys.argv[6],"w"),indent=2); print(open(sys.argv[6]).read())' "$pid" "$node0_result" "$node1_result" "$node0_status" "$node1_status" "$result"
wait "$workload_pid" || true
printf 'data=%s\nheat=%s\nfeatures=%s\nmigration=%s\n' "$data" "$heat" "$features" "$result"
