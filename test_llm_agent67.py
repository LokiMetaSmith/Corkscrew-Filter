# Only in `_generate_random_parameters`!

# OKAY, what if `parameters_def` was passed correctly, and `ordered_params` WAS populated,
# AND it generated `helix_profile_radius_mm` = 4.85!
# HOW is that mathematically possible?!
# `current_p_max = min(5.0, new_params["helix_path_radius_mm"] - 0.01)`
# If `new_params["helix_path_radius_mm"]` was `> 4.86`, then `current_p_max` would be `> 4.85`!
# Then `random.uniform(1.5, current_p_max)` COULD return `4.85`!

# BUT if `new_params["helix_path_radius_mm"]` was `> 4.86`,
# WHY IS IT `3.93` IN THE LOG?!
# Could it be that `new_params["helix_path_radius_mm"]` was CHANGED AFTER `helix_profile_radius_mm` was generated?!
# What modifies `new_params["helix_path_radius_mm"]` AFTER `helix_profile_radius_mm`?
# In `ordered_params` loop, it iterates over `param_name`.
# If `helix_path_radius_mm` appears TWICE in `ordered_params`?!
# Let's check `ordered_params` construction!
