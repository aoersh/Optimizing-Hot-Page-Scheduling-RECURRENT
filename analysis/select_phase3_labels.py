#!/usr/bin/env python3
"""Select the best parameter label in each phase 3 scenario group."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--latency-tolerance-ns", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    groups = defaultdict(list)
    for line in args.dataset.read_text().splitlines():
        row = json.loads(line)
        if row.get("measurement_available"):
            groups[(row["workload"], row["ratio"], row["scenario"], row["repeat"])].append(row)
    labels = []
    for key, rows in sorted(groups.items()):
        best_latency = min(row["label"]["latency_ns"] for row in rows)
        eligible = [row for row in rows
                    if row["label"]["latency_ns"] <= best_latency + args.latency_tolerance_ns]
        winner = max(eligible, key=lambda row: row["label"]["bandwidth_mb_s"])
        labels.append(winner)
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in labels))
    print(json.dumps({"groups": len(groups), "labels": len(labels),
                      "candidates": sum(len(rows) for rows in groups.values())}, sort_keys=True))
    return 0 if labels else 1


if __name__ == "__main__":
    raise SystemExit(main())
