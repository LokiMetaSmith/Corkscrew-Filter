import unittest
import os
import sys
import shutil
import tempfile
import numpy as np

# Ensure we can import from optimizer and its dependencies
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'optimizer')))

from optimizer.foam_driver import FoamDriver

class TestFoamMetrics(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.driver = FoamDriver(self.test_dir)
        # Create dummy log file
        with open(self.driver.log_file, 'w') as f:
            f.write("Dummy Log\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_parse_particle_collector(self):
        # Setup directory structure for patchPostProcessing
        # Path: case/postProcessing/kinematicCloud/patchPostProcessing1/*/patchPostProcessing1.dat
        pp_dir = os.path.join(self.test_dir, "postProcessing", "kinematicCloud", "patchPostProcessing1", "0")
        os.makedirs(pp_dir)

        dat_file = os.path.join(pp_dir, "patchPostProcessing1.dat")

        # Write dummy data
        # Header: # Time bin_1 bin_2 inlet outlet
        # Data: 10.0 50 30 10 500
        with open(dat_file, 'w') as f:
            f.write("# Time\tbin_1\tbin_2\tinlet\toutlet\n")
            f.write("1.0\t10\t5\t2\t100\n")
            f.write("10.0\t50\t30\t10\t500\n")

        # Mock log file for total injection
        # "Injector model_10um: injected 1000 parcels"
        with open(self.driver.log_file, 'w') as f:
            f.write("Starting simulation...\n")
            f.write("Injector model_10um: injected 1000 parcels\n")
            f.write("Injector model_20um: injected 1000 parcels\n")
            f.write("End\n")

        metrics = self.driver.get_metrics()

        print("Metrics:", metrics)

        self.assertIn("capture_by_bin", metrics)
        self.assertEqual(metrics["capture_by_bin"]["bin_1"], 50)
        self.assertEqual(metrics["capture_by_bin"]["bin_2"], 30)
        self.assertEqual(metrics["particles_injected"], 2000)

        # Check if efficiencies are calculated
        self.assertIn("efficiency_by_bin", metrics)
        # 50 / 2000 = 2.5%
        self.assertAlmostEqual(metrics["efficiency_by_bin"]["bin_1"], 2.5)
        # 30 / 2000 = 1.5%
        self.assertAlmostEqual(metrics["efficiency_by_bin"]["bin_2"], 1.5)

if __name__ == '__main__':
    unittest.main()
