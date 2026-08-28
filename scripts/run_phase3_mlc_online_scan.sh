#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_dir=${1:-/tmp/hotpage-perf-check/phase3-mlc-online-scan}
mkdir -p "$output_dir"
# One control plus the threshold x migration-limit x interval factorial. A cyclic
# rotation prevents any configuration from always occupying the same run slot.
configs=("2:0:0")
for threshold in ${THRESHOLDS:-1 2 4}; do
    for limit in ${MIGRATION_LIMITS:-256 512}; do
        for interval in ${MIGRATION_INTERVALS_MS:-0 20}; do
            configs+=("$threshold:$limit:$interval")
        done
    done
done
repeats=${REPEATS:-4}
for repeat in $(seq 1 "$repeats"); do
    offset=$(((repeat - 1) * 5 % ${#configs[@]}))
    for position in $(seq 0 $((${#configs[@]} - 1))); do
        config=${configs[$(((position + offset) % ${#configs[@]}))]}
        IFS=: read -r threshold limit interval <<<"$config"
        run_dir="$output_dir/t${threshold}-m${limit}-i${interval}-r${repeat}"
        MAX_MIGRATIONS="$limit" WORKLOAD="${WORKLOAD:-W21}" CXL_PERCENT="${CXL_PERCENT:-25}" \
            SAMPLE_SECONDS="${SAMPLE_SECONDS:-5}" MIN_DELTA="$threshold" \
            MIGRATION_INTERVAL_MS="$interval" RUN_POSITION="$((position + 1))" \
            "$root/scripts/run_phase3_mlc_online_pilot.sh" "$run_dir" >"$run_dir.log"
        python3 - "$run_dir/migration.json" "$((position + 1))" <<'PY'
import json, sys
path, position = sys.argv[1:]
row = json.load(open(path))
row["run_position"] = int(position)
json.dump(row, open(path, "w"), indent=2)
PY
    done
done
python3 "$root/analysis/summarize_mlc_online_scan.py" "$output_dir" \
    --output "$output_dir/summary.jsonl"
cat "$output_dir/summary.jsonl"
