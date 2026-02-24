import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import sys

# Add project root and optimizer directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../optimizer')))

from optimizer.foam_driver import FoamDriver

class TestFoamDriverCloud(unittest.TestCase):
    def setUp(self):
        # Mock instance methods to prevent real execution
        # We patch the class methods directly
        self.patcher1 = patch.object(FoamDriver, '_recover_from_crash')
        self.patcher2 = patch.object(FoamDriver, '_check_execution_environment')
        self.mock_recover = self.patcher1.start()
        self.mock_check = self.patcher2.start()

        # Initialize
        self.driver = FoamDriver("test_case", verbose=True)

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()

    def test_generate_kinematicCloudProperties_no_massFlowRate(self):
        # Mock file writing
        # We need to mock 'builtins.open' but only for the specific file?
        # Or globally for this test.

        m_open = mock_open()

        # We also need to patch os.makedirs and os.path.join to avoid filesystem errors
        # But verify_fix.py showed that generate_kinematicCloudProperties calls os.path.join

        with patch('builtins.open', m_open), \
             patch('os.makedirs'), \
             patch('os.path.exists', return_value=False):

            self.driver._generate_kinematicCloudProperties()

            # Get the content written to the file
            # m_open() returns a mock file object.
            # We want to check all writes to it.

            handle = m_open()
            # It's possible multiple write calls were made.
            # Or one big write.
            # In foam_driver.py: with open(...) as f: f.write(content)

            # Check if write was called
            if not handle.write.called:
                self.fail("File write not called")

            # Combine all written content
            content = "".join(call.args[0] for call in handle.write.call_args_list)

            # Assertions
            self.assertIn("parcelBasisType number;", content)
            self.assertIn("U0", content)

            # Critical Assertion: massFlowRate should NOT be active
            self.assertNotIn("\n            massFlowRate", content)
            self.assertNotIn(";            massFlowRate", content)

            # Check for the comment explaining removal
            self.assertIn("// massFlowRate removed", content)

    @patch('optimizer.foam_driver.run_command_with_spinner')
    @patch('optimizer.foam_driver.FoamDriver._print_log_tail')
    def test_run_command_logs_on_error(self, mock_print_log, mock_run):
        # Setup failure
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, ["cmd"])

        # Call run_command with verbose=False (default or explicit)
        self.driver.verbose = False
        result = self.driver.run_command(["cmd"], log_file="test.log")

        # Assert failure
        self.assertFalse(result)

        # Assert log tail printed despite verbose=False
        mock_print_log.assert_called_with("test.log")

if __name__ == '__main__':
    unittest.main()
