#!/usr/bin/env python3
"""Summarize MLC online migration scan artifacts."""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    groups = defaultdict(list)
    for path in sorted(args.root.glob("*/migration.json")):
        row = json.loads(path.read_text())
        key = (row.get("access_diff_threshold", 2),
               row.get("configured_max_migrations", int(path.parent.name.split("-")[0][1:])),
               row.get("migration_interval_ms", 0))
        groups[key].append(row)
    summaries = []
    for (threshold, configured, interval), rows in sorted(groups.items()):
        latency = [row["latency_ns"] for row in rows]
        bandwidth = [row["bandwidth_mb_s"] for row in rows]
        summaries.append({
            "access_diff_threshold": threshold,
            "configured_max_migrations": configured,
            "migration_interval_ms": interval, "repeats": len(rows),
            "actual_migrations": [row["verified"] for row in rows],
            "migration_shortfalls": sum(
                row["verified"] != configured for row in rows),
            "latency_mean_ns": statistics.mean(latency),
            "latency_stdev_ns": statistics.stdev(latency) if len(rows) > 1 else 0.0,
            "latency_cv": statistics.stdev(latency) / statistics.mean(latency) if len(rows) > 1 else 0.0,
            "bandwidth_mean_mb_s": statistics.mean(bandwidth),
            "bandwidth_stdev_mb_s": statistics.stdev(bandwidth) if len(rows) > 1 else 0.0,
            "bandwidth_cv": statistics.stdev(bandwidth) / statistics.mean(bandwidth) if len(rows) > 1 else 0.0,
            "migration_errors": sum(row["migration_errors"] for row in rows),
            "perf_out_of_order_events": sum(row.get("perf_out_of_order_events", 0) for row in rows),
        })
    if not summaries:
        parser.error("no migration artifacts found")
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in summaries))
    print(json.dumps({"groups": len(summaries), "runs": sum(row["repeats"] for row in summaries),
                      "errors": sum(row["migration_errors"] for row in summaries)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
