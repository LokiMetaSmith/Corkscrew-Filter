import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add optimizer to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'optimizer')))

from foam_driver import FoamDriver
from simulation_runner import run_simulation

class TestFeedbackPropagation(unittest.TestCase):
    def setUp(self):
        self.mock_scad = MagicMock()
        self.mock_physics = MagicMock(spec=FoamDriver)
        self.mock_physics.config = {'physics': {'type': 'cfd'}}
        self.mock_physics.case_dir = "/tmp/test_case"
        self.mock_physics.has_tools = True

    def test_meshing_failure_propagation(self):
        """Verifies that meshing failure details reach the simulation results."""
        self.mock_physics.run_meshing.return_value = False
        self.mock_physics.last_error_details = "checkMesh failed: High non-orthogonality: 85.2"

        import numpy as np
        params = {"test": 1, "target_cell_size": 100} # Use huge cell size to avoid computationally_intractable
        # Mock generate_cfd_assets to return dummy paths
        self.mock_scad.generate_cfd_assets.return_value = {
            "fluid": "corkscrew_fluid.stl", "inlet": "i.stl", "outlet": "o.stl", "wall": "w.stl"
        }
        self.mock_scad.get_bounds.return_value = (np.array([0,0,0]), np.array([1,1,1]))

        # Create dummy file to avoid FileNotFoundError in shutil.move
        tri_surface_dir = os.path.join(self.mock_physics.case_dir, "constant", "triSurface")
        os.makedirs(tri_surface_dir, exist_ok=True)
        with open(os.path.join(tri_surface_dir, "corkscrew_fluid.stl"), "w") as f:
            f.write("dummy")

        # Mock Validator
        with patch('simulation_runner.Validator') as mock_val:
            mock_val.return_value.validate_assembly.return_value = {"valid": True, "messages": []}

            metrics, _, _, _, _ = run_simulation(
                self.mock_scad, self.mock_physics, params, iteration=0
            )

            self.assertEqual(metrics["error"], "meshing_failed")
            self.assertEqual(metrics["details"], "checkMesh failed: High non-orthogonality: 85.2")

    def test_solver_failure_propagation(self):
        """Verifies that solver failure details reach the simulation results."""
        self.mock_physics.run_meshing.return_value = True
        self.mock_physics.run_solver.return_value = False
        self.mock_physics.last_error_details = "Fatal Error: Floating point exception; Peak Continuity Error: 1.5e+06"

        import numpy as np
        params = {"test": 1, "target_cell_size": 100} # Use huge cell size to avoid computationally_intractable
        self.mock_scad.generate_cfd_assets.return_value = {
            "fluid": "corkscrew_fluid.stl", "inlet": "i.stl", "outlet": "o.stl", "wall": "w.stl"
        }
        self.mock_scad.get_bounds.return_value = (np.array([0,0,0]), np.array([1,1,1]))
        self.mock_scad.get_internal_point.return_value = [0.5, 0.5, 0.5]

        # Create dummy file to avoid FileNotFoundError in shutil.move
        tri_surface_dir = os.path.join(self.mock_physics.case_dir, "constant", "triSurface")
        os.makedirs(tri_surface_dir, exist_ok=True)
        with open(os.path.join(tri_surface_dir, "corkscrew_fluid.stl"), "w") as f:
            f.write("dummy")

        with patch('simulation_runner.Validator') as mock_val, \
             patch('simulation_runner.get_container_memory_gb') as mock_mem:
            mock_val.return_value.validate_assembly.return_value = {"valid": True, "messages": []}
            mock_mem.return_value = 16.0

            metrics, _, _, _, _ = run_simulation(
                self.mock_scad, self.mock_physics, params, iteration=0
            )

            self.assertEqual(metrics["error"], "solver_failed")
            self.assertEqual(metrics["details"], "Fatal Error: Floating point exception; Peak Continuity Error: 1.5e+06")

if __name__ == "__main__":
    unittest.main()
