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

    def test_generate_kinematicCloudProperties_mass_basis(self):
        # Mock file writing
        # We need to mock 'builtins.open' but only for the specific file?
        # Or globally for this test.

        m_open = mock_open()

        # We also need to patch os.makedirs and os.path.join to avoid filesystem errors
        # But verify_fix.py showed that generate_kinematicCloudProperties calls os.path.join

        # We also need to patch shutil because backup/restore logic might trigger?
        # No, generate_kinematicCloudProperties writes directly.

        with patch('builtins.open', m_open), \
             patch('os.makedirs'), \
             patch('os.path.exists', return_value=False):

            self.driver._generate_kinematicCloudProperties()

            # Get the content written to the file
            # m_open() returns a mock file object.
            # We want to check all writes to it.
            # Note: mock_open creates a new mock on every call() unless reused.
            # But the 'm_open' object itself acts as the opener.
            # The context manager returns the file handle.

            # Retrieve the file handle that was returned by open() context manager
            # The structure of mock_open return value is tricky if multiple opens happen.
            # But here only one file is opened inside the method.

            handle = m_open()

            # Check if write was called
            if not handle.write.called:
                # Try getting calls from m_open directly if handle fails
                # But handle usually works.
                # Debugging: check calls on m_open
                pass

            # Combine all written content
            # Usually handle.write calls contain the content
            content = ""
            for call in handle.write.call_args_list:
                args, _ = call
                if args:
                   content += args[0]

            if not content:
                 # If write wasn't called on the handle, fail
                 self.fail("File write not called or empty content.")

            # Assertions for Mass Basis Fix
            self.assertIn("parcelBasisType mass;", content)
            self.assertIn("massTotal", content)
            self.assertIn("rho0", content)

            # Verify massTotal is calculated and formatted (e.g. scientific notation)
            # We check for a number.
            import re
            self.assertTrue(re.search(r"massTotal\s+[\d\.e\-\+]+;", content), "massTotal value not found")

            # Verify problematic entries are removed (ensure they are not active keys)
            # Use regex to avoid matching comments (e.g. "// nParticle removed")
            self.assertFalse(re.search(r"^\s*nParticle\s+", content, re.MULTILINE), "nParticle parameter found active")

            # Verify SIGFPE Fix: Ensure sourceTerms is removed
            self.assertNotIn("sourceTerms", content)

            # Verify Robust Patch Interactions
            self.assertIn('"(.*)"', content)
            self.assertIn("type rebound;", content)
            self.assertIn("e    0.97;", content)
            self.assertIn("mu   0.09;", content)

            # Verify Order: Catch-all should be before specific patches to allow override (if parser is first-match)
            # OR if parser is last-match, this order puts specific last.
            # Wait, foam_driver logic was updated to put catch-all FIRST.
            # patches ( "(.*)" { ... } corkscrew { ... } )

            # Find indices
            idx_catch_all = content.find('"(.*)"')
            idx_corkscrew = content.find('corkscrew', idx_catch_all + 1) # Search after catch-all? No, global search

            # Re-search correctly
            idx_catch_all = content.find('"(.*)"')
            # 'corkscrew' appears in patch list str earlier in function, but we want the one in "patches ( ... )"
            # It's safer to check relative order in the content string.
            # The 'corkscrew' inside localInteractionCoeffs comes after "(.*)"

            # Locate localInteractionCoeffs block
            loc_coeffs_start = content.find("localInteractionCoeffs")
            coeffs_content = content[loc_coeffs_start:]

            idx_catch_all_rel = coeffs_content.find('"(.*)"')
            idx_corkscrew_rel = coeffs_content.find('corkscrew', idx_catch_all_rel + 1) # Should be after if catch-all is first

            # Actually, we want specific to override.
            # If OpenFOAM matches strictly, order might not matter for disjoint sets.
            # But for regex vs explicit:
            # If "(.*)" is first, does it get processed? Yes.
            # Then "corkscrew" (which matches .*) is processed. Does it overwrite?
            # Standard practice: Put defaults first, specifics last.

            self.assertNotEqual(idx_catch_all_rel, -1, "Catch-all not found in coeffs")
            self.assertNotEqual(idx_corkscrew_rel, -1, "Corkscrew not found AFTER catch-all in coeffs")
            self.assertLess(idx_catch_all_rel, idx_corkscrew_rel, "Catch-all should appear BEFORE specific patches")

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
