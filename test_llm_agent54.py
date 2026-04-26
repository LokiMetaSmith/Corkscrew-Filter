# Ah!
# If `helix_path_radius_mm` WAS generated as >= 4.86,
# THEN `helix_profile_radius_mm` CAN BE 4.85!
# BUT the user log says:
# "Testing parameters: {'number_of_complete_revolutions': 3.06, 'num_bins': 1, 'helix_path_radius_mm': 3.93, 'helix_profile_radius_mm': 4.85, ...}"

# LOOK AT THE LOG!
# `helix_path_radius_mm` IS 3.93!
# `helix_profile_radius_mm` IS 4.85!

# So IF `helix_path_radius_mm` IS 3.93, how could `helix_profile_radius_mm` be 4.85?!
# ONLY if `helix_profile_radius_mm` was generated BEFORE `helix_path_radius_mm`?!
# Let's check `dependency_order`:
# 1. helix_path_radius_mm
# 2. helix_profile_radius_mm
# IT IS GENERATED AFTER.

# WHAT IF IT'S THE OTHER WAY AROUND?!
# "helix_profile_radius_mm" is modified:
# current_p_max = min(current_p_max, float(new_params["helix_path_radius_mm"]) - 0.01)
# Is `new_params["helix_path_radius_mm"]` 3.93?
# Yes!
# So `current_p_max` becomes 3.92.
# So `random.uniform(1.5, 3.92)` gives 4.85?!
# NO. IT'S PYTHON. `random.uniform(a, b)` gives `a <= N <= b`.
