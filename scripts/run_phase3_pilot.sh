#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
config=${PHASE3_CONFIG:-"$root/configs/phase3_scan.json"}
run_id=${RUN_ID:-$(date +%Y%m%d-%H%M%S)}
output_dir=${1:-"/tmp/hotpage-perf-check/phase3-$run_id"}
mkdir -p "$output_dir/runs"
dataset="$output_dir/dataset.jsonl"
labels="$output_dir/labels.jsonl"
summary="$output_dir/scan-summary.jsonl"
winner="$output_dir/winner.json"
: >"$dataset"
repeats=${REPEATS:-1}

mapfile -t thresholds < <(jq -r '.min_delta_values[]' "$config")
mapfile -t limits < <(jq -r '.max_migrations_values[]' "$config")
mapfile -t intervals < <(jq -r '.migration_interval_ms_values[]' "$config")
for threshold in "${thresholds[@]}"; do
    for limit in "${limits[@]}"; do
        for interval in "${intervals[@]}"; do
            for repeat in $(seq 1 "$repeats"); do
            stem="t${threshold}-m${limit}-i${interval}-r${repeat}"
            run_dir="$output_dir/runs/$stem"
            MIB="${MIB:-2}" DURATION="${DURATION:-5}" SAMPLE_SECONDS="${SAMPLE_SECONDS:-2}" \
                SAMPLE_PERIOD="$(jq -r '.sample_period' "$config")" MIN_DELTA="$threshold" \
                THRESHOLD="$threshold" MAX_MIGRATIONS="$limit" MIGRATION_INTERVAL_MS="$interval" \
                "$root/scripts/run_real_heat_migration.sh" "$run_dir" >"$run_dir.log"
            python3 "$root/analysis/build_phase3_record.py" --features "$run_dir/features.json" \
                --migration "$run_dir/migration.json" --run-id "$run_id-$stem" --repeat "$repeat" \
                --max-migrations "$limit" --threshold "$threshold" --interval-ms "$interval" \
                --source-artifacts "$run_dir/pebs.data" "$run_dir/page-heat.jsonl" \
                "$run_dir/features.json" "$run_dir/migration.json" >>"$dataset"
            done
        done
    done
done
python3 "$root/analysis/validate_phase3_dataset.py" "$dataset"
python3 "$root/analysis/select_phase3_labels.py" "$dataset" \
    --latency-tolerance-ns "$(jq -r '.objective.latency_tolerance_ns' "$config")" --output "$labels"
python3 "$root/analysis/summarize_phase3_scan.py" "$dataset" \
    --latency-tolerance-ns "$(jq -r '.objective.latency_tolerance_ns' "$config")" \
    --output "$summary" --winner-output "$winner"
printf 'dataset=%s\nlabels=%s\nsummary=%s\nwinner=%s\n' "$dataset" "$labels" "$summary" "$winner"
