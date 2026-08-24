#!/usr/bin/env python3
import json
import statistics
import sys
from collections import defaultdict


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} SWEEP.jsonl", file=sys.stderr)
        return 2
    groups = defaultdict(list)
    with open(sys.argv[1], encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            key = (row["sweep_threshold"], row["sweep_max_migrations"])
            groups[key].append(row)
    print("threshold,max_migrations,cycles,total_migrated,mean_control_ms,max_control_ms,errors")
    for (threshold, limit), rows in sorted(groups.items()):
        controls = [row["control_seconds"] * 1000 for row in rows]
        print(f"{threshold},{limit},{len(rows)},"
              f"{sum(row['migrated_pages'] for row in rows)},"
              f"{statistics.mean(controls):.3f},{max(controls):.3f},"
              f"{sum(row['migration_errors'] for row in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
