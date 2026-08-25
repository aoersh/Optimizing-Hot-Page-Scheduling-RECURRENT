#!/usr/bin/env python3
"""Select page addresses whose PEBS count favors Node 0 or Node 1."""
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("heat", type=Path)
    parser.add_argument("--min-delta", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=256)
    parser.add_argument("--node0-output", type=Path, required=True)
    parser.add_argument("--node1-output", type=Path, required=True)
    args = parser.parse_args()
    candidates = {0: [], 1: []}
    for line in args.heat.read_text().splitlines():
        row = json.loads(line)
        n0 = int(row["accesses_by_node"].get("0", 0))
        n1 = int(row["accesses_by_node"].get("1", 0))
        delta = abs(n0 - n1)
        if delta < args.min_delta or n0 == n1:
            continue
        node = 0 if n0 > n1 else 1
        candidates[node].append((delta, int(row["page"], 16)))
    for node, output in ((0, args.node0_output), (1, args.node1_output)):
        pages = [address for _, address in sorted(candidates[node], reverse=True)[:args.max_pages]]
        output.write_text("".join(f"0x{page:x}\n" for page in pages))
    print(json.dumps({"node0": min(len(candidates[0]), args.max_pages),
                      "node1": min(len(candidates[1]), args.max_pages),
                      "min_delta": args.min_delta}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
