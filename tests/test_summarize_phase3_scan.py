#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SummarizePhase3ScanTest(unittest.TestCase):
    def test_repeated_means_drive_winner(self):
        rows = []
        for repeat, latency, bandwidth in ((1, 10.0, 100.0), (2, 12.0, 100.0),
                                           (1, 10.5, 200.0), (2, 10.5, 200.0)):
            limit = 1 if bandwidth == 100.0 else 2
            rows.append({"workload": "w", "ratio": "r", "scenario": "s", "repeat": repeat,
                         "measurement_available": True,
                         "label": {"access_diff_threshold": 2, "max_migrations": limit,
                                   "migration_interval_ms": 0, "latency_ns": latency,
                                   "bandwidth_mb_s": bandwidth}})
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); source = base / "data"; summary = base / "summary"; winner = base / "winner"
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
            subprocess.run(["python3", str(ROOT / "analysis/summarize_phase3_scan.py"), str(source),
                            "--latency-tolerance-ns", "1", "--output", str(summary),
                            "--winner-output", str(winner)], check=True)
            self.assertEqual(json.loads(winner.read_text())["max_migrations"], 2)
            self.assertEqual(len(summary.read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
