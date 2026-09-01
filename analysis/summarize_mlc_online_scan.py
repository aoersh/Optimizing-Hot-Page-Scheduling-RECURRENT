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
    parser.add_argument("--winner-output", type=Path)
    parser.add_argument("--min-paired-repeats", type=int, default=5)
    parser.add_argument("--max-latency-degradation-ns", type=float, default=1.0)
    parser.add_argument("--min-bandwidth-improvement-fraction", type=float, default=0.8)
    args = parser.parse_args()
    groups = defaultdict(list)
    controls = {}
    for path in sorted(args.root.glob("*/migration.json")):
        row = json.loads(path.read_text())
        if "repeat" not in row:
            row["repeat"] = int(path.parent.name.rsplit("-r", 1)[1])
        key = (row.get("access_diff_threshold", 2),
               row.get("configured_max_migrations", int(path.parent.name.split("-")[0][1:])),
               row.get("migration_interval_ms", 0))
        groups[key].append(row)
        if key[1] == 0:
            controls[row["repeat"]] = row
    summaries = []
    for (threshold, configured, interval), rows in sorted(groups.items()):
        latency = [row["latency_ns"] for row in rows]
        bandwidth = [row["bandwidth_mb_s"] for row in rows]
        paired = [(controls[row["repeat"]], row) for row in rows
                  if configured and row["repeat"] in controls]
        latency_degradation = [candidate["latency_ns"] - control["latency_ns"]
                               for control, candidate in paired]
        bandwidth_improvement = [candidate["bandwidth_mb_s"] - control["bandwidth_mb_s"]
                                 for control, candidate in paired]
        stable = (len(paired) >= args.min_paired_repeats
                  and statistics.mean(latency_degradation) <= args.max_latency_degradation_ns
                  and sum(value > 0 for value in bandwidth_improvement) / len(paired)
                  >= args.min_bandwidth_improvement_fraction) if paired else False
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
            "paired_repeats": len(paired),
            "latency_degradation_mean_ns": (statistics.mean(latency_degradation)
                                             if paired else None),
            "bandwidth_improvement_mean_mb_s": (statistics.mean(bandwidth_improvement)
                                                  if paired else None),
            "bandwidth_improvement_fraction": (sum(value > 0 for value in bandwidth_improvement)
                                                 / len(paired) if paired else None),
            "stable_candidate": stable,
        })
    if not summaries:
        parser.error("no migration artifacts found")
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in summaries))
    eligible = [row for row in summaries if row["stable_candidate"] and not row["migration_shortfalls"]]
    winner = max(eligible, key=lambda row: row["bandwidth_improvement_mean_mb_s"]) if eligible else None
    if args.winner_output:
        decision = {"decision": "migrate" if winner else "fallback_zero_migration",
                    "winner": winner,
                    "criteria": {"min_paired_repeats": args.min_paired_repeats,
                                 "max_latency_degradation_ns": args.max_latency_degradation_ns,
                                 "min_bandwidth_improvement_fraction":
                                     args.min_bandwidth_improvement_fraction}}
        args.winner_output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"groups": len(summaries), "runs": sum(row["repeats"] for row in summaries),
                      "errors": sum(row["migration_errors"] for row in summaries),
                      "stable_candidates": len(eligible)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
