#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SelectPhase3LabelsTest(unittest.TestCase):
    def test_bandwidth_breaks_latency_tolerance_tie(self):
        def row(run, latency, bandwidth):
            return {"run_id": run, "workload": "w", "ratio": "r", "scenario": "s",
                    "repeat": 1, "measurement_available": True,
                    "label": {"latency_ns": latency, "bandwidth_mb_s": bandwidth}}
        rows = [row("fast", 10.0, 100.0), row("winner", 10.5, 200.0), row("slow", 12.0, 300.0)]
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "data", Path(directory) / "labels"
            source.write_text("".join(json.dumps(item) + "\n" for item in rows))
            subprocess.run(["python3", str(ROOT / "analysis/select_phase3_labels.py"), str(source),
                            "--latency-tolerance-ns", "1", "--output", str(output)], check=True)
            self.assertEqual(json.loads(output.read_text())["run_id"], "winner")


if __name__ == "__main__":
    unittest.main()
