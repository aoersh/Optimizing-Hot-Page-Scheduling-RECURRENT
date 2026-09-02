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
        if [[ " ${SKIP_CONFIGS:-} " == *" $config "* ]]; then
            printf 'configuration excluded: %s\n' "$config" >&2
            continue
        fi
        run_dir="$output_dir/t${threshold}-m${limit}-i${interval}-r${repeat}"
        if [[ "${RESUME:-0}" == 1 && -f "$run_dir/migration.json" ]]; then
            if python3 - "$run_dir/migration.json" "$threshold" "$limit" "$interval" "$repeat" <<'PY'
import json, sys
path, threshold, limit, interval, repeat = sys.argv[1:]
try:
    row = json.load(open(path))
except (OSError, ValueError):
    raise SystemExit(1)
expected = {
    "access_diff_threshold": int(threshold),
    "configured_max_migrations": int(limit),
    "migration_interval_ms": int(interval),
    "repeat": int(repeat),
    "migration_status": 0,
    "mlc_points": 19,
}
if any(row.get(key) != value for key, value in expected.items()):
    raise SystemExit(1)
if row.get("migration_errors") != 0:
    raise SystemExit(1)
PY
            then
                printf 'resume: valid run, skipping %s\n' "$run_dir" >&2
                continue
            fi
            printf 'resume: incomplete run, rerunning %s\n' "$run_dir" >&2
        fi
        MAX_MIGRATIONS="$limit" WORKLOAD="${WORKLOAD:-W21}" CXL_PERCENT="${CXL_PERCENT:-25}" \
            SAMPLE_SECONDS="${SAMPLE_SECONDS:-5}" MIN_DELTA="$threshold" \
            MIGRATION_INTERVAL_MS="$interval" RUN_POSITION="$((position + 1))" \
            REPEAT="$repeat" \
            "$root/scripts/run_phase3_mlc_online_pilot.sh" "$run_dir" >"$run_dir.log"
        python3 - "$run_dir/migration.json" "$((position + 1))" "${STRICT_MIGRATION_COUNT:-0}" <<'PY'
import json, sys
path, position, strict = sys.argv[1:]
row = json.load(open(path))
row["run_position"] = int(position)
json.dump(row, open(path, "w"), indent=2)
if strict == "1" and row["verified"] != row["configured_max_migrations"]:
    print(f"migration shortfall: {path}: {row['verified']}/"
          f"{row['configured_max_migrations']}", file=sys.stderr)
    raise SystemExit(2)
PY
    done
done
python3 "$root/analysis/summarize_mlc_online_scan.py" "$output_dir" \
    --output "$output_dir/summary.jsonl"
cat "$output_dir/summary.jsonl"
