#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SummarizePageHeatTest(unittest.TestCase):
    def test_six_features_include_unobserved_pages(self):
        rows = [
            {"page": "0x1000", "accesses_by_node": {"0": 30, "1": 10}, "samples": 40},
            {"page": "0x2000", "accesses_by_node": {"0": 5, "1": 15}, "samples": 20},
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "heat.jsonl"
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
            result = subprocess.run(
                ["python3", str(ROOT / "analysis/summarize_page_heat.py"), str(source),
                 "--threshold", "10", "--workset-pages", "4"],
                check=True, capture_output=True, text=True,
            )
        features = json.loads(result.stdout)
        self.assertEqual(features["total_pages"], 4)
        self.assertEqual(features["sampled_pages"], 2)
        self.assertEqual(features["avg_n0"], 8.75)
        self.assertEqual(features["avg_n1"], 6.25)
        self.assertEqual(features["max_delta"], 20)
        self.assertEqual(features["high_delta_pages"], 2)
        self.assertAlmostEqual(features["imbalance_ratio"], 10 / 60)
        self.assertEqual(features["page_coverage"], 0.5)


if __name__ == "__main__":
    unittest.main()
