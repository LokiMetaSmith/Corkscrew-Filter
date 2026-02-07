import unittest
import sys
import os

# Ensure we can import from optimizer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'optimizer')))

from parameter_validator import validate_parameters

class TestParameterValidator(unittest.TestCase):
    def setUp(self):
        # Baseline valid parameters (from config.scad defaults)
        self.base_params = {
            "tube_od_mm": 32,
            "tube_wall_mm": 1.5,
            "helix_path_radius_mm": 1.8,
            "helix_profile_radius_mm": 1.8,
            "helix_void_profile_radius_mm": 1.0,
            "insert_length_mm": 50
        }

    def test_valid_parameters(self):
        is_valid, msg = validate_parameters(self.base_params)
        self.assertTrue(is_valid, f"Expected valid, got invalid: {msg}")

    def test_self_intersection_center(self):
        # Profile larger than path -> crosses center axis
        params = self.base_params.copy()
        params["helix_path_radius_mm"] = 1.8
        params["helix_profile_radius_mm"] = 2.5 # > 1.8

        is_valid, msg = validate_parameters(params)
        self.assertFalse(is_valid)
        self.assertIn("self-intersection", msg.lower())

    def test_wall_thickness(self):
        # Void >= Profile -> no wall
        params = self.base_params.copy()
        params["helix_profile_radius_mm"] = 1.5
        params["helix_void_profile_radius_mm"] = 1.5

        is_valid, msg = validate_parameters(params)
        self.assertFalse(is_valid)
        self.assertIn("wall thickness", msg.lower())

    def test_tube_fit(self):
        # Helix too big for tube
        # Tube ID radius = (32/2) - 1.5 = 16 - 1.5 = 14.5
        params = self.base_params.copy()
        params["helix_path_radius_mm"] = 10
        params["helix_profile_radius_mm"] = 5
        # Outer radius = 15 > 14.5

        is_valid, msg = validate_parameters(params)
        self.assertFalse(is_valid)
        self.assertIn("intersect the tube", msg.lower())

    def test_negative_dimensions(self):
        params = self.base_params.copy()
        params["insert_length_mm"] = -10
        is_valid, msg = validate_parameters(params)
        self.assertFalse(is_valid)
        self.assertIn("positive", msg.lower())

    def test_user_failure_case(self):
        # specific case from user report
        params = {
            'part_to_generate': 'modular_filter_assembly',
            'num_bins': 1,
            'number_of_complete_revolutions': 2,
            'helix_path_radius_mm': 1.8,
            'helix_profile_radius_mm': 2.5,
            'helix_void_profile_radius_mm': 1.0,
            'helix_profile_scale_ratio': 1.4,
            'tube_od_mm': 32,
            'insert_length_mm': 50,
            'GENERATE_CFD_VOLUME': True
        }
        is_valid, msg = validate_parameters(params)
        self.assertFalse(is_valid)
        self.assertIn("self-intersection", msg.lower())

if __name__ == '__main__':
    unittest.main()
