#!/usr/bin/env python3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase3SocketParametersTest(unittest.TestCase):
    def test_online_pilot_parameterizes_socket_topology(self):
        script = (ROOT / "scripts/run_phase3_mlc_online_pilot.sh").read_text()
        for variable in ("MLC_THREAD_RANGE", "CPU_BIND", "CPU_NODE", "DRAM_NODE",
                         "CXL_NODE", "HOT_ACCESS_NODE"):
            self.assertIn(variable, script)
        self.assertIn('node${hot_access_node}.pages', script)
        self.assertIn('"$dram_node" "$pages" "$cxl_node"', script)


if __name__ == "__main__":
    unittest.main()
