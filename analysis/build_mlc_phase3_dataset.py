#!/usr/bin/env python3
"""Build traceable training records for a selected MLC scan winner."""
import argparse
import json
import subprocess
from pathlib import Path


FEATURE_KEYS = ("total_pages", "avg_n0", "avg_n1", "max_delta",
                "high_delta_pages", "imbalance_ratio")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scan_root", type=Path)
    parser.add_argument("decision", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--ratio", required=True)
    parser.add_argument("--scenario", required=True)
    args = parser.parse_args()
    decision = json.loads(args.decision.read_text())
    winner = decision.get("winner")
    if decision.get("decision") != "migrate" or not winner:
        parser.error("decision does not contain a migration winner")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    stem = (f"t{winner['access_diff_threshold']}-m{winner['configured_max_migrations']}"
            f"-i{winner['migration_interval_ms']}-r*")
    records = []
    for run_dir in sorted(args.scan_root.glob(stem)):
        if not run_dir.is_dir():
            continue
        features_path = run_dir / "features.json"
        migration_path = run_dir / "migration.json"
        features = json.loads(features_path.read_text())
        migration = json.loads(migration_path.read_text())
        repeat = int(migration["repeat"])
        if migration["verified"] != winner["configured_max_migrations"]:
            continue
        records.append({
            "run_id": run_dir.name,
            "workload": args.workload,
            "ratio": args.ratio,
            "scenario": args.scenario,
            "repeat": repeat,
            "git_revision": revision,
            "features": {key: features[key] for key in FEATURE_KEYS},
            "label": {
                "max_migrations": winner["configured_max_migrations"],
                "access_diff_threshold": winner["access_diff_threshold"],
                "migration_interval_ms": winner["migration_interval_ms"],
                "latency_ns": migration["latency_ns"],
                "bandwidth_mb_s": migration["bandwidth_mb_s"],
            },
            "measurement_available": True,
            "selection_criteria": decision["criteria"],
            "source_artifacts": [str(run_dir / name) for name in
                                 ("pebs.data", "page-heat.jsonl", "features.json",
                                  "migration.json", "mlc-curve.jsonl")],
        })
    if not records:
        parser.error("no complete winner runs found")
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records))
    print(json.dumps({"records": len(records), "winner": stem}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
