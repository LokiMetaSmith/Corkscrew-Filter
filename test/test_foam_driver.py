import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../optimizer')))

from optimizer.foam_driver import FoamDriver

class TestFoamDriver(unittest.TestCase):
    def setUp(self):
        self.driver = FoamDriver("test_case", container_engine="auto", verbose=True)
        # Mock actual file system operations that might happen in init
        self.driver._recover_from_crash = MagicMock()
        self.driver._check_execution_environment = MagicMock()

    @patch('optimizer.foam_driver.shutil.move')
    @patch('optimizer.foam_driver.os.remove')
    @patch('optimizer.foam_driver.os.path.exists')
    def test_scale_mesh_uses_temp_file(self, mock_exists, mock_remove, mock_move):
        # Setup mocks
        self.driver.run_command = MagicMock(return_value=True)
        mock_exists.return_value = True # Pretend destination exists to test removal

        # Call method
        result = self.driver.scale_mesh("test.stl", 0.001, log_file="meshing.log")

        # Assertions
        self.assertTrue(result)

        # Check run_command arguments
        args, kwargs = self.driver.run_command.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "surfaceMeshConvert")
        self.assertIn("constant/triSurface/test.stl", cmd[1]) # Input
        self.assertIn("constant/triSurface/temp_test.stl", cmd[2]) # Output (temp)
        self.assertEqual(kwargs['log_file'], "meshing.log")

        # Check file operations
        # Should verify destination removal
        mock_remove.assert_called()
        # Should verify move
        mock_move.assert_called()
        move_args = mock_move.call_args[0]
        self.assertTrue(move_args[0].endswith("temp_test.stl"))
        self.assertTrue(move_args[1].endswith("test.stl"))

    @patch('optimizer.foam_driver.shutil.move')
    def test_scale_mesh_failure(self, mock_move):
        # Setup mocks
        self.driver.run_command = MagicMock(return_value=False)

        # Call method
        result = self.driver.scale_mesh("test.stl", 0.001)

        # Assertions
        self.assertFalse(result)
        # Should NOT move if command failed
        mock_move.assert_not_called()

if __name__ == '__main__':
    unittest.main()
