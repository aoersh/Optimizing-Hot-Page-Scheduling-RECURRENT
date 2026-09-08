#!/usr/bin/env python3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase3ScanConfigTest(unittest.TestCase):
    def test_explicit_config_preserves_legacy_fallback(self):
        script = (ROOT / "scripts/run_phase3_mlc_online_scan.sh").read_text()
        self.assertIn('${SCAN_CONFIGS:-}', script)
        self.assertIn('${THRESHOLDS:-1 2 4}', script)
        self.assertIn('configs=("${CONTROL_THRESHOLD:-2}:0:0")', script)


if __name__ == "__main__":
    unittest.main()
