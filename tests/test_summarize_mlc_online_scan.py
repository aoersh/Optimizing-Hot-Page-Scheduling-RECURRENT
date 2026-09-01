#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SummarizeMlcOnlineScanTest(unittest.TestCase):
    def test_groups_configured_and_actual_migrations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for limit, latency in ((0, 10.0), (64, 9.0)):
                for repeat in (1, 2):
                    path = root / f"m{limit}-r{repeat}"; path.mkdir()
                    row = {"latency_ns": latency, "bandwidth_mb_s": 100.0,
                           "verified": limit, "migration_errors": 0, "repeat": repeat}
                    (path / "migration.json").write_text(json.dumps(row))
            output = root / "summary"
            subprocess.run(["python3", str(ROOT / "analysis/summarize_mlc_online_scan.py"),
                            str(root), "--output", str(output)], check=True)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual([row["configured_max_migrations"] for row in rows], [0, 64])
            self.assertEqual(rows[1]["actual_migrations"], [64, 64])
            self.assertEqual(rows[1]["migration_shortfalls"], 0)

    def test_stable_paired_winner_and_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for repeat in range(1, 6):
                for limit, latency, bandwidth in ((0, 10.0, 100.0), (512, 10.2, 102.0)):
                    path = root / f"t2-m{limit}-i0-r{repeat}"; path.mkdir()
                    row = {"latency_ns": latency, "bandwidth_mb_s": bandwidth,
                           "verified": limit, "migration_errors": 0, "repeat": repeat,
                           "access_diff_threshold": 2,
                           "configured_max_migrations": limit, "migration_interval_ms": 0}
                    (path / "migration.json").write_text(json.dumps(row))
            output, winner = root / "summary", root / "winner"
            subprocess.run(["python3", str(ROOT / "analysis/summarize_mlc_online_scan.py"),
                            str(root), "--output", str(output), "--winner-output", str(winner)],
                           check=True)
            decision = json.loads(winner.read_text())
            self.assertEqual(decision["decision"], "migrate")
            self.assertEqual(decision["winner"]["configured_max_migrations"], 512)


if __name__ == "__main__":
    unittest.main()
