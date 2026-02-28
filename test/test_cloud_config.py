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
        # Create constant directory
        os.makedirs(os.path.join(self.test_dir, "constant"))

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_generate_kinematic_cloud_properties(self):
        # Generate the config
        self.driver._generate_kinematicCloudProperties()

        config_path = os.path.join(self.test_dir, "constant", "kinematicCloudProperties")
        self.assertTrue(os.path.exists(config_path))

        with open(config_path, 'r') as f:
            content = f.read()

        # In v2512 we commented out patchPostProcessing1
        # Let's verify the patch interaction coeffs

        self.assertIn("patchInteractionModel localInteraction;", content)
        self.assertIn("corkscrew", content)
        self.assertIn("inlet", content)
        self.assertIn("outlet", content)

if __name__ == '__main__':
    unittest.main()
