import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add optimizer to path
sys.path.append(os.path.abspath("optimizer"))

# Import simulation_runner to test it
from simulation_runner import run_simulation

class TestSimulationIntegration(unittest.TestCase):
    def test_integration(self):
        # Create mocks
        mock_scad = MagicMock()
        mock_foam = MagicMock()

        # Setup return values
        mock_scad.generate_stl.return_value = True
        mock_scad.get_bounds.return_value = ([-10, -10, -10], [10, 10, 10])
        # Simulate finding a point
        internal_point = [1.0, 2.0, 3.0]
        mock_scad.get_internal_point.return_value = internal_point

        # Setup foam driver
        mock_foam.has_tools = True
        mock_foam.run_meshing.return_value = True
        mock_foam.run_solver.return_value = True
        mock_foam.get_metrics.return_value = {}

        params = {"some": "param"}

        # Run
        # We need to patch Timer inside simulation_runner if it's used as context manager
        with patch('simulation_runner.Timer') as mock_timer:
             metrics, pngs = run_simulation(mock_scad, mock_foam, params, dry_run=False, skip_cfd=False)

        # Verify calls
        mock_scad.generate_stl.assert_called()
        mock_scad.get_internal_point.assert_called()

        # Verify update_snappyHexMesh_location was called with the point
        mock_foam.update_snappyHexMesh_location.assert_called_with(internal_point)

        print("Integration test passed: update_snappyHexMesh_location called with internal point.")

    def test_integration_fallback(self):
        # Test fallback when point not found
        mock_scad = MagicMock()
        mock_foam = MagicMock()

        mock_scad.generate_stl.return_value = True
        bounds = ([-10, -10, -10], [10, 10, 10])
        mock_scad.get_bounds.return_value = bounds
        mock_scad.get_internal_point.return_value = None # Fail to find point

        mock_foam.has_tools = True
        mock_foam.run_meshing.return_value = True
        mock_foam.run_solver.return_value = True
        mock_foam.get_metrics.return_value = {}

        params = {"some": "param"}

        with patch('simulation_runner.Timer') as mock_timer:
             metrics, pngs = run_simulation(mock_scad, mock_foam, params, dry_run=False, skip_cfd=False)

        mock_scad.get_internal_point.assert_called()

        # Verify update_snappyHexMesh_location was called with bounds
        mock_foam.update_snappyHexMesh_location.assert_called_with(bounds)

        print("Integration fallback test passed: update_snappyHexMesh_location called with bounds.")

if __name__ == "__main__":
    t = TestSimulationIntegration()
    t.test_integration()
    t.test_integration_fallback()
