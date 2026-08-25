#!/usr/bin/env python3
"""Convert page-level PEBS JSONL records into the paper's six features."""
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--threshold", type=int, default=20)
    parser.add_argument("--workset-pages", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.threshold < 0:
        parser.error("threshold must be non-negative")

    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    if not rows:
        parser.error("input contains no page records")
    if args.workset_pages is not None and args.workset_pages < len(rows):
        parser.error("workset-pages cannot be smaller than sampled pages")
    total_pages = args.workset_pages or len(rows)
    nodes = sorted({int(node) for row in rows for node in row["accesses_by_node"]})
    totals = {node: sum(int(row["accesses_by_node"].get(str(node), 0)) for row in rows)
              for node in nodes}
    n0 = [int(row["accesses_by_node"].get("0", 0)) for row in rows]
    n1 = [int(row["accesses_by_node"].get("1", 0)) for row in rows]
    deltas = [abs(a - b) for a, b in zip(n0, n1)]
    sum0, sum1 = sum(n0), sum(n1)
    denominator = sum0 + sum1
    features = {
        "total_pages": total_pages,
        "avg_n0": sum0 / total_pages,
        "avg_n1": sum1 / total_pages,
        "max_delta": max(deltas),
        "high_delta_pages": sum(delta >= args.threshold for delta in deltas),
        "imbalance_ratio": abs(sum0 - sum1) / denominator if denominator else 0.0,
        "threshold": args.threshold,
        "sampled_pages": len(rows),
        "sampled_accesses": sum(int(row["samples"]) for row in rows),
        "accesses_by_node": totals,
        "observed_nodes": nodes,
    }
    if args.workset_pages is not None:
        features["workset_pages"] = args.workset_pages
        features["page_coverage"] = len(rows) / args.workset_pages
    output = json.dumps(features, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
