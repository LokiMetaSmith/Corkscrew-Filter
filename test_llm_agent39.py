import json
from optimizer.parameter_validator import validate_parameters

last_params = {"number_of_complete_revolutions": 3.06, "num_bins": 1, "helix_path_radius_mm": 3.93, "helix_profile_radius_mm": 4.85, "helix_void_profile_radius_mm": 1.93, "helix_profile_scale_ratio": 1.71, "insert_length_mm": 45.4, "slit_axial_length_mm": 2.07, "slit_chamfer_height": 0.97, "target_cell_size": 1.95, "part_to_generate": "modular_filter_assembly", "add_layers": True}
print("Is it possible that these params WERE the ones in history?!")
print("If they were in history, `base_params = full_history[-1]['parameters']` makes `base_params` exactly this!")
print("But wait, if `_generate_random_parameters` is called with this `base_params`, it creates a NEW random set.")
print("Unless... `_generate_random_parameters` hits 100 max_attempts AND returns `new_params`.")
print("But wait! If it returns `new_params` after 100 attempts, `new_params` would STILL HAVE BEEN OVERWRITTEN BY `random.uniform` in the last attempt!")
print("So `new_params` would have `helix_profile_radius_mm` between 1.5 and 3.92.")
print("So `new_params` CANNOT be EXACTLY `last_params`!")
print("THE ONLY WAY it returns EXACTLY `last_params` is if `ordered_params` loop DOES NOT OVERWRITE IT!")
print("When does `ordered_params` loop not overwrite it?")
