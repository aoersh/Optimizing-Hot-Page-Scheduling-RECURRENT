#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BuildMlcPhase3DatasetTest(unittest.TestCase):
    def test_ignores_matching_log_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "t1-m768-i0-r1"
            run.mkdir()
            (root / "t1-m768-i0-r1.log").write_text("log")
            features = {"total_pages": 1, "avg_n0": 1, "avg_n1": 0,
                        "max_delta": 1, "high_delta_pages": 1, "imbalance_ratio": 1}
            (run / "features.json").write_text(json.dumps(features))
            migration = {"repeat": 1, "verified": 768, "latency_ns": 10,
                         "bandwidth_mb_s": 100}
            (run / "migration.json").write_text(json.dumps(migration))
            decision = root / "winner.json"
            decision.write_text(json.dumps({
                "decision": "migrate", "criteria": {},
                "winner": {"access_diff_threshold": 1,
                           "configured_max_migrations": 768,
                           "migration_interval_ms": 0}}))
            output = root / "dataset.jsonl"
            subprocess.run([
                "python3", str(ROOT / "analysis/build_mlc_phase3_dataset.py"),
                str(root), str(decision), "--output", str(output),
                "--workload", "W21", "--ratio", "75:25", "--scenario", "s"], check=True)
            self.assertEqual(len(output.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
