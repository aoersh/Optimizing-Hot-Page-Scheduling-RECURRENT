#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_dir=${1:-/tmp/hotpage-perf-check/phase3-mlc-online}
mkdir -p "$output_dir"
mlc=${MLC_BIN:-"$root/third_party/intel-mlc/Linux/mlc"}
workload=${WORKLOAD:-W21}
cxl_percent=${CXL_PERCENT:-25}
ratio="$((100-cxl_percent)):$cxl_percent"
config="$output_dir/mlc.conf"
raw="$output_dir/mlc.txt"
data="$output_dir/pebs.data"
perf_log="$output_dir/perf-record.log"
heat="$output_dir/page-heat.jsonl"
features="$output_dir/features.json"
pages="$output_dir/candidates.pages"
migration="$output_dir/migration.json"
curve="$output_dir/mlc-curve.jsonl"
mlc_thread_range=${MLC_THREAD_RANGE:-1-15}
cpu_bind=${CPU_BIND:-0-15}
cpu_node=${CPU_NODE:-0}
dram_node=${DRAM_NODE:-0}
cxl_node=${CXL_NODE:-2}
hot_access_node=${HOT_ACCESS_NODE:-0}
if [[ "$hot_access_node" != 0 && "$hot_access_node" != 1 ]]; then
    printf 'HOT_ACCESS_NODE must be 0 or 1\n' >&2
    exit 2
fi

printf '%s %s seq %s dram %s dram %s %s\n' \
    "$mlc_thread_range" "$workload" "${BUFFER_KIB:-65536}" \
    "$dram_node" "$cxl_node" "$cxl_percent" >"$config"
make -C "$root/benchmarks" migrate_pid_pages >/dev/null
numactl --physcpubind="$cpu_bind" "$mlc" --loaded_latency -e -r \
    -c"$cpu_node" -j"$cpu_node" \
    -o"$config" -t"${MLC_TIME:-1}" >"$raw" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
sleep "${ATTACH_DELAY:-1}"
perf record -p "$pid" -c "${SAMPLE_PERIOD:-1000}" -d --sample-cpu \
    -e 'cpu/mem-loads,ldlat=30/P' -o "$data" -- sleep "${SAMPLE_SECONDS:-5}" \
    2>"$perf_log"
python3 "$root/analysis/parse_perf_mem.py" "$data" --pid "$pid" --jsonl "$heat" \
    --all-anonymous-min-kib "${MIN_MAPPING_KIB:-32768}"
workset_pages=$((15 * 2 * ${BUFFER_KIB:-65536} / 4))
python3 "$root/analysis/summarize_page_heat.py" "$heat" --threshold "${MIN_DELTA:-2}" \
    --workset-pages "$workset_pages" --output "$features"
node0_pages="$output_dir/node0.pages"
node1_pages="$output_dir/node1.pages"
python3 "$root/analysis/select_heat_pages.py" "$heat" --min-delta "${MIN_DELTA:-2}" \
    --max-pages "${CANDIDATE_POOL:-4096}" --node0-output "$node0_pages" \
    --node1-output "$node1_pages"
cp "$output_dir/node${hot_access_node}.pages" "$pages"
sleep "$(awk -v ms="${MIGRATION_INTERVAL_MS:-0}" 'BEGIN {printf "%.3f", ms / 1000}')"
set +e
"$root/benchmarks/migrate_pid_pages" "$pid" "$dram_node" "$pages" "$cxl_node" \
    "${MAX_MIGRATIONS:-64}" >"$migration"
migration_status=$?
set -e
wait "$pid"
trap - EXIT
python3 "$root/analysis/parse_mlc_loaded_latency.py" "$raw" --output "$curve" \
    --workload "$workload" --ratio "$ratio" \
    --scenario "socket${cpu_node}-online" --repeat 1 >"$output_dir/mlc-summary.json"
python3 - "$migration" "$output_dir/mlc-summary.json" "$migration_status" \
    "$perf_log" "${MIN_DELTA:-2}" "${MAX_MIGRATIONS:-64}" \
    "${MIGRATION_INTERVAL_MS:-0}" <<'PY'
import json, re, sys
migration_path, summary_path, status, perf_path, threshold, limit, interval = sys.argv[1:]
migration = json.load(open(migration_path)); summary = json.load(open(summary_path))
perf_text = open(perf_path).read()
out_of_order = sum(int(value.replace(",", "")) for value in
                   re.findall(r"([0-9][0-9,]*) out of order events", perf_text))
migration.update({"latency_ns": summary["lowest_load_latency_ns"],
                  "bandwidth_mb_s": summary["peak_bandwidth_mb_s"],
                  "mlc_points": summary["points"], "migration_status": int(status),
                  "access_diff_threshold": int(threshold),
                  "configured_max_migrations": int(limit),
                  "migration_interval_ms": int(interval),
                  "repeat": int(__import__('os').environ.get('REPEAT', '1')),
                  "perf_out_of_order_events": out_of_order})
json.dump(migration, open(migration_path, "w"), indent=2)
PY
cat "$migration"
printf 'features=%s\nmigration=%s\ncurve=%s\n' "$features" "$migration" "$curve"
