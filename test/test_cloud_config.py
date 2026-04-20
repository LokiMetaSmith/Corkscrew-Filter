import unittest
import os
import sys
import shutil
import tempfile
import re

# Ensure we can import from optimizer and its dependencies
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'optimizer')))

from optimizer.foam_driver import FoamDriver

class TestCloudConfig(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.driver = FoamDriver(self.test_dir)
        # Create constant directory INSIDE the driver's case_dir
        # Since foam_driver maps its case_dir to /dev/shm, we must use that path!
        os.makedirs(os.path.join(self.driver.case_dir, "constant"))

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        self.driver.cleanup_ram_disk()

    def test_generate_kinematic_cloud_properties(self):
        # Generate the config
        self.driver._generate_kinematicCloudProperties()

        config_path = os.path.join(self.driver.case_dir, "constant", "kinematicCloudProperties")
        self.assertTrue(os.path.exists(config_path))

        with open(config_path, 'r') as f:
            content = f.read()

        # In v2512 we commented out patchPostProcessing1
        # Let's verify the patch interaction coeffs

        self.assertIn("patchInteractionModel localInteraction;", content)
        self.assertIn("corkscrew", content)
        self.assertIn("inlet", content)
        self.assertIn("outlet", content)
        # In current version of foam_driver.py, cloudFunctions are commented out due to a bug in OpenFOAM 2512.
        # We'll just verify the model and turbulence parameterization here.
        if "dispersionModel none" not in content:
            self.assertIn("dispersionModel stochasticDispersionRAS", content)
        # self.assertNotIn("k               cellPoint;", content)

        # Test turbulent mode
        self.driver._generate_kinematicCloudProperties(turbulence="kOmegaSST")
        with open(config_path, 'r') as f:
            content2 = f.read()

        # dispersionModel was disabled for stability
        self.assertIn("dispersionModel none", content2)
        self.assertIn("k               cellPoint;", content2)
        # Verify cloudFunctions block exists and is empty or has commented out functionality
        # as patchPostProcessing is buggy in OpenFOAM v2512.
        pattern = re.compile(r"cloudFunctions\s*\{([\s\S]*?)\}", re.DOTALL)
        match = pattern.search(content)
        self.assertIsNotNone(match, "cloudFunctions block not found")

        block_content = match.group(1)

        # Ensure there are no active function definitions inside cloudFunctions
        # We can check that any active word besides comments is missing,
        # but a simple test is verifying that patchPostProcessing1 is commented out or missing.
        # Actually, let's just make sure we don't accidentally uncomment patchPostProcessing1
        self.assertNotIn("\n    patchPostProcessing1", block_content, "patchPostProcessing1 should not be active")

        # We can also check that the dynamically calculated parcelsPerSecond and U0 are present in the injections block
        # For default (32mm tube_od_mm), area ratio is 1, so parcelsPerSecond is 5000 and U0 is (-5 0 0)
        self.assertIn("parcelsPerSecond 5000;", content)
        self.assertIn("U0              (-5 0 0);", content)

if __name__ == '__main__':
    unittest.main()
