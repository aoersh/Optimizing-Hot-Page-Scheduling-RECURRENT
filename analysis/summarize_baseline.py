#!/usr/bin/env python3
import json
import statistics
import sys
from collections import defaultdict


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} RESULTS.jsonl", file=sys.stderr)
        return 2

    values = defaultdict(list)
    with open(sys.argv[1], encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            operation = row.get("operation")
            if operation in {"sequential_read", "sequential_write"}:
                values[(row["scenario"], operation, "MiB/s")].append(row["bandwidth_mib_s"])
            elif operation == "random_read":
                values[(row["scenario"], operation, "ns")].append(row["latency_ns"])

    print("scenario,operation,unit,n,mean,stdev")
    for (scenario, operation, unit), samples in sorted(values.items()):
        stdev = statistics.stdev(samples) if len(samples) > 1 else 0.0
        print(f"{scenario},{operation},{unit},{len(samples)},"
              f"{statistics.mean(samples):.3f},{stdev:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

