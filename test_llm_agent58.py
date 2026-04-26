import json

# Okay, wait.
# The user log says:
# "Testing parameters: {'number_of_complete_revolutions': 3.06, 'num_bins': 1, 'helix_path_radius_mm': 3.93, 'helix_profile_radius_mm': 4.85, 'helix_void_profile_radius_mm': 1.93, 'helix_profile_scale_ratio': 1.71, 'insert_length_mm': 45.4, 'slit_axial_length_mm': 2.07, 'slit_chamfer_height': 0.97, 'target_cell_size': 1.95, 'part_to_generate': 'modular_filter_assembly', 'add_layers': True}"

# Let's count the number of keys: 12.
# How many keys in `config['geometry']['parameters']`? 14.
# The missing keys are `tube_od_mm` and `GENERATE_CFD_VOLUME`!
# They are BOTH CONSTANT!
# WHY ARE THEY MISSING IN THE USER LOG?!
# If they were missing, then `base_params` DID NOT HAVE THEM!

# If `base_params` came from `full_history[-1]["parameters"]`, and `full_history[-1]["parameters"]` did NOT have them, then `new_params` will NOT have them!
# If `new_params` doesn't have them, `validate_parameters` will use default `32.0` and `1.0`.
# AND IT SUCCEEDS!
