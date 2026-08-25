#!/usr/bin/env python3
"""Aggregate perf mem samples into per-page NUMA-aware heat records."""
import argparse
import json
import re
import subprocess
from pathlib import Path
from collections import Counter, defaultdict

SAMPLE = re.compile(
    r"^\s*(?P<pid>\d+)/(?:\d+)\s+\[(?P<cpu>\d+)\].*?:\s+"
    r"(?:\d+\s+)?(?P<addr>[0-9a-f]+)\s+(?:\d+\s+)?(?P<ip>[0-9a-f]+)\s"
)
MMAP = re.compile(
    r"PERF_RECORD_MMAP2\s+(?P<pid>\d+)/(?:\d+):\s+"
    r"\[0x(?P<start>[0-9a-f]+)\(0x(?P<size>[0-9a-f]+)\).*\]:\s+"
    r"(?P<perms>....)\s+(?P<name>.*)$"
)


def expand_cpulist(value: str):
    for item in value.strip().split(","):
        if not item:
            continue
        bounds = item.split("-", 1)
        start = int(bounds[0])
        end = int(bounds[-1])
        yield from range(start, end + 1)


def cpu_nodes() -> dict[int, int]:
    mapping = {}
    for path in Path("/sys/devices/system/node").glob("node[0-9]*/cpulist"):
        node = int(path.parent.name.removeprefix("node"))
        for cpu in expand_cpulist(path.read_text(encoding="ascii")):
            mapping[cpu] = node
    return mapping


def largest_anonymous_mapping(data: str, pid: int):
    result = subprocess.run(
        ["perf", "script", "-i", data, "--show-mmap-events"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True,
    )
    candidates = []
    for line in result.stdout.splitlines():
        match = MMAP.search(line)
        if not match or int(match.group("pid")) != pid:
            continue
        start = int(match.group("start"), 16)
        size = int(match.group("size"), 16)
        if match.group("name") == "//anon" and start < 0x800000000000:
            candidates.append((size, start, start + size))
    if not candidates:
        raise RuntimeError(f"no anonymous mmap records found for PID {pid}")
    _, start, end = max(candidates)
    return start, end


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("data")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--maps")
    parser.add_argument("--range", nargs=2, type=lambda value: int(value, 0), metavar=("START", "END"))
    parser.add_argument("--jsonl", required=True)
    args = parser.parse_args()
    nodes_by_cpu = cpu_nodes()
    if not nodes_by_cpu:
        parser.error("could not read CPU NUMA topology from sysfs")

    allowed = None
    if args.maps:
        allowed = []
        for line in open(args.maps, encoding="utf-8"):
            match = re.match(r"^([0-9a-f]+)-([0-9a-f]+)", line)
            if match:
                allowed.append((int(match.group(1), 16), int(match.group(2), 16)))
    elif args.range:
        if args.range[0] >= args.range[1]:
            parser.error("range START must be smaller than END")
        allowed = [tuple(args.range)]
    else:
        allowed = [largest_anonymous_mapping(args.data, args.pid)]

    samples = defaultdict(lambda: Counter())
    total = 0
    script = subprocess.Popen(
        ["perf", "script", "-i", args.data, "-F", "pid,tid,cpu,time,event,addr,ip"],
        stdout=subprocess.PIPE, text=True,
    )
    assert script.stdout is not None
    for line in script.stdout:
        match = SAMPLE.match(line)
        if not match or int(match.group("pid")) != args.pid:
            continue
        address = int(match.group("addr"), 16)
        # Discard kernel/unknown samples before applying the selected mapping.
        if address >= 0x800000000000:
            continue
        if allowed and not any(start <= address < end for start, end in allowed):
            continue
        cpu = int(match.group("cpu"))
        if cpu not in nodes_by_cpu:
            parser.error(f"CPU {cpu} is absent from NUMA node cpulists")
        page = address & ~0xFFF
        samples[page][nodes_by_cpu[cpu]] += 1
        total += 1
    if script.wait() != 0:
        return 1

    with open(args.jsonl, "w", encoding="utf-8") as output:
        for page, counts in sorted(samples.items()):
            row = {
                "page": f"0x{page:x}",
                "accesses_by_node": dict(counts),
                "samples": sum(counts.values()),
            }
            output.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps({"pid": args.pid, "samples": total, "pages": len(samples),
                      "mapping": [f"0x{allowed[0][0]:x}", f"0x{allowed[0][1]:x}"],
                      "output": args.jsonl}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
