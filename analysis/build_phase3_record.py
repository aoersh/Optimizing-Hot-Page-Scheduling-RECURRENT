#!/usr/bin/env python3
"""Build one traceable phase 3 record from feature and migration artifacts."""
import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--workload", default="shared_heat_bench")
    parser.add_argument("--ratio", default="cxl-only")
    parser.add_argument("--scenario", default="node2-to-node0-1")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-migrations", type=int, required=True)
    parser.add_argument("--threshold", type=int, required=True)
    parser.add_argument("--interval-ms", type=int, default=0)
    parser.add_argument("--source-artifacts", nargs="+", required=True)
    args = parser.parse_args()
    features = json.loads(args.features.read_text())
    migration = json.loads(args.migration.read_text())
    latency = migration.get("latency_ns", migration.get("lowest_load_latency_ns"))
    bandwidth = migration.get("bandwidth_mb_s", migration.get("peak_bandwidth_mb_s"))
    measurement_available = latency is not None and bandwidth is not None
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    record = {
        "run_id": args.run_id, "workload": args.workload, "ratio": args.ratio,
        "scenario": args.scenario, "repeat": args.repeat, "git_revision": revision,
        "features": {key: features[key] for key in
                      ("total_pages", "avg_n0", "avg_n1", "max_delta", "high_delta_pages", "imbalance_ratio")},
        "label": {"max_migrations": args.max_migrations,
                   "access_diff_threshold": args.threshold,
                   "migration_interval_ms": args.interval_ms,
                   "latency_ns": latency, "bandwidth_mb_s": bandwidth},
        "measurement_available": measurement_available,
        "source_artifacts": args.source_artifacts,
    }
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
