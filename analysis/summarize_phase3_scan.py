#!/usr/bin/env python3
"""Aggregate repeated phase 3 candidates and select a stable winner."""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--latency-tolerance-ns", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--winner-output", type=Path, required=True)
    args = parser.parse_args()
    groups = defaultdict(list)
    for line in args.dataset.read_text().splitlines():
        row = json.loads(line)
        if not row.get("measurement_available"):
            continue
        label = row["label"]
        key = (row["workload"], row["ratio"], row["scenario"],
               label["access_diff_threshold"], label["max_migrations"],
               label["migration_interval_ms"])
        groups[key].append(row)
    summaries = []
    for key, rows in sorted(groups.items()):
        latency = [row["label"]["latency_ns"] for row in rows]
        bandwidth = [row["label"]["bandwidth_mb_s"] for row in rows]
        summaries.append({
            "workload": key[0], "ratio": key[1], "scenario": key[2],
            "access_diff_threshold": key[3], "max_migrations": key[4],
            "migration_interval_ms": key[5], "repeats": len(rows),
            "latency_mean_ns": statistics.mean(latency),
            "latency_stdev_ns": statistics.stdev(latency) if len(rows) > 1 else 0.0,
            "latency_cv": statistics.stdev(latency) / statistics.mean(latency) if len(rows) > 1 else 0.0,
            "bandwidth_mean_mb_s": statistics.mean(bandwidth),
            "bandwidth_stdev_mb_s": statistics.stdev(bandwidth) if len(rows) > 1 else 0.0,
            "bandwidth_cv": statistics.stdev(bandwidth) / statistics.mean(bandwidth) if len(rows) > 1 else 0.0,
        })
    if not summaries:
        parser.error("no training-ready records")
    best_latency = min(row["latency_mean_ns"] for row in summaries)
    eligible = [row for row in summaries
                if row["latency_mean_ns"] <= best_latency + args.latency_tolerance_ns]
    winner = max(eligible, key=lambda row: row["bandwidth_mean_mb_s"])
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in summaries))
    args.winner_output.write_text(json.dumps(winner, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"configurations": len(summaries), "winner": winner,
                      "repeat_counts": sorted({row["repeats"] for row in summaries})}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
