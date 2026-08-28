#!/usr/bin/env python3
"""Validate phase 3 training-record schema and report label coverage."""
import argparse
import json
from pathlib import Path

REQUIRED = {"run_id", "workload", "ratio", "scenario", "repeat", "features",
            "label", "source_artifacts", "git_revision"}
FEATURES = {"total_pages", "avg_n0", "avg_n1", "max_delta", "high_delta_pages", "imbalance_ratio"}
LABELS = {"max_migrations", "access_diff_threshold", "migration_interval_ms", "latency_ns", "bandwidth_mb_s"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    errors = []
    for index, row in enumerate(rows, 1):
        missing = REQUIRED - row.keys()
        missing_features = FEATURES - row.get("features", {}).keys()
        missing_labels = LABELS - row.get("label", {}).keys()
        if missing or missing_features or missing_labels:
            errors.append({"line": index, "missing": sorted(missing),
                           "missing_features": sorted(missing_features),
                           "missing_labels": sorted(missing_labels)})
        if row.get("measurement_available"):
            label = row.get("label", {})
            if not isinstance(label.get("latency_ns"), (int, float)) or label.get("latency_ns", 0) <= 0:
                errors.append({"line": index, "invalid": "latency_ns"})
            if not isinstance(label.get("bandwidth_mb_s"), (int, float)) or label.get("bandwidth_mb_s", 0) <= 0:
                errors.append({"line": index, "invalid": "bandwidth_mb_s"})
    result = {"records": len(rows), "valid": not errors, "errors": errors,
              "training_ready_records": sum(r.get("measurement_available", False) for r in rows),
              "groups": sorted({(r.get("workload"), r.get("ratio"), r.get("scenario")) for r in rows})}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if rows and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
