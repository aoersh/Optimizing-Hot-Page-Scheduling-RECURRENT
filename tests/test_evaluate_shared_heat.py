#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EvaluateSharedHeatTest(unittest.TestCase):
    def test_direction_and_missing_pages(self):
        rows = [
            {"page": "0x1000", "accesses_by_node": {"0": 4, "1": 1}, "samples": 5},
            {"page": "0x2000", "accesses_by_node": {"0": 2, "1": 2}, "samples": 4},
            {"page": "0x3000", "accesses_by_node": {"0": 3, "1": 1}, "samples": 4},
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "heat.jsonl"
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
            result = subprocess.run(
                ["python3", str(ROOT / "analysis/evaluate_shared_heat.py"), str(source),
                 "--start", "0x1000", "--pages", "4"],
                check=True, capture_output=True, text=True,
            )
        metrics = json.loads(result.stdout)
        self.assertEqual(metrics["correct_pages"], 1)
        self.assertEqual(metrics["wrong_pages"], 1)
        self.assertEqual(metrics["tie_pages"], 1)
        self.assertEqual(metrics["unobserved_pages"], 1)
        self.assertEqual(metrics["classified_accuracy"], 0.5)
        self.assertEqual(metrics["workset_correct_coverage"], 0.25)


if __name__ == "__main__":
    unittest.main()
