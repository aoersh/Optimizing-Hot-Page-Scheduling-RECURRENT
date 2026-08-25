#!/usr/bin/env python3
"""Summarize repeated MLC matrix runs and compute coefficient of variation."""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    groups = defaultdict(list)
    for line in args.summary.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("record") == "summary":
                groups[(row["scenario"], row["workload"], row["ratio"])].append(row)
    output = []
    for key, rows in sorted(groups.items()):
        bandwidth = [row["peak_bandwidth_mb_s"] for row in rows]
        latency = [row["lowest_load_latency_ns"] for row in rows]
        def cv(values):
            mean = statistics.mean(values)
            return statistics.stdev(values) / mean if len(values) > 1 and mean else 0.0
        output.append({
            "scenario": key[0], "workload": key[1], "ratio": key[2], "repeats": len(rows),
            "peak_bandwidth_mean_mb_s": statistics.mean(bandwidth),
            "peak_bandwidth_stdev_mb_s": statistics.stdev(bandwidth) if len(rows) > 1 else 0.0,
            "peak_bandwidth_cv": cv(bandwidth),
            "lowest_load_latency_mean_ns": statistics.mean(latency),
            "lowest_load_latency_stdev_ns": statistics.stdev(latency) if len(rows) > 1 else 0.0,
            "lowest_load_latency_cv": cv(latency),
            "all_points_19": all(row["points"] == 19 for row in rows),
        })
    if not output:
        parser.error("no summary records found")
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output))
    print(json.dumps({"scenarios": len(output), "repeats": sorted({r["repeats"] for r in output}),
                      "max_bandwidth_cv": max(r["peak_bandwidth_cv"] for r in output),
                      "max_latency_cv": max(r["lowest_load_latency_cv"] for r in output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
