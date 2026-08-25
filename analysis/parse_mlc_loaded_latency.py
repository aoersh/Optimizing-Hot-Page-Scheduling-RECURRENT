#!/usr/bin/env python3
"""Parse an Intel MLC loaded-latency curve into JSONL."""
import argparse
import json
import re
from pathlib import Path


ROW = re.compile(r"^\s*(\d+)\s+([0-9.]+)\s+([0-9.]+)\s*$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--ratio", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--repeat", required=True, type=int)
    args = parser.parse_args()
    rows = []
    for line in args.input.read_text(errors="replace").splitlines():
        match = ROW.match(line)
        if match:
            rows.append({"delay": int(match.group(1)), "latency_ns": float(match.group(2)),
                         "bandwidth_mb_s": float(match.group(3))})
    if not rows:
        parser.error("no loaded-latency rows found")
    peak = max(rows, key=lambda row: row["bandwidth_mb_s"])
    summary = {
        "record": "summary", "workload": args.workload, "ratio": args.ratio,
        "scenario": args.scenario, "repeat": args.repeat, "points": len(rows),
        "peak_bandwidth_mb_s": peak["bandwidth_mb_s"],
        "latency_at_peak_ns": peak["latency_ns"],
        "lowest_load_latency_ns": rows[-1]["latency_ns"],
    }
    with args.output.open("w") as output:
        output.write(json.dumps(summary, sort_keys=True) + "\n")
        for row in rows:
            output.write(json.dumps({**summary, "record": "point", **row}, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
