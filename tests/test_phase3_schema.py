#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase3SchemaTest(unittest.TestCase):
    def test_pilot_without_measurement_is_not_training_ready(self):
        row = {
            "run_id": "pilot", "workload": "x", "ratio": "x", "scenario": "x", "repeat": 1,
            "git_revision": "abc", "features": {"total_pages": 1, "avg_n0": 0, "avg_n1": 0,
            "max_delta": 0, "high_delta_pages": 0, "imbalance_ratio": 0},
            "label": {"max_migrations": 1, "access_diff_threshold": 1,
            "migration_interval_ms": 0, "latency_ns": None, "bandwidth_mb_s": None},
            "source_artifacts": ["x"], "measurement_available": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dataset.jsonl"
            source.write_text(json.dumps(row) + "\n")
            result = subprocess.run(["python3", str(ROOT / "analysis/validate_phase3_dataset.py"), str(source)],
                                    check=True, capture_output=True, text=True)
        report = json.loads(result.stdout)
        self.assertEqual(report["records"], 1)
        self.assertEqual(report["training_ready_records"], 0)


if __name__ == "__main__":
    unittest.main()
