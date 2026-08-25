#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SelectHeatPagesTest(unittest.TestCase):
    def test_threshold_direction_and_limit(self):
        rows = [
            {"page": "0x1000", "accesses_by_node": {"0": 5, "1": 1}, "samples": 6},
            {"page": "0x2000", "accesses_by_node": {"0": 4, "1": 1}, "samples": 5},
            {"page": "0x3000", "accesses_by_node": {"0": 1, "1": 6}, "samples": 7},
            {"page": "0x4000", "accesses_by_node": {"0": 2, "1": 1}, "samples": 3},
        ]
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, node0, node1 = base / "heat.jsonl", base / "n0", base / "n1"
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
            subprocess.run(
                ["python3", str(ROOT / "analysis/select_heat_pages.py"), str(source),
                 "--min-delta", "2", "--max-pages", "1",
                 "--node0-output", str(node0), "--node1-output", str(node1)], check=True)
            self.assertEqual(node0.read_text(), "0x1000\n")
            self.assertEqual(node1.read_text(), "0x3000\n")


if __name__ == "__main__":
    unittest.main()
