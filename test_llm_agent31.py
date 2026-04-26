import yaml
import json

with open('configs/corkscrew_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Ah! Look at the last run's parameters:
last_params = {"number_of_complete_revolutions": 1.06, "num_bins": 1, "helix_path_radius_mm": 2.76, "helix_profile_radius_mm": 2.7, "helix_void_profile_radius_mm": 0.9, "helix_profile_scale_ratio": 1.33, "insert_length_mm": 50.33, "slit_axial_length_mm": 2.89, "slit_chamfer_height": 0.26, "target_cell_size": 4.54, "part_to_generate": "modular_filter_assembly", "add_layers": True}

# Why did my simulation fail for the user?
# Wait! In the user log:
# "Testing parameters: {'number_of_complete_revolutions': 3.06, 'num_bins': 1, 'helix_path_radius_mm': 3.93, 'helix_profile_radius_mm': 4.85, 'helix_void_profile_radius_mm': 1.93, ...}"

# But in the `optimization_log.jsonl` provided here, the last line is DIFFERENT.
# Let's search `optimization_log.jsonl` for `3.06`!
