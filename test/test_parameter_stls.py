import unittest
import os
import sys
import glob
import trimesh
import tempfile
import shutil
import subprocess
from unittest.mock import patch

# Ensure we can import from optimizer and its dependencies
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'optimizer')))
from optimizer.scad_driver import ScadDriver

class TestParameterSTLs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure we are in the repo root for export.js to work
        # This assumes the test file is in <repo_root>/test/
        cls.original_cwd = os.getcwd()
        cls.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        os.chdir(cls.repo_root)

    @classmethod
    def tearDownClass(cls):
        # Restore original working directory
        os.chdir(cls.original_cwd)

    def verify_stl(self, stl_path):
        """Verifies that the STL file exists and is a valid, watertight mesh."""
        self.assertTrue(os.path.exists(stl_path), f"STL file not found: {stl_path}")

        # Load the mesh using trimesh
        # Force file type to avoid ambiguity if extension is weird, though it is .stl
        mesh = trimesh.load(stl_path, file_type='stl')
        self.assertIsNotNone(mesh, "Failed to load mesh")

        # Handle Scene objects (if multiple bodies)
        if isinstance(mesh, trimesh.Scene):
            if len(mesh.geometry) == 0:
                self.fail("Loaded mesh is an empty scene")
            # Concatenate all geometries in the scene into a single mesh for validation
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        self.assertTrue(mesh.is_watertight, "Mesh is not watertight")
        self.assertGreater(mesh.volume, 0, "Mesh volume is not positive")

def create_test_method(param_file):
    def test_method(self):
        file_name = os.path.basename(param_file)
        print(f"Testing parameter file: {file_name}", flush=True)
        driver = ScadDriver("corkscrew.scad")

        # Patch subprocess.run to include a timeout
        original_run = subprocess.run
        def run_with_timeout(*args, **kwargs):
            # Set timeout to 600 seconds (10 minutes) to accommodate slow WASM processing
            kwargs.setdefault('timeout', 600)
            return original_run(*args, **kwargs)

        with patch('optimizer.scad_driver.subprocess.run', side_effect=run_with_timeout):
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Test Solid Generation
                    solid_stl = os.path.join(temp_dir, f"{file_name}_solid.stl")
                    print(f"  Generating Solid STL: {solid_stl}", flush=True)
                    # Reduce resolution to 10 to speed up tests
                    success = driver.generate_stl(
                        params={"GENERATE_CFD_VOLUME": False, "high_res_fn": 10},
                        output_path=solid_stl,
                        params_file=param_file
                    )
                    self.assertTrue(success, f"Solid STL generation failed for {file_name}")
                    self.verify_stl(solid_stl)

                    # Test Fluid Generation (CFD Volume)
                    fluid_stl = os.path.join(temp_dir, f"{file_name}_fluid.stl")
                    print(f"  Generating Fluid STL: {fluid_stl}", flush=True)
                    success = driver.generate_stl(
                        params={"GENERATE_CFD_VOLUME": True, "high_res_fn": 10},
                        output_path=fluid_stl,
                        params_file=param_file
                    )
                    self.assertTrue(success, f"Fluid STL generation failed for {file_name}")
                    self.verify_stl(fluid_stl)

                except subprocess.TimeoutExpired:
                    self.fail(f"STL generation timed out (300s limit) for {file_name}. The model might be too complex or invalid.")
    return test_method

# Dynamically add test methods for each parameter file found
# Determine repo root relative to this file
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.abspath(os.path.join(current_dir, '..'))
parameters_dir = os.path.join(repo_root, "parameters")

if os.path.exists(parameters_dir):
    param_files = glob.glob(os.path.join(parameters_dir, "*.scad"))
    for p in param_files:
        # Create a valid method name
        test_name = f"test_{os.path.basename(p).replace('.', '_').replace('-', '_')}"
        setattr(TestParameterSTLs, test_name, create_test_method(p))
else:
    print(f"Warning: Parameters directory not found at {parameters_dir}")

if __name__ == '__main__':
    unittest.main()
