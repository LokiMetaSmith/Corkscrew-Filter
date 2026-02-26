import unittest
import os
import sys
import tempfile
import trimesh
from unittest.mock import patch
import subprocess

# Ensure we can import from optimizer and its dependencies
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'optimizer')))
from optimizer.scad_driver import ScadDriver

class TestCFDGeneration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure we are in the repo root for export.js to work
        cls.original_cwd = os.getcwd()
        cls.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        os.chdir(cls.repo_root)
        cls.driver = ScadDriver("corkscrew.scad")

    @classmethod
    def tearDownClass(cls):
        # Restore original working directory
        os.chdir(cls.original_cwd)

    def verify_stl(self, stl_path):
        """Verifies that the STL file exists and is a valid, watertight mesh."""
        self.assertTrue(os.path.exists(stl_path), f"STL file not found: {stl_path}")

        # Load the mesh using trimesh
        mesh = trimesh.load(stl_path, file_type='stl')
        self.assertIsNotNone(mesh, "Failed to load mesh")

        # Handle Scene objects (if multiple bodies)
        if isinstance(mesh, trimesh.Scene):
            if len(mesh.geometry) == 0:
                self.fail("Loaded mesh is an empty scene")
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        self.assertGreater(mesh.volume, 0, "Mesh volume is not positive")
        # Note: InletCap/OutletCap are single sheets if thickness is small?
        # But CapGeometry has thickness=0.5. So it should be a volume.
        self.assertTrue(mesh.is_watertight, "Mesh is not watertight")

    def test_inlet_cap_generation(self):
        """Test generation of Inlet Cap STL."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "inlet.stl")
            params = {
                "part_to_generate": "inlet_cap",
                "GENERATE_CFD_VOLUME": True,
                "high_res_fn": 20 # Low res for speed
            }
            print("Generating Inlet Cap...")
            success = self.driver.generate_stl(params, output_path)
            self.assertTrue(success, "Inlet Cap generation failed")
            self.verify_stl(output_path)

    def test_outlet_cap_generation(self):
        """Test generation of Outlet Cap STL."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "outlet.stl")
            params = {
                "part_to_generate": "outlet_cap",
                "GENERATE_CFD_VOLUME": True,
                "high_res_fn": 20
            }
            print("Generating Outlet Cap...")
            success = self.driver.generate_stl(params, output_path)
            self.assertTrue(success, "Outlet Cap generation failed")
            self.verify_stl(output_path)

if __name__ == '__main__':
    unittest.main()
