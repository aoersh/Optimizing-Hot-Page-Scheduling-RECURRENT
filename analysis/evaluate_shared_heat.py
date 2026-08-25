#!/usr/bin/env python3
"""Evaluate PEBS recovery against shared_heat_bench's known two-half bias."""
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("heat", type=Path)
    parser.add_argument("--start", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--pages", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.pages <= 0 or args.pages % 2:
        parser.error("pages must be a positive even number")

    halves = [{"node0": 0, "node1": 0, "correct": 0, "wrong": 0, "ties": 0}
              for _ in range(2)]
    seen = set()
    for line in args.heat.read_text().splitlines():
        row = json.loads(line)
        index = (int(row["page"], 16) - args.start) // 4096
        if not 0 <= index < args.pages:
            parser.error(f"page outside declared workset: {row['page']}")
        seen.add(index)
        half = 0 if index < args.pages // 2 else 1
        node0 = int(row["accesses_by_node"].get("0", 0))
        node1 = int(row["accesses_by_node"].get("1", 0))
        halves[half]["node0"] += node0
        halves[half]["node1"] += node1
        if node0 == node1:
            halves[half]["ties"] += 1
        elif (half == 0 and node0 > node1) or (half == 1 and node1 > node0):
            halves[half]["correct"] += 1
        else:
            halves[half]["wrong"] += 1

    correct = sum(item["correct"] for item in halves)
    wrong = sum(item["wrong"] for item in halves)
    ties = sum(item["ties"] for item in halves)
    classified = correct + wrong
    result = {
        "pages": args.pages,
        "observed_pages": len(seen),
        "unobserved_pages": args.pages - len(seen),
        "correct_pages": correct,
        "wrong_pages": wrong,
        "tie_pages": ties,
        "classified_accuracy": correct / classified if classified else 0.0,
        "workset_correct_coverage": correct / args.pages,
        "first_half": halves[0],
        "second_half": halves[1],
    }
    result["first_half"]["preferred_ratio"] = (
        halves[0]["node0"] / halves[0]["node1"] if halves[0]["node1"] else None)
    result["second_half"]["preferred_ratio"] = (
        halves[1]["node1"] / halves[1]["node0"] if halves[1]["node0"] else None)
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
