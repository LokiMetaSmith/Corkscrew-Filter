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

        # In current version of foam_driver.py, cloudFunctions are commented out due to a bug in OpenFOAM 2512.
        # We'll just verify the model and turbulence parameterization here.
        self.assertIn("dispersionModel none;", content)
        self.assertNotIn("k               cellPoint;", content)

        # Test turbulent mode
        self.driver._generate_kinematicCloudProperties(turbulence="kOmegaSST")
        with open(config_path, 'r') as f:
            content2 = f.read()

        self.assertIn("dispersionModel stochasticDispersionRAS;", content2)
        self.assertIn("k               cellPoint;", content2)

if __name__ == '__main__':
    unittest.main()
