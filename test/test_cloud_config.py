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

        # Verify patchPostProcessing1 block exists and parameters are INSIDE it
        # Extract block content
        pattern = re.compile(r"patchPostProcessing1\s*\{(.*?)\}", re.DOTALL)
        match = pattern.search(content)
        self.assertIsNotNone(match, "patchPostProcessing1 block not found")

        block_content = match.group(1)

        self.assertIn("type            patchPostProcessing;", block_content)
        self.assertIn("patches         ( corkscrew inlet outlet );", block_content)
        self.assertIn("maxStoredParcels 1000000;", block_content)

        # Check for newly added parameters (should fail initially)
        self.assertIn("resetOnWrite    false;", block_content)
        self.assertIn("log             true;", block_content)

if __name__ == '__main__':
    unittest.main()
