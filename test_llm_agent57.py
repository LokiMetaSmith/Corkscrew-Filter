# If `current_params` was `config['geometry']['parameters']`!
# Then `new_params` STARTS with dicts!
# And for keys that are NOT in `ordered_params` (or `constant` keys), it REMAINS a dict!
# `tube_od_mm` has `constant: True`.
# So it is SKIPPED in `ordered_params` loop!
# So `new_params['tube_od_mm']` REMAINS `{'type': 'float', 'default': 32.0, 'constant': True}`.
# Then `validate_parameters(new_params)` is called.
# It does: `tube_od = float(params.get("tube_od_mm", 32))`
# Since `params.get("tube_od_mm")` is a dict, it raises `TypeError`!
# `except (ValueError, TypeError) as e: return False, f"Parameter type error: {e}"`
# So `validate_parameters` returns `False`!
# It does this for ALL 100 ATTEMPTS!
# After 100 attempts, it prints the warning, and returns the LAST `new_params`.
# But wait! If it returns the last `new_params`, `new_params['tube_od_mm']` would STILL BE A DICT!
# Look at the user log:
# "Testing parameters: {'number_of_complete_revolutions': 3.06, 'num_bins': 1, 'helix_path_radius_mm': 3.93, 'helix_profile_radius_mm': 4.85, ...}"
# THE USER LOG DOES NOT SHOW `tube_od_mm` IN THE PRINTED PARAMS!
# IT DOES NOT SHOW DICTS!
